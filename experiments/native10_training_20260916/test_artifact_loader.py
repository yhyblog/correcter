"""Actual file-chain auditing against tiny MainCollector arithmetic stubs only."""
from copy import deepcopy
import json

import numpy as np
import pytest

from . import artifact_loader, dataset, storage, scene_identity, main_collection
from .artifact_loader import ArtifactAuditError, load_artifact_dataset, save_audited_dataset
from .dataset import load_saved_dataset
from .protocol import canonical_hash
from .test_main_collection import setup, approve


@pytest.fixture
def collected(setup,tmp_path,monkeypatch,request):
    config,case,build,document,ready=setup
    monkeypatch.setattr(storage,'LOCK_PATH',tmp_path/'synthetic_ledger.lock')
    monkeypatch.setattr(storage,'CACHE_PATH',tmp_path/'synthetic_ledger_cache.json')
    monkeypatch.setattr(scene_identity,'ROOT',storage.ROOT)
    monkeypatch.setattr(scene_identity,'LOCK',tmp_path/'synthetic_scene_registry.lock')
    config['scene_identity']={'schema':scene_identity.SCHEMA}
    def synthetic_scene(runtime,case,attempt,config,destination):
        def initial(_runtime):
            raw=dict(qpos=np.zeros(1),qvel=np.zeros(1),joint_type=np.asarray([3]),
                joint_qpos_address=np.asarray([0]),joint_dof_address=np.asarray([0]),
                target_pos=np.asarray([case['env_seed']*1e-6,0.,0.]),mocap_pos=np.empty((0,3)),
                model_body_pos=np.zeros((1,3)),model_site_pos=np.zeros((1,3)),model_geom_pos=np.zeros((1,3)),
                mocap_quat=np.empty((0,4)),model_body_quat=np.asarray([[1.,0.,0.,0.]]),
                model_site_quat=np.asarray([[1.,0.,0.,0.]]),model_geom_quat=np.asarray([[1.,0.,0.,0.]]),
                act=np.empty(0),runtime_physics_state=runtime.physics_state())
            return raw,dict(control_steps=0,native_path_length=0)
        monkeypatch.setattr(scene_identity,'read_initial_scene',initial)
        return scene_identity.capture_scene_identity(runtime,case,attempt,config,destination)
    monkeypatch.setattr(main_collection,'_capture_scene',synthetic_scene)
    documents={}
    for name in dataset.ANALYSIS_SOURCE_NAMES:
        path=storage.ROOT/'analysis_inputs'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('CPU synthetic analysis binding only: '+name)
        documents[str(path)]=storage.sha256(path)
    config['analysis_documents']=documents
    backup=None
    if getattr(request,'param',None) in ('mixed_bank','pending_source'):
        other=deepcopy(case)
        other.update(episode_id='disassemble-v3__9003',case_id='disassemble-v3__9003',env_seed=9003)
        if request.param=='mixed_bank':other.update(split='development',round=None)
        config['episode_manifest'].append(other)
        registration=config['main_collection']['banks']['labels_round1']
        registration['episode_ids'].append(other['episode_id'])
        registration['channel_radius_by_episode'][other['episode_id']]=.5
    if getattr(request,'param',None)=='reject_primary':
        backup=deepcopy(case)
        backup.update(episode_id='disassemble-v3__9002',case_id='disassemble-v3__9002',env_seed=9002,
                      replacement_of=case['episode_id'])
        config['episode_manifest'].append(backup)
        config['main_collection']['replacement_candidates']={case['episode_id']:[backup['episode_id']]}
        config['budget']['stages']['technical_reserve']=dict(simulator_attempts=20,training_updates=0)
        config['stage_release_scopes']['technical_reserve']='main_collection'
    collector,engine,_=build(success_at=12)
    original_context=engine.context
    def context(*args):
        result=original_context(*args)
        result['remaining']=np.asarray([(300-args[4])/300],np.float32)
        return result
    engine.context=context
    collector.ledger=storage.AttemptLedger(config)
    if backup is None:
        collector.collect_episode(case)
    else:
        original_reset=engine.runtime.reset
        def reset(selected,horizon):
            if selected['episode_id']==case['episode_id']:
                raise RuntimeError('Synthetic initialization fault before any action')
            return original_reset(selected,horizon)
        engine.runtime.reset=reset
        with pytest.raises(main_collection.MainSourceRejected,match='initialization_failed'):
            collector.collect_episode(case)
        collector.collect_episode(backup)
    return config,case,collector,document,ready


def load(collected,**kwargs):
    config,_,_,_,_=collected
    return load_artifact_dataset(config,'labels_round1',purpose='train',rounds=[1],**kwargs)


