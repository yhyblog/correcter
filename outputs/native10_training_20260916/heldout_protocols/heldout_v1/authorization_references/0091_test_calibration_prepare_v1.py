"""Small synthetic metadata tests: no actual data, models or simulator calls."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from . import calibration_prepare_v1 as prepare, storage
from .protocol import TASKS, canonical_hash


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def metadata(tmp_path, monkeypatch):
    package = tmp_path/'package'; root = package/'outputs'
    monkeypatch.setattr(storage, 'PACKAGE', package);monkeypatch.setattr(storage, 'ROOT', root)
    monkeypatch.setattr(prepare, 'validate_protocol', lambda *a, **kw: {'runnable': False})
    seeds = list(range(2026111700,2026111750))+list(range(2026111800,2026111850))
    primary = [dict(episode_id=f'{TASKS[i%5]}__{seed}',case_id=f'{TASKS[i%5]}__{seed}',
        task=TASKS[i%5],env_seed=seed,split='calibration',round=None,source_horizon=10,
        cut_rule={'kind':'first_alarm'}) for i,seed in enumerate(seeds)]
    backups=[];replacements={}
    for i,row in enumerate(primary):
        replacements[row['episode_id']]=[]
        for ordinal in (1,2):
            seed=2026120000+2*i+ordinal-1; identity=f'{row["task"]}__{seed}'
            backups.append(dict(row,episode_id=identity,case_id=identity,env_seed=seed,
                replacement_of=row['episode_id'],replacement_ordinal=ordinal))
            replacements[row['episode_id']].append(identity)
    selected = root/'models/final/final_fit_v1'; refs={}
    for name in ('complete.json','selected/complete.json','selected_reload_audit.json'):
        p=write(selected/name, {'synthetic':name});refs[name]=storage.sha256(p)
    review=write(package/'analysis/model_review.json',{'synthetic':True})
    members={str(i):str(i+1)*64 for i in range(4)}
    model_hashes=dict(vla='a'*64,d='b'*64,g0='c'*64,implementation='d'*64,
                      **{'critic_'+k:v for k,v in members.items()})
    original_config=write(root/'original/config.json',{'synthetic':True})
    original_freeze=write(root/'original/freeze.json',{'synthetic':True})
    old=dict(episode_manifest=primary+backups,source_horizon=10,prefix_horizon=10,suffix_horizon=10,
        seed_namespace='synthetic',control_budget=300,gate_threshold=.05,guidance={'alpha':10},
        matching={'boundary_clearance':.05},cpu={'worker_threads':4,'critic_threads':2},
        scene_identity={'schema':'synthetic'},command_semantics='raw',methods=prepare.ARMS,
        split_replicates={'train':4,'development':4,'calibration':2,'heldout':4},
        critic_assets=str(selected/'selected'),analysis_approval={'status':'approved'},
        policy_deployment=dict(selected_training=dict(path=str(selected),seal_sha256=refs['complete.json'],
            selected_seal_sha256=refs['selected/complete.json'],selected_reload_audit_sha256=refs['selected_reload_audit.json'],
            model_review={'path':str(review),'sha256':storage.sha256(review)}),
            old_collection=dict(config_path=str(original_config),config_sha256=storage.sha256(original_config),
                freeze_path=str(original_freeze),freeze_sha256=storage.sha256(original_freeze),bank_version='round1_labels_v1')),
        policy_preparation={'old':True},policy_statistics={'old':True},
        budget=dict(hard_total=50000,training_update_total=51200,count_failures=True,count_retries=True,
            stages={k:dict(simulator_attempts=n,training_updates=0) for k,n in
                    [('p0',600),('calibration',1200),('technical_reserve',1200),('heldout',2200)]}),
        main_collection=dict(concurrency={'workers_per_gpu':4},replacement_capture_stage='technical_reserve',
            replacement_candidates=replacements,banks={'round2_policy_v1':dict(random_seed_domain='original',
                model_hashes=model_hashes,critic_member_hashes=members)}))
    base=write(root/'base/config.json',old)
    freeze=write(root/'base/freeze.json',dict(files={str(base):storage.sha256(base)}))
    monkeypatch.setattr(prepare,'BASE_CONFIG_SHA',storage.sha256(base))
    monkeypatch.setattr(prepare,'BASE_FREEZE_SHA',storage.sha256(freeze))
    decision=write(package/prepare.DECISION,{'preparation_only':True})
    monkeypatch.setattr(prepare,'DECISION_SHA',storage.sha256(decision))
    ready=write(package/'coordination/NATIVE10_ANALYSIS_READY.json',dict(version=11,
        task_id='native10-training-20260916',status='protocol_approved_final_training',
        released_scope=['final_critic_training','round2_development_policy']))
    return dict(package=package,root=root,base=base,ready=ready,old=old,primary=primary)


def test_pending_preserves_full_registration_science_and_final_model(metadata):
    m=metadata;cfg=prepare.build_pending(m['base'],m['ready']);old=m['old']
    assert cfg['status']=='pending' and cfg['analysis_approval']=={'status':'pending'}
    for key in ('episode_manifest','seed_namespace','guidance','matching','critic_assets','split_replicates'):
        assert cfg[key]==old[key]
    assert cfg['main_collection']['replacement_candidates']==old['main_collection']['replacement_candidates']
    bank=cfg['main_collection']['banks'][prepare.BANK]
    assert bank['generation_round']==2 and bank['generation_phase']=='calibration'
    assert len(bank['episode_ids'])==100 and canonical_hash(bank['episode_ids'])==prepare.PRIMARY_IDS_SHA
    assert cfg['calibration_collection']['global_acceptance']==prepare.GLOBAL_ACCEPTANCE
    assert cfg['stage_release_scopes']['technical_reserve']==prepare.RESERVE_SCOPE
    assert cfg['stage_release_scopes']['heldout'].startswith('not_released_')
    assert 'policy_deployment' not in cfg
    assert not cfg['calibration_preparation']['physical_initial_uniqueness_established']


def test_v11_freeze_rejected_before_pending_reads_or_output(metadata,monkeypatch):
    calls=[];reader=prepare.read
    monkeypatch.setattr(prepare,'read',lambda path:(calls.append(Path(path)),reader(path))[1])
    with pytest.raises(ValueError,match='explicitly release calibration'):
        prepare.freeze(metadata['root']/'missing',metadata['ready'],[],version='not_created')
    assert calls==[metadata['ready']]
    assert not (metadata['root']/'calibration_protocols').exists()


def test_registration_wrong_seed_or_initialized_backup_denied(metadata):
    cfg=prepare.build_pending(metadata['base'],metadata['ready'])
    wrong=deepcopy(cfg);wrong['episode_manifest'][50]['env_seed']=2026111750
    with pytest.raises(ValueError,match='original ordered'):prepare.original_slots(wrong)
    ids=prepare.assert_uninitialized(cfg);assert len(ids)==300
    backup=cfg['main_collection']['replacement_candidates'][cfg['episode_manifest'][0]['episode_id']][0]
    (metadata['root']/'sources'/backup).mkdir(parents=True)
    with pytest.raises(ValueError,match='initialized source'):prepare.assert_uninitialized(cfg)


def test_pending_snapshot_allows_later_live_append_without_mutating_prefix(metadata,monkeypatch):
    from . import calibration_collection_v1 as collection
    registry=metadata['root']/'scene_registry/entries.jsonl';registry.parent.mkdir(parents=True)
    raw=b'{"episode_id":"earlier_training_source"}\n';registry.write_bytes(raw)
    seen=[]
    monkeypatch.setattr(collection,'validate_calibration_inputs',
        lambda cfg,bank,**kw:(seen.append((bank,kw)),{'status':'synthetic_passed'})[1])
    output=metadata['root']/'pending'
    result=prepare.prepare_pending(metadata['base'],metadata['ready'],output)
    assert seen==[(prepare.BANK,{'require_release':False})]
    cfg=prepare.read(output/'config.json');contract=prepare.read(output/'ready_contract.json')
    assert cfg['status']=='pending' and contract['arms']==prepare.ARMS
    assert contract['simulator_attempts_upper_bound']==1200 and contract['paired_suffixes_per_state']==2
    assert contract['heldout_initialization_allowed'] is False and contract['selection_seal_authorized'] is False
    assert contract['global_acceptance']==prepare.GLOBAL_ACCEPTANCE
    assert contract['initialization_replacement_scope']==prepare.RESERVE_SCOPE
    registry.write_bytes(raw+b'{"episode_id":"later_unrelated_append"}\n')
    snapshot=Path(cfg['calibration_preparation']['scene_registry_before']['snapshot_path'])
    assert snapshot.read_bytes()==raw
    assert result['seal_sha256']==storage.sha256(output/'complete.json')
    with pytest.raises(FileExistsError):prepare.prepare_pending(metadata['base'],metadata['ready'],output)


def inventory_fixture(metadata):
    root,package=metadata['root'],metadata['package']
    absolute=write(root/'review.json',{'review':'synthetic'})
    relative=write(package/'coordination/task.json',{'task':'synthetic'})
    source_config=write(root/'source/config.json',{'source':'synthetic'})
    source_freeze=write(root/'source/freeze.json',{'source_freeze':'synthetic'})
    seal=write(root/'sealed/complete.json',{'status':'complete'})
    ready=dict(task_document='coordination/task.json',task_document_sha256=storage.sha256(relative),
        nested=[dict(review=str(absolute),review_sha256=storage.sha256(absolute)),
            dict(source=dict(config_path=str(source_config),config_sha256=storage.sha256(source_config),
                             freeze_path=str(source_freeze),freeze_sha256=storage.sha256(source_freeze))),
            dict(path=str(seal.parent),seal_sha256=storage.sha256(seal))],
        code_sha256={str(absolute):storage.sha256(absolute)})
    return ready,[absolute,relative,source_config,source_freeze,seal]


def test_recursive_absolute_relative_and_stem_path_inventory(metadata):
    ready,paths=inventory_fixture(metadata)
    rows=prepare.authorization_references(ready)
    assert {x['original_path'] for x in rows}=={str(p) for p in paths}
    assert len(rows)==5 and len(next(x for x in rows if x['original_path']==str(paths[0]))['references'])==2
    dest=metadata['root']/'inventory';dest.mkdir()
    prepare.snapshot_authorization_references(ready,dest)
    ready_path=write(dest/'coordination/NATIVE10_ANALYSIS_READY.json',ready)
    inventory=dest/'authorization_inventory.json'
    cfg=dict(analysis_ready=dict(path=str(ready_path),sha256=storage.sha256(ready_path)),
        calibration_preparation={'authorization_inventory':dict(path=str(inventory),sha256=storage.sha256(inventory))})
    files={str(p):storage.sha256(p) for p in paths}
    files.update({str(p):storage.sha256(p) for p in dest.rglob('*') if p.is_file()})
    assert prepare.verify_authorization_inventory(cfg,{'files':files})['reference_count']==5
    del files[str(paths[0])]
    with pytest.raises(ValueError,match='omits authorization original'):
        prepare.verify_authorization_inventory(cfg,{'files':files})


def test_inventory_omission_and_changed_original_are_rejected(metadata):
    ready,paths=inventory_fixture(metadata);dest=metadata['root']/'inventory';dest.mkdir()
    record=prepare.snapshot_authorization_references(ready,dest)
    rp=write(dest/'coordination/NATIVE10_ANALYSIS_READY.json',ready);ip=dest/'authorization_inventory.json'
    cfg=dict(analysis_ready=dict(path=str(rp),sha256=storage.sha256(rp)),
        calibration_preparation={'authorization_inventory':dict(path=str(ip),sha256=storage.sha256(ip))})
    files={str(p):storage.sha256(p) for p in paths};files.update({str(p):storage.sha256(p) for p in dest.rglob('*') if p.is_file()})
    omitted=deepcopy(record);omitted['references'].pop();write(ip,omitted)
    cfg['calibration_preparation']['authorization_inventory']['sha256']=storage.sha256(ip)
    with pytest.raises(ValueError,match='exhaustively match'):prepare.verify_authorization_inventory(cfg,{'files':files})
    write(ip,record);cfg['calibration_preparation']['authorization_inventory']['sha256']=storage.sha256(ip)
    files[str(ip)]=storage.sha256(ip)
    paths[0].write_text('changed')
    with pytest.raises(ValueError,match='SHA mismatch'):prepare.verify_authorization_inventory(cfg,{'files':files})


def test_mutable_scene_and_ledger_need_immutable_authorization_snapshots(metadata):
    root=metadata['root'];snapshot=write(root/'prefix.json',{'prefix':'fixed'})
    for name in ('scene_registry/entries.jsonl','budget/attempts.jsonl'):
        live=root/name;live.parent.mkdir(parents=True,exist_ok=True);live.write_text('line\n')
        with pytest.raises(ValueError,match='immutable snapshot'):
            prepare.authorization_references(dict(path=str(live),sha256=storage.sha256(live)))
        refs=prepare.authorization_references(dict(scene_registry_before=dict(live_path=str(live),
            snapshot_path=str(snapshot),sha256=storage.sha256(snapshot))))
        assert [x['original_path'] for x in refs]==[str(snapshot)]
        live.write_text('line\nappend\n')
        assert storage.sha256(snapshot)==refs[0]['sha256']


def test_conflicting_or_unpaired_sha_rejected(metadata):
    path=write(metadata['root']/'review.json',{})
    with pytest.raises(ValueError,match='Conflicting'):
        prepare.authorization_references([{'path':str(path),'sha256':storage.sha256(path)},
                                         {'path':str(path),'sha256':'0'*64}])
    with pytest.raises(ValueError,match='Unpaired'):
        prepare.authorization_references({'nested':{'sha256':'1'*64}})


def freeze_fixture(metadata,monkeypatch):
    """Synthetic pending inputs and future READY; all execution gates are stubbed."""
    from . import calibration_collection_v1 as collection, calibration_runner_v1 as runner
    cfg=prepare.build_pending(metadata['base'],metadata['ready'])
    pending=metadata['root']/'prepared';pending.mkdir()
    registry=metadata['root']/'scene_registry/entries.jsonl';registry.parent.mkdir(parents=True)
    registry.write_text('{"episode_id":"earlier"}\n')
    snapshot=pending/'scene_registry_before.jsonl';snapshot.write_bytes(registry.read_bytes())
    cfg['calibration_preparation']['scene_registry_before']=dict(live_path=str(registry),
        snapshot_path=str(snapshot),sha256=storage.sha256(snapshot),bytes=snapshot.stat().st_size,records=1)
    storage.dump(pending/'config.json',cfg)
    storage.dump(pending/'ready_contract.json',prepare.ready_contract(cfg))
    storage.seal(pending,role='calibration_isolated_preparation',simulator_attempts=0,optimizer_updates=0)
    coverage={str(Path(prepare.__file__).resolve()):storage.sha256(prepare.__file__)}
    ready=dict(task_id='native10-training-20260916',version=999,status='protocol_approved_SYNTHETIC',
        released_scope=[prepare.SCOPE,prepare.RESERVE_SCOPE],task_document=prepare.DECISION,
        task_document_sha256=prepare.DECISION_SHA,protocol_review=prepare.DECISION,
        protocol_review_sha256=prepare.DECISION_SHA,calibration=prepare.ready_contract(cfg),
        calibration_preparation_binding=prepare._preparation_binding(pending,[],coverage))
    write(metadata['ready'],ready)
    calls=[]
    monkeypatch.setattr(prepare,'cpu_checks',lambda paths:coverage)
    monkeypatch.setattr(prepare,'require_stage_budget',lambda cfg,stage:calls.append(('scope',stage)))
    monkeypatch.setattr(collection,'validate_calibration_inputs',
        lambda cfg,bank,**kw:(calls.append(('validator',kw['require_release'])),{'status':'synthetic_passed'})[1])
    monkeypatch.setattr(runner,'verify_frozen',lambda *args:calls.append(('runner',args[2:])))
    return pending,cfg,ready,calls


def test_freeze_orchestration_binds_inventory_and_stable_scene_reference(metadata,monkeypatch):
    pending,original,ready,calls=freeze_fixture(metadata,monkeypatch)
    result=prepare.freeze(pending,metadata['ready'],[],version='synthetic_freeze')
    cfg=prepare.read(result['config']);frozen=prepare.read(result['freeze'])
    assert cfg['status']=='frozen'
    assert prepare.ready_contract(cfg)==ready['calibration']
    current=cfg['calibration_preparation']['scene_registry_before']
    previous=cfg['calibration_preparation']['authorized_scene_registry_before']
    assert current['snapshot_path']!=previous['snapshot_path']
    assert Path(current['snapshot_path']).read_bytes()==Path(previous['snapshot_path']).read_bytes()
    assert prepare.verify_authorization_inventory(cfg,frozen)['all_original_and_snapshot_files_frozen']
    assert ('validator',False) in calls and ('validator',True) in calls
    assert ('scope','calibration') in calls and ('scope','technical_reserve') in calls
    assert calls[-1]==('runner',('calibration',prepare.BANK,32))
    assert prepare.read(result['config'])['analysis_ready']['sha256']==storage.sha256(metadata['ready'])
    with pytest.raises(FileExistsError):prepare.freeze(pending,metadata['ready'],[],version='synthetic_freeze')


def test_ready_mutation_after_release_rejected_before_freeze_output(metadata,monkeypatch):
    pending,_,ready,_=freeze_fixture(metadata,monkeypatch)
    release=prepare.release
    def changed(path,cfg):
        output=release(path,cfg)
        later=deepcopy(ready);later['calibration']['simulator_attempts_limit']=1201
        write(path,later)
        return output
    monkeypatch.setattr(prepare,'release',changed)
    with pytest.raises(ValueError,match='SHA mismatch'):
        prepare.freeze(pending,metadata['ready'],[],version='race_rejected')
    assert not (metadata['root']/'calibration_protocols/race_rejected').exists()


@pytest.mark.parametrize('changed', ['missing','pending','cpu','code'])
def test_exact_ready_preparation_binding_required_before_destination(metadata,monkeypatch,changed):
    pending,_,ready,_=freeze_fixture(metadata,monkeypatch)
    assert prepare.expected_preparation_binding(pending,[])==ready['calibration_preparation_binding']
    if changed=='missing':
        del ready['calibration_preparation_binding']
    elif changed=='pending':
        other=metadata['root']/'other_pending';other.mkdir()
        (other/'complete.json').write_bytes((pending/'complete.json').read_bytes())
        ready['calibration_preparation_binding']['pending_inputs']['path']=str(other)
    elif changed=='cpu':
        # A well-formed reference that differs from the supplied CPU argument.
        ready['calibration_preparation_binding']['cpu_evidence']=[
            dict(path=str(pending),seal_sha256=storage.sha256(pending/'complete.json'))]
    else:
        ready['calibration_preparation_binding']['code_sha256']={}
    write(metadata['ready'],ready)
    with pytest.raises(ValueError,match='READY must bind these exact'):
        prepare.freeze(pending,metadata['ready'],[],version='wrong_binding')
    assert not (metadata['root']/'calibration_protocols/wrong_binding').exists()
