"""Seal C's r4 callback audit, including the already-finished r5 successor."""
import collections
import json
import sys
from pathlib import Path

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=C/'results/C/C_D24_L11_RETEST_V1'
E='C_4834113fcd0b6f4d5d6f6ba9fff7b341'
O=R/'event_audits'/E
sys.path.insert(0,str(R/'continuations/r4/code'))
from qio import read,new_json,atomic_json,ref,utc


def main():
    units=read(R/'UNIT_INDEX.json'); byid={u['unit_id']:u for u in units}
    roots=[R]+[R/'continuations'/s for s in ['r2','r3','r4','r5']]
    claims=collections.defaultdict(list)
    for root in roots:
        for p in (root/'claims/units').glob('*.json'):
            v=read(p);assert v['unit_id'] in byid
            claims[v['unit_id']].append((root,p,v))
    assert len(claims)==2500 and sum(map(len,claims.values()))==2750 and max(map(len,claims.values()))==2
    for uid,rs in claims.items():
        assert sorted(x[2]['attempt'] for x in rs)==list(range(1,len(rs)+1))
        if len(rs)==2:
            old=min(rs,key=lambda x:x[2]['attempt']);u=byid[uid]
            result=old[0]/'evaluation'/u['method']/u['source_id']/'RESULT.json'
            assert read(result)['status']=='technical_failure',uid
    # Match the actually loaded pi05 auxiliary identities to the fixed config.
    pi=R/'continuations/r4';cfg=read(pi/'config/PI_ENGINE.json')
    aux=list((pi/'chains/evaluate/stages').glob('*/workers/*/AUXILIARY_IDENTITY.json'))
    assert len(aux)==72
    for p in aux:
        a=read(p);ready=read(p.parent/'MODEL_READY.json')
        assert a['full_Q']==cfg['selected_model'] and a['optimizer_updates']==0
        assert ready['loss']=='L11' and ready['fit_seed']==9101
    # r5 already ended while this CPU audit was running. Validate existing
    # records; this does not acknowledge a different wakeup event.
    xr=R/'continuations/r5';xsum=collections.Counter();esum=collections.Counter();csum=collections.Counter();xids=set();cuts=0
    for p in (xr/'evaluation/Velocity').glob('*/RESULT.json'):
        v=read(p);u=byid[v['unit_id']];xids.add(v['unit_id'])
        assert u['model']=='X-VLA' and u['method']=='Velocity' and u['H']==10
        assert v['status']=='complete' and type(v['success']) is bool and v['loss']=='L11' and v['fit_seed']==9101
        assert v['reset_seed']==u['env_seed'] and v['policy_seed']==u['policy_seed'] and v['claim']['attempt']==1
        es=v['events'];ts=[e for e in es if e.get('trigger')]
        assert len(ts)==v['interventions'] and v['first_cut']==(ts[0]['step'] if ts else None)
        for n,e in enumerate(ts):
            assert e['commit_until']==e['step']+10 and e['legal_cut'] and e['gate']>.05
            assert e['intervention_index']==n+1 and not any(e['step']<k['step']<e['step']+10 for k in es)
            assert e['restore_native_K']==10
        # The successful native runner serializes sparse Counter objects;
        # absent optional operations mean zero only in this completed record.
        cnt=collections.Counter(v['counters']);enc=collections.Counter(v['encoder_counters'])
        assert cnt['policy_flow_calls']==10*cnt['policy_queries']
        assert cnt['policy_queries']==cnt['candidate_queries']+cnt['natural_queries']
        assert cnt['environment_steps']==v['steps'] and cnt['candidate_queries']==2*len(ts)
        assert enc['D_forward_calls']==enc['G0_forward_calls']==2*len(es)
        assert enc['action_gradient_calls']==enc['Q_ensemble_forward_calls']==3*len(ts)
        assert enc['Q_member_forward_calls']==4*enc['Q_ensemble_forward_calls']
        xsum.update(raw_terminals=1,successes=int(v['success']),legal_false=int(not v['success']),steps=v['steps'])
        csum.update(cnt);esum.update(enc);cuts+=len(ts)
    assert len(xids)==500 and xsum['successes']==407
    workers=[];native=collections.Counter();encoder=collections.Counter();meters=collections.Counter();loads=collections.Counter()
    for p in sorted((xr/'chains/evaluate/stages').glob('*/workers/*/CLIENT_RESULT.json')):
        n=read(p);e=read(p.parent/'encoder/RESULT.json');done=read(p.parent/'CONTEXTS_COMPLETE.json')
        assert n['status']==e['status']=='complete' and n['fatal'] is None and e['fatal'] is None
        assert not done['pending_sources'] and done['peak_active_contexts']==8 and e['external_encoder_sampling_calls']==0
        native.update(n['counters']);encoder.update(e['counts'])
        for key,row in e['meter_by_context'].items():
            assert row['entered']==row['returned'] and not row['failed']
            (meters if key.startswith('D24_MW_') else loads).update(row['entered'])
        workers.append(dict(worker=p.parent.name,native_seconds=n['elapsed_seconds'],encoder_seconds=e['elapsed_seconds'],
                            encoder_load_seconds=e['identity']['external_encoder_load_seconds'],native_peak_GPU_bytes=n['peak_allocated_bytes'],
                            encoder_peak_GPU_bytes=e['peak_allocated_bytes'],completed=len(done['completed'])))
    assert len(workers)==24 and sum(w['completed'] for w in workers)==500
    for k,v in csum.items():assert abs(native[k]-v)<=1e-6*max(1,abs(v)),k
    for k,v in esum.items():assert abs(encoder[k]-v)<=1e-6*max(1,abs(v)),k
    new_json(O/'R5_EXISTING_RESULT_AUDIT.json',dict(utc=utc(),summary=dict(xsum),cut_count=cuts,all500_claims_seeds_C10_costs_verified=True,
              native_counters=dict(native),encoder_counters=dict(encoder),encoder_numerical_calls=dict(meters),encoder_load_calls=dict(loads),
              workers=workers,raw_summary=ref(xr/'FINAL_SUMMARY.json'),separate_event_ACK_written=False,new_GPU_calls=0))
    summary=read(R/'task_summary/SUMMARY.json');assert summary['claims']==2750 and summary['dispositions']['execution_integrity_unverified']==1500
    assert summary['dispositions']['valid']==736 and summary['missing_attempt_terminals']==0 and summary['complete'] is False
    (O/'TASK_SUMMARY_SNAPSHOT.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
    live=read(O/'LIVE_EXIT_AND_OCCUPANCY.json');issue=read(O/'QUALITY_ISSUE.json');delivery=read(O/'QUALITY_ISSUE_TRANSPORT.json')
    perrun=[dict(root=str(p),claim=ref(p/'CLAIM.json'),attempts=len(list((p/'claims/units').glob('*.json'))),terminal=ref(p/'RESULT.json')) for p in roots]
    audit=dict(utc=utc(),task_id=R.name,event_id=E,outcome='audited_terminal_with_quality_hold_and_budget_gaps',
               event=ref(C/'persistent_queue/nodes/C/wakeup/outbox'/(E+'.json')),original_task_ACK=ref(C/'receipts/C/C_D24_L11_RETEST_V1_ACK.json'),
               record_audit=ref(O/'RECORD_AUDIT.json'),r4_costs=ref(O/'PROCESS_COSTS.json'),r5_existing_result_audit=ref(O/'R5_EXISTING_RESULT_AUDIT.json'),
               owner_C_exact_units=2500,unique_task_claim_lineage=perrun,total_claims=2750,task_attempt_cap=2750,
               node_cumulative_attempts=14943+2750,node_attempt_cap=18750,maximum_per_source_attempts=2,
               every_retry_follows_technical_failure=True,completed_source_replays=0,scientifically_accepted=736,
               technical_missing=211,unknown=31,first_wave_render_unverified=22,r4_execution_integrity_unverified=1500,
               all_task_attempts_have_terminal_records=True,scientific_task_complete=False,
               all_formal_families_exited=live['all_current_formal_families_exited'],holders_restored=True,
               live_exit_occupancy=ref(O/'LIVE_EXIT_AND_OCCUPANCY.json'),measured_holder_SM_this_audit=None,
               r4_peak_contexts=192,r5_peak_contexts=192,model_batch_size=1,contexts_per_model=8,replicas_per_GPU=3,
               r4_actual_utilization=ref(pi/'chains/evaluate/UTILIZATION_SUMMARY.json'),
               shared_EGL_cause_suspected_not_runtime_confirmed=True,diagnostic=ref(O/'PREINTERVENTION_DIAGNOSTIC.json'),
               private_repair_candidate=ref(O/'REPAIR_CANDIDATE_CPU_CHECK.json'),repair_GPU_validated=False,
               old_L01_preserved=True,no_loss_reselection=True,not_an_independent_blind_test=True,
               Post_current_paper=str(R/'task_summary/POST_CURRENT_PAPER.csv'),Velocity_other_work=str(R/'task_summary/VELOCITY_OTHER_WORK.csv'),
               current_Post_rows_paper_eligible=False,task_summary=ref(O/'TASK_SUMMARY_SNAPSHOT.json'),
               quality_hold=ref(R/'EXECUTION_QUALITY_HOLDS.json'),issue_id=issue['issue_id'],analysis_response_due_at=issue['analysis_response_due_at'],
               issue_transport_status=delivery['status'],issue_handler_ACK=False,CPU_issue_timer_alive=live['CPU_watcher_alive'],
               new_training_updates=0,new_collection=0,new_scientific_units=0,new_GPU_calls=0,
               scientific_processes_signalled=0,own_CPU_export_replaced=ref(O/'CPU_EXPORT_REPLACEMENT.json'),callback_recursive_wakeup=False)
    new_json(O/'AUDIT.json',audit)
    text='''# C L11 终局审计

事件 C_4834113fcd0b6f4d5d6f6ba9fff7b341 已核对，为 r4 π0.5 三格共1500条的终局。审计期间，既有 r5 X Velocity 500条也正常结束。未重训、采集或重跑任何源，未新增GPU调用。

| Cell | 科学有效 | 有效成功 | 处置 |
|---|---:|---:|---|
| X Post H10 | 236/500 | 198 | 211技术缺项、31未知、22首波渲染未核实；不能称完整500源成功率 |
| X Velocity H10 | 500/500 | 407（81.4%） | 同源旧L01为412/500，差-1.0pp；仅用于其他工作 |
| π0.5 Post H40 | 待核实500 | 未定义 | 原记录49成功，执行完整性未核实，暂不进入有效论文数据 |
| π0.5 Velocity H40 | 待核实500 | 未定义 | 原记录40成功，仅保留诊断结果 |
| π0.5 Velocity H50 | 待核实500 | 未定义 | 原记录38成功，仅保留诊断结果 |

π0.5 的原始1500条均为complete，C10、first_cut、每源种子和计数一致。但固定选取的10个源在首次Q干预前已经出现执行差异：前5步动作/奖励、step0 G0完全相同，step5 G0不同。因此不能将原始成功率变化归因于L11，也不把这些未知质量结果计为科学失败。所有成功和false原记录均保留、同等隔离，没有挑选结果。共享EGL上下文未在绘制前显式恢复各viewer framebuffer是当前代码疑点；仅保存了CPU验证的私有修复候选，尚无GPU修复验证。

唯一2500个C单位、L11/fit9101/members1041..1044及原ACK一致。r1/r2/r3/r4/r5依次使用447/193/110/1500/500次，共2750/2750；每源最多2次，第二次均对应既有技术失败。C累计17693/18750，但本任务2750上限已满，不会用节点余量擅自扩充阶段预算。全部2750次均有原始终局。当前有效736，其他1764为技术缺项、未知或完整性未核实，全任务未获科学完成。

r4和r5实际峰值均192个活动环境，24份常驻模型各轮转8个分支，batch=1，并非192份模型同时推理。r4三阶段累计加载72份π0.5模型；r5为24份X原生模型及24份外部特征编码器。r4各卡采样平均利用率约60.6%–69.5%，含装载和尾部，不是连续利用率保证。r4完整新成本为32735次采样、327350次flow、D/G0各148832次、Q ensemble62490次、action gradient23010次；视觉/语言/预处理、模型装载和逐源时间见PROCESS_COSTS.json。r5相应为8315/83150、D/G0各20816、Q/gradient各4503；模型和编码器额外调用单列。嵌套计时不能相加当作GPU内核时间，轮转wall time包含等待。

两轮正式全族现均退出；r4先恢复holder，再在r5入口确认其后代退出；r5退出后八卡holder恢复且本次读取确认其manager存活。占卡目标设置不等于本次实测SM；本审计没有另做GPU探针。占卡成本不进入科学调用预算。

Post与Velocity继续分表，旧L01不改；现有Post表明确标记不具备完整论文入表条件。原始配对保存在PAIRED_L01_RAW_DIAGNOSTIC.csv，有效配对单独保存。固定已公开源重测，不宣称独立盲测，也未再次选择loss/fit/阈值。

执行完整性及额外恢复预算问题已写C issue/outbox，30分钟期限为04:41:31 UTC。固定分析线程的一次投递失败（no rollout found）；无分析端ACK，没有换线程或递归唤醒。CPU后台已接管计时和质量感知汇总。当前L11没有可在现有阶段预算内新增的计算，保留全部科学终局并等待具体处置。
'''
    (O/'AUDIT.md').write_text(text)
    atomic_json(R/'LATEST_RUN.json',dict(utc=utc(),task_id=R.name,run_id='D24_C_L11_RETEST_r5',root=str(xr),terminal=True,
                status='terminal_with_quality_hold_and_budget_gaps',scientific_task_complete=False,claim=ref(xr/'CLAIM.json'),
                aggregate=str(R/'task_summary'),audit=ref(O/'AUDIT.json'),queued_next_root=None))
    new_json(R/'NO_RUNNABLE_L11_UNITS_WITHIN_BUDGET.json',dict(utc=utc(),scope=R.name,attempts=2750,cap=2750,
                reason='All exact units entered; preserve valid terminals, technical/unknown and quality holds; additional recovery exceeds task cap.',
                issue=issue['issue_id'],other_authorized_task_discovery_unchanged=True,new_GPU_calls=0))
    atomic_json(C/'receipts/C/C_D24_L11_RETEST_V1_TERMINAL_AUDIT.json',dict(utc=utc(),event_id=E,audit=ref(O/'AUDIT.json'),
                report=str(O/'AUDIT.md'),summary=str(R/'task_summary/SUMMARY.json'),scientific_task_complete=False,
                disposition='quality_hold_and_stage_budget_exhausted',all_formal_exited=True,holders_restored=True,new_GPU_calls=0))
    print(json.dumps(dict(audit=str(O/'AUDIT.json'),attempts=2750,valid=736,held_pi05=1500,all_formal_exited=True)))

if __name__=='__main__':main()