def test_main_collector_artifacts_pack_and_separate_frozen_ledger_audit_are_end_to_end(collected):
    config,case,_,_,_=collected
    audited=load(collected)
    assert audited['input_audit']['status']=='passed'
    assert all(audited['input_audit']['checks'].values())
    assert len(audited['input_audit']['referenced_attempts'])==58
    assert audited['packed']['arrays']['outcomes'].shape==(1,13,4)
    assert audited['packed']['arrays']['control_valid'].all()
    assert len(audited['input_audit']['episode_ids'])==1
    binding=save_audited_dataset('cpu_artifact_v1',audited)
    assert binding['input_protocol_sha256']==config['analysis_approval']['protocol_sha256']
    packed=load_saved_dataset(binding['path'],'train',canonical_hash(config['episode_manifest']))
    np.testing.assert_array_equal(packed['arrays']['outcomes'],audited['packed']['arrays']['outcomes'])
    from .training_pipeline import load_audited_dataset
    pipeline_pack=load_audited_dataset(binding,purpose='train',manifest=config['episode_manifest'])
    assert pipeline_pack['rows']==packed['rows']
    audit=json.loads(open(binding['input_audit_path']).read())
    snapshots=[row for row in audit['artifacts'] if row['role']=='budget_snapshot']
    assert len(snapshots)==1 and snapshots[0]['path'].endswith('dataset_audits/cpu_artifact_v1/budget_snapshot.jsonl')
    old_snapshot_hash=storage.sha256(snapshots[0]['path'])
    # Later training/capture reservations may append to live accounting; the
    # input evidence is a frozen byte snapshot, never its moving ledger hash.
    with (storage.ROOT/'budget/attempts.jsonl').open('a') as stream:
        stream.write('{}\n')
    assert storage.sha256(snapshots[0]['path'])==old_snapshot_hash
    for row in audit['artifacts']:
        assert storage.sha256(row['path'])==row['sha256']


def test_sealed_branch_tampering_is_detected_before_its_label_is_accepted(collected):
    _,case,collector,_,_=collected
    path=collector.branch_path(case,5,'a0',0)/'summary.json'
    row=json.loads(path.read_text());row['success']=False
    path.write_text(json.dumps(row))
    with pytest.raises(ArtifactAuditError,match='SHA mismatch'):
        load(collected)


def test_matching_modified_seal_does_not_bypass_ledger_or_raw_trajectory_checks(collected):
    _,case,collector,_,_=collected
    folder=collector.branch_path(case,5,'a0',0)
    path=folder/'summary.json'
    row=json.loads(path.read_text());row['budget_attempt']+=500
    path.write_text(json.dumps(row))
    complete=folder/'complete.json'
    seal=json.loads(complete.read_text());seal['files']['summary.json']=storage.sha256(path)
    complete.write_text(json.dumps(seal))
    with pytest.raises(ArtifactAuditError,match='Attempt kind'):
        load(collected)


def test_unsealed_missing_label_retains_episode_and_blocks_complete_audit(collected):
    _,case,collector,_,_=collected
    # A missing independent physical branch remains a technical gap even when
    # another logical slot happens to have identical raw commands.
    path=collector.branch_path(case,5,'a0',0)/'complete.json'
    path.unlink()
    audited=load(collected)
    assert audited['input_audit']['status']=='incomplete'
    assert not audited['input_audit']['checks']['branch_seals']
    assert audited['packed']['metadata']['planned_episode_count']==1
    assert audited['input_audit']['missing_artifacts'][0]['method']=='a0'


def test_ready_scope_is_checked_before_any_outcome_or_ledger_read(collected,monkeypatch):
    config,_,_,document,ready=collected
    approve(config,document,ready,release_main=False)
    monkeypatch.setattr(artifact_loader,'_ledger_snapshot',lambda:pytest.fail('Ledger read before main READY gate'))
    with pytest.raises(ValueError,match='has not released'):
        load(collected)


@pytest.mark.parametrize('purpose',['heldout','calibration','p0'])
def test_protected_outcome_purpose_is_rejected_before_filesystem_access(collected,monkeypatch,purpose):
    config,_,_,_,_=collected
    monkeypatch.setattr(artifact_loader,'_ledger_snapshot',lambda:pytest.fail('Protected split read'))
    with pytest.raises(ArtifactAuditError,match='forbidden'):
        load_artifact_dataset(config,'labels_round1',purpose=purpose)


def test_scene_provenance_stays_out_of_critic_inputs_and_is_retained_in_records(collected):
    # The registered manifest and source summaries already round-trip verbatim.
    # Scene files become source-seal evidence, never an extra observed STATE_KEY.
    audited=load(collected)
    assert set(dataset.STATE_KEYS)<=set(audited['packed']['arrays'])
    assert not any('scene' in name for name in audited['packed']['arrays'])
    assert audited['packed']['metadata']['records'][0]['source_summary']['case']==collected[1]


def test_registered_bank_cannot_silently_cross_round_or_split(collected):
    config,case,_,document,ready=collected
    another=deepcopy(case)
    another.update(episode_id='disassemble-v3__9002',case_id='disassemble-v3__9002',env_seed=9002,split='heldout')
    config['episode_manifest'].append(another)
    config['main_collection']['banks']['labels_round1']['episode_ids'].append(another['episode_id'])
    approve(config,document,ready)
    with pytest.raises(ArtifactAuditError,match='crosses split'):
        load(collected)


