"""Bounded CPU audit of the original X full-Q terminal. No compute launch."""
import csv, hashlib, json, math, socket, sys
from collections import Counter
from pathlib import Path
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1'
sys.path.insert(0,str(R/'code'))
from qio import read,ref,verify,sha,atomic_json,utc
from report import validate_episode,paired
sys.path.insert(0,str(C/'work/C/C_D24_QUOTA_INDEPENDENT_QUEUE_V1_r1'))
import queue_common as q
from selection_bridge import locked_post_choice
EVENT='C_cbcb4949aa0ac02654a12702a75e95fa'

def reference_csv(path,method,sources):
    rows={}
    with path.open() as f:
        for raw in csv.DictReader(f):
            if raw['method']!=method:continue
            sid=raw['source_id'];assert sid not in rows and sid in sources
            assert raw['status']=='complete' and raw['success'] in ['True','False']
            assert raw['task']==sources[sid]['task']
            assert all(int(raw[k])==sources[sid][k] for k in ['reset_seed','policy_seed'])
            rows[sid]=dict(raw,success=raw['success']=='True')
    assert set(rows)==set(sources)
    return rows

def main():
    event_path=C/'persistent_queue/nodes/C/wakeup/outbox'/(EVENT+'.json')
    event=read(event_path);q.authority()
    assert event['node']=='C' and event['hostname']==socket.gethostname() and not event['synthetic']
    assert event['executor_thread_id']=='01a0c793-10d2-7791-a250-fd65d88e1ccb'
    assert event['job']['task_id']==R.name and Path(event['job']['result_path'])==R/'RESULT.json'
    assert sha(event['job']['claim_identity']['path'])==event['job']['claim_identity']['sha256']
    result=read(R/'RESULT.json');assert result==event['result'] and result['status']=='complete' and result['report_exit_code']==0
    grant=C/'deadline_20260924/FULL_Q_LOSS_SELECTION_AUTHORIZATION_V1.json'
    assert sha(grant)=='8fc0bf2c7c0c761d9fba424fb7fb127af8a9c505668fccd7231126535c6422c1'
    candidates=read(R/'CANDIDATES_READY.json');training=read(R/'evidence/TRAINING_RESULT_AUDIT.json');fits=[]
    assert candidates['fits']==16 and candidates['actual_optimizer_updates']==64000
    for record in training['terminal_results']:
        row=read(verify(record));fits.append(row)
        assert row['status']=='complete' and row['updates']==row['selected_at_fixed_update']==4000 and row['fit_seed']==9101
        assert row['trainable_parameters']==7058 and not row['old_network_loaded'] and row['preprocessing_unchanged']
        assert set(row['modules'])=={'state','action','head','residual','advantage'}
        assert all(v['changed_tensors']>0 and v['delta_l2']>0 for v in row['modules'].values())
    assert {(r['loss'],r['member']) for r in fits}=={(l,m) for l in ['L00','L10','L01','L11'] for m in [1041,1042,1043,1044]}
    assert len(fits)==16 and sum(r['updates'] for r in fits)==64000
    selected=read(R/'SELECTION_CONSUMED.json');choice=locked_post_choice()
    assert choice['chosen_loss']==selected['chosen_loss']=='L01' and selected['fixed_fit_seed']==9101
    assert choice['selection_ref']==selected['A_selection'] and choice['lock_ref']==selected['A_lock']
    assert selected['local_test_used'] is False and selected['A_pi05_weights_loaded'] is False
    ranking=read(verify(selected['own_ranking']));small_weights=[]
    for member in selected['own_members']:
        p=Path(member['checkpoint']);target=Path(selected['own_assets'])/'models/refit'/f"member_{member['member']}"/'selected.pt'
        assert p==R/'training'/f"L01_s9101_m{member['member']}"/'final.pt' and target.resolve()==p
        assert sha(p)==member['sha256']==ranking['model_hashes'][str(member['member'])]
        small_weights.append(ref(p))
    assert len(small_weights)==4 and {m['member'] for m in selected['own_members']}=={1041,1042,1043,1044}
    source_rows=read(R/'config/TEST_SOURCES.json')['sources'];sources={s['source_id']:s for s in source_rows}
    assert len(sources)==len(source_rows)==500
    expected={m+'/'+sid for m in ['Post','Velocity'] for sid in sources};claims={}
    for p in (R/'claims/attempts').glob('*.json'):
        r=read(p);assert r['phase']=='evaluate' and r['identity'] not in claims and r['identity'] in expected
        assert p.stem==hashlib.sha256(r['identity'].encode()).hexdigest();claims[r['identity']]=r
    assert set(claims)==expected and {v['number'] for v in claims.values()}==set(range(1,1001))
    actual={};encoder=Counter();native=Counter();groups=[]
    for method in ['Post','Velocity']:
        rows={}
        for p in (R/'evaluation'/method).glob('*/RESULT.json'):
            r=read(p);sid=p.parent.name;assert sid not in rows and sid in sources
            assert r['status']=='complete' and type(r['success']) is bool and r['method']==method
            assert Path(r['claim'])==R/'claims/attempts'/(hashlib.sha256((method+'/'+sid).encode()).hexdigest()+'.json')
            assert (p.parent/'ENTERED.json').exists();validate_episode(r,sources[sid]);rows[sid]=r
            encoder.update(r['encoder_counters']);native.update(r['counters'])
        assert set(rows)==set(sources);actual[method]=rows
        groups.append(dict(method=method,valid=500,successes=sum(r['success'] for r in rows.values()),legal_failures=sum(not r['success'] for r in rows.values()),technical=0,unknown=0,unstarted=0,interventions=sum(r['interventions'] for r in rows.values()),first_cut_and_C10_checked=500))
    assert read(R/'ATTEMPT_COUNTER.json')['reserved_attempts']==1000
    Npath=C/'work/C/C_D24_MW_VELOCITY_V1_r2/VALID_N_INDEX.json';N={r['source_id']:r for r in read(Npath)['xvla']}
    assert set(N)==set(sources) and all(r['status']=='complete' and type(r['success']) is bool for r in N.values())
    assert all(all(r[k]==sources[sid][k] for k in ['task','reset_seed','policy_seed']) for sid,r in N.items())
    once_path=C/'results/C/C_D24_XVLA_AUX_RETRAIN_V1/FINAL_EPISODES.csv'
    multi_path=C/'results/C/C_D24_XVLA_MULTI_EVAL_V1/FINAL_EPISODES.csv'
    Rmulti=reference_csv(multi_path,'R',sources);pairs={}
    for method in ['Post','Velocity']:
        tables={'multi_vs_N':N,'multi_vs_R_multi':Rmulti,'newQ_multi_vs_oldQ_once':reference_csv(once_path,method,sources),'newQ_multi_vs_oldQ_multi':reference_csv(multi_path,method,sources)}
        for name,table in tables.items():pairs[method+'_'+name]=paired(actual[method],table)
    assert pairs==read(R/'PAIRED.json')
    assert read(R/'POST_PAPER_PAIRED.json')=={k:v for k,v in pairs.items() if k.startswith('Post_')}
    assert read(R/'VELOCITY_OTHER_WORK_PAIRED.json')=={k:v for k,v in pairs.items() if k.startswith('Velocity_')}
    resources=read(R/'RESOURCE_SUMMARY.json');assert len(resources['workers'])==24 and resources['episode_encoder_calls_reconciled_with_workers']
    for observed,stored in [(encoder,resources['encoder_totals']),(native,resources['native_totals'])]:
        assert set(observed)==set(stored)
        assert all(math.isclose(v,stored[k],rel_tol=1e-10,abs_tol=1e-6) for k,v in observed.items())
    assert all(w['encoder']['status']==w['native']['status']=='complete' for w in resources['workers'])
    exit_proof=q.family(R);assert exit_proof['exited'] and result['all_owned_descendants_exited']
    restoration=read(R/'chains/evaluate/RESTORATION.json');assert restoration['status']=='occupancy_resolved'
    assert len(restoration['guard_status']['gpus'])==8 and all(r['state']=='holder' for r in restoration['guard_status']['gpus'].values())
    for stage in ['train','evaluate']:
        chain=R/'chains'/stage
        assert read(chain/'BEFORE_RESERVATION_RELEASE.json')['cleanup']['status']=='all_formal_group_members_exited'
        assert read(chain/'HOLDER_EXIT_ACK.json')['all_holder_private_sessions_observed_empty']
    pi=q.snapshot(q.P/'HEARTBEAT.json');guard=q.snapshot('/tmp/gpu_occupancy_guard/status.json')
    audit=dict(event_id=EVENT,task_id=R.name,status='audited_complete',utc=utc(),event=ref(event_path),claim=ref(R/'CLAIM.json'),authorization=ref(grant),original_PROCESS=read(R/'PROCESS.json'),training=dict(fits=16,actual_optimizer_updates=64000,trainable_parameters_per_member=7058,old_parameters_loaded=False,preprocessing_unchanged=True,evidence=ref(R/'evidence/TRAINING_RESULT_AUDIT.json')),selection=dict(loss='L01',fit_seed=9101,criterion='complete Post-only development, test unused',A_selection=selected['A_selection'],A_lock=selected['A_lock'],own_X_weights=small_weights,own_ranking=selected['own_ranking']),per_source=dict(expected=1000,unique_claims=1000,valid=1000,retries=0,replays=0,groups=groups,source_manifest=ref(R/'config/TEST_SOURCES.json'),raw_summary=ref(R/'FINAL_SUMMARY.json')),pairs=pairs,pair_sources=[ref(Npath),ref(once_path),ref(multi_path)],paired_source_task_reset_and_policy_seeds_verified=True,resource_audit=dict(workers_complete=24,all_episode_calls_match_workers=True,encoder_totals=dict(encoder),native_totals=dict(native),resource_summary=ref(R/'RESOURCE_SUMMARY.json')),actual_formal_exit=exit_proof,holder_restoration=ref(R/'chains/evaluate/RESTORATION.json'),holder_restored_at=restoration['observed_at']['utc'],current_successor=dict(task_id=q.P.name,process=q.snapshot(q.P/'PROCESS.json'),alive=q.live(q.snapshot(q.P/'PROCESS.json')),heartbeat=pi,holder_exit=ref(q.P/'chains/evaluate/HOLDER_EXIT_ACK.json'),cached_guard=guard,interpretation='X restored all holders at exit; authorized Pi05 subsequently took the reservation. Do not restart holders during its wave.'),paper_primary='Post',Velocity_other_work=True,interpretation='All eight paired CIs contain zero; no established improvement claim. New Q multi versus old Q once changes both Q and trigger count.',source_recomputation=0,new_GPU_calls=0,new_training_updates_in_this_audit=0,fault_repairs_required=False,recursive_wakeup=False)
    target=R/'evidence'/('TERMINAL_AUDIT_'+EVENT+'.json');atomic_json(target,audit)
    lines=['C X-VLA 完整Q终局审计通过。','', '16 fits / 64000 updates；Post-only开发选择L01，固定fit9101，本机X四成员。Post 409/500；Velocity 412/500。1000个唯一claim全部合法终局，重试、重复评测和新增训练均为0。','', '| 方法 | 相对N百分点 | 相对R-multi百分点 | 相对旧Q multi百分点 | 相对旧Q once百分点 |','|---|---:|---:|---:|---:|']
    for m in ['Post','Velocity']:lines.append('| '+m+' | '+' | '.join(str(pairs[m+'_'+n]['difference_pp']) for n in ['multi_vs_N','multi_vs_R_multi','newQ_multi_vs_oldQ_multi','newQ_multi_vs_oldQ_once'])+' |')
    lines+=['','每项均为500对；八项95%任务聚类bootstrap区间均包含0，不能宣称收益已确立。旧Q once比较同时改变Q和触发次数。Post用于本篇，Velocity另篇保留。','', '24个worker及逐源调用已核对；X整族退出，17:55:53 UTC八卡holder恢复。后继Pi05重新取得整波预留，运行期间holder保持停算。','', '详细审计：'+str(target)]
    (R/'TERMINAL_AUDIT.md').write_text('\n'.join(lines)+'\n')
    atomic_json(C/'receipts/C/C_D24_FULL_Q_LOSS_REFRESH_V1_TERMINAL_AUDIT_r1.json',dict(utc=utc(),task_id=R.name,event_id=EVENT,status='audited_complete',audit=ref(target),summary=ref(R/'TERMINAL_AUDIT.md'),new_scientific_compute=0))
    print(json.dumps(dict(audit=str(target),status=audit['status'],groups=groups,Pi05_H=pi.get('progress',{}).get('H')),ensure_ascii=False))

if __name__=='__main__':main()
