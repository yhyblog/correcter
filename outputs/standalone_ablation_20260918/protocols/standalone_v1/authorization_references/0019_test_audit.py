"""Synthetic adapter checks only; no real source results or model construction."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from . import audit, protocol
from .candidates import project_solo


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def seal(path, p):
    put(path/'complete.json', dict(status='complete', protocol_sha256=p, role='standalone_worker',
        files={str(x.relative_to(path)):audit.storage.sha256(x) for x in path.rglob('*')
               if x.is_file() and x != path/'complete.json'}))


@pytest.fixture
def wave(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, 'ROOT', tmp_path)
    ids = list(audit.REGISTERED_PRIMARY_IDS); stage = protocol.FORMAL; p = 'a'*64
    plan = dict(workers=32, episode_ids=ids, methods=list(protocol.METHODS), repeats=[0,1,2,3],
        bank_mode='solo', expected_attempts=1274)
    selected = tmp_path/'selected'; hashes = {str(i):str(i)*64 for i in range(4)}
    cfg = dict(execution_plans={stage:plan}, analysis_approval=dict(protocol_sha256=p), critic_assets=str(selected))
    old_cfg = dict(main_collection=dict(banks={'heldout_policy_v1':dict(critic_member_hashes=hashes)}))
    cp, fp = tmp_path/'config.json', tmp_path/'freeze.json'; put(cp,cfg); put(fp,{'synthetic':True})
    path = tmp_path/'execution'/stage/'wave'
    put(path/'wave_spec.json', dict(config_sha256=audit.storage.sha256(cp), freeze_sha256=audit.storage.sha256(fp),
        stage=stage, **plan, original_primary_slots=100, reference_methods=[], ref_repeats=[],
        source_capture_allowed=False, replacement_allowed=False, hold_idle=False, next_stage_automatically_started=False))
    put(path/'launch_result.json', dict(status='complete', returncode=0, lifecycle_covers_entire_wave=True,
        hold_idle=False, next_stage_automatically_started=False, command=['lifecycle','--spec',str(path/'wave_spec.json')]))
    model = dict(status='passed',stage=stage,selected_assets=str(selected),
        model_paths=[str(selected/f'models/refit/member_{i}/selected.pt') for i in range(4)],member_hashes=hashes,
        selection=dict(path='A',step=4000),optimizer_updates=0,actual_selector_paths=True,checkpoint_file_sha=True,
        frozen_parameter_buffer_versions=True,eval_cpu_no_parameter_grad=True,generation_only=True)
    for rank in range(32):
        folder = path/'workers'/f'worker_{rank:02d}'; assigned=ids[rank::32]
        put(folder/'loaded_model_identity.json',model)
        put(folder/'status.json',dict(status='complete',stage=stage,wave_id='wave',rank=rank,workers=32,
            config_sha256=audit.storage.sha256(cp),freeze_sha256=audit.storage.sha256(fp),protocol_sha256=p,
            assigned_slot_ids=assigned,completed_slot_records=len(assigned),missing_slot_ids=[],
            source_capture_allowed=False,replacement_allowed=False,next_stage_automatically_started=False))
        for identity in assigned:
            collection=tmp_path/'collections'/stage/identity
            put(collection/'complete.json',{'only_completion_metadata':True})
            put(folder/'slots'/f'{identity}.json',dict(status='complete',episode_id=identity,
                completion_path=str(collection),completion_sha256=audit.storage.sha256(collection/'complete.json')))
        seal(folder,p)
    return cfg,cp,fp,path,stage,{},old_cfg


def test_all_100_complete_gate_needs_no_outcome_files(wave):
    got=audit.wave_gate(*wave)
    assert got['all_slots_complete'] and len(got['slots'])==100 and got['loaded_workers']==32


@pytest.mark.parametrize('change',['missing_launch','failed_exit','missing_worker','missing_slot','changed_model'])
def test_gate_blocks_before_any_outcomes(wave,change):
    cfg,cp,fp,path,stage,artifacts,old=wave
    if change=='missing_launch': (path/'launch_result.json').unlink()
    elif change=='failed_exit':
        row=audit.read(path/'launch_result.json');row['returncode']=1;put(path/'launch_result.json',row)
    elif change=='missing_worker': (path/'workers/worker_31/complete.json').unlink()
    else:
        folder=path/'workers/worker_00'
        if change=='missing_slot': next((folder/'slots').glob('*.json')).unlink()
        else:
            row=audit.read(folder/'loaded_model_identity.json');row['selection']['path']='B'
            put(folder/'loaded_model_identity.json',row)
        seal(folder,'a'*64)
    with pytest.raises((ValueError,FileNotFoundError)):audit.wave_gate(*wave)


def ledger_fixture(stage=protocol.PREFLIGHT):
    cfg=dict(analysis_approval=dict(protocol_sha256='a'*64),carry_in=dict(ledger=dict(sha256='b'*64)))
    rows=[dict(number=i+1,stage=stage,kind='candidate_restore' if i<10 else 'branch_including_restore',
        identity=f'new/{stage}/{i}',resource='simulator_attempts',amount=1,protocol_sha256='a'*64,
        carry_in_ledger_sha256='b'*64,cumulative_simulator_attempts=48184+i,optimizer_updates=0) for i in range(30)]
    return cfg,rows


def test_preflight_plan_can_be_30_without_solo_outcome_branches():
    cfg,rows=ledger_fixture()
    result=audit.ledger_closure(cfg,rows,list(range(1,31)),stage=protocol.PREFLIGHT,
        expected_counts=dict(candidate_restore=10,branch_including_restore=20))
    assert result['new_stage_attempts']==30 and result['cross_ledger_simulator_attempts']==48213


@pytest.mark.parametrize('change',['missing_used','duplicate_used','capture','optimizer','duplicate_identity','carry','stage_cap'])
def test_ledger_failures_do_not_disappear(change):
    cfg,rows=ledger_fixture();used=list(range(1,31))
    if change=='missing_used':used.pop()
    elif change=='duplicate_used':used.append(used[0])
    elif change=='capture':rows[0]['kind']='source_capture'
    elif change=='optimizer':rows[0]['resource']='training_updates'
    elif change=='duplicate_identity':rows[1]['identity']=rows[0]['identity']
    elif change=='carry':rows[0]['carry_in_ledger_sha256']='c'*64
    else:
        for i in range(30,61):rows.append(dict(rows[0],number=i+1,identity=f'new/{i}',cumulative_simulator_attempts=48184+i))
        used=list(range(1,62))
    with pytest.raises(ValueError):audit.ledger_closure(cfg,rows,used,stage=protocol.PREFLIGHT,
        expected_counts=dict(candidate_restore=10,branch_including_restore=20))


def test_reference_comparison_does_not_invent_historical_native_directions():
    a=np.zeros((50,4),np.float32)
    plans={k:a.copy() for k in ('alarm_replan10','velocity','direct','post')}
    formal={'raw_a0':a.copy(),'post_internal_metric_direction':a[:10].copy()}
    reference=dict(deepcopy(formal),velocity_native_raw=a.copy(),direct_native_raw=a.copy())
    result=audit.compare_reference(plans,formal,plans,reference)
    assert not result['native_velocity_direct_historically_saved']
    reference['raw_a0'][0,0]=-0.
    with pytest.raises(ValueError):audit.compare_reference(plans,formal,plans,reference)


def test_reference_full_replay_checks_flags_noise_and_discrete_bytes():
    summary=dict(method='post',repeat=0,success=True,suffix_seeds=[dict(step=15,decision_index=0,seed=5,noise_sha256='b'*64)])
    old={'actions':np.zeros((2,4),np.float32),'physics_states':np.zeros((3,6)),
        'rewards':np.zeros(2),'done_flags':np.array([False,True])}
    new={k:v.copy() for k,v in old.items()}
    assert audit.compare_replay(summary,summary,old,new)['outcome_exact']
    new['actions'][0,0]=-0.
    with pytest.raises(ValueError):audit.compare_replay(summary,summary,old,new)
    new={k:v.copy() for k,v in old.items()};new['physics_states'][0,0]=1e-9
    with pytest.raises(ValueError):audit.compare_replay(summary,summary,old,new)


@pytest.fixture
def method_inputs():
    raw=np.zeros((50,4),np.float32);direction=np.ones((10,4),np.float32)*.1
    _,matching,saved=project_solo(raw,direction,protocol.MATCHING)
    saved.update(post_command_gradient=direction.copy(),post_internal_metric_direction=direction.copy())
    observed={'history':np.zeros((5,4),np.float32)}
    case=dict(task=protocol.TASKS[0],env_seed=2026111750,episode_id=protocol.PRIMARY_IDS[0]);cut=5
    cfg=dict(seed_namespace='corrector_native10_training_20260916_v1',matching=protocol.MATCHING,
             guidance=dict(alpha=10,times=[.3,.2,.1]))
    seed=audit.candidate_seed(case,cut,namespace=cfg['seed_namespace']);noise='b'*64
    base=dict(noise_sha256=noise,policy_calls=1,fallback=None)
    meta=dict(schema='standalone_generation_v1',status='complete',method='solo_post',base_seed=seed,
        actual_policy_calls=1,expected_policy_calls=1,native_direction='post',other_direction_calls=0,random_calls=0,
        joint_bank_calls=0,cached_a0_used=False,context_sha256=audit.context_sha(observed),raw_a0_sha256=audit.array_sha(raw),
        same_noise=True,a0_slot=0,saved_before_any_branch=True,environment_unchanged=True,
        includes_own_a0_generation=True,restore_included=False,model_loading_included=False,
        new_acceptance_or_selection_rule=False,noise_sha256=noise,base_generation=base,
        proposal_records=[dict(purpose='base',mode=None,seed=seed,stats=base)],post_gradient=dict(value=0),
        predictions=dict(replan=dict(mean_gain=0)),matching=matching)
    old=dict(raw_a0=raw,critic_a0=raw.copy(),mask=saved['mask'],post_command_gradient=direction.copy(),
             post_internal_metric_direction=direction.copy())
    gen=dict(base_seed=seed,base_generation=base,matching=dict(groups={g:dict(achieved_target=0.) for g in ('xyz','gripper')}))
    return 'solo_post',saved,meta,old,gen,observed,case,cut,cfg


def test_post_entry_matches_original_a0_gradient_and_no_cross_calls(method_inputs):
    result=audit.audit_method(*method_inputs)
    assert result['original_post_direction_checked'] and result['actual_policy_calls']==1
    assert not result['captured_native_reference_checked']


@pytest.mark.parametrize('change',['extra_call','noise','context','post_direction','radius'])
def test_bad_standalone_identity_is_not_accepted(method_inputs,change):
    method,saved,meta,old,gen,obs,case,cut,cfg=method_inputs
    if change=='extra_call':meta['joint_bank_calls']=1
    elif change=='noise':meta['noise_sha256']='c'*64
    elif change=='context':meta['context_sha256']='c'*64
    elif change=='post_direction':saved['post_internal_metric_direction']=saved['post_internal_metric_direction']*2
    else:gen['matching']['groups']['xyz']['achieved_target']=.2
    with pytest.raises(ValueError):audit.audit_method(*method_inputs)
