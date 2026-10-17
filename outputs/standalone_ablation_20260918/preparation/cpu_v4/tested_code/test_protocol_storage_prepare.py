"""Authorization/accounting tests; only temporary metadata and synthetic attempts."""
from copy import deepcopy
from pathlib import Path
import json
import pytest

from . import prepare, protocol, storage


@pytest.fixture(scope='module')
def original_inputs():
    return prepare.build_inputs()


@pytest.fixture
def cfg(original_inputs):
    return deepcopy(original_inputs)


def authorize(cfg, directory, scopes=(protocol.PREFLIGHT, protocol.FORMAL)):
    ready_path=directory/'STANDALONE_ABLATION_ANALYSIS_READY.json'
    cfg.update(status='frozen',release_contract=prepare.ready_contract(cfg),
        preparation_binding={'synthetic_cpu_fixture':True})
    ready=dict(task_id=protocol.TASK_ID,status='approved',released_scope=list(scopes),
        task_document=cfg['task_document']['path'],task_document_sha256=cfg['task_document']['sha256'],
        standalone_ablation=deepcopy(cfg['release_contract']),
        standalone_preparation_binding=deepcopy(cfg['preparation_binding']))
    ready_path.write_text(json.dumps(ready))
    cfg['analysis_ready']=dict(path=str(ready_path),sha256=storage.sha256(ready_path))
    cfg['analysis_approval']=dict(status='approved',approved_by='analysis',protocol_sha256=protocol.protocol_digest(cfg))
    return cfg


def test_original_100_ids_98_cuts_old_seed_namespace_and_denominators(cfg):
    assert protocol.validate_config(cfg)['planned_sources']==100
    assert list(cfg['inputs']['sources'])==list(protocol.PRIMARY_IDS)
    assert sum(not s['no_cut'] for s in cfg['inputs']['sources'].values())==98
    assert sorted(s['common_outcome'] for s in cfg['inputs']['sources'].values() if s['no_cut'])==[False,True]
    assert cfg['execution_plans'][protocol.FORMAL]['expected_attempts']==98*(1+3*4)
    assert cfg['execution_plans'][protocol.PREFLIGHT]['expected_attempts'] in (30,50)
    assert cfg['seed_namespace']=='corrector_native10_training_20260916_v1'


def test_pending_and_old_ready_cannot_start(cfg,tmp_path):
    with pytest.raises(ValueError,match='Pending'):protocol.require_stage_budget(cfg,protocol.PREFLIGHT)
    cfg=authorize(cfg,tmp_path)
    cfg['analysis_ready']['path']=str(tmp_path/'NATIVE10_ANALYSIS_READY.json')
    cfg['analysis_approval']['protocol_sha256']=protocol.protocol_digest(cfg)
    with pytest.raises(ValueError,match='New standalone READY'):protocol.require_stage_budget(cfg,protocol.PREFLIGHT)


def test_exact_release_and_actual_inputs_bound(cfg,tmp_path):
    cfg=authorize(cfg,tmp_path)
    protocol.require_stage_budget(cfg,protocol.PREFLIGHT)
    cfg['inputs']['sources'][protocol.PRIMARY_IDS[0]]['scene_fingerprint']='tampered'
    cfg['analysis_approval']['protocol_sha256']=protocol.protocol_digest(cfg)
    with pytest.raises(ValueError,match='Source/ID content hash'):protocol.require_stage_budget(cfg,protocol.PREFLIGHT)
    cfg['inputs']['source_bindings_hash']=protocol.canonical_hash(cfg['inputs']['sources'])
    cfg['analysis_approval']['protocol_sha256']=protocol.protocol_digest(cfg)
    with pytest.raises(ValueError,match='Released contract'):protocol.require_stage_budget(cfg,protocol.PREFLIGHT)


def test_preparation_binding_not_interchangeable(cfg,tmp_path):
    cfg=authorize(cfg,tmp_path);cfg['preparation_binding']={'different':True}
    cfg['analysis_approval']['protocol_sha256']=protocol.protocol_digest(cfg)
    with pytest.raises(ValueError,match='preparation binding'):protocol.require_stage_budget(cfg,protocol.PREFLIGHT)


@pytest.mark.parametrize('field,value',[('capture_allowed',True),('replacement_allowed',True),
    ('training_allowed',True),('scene_append_allowed',True),('source_horizon',50),('gate_threshold',.1)])
def test_no_hidden_scope_or_science_changes(cfg,field,value):
    cfg[field]=value
    with pytest.raises(ValueError):protocol.validate_config(cfg)


