"""Synthetic CPU diagnostics only; never opens real calibration data."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
from . import calibration_diagnostics_v1 as diag


def fixture():
    ids=[f'task_{i%5}__{i}' for i in range(100)]
    cases=[dict(episode_id=p,case_id=p,split='calibration',task=f'task_{i%5}') for i,p in enumerate(ids)]
    config=dict(episode_manifest=cases,split_replicates={'calibration':2},analysis_approval={'protocol_sha256':'p'},
        main_collection=dict(banks={diag.BANK:dict(kind='policy5',stage='calibration',episode_ids=ids,model_hashes={},critic_member_hashes={str(m):str(m) for m in range(4)})},replacement_candidates={p:[] for p in ids}),
        critic_assets='/synthetic/selected',calibration_collection=dict(selected_training=dict(selected_seal_sha256='s',selected_reload_audit_sha256='r')),
        matching=dict(boundary_clearance=.05,tolerance=1e-6,xyz_rms=.05,gripper_rms=.1,xyz_linf=.15,gripper_linf=.4))
    y=np.zeros((100,5,2),bool);y[0,4]=True
    rows=[dict(planned_slot_id=p,resolved_episode_id=p,task=cases[i]['task'],no_cut=i!=0,actual_cut=5 if i==0 else None,
        scene_fingerprint=f'{i:064x}',outcomes=dict(zip(diag.METHODS,y[i].tolist())),resolution={'ordered_rejections':[]}) for i,p in enumerate(ids)]
    def group(data):
        if not len(data):return dict(sources=0,logical_outcomes_per_arm=0,success_counts=None,success_rates=None,comparisons=None)
        comparisons={}
        for a,b in diag.COMPARISONS:
            delta=(data[:,a].astype(int)-data[:,b].astype(int)).mean(1)
            comparisons[diag.METHODS[a]+'_minus_'+diag.METHODS[b]]=dict(gain=float(delta.mean()),rescues=int((data[:,a]&~data[:,b]).sum()),
                harms=int((~data[:,a]&data[:,b]).sum()),positive_sources=int((delta>0).sum()),negative_sources=int((delta<0).sum()),zero_sources=int((delta==0).sum()),source_95ci=[-.123,.456])
        return dict(sources=len(data),logical_outcomes_per_arm=2*len(data),success_counts=dict(zip(diag.METHODS,data.sum((0,2)).tolist())),
            success_rates=dict(zip(diag.METHODS,data.mean((0,2)).tolist())),comparisons=comparisons)
    statistics=dict(status='complete_statistics_proposal_only',source_denominator=100,replicates=2,logical_outcomes_per_arm=200,
        primary_ids=ids,resolved_source_ids=ids,technical_missing=0,physical_branch_count=10,overall=group(y),
        per_task={f'task_{k}':group(y[k::5]) for k in range(5)},alarm_conditioned=group(y[:1]),no_cut_common_outcomes=group(y[1:]),
        bootstrap=dict(draws=10000,seed=2026091622),selection_proposal={'status':'proposal_only','method':'post'})
    audit=dict(status='passed',role=diag.AUDIT_ROLE,stage=diag.STAGE,bank_version=diag.BANK,config_sha256='c',config_content_sha256=diag._canonical(config),
        protocol_sha256='p',planned_slots=100,technical_missing=0,per_source=rows,statistics=statistics,physical_branches=10,
        resource_totals={'simulator_attempts':111,'training_updates':0},new_attempts=111,attempts_by_stage_kind={'calibration':{'source_capture':100,'candidate_restore':1,'branch_including_restore':10}})
    return config,audit,y


def test_all100_two_repeats_gate():
    c,a,y=fixture();np.testing.assert_array_equal(diag.validate_gate(c,a,config_sha256='c'),y)
    assert a['statistics']['overall']['comparisons'][diag.PRIMARY]['gain']==.01


@pytest.mark.parametrize('change',['partial','missing','duplicate','four_repeats','mixed_no_alarm','stage','hash','counts'])
def test_gate_rejects_incomplete_or_mismatched(change):
    c,a,_=fixture()
    if change=='partial':a['per_source'].pop()
    elif change=='missing':a['technical_missing']=1
    elif change=='duplicate':a['per_source'][1]['resolved_episode_id']=a['per_source'][0]['resolved_episode_id']
    elif change=='four_repeats':a['per_source'][0]['outcomes']['post']=[True]*4
    elif change=='mixed_no_alarm':a['per_source'][1]['outcomes']['post'][0]=True
    elif change=='stage':a['stage']='round2_development_policy'
    elif change=='hash':a['config_content_sha256']='x'
    elif change=='counts':a['statistics']['overall']['success_counts']['post']=200
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
    with pytest.raises(ValueError,match='whole calibration'):
        diag.run(root/'missingconfig',root/'missingaudit',root/'calibration_execution/calibration/v/w',output_path=root/'calibration_diagnostics/new',root=root)


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
    audit.update(config_sha256=diag._hash(configpath),config_content_sha256=diag._canonical(config))
    ids=config['main_collection']['banks'][diag.BANK]['episode_ids']
    wave=root/'calibration_execution'/diag.STAGE/diag.BANK/'synthetic'
    dump(wave/'launch_result.json',dict(status='complete',returncode=0,lifecycle_covers_entire_wave=True,hold_idle=False,wall_seconds_including_lifecycle=10))
    dump(wave/'wave_spec.json',dict(stage=diag.STAGE,bank_version=diag.BANK,workers=32,paired_suffixes_per_state=2,
        original_primary_slots=100,global_choice_applied_during_collection=False,config_sha256=diag._hash(configpath),freeze_sha256=diag._hash(freeze)))
    loaded=dict(status='passed',stage=diag.STAGE,selected_assets='/synthetic/selected',selected_path='/synthetic/selected',selected_seal_sha256='s',selected_reload_audit_sha256='r',
        member_hashes={str(m):str(m) for m in range(4)},model_hashes={str(m):str(m) for m in range(4)},selection=dict(path='A',step=4000),optimizer_updates=0,
        actual_selector_paths=True,checkpoint_file_sha=True,frozen_parameter_buffer_versions=True,eval_cpu_no_parameter_grad=True,
        model_paths=[f'/synthetic/selected/models/refit/member_{m}/selected.pt' for m in range(4)])
    for rank in range(32):
        folder=wave/'workers'/f'worker_{rank:02d}';assigned=ids[rank::32]
        dump(folder/'status.json',dict(status='complete',stage=diag.STAGE,bank_version=diag.BANK,workers=32,wave_id='synthetic',missing_slot_ids=[],rank=rank,
            config_sha256=diag._hash(configpath),freeze_sha256=diag._hash(freeze),guard_factory='create_calibration_collector',slot_entry='collect_calibration_slot',
            assigned_slot_ids=assigned,completed_slot_records=len(assigned),global_choice_applied_during_collection=False,
            no_cut_sources=len(assigned)-(rank==0),actual_branch_count=10 if rank==0 else 0,loading_seconds=1,wall_seconds=2,
            started_utc='2026-01-01T00:00:00',finished_utc='2026-01-01T00:00:02'))
        dump(folder/'loaded_model_identity.json',loaded);seal(folder,'guarded_calibration_worker')
    for index,row in enumerate(audit['per_source']):
        case=config['episode_manifest'][index];folder=root/'sources'/case['case_id']
        dump(folder/'summary.json',dict(case=case,planned_slot_id=row['planned_slot_id'],protocol_sha256='p',actual_cut=row['actual_cut'],no_cut=row['no_cut'],
            source_capture_stage=diag.STAGE,selection_audit={'training_fallback_allowed':False},wall_seconds=1,policy_calls=1,policy_seconds=.2,environment_seconds=.4,steps=5))
        seal(folder,track=True)
    first=ids[0];source=root/'sources'/first;bank=root/'banks'/diag.BANK/first/'cut005'
    bank.mkdir(parents=True);plans={m:np.zeros((50,4),np.float32) for m in diag.METHODS[1:]}
    np.savez(bank/'plans.npz',**plans)
    generation=dict(episode_id=first,cut_step=5,stage=diag.STAGE,bank_version=diag.BANK,protocol_sha256='p',model_hashes={},
        base_generation=dict(noise_sha256='n',seconds=.1,fallback=None),guidance={m:dict(seconds=.2,updates=[],fallback=None) for m in ('velocity','direct')},
        post_gradient=dict(seconds=.01),restore_seconds=.3,candidate_bank_seconds=.6,generation_wall_seconds=1,
        bank_predictions={m:dict(mean_gain=0,candidate_mean_probability=.5,a0_mean_probability=.5) for m in diag.METHODS[1:]})
    dump(bank/'generation.json',generation);seal(bank,track=True)
    guard=root/'calibration_guard'/diag.STAGE/diag.BANK/first
    dump(guard/'bank_check.json',dict(status='passed',checked_before_branch=True,episode_id=first,cut=5,
        source_seal_sha256=diag._hash(source/'complete.json'),bank_seal_sha256=diag._hash(bank/'complete.json'),old_development_a0_compared=False,noise_sha256='n'))
    seal(guard,'calibration_same_bank_check',track=True)
    for arm,method in enumerate(diag.METHODS):
        for repeat in range(2):
            folder=root/'rollouts'/diag.STAGE/diag.BANK/first/'cut005'/method/f'repeat_{repeat}'
            dump(folder/'summary.json',dict(status='complete',episode_id=first,method=method,repeat=repeat,
                candidate_bank_sha256=diag._hash(bank/'complete.json'),success=bool(y[0,arm,repeat]),
                actual_prefix_steps=5 if arm==0 else 10,requested_prefix_steps=5 if arm==0 else 10,
                command_sha256=diag.hashlib.sha256(np.zeros((10,4),np.float32).tobytes()).hexdigest(),
                wall_seconds=2,restore_seconds=.3,policy_seconds=.4,environment_seconds=.5,policy_calls=1,terminal_step=20))
            seal(folder,track=True)
    audit['artifacts']=artifacts;auditpath=root/'audit';dump(auditpath/'result.json',audit);seal(auditpath,diag.AUDIT_ROLE)
    dump(root/'budget/attempts.jsonl',{'synthetic':True})
    output=root/'calibration_diagnostics/synthetic';result=diag.run(configpath,auditpath,wave,output_path=output,root=root)
    assert result['source_denominator']==100 and result['command_q_denominator']==1
    saved=diag._read(output/'result.json');diag._seal(output,role=diag.SCHEMA)
    assert saved['primary_statistics']==audit['statistics']
    assert saved['q_missing_no_cut_sources']==99 and saved['physical_branches']==10
    assert saved['quality']['aliases_of_a0']['post']==1
    assert saved['q_vs_actual']['post']['all_cut_sources']['mean_prediction_minus_actual_gain']==-1
    assert saved['cost']['capture']['wall_seconds']['sum']==100
    assert saved['cost']['generation']['restore_seconds']['sum']==.3
    assert saved['ledger_sha256_before']==saved['ledger_sha256_after'] and saved['selection_seals_written']==0
    assert saved['model_calls']==saved['simulator_calls']==saved['optimizer_updates']==0
    text=(output/'report.md').read_text()
    assert '主比较' in text and '-12.30, 45.60' in text and 'provenance.json' in text
    assert not list(root.glob('**/selected_policy*'))
    with pytest.raises(FileExistsError):diag.run(configpath,auditpath,wave,output_path=output,root=root)
    changed=source/'summary.json';changed.write_text('{}')
    with pytest.raises(ValueError,match='changed'):
        diag.run(configpath,auditpath,wave,output_path=root/'calibration_diagnostics/changed',root=root)
