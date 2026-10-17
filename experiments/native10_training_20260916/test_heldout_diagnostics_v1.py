"""Synthetic CPU diagnostics only; never opens real heldout data."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
from . import heldout_diagnostics_v1 as diag


def fixture():
    ids=[f'task_{i%5}__{i}' for i in range(100)]
    cases=[dict(episode_id=p,case_id=p,split='heldout',task=f'task_{i%5}') for i,p in enumerate(ids)]
    config=dict(episode_manifest=cases,split_replicates={'heldout':4},analysis_approval={'protocol_sha256':'p'},
        main_collection=dict(banks={diag.BANK:dict(kind='policy5',stage='heldout',episode_ids=ids,model_hashes={},critic_member_hashes={str(m):str(m) for m in range(4)})},replacement_candidates={p:[] for p in ids}),
        critic_assets='/synthetic/selected',heldout_collection=dict(selected_training=dict(selected_seal_sha256='s',selected_reload_audit_sha256='r'),
            final_selection=dict(path='/synthetic/final_selections/final_selection_v1',seal_sha256='s'*64,result_sha256='r'*64)),
        matching=dict(boundary_clearance=.05,tolerance=1e-6,xyz_rms=.05,gripper_rms=.1,xyz_linf=.15,gripper_linf=.4))
    y=np.zeros((100,5,4),bool);y[0,4]=True
    rows=[dict(planned_slot_id=p,resolved_episode_id=p,task=cases[i]['task'],no_cut=i!=0,actual_cut=5 if i==0 else None,
        scene_fingerprint=f'{i:064x}',outcomes=dict(zip(diag.METHODS,y[i].tolist())),resolution={'ordered_rejections':[]}) for i,p in enumerate(ids)]
    def group(data):
        if not len(data):return dict(sources=0,logical_outcomes_per_arm=0,success_counts=None,success_rates=None,comparisons=None)
        comparisons={}
        for a,b in diag.COMPARISONS:
            delta=(data[:,a].astype(int)-data[:,b].astype(int)).mean(1)
            comparisons[diag.METHODS[a]+'_minus_'+diag.METHODS[b]]=dict(gain=float(delta.mean()),rescues=int((data[:,a]&~data[:,b]).sum()),
                harms=int((~data[:,a]&data[:,b]).sum()),positive_sources=int((delta>0).sum()),negative_sources=int((delta<0).sum()),zero_sources=int((delta==0).sum()),source_95ci=[-.123,.456])
        return dict(sources=len(data),logical_outcomes_per_arm=4*len(data),success_counts=dict(zip(diag.METHODS,data.sum((0,2)).tolist())),
            success_rates=dict(zip(diag.METHODS,data.mean((0,2)).tolist())),comparisons=comparisons)
    statistics=dict(status='complete_statistics_fixed_policy',source_denominator=100,replicates=4,logical_outcomes_per_arm=400,
        primary_ids=ids,resolved_source_ids=ids,technical_missing=0,physical_branch_count=20,overall=group(y),
        per_task={f'task_{k}':group(y[k::5]) for k in range(5)},alarm_conditioned=group(y[:1]),no_cut_common_outcomes=group(y[1:]),
        bootstrap=dict(draws=10000,seed=2026091622),fixed_method='post',primary_comparison=diag.PRIMARY,calibration_outcomes_pooled=False)
    statistics['primary_assessment']=dict(comparison=diag.PRIMARY,method_fixed_before_heldout='post',
        paired_success_difference=4,point_estimate=.01,practical_target=.05,point_estimate_target_met=False,
        source_95ci=[-.123,.456],ci_supports_positive_gain=False,true_gain_at_least_target_guaranteed=False,
        nonpositive_or_crossing_ci_does_not_prove_ineffectiveness=True,posthoc_method_selection=False,selection_rule_changed=False)
    audit=dict(status='passed',role=diag.AUDIT_ROLE,stage=diag.STAGE,bank_version=diag.BANK,config_sha256='c',config_content_sha256=diag._canonical(config),
        protocol_sha256='p',planned_slots=100,technical_missing=0,per_source=rows,statistics=statistics,physical_branches=20,
        selected_training=deepcopy(config['heldout_collection']['selected_training']),
        final_selection=deepcopy(config['heldout_collection']['final_selection']),primary_assessment=deepcopy(statistics['primary_assessment']),
        resource_totals={'simulator_attempts':121,'training_updates':0},new_attempts=121,attempts_by_stage_kind={'heldout':{'source_capture':100,'candidate_restore':1,'branch_including_restore':20}})
    return config,audit,y


def test_all100_four_repeats_gate():
    c,a,y=fixture();np.testing.assert_array_equal(diag.validate_gate(c,a,config_sha256='c'),y)
    assert a['statistics']['overall']['comparisons'][diag.PRIMARY]['gain']==.01


@pytest.mark.parametrize('change',['partial','missing','duplicate','two_repeats','mixed_no_alarm','stage','hash','counts',
    'calibration_pool','reselection','method','assessment','selection_binding','trained_binding','eighth_comparison'])
def test_gate_rejects_incomplete_or_mismatched(change):
    c,a,_=fixture()
    if change=='partial':a['per_source'].pop()
    elif change=='missing':a['technical_missing']=1
    elif change=='duplicate':a['per_source'][1]['resolved_episode_id']=a['per_source'][0]['resolved_episode_id']
    elif change=='two_repeats':a['per_source'][0]['outcomes']['post']=[True]*2
    elif change=='mixed_no_alarm':a['per_source'][1]['outcomes']['post'][0]=True
    elif change=='stage':a['stage']='round2_development_policy'
    elif change=='hash':a['config_content_sha256']='x'
    elif change=='counts':a['statistics']['overall']['success_counts']['post']=200
    elif change=='calibration_pool':a['statistics']['calibration_outcomes_pooled']=True
    elif change=='reselection':a['selection_proposal']={'method':'direct'}
    elif change=='method':a['statistics']['fixed_method']='direct'
    elif change=='assessment':a['primary_assessment']['point_estimate_target_met']=True
    elif change=='selection_binding':a['final_selection']['result_sha256']='different'
    elif change=='trained_binding':a['selected_training']['selected_seal_sha256']='different'
    elif change=='eighth_comparison':a['statistics']['overall']['comparisons']['random_minus_post']={}
    with pytest.raises(ValueError):diag.validate_gate(c,a,config_sha256='c')


def test_q_no_alarm_not_zero_imputed():
    c,a,y=fixture();sources=[dict(task='task',no_cut=True,q=None,command_diagnostic=None)]*99
    sources.append(dict(task='task',no_cut=False,q={m:dict(predicted_gain=.1,actual_source_gain=.5) for m in diag.CORRECTIONS},
        command_diagnostic={'methods':{m:dict(raw_alias_of_a0=False) for m in diag.CORRECTIONS}}))
    q=diag.summarize_q(sources)['post']['all_cut_sources']
    assert q['sources']==1 and q['predicted_gain']['mean']==.1 and q['mean_prediction_minus_actual_gain']==-.4
    assert q['pearson'] is None
    empty=diag.summarize_q(sources[:-1])['post']['all_cut_sources']
    assert empty['sources']==0 and empty['mean_prediction_minus_actual_gain'] is None


def test_shared_raw_math_unchanged():
    assert diag.command_diagnostics is diag.pure.command_diagnostics
    assert diag.association is diag.pure.association


def test_running_wave_rejected_before_outcomes(tmp_path,monkeypatch):
    root=tmp_path
    monkeypatch.setattr(diag,'_seal',lambda *a,**k:pytest.fail('Must not read audit outcomes while wave runs'))
    with pytest.raises(ValueError,match='whole heldout'):
        diag.run(root/'missingconfig',root/'missingaudit',root/'heldout_execution/heldout/v/w',output_path=root/'heldout_diagnostics/new',root=root)


def test_synthetic_completed_wave_end_to_end(tmp_path):
    root=tmp_path;config,audit,y=fixture();artifacts=[]
    def dump(path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
    def seal(path,role=None,track=False):
        record=dict(status='complete',protocol_sha256='p',files={str(p.relative_to(path)):diag._hash(p) for p in path.rglob('*') if p.is_file()})
        if role:record['role']=role
        dump(path/'complete.json',record)
        if track:artifacts.extend(dict(path=str(p),sha256=diag._hash(p)) for p in path.rglob('*') if p.is_file())
    configpath=root/'protocol/config.json';dump(configpath,config)
    freeze=root/'protocol/freeze.json';dump(freeze,dict(config_sha256=diag._hash(configpath),files={str(configpath):diag._hash(configpath)}))
    audit.update(config_sha256=diag._hash(configpath),config_content_sha256=diag._canonical(config),freeze_sha256=diag._hash(freeze))
    ids=config['main_collection']['banks'][diag.BANK]['episode_ids']
    wave=root/'heldout_execution'/diag.STAGE/diag.BANK/'synthetic'
    audit['wave_gate']={'wave_path':str(wave)}
    dump(wave/'launch_result.json',dict(status='complete',returncode=0,lifecycle_covers_entire_wave=True,hold_idle=False,wall_seconds_including_lifecycle=10))
    dump(wave/'wave_spec.json',dict(stage=diag.STAGE,bank_version=diag.BANK,workers=32,paired_suffixes_per_state=4,
        original_primary_slots=100,global_choice_applied_during_collection=False,config_sha256=diag._hash(configpath),freeze_sha256=diag._hash(freeze),
        fixed_main_injection='post',primary_policy_fixed_before_heldout=True,selection_after_heldout_allowed=False,
        physical_arms=list(diag.METHODS),final_selection=config['heldout_collection']['final_selection']))
    loaded=dict(status='passed',stage=diag.STAGE,selected_assets='/synthetic/selected',selected_path='/synthetic/selected',selected_seal_sha256='s',selected_reload_audit_sha256='r',
        member_hashes={str(m):str(m) for m in range(4)},model_hashes={str(m):str(m) for m in range(4)},selection=dict(path='A',step=4000),optimizer_updates=0,
        actual_selector_paths=True,checkpoint_file_sha=True,frozen_parameter_buffer_versions=True,eval_cpu_no_parameter_grad=True,
        final_selection=dict(status='sealed',**config['heldout_collection']['final_selection'],method='post',post_enabled_on_alarm=True,
            primary_comparison=diag.PRIMARY,selection_after_heldout_allowed=False),
        model_paths=[f'/synthetic/selected/models/refit/member_{m}/selected.pt' for m in range(4)])
    for rank in range(32):
        folder=wave/'workers'/f'worker_{rank:02d}';assigned=ids[rank::32]
        dump(folder/'status.json',dict(status='complete',stage=diag.STAGE,bank_version=diag.BANK,workers=32,wave_id='synthetic',missing_slot_ids=[],rank=rank,
            config_sha256=diag._hash(configpath),freeze_sha256=diag._hash(freeze),guard_factory='create_heldout_collector',slot_entry='collect_heldout_slot',
            assigned_slot_ids=assigned,completed_slot_records=len(assigned),global_choice_applied_during_collection=False,
            fixed_main_injection='post',primary_policy_fixed_before_heldout=True,selection_after_heldout_allowed=False,
            final_selection=config['heldout_collection']['final_selection'],
            no_cut_sources=len(assigned)-(rank==0),actual_branch_count=20 if rank==0 else 0,loading_seconds=1,wall_seconds=2,
            started_utc='2026-01-01T00:00:00',finished_utc='2026-01-01T00:00:02'))
        dump(folder/'loaded_model_identity.json',loaded);seal(folder,'guarded_heldout_worker')
    for index,row in enumerate(audit['per_source']):
        case=config['episode_manifest'][index];folder=root/'sources'/case['case_id']
        dump(folder/'summary.json',dict(case=case,planned_slot_id=row['planned_slot_id'],protocol_sha256='p',actual_cut=row['actual_cut'],no_cut=row['no_cut'],
            source_capture_stage=diag.STAGE,selection_audit={'training_fallback_allowed':False},wall_seconds=1,policy_calls=1,policy_seconds=.2,environment_seconds=.4,steps=5))
        seal(folder,track=True)
    first=ids[0];source=root/'sources'/first;bank=root/'banks'/diag.BANK/first/'cut005'
    bank.mkdir(parents=True);plans,formal,dependency_guard=dependency_fixture()
    np.savez(bank/'plans.npz',**plans)
    np.savez(bank/'formal_directions.npz',**formal)
    generation=dict(episode_id=first,cut_step=5,stage=diag.STAGE,bank_version=diag.BANK,protocol_sha256='p',model_hashes={},
        base_generation=dict(noise_sha256='n',seconds=.1,fallback=None),guidance={m:dict(seconds=.2,updates=[],fallback=None) for m in ('velocity','direct')},
        post_gradient=dict(seconds=.01),restore_seconds=.3,candidate_bank_seconds=.6,generation_wall_seconds=1,
        bank_predictions={m:dict(mean_gain=0,candidate_mean_probability=.5,a0_mean_probability=.5) for m in diag.METHODS[1:]})
    dump(bank/'generation.json',generation);seal(bank,track=True)
    guard=root/'heldout_guard'/diag.STAGE/diag.BANK/first
    dump(guard/'bank_check.json',dict(status='passed',checked_before_branch=True,episode_id=first,cut=5,
        source_seal_sha256=diag._hash(source/'complete.json'),bank_seal_sha256=diag._hash(bank/'complete.json'),old_development_a0_compared=False,noise_sha256='n',**dependency_guard))
    seal(guard,'heldout_same_bank_check',track=True)
    for arm,method in enumerate(diag.METHODS):
        for repeat in range(4):
            folder=root/'rollouts'/diag.STAGE/diag.BANK/first/'cut005'/method/f'repeat_{repeat}'
            dump(folder/'summary.json',dict(status='complete',episode_id=first,method=method,repeat=repeat,
                candidate_bank_sha256=diag._hash(bank/'complete.json'),success=bool(y[0,arm,repeat]),
                actual_prefix_steps=5 if arm==0 else 10,requested_prefix_steps=5 if arm==0 else 10,
                command_sha256=diag.hashlib.sha256(np.zeros((10,4),np.float32).tobytes()).hexdigest(),
                wall_seconds=2,restore_seconds=.3,policy_seconds=.4,environment_seconds=.5,policy_calls=1,terminal_step=20))
            seal(folder,track=True)
    audit['artifacts']=artifacts;auditpath=root/'audit';dump(auditpath/'result.json',audit);seal(auditpath,diag.AUDIT_ROLE)
    dump(root/'budget/attempts.jsonl',{'synthetic':True})
    output=root/'heldout_diagnostics/synthetic';result=diag.run(configpath,auditpath,wave,output_path=output,root=root)
    assert result['source_denominator']==100 and result['command_q_denominator']==1
    saved=diag._read(output/'result.json');diag._seal(output,role=diag.SCHEMA)
    assert saved['primary_statistics']==audit['statistics']
    assert saved['primary_assessment']==audit['primary_assessment'] and saved['fixed_method']=='post'
    assert saved['calibration_outcomes_pooled'] is False and saved['selection_proposals_written']==0
    assert saved['q_missing_no_cut_sources']==99 and saved['physical_branches']==20
    assert saved['quality']['aliases_of_a0']['post']==1
    assert saved['quality']['dependency_aliases_of_a0']['random_matched']==1
    assert saved['per_source'][0]['matching_dependencies']['reverse_random_physical_branches'] is False
    assert saved['q_vs_actual']['post']['all_cut_sources']['mean_prediction_minus_actual_gain']==-1
    assert saved['cost']['capture']['wall_seconds']['sum']==100
    assert saved['cost']['generation']['restore_seconds']['sum']==.3
    assert saved['ledger_sha256_before']==saved['ledger_sha256_after'] and saved['selection_seals_written']==0
    assert saved['model_calls']==saved['simulator_calls']==saved['optimizer_updates']==0
    assert saved['runtime']['gpu_worker_envelopes']['7']['worker_envelope_wall_seconds']==2
    text=(output/'report.md').read_text()
    assert '主比较' in text and '-12.30, 45.60' in text and 'provenance.json' in text and '成功/400' in text
    assert '不保证真实提升至少 5 pp' in text and '没有读取或合并校准结局' in text
    assert not list(root.glob('**/selected_policy*'))
    with pytest.raises(FileExistsError):diag.run(configpath,auditpath,wave,output_path=output,root=root)
    changed=source/'summary.json';changed.write_text('{}')
    with pytest.raises(ValueError,match='changed'):
        diag.run(configpath,auditpath,wave,output_path=root/'heldout_diagnostics/changed',root=root)


def dependency_fixture(amplitude=0.,signed_zero=False):
    raw=np.zeros((50,4),np.float32)
    if signed_zero:raw[0,0]=-0.
    plans={m:raw.copy() for m in diag.METHODS[1:]};formal={};actual={}
    mapping={'replan':'alarm_replan10','velocity_matched':'velocity','direct_matched':'direct','post_matched':'post'}
    for name in ('replan',)+diag.DEPENDENCIES:
        plan=raw.copy()
        if name!='replan' and amplitude:
            plan[:10]=np.float32(-amplitude if name=='reverse_matched' else amplitude)
        delta=plan[:10].astype(np.float64)-raw[:10].astype(np.float64)
        formal[name+'_actual_delta']=delta;formal[name+'_critic_commands']=np.clip(plan[:10],-1,1)
        actual[name]=dict(actual_delta=diag._radii(delta),critic_mapping_passed=True,mask_passed=True)
        if name in mapping:plans[mapping[name]]=plan
    guard=dict(complete_matching_dependencies=list(diag.DEPENDENCIES),reverse_random_physical_branches=False,
        raw_a0_identity_scope='within_this_new_heldout_bank',raw50_sha256=diag.hashlib.sha256(raw.tobytes()).hexdigest(),
        critic_command_mapping_exact=True,raw_tail_and_mask_preserved=True,finite_post_gradients=True,slot_zero_anchor_exact=True,
        dependency_raw_audit=dict(status='passed',anchor_bit_identical=True,actual=actual),dependency_rms_spread=dict(xyz=0.,gripper=0.))
    return plans,formal,guard


@pytest.mark.parametrize('amplitude,signed_zero',[(0.,False),(.02,False),(0.,True)])
def test_saved_all_five_dependencies_and_signed_zero(amplitude,signed_zero):
    c,_,_=fixture();plans,formal,guard=dependency_fixture(amplitude,signed_zero)
    result=diag.dependency_diagnostics(plans,formal,guard,c['matching'])
    assert result['status']=='passed' and result['reverse_random_physical_branches'] is False
    assert result['raw_unique_groups']==(1 if not amplitude else 3)
    assert result['methods']['reverse_matched']['physical_arm'] is None
    assert result['methods']['random_matched']['raw_alias_of_a0']==(not amplitude)


@pytest.mark.parametrize('change',['missing_random','reverse_physical','raw_anchor','different_delta','mismatched_rms','missing_gradient_proof'])
def test_saved_dependency_proof_rejects_change(change):
    c,_,_=fixture();plans,formal,guard=dependency_fixture(.02)
    if change=='missing_random':formal.pop('random_matched_actual_delta')
    elif change=='reverse_physical':guard['reverse_random_physical_branches']=True
    elif change=='raw_anchor':guard['raw50_sha256']='changed'
    elif change=='different_delta':formal['post_matched_actual_delta'][0,0]=.5
    elif change=='mismatched_rms':guard['dependency_rms_spread']['xyz']=.1
    elif change=='missing_gradient_proof':guard.pop('finite_post_gradients')
    with pytest.raises(ValueError):diag.dependency_diagnostics(plans,formal,guard,c['matching'])


def test_gpu_wall_envelopes_are_not_sum_of_worker_times():
    workers=[dict(rank=i,started_utc=f'2026-01-01T00:00:0{i%4}+00:00',finished_utc=f'2026-01-01T00:00:0{5+i%4}+00:00') for i in range(32)]
    result=diag.gpu_worker_envelopes(workers)
    assert result['0']['worker_envelope_wall_seconds']==8
    assert result['7']['worker_ranks']==[28,29,30,31]