def test_stage_total_and_zero_optimizer_guards(cfg,tmp_path,monkeypatch):
    cfg=authorize(cfg,tmp_path)
    monkeypatch.setattr(protocol,'require_preflight_pass',lambda _:None)
    assert protocol.require_stage_budget(cfg,protocol.FORMAL,used=1399,total_used=1449)['limit']==1400
    for args in (dict(stage=protocol.REPAIR),dict(stage=protocol.FORMAL,used=1400,total_used=1450),
                 dict(stage=protocol.FORMAL,used=1399,total_used=1500),
                 dict(stage=protocol.PREFLIGHT,resource='optimizer_updates'),
                 dict(stage=protocol.PREFLIGHT,requested=0)):
        with pytest.raises(ValueError):protocol.require_stage_budget(cfg,**args)


def test_formal_budget_entry_cannot_bypass_missing_preflight(cfg,tmp_path):
    cfg=authorize(cfg,tmp_path)
    with pytest.raises(ValueError,match='passed preflight'):
        protocol.require_stage_budget(cfg,protocol.FORMAL)


def test_same_freeze_preflight_condition_is_required_at_low_level(cfg,tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'new')
    cfg['protocol_version']='synthetic';cfg=authorize(cfg,tmp_path)
    folder=storage.ROOT/'protocols/synthetic';cp=folder/'config.json';fp=folder/'freeze.json'
    storage.dump(cp,cfg);storage.dump(fp,dict(config_sha256=storage.sha256(cp),files={str(cp):storage.sha256(cp)}))
    with pytest.raises(FileNotFoundError):protocol.require_stage_budget(cfg,protocol.FORMAL)
    audit=storage.ROOT/'preflight_audits/synthetic'
    storage.dump(audit/'result.json',dict(status='passed',config_sha256=storage.sha256(cp),
        freeze_sha256=storage.sha256(fp),expected_attempts=cfg['execution_plans'][protocol.PREFLIGHT]['expected_attempts']))
    storage.seal(audit,role='standalone_preflight_audit')
    protocol.require_stage_budget(cfg,protocol.FORMAL)
    frozen=json.loads(fp.read_text());frozen['unexpected_new_freeze']=True;fp.write_text(json.dumps(frozen))
    with pytest.raises(ValueError,match='Same-freeze'):
        protocol.require_stage_budget(cfg,protocol.FORMAL)


def ledger_fixture(tmp_path,monkeypatch):
    snapshot=tmp_path/'snapshot.jsonl';live=tmp_path/'old_live.jsonl'
    snapshot.write_text('closed original ledger\n');live.write_bytes(snapshot.read_bytes())
    config=dict(carry_in=dict(ledger={'path':str(snapshot),'sha256':storage.sha256(snapshot)},
        legacy_ledger_path=str(live)),analysis_approval={'protocol_sha256':'unit_fixture'})
    calls=[]
    def gate(cfg,stage,**kwargs):
        calls.append((stage,kwargs))
        if kwargs['used']+kwargs['requested']>protocol.CAPS[stage]:raise ValueError('stage cap')
    monkeypatch.setattr(protocol,'require_stage_budget',gate)
    ledger=storage.AttemptLedger(config,root=tmp_path/'new',lock_path=tmp_path/'lock')
    return ledger,live,calls


def test_failed_attempt_stays_counted_and_no_duplicate_or_capture(tmp_path,monkeypatch):
    ledger,live,calls=ledger_fixture(tmp_path,monkeypatch)
    entry=ledger.reserve(protocol.PREFLIGHT,'candidate_restore','source:bank:attempt0')
    assert entry['cumulative_simulator_attempts']==48184
    # Simulated downstream failure makes no deletion or refund.
    with pytest.raises(RuntimeError):raise RuntimeError('synthetic restore failure')
    with pytest.raises(ValueError,match='already reserved'):
        ledger.reserve(protocol.PREFLIGHT,'candidate_restore','source:bank:attempt0')
    for kind in ('capture','initialization_replacement'):
        with pytest.raises(ValueError):ledger.reserve(protocol.PREFLIGHT,kind,'forbidden')
    with pytest.raises(ValueError):ledger.reserve(protocol.PREFLIGHT,'candidate_restore','optimizer',resource='optimizer_updates')
    rows=[json.loads(x) for x in (ledger.root/'budget/attempts.jsonl').read_text().splitlines()]
    assert len(rows)==1 and len(calls)==1


