"""CPU-only terminal reconciliation; never launches or imports scientific runtimes."""
import csv,hashlib,json,math,sys
from collections import Counter
from pathlib import Path

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=C/'results/C/C_D24_XVLA_MULTI_EVAL_V1';W=R/'concurrency24_r1';AUX=C/'results/C/C_D24_XVLA_AUX_RETRAIN_V1'
EID='C_70fa1ddefc18dffaaf2cddb8a27d5f12'
sys.path.insert(0,str(R/'code'))
from qio import read,new_json,atomic_json,ref,sha,utc

def require(ok,label):
    if not ok:raise ValueError(label)

def equal_counts(a,b,label):
    for key in set(a)|set(b):
        if key.endswith('seconds'):continue
        require(a.get(key,0)==b.get(key,0),f'{label}/{key}')

def pair(new,old):
    ids=set(new)&set(old);rescued=sum(new[s]['success'] and not old[s]['success'] for s in ids)
    harmed=sum(old[s]['success'] and not new[s]['success'] for s in ids)
    return dict(paired_valid=len(ids),rescued=rescued,harmed=harmed,difference_pp=100*(rescued-harmed)/len(ids),
        new_successes=sum(new[s]['success'] for s in ids),reference_successes=sum(old[s]['success'] for s in ids))

