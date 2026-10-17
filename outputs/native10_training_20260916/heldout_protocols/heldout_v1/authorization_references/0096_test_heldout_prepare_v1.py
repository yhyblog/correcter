"""New held metadata integration only; synthetic inputs, no old79 test rerun."""
from copy import deepcopy
from pathlib import Path
import pytest
from . import heldout_prepare_v1 as prepare, storage
from .protocol import TASKS, canonical_hash
from .test_calibration_prepare_v1 import metadata as calibration_metadata, write


@pytest.fixture
def metadata(calibration_metadata, monkeypatch):
    m=calibration_metadata; old=deepcopy(m['old'])
    seeds=list(range(2026111750,2026111800))+list(range(2026111850,2026111900))
    rows=[];backups=[];mapping={}
    for i,seed in enumerate(seeds):
        task=TASKS[i%5];identity=f'{task}__{seed}'
        row=dict(episode_id=identity,case_id=identity,env_seed=seed,task=task,split='heldout',
                 round=None,source_horizon=10,cut_rule={'kind':'first_alarm'})
        rows.append(row);mapping[identity]=[]
        for ordinal in (1,2):
            replacement_seed=2026130000+i*2+ordinal
            replacement=f'{task}__{replacement_seed}'
            backups.append(dict(row,episode_id=replacement,case_id=replacement,env_seed=replacement_seed,
                replacement_of=identity,replacement_ordinal=ordinal));mapping[identity].append(replacement)
    old['episode_manifest']=rows+backups
    old['main_collection']['replacement_candidates']=mapping
    old['main_collection']['banks']={'calibration_policy_v1':old['main_collection']['banks']['round2_policy_v1']}
    old['calibration_collection']=dict(selected_training=old['policy_deployment']['selected_training'])
    old['calibration_preparation']=dict(registration_origin=old['policy_deployment']['old_collection'])
    old.pop('policy_deployment');old.pop('policy_preparation');old.pop('policy_statistics')
    old['matching'].update(shared_radius_dependencies='velocity/direct/post/reverse/random',amplitude_can_expand_native=True)
    write(m['base'],old)
    write(m['base'].with_name('freeze.json'),dict(files={str(m['base']):storage.sha256(m['base'])}))
    monkeypatch.setattr(prepare,'BASE_CONFIG_SHA',storage.sha256(m['base']))
    monkeypatch.setattr(prepare,'BASE_FREEZE_SHA',storage.sha256(m['base'].with_name('freeze.json')))
    monkeypatch.setattr(prepare,'validate_protocol',lambda *a,**kw:None)
    decision=write(m['package']/prepare.DECISION,{'synthetic':'preparation only'})
    monkeypatch.setattr(prepare,'DECISION_SHA',storage.sha256(decision))
    def selected(binding,*,require_actual=False):
        if require_actual and binding.get('status')=='pending_selection_seal':
            raise ValueError('Actual final selection seal is required')
        return {'synthetic':True}
    monkeypatch.setattr(prepare,'validate_final_selection_reference',selected)
    pending_selection=dict(status='pending_selection_seal',expected_directory=str(m['root']/'final_selections/v1'),
        preparation={'path':'synthetic'},payload={'path':'synthetic'})
    return dict(m,old=old,primary=rows,selection=pending_selection)


def config(m):
    return prepare.build_pending(m['base'],m['ready'],final_selection=m['selection'])


def test_new_held_registration_and_full_matched_post_science(metadata):
    m=metadata;cfg=config(m)
    for key in ('episode_manifest','source_horizon','prefix_horizon','suffix_horizon',
                'seed_namespace','guidance','matching','command_semantics','critic_assets','split_replicates'):
        assert cfg[key]==m['old'][key]
    assert cfg['main_collection']['replacement_candidates']==m['old']['main_collection']['replacement_candidates']
    assert len(prepare.assert_uninitialized(cfg))==300
    assert canonical_hash([r['episode_id'] for r in prepare.original_slots(cfg)])==prepare.PRIMARY_IDS_SHA
    assert cfg['heldout_collection']['original_collection']['bank_version']=='calibration_policy_v1'
    assert cfg['heldout_collection']['global_acceptance']['replicates']==2  # fixed calibration rule, never held reselection
    assert cfg['heldout_statistics']['replicates']==4
    assert cfg['heldout_statistics']==prepare.statistics_contract(cfg)
    assert cfg['heldout_preparation']['branch_upper_bound']==2000
    assert cfg['heldout_preparation']['simulator_attempts_upper_bound']==2200
    assert cfg['stage_release_scopes']['calibration']=='not_released_calibration'
    assert 'calibration_collection' not in cfg and 'calibration_preparation' not in cfg


def test_current_ready_denies_freeze_before_pending_access(metadata,monkeypatch):
    calls=[];read=prepare.read
    monkeypatch.setattr(prepare,'read',lambda path:(calls.append(Path(path)),read(path))[1])
    with pytest.raises(ValueError,match='explicitly release heldout'):
        prepare.freeze(metadata['root']/'absent',metadata['ready'],[],version='absent')
    assert calls==[metadata['ready']]
    assert not (metadata['root']/'heldout_protocols').exists()