def test_old_live_ledger_append_blocks_before_new_reservation(tmp_path,monkeypatch):
    ledger,live,calls=ledger_fixture(tmp_path,monkeypatch)
    with live.open('a') as stream:stream.write('unexpected old-workflow attempt\n')
    with pytest.raises(ValueError,match='carry-in ledger changed'):
        ledger.reserve(protocol.PREFLIGHT,'candidate_restore','new')
    assert not (ledger.root/'budget/attempts.jsonl').exists() and calls==[]


def test_two_ledger_clients_serialize_global_numbering(tmp_path,monkeypatch):
    first,live,calls=ledger_fixture(tmp_path,monkeypatch)
    second=storage.AttemptLedger(first.config,root=first.root,lock_path=first.lock_path)
    a=first.reserve(protocol.PREFLIGHT,'candidate_restore','one')
    b=second.reserve(protocol.FORMAL,'branch_including_restore','two')
    assert [a['number'],b['number']]==[1,2]
    assert calls[-1][1]['total_used']==1 and b['cumulative_simulator_attempts']==48185


def test_budget_hardcap_applies_across_stages(tmp_path,monkeypatch):
    ledger,live,calls=ledger_fixture(tmp_path,monkeypatch)
    path=ledger.root/'budget/attempts.jsonl';path.parent.mkdir(parents=True)
    rows=[dict(number=i+1,resource='simulator_attempts',amount=1,identity=str(i),stage=protocol.FORMAL)
          for i in range(1500)]
    path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    with pytest.raises(ValueError,match='hard limit'):
        ledger.reserve(protocol.PREFLIGHT,'candidate_restore','beyond')
    assert len(path.read_text().splitlines())==1500


def test_writes_cannot_reach_old_archives(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'new')
    with pytest.raises(ValueError,match='isolated'):storage.dump(tmp_path/'old/result.json',{})
    storage.dump(tmp_path/'new/result.json',{'status':'complete'})
    with pytest.raises(FileExistsError):storage.dump(tmp_path/'new/result.json',{'status':'overwrite'})


def test_unsealed_failure_file_rejects_previously_complete_artifact(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    folder=tmp_path/'complete';storage.dump(folder/'result.json',{'status':'passed'})
    storage.seal(folder,role='test');storage.sealed(folder)
    storage.dump(folder/'failure.json',{'error':'late synthetic failure'})
    with pytest.raises(ValueError,match='inventory'):storage.sealed(folder)


def test_recursive_inventory_covers_absolute_relative_and_snapshot(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'new')
    asset=tmp_path/'source.txt';asset.write_text('immutable authorization evidence')
    value={'deep':[{'path':str(asset),'sha256':storage.sha256(asset)},
                   {'path':asset.name,'sha256':storage.sha256(asset)}]}
    monkeypatch.setattr(storage,'PACKAGE',tmp_path)
    dest=storage.ROOT/'protocol';dest.mkdir(parents=True)
    rows=prepare._inventory(value,dest)
    assert len(rows)==1 and len(rows[0]['references'])==2
    assert all(storage.sha256(r['original_path'])==storage.sha256(r['snapshot_path'])==r['sha256'] for r in rows)
    asset.write_text('changed')
    with pytest.raises(ValueError,match='SHA'):prepare._inventory(value,storage.ROOT/'another')


def test_cpu_archive_rejects_stale_code_and_nonzero_runtime(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    code=tmp_path/'code';code.mkdir();module=code/'only.py';module.write_text('VALUE = 1\n')
    monkeypatch.setattr(prepare,'CODE',code)
    evidence=tmp_path/'cpu';evidence.mkdir();hashes={str(module):storage.sha256(module)}
    value=dict(status='passed',returncode=0,code_before=hashes,code_after=hashes,simulator_calls=0,model_calls=0,optimizer_updates=0)
    storage.dump(evidence/'result.json',value);storage.seal(evidence,role='synthetic_cpu_fixture')
    assert prepare.cpu_checks(evidence)==hashes
    module.write_text('VALUE = 2\n')
    with pytest.raises(ValueError,match='SHA'):prepare.cpu_checks(evidence)


def test_metadata_preflight_count_conflict_is_explicit(original_inputs):
    other=30 if original_inputs['execution_plans'][protocol.PREFLIGHT]['expected_attempts']==50 else 50
    with pytest.raises(ValueError,match='differs from actual TASK'):prepare.build_inputs(preflight_attempts=other)
