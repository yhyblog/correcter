"""Synthetic filesystem gates only: no real labels/models/physics are opened."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

import pytest

from experiments.native10_training_20260916 import round2_dataset_audit_v1 as audit, storage


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def reseal(path, protocol, **extra):
    complete = path/'complete.json'
    if complete.exists(): complete.unlink()
    storage.seal(path, protocol_sha256=protocol, **extra)


@pytest.fixture
def example(tmp_path, monkeypatch):
    root = tmp_path/'outputs'; root.mkdir()
    monkeypatch.setattr(storage, 'ROOT', root)
    monkeypatch.setattr(storage, 'LOCK_PATH', tmp_path/'ledger.lock')
    contract = root/'contract.md'; contract.write_text('synthetic explicit CPU permission')
    monkeypatch.setattr(audit, 'CONTRACT_SHA', storage.sha256(contract))
    protocol = 'a'*64
    cases = [dict(episode_id=f'task{i//60}__{2026111300+i}', case_id=f'task{i//60}__{2026111300+i}',
                  task=f'task{i//60}', env_seed=2026111300+i, split='train', round=2) for i in range(300)]
    ids = [c['episode_id'] for c in cases]
    backups = {}; registry = list(cases)
    for c in cases:
        backups[c['episode_id']] = []
        for n in range(2):
            b = dict(c, episode_id=c['episode_id']+f'_b{n}', case_id=c['case_id']+f'_b{n}',
                     env_seed=c['env_seed']+1000+n*300, replacement_of=c['episode_id'])
            registry.append(b); backups[c['episode_id']].append(b['episode_id'])
    readiness = root/'old/coordination/NATIVE10_TRAINING_READINESS_REVIEW.md'
    readiness.parent.mkdir(parents=True); readiness.write_text('synthetic prior readiness')
    readiness_sha = storage.sha256(readiness); monkeypatch.setattr(audit, 'READINESS_SHA', readiness_sha)
    old_path, old_freeze = root/'old/config.json', root/'old/freeze.json'
    write(old_path, dict(analysis_documents={str(readiness):readiness_sha}, analysis_approval={'protocol_sha256':'b'*64}))
    write(old_freeze, {'files':{str(readiness):readiness_sha, str(old_path):storage.sha256(old_path)}})
    monkeypatch.setattr(audit, 'BASE_CONFIG_SHA', storage.sha256(old_path))
    monkeypatch.setattr(audit, 'BASE_FREEZE_SHA', storage.sha256(old_freeze))
    hashes = {str(i):str(i)*64 for i in range(4)}
    cfg = dict(episode_manifest=registry,critic_assets=str(root/'selected'),analysis_documents={},
        analysis_approval={'protocol_sha256':protocol},
        budget={'stages':{'training_round1':{'simulator_attempts':0,'training_updates':19200},
                          audit.STAGE:{'simulator_attempts':17400,'training_updates':0},
                          'technical_reserve':{'simulator_attempts':1200,'training_updates':0}}},
        main_collection={'banks':{audit.BANK:{'episode_ids':ids,'critic_member_hashes':hashes}},
                         'replacement_candidates':backups},
        round2_collection={'original_collection':{'config_path':str(old_path),'config_sha256':storage.sha256(old_path),
            'freeze_path':str(old_freeze),'freeze_sha256':storage.sha256(old_freeze)},
            'selected_training':{'path':str(root/'models/round1'),'selected_seal_sha256':'c'*64}},
        round2_preparation={'scene_registry_before':{'sha256':'d'*64,'records':400}})
    config_path, freeze_path = root/'round2/config.json', root/'round2/freeze.json'
    write(config_path,cfg); write(freeze_path,{'files':{str(config_path):storage.sha256(config_path)}})
    wave = root/'round2_execution'/audit.STAGE/audit.BANK/'synthetic'
    write(wave/'wave_spec.json',dict(config_sha256=storage.sha256(config_path),freeze_sha256=storage.sha256(freeze_path),
        stage=audit.STAGE,bank_version=audit.BANK,workers=32,hold_idle=False,original_primary_slots=300))
    write(wave/'launch_result.json',dict(status='complete',returncode=0,lifecycle_covers_entire_wave=True,
        hold_idle=False,next_stage_automatically_started=False,command=['bash','lifecycle','--spec',str(wave/'wave_spec.json')]))
    rows = [dict(number=1,resource='training_updates',amount=19200,stage='training_round1',kind='optimizer',
                 identity='old',protocol_sha256='b'*64)]
    slots = {}
    for case in cases:
        identity=case['episode_id']; source=root/'sources'/identity
        write(source/'metadata.json',{'synthetic':True}); reseal(source,protocol)
        collection=root/'collections'/audit.STAGE/audit.BANK/identity
        write(collection/'summary.json',{'private_outcome_placeholder':'never parsed by the gate'})
        reseal(collection,protocol)
        resolution=root/'slot_resolution'/identity
        write(resolution/'resolution.json',dict(status='resolved',planned_slot_id=identity,resolved_episode_id=identity,
            task=case['task'],split='train',round=2,original_env_seed=case['env_seed'],resolved_env_seed=case['env_seed'],
            source_protocol_sha256=protocol,source_seal_sha256=storage.sha256(source/'complete.json'),
            substitution_after_outcome_forbidden=True,ordered_rejections=[]))
        reseal(resolution,protocol)
        slots[identity]=dict(status='complete',planned_slot_id=identity,resolved_episode_id=identity,
            resolution_path=str(resolution),completion_path=str(collection),completion_sha256=storage.sha256(collection/'complete.json'),
            ordered_rejections=[])
        rows.append(dict(number=len(rows)+1,resource='simulator_attempts',amount=1,stage=audit.STAGE,
                         kind='source_capture',identity=identity,protocol_sha256=protocol))
    for rank in range(32):
        worker=wave/'workers'/f'worker_{rank:02d}'
        assigned=ids[rank::32]
        for identity in assigned:write(worker/'slots'/f'{identity}.json',slots[identity])
        write(worker/'loaded_model_identity.json',dict(status='passed',selected_path=cfg['critic_assets'],model_hashes=hashes,
            model_paths=[str(Path(cfg['critic_assets'])/f'models/refit/member_{m}/selected.pt') for m in hashes],
            selected_seal_sha256='c'*64,checks=['actual_selector_paths','checkpoint_file_sha',
                'frozen_parameter_buffer_versions','eval_cpu_no_parameter_grad'],optimizer_updates=0,candidate_generation_only=True))
        write(worker/'status.json',dict(status='complete',stage=audit.STAGE,bank_version=audit.BANK,wave_id='synthetic',rank=rank,
            workers=32,config_sha256=storage.sha256(config_path),freeze_sha256=storage.sha256(freeze_path),
            protocol_sha256=protocol,assigned_slot_ids=assigned,completed_slot_records=len(assigned),missing_slot_ids=[],
            guard_factory='create_round2_collector',slot_entry='collect_round2_slot',next_stage_automatically_started=False))
        reseal(worker,protocol,role='guarded_round2_worker')
    ledger=root/'budget/attempts.jsonl'; ledger.parent.mkdir()
    ledger.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    calls=[]
    monkeypatch.setattr(audit,'_verify_frozen',lambda *args: cfg)
    def load(config,sources):
        calls.append('loader')
        assert sources[str(readiness)]==readiness_sha
        records=[dict(episode_id=x,planned_slot_id=x,status='no_cut') for x in ids]
        return dict(packed={'metadata':{'records':records,'planned_episode_count':300,'complete_critic_groups':0,
            'status_counts':{'no_cut':300},'complete_planned_selection_evidence':True}},
            input_audit=dict(status='passed',episode_ids=ids,protocol_sha256=protocol,
                referenced_attempts=list(range(2,302)),slot_resolutions=[dict(planned_slot_id=x,resolved_episode_id=x) for x in ids]),
            budget_snapshot=ledger.read_bytes())
    def save(version, audited):
        calls.append('save')
        return dict(path=str(root/'datasets'/version),seal_sha256='e'*64,input_audit_path=str(root/'dataset_audits'/version/'input_audit.json'),
                    input_audit_sha256='f'*64,input_protocol_sha256=protocol)
    monkeypatch.setattr(audit,'_load',load);monkeypatch.setattr(audit,'_save',save)
    return dict(root=root,cfg=cfg,config=config_path,freeze=freeze_path,wave=wave,contract=contract,
                rows=rows,ledger=ledger,ids=ids,calls=calls,protocol=protocol)


def run(e,version='new'):
    return audit.run_audit(e['config'],e['freeze'],'synthetic',version,contract_path=e['contract'])


def test_complete_wave_saves_original_protocol_and_all_300_nocut_records(example):
    e=example;r=run(e)
    assert r['status']=='passed' and r['planned_slot_count']==300 and r['complete_critic_groups']==0
    assert e['calls']==['loader','save']
    result=json.loads((Path(r['path'])/'result.json').read_text())
    assert result['dataset_binding']['input_protocol_sha256']==e['protocol']
    assert result['ledger']['new_optimizer_updates']==0 and result['wave_gate']['loaded_workers']==32
    assert result['readiness_supplement']['sha256']==audit.READINESS_SHA
    assert result['model_calls']==result['simulator_calls']==result['optimizer_updates']==result['pca_fits']==0
    assert storage.sha256(Path(r['path'])/'complete.json')==r['completion_audit']['seal_sha256']


@pytest.mark.parametrize('problem',['no_exit','failed_exit','missing_worker','missing_slot','unsealed_worker','wrong_assignment','wrong_model','wrong_resolution'])
def test_every_completion_gate_failure_precedes_loader(example,problem):
    e=example;worker=e['wave']/'workers/worker_00'
    if problem=='no_exit':(e['wave']/'launch_result.json').unlink()
    elif problem=='failed_exit':
        p=e['wave']/'launch_result.json';r=json.loads(p.read_text());r['returncode']=1;write(p,r)
    elif problem=='missing_worker':(worker/'complete.json').unlink();worker.rename(worker.with_name('unexpected'))
    elif problem=='missing_slot':
        (worker/'slots'/f"{e['ids'][0]}.json").unlink();reseal(worker,e['protocol'],role='guarded_round2_worker')
    elif problem=='unsealed_worker':(worker/'complete.json').unlink()
    elif problem=='wrong_assignment':
        p=worker/'status.json';r=json.loads(p.read_text());r['assigned_slot_ids']=r['assigned_slot_ids'][::-1];write(p,r)
        reseal(worker,e['protocol'],role='guarded_round2_worker')
    elif problem=='wrong_model':
        p=worker/'loaded_model_identity.json';r=json.loads(p.read_text());r['model_paths'][0]='wrong';write(p,r)
        reseal(worker,e['protocol'],role='guarded_round2_worker')
    else:
        p=e['root']/'slot_resolution'/e['ids'][0]/'resolution.json';r=json.loads(p.read_text());r['resolved_env_seed']+=1;write(p,r)
        reseal(p.parent,e['protocol'])
    with pytest.raises((ValueError,FileNotFoundError)):run(e)
    assert e['calls']==[]


@pytest.mark.parametrize('problem',['number_gap','negative_amount','training_update','stage_cap','reserve_cap','unregistered_stage','different_protocol_after_start'])
def test_full_ledger_fail_closed_before_loader(example,problem):
    e=example;rows=deepcopy(e['rows'])
    if problem=='number_gap':rows[-1]['number']+=1
    elif problem=='negative_amount':rows[-1]['amount']=-1
    elif problem=='training_update':rows[0]['amount']=19201
    elif problem=='stage_cap':e['cfg']['budget']['stages'][audit.STAGE]['simulator_attempts']=299
    elif problem=='reserve_cap':
        rows.append(dict(rows[-1],number=len(rows)+1,stage='technical_reserve',amount=1201))
    elif problem=='unregistered_stage':rows[-1]['stage']='forbidden'
    else:rows[-1]['stage']='technical_reserve';rows[-1]['protocol_sha256']='9'*64
    e['ledger'].write_text(''.join(json.dumps(x)+'\n' for x in rows))
    with pytest.raises(ValueError):run(e)
    assert e['calls']==[]


def test_retries_are_counted_and_unreferenced_charges_remain(example):
    e=example;rows=e['rows']
    for _ in range(2):
        rows.append(dict(number=len(rows)+1,stage=audit.STAGE,resource='simulator_attempts',amount=1,
                         kind='candidate_restore',identity='same_retry',protocol_sha256=e['protocol']))
    e['ledger'].write_text(''.join(json.dumps(x)+'\n' for x in rows))
    result=run(e);saved=json.loads((Path(result['path'])/'result.json').read_text())
    assert saved['ledger']['resource_totals']['simulator_attempts']==302
    assert saved['ledger']['unreferenced_charged_attempt_numbers']==[302,303]
    assert saved['ledger']['repeated_attempt_identities'][0]['attempts']==2


@pytest.mark.parametrize('problem',['readiness_bytes','old_freeze','contract'])
def test_document_provenance_cannot_be_substituted(example,problem):
    e=example
    if problem=='readiness_bytes':(e['root']/'old/coordination/NATIVE10_TRAINING_READINESS_REVIEW.md').write_text('changed')
    elif problem=='old_freeze':(e['root']/'old/freeze.json').write_text('{}')
    else:e['contract'].write_text('different permission')
    with pytest.raises(ValueError):run(e)
    assert e['calls']==[]


def test_no_technical_gate_parses_collection_outcomes(example,monkeypatch):
    original=audit._read
    def checked(path):
        if Path(path).name=='summary.json':pytest.fail('Gate parsed scientific outcome')
        return original(path)
    monkeypatch.setattr(audit,'_read',checked)
    assert run(example)['status']=='passed'


def test_real_loader_is_called_only_once_and_must_keep_ledger_snapshot(example,monkeypatch):
    e=example;original=audit._load
    def changed(*args):
        data=original(*args);data['budget_snapshot']+=b'\n';return data
    monkeypatch.setattr(audit,'_load',changed)
    with pytest.raises(ValueError,match='Ledger changed'):run(e)
    assert e['calls']==['loader']


def test_new_version_refuses_overwriting_existing_dataset(example):
    e=example;(e['root']/'datasets/new').mkdir(parents=True)
    with pytest.raises(FileExistsError):run(e)
    assert 'save' not in e['calls']


def test_loader_incomplete_result_is_sealed_as_incomplete_not_training_input(example,monkeypatch):
    original=audit._load
    def incomplete(*args):
        result=original(*args);result['input_audit']['status']='incomplete'
        result['packed']['metadata']['complete_planned_selection_evidence']=False
        return result
    monkeypatch.setattr(audit,'_load',incomplete)
    r=run(example)
    assert r['status']=='incomplete'
    assert not json.loads((Path(r['path'])/'result.json').read_text())['final_training_released']


@pytest.mark.parametrize('corrupt_attempt',[False, True])
def test_exhausted_registered_chain_is_accounted_independently_without_a_collection(example,monkeypatch,corrupt_attempt):
    e=example;identity=e['ids'][0];cfg=e['cfg'];worker=e['wave']/'workers/worker_00'
    chain=[identity]+cfg['main_collection']['replacement_candidates'][identity]
    cases={c['episode_id']:c for c in cfg['episode_manifest']};rejections=[]
    for index,key in enumerate(chain):
        source=e['root']/'sources'/cases[key]['case_id']
        if index==0:
            attempt=deepcopy(e['rows'][1])
        else:
            attempt=dict(number=len(e['rows'])+1,resource='simulator_attempts',amount=1,
                stage='technical_reserve',kind='source_capture',identity=cases[key]['case_id'],protocol_sha256=e['protocol'])
            e['rows'].append(attempt)
        write(source/'attempt.json',dict(attempt,amount=2) if corrupt_attempt and index==2 else attempt)
        write(source/'rejection.json',dict(episode_id=key,planned_slot_id=identity,reason='duplicate_initial_scene',
            budget_attempt=attempt['number'],before_first_action=True,outcome_not_observed=True,control_steps_executed=0))
        reseal(source,e['protocol'])
        rejections.append(dict(episode_id=key,reason='duplicate_initial_scene',budget_attempt=attempt['number'],before_first_action=True))
    e['ledger'].write_text(''.join(json.dumps(x)+'\n' for x in e['rows']))
    write(worker/'slots'/f'{identity}.json',dict(status='missing_unique_initial_scene',planned_slot_id=identity,
        resolved_episode_id=None,ordered_rejections=rejections,outcome_unknown=True))
    status=json.loads((worker/'status.json').read_text());status.update(status='complete_with_missing_slots',missing_slot_ids=[identity])
    write(worker/'status.json',status);reseal(worker,e['protocol'],role='guarded_round2_worker')
    original=audit._load
    def incomplete(*args):
        result=original(*args);result['input_audit']['status']='incomplete'
        result['input_audit']['slot_resolutions'][0]['resolved_episode_id']=None
        result['input_audit']['referenced_attempts'].remove(2)
        result['packed']['metadata']['complete_planned_selection_evidence']=False
        return result
    monkeypatch.setattr(audit,'_load',incomplete)
    if corrupt_attempt:
        with pytest.raises(ValueError,match='Rejected initialization attempt'):run(e)
        assert e['calls']==[]
    else:
        result=run(e);saved=json.loads((Path(result['path'])/'result.json').read_text())
        assert result['status']=='incomplete' and saved['wave_gate']['all_300_disposed']
        assert saved['coverage']['unresolved_or_exhausted_slot_ids']==[identity]
        assert saved['ledger']['independently_verified_rejection_attempt_numbers']==[2,302,303]
        assert saved['ledger']['resources_by_stage']['technical_reserve']['simulator_attempts']==2
