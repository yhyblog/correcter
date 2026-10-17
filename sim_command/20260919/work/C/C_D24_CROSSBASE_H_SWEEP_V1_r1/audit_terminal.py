"""CPU-only terminal audit of the fixed C H sweep; no scientific entrypoints."""
import collections,csv,hashlib,json,math,os,socket,sys,time
from pathlib import Path
import numpy as np
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=C/'results/C/C_D24_CROSSBASE_H_SWEEP_V1'
EID='C_70ffbe22dfd744c7a7140f73ba7abe30'
OUT=R/'event_audits'/EID;OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(R/'code'))
from qio import read,new_json,atomic_json,ref,verify,sha,utc,process_identity,same_process
from process_family import group_members
sys.path.insert(0,str(C.parents[2]/'Corrector'))
from experiments.native10_training_20260916.protocol import seed_for

def dump(name,value):atomic_json(OUT/name,value)
def csvout(name,rows):
    rows=list(rows);keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def check(ok,tag,uid=None):
    if not ok:raise AssertionError((tag,uid))
def identity_alive(p):
    return same_process(dict(p,host=p.get('host',p.get('hostname'))))
def counters_equal(a,b,keys):
    return all(math.isclose(a.get(k,0),b.get(k,0),rel_tol=1e-8,abs_tol=1e-6) for k in keys)