def test_pending_selection_cannot_become_held_release(metadata):
    m=metadata;cfg=config(m)
    write(m['ready'],dict(task_id='native10-training-20260916',status='approved',
        released_scope=['heldout','heldout_initialization_replacements']))
    with pytest.raises(ValueError,match='Actual final selection'):
        prepare.release(m['ready'],cfg)


def test_wrong_registration_and_initialized_backup_denied(metadata):
    cfg=config(metadata);wrong=deepcopy(cfg);wrong['episode_manifest'][50]['env_seed']=2026111800
    with pytest.raises(ValueError,match='original ordered'):prepare.original_slots(wrong)
    backup=cfg['main_collection']['replacement_candidates'][cfg['episode_manifest'][0]['episode_id']][0]
    (metadata['root']/'sources'/backup).mkdir(parents=True)
    with pytest.raises(ValueError,match='initialized source'):prepare.assert_uninitialized(cfg)


def pending(m,monkeypatch,selection=None):
    from . import heldout_collection_v1 as collection
    registry=m['root']/'scene_registry/entries.jsonl';registry.parent.mkdir(parents=True,exist_ok=True)
    registry.write_text('{"episode_id":"prior_cal_source"}\n')
    monkeypatch.setattr(collection,'validate_heldout_inputs',lambda *a,**kw:{'status':'synthetic_passed'})
    out=m['root']/'held_pending'
    result=prepare.prepare_pending(m['base'],m['ready'],out,final_selection=selection or m['selection'])
    return out,result


def test_pending_records_metadata_prefix_and_non_runnable_selection(metadata,monkeypatch):
    m=metadata;out,result=pending(m,monkeypatch)
    cfg=prepare.read(out/'config.json');contract=prepare.read(out/'ready_contract.json')
    assert contract['paired_suffixes_per_state']==4 and contract['per_arm_outcome_denominator']==400
    assert contract['simulator_attempts_limit']==2200 and contract['optimizer_updates_limit']==0
    assert contract['actual_selection_seal_required'] is True
    assert contract['final_selection']['status']=='pending_selection_seal'
    assert contract['final_selection_result']=={'status':'not_created_pending_selection_seal'}
    assert contract['statistics']['primary_comparison']=='post_minus_alarm_replan10'
    assert contract['scientific_semantics']['matching']==m['old']['matching']
    assert prepare.read(out/'result.json')['runnable'] is False
    prefix=Path(cfg['heldout_preparation']['scene_registry_before']['snapshot_path']).read_bytes()
    (m['root']/'scene_registry/entries.jsonl').write_bytes(prefix+b'{"episode_id":"later"}\n')
    assert prepare.read(out/'ready_contract.json')==contract
    assert result['seal_sha256']==storage.sha256(out/'complete.json')


def test_synthetic_actual_seal_freeze_binds_inputs_inventory_and_new_stage(metadata,monkeypatch):
    from . import heldout_collection_v1 as collection,heldout_runner_v1 as runner
    m=metadata;fake=m['root']/'final_selection';fake.mkdir()
    write(fake/'complete.json',{'synthetic':True});write(fake/'result.json',{'method':'post'})
    binding=dict(path=str(fake),seal_sha256=storage.sha256(fake/'complete.json'),result_sha256=storage.sha256(fake/'result.json'))
    out,_=pending(m,monkeypatch,binding);cfg=prepare.read(out/'config.json')
    coverage={str(Path(prepare.__file__).resolve()):storage.sha256(prepare.__file__)}
    ready=dict(task_id='native10-training-20260916',version=999,status='protocol_approved_SYNTHETIC',
        released_scope=[prepare.SCOPE,prepare.RESERVE_SCOPE],task_document=prepare.DECISION,
        task_document_sha256=prepare.DECISION_SHA,protocol_review=prepare.DECISION,
        protocol_review_sha256=prepare.DECISION_SHA,heldout=prepare.ready_contract(cfg),
        heldout_preparation_binding=prepare._preparation_binding(out,[],coverage))
    write(m['ready'],ready);monkeypatch.setattr(prepare,'cpu_checks',lambda paths:coverage)
    calls=[];monkeypatch.setattr(prepare,'require_stage_budget',lambda c,s:calls.append(s))
    monkeypatch.setattr(runner,'verify_frozen',lambda *args:calls.append(args[2]))
    result=prepare.freeze(out,m['ready'],[],version='synthetic_only')
    actual=prepare.read(result['config']);frozen=prepare.read(result['freeze'])
    assert prepare.ready_contract(actual)==ready['heldout']
    assert frozen['simulator_attempts_limit']==2200 and frozen['training_updates_limit']==0
    assert prepare.verify_authorization_inventory(actual,frozen)['all_original_and_snapshot_files_frozen']
    assert actual['heldout_collection']['final_selection']==binding
    assert frozen['files'][str(fake/'complete.json')]==binding['seal_sha256']
    assert frozen['files'][str(fake/'result.json')]==binding['result_sha256']
    assert calls==['heldout','technical_reserve','heldout']
    with pytest.raises(FileExistsError):prepare.freeze(out,m['ready'],[],version='synthetic_only')
