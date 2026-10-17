"""Synthetic sealed CPU fixtures only; no model, optimizer or simulator calls."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from . import policy_deployment_round2_v1 as policy, storage, main_collection, engine
from .main_collection import POLICY_METHODS, SPLIT_REPLICATES, select_cut
from .protocol import candidate_seed, canonical_hash


def read(path):
    return json.loads(Path(path).read_text())


def rewrite(path, value):
    Path(path).write_text(json.dumps(value))


def reseal(path, **metadata):
    (path/'complete.json').unlink()
    storage.seal(path, **metadata)
    return storage.sha256(path/'complete.json')


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path/'outputs'
    for module in (policy, storage):
        monkeypatch.setattr(module, 'ROOT', root)
    tasks=('disassemble-v3','pick-place-wall-v3','shelf-place-v3','stick-pull-v3','stick-push-v3')
    cases = [dict(episode_id=f'{tasks[i%5]}__{2026111600+i}',case_id=f'{tasks[i%5]}__{2026111600+i}',
        task=tasks[i%5],env_seed=2026111600+i,split='development',round=None,
        source_horizon=10,cut_rule={'kind':'first_alarm'}) for i in range(100)]
    old_protocol, new_protocol = 'a'*64, 'b'*64
    old_models = dict(vla='c'*64, d='d'*64, g0='e'*64, implementation='f'*64,
                      **{'critic_'+str(i): str(i)*64 for i in range(4)})
    registration = dict(kind='labels13', stage='round1_labels', generation_round=1,
        episode_ids=[row['episode_id'] for row in cases], model_hashes=old_models,
        critic_member_hashes={str(i): str(i)*64 for i in range(4)},
        cut_selection_policy='analysis_lead_v1', random_seed_domain='original')
    old = dict(episode_manifest=cases, seed_namespace='synthetic_cpu_only',
        source_horizon=10, prefix_horizon=10, suffix_horizon=10, control_budget=300,
        gate_threshold=.05, guidance={'alpha': 10, 'times': [.3, .2, .1]},
        matching=dict(xyz_rms=.05, gripper_rms=.1, xyz_linf=.15, gripper_linf=.4,
            boundary_clearance=.05, tolerance=1e-6, zero_threshold=1e-10),
        cpu={'worker_threads': 2}, scene_identity={'schema': 'test'},command_semantics={'raw_a0':True},
        split_replicates=dict(SPLIT_REPLICATES), methods=list(POLICY_METHODS),
        main_collection={'banks': {'original': registration}, 'concurrency': {'workers_per_gpu': 4}},
        analysis_approval={'protocol_sha256': old_protocol})
    old_path = root/'original/config.json'
    storage.dump(old_path, old)
    freeze = root/'original/freeze.json'
    storage.dump(freeze, {'files': {str(old_path): storage.sha256(old_path)}})
    bound = {}
    raw = np.zeros((50, 4), np.float32)
    raw[:, 3] = 1.5  # Raw action preservation must catch accidental clamping.
    mask = np.ones((10, 4), bool); mask[:, 3] = False
    for i, case in enumerate(cases):
        identity = case['episode_id']; cut = 5 if i < 95 else None
        source = root/'sources'/identity
        selection = select_cut(case, [5] if cut else [], cut)
        storage.dump(source/'summary.json', dict(case=case, planned_episode_retained=True,
            outcome_filter_applied=False, cuts=[5] if cut else [], **selection,
            seed_namespace=old['seed_namespace'], no_alarm=cut is None, success=i>=96,
            full_episode_outcome_available=cut is None, model_hashes=old_models,
            cut_selection_policy='analysis_lead_v1'))
        storage.arrays(source/'trajectory.npz', actions=np.zeros((5, 4), np.float32))
        if cut:
            storage.dump(source/'cut005/anchor.json', {'step': 5})
            storage.arrays(source/'cut005/context.npz', full_plan=raw)
        storage.seal(source, protocol_sha256=old_protocol)
        source_sha = storage.sha256(source/'complete.json')
        resolution = root/'slot_resolution'/identity
        storage.dump(resolution/'resolution.json', dict(status='resolved', planned_slot_id=identity,
            resolved_episode_id=identity, ordered_rejections=[], source_protocol_sha256=old_protocol,
            source_seal_sha256=source_sha))
        storage.seal(resolution, protocol_sha256=old_protocol)
        bank_sha = None
        if cut:
            bank = root/'banks/original'/identity/'cut005'
            noise = '9'*64
            storage.arrays(bank/'plans.npz', a0=raw)
            storage.arrays(bank/'formal_directions.npz', raw_a0=raw, mask=mask)
            storage.dump(bank/'generation.json', dict(episode_id=identity, cut_step=5,
                source_seal_sha256=source_sha, model_hashes=old_models,
                base_seed=candidate_seed(case, 5, namespace=old['seed_namespace']),
                base_generation={'noise_sha256': noise},
                noise_hashes=dict(replan=noise, velocity=noise, direct=noise),
                suffix_seed_namespace=old['seed_namespace'], suffix_protocol='native10_first_ten_raw_commands_v1'))
            storage.seal(bank, protocol_sha256=old_protocol)
            bank_sha = storage.sha256(bank/'complete.json')
        bound[identity] = dict(source_seal_sha256=source_sha,
            resolution_seal_sha256=storage.sha256(resolution/'complete.json'), old_bank_seal_sha256=bank_sha)
    trained = root/'models/final/final_fit_v1'
    selected = trained/'selected'
    hashes = {}
    for member in range(4):
        path = selected/f'models/refit/member_{member}/selected.pt'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f'CPU synthetic artifact {member}; never torch.load'.encode())
        hashes[str(member)] = storage.sha256(path)
    storage.dump(selected/'config.json', {'synthetic_config':True})
    storage.dump(selected/'ranking.json', dict(horizon=10, a0_slot=0, model_hashes=hashes))
    storage.seal(selected, role='four_member_critic_export', model_hashes=hashes)
    storage.dump(trained/'result.json', dict(status='complete', phase='final',selection={'path':'A','step':4000},optimizer_updates=32000,simulator_calls=0,
        selected_assets=str(selected), model_hashes=hashes))
    storage.dump(trained/'selected_reload_audit.json', dict(status='passed', source_count=95,
        episode_ids=[row['episode_id'] for row in cases[:95]], members_checked=4, gradient_slots=[0, 11],
        feature_cache_bit_exact=True, thirteen_candidate_member_probability_bit_exact=True,
        member_and_ensemble_gradient_bit_exact=True, a0_anchor_exactly_zero=True, state_and_anchor_immutable=True))
    storage.seal(trained, role='native10_final_two_path_training', phase='final', model_hashes=hashes)
    review_path=root/'review/final_model.json'
    storage.dump(review_path,dict(schema='native10_final_trained_model_independent_review_v1',status='passed',blockers=[],
        model_hashes=hashes,selection={'path':'A','step':4000},bindings=dict(model_directory=str(trained),selected_directory=str(selected),
        model_complete_sha256=storage.sha256(trained/'complete.json'),model_result_sha256=storage.sha256(trained/'result.json'),
        selected_complete_sha256=storage.sha256(selected/'complete.json'),selected_reload_audit_sha256=storage.sha256(trained/'selected_reload_audit.json'),
        selected_config_sha256=storage.sha256(selected/'config.json'),selected_ranking_sha256=storage.sha256(selected/'ranking.json')),
        selected_models=[dict(member=m,path=str(selected/f'models/refit/member_{m}/selected.pt'),sha256=hashes[str(m)],
                             exact_tensor_match_to_A4000_checkpoint=True) for m in range(4)]))
    monkeypatch.setattr(policy,'FINAL_MODEL_SEAL',storage.sha256(trained/'complete.json'))
    monkeypatch.setattr(policy,'FINAL_SELECTED_SEAL',storage.sha256(selected/'complete.json'))
    config = deepcopy(old)
    config['critic_assets'] = str(selected)
    config['analysis_approval']['protocol_sha256'] = new_protocol
    config['budget'] = {'stages': {policy.STAGE: dict(simulator_attempts=2100, training_updates=0)}}
    config['stage_release_scopes'] = {policy.STAGE: policy.STAGE}
    newreg = deepcopy(registration)
    newreg.update(kind='policy5', stage=policy.STAGE, generation_round=2,critic_member_hashes=hashes,
        allowed_source_protocol_sha256=[old_protocol],
        model_hashes={**{k: old_models[k] for k in ('vla', 'd', 'g0', 'implementation')},
                      **{'critic_'+k: v for k, v in hashes.items()}})
    config['main_collection']['banks'] = {'new': newreg}
    config['policy_deployment'] = dict(schema=policy.SCHEMA,
        old_collection=dict(config_path=str(old_path), config_sha256=storage.sha256(old_path),
            freeze_path=str(freeze), freeze_sha256=storage.sha256(freeze), bank_version='original'),
        selected_training=dict(path=str(trained), seal_sha256=storage.sha256(trained/'complete.json'),
            selected_seal_sha256=storage.sha256(selected/'complete.json'),selected_reload_audit_sha256=storage.sha256(trained/'selected_reload_audit.json'),
            model_review={'path':str(review_path),'sha256':storage.sha256(review_path)}), source_bindings=bound)
    return config, cases, root


def new_bank(inputs, case):
    bound = inputs['sources'][case['episode_id']]
    old = Path(bound['old_bank_path'])
    new = policy.ROOT/'banks/new'/case['case_id']/'cut005'
    with np.load(old/'plans.npz') as data:
        raw = data['a0'].copy()
        plans = {name: raw.copy() for name in POLICY_METHODS[1:]}
        storage.arrays(new/'plans.npz', **plans)
        storage.arrays(new/'directions.npz', raw_a0=raw, critic_a0=np.clip(raw, -1, 1),
            critic_candidates=np.stack([np.clip(plan, -1, 1) for plan in plans.values()]))
    with np.load(old/'formal_directions.npz') as data:
        storage.arrays(new/'formal_directions.npz', **{key: data[key] for key in data.files})
    storage.dump(new/'generation.json', read(old/'generation.json'))
    storage.seal(new, protocol_sha256=bound['new_protocol_sha256'])
    return new


def test_final_round2_assets_keep_original_round1_source_provenance(prepared):
    config,cases,root=prepared;got=policy.validate_deployment_inputs(config,'new')
    assert got['stage']=='round2_development_policy' and got['expected_attempts']==1995 and got['hard_attempt_limit']==2100
    assert got['training']['selection']=={'path':'A','step':4000}
    assert got['training']['selected_assets']==str(root/'models/final/final_fit_v1/selected')
    assert got['old_protocol_sha256']=='a'*64 and all(r['old_protocol_sha256']=='a'*64 for r in got['sources'].values())
    assert config['main_collection']['banks']['new']['generation_round']==2
    assert read(root/'original/config.json')['main_collection']['banks']['original']['generation_round']==1
    common=[r['common_outcome'] for r in got['sources'].values() if r['cut'] is None]
    assert common.count(True)==4 and common.count(False)==1 and got['planned_denominator_per_arm']==400
    assert got['simulator_calls']==got['model_calls']==0


@pytest.mark.parametrize('field,value',[('stage','round1_development_policy'),('generation_round',1)])
def test_no_stage_or_generation_round_masquerading(prepared,field,value):
    config,_,_=prepared;config['main_collection']['banks']['new'][field]=value
    with pytest.raises(ValueError,match='round2'):policy.validate_deployment_inputs(config,'new')


def test_old_release_cannot_authorize_final_collector(prepared,monkeypatch):
    config,_,_=prepared;config['stage_release_scopes'][policy.STAGE]='round1_development_policy'
    with pytest.raises(ValueError,match='own round2'):policy.validate_deployment_inputs(config,'new')
    monkeypatch.setattr(policy,'_require_main',lambda *a: (_ for _ in ()).throw(ValueError('not released')))
    monkeypatch.setattr(policy,'validate_deployment_inputs',lambda *a:pytest.fail('No data before release'))
    with pytest.raises(ValueError,match='not released'):policy.create_policy_collector(config,policy.STAGE,bank_version='new')


@pytest.mark.parametrize('key',[ 'seal_sha256','selected_seal_sha256','selected_reload_audit_sha256'])
def test_old_or_wrong_final_asset_binding_rejected(prepared,key):
    config,_,_=prepared;config['policy_deployment']['selected_training'][key]='0'*64
    with pytest.raises(ValueError):policy.validate_deployment_inputs(config,'new')


def test_model_review_must_bind_actual_reload_and_A4000(prepared):
    config,_,_=prepared;b=config['policy_deployment']['selected_training'];review=Path(b['model_review']['path'])
    row=read(review);row['selection']['path']='B';rewrite(review,row);b['model_review']['sha256']=storage.sha256(review)
    with pytest.raises(ValueError,match='Independent review'):policy.validate_deployment_inputs(config,'new')


def test_missing_original_source_cannot_fall_through_to_capture(prepared,monkeypatch):
    config,cases,root=prepared;(root/'sources'/cases[0]['case_id']/'complete.json').unlink()
    monkeypatch.setattr(policy,'_require_main',lambda *a:None)
    monkeypatch.setattr(engine,'create_engine',lambda *a:pytest.fail('Must fail before real model construction'))
    with pytest.raises(FileNotFoundError):policy.create_policy_collector(config,policy.STAGE,bank_version='new')
    collector=object.__new__(policy.GuardedPolicyCollector)
    with pytest.raises(ValueError,match='forbids'):collector.capture(cases[0])


@pytest.mark.parametrize('key', ['guidance','matching','command_semantics'])
def test_scientific_and_raw_semantics_unchanged(prepared,key):
    config,_,_=prepared;config[key]={}
    with pytest.raises(ValueError,match='semantics'):policy.validate_deployment_inputs(config,'new')


def test_no_capture_replacement_old_guided_or_optimization_budget(prepared):
    config,cases,_=prepared;got=policy.validate_deployment_inputs(config,'new');calls=[]
    ledger=policy._PolicyLedger(SimpleNamespace(reserve=lambda *a,**k:calls.append(a)),got)
    tail='new/'+cases[0]['case_id']+'/cut005'
    ledger.reserve(policy.STAGE,'candidate_restore','banks/'+tail)
    ledger.reserve(policy.STAGE,'branch_including_restore','rollouts/'+policy.STAGE+'/'+tail+'/post/repeat_0')
    for stage,kind,identity,resource in [
        (policy.STAGE,'source_capture','source','simulator_attempts'),
        ('technical_reserve','source_capture','backup','simulator_attempts'),
        ('round1_development_policy','branch_including_restore','rollouts/round1_development_policy/'+tail+'/post/repeat_0','simulator_attempts'),
        (policy.STAGE,'critic_optimizer_update','A4000','training_updates')]:
        with pytest.raises(ValueError,match='prohibits'):ledger.reserve(stage,kind,identity,resource=resource)
    assert len(calls)==2


@pytest.mark.parametrize('change',['raw','noise','mask','tail','critic'])
def test_new_bank_reuses_raw_anchor_noise_mask_but_not_old_guided_results(prepared,change):
    config,cases,_=prepared;inputs=policy.validate_deployment_inputs(config,'new');bank=new_bank(inputs,cases[0])
    assert policy.verify_bank_anchor(bank,inputs['sources'][cases[0]['episode_id']])['checked_before_branch']
    if change=='noise':
        path=bank/'generation.json';value=read(path);value['base_generation']['noise_sha256']='8'*64
        value['noise_hashes']=dict(replan='8'*64,velocity='8'*64,direct='8'*64);rewrite(path,value)
    else:
        path=bank/('formal_directions.npz' if change=='mask' else 'directions.npz' if change=='critic' else 'plans.npz')
        with np.load(path) as a:values={k:a[k].copy() for k in a.files}
        if change=='raw':values['alarm_replan10'][49,3]=1.
        elif change=='tail':values['post'][10,0]=.2
        elif change=='mask':values['mask'][0,0]=False
        else:values['critic_candidates'][0,0,0]=.2
        path.unlink();storage.arrays(path,**values)
    reseal(bank,protocol_sha256='b'*64)
    with pytest.raises(ValueError):policy.verify_bank_anchor(bank,inputs['sources'][cases[0]['episode_id']])


def test_actual_loaded_selector_paths_and_hashes_checked(prepared,monkeypatch):
    config,_,_=prepared;inputs=policy.validate_deployment_inputs(config,'new');expected=inputs['training']
    collector=object.__new__(policy.GuardedPolicyCollector);collector.deployment_inputs=inputs
    calls=[];selector=SimpleNamespace(assets_dir=expected['selected_assets'],model_paths=expected['model_paths'],
        ranking={'model_hashes':expected['model_hashes']},verify=lambda **kw:calls.append(kw))
    collector.engine=SimpleNamespace(selector=selector)
    monkeypatch.setattr(main_collection.MainCollector,'_verify_models',lambda self:None)
    collector._verify_models()
    assert calls==[{'check_files':True}]
    assert collector.loaded_critic_identity['selection']=={'path':'A','step':4000}
    selector.assets_dir=str(Path(expected['selected_assets']).parent/'old_B200')
    with pytest.raises(ValueError,match='Actual loaded critic'):collector._verify_models()


def test_math_helpers_equal_old_implementation_without_mutating_old_globals():
    import ast
    from . import policy_deployment_v1 as old
    oldtree=ast.parse(Path(old.__file__).read_text());newtree=ast.parse(Path(policy.__file__).read_text())
    for name in ('_raw','_noise','compare_bank_identity','verify_bank_anchor','_matched_rms','_PolicyLedger'):
        a=next(node for node in oldtree.body if getattr(node,'name',None)==name)
        b=next(node for node in newtree.body if getattr(node,'name',None)==name)
        assert ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
    assert old.STAGE=='round1_development_policy' and policy.STAGE=='round2_development_policy'