def main():
    check(not (OUT/'AUDIT.json').exists(),'existing terminal audit: do not replace')
    eventpath=C/'persistent_queue/nodes/C/wakeup/outbox'/(EID+'.json');ev=read(eventpath)
    check(ev['hostname']==socket.gethostname() and ev['executor_thread_id']=='01a0c793-10d2-7791-a250-fd65d88e1ccb' and not ev['synthetic'],'event identity')
    verify(ev['job']['claim_identity']);check(read(ev['job']['result_path'])==ev['result'],'event result snapshot')
    claim=read(R/'CLAIM.json');check(claim['process']==ev['job']['process_identity'] and claim['revision']==1,'unique claim identity')
    authpath=C/'deadline_20260924/CROSSBASE_H_SWEEP_V1/AUTHORIZATION.json';auth=read(authpath)
    check(sha(authpath)==claim['authorization_sha256']=='4f8406e67e2d0b73beda277b3bc633749060f30e8420e8513285780a06952c5f','authorization')
    manifestpath=verify(auth['nodes']['C']['units'],base=C);grant=[json.loads(l) for l in manifestpath.read_text().splitlines()]
    units=read(R/'UNIT_INDEX.json');frozen={u['unit_id']:u for u in grant}
    check(len(grant)==len(units)==len(frozen)==4000,'4000 scope')
    for u in units:
        check(all(u[k]==v for k,v in frozen[u['unit_id']].items()),'manifest exact fields',u['unit_id'])
        check(u['owner']=='C' and u['H'] in (20,30) and u['model']=='X-VLA','owner/H')
    check(collections.Counter((u['method'],u['H']) for u in units)=={(m,h):500 for m in ('N','Post','R','Velocity') for h in (20,30)},'eight full cells')
    # Verify private runtime/config fingerprints, not large model weight contents.
    source_manifest=read(R/'CODE_MANIFEST.json')
    for x in source_manifest['files']:check(sha(x['path'])==x['sha256'],'runtime/config unchanged '+x['path'])
    assets=read(R/'ASSETS.json')['X-VLA'];approved=read(C/'deadline_20260924/CROSSBASE_H_SWEEP_V1/Q_ASSETS.json')['assets']['X-VLA']
    check(assets['assets']==approved['assets'] and assets['loss']=='L11' and assets['fit_seed']==9101,'Q selection')
    verify(approved['ranking']);check({m['member'] for m in approved['members']}=={1041,1042,1043,1044},'Q members')
    nativeconfig=read(R/'config/X_NATIVE.json');verify(nativeconfig['test_sources'])
    sources={s['source_id']:s for s in read(nativeconfig['test_sources']['path'])['sources']};check(len(sources)==500,'500 fixed sources')
    reused=read(R/'REUSED_H10.json')
    for x in reused['source_references']:verify(x)
    check(len(reused['rows'])==2000 and reused['replay_count']==0,'H10 reused')
    dep=read(R/'DEPENDENCY_EXIT.json');verify(dep['previous_counter']);prior=read(dep['previous_counter']['path'])
    check(prior['cumulative_C_reserved']==dep['prior_C_attempts']==19457,'prior count')
    cp=list((R/'claims/units').glob('*.json'));check(len(cp)==4000,'unique claim paths')
    claims={read(p)['unit_id']:read(p) for p in cp};check(set(claims)==set(frozen),'claims exact ownership')
    check(sorted(c['stage_ordinal'] for c in claims.values())==list(range(1,4001)),'attempt ordinal unique')
    check(all(c['attempt']==1 and c['prior_attempt_count']==0 and c['implicit_retry'] is False for c in claims.values()),'no retries')
    ct=read(R/'ATTEMPT_COUNTER.json');check(ct['count']==4000 and ct['cumulative_C_reserved']==23457 and 4000<=auth['nodes']['C']['stage_attempt_cap'] and 23457<=auth['nodes']['C']['cumulative_attempt_cap'],'finite cumulative caps')
    check(len(list((R/'evaluation').glob('*/*/RESULT.json')))==4000,'unique raw results')
    rows=[];raw_by_uid={};bycell=collections.defaultdict(collections.Counter);cut_count=0;monitor_count=0;zero_corrections=0;terminated_short_commitments=0;epochs=[]
    for u in units:
        uid=u['unit_id'];p=R/'evaluation'/u['cell_id']/u['source_id']/'RESULT.json';r=read(p);raw_by_uid[uid]=r
        check(r['unit_id']==uid and r['claim']==claims[uid] and r['context_key']==uid,'result/claim/context',uid)
        check(r['status']=='complete' and type(r['success']) is bool,'legitimate terminal',uid)
        check(all(r[k]==v for k,v in sources[u['source_id']].items()),'source/reset/policy identity',uid)
        check(r['normal_H']==r['H']==u['H'] and r['C']==u['C'] and r['raw_plan_length']==30 and r['mode']==u['mode'],'H/C/raw/mode',uid)
        check(r['loss']==u['Q_loss'] and r['fit_seed']==u['Q_fit_seed'] and r['Q_members']==u['Q_members'],'per-arm Q identity',uid)
        check(r['max_interventions']==u['max_interventions'] and r['repeat'] is None,'no changed cap/repeat',uid)
        check(abs(r['physics']['timestep']-.0025)<1e-10 and r['physics']['frame_skip']==5 and abs(r['physics']['action_scale']-.01)<1e-10,'frozen native physics',uid)
        check(r['render_context']['explicit_owning_context_binding'] is True,'owning GL binding',uid)
        counts=r['counters'];enc=r['encoder_counters'];steps=r['steps'];H=u['H'];m=u['method']
        check(r['encoder_cost_complete'] is True and 0<steps<=300 and counts['environment_steps']==steps and counts['environment_resets']==1,'complete measured costs/steps',uid)
        events={e['step']:e for e in r['events']};check(len(events)==len(r['events']),'unique monitor clock',uid)
        natural={p['step']:p for p in r['plans'] if p['kind']=='natural'}
        candidates={p['step']:p for p in r['plans'] if p['kind']=='candidate_a0'}
        guided={p['step']:p for p in r['plans'] if p['kind']=='guided'}
        check(len(natural)+len(candidates)+len(guided)==len(r['plans']),'unique per-kind plan timestamps',uid)
        for plan in r['plans']:
            st=plan['stats'];check(plan['raw_length']==30 and st['flow_calls']==10 and len(st['times'])==10 and all(abs(v-(1-i/10))<1e-5 for i,v in enumerate(st['times'])),'raw30/NFE10 native schedule',uid)
            check(plan['execution_limit']==(H if plan['kind']=='natural' else 10),'natural_H or candidate_C',uid)
            check(len(st['noise_sha256'])==64,'sampling noise evidence',uid)
        check(counts['policy_queries']==counts['policy_queries_entered']==len(r['plans']) and counts['policy_flow_calls']==10*len(r['plans']),'all sampling calls accounted',uid)
        age=0;limit=H;correction=False;locked=0;last_cut=None;seen_natural=[];seen_monitors=[];seen_cuts=[]
        for t in range(steps):
            if t==0 or age==limit:
                check(t in natural,'expected fresh natural refill',uid);seen_natural.append(t)
                if correction:
                    check(t==locked and last_cut['restored_at_step']==t and last_cut['intervention_tail_discarded'] and last_cut['new_natural_sample'],'C10 tail discarded and native_H restored',uid)
                age=0;limit=H;correction=False
            eligible=m!='N' and not correction and t>=locked and t%5==0 and t>=4 and age>0 and limit-age>=5 and t+10<=300
            check((t in events)==eligible,'exact absolute monitor eligibility',uid)
            if eligible:
                e=events[t];seen_monitors.append(t)
                check(e['queue_age']==age and e['queue_limit']==limit and e['old_queue_remaining']==limit-age and e['history_frames']==5 and e['history_actions']==t and e['locked_until_before']==locked,'cut history/old queue',uid)
                check(e['legal_cut'] is True and abs(e['gate']-sum(e['member_gates'])/2)<1e-7 and e['trigger']==(e['gate']>.05),'frozen strict mean G0 gate',uid)
                if e['trigger']:
                    seen_cuts.append(t);check(t in candidates,'designated a0 call',uid)
                    seed=seed_for('D24_designated_a0',r['source_id'],r['policy_seed'],t,namespace=nativeconfig['seed_namespace'])
                    check(e['candidate_seed']==candidates[t]['candidate_seed']==seed,'candidate seed excludes H/method',uid)
                    check(e['commit_until']==t+10 and e['C']==10 and e['restore_normal_H']==H and e['Q_acceptance_gate'] is False and e['intervention_index']==len(seen_cuts),'C10/uncapped/no-Q-gate',uid)
                    check(e['commitment_executed']==min(10,steps-t) and e['commitment_complete']==(steps-t>=10),'actual commitment steps',uid)
                    terminated_short_commitments+=int(steps-t<10)
                    age=0;limit=10;correction=True;locked=t+10;last_cut=e
                    if m in ('Post','Velocity'):
                        mt=e['matching']
                        check(mt['other_directions_used'] is False and mt.get('random_calls',0)==0,'no random fallback',uid)
                        zero_corrections+=int(all(v==0 for v in mt['actual'].values()))
                    if m=='Post':check('pi05' in e['Post_metric'] and 'S squared' in e['Post_metric'],'frozen X Post metric',uid)
                    if m=='Velocity':
                        check(t in guided and guided[t]['candidate_seed']==seed and guided[t]['stats']['noise_sha256']==candidates[t]['stats']['noise_sha256'],'native guided paired noise',uid)
                        updates=e['guidance']['updates'];check(len(updates)==3 and all(abs(x['tau']-expected)<1e-5 and x['alpha']==10 and x['true_clamp'] and x['native_inverse_normalization'] and x['action_only_backward'] for x,expected in zip(updates,[.3,.2,.1])),'native velocity guidance',uid)
            age+=1
        check(set(seen_natural)==set(natural) and set(seen_monitors)==set(events) and set(seen_cuts)==set(candidates),'complete plan/event timeline',uid)
        check(set(guided)==(set(seen_cuts) if m=='Velocity' else set()),'guidance arm isolation',uid)
        check(r['first_cut']==(seen_cuts[0] if seen_cuts else None) and r['interventions']==len(seen_cuts),'first_cut/count',uid)
        check(counts.get('natural_queries',0)==len(natural) and counts.get('candidate_queries',0)==len(candidates)+len(guided),'natural/candidate counters',uid)
        qcalls=(3 if m=='Velocity' else 1 if m=='Post' else 0)*len(seen_cuts)
        check(enc.get('Q_ensemble_forward_calls',0)==enc.get('action_gradient_calls',0)==qcalls and enc.get('Q_member_forward_calls',0)==4*qcalls,'Q/gradient counts',uid)
        check(enc.get('monitor_calls',0)==len(events) and enc.get('D_forward_calls',0)==enc.get('G0_forward_calls',0)==2*len(events) and enc.get('visual_encoder_calls',0)==5*len(events),'monitor/D/G0/visual calls',uid)
        if m=='N':check(not any(enc.values()) and not events and counts.get('encoder_RPC_entered',0)==0,'N no auxiliary calls',uid)
        else:
            meter=r['encoder_meter'];check(meter['entered']==meter['returned'] and not meter['failed'],'encoder entered/returned',uid)
            check(meter['entered'].get('visual_encoder_forwards',0)==enc['visual_encoder_calls'] and meter['entered'].get('language_embedding_forwards',0)==enc['language_encoder_calls'],'independent encoder instrumentation',uid)
        with np.load(p.parent/'trajectory.npz',allow_pickle=False) as tr:
            check(tr['actions'].shape==(steps,4) and tr['rewards'].shape==(steps,) and len(tr['success_flags'])==steps,'actual trajectory length',uid)
            check(np.isfinite(tr['actions']).all() and np.isfinite(tr['rewards']).all() and np.max(np.abs(tr['actions']))<=1+1e-6 and bool(tr['success_flags'][-1])==r['success'],'actual trajectory finite and terminal',uid)
        row=dict(unit_id=uid,cell_id=u['cell_id'],model='X-VLA',method=m,mode=u['mode'],H=H,normal_H=H,raw_plan_length=30,C=u['C'],loss=u['Q_loss'],fit_seed=u['Q_fit_seed'],source_id=r['source_id'],task=r['task'],env_seed=r['reset_seed'],policy_seed=r['policy_seed'],success=r['success'],status='complete',steps=steps,interventions=len(seen_cuts),first_cut=r['first_cut'],monitor_calls=len(events),sampling_calls=counts['policy_queries'],flow_calls=counts['policy_flow_calls'],Q_ensemble_forward=qcalls,Q_member_forward=4*qcalls,action_gradient_calls=qcalls,Q_member_feature_context_calls_derived=4*len(seen_cuts) if m in ('Post','Velocity') else 0,native_inverse_transform_backward_calls_derived=3*len(seen_cuts) if m=='Velocity' else 0,D_forward=enc.get('D_forward_calls',0),G0_forward=enc.get('G0_forward_calls',0),visual_encoder_calls=enc.get('visual_encoder_calls',0),language_encoder_calls=enc.get('language_encoder_calls',0),elapsed_seconds=r['elapsed_seconds'],policy_seconds=counts['policy_seconds'],environment_seconds=counts['environment_seconds'],encoder_seconds=enc.get('encoder_seconds',0) if m=='N' else enc.get('encoder_seconds'),result_path=str(p),claim_path=str(R/'claims/units'/(u['storage_key']+'.json')),reused_H10=False,current_paper=m!='Velocity')
        rows.append(row);b=bycell[u['cell_id']]
        for k in ('steps','interventions','monitor_calls','sampling_calls','flow_calls','Q_ensemble_forward','Q_member_forward','action_gradient_calls','Q_member_feature_context_calls_derived','native_inverse_transform_backward_calls_derived','D_forward','G0_forward','visual_encoder_calls','language_encoder_calls','elapsed_seconds','policy_seconds','environment_seconds','encoder_seconds'):b[k]+=row[k]
        b['valid']+=1;b['successes']+=r['success'];b['trigger_zero']+=not seen_cuts;b['trigger_once']+=len(seen_cuts)==1;b['trigger_multi']+=len(seen_cuts)>1
        cut_count+=len(seen_cuts);monitor_count+=len(events)
    check(cut_count==10809,'all cut count')
    dump('SOURCE_PROTOCOL_AUDIT.json',dict(utc=utc(),passed=True,owned_manifest=ref(manifestpath),valid=4000,claims=4000,first_attempts=4000,cuts=cut_count,monitors=monitor_count,terminated_before_C10_complete=terminated_short_commitments,legitimate_zero_corrections=zero_corrections,H20_H30_natural_C10_separated=True,N_auxiliary_calls=0,R_Q_calls=0,physics='Mesa/native80Hz/.01/corner2_480/NFE10/raw30',first_cut_and_uncapped_interventions_valid=True,actual_trajectories_checked=4000,source_rng_and_full_unit_context_key_verified=True,errors=[]))
    # Reconcile each resident replica's aggregate with its assigned episodes.
    worker_rows=[];models=[];process_records=[];native_totals=collections.Counter();encoder_totals=collections.Counter();encoder_meter_entered=collections.Counter();encoder_meter_returned=collections.Counter();load_meter=collections.Counter();native_init_backward=0
    stages=sorted((R/'chains/evaluate/stages').iterdir())
    for stage in stages:
        sr=read(stage/'RESULT.json');method=sr['stage']['method'];check(len(sr['workers'])==24 and not any(sr['workers'].values()) and sr['peak_live_rollout_contexts']==192,'24 replicas and 192 live contexts each stage')
        for wr in sorted((stage/'workers').iterdir(),key=lambda p:int(p.name)):
            cfg=read(wr/'CONFIG.json');ids=[u['unit_id'] for u in cfg['units']];rs=[raw_by_uid[uid] for uid in ids]
            done=read(wr/'CONTEXTS_COMPLETE.json');check(len(done['completed'])==len(ids) and not done['pending_units'] and done['peak_active_contexts']==8 and {x['unit_id'] for x in done['completed']}==set(ids),'worker scope complete')
            check(all(x['status']=='complete' for x in done['completed']),'worker all valid')
            nr=read(wr/'CLIENT_RESULT.json');ready=read(wr/'MODEL_READY.json');check(nr['status']=='complete' and ready['encoder_required']==(method!='N'),'native ready and exit')
            sum_native=collections.Counter();sum_encoder=collections.Counter()
            for r in rs:sum_native.update(r['counters']);sum_encoder.update(r['encoder_counters'])
            keys=set(sum_native)-{'encoder_RPC_entered','encoder_RPC_seconds'}
            check(counters_equal(nr['counters'],sum_native,keys),'native worker/source accounting')
            if method!='N':check(nr['counters']['encoder_RPC_entered']==sum_native['encoder_RPC_entered']+1,'one close RPC outside episode')
            native_totals.update(sum_native);encoder_totals.update(sum_encoder)
            models.append(dict(stage=method,slot=cfg['slot'],kind='native',path=str(wr/'MODEL_READY.json'),parameters=ready['base_parameters'],load_seconds=ready['load_seconds'],peak_allocated_bytes=nr['peak_allocated_bytes'],process=ready['process']))
            process_records.append(ready['process'])
            native_init_backward+=int(method in ('Post','Velocity'))
            for name in ('PROCESS_STARTED.json','CLIENT_PROCESS.json','SERVER_PROCESS.json'):
                p=wr/name
                if p.exists():x=read(p);process_records.append(x.get('process',x))
            if method=='N':check(not (wr/'encoder').exists() and (wr/'ENCODER_NOT_REQUIRED.json').exists(),'N no auxiliary server loaded')
            else:
                er=read(wr/'encoder/RESULT.json');er_ready=read(wr/'encoder/READY.json')
                check(er['status']=='complete' and counters_equal(er['counts'],sum_encoder,set(sum_encoder)|set(er['counts'])),'encoder worker/source accounting')
                check(er_ready['loaded_new_D']==er_ready['loaded_new_G0']==2 and er_ready['loaded_new_Q']==(4 if method in ('Post','Velocity') else 0),'frozen loaded heads per arm')
                check(er_ready['base_policy_sampling_calls']==er['external_encoder_sampling_calls']==0,'external model never sampled actions')
                mb=er['meter_by_context'];check(set(mb)==set(ids)|{'resident_load'},'full-unit external context separation')
                for uid in ids:
                    check(mb[uid]==raw_by_uid[uid]['encoder_meter'],'per-unit meter exact reconciliation')
                    encoder_meter_entered.update(mb[uid]['entered']);encoder_meter_returned.update(mb[uid]['returned'])
                check(mb['resident_load']['entered']==mb['resident_load']['returned'] and not mb['resident_load']['failed'],'load returned')
                load_meter.update(mb['resident_load']['entered'])
                models.append(dict(stage=method,slot=cfg['slot'],kind='external_encoder',path=str(wr/'encoder/READY.json'),parameters=er_ready['external_model_parameters'],load_seconds=er_ready['external_encoder_load_seconds'],peak_allocated_bytes=er['peak_allocated_bytes'],process=er_ready['process'],D_loaded=2,G0_loaded=2,Q_loaded=er_ready['loaded_new_Q']))
                process_records.append(er_ready['process'])
            worker_rows.append(dict(stage=method,slot=cfg['slot'],gpu_uuid=read(wr/'PROCESS_STARTED.json')['GPU']['gpu_uuid'],sources=len(ids),model_replicas=1,peak_live_contexts=8,load_seconds=ready['load_seconds'],elapsed_seconds=nr['elapsed_seconds'],peak_allocated_bytes=nr['peak_allocated_bytes'],all_source_costs_reconciled=True))
        epochs.append(dict(method=method,valid=1000,physical_model_replicas=24,replicas_per_GPU=3,contexts_per_replica=8,peak_live_contexts=192,elapsed_seconds=sr['elapsed_seconds'],cleanup=sr['cleanup']))
    check(len(worker_rows)==96 and len(models)==168,'96 native loads / 72 external loads')
    # H10 reuses original evidence and never consumes new claims.
    for x in reused['rows']:
        m=x['method'];sid=x['source_id'];s=sources[sid];mode='native' if m=='N' else 'G0-multi';loss='L11' if m in ('Post','Velocity') else None;fit=9101 if loss else None
        rows.append(dict(x,unit_id=f'X-VLA|{sid}|{m}|{mode}|10|{loss}|{fit}',cell_id=f'X-VLA_{m}_H10',normal_H=10,raw_plan_length=30,C=None if m=='N' else 10,mode=mode,loss=loss,fit_seed=fit,task=s['task'],env_seed=s['reset_seed'],policy_seed=s['policy_seed'],current_paper=m!='Velocity',claim_path=None,reused_H10=True))
    check(len(rows)==6000 and len({r['unit_id'] for r in rows})==6000,'unique 6000 analytical keys')
    groups=collections.defaultdict(dict)
    for r in rows:groups[(r['method'],r['H'])][r['source_id']]=r
    all_source_ids=set(sources)
    check(all(set(g)==all_source_ids for g in groups.values()) and len(groups)==12,'all 12 cells use common 500')
    cells=[]
    for m in ('N','Post','R','Velocity'):
        for H in (10,20,30):
            group=list(groups[m,H].values());cs=sum(r['success'] for r in group)
            cells.append(dict(model='X-VLA',cell_id=f'X-VLA_{m}_H{H}',method=m,H=H,mode=group[0]['mode'],loss=group[0]['loss'],fit_seed=group[0]['fit_seed'],valid=500,planned=500,successes=cs,task_failures=500-cs,success_rate=cs/500,success_percent=cs/5,unknown=0,technical=0,reused_H10=H==10,current_paper=m!='Velocity'))
    reported={(r['method'],int(r['H'])):r for r in csv.DictReader((R/'FINAL_CELLS.csv').open())}
    for cell in cells:check(int(reported[cell['method'],cell['H']]['successes'])==cell['successes'] and int(reported[cell['method'],cell['H']]['valid'])==500,'published cell agrees')
    pairs=[]
    for p in csv.DictReader((R/'PAIRED.csv').open()):
        left=groups[p['left_method'],int(p['left_H'])];right=groups[p['right_method'],int(p['right_H'])]
        c=collections.Counter((left[s]['success'],right[s]['success']) for s in all_source_ids)
        recomputed=dict(common_valid=500,left_only=0,right_only=0,both_success=c[True,True],left_only_success=c[True,False],right_only_success=c[False,True],both_task_fail=c[False,False])
        check(all(int(p[k])==v for k,v in recomputed.items()) and abs(float(p['right_minus_left_success'])-(c[False,True]-c[True,False])/500)<1e-12,'pair table counts')
        pairs.append(dict(p,right_minus_left_pp=(c[False,True]-c[True,False])/5,current_paper='Velocity' not in (p['left_method'],p['right_method'])))
    csvout('AUDITED_EPISODES.csv',rows);csvout('AUDITED_CELLS.csv',cells);csvout('AUDITED_PAIRS.csv',pairs)
    csvout('CURRENT_PAPER_N_R_POST_CELLS.csv',[r for r in cells if r['current_paper']]);csvout('CURRENT_PAPER_N_R_POST_PAIRS.csv',[r for r in pairs if r['current_paper']])
    csvout('VELOCITY_OTHER_WORK_CELLS.csv',[r for r in cells if not r['current_paper']]);csvout('VELOCITY_OTHER_WORK_PAIRS.csv',[r for r in pairs if not r['current_paper']])
    csvout('PER_CELL_NEW_COSTS.csv',[dict(cell_id=k,**dict(v)) for k,v in sorted(bycell.items())]);csvout('WORKER_COSTS.csv',worker_rows)
    # The old summaries provide H10 costs. Do not reread full historical logs.
    h10p=C/'results/C/C_D24_L11_RENDER_RECOVERY_V1/event_audits/C_789594321516138f017292900ce238df/CALL_COST_AUDIT.json';h10r=C/'results/C/C_D24_XVLA_MULTI_EVAL_V1/FINAL_SUMMARY.json'
    priorcost=read(h10p)['all_valid_scientific_costs'];priorr=next(x for x in read(h10r)['groups'] if x['method']=='R')
    costs=dict(utc=utc(),new_attempts=4000,new_valid=4000,attempts_with_missing_cost_records=0,source_costs_by_cell={k:dict(v) for k,v in bycell.items()},native_counter_totals=dict(native_totals),external_encoder_counter_totals=dict(encoder_totals),external_encoder_instrumentation_entered=dict(encoder_meter_entered),external_encoder_instrumentation_returned=dict(encoder_meter_returned),external_encoder_load_calls=dict(load_meter),model_load_records=models,derived_costs=dict(Q_member_feature_context_forwards=sum(x['Q_member_feature_context_calls_derived'] for x in rows if not x['reused_H10']),Q_member_backwards=encoder_totals['action_gradient_calls']*4,native_inverse_transform_backwards_during_velocity=sum(x['native_inverse_transform_backward_calls_derived'] for x in rows if not x['reused_H10']),native_inverse_transform_startup_checks=native_init_backward,native_postprocessor_single_action_calls=30*native_totals['policy_queries']),derivation_source=dict(objective=ref(C.parents[2]/'Corrector/src/corrector/guidance.py'),native_bridge=ref(R/'xcode/native_velocity.py'),native_client=ref(R/'xcode/native_client.py')),N_encoder_seconds=dict(value=0,reason='No external encoder process or RPC exists for all 1000 N units; structural zero, original generic COSTS sparse time fields preserved'),H10_reuse_costs=dict(N=dict(sampling_calls=sum(x['sampling_calls'] for x in reused['rows'] if x['method']=='N'),flow_calls=sum(x['flow_calls'] for x in reused['rows'] if x['method']=='N'),auxiliary_calls=0),R=dict(policy=priorr['policy_and_runtime_counters'],encoder=priorr['external_encoder_and_heads_counters'],Q_calls=0,source=ref(h10r)),Post=priorcost['X-VLA_Post_H10_L11'],Velocity=priorcost['X-VLA_Velocity_H10_L11'],Post_Velocity_source=ref(h10p)),no_unavailable_cost_assumed_zero=True,worker_and_episode_counters_overlap_do_not_add=True,timing_scope='Operation timers and episode timers overlap; context elapsed includes cooperative scheduling/RPC waits. Model loads are separate. H10 has different historical concurrency/loading, so wall-time comparison is descriptive only.',measurement_limits=['Native policy chunk calls and ten native flow forwards measured; native visual/language submodule forwards were not independently instrumented.','Q feature contexts and backward counts are explicitly code-derived, not new GPU measurements.','Rendering framework subcall timing was not independently instrumented; real environment steps/trajectories are checked.'])
    dump('CALL_COST_AUDIT.json',costs)
    # Actual host-scoped exit and current idle occupancy, without NVML/GPU probes.
    manager=read(R/'chains/evaluate/MANAGER_STARTED.json')['process'];process_records.extend([dict(claim['process'],host=claim['process']['hostname']),manager,read(R/'chains/evaluate/LIFECYCLE_STARTED.json')['process']])
    process_records.extend(c['process'] for c in claims.values())
    process_records=list({(p['pid'],p['start_ticks']):p for p in process_records}.values())
    living=[p for p in process_records if identity_alive(p)];remaining=group_members(manager['pgid'],manager['pid']);check(not living and not remaining,'entire recorded formal family exited')
    guard=read('/tmp/gpu_occupancy_guard/status.json');check(time.time()-guard['updated']<30 and len(guard['gpus'])==8 and all(v['state']=='holder' for v in guard['gpus'].values()),'8 holders restored')
    uuids={str(x['gpu_index']):x['gpu_uuid'] for x in read(R/'config/BASE.json')['device_list']};holders=[]
    for idx,v in guard['gpus'].items():
        ident=process_identity(v['manager_pid']);check(ident and ident['state']!='Z','holder alive')
        cmd=(Path('/proc')/str(ident['pid'])/'cmdline').read_bytes().replace(b'\0',b' ').decode();check('--target-util 0.915' in cmd and '--devices '+idx+' ' in cmd,'idle holder duty unchanged')
        children=(Path('/proc')/str(ident['pid'])/'task'/str(ident['pid'])/'children').read_text().split()
        children=[process_identity(int(x)) for x in children];check(len([x for x in children if x and x['state']!='Z'])>=2,'holder children alive')
        holders.append(dict(gpu_index=int(idx),gpu_uuid=uuids[idx],identity=ident,command=cmd,descendants=children,target_duty=.915,measured_SM_utilization_percent=None))
    before=read(R/'chains/evaluate/HOLDER_EXIT_ACK.json');check(before['status']=='all8_holder_processes_exited_before_formal_child','pre-compute holder exit')
    release=read(R/'chains/evaluate/BEFORE_RESERVATION_RELEASE.json');check(release['cleanup']['status']=='all_formal_group_members_exited','release only after family exit')
    dump('LIVE_EXIT_AND_OCCUPANCY.json',dict(utc=utc(),formal_process_records=len(process_records),living_formal_processes=living,remaining_formal_group=remaining,manager=manager,holders=holders,cached_guard=guard,pre_compute_exit_ACK=ref(R/'chains/evaluate/HOLDER_EXIT_ACK.json'),retained_formal_lock=ref(R/'chains/evaluate/SAME_LOCK_FD_RETAINED.json'),cleanup_before_release=ref(R/'chains/evaluate/BEFORE_RESERVATION_RELEASE.json'),restoration=ref(R/'chains/evaluate/RESTORATION.json'),new_GPU_probe_calls=0,occupancy_duty_is_not_measured_SM=True))
    util=read(R/'chains/evaluate/UTILIZATION_SUMMARY.json');means=[v['sample_mean_utilization_percent'] for v in util['GPUs'].values()]
    concurrency=dict(utc=utc(),stages=epochs,formal_wave_seconds=read(R/'chains/evaluate/MANAGER_EXIT.json')['elapsed_seconds'],end_to_end_seconds=ev['result']['elapsed_seconds'],eight_GPU_sampled_mean_utilization_percent=sum(means)/len(means),utilization_source=ref(R/'chains/evaluate/UTILIZATION_SUMMARY.json'),concurrency_definition='24 native replicas x 8 independent live environments, interleaved steps; inference remains batch size one within each replica.',occupancy_conditions='All eight holders exited before formal model entry; one retained reservation through all four phases; restored after complete family exit. Tail/load/CPU-rendering time is included.',sampled_utilization_not_continuous_coverage=True)
    dump('CONCURRENCY_AND_RUNTIME.json',concurrency)
    unfinished=read(R/'UNFINISHED_UNITS.json');check(unfinished['units']==[],'empty unfinished manifest')
    check(not list(R.glob('PAUSE_ADMISSIONS_*.json')),'no paused recovery')
    summary=dict(utc=utc(),task_id=claim['task_id'],event_id=EID,status='audited_complete',planned_new_units=4000,valid_new_units=4000,reused_H10=2000,combined_unique_valid=6000,original_source_count=500,all_H_common_valid_per_method=500,attempts_new=4000,prior_C_attempts=19457,cumulative_C_attempts=23457,stage_attempt_cap=4400,node_attempt_cap=25150,corrected_retries=0,technical_missing=0,unknown=0,unfinished=0,valid_terminal_replays=0,Q_loss='L11',Q_fit_seed=9101,Q_members=[1041,1042,1043,1044],cuts=cut_count,protocol_errors=0,cells=cells,pairs=pairs,new_training_updates=0,new_collection=0,formal_family_exited=True,all_eight_holders_restored=True,holder_target_duty=.915,holder_SM_measurement=None,current_paper='N/R/Post',Velocity='separate_other_work',test_sources_previously_revealed=True,H10_native10_heads_reused_without_per_H_retraining=True,original_claim=ref(R/'CLAIM.json'),original_terminal=ref(R/'RESULT.json'),event=ref(eventpath),audits={k:ref(OUT/(k+'.json')) for k in ['SOURCE_PROTOCOL_AUDIT','CALL_COST_AUDIT','LIVE_EXIT_AND_OCCUPANCY','CONCURRENCY_AND_RUNTIME']},new_GPU_calls_by_audit=0,callback_completion_does_not_emit_event=True,new_wakeup_events=0)
    dump('AUDIT.json',summary);new_json(R/'AUDITED_SUMMARY.json',summary)
    lines=['# C X-VLA H 扫描终局审计','','4000/4000 条新回合全部合法终局，H10 仅复用 2000 条。所有 12 格均为原同一 500 源；无未知、技术缺项、重试或重放。累计 C 尝试 23457/25150，本阶段 4000/4400。','','| 执行 H | N | R-multi | L11 Post-multi |','|---|---:|---:|---:|']
    cs={(r['method'],r['H']):r for r in cells}
    for h in (10,20,30):lines.append('| '+str(h)+' | '+' | '.join(f"{cs[m,h]['successes']}/500 ({cs[m,h]['success_percent']:.1f}%)" for m in ('N','R','Post'))+' |')
    lines += ['', 'Post 相对同 H 的 N：H10 +1.6 个百分点（救回25、损失17），H20 +2.0（36、26），H30 0.0（33、33）；每对均为共同有效的500源。H20/H30 Post 相对 H10 分别 −2.6/−5.2 个百分点，仅作固定配置的描述性比较，不据此重新选型。', '', 'Velocity 单独保存于 VELOCITY_OTHER_WORK_CELLS.csv 与 VELOCITY_OTHER_WORK_PAIRS.csv；H10/H20/H30 成功为407/399/388，各500源。', '', f'逐源重建自然H与C10的时间线，核对{cut_count}次干预、first_cut、G0阈值、候选种子和NFE10；N辅助调用为0，R的Q/梯度调用为0。L11/fit9101四成员、原X坐标桥和Mesa80Hz/.01协议保持。每个C10结束后丢弃尾部并重新自然采样，提前环境终止另行记录。', '', f'4阶段各24个native模型进程、峰值192个交错环境上下文；共96次native加载、72次外部编码器加载。正式波耗时{concurrency["formal_wave_seconds"]/60:.2f}分钟，8卡采样均值{concurrency["eight_GPU_sampled_mean_utilization_percent"]:.2f}%；该采样值包含加载、渲染、调度和尾部时间。全部进程退出后8卡holder已恢复为0.915 duty，duty不等于实测SM。', '', 'CALL_COST_AUDIT.json逐源/worker交叉核对39391次native采样、393910次flow、14374次Q ensemble/动作梯度、57496次Q member、D/G0各89124次、222810次外部视觉编码和1800次语言编码。编码器加载与操作计时单列，嵌套计时不相加；N编码器用时由无进程/无RPC证明为0。未独立测量的子模块计时明确保留缺项。', '', '完整源表与配对见AUDITED_EPISODES.csv、AUDITED_PAIRS.csv；N/R/Post论文用表与Velocity分别导出至C自有目录，原raw、原始汇总和H10历史引用保持。未改写共享论文文件。此前已公开的源和native10训练辅助模型继续用于本H扫描，不宣称独立盲测或每H重新校准。']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    new_json(C/'receipts/C/C_D24_CROSSBASE_H_SWEEP_V1_AUDITED_r1.json',dict(task_id=claim['task_id'],event_id=EID,utc=utc(),status='audited_complete',audit=ref(OUT/'AUDIT.json'),summary=ref(R/'AUDITED_SUMMARY.json'),report=ref(OUT/'REPORT.md'),current_paper_cells=ref(OUT/'CURRENT_PAPER_N_R_POST_CELLS.csv'),current_paper_pairs=ref(OUT/'CURRENT_PAPER_N_R_POST_PAIRS.csv'),Velocity_cells=ref(OUT/'VELOCITY_OTHER_WORK_CELLS.csv'),Velocity_pairs=ref(OUT/'VELOCITY_OTHER_WORK_PAIRS.csv'),valid_new=4000,H10_reused=2000,unfinished=0,attempts=4000,cumulative_C_attempts=23457,new_GPU_calls_by_audit=0,original_results_unchanged=True))
    print(json.dumps(dict(audit=str(OUT/'AUDIT.json'),status='audited_complete',valid=4000,H10_reused=2000,cuts=cut_count,native_sampling=native_totals['policy_queries'],flow=native_totals['policy_flow_calls'],Q_calls=encoder_totals['Q_ensemble_forward_calls'],formal_process_records=len(process_records),holder_count=len(holders),sample_mean_utilization=concurrency['eight_GPU_sampled_mean_utilization_percent']),ensure_ascii=False))
if __name__=='__main__':main()
