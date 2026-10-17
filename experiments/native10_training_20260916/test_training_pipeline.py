"""Synthetic pipeline tests; real data, old assets and optimizer fits are forbidden."""
from copy import deepcopy
import json

import numpy as np
import pytest
import torch

from experiments.native10_training_20260916 import storage
from experiments.native10_training_20260916 import training_pipeline as pipeline
from experiments.native10_training_20260916.protocol import (
    TASKS, ProtocolError, canonical_hash, episode_key, pending_protocol,
)
from experiments.native10_training_20260916.training import (
    checkpoint_state, dedup_weights, initialize_model,
)
from experiments.native10_training_20260916.test_training import preprocessing, state_arrays


def rows(n, split='train', start=930000):
    return [dict(episode_id=episode_key(TASKS[i % 5], start+i), task=TASKS[i % 5],
                 env_seed=start+i, split=split, round=1 if split == 'train' else None)
            for i in range(n)]


def synthetic_arrays(n):
    values = {key: value.numpy() for key, value in state_arrays(n).items()}
    values['actions'] = np.zeros((n, 13, 10, 4), np.float32)
    values['outcomes'] = np.zeros((n, 13, 4), np.bool_)
    values['group_ids'] = np.zeros((n, 13), np.int64)
    values.update({key: value.numpy() for key, value in dedup_weights(values['group_ids']).items()})
    return values


def pack(manifest, selected, count, purpose):
    complete = selected[:count]
    records = [dict(episode_id=row['episode_id'], status='complete', critic_eligible=True,
                    control_complete=True) for row in complete]
    records += [dict(episode_id=row['episode_id'], status='no_cut', critic_eligible=False,
                     full_episode_outcome_available=True, native10_outcome=True)
                for row in selected[count:]]
    return dict(rows=complete, arrays=synthetic_arrays(count), metadata=dict(
        records=records, purpose=purpose, planned_episode_count=len(selected),
        complete_planned_selection_evidence=True, manifest_sha256=canonical_hash(manifest)))


@pytest.fixture
def root(tmp_path, monkeypatch):
    output = tmp_path/'workflow'
    output.mkdir()
    monkeypatch.setattr(storage, 'ROOT', output)
    return output


@pytest.fixture
def states():
    return [checkpoint_state(initialize_model('B', seed=71+i, preprocessing=preprocessing())) for i in range(4)]


