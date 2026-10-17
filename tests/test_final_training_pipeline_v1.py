"""Cross-protocol orchestration with synthetic states only; no optimizer calls."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from experiments.native10_training_20260916 import final_training_pipeline_v1 as pipeline, storage
from experiments.native10_training_20260916 import training_pipeline as core
from experiments.native10_training_20260916.protocol import canonical_hash, TASKS, episode_key
from experiments.native10_training_20260916.test_training import preprocessing, state_arrays
from experiments.native10_training_20260916.training import checkpoint_state, initialize_model, dedup_weights


def rows(n,split,start,round):
    return [dict(episode_id=episode_key(TASKS[i%5],start+i),task=TASKS[i%5],env_seed=start+i,
                 split=split,round=round) for i in range(n)]


def pack(manifest,planned,reached,purpose):
    selected={r['episode_id'] for r in reached}
    records=[dict(episode_id=r['episode_id'],planned_slot_id=r['episode_id'],
        status='complete' if r['episode_id'] in selected else 'no_cut',critic_eligible=r['episode_id'] in selected,
        control_complete=r['episode_id'] in selected,full_episode_outcome_available=True,native10_outcome=True)
        for r in planned]
    arrays={k:v.numpy() for k,v in state_arrays(len(reached)).items()}
    arrays.update(actions=np.zeros((len(reached),13,10,4),np.float32),
                  outcomes=np.zeros((len(reached),13,4),np.bool_),group_ids=np.zeros((len(reached),13),np.int64))
    arrays.update({k:v.numpy() for k,v in dedup_weights(arrays['group_ids']).items()})
    return dict(rows=deepcopy(reached),arrays=arrays,metadata=dict(purpose=purpose,records=records,
        planned_episode_count=len(planned),complete_planned_selection_evidence=True,manifest_sha256=canonical_hash(manifest)))


@pytest.fixture
def example(tmp_path,monkeypatch):
    root=tmp_path/'workflow';root.mkdir();monkeypatch.setattr(storage,'ROOT',root)
    r1,r2,dev=rows(300,'train',800000,1),rows(300,'train',810000,2),rows(100,'development',820000,None)
    manifest=r1+r2+dev
    train=pack(manifest,r1+r2,r1[:10]+r2[:10],'train');development=pack(manifest,dev,dev[:2],'development')
    binding=dict(path=str(root/'synthetic_bundle'),seal_sha256='a'*64,input_bundle_sha256='b'*64)
    source_bindings={role:{'pipeline_binding':{'path':role,'seal_sha256':str(i)*64,'input_protocol_sha256':str(i)*64}}
                     for i,role in enumerate(('round1_train','round2_train','development'))}
    feature={'canonical':'synthetic unprojected features'}
    spec=dict(schema=pipeline.SCHEMA,phase='final',input_bundle=binding,source_bindings=source_bindings,
        manifest_sha256=canonical_hash(manifest),feature_contract_sha256=canonical_hash(feature),
        design={'path':'synthetic','sha256':'c'*64},
        documents={'numerical_decision':{'sha256':pipeline.NUMERICAL_DECISION_SHA}},
        numeric_runtime=pipeline._runtime(),code_files={},stop_after={'A':4000,'B':4000})
    cfg=dict(synthetic_allow_mode='preflight',seed_namespace='synthetic_final_v1',episode_manifest=manifest,
        final_training_pipeline=spec,analysis_approval={'protocol_sha256':'d'*64},analysis_ready={'path':'synthetic_ready','sha256':'e'*64})
    bundle=dict(train=train,development=development,manifest=manifest,bundle_manifest={'feature_contract':feature},
        metadata={'sources':source_bindings},verification={'status':'passed','bundle_identity':binding})
    events=[]
    def validate(config,mode):
        events.append('gate:'+mode)
        if config.get('synthetic_allow_mode')!=mode:raise ValueError('Synthetic gate not released')
        specification=deepcopy(config['final_training_pipeline'])
        identity={k:v for k,v in specification.items() if k not in ('schema','preflight')}
        identity['seed_namespace']=config['seed_namespace']
        return specification,{'old_weight_import':{'synthetic':True}},identity
    def load(binding):events.append('bundle');return deepcopy(bundle)
    states=[checkpoint_state(initialize_model('B',seed=123+m,preprocessing=preprocessing())) for m in range(4)]
    def old(*args):events.append('old_weights');return deepcopy(states),{'read_only':True,'synthetic':True}
    monkeypatch.setattr(pipeline,'_validate_specification',validate)
    monkeypatch.setattr(pipeline,'load_bundle',load)
    monkeypatch.setattr(core,'load_old_members',old)
    for name in ('_specification','_require_preflight','load_preflight'):
        monkeypatch.setattr(core,name,lambda *a,**k:pytest.fail('Old single-collection boundary used'))
    def strict(models,selector,arrays,source_rows):
        events.append('reload:'+source_rows[0]['split'])
        return dict(status='passed',source_count=len(source_rows),episode_ids=[r['episode_id'] for r in source_rows],
            feature_cache_bit_exact=True,thirteen_candidate_member_probability_bit_exact=True,
            gradient_slots=[0,11],member_and_ensemble_gradient_bit_exact=True,members_checked=4,
            a0_anchor_exactly_zero=True,state_and_anchor_immutable=True)
    def batch(models,arrays,source_rows):
        n=len(source_rows)
        difference=lambda shape:pipeline._difference(torch.zeros(shape),torch.zeros(shape))
        members=[dict(member=m,observed_features={name:difference([n,width]) for name,width in
            (('visual',8192),('language',2048),('other',37))},projected_features=difference([n,61]),
            probabilities=difference([n,13]),action_batch_shape=[n,2,10,4],probability_slots=list(range(13)),
            gradients={slot:difference([n,10,4]) for slot in ('0','11')}) for m in range(4)]
        return dict(status='reported_exact',source_count=n,episode_ids=[r['episode_id'] for r in source_rows],all_bit_exact=True,
            members=members,ensemble_gradients={slot:difference([n,10,4]) for slot in ('0','11')},gradient_slots=[0,11],
            diagnostics_complete=True,numeric_contract=pipeline.NUMERIC_CONTRACT,decision_sha256=pipeline.NUMERICAL_DECISION_SHA,
            input_sha256=pipeline._fingerprint({k:arrays[k] for k in [*pipeline.STATE_KEYS,'actions']}),
            model_state_sha256=[pipeline._fingerprint(m.state_dict()) for m in models],numeric_runtime=pipeline._runtime(),
            state_a0_actions_model_unchanged=True,a0_detached=True,a0_relative_advantage_exact_zero=True,
            source_independent_linear_silu_structure=True,member_gradient_reduction='sum source gains; no 1/N scaling',
            ensemble_gradient_reduction='mean members then sum sources; no 1/N scaling',new_tolerance_introduced=False,
            diagnostic_batch_path_used_for_canonical_inference=False)
    monkeypatch.setattr(core,'audit_reload',strict)
    monkeypatch.setattr(pipeline,'batch_singleton_diagnostics',batch)
    monkeypatch.setattr(core,'fit_member',lambda *a,**k:pytest.fail('Optimizer fitting is forbidden in these tests'))
    return dict(root=root,config=cfg,bundle=bundle,events=events,states=states)


def completed(e):
    bound=pipeline.preflight(e['config'],version='synthetic')
    config=deepcopy(e['config']);config['synthetic_allow_mode']='fit'
    config['final_training_pipeline']['preflight']={k:bound[k] for k in ('path','seal_sha256','result_sha256')}
    return config,bound


def test_preflight_gates_before_bundle_or_weights(example):
    example['config']['synthetic_allow_mode']='none'
    with pytest.raises(ValueError,match='gate not released'):pipeline.preflight(example['config'],version='blocked')
    assert example['events']==['gate:preflight']
    assert not (example['root']/'fit_preflight').exists()


@pytest.mark.parametrize('field',['source_bindings','manifest_sha256','feature_contract_sha256'])
def test_every_bundle_binding_precedes_pca_and_initialization(example,field):
    example['config']['final_training_pipeline'][field]='changed'
    with pytest.raises(ValueError,match='Verified bundle'):pipeline.preflight(example['config'],version='blocked')
    assert 'old_weights' not in example['events']


def test_preflight_saves_eight_initial_states_unique_train_pca_and_full_dev_denominator(example):
    cfg,binding=completed(example);directory=Path(binding['path']);r=json.loads((directory/'result.json').read_text())
    assert r['status']=='passed' and r['optimizer_updates']==r['simulator_calls']==0 and not r['model_fit_complete']
    assert r['coverage']['train_planned']==600 and r['coverage']['train_reached']==20
    assert r['coverage']['development_planned']==100 and r['coverage']['development_reached']==2
    assert r['pca_audit']['fit_episode_ids']==[x['episode_id'] for x in example['bundle']['train']['rows']]
    assert r['pca_audit']['pca_diagnostics']['visual']['scale_floor']==1e-3
    assert example['events'][:3]==['gate:preflight','bundle','old_weights']
    assert example['events'].count('reload:train')==example['events'].count('reload:development')==2
    masks=json.loads((directory/'trainable_masks.json').read_text())
    sampling=json.loads((directory/'sampling.json').read_text())
    for path in ('A','B'):
        assert len(masks[path])==len(sampling[path])==len(r['initial_assets'][path]['model_hashes'])==4
        for sample in sampling[path]:
            assert len(sample['bootstrap']['indices'])==20
            assert all(v['drawn']==v['unique_available']==4 for v in sample['bootstrap']['per_task'].values())
    with np.load(directory/'preprocessing.npz') as a:
        assert a['B__visual_basis'].shape==(8192,16) and a['B__language_basis'].shape==(2048,8)
        assert np.array_equal(a['A0__visual_basis'],example['states'][0]['visual_basis'].numpy())
    with np.load(directory/'minibatch_plans.npz') as archive:
        assert len(archive.files)==8 and archive['A_0'].shape==(4000,32)
        assert np.array_equal(archive['A_0'],pipeline._minibatches(sampling['A'][0]))


def test_prefit_reloading_reuses_sealed_pca_and_initialization_without_old_weight_read(example,monkeypatch):
    cfg,binding=completed(example)
    for name in ('load_old_members','fit_train_preprocessing','initialize_model'):
        monkeypatch.setattr(core,name,lambda *a,**k:pytest.fail('Fit regenerated a preflight artifact'))
    result,states=pipeline.load_preflight(cfg)
    assert result['status']=='passed' and len(states['A'])==len(states['B'])==4
    assert all(torch.equal(states['A'][0][k],v) for k,v in example['states'][0].items())


def test_finite_dense_difference_is_reported_and_does_not_replace_canonical_acceptance(example,monkeypatch):
    original=pipeline.batch_singleton_diagnostics
    def difference(*args):
        report=original(*args);report.update(status='reported_differences',all_bit_exact=False)
        report['members'][0]['probabilities'].update(exact_equal=False,mismatched_elements=1,max_abs_difference=1e-7)
        return report
    monkeypatch.setattr(pipeline,'batch_singleton_diagnostics',difference)
    cfg,binding=completed(example)
    assert binding['status']=='passed'
    result,states=pipeline.load_preflight(cfg)
    assert result['numeric_contract']==pipeline.NUMERIC_CONTRACT
    assert not result['batch_singleton_bit_exact'] and result['canonical_reload_passed']
    assert result['dense_report_analysis_review_required_before_training'] and not result['final_training_released']


def test_failed_b_initialization_cannot_publish_complete_or_start_fit(example,monkeypatch):
    original=core.initialize_model
    def init(path,**kwargs):
        if path=='B':raise ValueError('synthetic B initialization failure')
        return original(path,**kwargs)
    monkeypatch.setattr(core,'initialize_model',init)
    with pytest.raises(ValueError,match='B initialization failure'):pipeline.preflight(example['config'],version='failed')
    directory=example['root']/'fit_preflight/final/failed'
    assert (directory/'failure.json').exists() and not (directory/'complete.json').exists()


@pytest.mark.parametrize('name',['sampling.json','minibatch_plans.npz','trainable_masks.json','preprocessing.npz','source_sets.json'])
def test_mutating_any_sealed_fit_input_is_rejected_before_model_reload(example,monkeypatch,name):
    cfg,binding=completed(example)
    with (Path(binding['path'])/name).open('ab') as stream:stream.write(b'changed')
    monkeypatch.setattr(pipeline,'FrozenSelector',lambda *a,**k:pytest.fail('Altered seal reached checkpoint loading'))
    with pytest.raises(ValueError,match='SHA mismatch'):pipeline.load_preflight(cfg)


def test_changed_bundle_protocol_binding_cannot_reuse_previous_prefit(example):
    cfg,binding=completed(example)
    cfg['final_training_pipeline']['source_bindings']['round2_train']['pipeline_binding']['input_protocol_sha256']='9'*64
    with pytest.raises(ValueError,match='Verified bundle'):pipeline.load_preflight(cfg)


def test_runtime_change_after_prefit_is_rejected(example,monkeypatch):
    cfg,binding=completed(example);runtime=pipeline._runtime();runtime['python']='different'
    monkeypatch.setattr(pipeline,'_runtime',lambda:runtime)
    with pytest.raises(ValueError,match='changed frozen identity'):pipeline.load_preflight(cfg)


def test_inference_mode_is_rejected_before_model_or_pca_work(example):
    with torch.inference_mode(),pytest.raises(ValueError,match='inference_mode'):
        pipeline.preflight(example['config'],version='blocked')
    assert 'old_weights' not in example['events']


def test_run_requires_the_new_fit_gate_before_any_scientific_compute(example):
    with pytest.raises(ValueError,match='gate not released'):pipeline.run(example['config'],None,version='blocked')
    assert example['events']==['gate:fit']


def test_fit_orchestration_uses_all_eight_sealed_models_and_original_dev100_without_updates(example,monkeypatch):
    cfg,binding=completed(example)
    for name in ('load_old_members','fit_train_preprocessing','initialize_model'):
        monkeypatch.setattr(core,name,lambda *a,**k:pytest.fail('Fit regenerated preflight'))
    monkeypatch.setattr(torch.optim,'AdamW',lambda *a,**k:pytest.fail('No optimizer may be created in this CPU test'))
    calls=[];counter=[0]
    def fit(config,ledger,*,phase,path,member,model,features,data,stop_after,on_checkpoint):
        # Synthetic orchestration receipt: no gradients/optimizer/ledger writes.
        assert phase=='final' and stop_after==4000 and features.shape==(20,61)
        assert model._native10_training_path==path
        calls.append((path,member))
        for step in core.CHECKPOINTS['final']:on_checkpoint(step,checkpoint_state(model),{'synthetic_no_updates':True})
        sampled=pipeline._sampling(data['rows'],config,path,member)
        numbers=list(range(counter[0]+1,counter[0]+4001));counter[0]+=4000
        return dict(updates=4000,attempt_numbers=numbers,bootstrap=sampled['bootstrap'],batch_seed=sampled['batch_seed'],
            minibatches=pipeline._minibatches(sampled).tolist(),checkpoints={},synthetic_no_optimizer_updates=True)
    monkeypatch.setattr(core,'fit_member',fit)
    result=pipeline.run(cfg,None,version='synthetic_fit')
    assert calls==[(p,m) for p in ('A','B') for m in range(4)]
    assert len(result['compared_checkpoints'])==14
    assert all(r['metrics']['planned_episodes']==100 and r['metrics']['reached_episodes']==2 for r in result['compared_checkpoints'])
    assert not result['preprocessing_refitted'] and not result['new_initialization_generated']
    assert not result['independent_validation_success'] and not result['next_stage_automatically_started']


def test_real_synthetic_singleton_reload_is_strict_for_all_probabilities_and_gradients(tmp_path,monkeypatch):
    root=tmp_path/'workflow';root.mkdir();monkeypatch.setattr(storage,'ROOT',root)
    states=[checkpoint_state(initialize_model('B',seed=100+m,preprocessing=preprocessing())) for m in range(4)]
    models=core.frozen_models(states);selector=core.export_ensemble(states,root/'export',provenance={'synthetic':True})
    source_rows=rows(2,'train',900000,1)
    arrays={k:v.numpy() for k,v in state_arrays(2).items()};arrays['actions']=np.zeros((2,13,10,4),np.float32)
    arrays['actions'][:,11]=.025
    checked=core.audit_reload(models,selector,arrays,source_rows);pipeline._audit_ok(checked,source_rows)
    diagnostic=pipeline.batch_singleton_diagnostics(models,arrays,source_rows)
    assert diagnostic['source_count']==2 and len(diagnostic['members'])==4
    for record in diagnostic['members']:
        assert record['probabilities']['finite'] and record['probability_slots']==list(range(13))
        assert record['action_batch_shape']==[2,2,10,4]
    assert diagnostic['status']==('reported_exact' if diagnostic['all_bit_exact'] else 'reported_differences')
    pipeline._dense_ok(diagnostic,arrays,source_rows,models)


def test_dense_difference_scales_use_finite_float64_measurement_without_changing_computation():
    first=torch.tensor([3e38],dtype=torch.float32);second=-first
    result=pipeline._difference(first,second)
    assert np.isfinite(result['max_abs_difference']) and result['max_abs_difference']>5e38
    assert result['reference_max_abs']==float(first[0]) and first.dtype==second.dtype==torch.float32
    with pytest.raises(ValueError,match='Nonfinite'):pipeline._difference(torch.tensor([float('nan')]),torch.zeros(1))


@pytest.mark.parametrize('problem',['wrong_gradient_scale','nonfinite','missing_member','state_changed'])
def test_semantic_or_nonfinite_dense_failures_remain_blocking(example,monkeypatch,problem):
    original=pipeline.batch_singleton_diagnostics
    def bad(*args):
        record=original(*args)
        if problem=='wrong_gradient_scale':record['member_gradient_reduction']='mean source gains'
        elif problem=='nonfinite':record['members'][0]['gradients']['11']['max_abs_difference']=float('inf')
        elif problem=='missing_member':record['members'].pop()
        else:record['state_a0_actions_model_unchanged']=False
        return record
    monkeypatch.setattr(pipeline,'batch_singleton_diagnostics',bad)
    with pytest.raises(ValueError,match='Dense'):pipeline.preflight(example['config'],version='blocked')
    assert not (example['root']/'fit_preflight/final/blocked/complete.json').exists()