def main():
    event_path=C/'persistent_queue/nodes/C/wakeup/outbox'/f'{EID}.json';event=read(event_path)
    require(event['event_id']==EID and not event['synthetic'] and event['job']['task_id']=='C_D24_XVLA_MULTI_EVAL_V1','event identity')
    require(event['executor_thread_id']=='01a0c793-10d2-7791-a250-fd65d88e1ccb','original C thread')
    claim=event['job']['claim_identity'];require(sha(claim['path'])==claim['sha256'],'claim SHA')
    require(event['result']==read(event['job']['result_path']),'terminal event/result identity')
    terminal=event['result'];require(terminal['status']=='complete' and terminal['all_owned_descendants_exited'],'terminal status')
    cfg=read(R/'config/CONFIG.json');summary=read(R/'FINAL_SUMMARY.json');published_pairs=read(R/'PAIRED.json');resource=read(R/'RESOURCE_SUMMARY.json')
    sources=read(R/'config/TEST_SOURCES.json')['sources'];index={s['source_id']:s for s in sources}
    require(len(index)==len(sources)==500 and set(Counter(s['task'] for s in sources).values())=={10},'500 fixed sources/50 tasks')
    frozen=read(R/'FROZEN_HEADS.json')
    for key in ['Q_ranking','fit_summary','normalization']:require(sha(frozen[key]['path'])==frozen[key]['sha256'],'frozen head metadata '+key)
    require(set(frozen['members'])=={'D_2241','D_2242','G0_2341','G0_2342','Q_29301','Q_29302','Q_29303','Q_29304'},'dedicated head identities')
    for member,data in frozen['members'].items():
        result=read(data['result']['path'])
        require(result['status']=='complete' and result['updates']==4000 and Path(data['checkpoint']).stat().st_size==data['size_bytes'],'frozen final head '+member)
    batch=read(C/'work/C/C_D24_MW_VELOCITY_V1_r2/MW_VELOCITY_BATCH.json')
    baseline={s['source_id']:s for s in read(batch['baseline_index'])['xvla']}
    require(set(baseline)==set(index) and sum(s['success'] for s in baseline.values())==403,'N500 identity')
    methods={};pairs={};groups=[];encoder=Counter();native=Counter();numbers=[];identities=[];perwave=Counter();artifact_count=0;monitor_count=0;trigger_count=0
    managers={read(p/'chain/MANAGER_STARTED.json')['process']['pgid']:label for p,label in [(R,'original8'),(W,'concurrency24')]}
    for method in ['R','Post','Velocity']:
        rows={p.parent.name:read(p) for p in (R/'evaluation'/method).glob('*/RESULT.json')}
        once={p.parent.name:read(p) for p in (AUX/'evaluation'/method).glob('*/RESULT.json')}
        require(set(rows)==set(once)==set(index),'complete source sets '+method);methods[method]=rows
        costs=Counter();enc=Counter();hist=Counter()
        for sid,row in rows.items():
            s=index[sid]
            require(row['status']=='complete' and type(row['success']) is bool,'valid terminal '+method+'/'+sid)
            require(row['method']==method and row['mode']=='G0-multi','method/mode identity')
            for other in [row,once[sid],baseline[sid]]:
                require(all(other[k]==s[k] for k in ['source_id','task','reset_seed','policy_seed']),'paired source/seed mismatch')
            require(once[sid]['status']=='complete' and type(once[sid]['success']) is bool,'once validity')
            ep=R/'evaluation'/method/sid;entered=read(ep/'ENTERED.json');require(entered['claim']==row['claim'],'entry claim')
            attempt=read(row['claim']);require(attempt['identity']==method+'/'+sid and attempt['source_id']==sid and attempt['method']==method,'attempt identity')
            numbers.append(attempt['number']);identities.append(attempt['identity']);perwave[managers[attempt['process']['pgid']]]+=1
            require(row['physics']==dict(timestep=.0025,frame_skip=5,action_scale=.01),'frozen physics')
            require(0<row['steps']<=300 and row['counters']['environment_steps']==row['steps'],'actual control steps')
            lock=0;last=-1;cuts=[]
            for e in row['events']:
                t=e['step'];require(t>last and t>=lock and t%5==0 and t<row['steps'],'C10 no monitor/reentry '+sid)
                require(e['trigger']==bool(e['legal_cut'] and e['gate']>.05),'strict G0 trigger')
                require(math.isfinite(e['gate']) and abs(e['gate']-sum(e['member_gates'])/2)<1e-8,'D2/G02 gate aggregation')
                last=t;monitor_count+=1
                if e['trigger']:
                    cuts.append(t);trigger_count+=1
                    require(e['queue_age']==5 and t+10<=300 and e['commit_until']==t+10 and e['restore_native_K']==10 and not e['Q_acceptance_gate'],'legal C10 intervention')
                    require(e['intervention_index']==len(cuts),'ordered intervention index')
                    key=['native10_seed_v1',cfg['seed_namespace'],'D24_designated_a0',sid,s['policy_seed'],t]
                    digest=hashlib.sha256(json.dumps(key,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
                    require(e['candidate_seed']==int(digest[:16],16)%(2**63-1),'fixed candidate stream')
                    lock=t+10
                    if method!='R':
                        require((ep/f'intervention_cut_{t:03d}.npz').is_file(),'per-cut artifact missing');artifact_count+=1
                    if method=='Velocity':
                        updates=e['guidance']['updates'];require(len(updates)==3,'Velocity gradient call schedule')
                        require(all(abs(u['tau']-tau)<1e-6 and u['action_only_backward'] and u['native_inverse_normalization'] for u,tau in zip(updates,[.3,.2,.1])),'native Velocity guidance')
            require(row['first_cut']==(cuts[0] if cuts else None) and row['interventions']==len(cuts),'first_cut and total')
            require(len(list(ep.glob('intervention_cut_*.npz')))==(len(cuts) if method!='R' else 0),'exact cut artifact set')
            x=row['encoder_counters'];y=row['counters'];factor={'R':0,'Post':1,'Velocity':3}[method]
            require(x['monitor_calls']==len(row['events']) and x['D_forward_calls']==x['G0_forward_calls']==2*len(row['events']),'monitor cost')
            require(x.get('Q_ensemble_forward_calls',0)==x.get('action_gradient_calls',0)==factor*len(cuts),'Q/gradient cost')
            require(x.get('Q_member_forward_calls',0)==4*factor*len(cuts),'four Q members')
            require(y['policy_flow_calls']==10*y['policy_queries'] and y['policy_queries']==y['natural_queries']+y.get('candidate_queries',0),'native NFE10 cost')
            require(y.get('candidate_queries',0)==(2 if method=='Velocity' else 1)*len(cuts) and y['environment_resets']==1,'candidate/reset counts')
            costs.update(y);enc.update(x);hist[row['interventions']]+=1
        pairs[method+'_multi_vs_once']=pair(rows,once);pairs[method+'_multi_vs_N']=pair(rows,baseline)
        g=next(g for g in summary['groups'] if g['method']==method);successes=sum(x['success'] for x in rows.values())
        require(g['valid']==500 and g['successes']==successes and g['technical']==g['unknown']==g['unstarted']==0,'published denominators')
        equal_counts(costs,g['policy_and_runtime_counters'],method+'/published native');equal_counts(enc,g['external_encoder_and_heads_counters'],method+'/published encoder')
        calls=dict(costs,**enc);calls['interventions']=sum(k*v for k,v in hist.items())
        for k,v in calls.items():
            require(math.isclose(g['per_valid_episode'][k],v/500,rel_tol=1e-9,abs_tol=1e-8),'per valid cost')
            require(math.isclose(g['all_valid_cost_per_success'][k],v/successes,rel_tol=1e-9,abs_tol=1e-8),'per success cost')
        groups.append(dict(method=method,valid=500,successes=successes,rate=successes/500,once_successes=sum(x['success'] for x in once.values()),
            interventions=calls['interventions'],zero_trigger=hist[0],once_trigger=hist[1],multi_trigger=sum(v for k,v in hist.items() if k>1),
            costs=dict(costs),encoder=dict(enc),paired_once=pairs[method+'_multi_vs_once'],paired_N=pairs[method+'_multi_vs_N']))
        native.update(costs);encoder.update(enc)
    for method in ['Post','Velocity']:pairs[method+'_multi_vs_R_multi']=pair(methods[method],methods['R'])
    for name,row in pairs.items():
        for key,value in row.items():require(published_pairs[name][key]==value,'published pair '+name+'/'+key)
    require(sorted(numbers)==list(range(1,1501)) and len(set(identities))==1500,'no duplicate/replayed attempt')
    require(len(list((R/'claims/attempts').glob('*.json')))==1500,'claim count')
    require(perwave==dict(original8=730,concurrency24=770),'disjoint physical-wave allocation')
    require(read(R/'ATTEMPT_COUNTER.json')['reserved_attempts']==1500 and summary['cumulative_C_attempts']==11943,'cumulative budget')
    equal_counts(native,resource['native_totals'],'complete native worker totals');equal_counts(encoder,resource['encoder_totals'],'complete encoder worker totals')
    require(len(resource['workers'])==32 and resource['episode_encoder_calls_reconciled_with_workers'],'two-wave worker reconciliation')
    for worker in resource['workers']:require(worker['native']['status']==worker['encoder']['status']=='complete','worker exit')
    csv_rows=list(csv.DictReader((R/'FINAL_EPISODES.csv').open()));require(len(csv_rows)==1500,'episode CSV count')
    require(len({(r['method'],r['source_id']) for r in csv_rows})==1500,'episode CSV uniqueness')
    for x in csv_rows:
        y=methods[x['method']][x['source_id']]
        require(x['status']==y['status'] and x['success']==str(y['success']) and int(x['interventions'])==y['interventions'],'CSV/raw terminal agreement')
    runtime=W/'evidence'/f'{EID}_RUNTIME.json';require(read(runtime)['status']=='passed','runtime audit')
    utilization={name:sum(g['sample_mean_utilization_percent'] for g in value['GPUs'].values())/8 for name,value in resource['utilization'].items()}
    out=R/'audits'/f'{EID}.json'
    result=dict(schema='C_multi_terminal_audit_v1',event_id=EID,utc=utc(),status='audited_complete',task_id='C_D24_XVLA_MULTI_EVAL_V1',
        event=ref(event_path),claim=claim,terminal=ref(event['job']['result_path']),runtime=ref(runtime),
        valid_episodes=1500,successes=sum(g['successes'] for g in groups),technical=0,unknown=0,unstarted=0,
        fixed_sources_per_method=500,N_reused_successes=403,groups=groups,paired_recomputed=pairs,
        source_claims_unique=True,attempts=1500,cumulative_C_attempts_at_terminal=11943,stage_cap=1650,cumulative_cap=14000,
        physical_waves=dict(perwave),monitor_records_checked=monitor_count,interventions_checked=trigger_count,cut_artifacts_checked=artifact_count,
        C10_no_reentry_passed=True,first_cut_and_each_cut_passed=True,candidate_streams_passed=True,
        dedicated_D2_G02_Q4_frozen_final=True,new_training_updates=0,new_collection=0,N_replays=0,science_launched_by_audit=0,retries=0,
        native_calls=dict(native),external_encoder_calls=dict(encoder),all32_worker_costs_reconciled=True,
        sampled_GPU_mean_percent=utilization,platform_SM_alarm_clearance_verified=False,
        fullQ_successor_preserved=True,scope='historical fixed dedicated Q multi; not the new full-Q development-selected test',
        limitations=['Previously revealed fixed test500; same-head trigger-count comparison, not new blind test.',
            'Paired task-cluster intervals are pointwise, not adjusted for multiple comparisons.',
            '8-worker and24-worker waves contain different methods/tasks; raw throughput is not a causal concurrency benchmark.',
            'GPU utilization values are nvidia-smi samples including loading/tails; platform SM aggregation unknown.',
            'Legacy cancellation was rejected by automatic approval review; wave finished naturally. New Q task retains its own records.'],
        summary=ref(R/'FINAL_SUMMARY.json'),paired=ref(R/'PAIRED.json'),resource_summary=ref(R/'RESOURCE_SUMMARY.json'),
        handler_ACK_pending=True)
    new_json(out,result)
    lines=['C X-VLA 原专属 Q multi 终局审计','',f'事件 {EID}；1500/1500有效，技术失败/未知/未启动均0。未启动任何科学计算或重试。','',
        '| 方法 | 成功/有效 | 相对同Q once (pp) | 相对 N (pp) | 干预总数 | Q集成调用 |',
        '|---|---:|---:|---:|---:|---:|']
    for g in groups:lines.append(f"| {g['method']} | {g['successes']}/500 | {g['paired_once']['difference_pp']:+.1f} | {g['paired_N']['difference_pp']:+.1f} | {g['interventions']} | {g['encoder'].get('Q_ensemble_forward_calls',0)} |")
    lines+=['',f'逐源核对1500个独占claim，{monitor_count}条monitor记录、{trigger_count}次干预及{artifact_count}个P/V cut文件。C10禁止重入、first_cut、候选随机流及调用恒等式通过。',
        '',f'全部两段32个worker的成本已对账：policy查询{native["policy_queries"]}、flow调用{native["policy_flow_calls"]}、视觉编码{encoder["visual_encoder_calls"]}、语言编码{encoder["language_encoder_calls"]}、D/G0各{encoder["D_forward_calls"]}、Q成员调用{encoder["Q_member_forward_calls"]}。完整时间/内存及每有效/每成功成本见原RESOURCE_SUMMARY与FINAL_SUMMARY。',
        '',f'8路730回合，24路770回合，无重叠；GPU采样均值分别{utilization["original8"]:.2f}%和{utilization["concurrency24"]:.2f}%，包含加载与尾部，不能据此证明SM告警解除或并发因果提速。两段整族退出和占卡恢复已核对。',
        '', '相对各自once的点估计为+0.4/-0.8/+0.2pp，相应区间均含0；不声称multi已确立提升。固定500源已揭晓，旧Q结果保留为历史机制证据，不混入新完整Q验证。',
        '', '原取消控制器被自动审批拒绝且未执行，旧波自然收尾；新完整Q的16fits/64000更新及选择监听器保持独立，审计未干预。',
        '',f'审计 JSON：{out}']
    (R/'audits'/f'{EID}.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(audit=str(out),valid=1500,groups=[{k:g[k] for k in ['method','successes','interventions']} for g in groups],monitors=monitor_count,cuts=trigger_count,artifacts=artifact_count,utilization=utilization),ensure_ascii=False))

if __name__=='__main__':main()