def test_pending_run_rejects_before_any_real_dataset_or_weight_read(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Pending pipeline reached real data/old weights')
    monkeypatch.setattr(pipeline, 'load_audited_dataset', forbidden)
    monkeypatch.setattr(pipeline, 'load_old_members', forbidden)
    for phase in ('round1', 'final'):
        with pytest.raises(ProtocolError):
            pipeline.run(pending_protocol(), None, phase=phase, version='synthetic')


def test_export_loads_frozen_selector_and_real_objective_arithmetic_with_synthetic_inputs(root, states):
    selector = pipeline.export_ensemble(states, root/'synthetic_export', provenance={'synthetic': True})
    models = pipeline.frozen_models(states)
    arrays = synthetic_arrays(2)
    arrays['actions'][:, 1] = .03
    arrays['actions'][:, 11] = -.02
    audit = pipeline.audit_reload(models, selector, arrays, rows(2))
    assert audit['status'] == 'passed' and audit['source_count'] == 2
    assert audit['feature_cache_bit_exact']
    assert audit['member_and_ensemble_gradient_bit_exact']
    assert audit['gradient_slots'] == [0, 11]
    assert audit['a0_anchor_exactly_zero'] and audit['state_and_anchor_immutable']
    assert audit['members_checked']==4
    assert selector.verify(check_files=True)
    with pytest.raises(FileExistsError):
        pipeline.export_ensemble(states, root/'synthetic_export', provenance={})
    with pytest.raises(ValueError, match='within the new workflow'):
        pipeline.export_ensemble(states, root.parent/'outside', provenance={})
    # A changed cached input cannot be waved through as numerical tolerance.
    selector.models[0].visual_center.add_(1)
    with pytest.raises(ValueError, match='probabilities changed|feature|changed'):
        pipeline.audit_reload(models, selector, arrays, rows(2))


def test_old_import_verifies_ranking_and_checkpoint_sha_before_each_load(root, states, monkeypatch):
    directory = root/'old_synthetic_assets'
    selector = pipeline.export_ensemble(states, directory, provenance={'synthetic': True})
    spec = dict(ranking=str((directory/'ranking.json').relative_to(root)),
                ranking_sha256=storage.sha256(directory/'ranking.json'),
                files={str(path.relative_to(root)): selector.ranking['model_hashes'][str(i)]
                       for i, path in enumerate(selector.model_paths)})
    imported, audit = pipeline.load_old_members(root, spec)
    assert len(imported) == 4 and audit['read_only']
    assert all(torch.equal(imported[i]['state.0.weight'], states[i]['state.0.weight']) for i in range(4))
    bad = deepcopy(spec);bad['ranking_sha256'] = '0'*64
    monkeypatch.setattr(torch, 'load', lambda *a, **k: pytest.fail('SHA failure reached checkpoint deserialization'))
    with pytest.raises(ValueError, match='SHA mismatch'):
        pipeline.load_old_members(root, bad)


def test_development_no_cut_full_denominator_and_unknown_outcome_block():
    manifest = rows(3, split='development')
    packed = pack(manifest, manifest, 2, 'development')
    packed['arrays']['outcomes'][0, 0] = [False, False, True, True]
    packed['arrays']['outcomes'][0, 1] = [True, True, False, True]
    packed['arrays']['group_ids'] = np.tile(np.arange(13), (2, 1))
    packed['arrays'].update({key: value.numpy() for key, value in dedup_weights(packed['arrays']['group_ids']).items()})
    probabilities = np.full((4, 2, 13), .2, np.float32);probabilities[:, 0, 1] = .8
    metrics, full = pipeline.development_selection(packed, probabilities)
    assert metrics['planned_episodes'] == 3 and metrics['reached_episodes'] == 2
    assert metrics['rescues'] == 2 and metrics['harms'] == 1
    assert metrics['gain'] == pytest.approx(1/12)
    assert metrics['gain_conditional'] == pytest.approx(1/8)
    assert np.isnan(full['member_probabilities'][:, 2]).all()
    assert full['outcomes'][2].all() and metrics['selected_slots'][2] == 0
    bad = deepcopy(packed);bad['metadata']['records'][2]['native10_outcome'] = None
    with pytest.raises(ValueError, match='Unknown technical'):
        pipeline.development_selection(bad, probabilities)
    bad = deepcopy(packed);bad['metadata']['records'][1]['control_complete'] = False
    with pytest.raises(ValueError, match='Incomplete development'):
        pipeline.development_selection(bad, probabilities)


def test_phase_coverage_retains_all_planned_sources_and_rejects_cross_round():
    train_rows, dev_rows = rows(300), rows(100, 'development', 940000)
    manifest = train_rows+dev_rows
    train, dev = pack(manifest, train_rows, 18, 'train'), pack(manifest, dev_rows, 1, 'development')
    audit = pipeline.validate_phase_datasets(train, dev, manifest, 'round1')
    assert audit['train_planned'] == 300 and audit['train_reached'] == 18
    assert audit['development_planned'] == 100
    bad = deepcopy(train);bad['metadata']['records'].pop()
    with pytest.raises(ValueError, match='lost/replaced'):
        pipeline.validate_phase_datasets(bad, dev, manifest, 'round1')
    bad = deepcopy(train);bad['rows'][0]['round'] = 2
    with pytest.raises(ValueError, match='episode/round'):
        pipeline.validate_phase_datasets(bad, dev, manifest, 'round1')


def test_registered_initialization_replacement_keeps_primary_denominator_and_actual_identity():
    train_rows, dev_rows = rows(300), rows(100, 'development', 940000)
    backup = dict(dev_rows[0], env_seed=950000,
                  episode_id=episode_key(dev_rows[0]['task'], 950000), replacement_of=dev_rows[0]['episode_id'])
    manifest = train_rows+dev_rows+[backup]
    train, dev = pack(manifest, train_rows, 18, 'train'), pack(manifest, dev_rows, 1, 'development')
    dev['rows'][0] = dict(backup, planned_slot_id=dev_rows[0]['episode_id'])
    dev['metadata']['records'][0].update(episode_id=backup['episode_id'], planned_slot_id=dev_rows[0]['episode_id'])
    coverage = pipeline.validate_phase_datasets(train, dev, manifest, 'round1')
    assert coverage['development_planned'] == 100
    metrics, _ = pipeline.development_selection(dev, np.full((4, 1, 13), .4, np.float32))
    assert metrics['episode_ids'][0] == backup['episode_id']
    assert metrics['planned_slot_ids'][0] == dev_rows[0]['episode_id']
    assert metrics['planned_episodes'] == 100
    bad = deepcopy(dev);bad['rows'][0]['planned_slot_id'] = dev_rows[1]['episode_id']
    with pytest.raises(ValueError, match='replacement slot'):
        pipeline.validate_phase_datasets(train, bad, manifest, 'round1')


def test_dataset_audit_must_bind_upstream_bytes_not_just_pack_seal(root, monkeypatch):
    from experiments.native10_training_20260916 import dataset
    manifest = rows(1, 'development')
    packed = pack(manifest, manifest, 0, 'development')
    directory = root/'datasets'/'synthetic';directory.mkdir(parents=True)
    (directory/'complete.json').write_text('{}')
    evidence = root/'evidence';evidence.mkdir()
    source = evidence/'source.json';source.write_text('{"synthetic":true}')
    budget = evidence/'budget.json';budget.write_text('[]')
    audit_path = evidence/'input_audit.json'
    audit = dict(schema='native10_input_artifact_audit_v1', status='passed', purpose='development',
                 dataset_seal_sha256=storage.sha256(directory/'complete.json'),
                 manifest_sha256=canonical_hash(manifest), protocol_sha256='a'*64,
                 episode_ids=[manifest[0]['episode_id']], checks={key: True for key in pipeline.INPUT_CHECKS},
                 artifacts=[dict(path=str(path), sha256=storage.sha256(path), role=role)
                            for path, role in ((source, 'source'), (budget, 'budget_snapshot'))])
    audit_path.write_text(json.dumps(audit))
    binding = dict(path=str(directory), seal_sha256=audit['dataset_seal_sha256'],
                   input_audit_path=str(audit_path), input_audit_sha256=storage.sha256(audit_path),
                   input_protocol_sha256='a'*64)
    monkeypatch.setattr(dataset, 'load_saved_dataset', lambda *a, **k: deepcopy(packed))
    assert pipeline.load_audited_dataset(binding, purpose='development', manifest=manifest)['rows'] == []
    source.write_text('changed after source audit')
    with pytest.raises(ValueError, match='SHA mismatch'):
        pipeline.load_audited_dataset(binding, purpose='development', manifest=manifest)
    source.write_text('{"synthetic":true}');audit['checks']['suffix_pairing'] = False
    audit_path.write_text(json.dumps(audit));binding['input_audit_sha256'] = storage.sha256(audit_path)
    with pytest.raises(ValueError, match='incomplete or unbound'):
        pipeline.load_audited_dataset(binding, purpose='development', manifest=manifest)


def synthetic_environment(root,states,monkeypatch):
    train_rows, dev_rows = rows(300), rows(100, 'development', 940000)
    manifest = train_rows+dev_rows
    train, dev = pack(manifest, train_rows, 18, 'train'), pack(manifest, dev_rows, 1, 'development')
    design = root/'synthetic_design.json'
    design.write_text(json.dumps(dict(schema_version=2, task_id='native10-training-20260916', old_weight_import={})))
    collection_config=root/'collection_config.json'
    collection_config.write_text(json.dumps(dict(episode_manifest=manifest,analysis_approval=dict(protocol_sha256='c'*64))))
    collection_freeze=root/'collection_freeze.json'
    collection_freeze.write_text(json.dumps(dict(files={str(collection_config):storage.sha256(collection_config)})))
    collection=dict(config_path=str(collection_config),config_sha256=storage.sha256(collection_config),
                    freeze_path=str(collection_freeze),freeze_sha256=storage.sha256(collection_freeze))
    cfg = dict(seed_namespace='synthetic_test_only', episode_manifest=manifest,
               analysis_approval=dict(protocol_sha256='0'*64),
               budget=dict(training_update_total=51200,stages={'round1_fit_preflight':dict(simulator_attempts=0,training_updates=0)}),
               stage_release_scopes={'round1_fit_preflight':'round1_fit_preflight'},
               training_pipeline=dict(design=dict(path=str(design), sha256=storage.sha256(design)),
                   code_files=pipeline.training_code_files(),
                   collection=collection,
                   stop_after={'round1': {'A': 200, 'B': 200}},
                   datasets={'round1': {purpose: dict(seal_sha256=letter*64,input_protocol_sha256='c'*64)
                            for purpose, letter in (('train', 'a'), ('development', 'b'))}}))
    ready=root/'NATIVE10_ANALYSIS_READY.json'
    ready.write_text(json.dumps(dict(released_scope=['round1_fit_preflight'],round1_fit_preflight=dict(
        stage='round1_fit_preflight',scope='round1_fit_preflight',simulator_attempts_limit=0,
        optimizer_updates_limit=0,training_updates=0,input_config_sha256=collection['config_sha256'],
        input_freeze_sha256=collection['freeze_sha256']))))
    cfg['analysis_ready']=dict(path=str(ready),sha256=storage.sha256(ready))
    gates=[]
    monkeypatch.setattr(pipeline, 'require_stage_budget', lambda config, stage, **kw: gates.append((stage, kw)))
    monkeypatch.setattr(pipeline, 'validate_protocol', lambda *a,**kw:dict(runnable=True))
    monkeypatch.setattr(pipeline, 'load_audited_dataset', lambda binding, *, purpose, manifest: deepcopy(train if purpose == 'train' else dev))
    monkeypatch.setattr(pipeline, 'load_old_members', lambda *args: (states, dict(synthetic=True)))
    monkeypatch.setattr(torch.optim,'AdamW',lambda *a,**kw:pytest.fail('Synthetic pipeline test created an optimizer'))
    return cfg,train,dev,gates


def test_synthetic_mocked_fit_orchestrates_both_paths_four_members_and_selects_once(root, states, monkeypatch):
    """No optimizer exists here: a mock emits one unchanged synthetic checkpoint."""
    cfg,train,dev,gates=synthetic_environment(root,states,monkeypatch)
    monkeypatch.setattr(pipeline,'fit_member',lambda *a,**kw:pytest.fail('Fit invoked during preflight'))
    binding=pipeline.preflight(cfg,phase='round1',version='synthetic_preflight')
    cfg['training_pipeline']['preflight']={'round1':binding}
    # Training must reuse the audited owned initial states, never recompute PCA,
    # reread old warm starts, or create a different random initialization.
    for name in ('fit_train_preprocessing','load_old_members','initialize_model'):
        monkeypatch.setattr(pipeline,name,lambda *a,**kw:pytest.fail('Training repeated fit-before preparation'))
    calls=[]
    def mock_fit(config, ledger, **kwargs):
        calls.append((kwargs['phase'], kwargs['path'], kwargs['member'], kwargs['stop_after']))
        assert kwargs['features'].shape == (18, 61)
        state = checkpoint_state(kwargs['model'])
        kwargs['on_checkpoint'](200, state, dict(last_minibatch_only=True, synthetic_mock=True))
        # Synthetic counter references only; no real ledger or optimizer exists.
        start = 200*(len(calls)-1)+1
        return dict(checkpoints={200: state}, updates=200, attempt_numbers=list(range(start, start+200)),
                    **pipeline._sampling(train['rows'],config,kwargs['phase'],kwargs['path'],kwargs['member']),
                    synthetic_mock=True, optimizer_created=False)
    monkeypatch.setattr(pipeline, 'fit_member', mock_fit)
    result = pipeline.run(cfg, None, phase='round1', version='synthetic_mock')
    assert calls == [('round1', path, member, 200) for path in ('A', 'B') for member in range(4)]
    assert gates == [('training_round1', dict(resource='training_updates'))]
    assert len(result['compared_checkpoints']) == 2
    assert result['selection']['path'] == 'B' and result['selection']['step'] == 200
    assert result['selection']['metrics']['planned_episodes'] == 100
    assert result['optimizer_updates'] == 1600
    assert len(set(result['optimizer_attempt_numbers'])) == 1600
    assert not result['independent_validation_success']
    assert not result['real_policy_evaluation_performed']
    assert (root/'models'/'round1'/'synthetic_mock'/'complete.json').exists()


@pytest.mark.parametrize('field',['scene_identity','replacement_chain'])
def test_input_audit_requires_scene_and_replacement_checks(root,monkeypatch,field):
    directory=root/'datasets/synthetic';directory.mkdir(parents=True)
    (directory/'complete.json').write_text('{}')
    audit_path=root/'input_audit.json'
    manifest=rows(1,'development')
    audit=dict(schema='native10_input_artifact_audit_v1',status='passed',purpose='development',
        dataset_seal_sha256=storage.sha256(directory/'complete.json'),manifest_sha256=canonical_hash(manifest),
        protocol_sha256='a'*64,checks={key:True for key in pipeline.INPUT_CHECKS if key!=field})
    audit_path.write_text(json.dumps(audit))
    binding=dict(path=str(directory),seal_sha256=audit['dataset_seal_sha256'],input_audit_path=str(audit_path),
                 input_audit_sha256=storage.sha256(audit_path),input_protocol_sha256='a'*64)
    with pytest.raises(ValueError,match='incomplete or unbound'):
        pipeline.load_audited_dataset(binding,purpose='development',manifest=manifest)


def test_main_collection_scope_cannot_run_cpu_fit_before_audit(root,states,monkeypatch):
    cfg,_,_,_=synthetic_environment(root,states,monkeypatch)
    ready=root/'NATIVE10_ANALYSIS_READY.json'
    ready.write_text(json.dumps(dict(released_scope=['round1_native10_local_labels','cpu_protocol_checks'])))
    monkeypatch.setattr(pipeline,'load_audited_dataset',lambda *a,**kw:pytest.fail('Missing prefit scope read real datasets'))
    monkeypatch.setattr(pipeline,'fit_train_preprocessing',lambda *a,**kw:pytest.fail('Missing prefit scope fitted PCA'))
    with pytest.raises(ValueError,match='has not released CPU fit-before'):
        pipeline.preflight(cfg,phase='round1',version='not_released')
    assert not (root/'fit_preflight').exists()


def test_zero_update_preflight_is_independent_exclusive_and_binds_both_paths(root,states,monkeypatch):
    cfg,train,_,gates=synthetic_environment(root,states,monkeypatch)
    monkeypatch.setattr(pipeline,'fit_member',lambda *a,**kw:pytest.fail('Preflight attempted training'))
    binding=pipeline.preflight(cfg,phase='round1',version='zero_updates')
    result=json.loads((root/'fit_preflight/round1/zero_updates/result.json').read_text())
    assert binding['optimizer_updates']==0 and result['optimizer_updates']==0 and gates==[]
    assert result['role']==pipeline.PREFLIGHT_ROLE and not result['model_fit_complete']
    assert not result['training_released_by_this_artifact']
    assert set(result['initial_assets'])==set(result['reload_audits'])=={'A','B'}
    assert result['pca_fitting_performed'] and not result['optimizer_model_fitting_performed']
    directory=root/'fit_preflight/round1/zero_updates'
    assert result['sampling_sha256']==storage.sha256(directory/'sampling.json')
    assert result['trainable_masks_sha256']==storage.sha256(directory/'trainable_masks.json')
    masks=json.loads((directory/'trainable_masks.json').read_text())
    assert all(p['requires_grad']==p['name'].startswith(('residual.','advantage.')) for p in masks['A'][0]['parameters'])
    assert all(p['requires_grad'] for p in masks['B'][0]['parameters'])
    assert result['pca_audit']['fit_episode_ids']==[row['episode_id'] for row in train['rows']]
    assert not (root/'models').exists() and not (root/'budget').exists()
    with pytest.raises(FileExistsError):pipeline.preflight(cfg,phase='round1',version='zero_updates')


def test_failed_b_audit_leaves_zero_update_failure_without_passing_seal(root,states,monkeypatch):
    cfg,_,_,_=synthetic_environment(root,states,monkeypatch)
    original=pipeline.audit_reload;calls=[]
    def audit(*args):
        calls.append(True)
        if len(calls)==2:raise ValueError('Synthetic B reload failure')
        return original(*args)
    monkeypatch.setattr(pipeline,'audit_reload',audit)
    monkeypatch.setattr(pipeline,'fit_member',lambda *a,**kw:pytest.fail('Failed preflight attempted training'))
    with pytest.raises(ValueError,match='Synthetic B reload failure'):
        pipeline.preflight(cfg,phase='round1',version='failed_b')
    directory=root/'fit_preflight/round1/failed_b'
    failure=json.loads((directory/'failure.json').read_text())
    assert failure['optimizer_updates']==0 and not failure['model_fit_complete']
    assert not (directory/'complete.json').exists() and not (directory/'result.json').exists()


@pytest.mark.parametrize('mutation',['dataset','stops','code','unsealed','weight'])
def test_run_rejects_changed_or_partial_prefit_before_any_fit(root,states,monkeypatch,mutation):
    cfg,_,_,_=synthetic_environment(root,states,monkeypatch)
    binding=pipeline.preflight(cfg,phase='round1',version='bound')
    cfg['training_pipeline']['preflight']={'round1':binding}
    directory=root/'fit_preflight/round1/bound'
    if mutation=='dataset':cfg['training_pipeline']['datasets']['round1']['train']['seal_sha256']='c'*64
    elif mutation=='stops':cfg['training_pipeline']['stop_after']['round1']['A']=400
    elif mutation=='code':cfg['training_pipeline']['code_files'][str(pipeline.Path(pipeline.__file__).resolve())]='0'*64
    elif mutation=='unsealed':(directory/'complete.json').unlink()
    else:
        path=directory/'B/initial/models/refit/member_0/selected.pt'
        path.write_bytes(path.read_bytes()+b'changed')
    monkeypatch.setattr(pipeline,'fit_member',lambda *a,**kw:pytest.fail('Invalid preflight reached fit'))
    monkeypatch.setattr(pipeline,'fit_train_preprocessing',lambda *a,**kw:pytest.fail('Run refitted PCA'))
    with pytest.raises((ValueError,FileNotFoundError)):
        pipeline.run(cfg,None,phase='round1',version='must_not_start')
    assert not (root/'models').exists()


@pytest.mark.parametrize('mutation',['positive_updates','positive_simulator','wrong_mapping','wrong_collection_release'])
def test_prefit_requires_exact_zero_resource_stage_and_collection_release(root,states,monkeypatch,mutation):
    cfg,_,_,_=synthetic_environment(root,states,monkeypatch)
    if mutation=='positive_updates':cfg['budget']['stages']['round1_fit_preflight']['training_updates']=1
    elif mutation=='positive_simulator':cfg['budget']['stages']['round1_fit_preflight']['simulator_attempts']=1
    elif mutation=='wrong_mapping':cfg['stage_release_scopes']['round1_fit_preflight']='cpu_protocol_checks'
    else:cfg['training_pipeline']['collection']['config_sha256']='f'*64
    monkeypatch.setattr(pipeline,'load_audited_dataset',lambda *a,**kw:pytest.fail('Invalid zero-resource gate read datasets'))
    with pytest.raises(ValueError,match='zero simulator|READY fit-before'):
        pipeline.preflight(cfg,phase='round1',version='forbidden')
    assert not (root/'fit_preflight').exists()
