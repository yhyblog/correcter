"""CPU-only terminal audit. Every source joins its immutable transferred claim."""
import csv,json,math,socket,sys
from collections import Counter
from pathlib import Path
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=C/'results/C/C_D24_PI05_SELECTED_H40_H50_V1'
sys.path.insert(0,str(P/'code'))
from qio import read,ref,verify,sha,atomic_json,utc
from selection import consumed_selection,validate_selection
from transfer import validate_partition,verify_dispatcher_exit,assert_not_A_owned
from publication_data import load_evidence
from analysis_tools import pair,read_csv,write_csv
from report import references
sys.path.insert(0,str(C/'work/C/C_D24_QUOTA_INDEPENDENT_QUEUE_V1_r1'))
import queue_common as q
EVENT='C_0b8e67baac47ec45c382138d97fd5891'

def close(a,b):return math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-6)

def main():
    q.authority();event_path=C/'persistent_queue/nodes/C/wakeup/outbox'/(EVENT+'.json');event=read(event_path)
    assert event['node']=='C' and event['hostname']==socket.gethostname() and not event['synthetic']
    assert event['executor_thread_id']=='01a0c793-10d2-7791-a250-fd65d88e1ccb'
    assert event['job']['task_id']==P.name and sha(event['job']['claim_identity']['path'])==event['job']['claim_identity']['sha256']
    result=read(P/'RESULT.json');assert result==event['result'] and result['status']=='complete' and result['report_exit_code']==0
    grant=C/'deadline_20260924/FULL_Q_AUTORUN_AUTHORIZATION_V2.json'
    assert sha(grant)=='fb15e23ad4ed75eaa1b9490784d58dc9dc925e440194e99cab066ae11af6414f'
    selected=consumed_selection();choice=read(verify(selected['A_selection']));lock=read(verify(selected['A_lock']))
    assert lock['immutable'] and lock['selection']['sha256']==selected['A_selection']['sha256']
    assert validate_selection(choice)==selected['chosen_loss']=='L01' and selected['fixed_fit_seed']==9101
    assert not selected['local_test_used'] and not selected['local_X_weights_used']
    ensemble=selected['ensemble'];assets=Path(ensemble['assets']);assert assets==C/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/ensembles/L01_s9101'
    weights=[]
    for member in ensemble['members']:
        p=assets/'models/refit'/f"member_{member['member']}"/'selected.pt'
        assert p.resolve()==Path(member['checkpoint']).resolve() and sha(p)==member['sha256']==ensemble['member_hashes'][str(member['member'])]
        assert Path(member['checkpoint']).is_relative_to(C/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/training')
        weights.append(dict(weight=ref(p),preprocessing=ref(member['preprocessing_evidence'])))
    assert len(weights)==4 and set(ensemble['member_hashes'])=={'1041','1042','1043','1044'}
    consumed=read(P/'TRANSFER_CONSUMED.json');transfer=read(verify(consumed['transfer']));verify(consumed['job_index']);verify(consumed['selection'])
    planned={r['job_id']:read(verify(r)) for r in read(P/'PLANNED_JOB_INDEX.json')['jobs']}
    jobs,units,excluded=validate_partition(transfer,planned,selected);assert len(jobs)==400 and len(units)==2000 and not excluded
    verify_dispatcher_exit(transfer['old_exit_evidence'])
    A_index=read(verify(transfer['A_continuation_job_index']));assert not {r['job_id'] for r in A_index['jobs']}&set(jobs)
    local_index=read(P/'JOB_INDEX.json');assert {r['job_id']:read(verify(r)) for r in local_index['jobs']}==jobs
    for uid,u in units.items():assert_not_A_owned(u['job_id'],uid)
    job_rows,attempts,claims,_=load_evidence();byclaim={r['unit_id']:r for r in claims}
    assert len(job_rows)==400 and len(attempts)==len(claims)==2000 and set(byclaim)==set(units)
    assert all(r['status']=='complete' and r['entered_episodes']==r['terminal_episodes']==5 and r['technical_failures']==0 for r in job_rows)
    assert {r['stage_ordinal'] for r in claims}==set(range(1,2001))
    assert len(list((P/'claims').glob('*.json')))==400
    for uid,c in byclaim.items():
        assert c['source']==units[uid]['source'] and c['attempt']==0 and c['retry'] is False
        assert c['cell_id']==units[uid]['cell_id'] and c['H']==units[uid]['H'] and c['fit_seed']==9101
    raw_rows=[];cuts=[];native=Counter();numeric=Counter();cells={};terminal_commit=0
    for compact in attempts:
        raw=read(compact['result_path']);uid=raw['unit_id'];u=units[uid];s=u['source']
        assert raw['status']=='complete' and raw['terminal'] and type(raw['success']) is bool and raw['technical_failure'] is None
        assert (raw['H'],raw['method'],raw['cell_id'])==(u['H'],u['method'],u['cell_id'])
        assert all(raw[k]==s[k] for k in ['source_id','task','ordinal','env_seed','policy_seed'])
        assert raw['attempt_index']==0 and not raw['corrected_retry'] and raw['loss']=='L01' and raw['fit_seed']==9101
        assert (raw['control_hz'],raw['physics_hz'],raw['action_scale'],raw['action_dim'],raw['renderer'],raw['mode'])==(30,400,.015,4,'NVIDIA_EGL','G0-multi')
        assert 1<=raw['steps']<=300
        triggered=[e for e in raw['events'] if e['intervention_executed']];xs=[e['step'] for e in triggered]
        assert xs==raw['intervention_cuts'] and len(xs)==raw['interventions']
        assert raw['first_cut']==(xs[0] if xs else None) and raw['last_cut']==(xs[-1] if xs else None)
        commit_until=0
        for e in raw['events']:
            assert e['step']>=commit_until and e['step']%5==0 and not e['synthetic'] and not e['forced_intervention']
            if not e['intervention_executed']:continue
            assert e['legal_cut'] and e['history_mature'] and e['true_G0_trigger'] and not e['G0_shadow_only']
            assert e['queue_age']>0 and e['gate_threshold']==.05 and e['gate']>.05 and e['step']+10<=300
            assert e['commit_until']==e['step']+10 and e['restore_native_H']==raw['H'] and e['old_tail_discarded']
            count=min(10,raw['steps']-e['step']);assert e['C10_steps_executed']==count and e['C10_complete']==(count==10)
            if raw['steps']>e['commit_until']:
                assert e['native_H_restored'] and e['native_restore_step']==e['commit_until']
            else:
                assert not e['native_H_restored'] and e.get('restore_not_executed_reason','').startswith('episode_terminal:');terminal_commit+=1
            assert e['new_plan_tail_discarded'] and not e['generation']['Q_acceptance_gate'] and e['generation']['other_direction_calls']==0
            commit_until=e['commit_until'];cuts.append(dict(unit_id=uid,cell_id=raw['cell_id'],source_id=raw['source_id'],H=raw['H'],method=raw['method'],step=e['step'],intervention_index=e['intervention_index'],first_cut=raw['first_cut'],seed=e['seed'],commit_until=e['commit_until'],C10_steps_executed=count,C10_complete=e['C10_complete'],native_H_restored=e['native_H_restored'],terminal_before_restore_reason=e.get('restore_not_executed_reason')))
        n=len(triggered);factor=1 if raw['method']=='Post' else 3;forward=3 if raw['method']=='Post' else 8
        assert raw['counters']['action_gradients']==factor*n and raw['counters']['Q_ensemble_forward']==forward*n
        assert raw['flow_calls']==10*raw['sampling_calls']==raw['numeric_counters']['flow_forward_calls']
        native.update(raw['counters']);numeric.update(raw['numeric_counters']);raw_rows.append(raw)
        cells.setdefault(raw['cell_id'],[]).append(raw)
    summary=read(P/'FINAL_SUMMARY.json');assert summary['valid']==2000 and summary['compute_complete'] and summary['cumulative_C_attempts']==14943
    for cell in summary['cells']:
        rows=cells[cell['cell_id']];assert len(rows)==500 and sum(r['success'] for r in rows)==cell['successes'] and sum(r['interventions'] for r in rows)==cell['interventions']
    barrier=read(P/'H40_DISPATCH_COMPLETE.json');assert barrier['all_job_boundaries_drained']
    assert max(r['episode_finished_utc'] for r in raw_rows if r['H']==40)<=barrier['utc']<min(r['episode_started_utc'] for r in raw_rows if r['H']==50)
    counter=read(P/'ATTEMPT_COUNTER.json');assert counter['count']==2000 and counter['node_cumulative']==14943 and counter['stage_cap']==2200 and counter['node_cap']==16000
    resources=read(P/'RESOURCE_SUMMARY.json');wnative=Counter();wnum=Counter();wreturned=Counter();worker_proof=[]
    for wr in sorted((P/'chains/evaluate/workers').iterdir()):
        end=read(wr/'WORKER_EXIT.json');ready=read(wr/'MODEL_READY.json')
        assert end['fatal'] is None and not end['cleanup'] and not end['numeric']['failed']
        assert end['numeric']['entered']==end['numeric']['returned']
        assert read(wr/'PROCESS_EXIT.json')['exit_code']==0
        wnative.update(end['method_counts']);wnum.update(end['numeric']['entered']);wreturned.update(end['numeric']['returned']);worker_proof.append(dict(worker=wr.name,ready=ref(wr/'MODEL_READY.json'),exit=ref(wr/'WORKER_EXIT.json'),GPU=ready['GPU']))
    assert len(worker_proof)==24 and len(resources['loading'])==24
    assert dict(wnative)==resources['all_worker_method_counts']==dict(native)
    assert dict(wnum)==resources['all_worker_numeric_entered']==resources['all_worker_numeric_returned']==dict(wreturned)
    overhead={k:v-numeric.get(k,0) for k,v in wnum.items()};assert all(v>=0 for v in overhead.values())
    assert overhead['model_initializations']==overhead['policy_model_loads']==24
    baseline,baseline_refs=references();published=list(csv.DictReader((P/'PAIRED.csv').open()));audited_pairs=[]
    for saved in published:
        H=int(saved['H']);method=saved['method'];rows=[r for r in raw_rows if r['H']==H and r['method']==method];table=baseline[(H,saved['reference'])]
        assert len(table)==500
        got=pair(rows,list(table.values()),name=saved['comparison'])
        for k,v in got.items():
            if isinstance(v,(int,float)):assert close(float(saved[k]),v),(k,saved[k],v)
            else:assert saved[k]==v
        audited_pairs.append(dict(got,H=H,method=method,reference=saved['reference']))
    assert len(audited_pairs)==20 and all(r['paired_valid']==500 for r in audited_pairs)
    for H in [40,50]:
        for m in ['Post','Velocity']:assert {'N','R_multi_R','R_once_R'}<={r['reference'] for r in audited_pairs if r['H']==H and r['method']==m}
    write_csv(P/'VELOCITY_OTHER_WORK_PAIRED.csv',[r for r in published if r['method']=='Velocity'])
    write_csv(P/'evidence/ALL_CUTS_AUDITED.csv',cuts)
    px=q.family(P);xx=q.family(q.X);assert px['exited'] and xx['exited']
    previous=read(P/'PREDECESSOR_EXIT.json');assert previous['all_owned_family_exited'] and previous['prior_C_attempts']==12943;verify(previous['result'])
    release=read(P/'chains/evaluate/BEFORE_RESERVATION_RELEASE.json');restore=read(P/'chains/evaluate/RESTORATION.json')
    assert release['cleanup']['status']=='all_formal_group_members_exited' and restore['status']=='occupancy_resolved'
    assert read(P/'chains/evaluate/HOLDER_EXIT_ACK.json')['all_holder_private_sessions_observed_empty']
    guard=q.snapshot('/tmp/gpu_occupancy_guard/status.json');assert len(guard['gpus'])==8 and all(r['state']=='holder' for r in guard['gpus'].values())
    holders=[q.process_identity(r['manager_pid']) for r in guard['gpus'].values()];assert all(r and r['state']!='Z' for r in holders)
    repair=dict(utc=utc(),change='R-once baseline path now follows completed audited LATEST_RUN r2 instead of original empty startup publication',old_reference=str(C/'results/C/C_D24_R_H40_H50_V1/EPISODES.csv'),new_reference=ref(C/'results/C/C_D24_R_H40_H50_V1/r2/EPISODES.csv'),latest_pointer=ref(C/'results/C/C_D24_R_H40_H50_V1/LATEST_RUN.json'),old_report=ref(P/'evidence/R_ONCE_REFERENCE_FIX/report.py'),new_report=ref(P/'code/report.py'),old_pair_count=16,new_pair_count=20,added_R_once_pairs=4,scientific_compute=0,original_results_unchanged=True)
    atomic_json(P/'evidence/R_ONCE_REFERENCE_FIX/RESULT.json',repair)
    audit=dict(event_id=EVENT,task_id=P.name,status='audited_complete',utc=utc(),event=ref(event_path),claim=ref(P/'CLAIM.json'),authorization=ref(grant),Post_only_selection=selected['A_selection'],selection_lock=selected['A_lock'],selected_loss='L01',fit_seed=9101,A_pi05_Q_weights=weights,local_X_Q_used=False,ownership=dict(transfer=consumed['transfer'],local_index=consumed['job_index'],exact_granted_jobs=400,exact_granted_units=2000,unique_job_claims=400,unique_unit_claims=2000,A_overlapping_claims=0,other_node_overlap=0,seed_and_source_changes=0),cells=summary['cells'],valid=2000,technical=0,unknown=0,not_started=0,retries=0,replays=0,source_terminal_table=ref(P/'SOURCE_TERMINALS.csv'),cuts=dict(total=len(cuts),first_cut_C10_checks=2000,early_terminal_before_restore=terminal_commit,early_terminal_is_legitimate=True,per_cut=ref(P/'evidence/ALL_CUTS_AUDITED.csv')),paired=audited_pairs,pair_sources=baseline_refs,publication_repair=ref(P/'evidence/R_ONCE_REFERENCE_FIX/RESULT.json'),costs=dict(whole_worker_method_counts=dict(wnative),whole_worker_numeric_entered=dict(wnum),whole_worker_numeric_returned=dict(wreturned),episode_numeric_totals=dict(numeric),non_episode_numeric_overhead=overhead,worker_proof=worker_proof,summary=ref(P/'RESOURCE_SUMMARY.json'),no_failed_or_unknown_costs_imputed=True),ordering=dict(H40_barrier=ref(P/'H40_DISPATCH_COMPLETE.json'),H50_after_all_H40_sources=True,original_X_exit=previous),actual_X_family_exit=xx,actual_Pi05_family_exit=px,occupancy=dict(exit=ref(P/'chains/evaluate/BEFORE_RESERVATION_RELEASE.json'),restoration=ref(P/'chains/evaluate/RESTORATION.json'),restored_at=restore['observed_at']['utc'],current_cached_guard=guard,current_holder_manager_identities=holders,GPU_probes_in_audit=0),Post_current_paper=True,Velocity_separate_files=[str(P/'VELOCITY_OTHER_WORK_CELLS.csv'),str(P/'VELOCITY_OTHER_WORK_PAIRED.csv')],statistics_scope='Pointwise within fixed tasks/source bootstrap; no multiplicity/training-seed uncertainty. Old-Q once comparison changes both Q and mode. Cross-host runtime is descriptive.',new_scientific_compute=0,new_training_updates=0,new_collection=0,recursive_wakeup=False)
    target=P/'evidence'/('TERMINAL_AUDIT_'+EVENT+'.json');atomic_json(target,audit)
    lines=['C π0.5 H40/H50 终局审计通过。','', 'A Post-only开发集锁定L01、fit9101四成员；400个精确转移job、2000个唯一源claim全部合法终局。技术故障、未知、重试与重放均为0。','', '| H | 方法 | 成功/有效 | 相对N百分点 | 相对R-multi百分点 | 相对R-once百分点 |','|---|---|---:|---:|---:|---:|']
    for c in summary['cells']:
        vals={r['reference']:r['difference_pp'] for r in audited_pairs if r['H']==c['H'] and r['method']==c['method']}
        lines.append(f"| {c['H']} | {c['method']} | {c['successes']}/500 | {vals['N']:+.1f} | {vals['R_multi_R']:+.1f} | {vals['R_once_R']:+.1f} |")
    lines+=['', 'Post进入本篇，Velocity单独保存。与R-multi的四项区间均包含0；与N、R-once及旧Q once的比较保留完整配对区间。旧Q once比较同时改变Q与触发次数，不能视为纯Q效果。','', f'逐次cut共{len(cuts)}次；first_cut、C10禁止重入及正常回合终止的提前退出均已核查。24个worker的调用、加载和非回合开销分别对账。','', '修复了R-once汇总指向旧空表的问题，改读已审计r2的现有结果，补齐4项各500对比较；没有新增科学计算。','', '原X及本批次正式族均已退出，18:20:19 UTC恢复八卡holder；当前8个holder管理进程存活。','', '详细审计：'+str(target)]
    (P/'TERMINAL_AUDIT.md').write_text('\n'.join(lines)+'\n')
    atomic_json(C/'receipts/C/C_D24_PI05_SELECTED_H40_H50_V1_TERMINAL_AUDIT_r1.json',dict(utc=utc(),task_id=P.name,event_id=EVENT,status='audited_complete',audit=ref(target),summary=ref(P/'TERMINAL_AUDIT.md'),valid=2000,pair_count=20,new_scientific_compute=0))
    print(json.dumps(dict(audit=str(target),valid=2000,pairs=20,cuts=len(cuts),status='audited_complete'),ensure_ascii=False))

if __name__=='__main__':main()