@pytest.mark.parametrize('collected',['reject_primary'],indirect=True)
def test_ordered_preaction_replacement_resolves_one_slot_and_charges_both_capture_attempts(collected):
    config,primary,_,_,_=collected
    audited=load(collected)
    assert audited['input_audit']['status']=='passed'
    assert len(audited['input_audit']['referenced_attempts'])==59
    assert audited['input_audit']['episode_ids']==[primary['episode_id']]
    row=audited['packed']['rows'][0]
    assert row['episode_id']=='disassemble-v3__9002' and row['planned_slot_id']==primary['episode_id']
    assert audited['packed']['metadata']['planned_episode_count']==1
    resolution=audited['input_audit']['slot_resolutions'][0]
    assert resolution['preceding_rejections'][0]['reason']=='initialization_failed'
    with (storage.ROOT/'sources'/row['episode_id']/'attempt.json').open() as stream:
        assert json.load(stream)['stage']=='technical_reserve'


@pytest.mark.parametrize('collected',['reject_primary'],indirect=True)
def test_outcome_based_replacement_is_rejected_even_with_a_consistent_resealed_file(collected):
    _,primary,_,_,_=collected
    folder=storage.ROOT/'sources'/primary['episode_id']
    path=folder/'rejection.json'
    row=json.loads(path.read_text());row['reason']='failed_episode_no_success'
    path.write_text(json.dumps(row))
    complete=folder/'complete.json'
    seal=json.loads(complete.read_text());seal['files']['rejection.json']=storage.sha256(path)
    complete.write_text(json.dumps(seal))
    with pytest.raises(ArtifactAuditError,match='valid pre-action rejection'):
        load(collected)


def test_actual_raw_commands_are_checked_even_if_someone_updates_their_file_seal(collected):
    _,case,collector,_,_=collected
    folder=collector.branch_path(case,5,'a0',0)
    path=folder/'trajectory.npz'
    with np.load(path,allow_pickle=False) as archive:
        values={name:archive[name].copy() for name in archive.files}
    values['actions'][5,0]+=.01
    with path.open('wb') as stream:
        np.savez_compressed(stream,**values)
    complete=folder/'complete.json'
    seal=json.loads(complete.read_text());seal['files']['trajectory.npz']=storage.sha256(path)
    complete.write_text(json.dumps(seal))
    with pytest.raises(ArtifactAuditError,match='Executed prefix'):
        load(collected)


def test_accepted_scene_must_have_the_same_registry_identity_and_exact_initial_state(collected):
    path=storage.ROOT/'scene_registry/entries.jsonl'
    entry=json.loads(path.read_text());entry['exact_state_sha256']='0'*64
    path.write_text(json.dumps(entry)+'\n')
    with pytest.raises(ArtifactAuditError,match='accepted-scene registry'):
        load(collected)


@pytest.mark.parametrize('collected',['mixed_bank'],indirect=True)
def test_mixed_train_development_bank_reads_only_requested_purpose(collected,monkeypatch):
    config,case,_,_,_=collected
    original=artifact_loader._resolve
    visited=[]
    def resolve(primary,*args):
        visited.append(primary['split'])
        return original(primary,*args)
    monkeypatch.setattr(artifact_loader,'_resolve',resolve)
    audited=load(collected)
    assert audited['input_audit']['status']=='passed' and visited==['train']
    assert audited['input_audit']['episode_ids']==[case['episode_id']]
    visited.clear()
    audited=load_artifact_dataset(config,'labels_round1',purpose='development')
    assert audited['input_audit']['status']=='incomplete' and visited==['development']
    assert audited['packed']['metadata']['planned_episode_count']==1
    assert audited['packed']['rows']==[]


@pytest.mark.parametrize('collected',['pending_source'],indirect=True)
def test_live_smoke_fixes_completed_set_before_ledger_and_keeps_pending_denominator(collected,monkeypatch):
    config,case,_,_,_=collected
    other=config['episode_manifest'][1]
    original=artifact_loader._ledger_snapshot
    def racing_ledger():
        # Simulate work publishing after the completed-collection snapshot.
        # Malformed sentinel contents ensure this audit cannot read those files.
        collection=storage.ROOT/'collections/collect/labels_round1'/other['case_id']
        collection.mkdir(parents=True)
        (collection/'complete.json').write_text('NOT PART OF THIS SNAPSHOT')
        source=storage.ROOT/'sources'/other['case_id']
        source.mkdir(parents=True)
        (source/'complete.json').write_text('NOT PART OF THIS SNAPSHOT')
        return original()
    monkeypatch.setattr(artifact_loader,'_ledger_snapshot',racing_ledger)
    audited=load(collected,completed_collections_only=True)
    assert audited['input_audit']['status']=='incomplete'
    assert audited['input_audit']['completed_collection_slot_ids']==[case['episode_id']]
    assert len(audited['input_audit']['referenced_attempts'])==58
    assert audited['packed']['metadata']['planned_episode_count']==2
    assert audited['packed']['arrays']['outcomes'].shape==(1,13,4)
    assert audited['input_audit']['missing_artifacts']==[
        dict(episode_id=other['episode_id'],kind='collection_unsealed_at_snapshot')]
