"""Independent CPU terminal audit. No launch, GPU call, message or retry."""
import collections,csv,datetime,hashlib,json,math
from pathlib import Path
import numpy as np
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');TASK='C_D24_R_TRIGGER_MODES_V1';R=C/'results/C'/TASK
EID='C_c03cc2835839dc0f52a72a7e13763471';EVENT=C/'persistent_queue/nodes/C/wakeup/outbox'/(EID+'.json');AUDIT=C/'receipts/C/events'/(EID+'_AUDIT.json')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csvread(p):
 with Path(p).open() as f:return list(csv.DictReader(f))
def write(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def near(a,b):assert math.isclose(float(a),float(b),abs_tol=1e-9,rel_tol=1e-10),(a,b)
def dumpcsv(p,rows):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
event=read(EVENT);claim=read(R/'CLAIM.json');cfg=read(R/'config/CONFIG.json');result=read(R/'RESULT.json');frozen=read(R/'METHOD_FROZEN.json')
assert event['job']['task_id']==TASK and event['result']==result and result['status']=='complete' and result['exit_code']==0
assert event['job']['claim_identity']['sha256']==sha(R/'CLAIM.json') and event['job']['process_identity']==claim['process']
for name in ['config','method_frozen','CPU_check']:assert sha(claim[name]['path'])==claim[name]['sha256']
assert sha(frozen['authorization']['path'])==claim['authorization_sha256']
for name in ['TEST_SOURCES_V1.json','RANDOM_ONCE_SCHEDULE_V1.json','G0_ONCE_BASELINES.json']:
 assert sha(R/'config'/name)==frozen['inputs'][name]['sha256']
sources=read(R/'config/TEST_SOURCES_V1.json')['rows'];source_map={s['source_id']:s for s in sources};ordered=sorted(sources,key=lambda s:(s['task'],s['ordinal']));assert len(sources)==len(source_map)==500
schedule={(x['source_id'],x['H']):x['selected_cut'] for x in read(R/'config/RANDOM_ONCE_SCHEDULE_V1.json')['rows']}
base={(int(x['H']),x['source_id']):x for x in read(R/'config/G0_ONCE_BASELINES.json')['rows']};assert len(base)==2500
scalars=csvread(R/'FINAL_EPISODES.csv');assert len(scalars)==5000
claims=list(R.glob('unit_claims/*.json'));assert len(claims)==5000 and len(list(R.glob('claims/*.json')))==500
core={};counts=collections.Counter();totals=collections.Counter();per_cell=collections.defaultdict(list)
for row in scalars:
 h=int(row['H']);mode=row['mode'];sid=row['source_id'];cell=f'R_H{h}_{mode}';key=(h,mode,sid);assert key not in core
 a=read(R/'unit_claims'/(cell+'__'+sid+'__attempt1.json'));assert a['attempt']==1 and a['retry'] is False and a['mode']==mode and a['source']==source_map[sid]
 p=Path(row['result_path']);assert p.parent==Path(a['output']) and p.is_relative_to(R/'runs') and (p.parent/'ENTERED.json').exists()
 ep=read(p);assert ep['status']=='complete' and ep['terminal'] and type(ep['success']) is bool and ep['technical_failure'] is None
 assert ep['mode']==mode and ep['H']==h and ep['method']=='R'
 for field in ['source_id','task','ordinal','env_seed','policy_seed']:assert ep[field]==source_map[sid][field] and row[field]==str(ep[field])
 assert row['success']==str(ep['success']) and json.loads(row['intervention_cuts'])==ep['intervention_cuts']
 assert (ep['control_hz'],ep['physics_hz'],ep['action_scale'],ep['action_dim'])==(30,400,.015,4)
 cuts=ep['intervention_cuts'];fired=[x for x in ep['events'] if x['intervention_executed']]
 assert ep['interventions']==len(cuts)==len(fired) and cuts==[x['step'] for x in fired]
 assert ep['first_cut']==(cuts[0] if cuts else None) and ep['last_cut']==(cuts[-1] if cuts else None)
 assert all(b-a>=15 for a,b in zip(cuts,cuts[1:]))
 for ev in fired:
  assert ev['legal_cut'] and ev['history_mature'] and ev['queue_age']>0 and ev['commit_until']==ev['step']+10 and ev['restore_native_H']==h
  assert not ev['forced_intervention'] and not ev['synthetic'] and ev['generation']['method']=='R' and not ev['generation']['Q_acceptance_gate']
 if mode=='Random-once':
  assert ep['max_interventions']==1 and ep['random_scheduled_cut']==schedule[sid,h] and cuts in ([],[schedule[sid,h]])
  assert all(ev['shadow_G0'] for ev in ep['events'])
  if not cuts:assert ep['no_intervention_reason']=='terminal_before_scheduled_cut' and ep['steps']<=schedule[sid,h]
 else:
  assert mode=='G0-multi' and ep['max_interventions'] is None and ep['random_scheduled_cut'] is None
  assert all(ev['gate']>.05 and ev['true_G0_trigger'] and not ev['shadow_G0'] for ev in fired)
 assert ep['flow_calls']==ep['policy_calls']*10 and ep['counters']['action_gradients']==ep['counters']['Q_ensemble_forward']==0
 for field in ['elapsed_seconds','inference_seconds','environment_seconds','monitor_seconds','shadow_context_DG0_seconds']:near(row[field],ep[field])
 core[key]=ep;per_cell[cell].append(ep);counts[cell]+=1;totals.update(ep['counters'])
assert len(counts)==10 and set(counts.values())=={500}
summary=read(R/'SUMMARY.json');assert summary['valid']==summary['attempts']==5000 and summary['cumulative_C_attempts']==7013
assert summary['technical_failures']==summary['unknown_entered']==summary['not_started']==summary['automatic_retries']==0
assert summary['prior_C_attempts']==2013 and 5000<=cfg['stage_attempt_cap']==5500 and 7013<=cfg['node_cumulative_attempt_cap']==7900
cell_csv={x['cell_id']:x for x in csvread(R/'FINAL_CELLS.csv')};paired_saved={x['cell_id']:x for x in read(R/'FINAL_PAIRED.json')['comparisons']}
draws=np.random.default_rng(20260921).integers(0,10,size=(2000,50,10));pairs=[];costs=[]
for cell,eps in per_cell.items():
 h=eps[0]['H'];mode=eps[0]['mode'];s=summary['cells'][cell];c=cell_csv[cell];assert s['successes']==int(c['successes'])==sum(ep['success'] for ep in eps)
 interventions=[x['interventions'] for x in eps]
 for key,v in [('trigger_0',sum(x==0 for x in interventions)),('trigger_1',sum(x==1 for x in interventions)),('trigger_ge2',sum(x>=2 for x in interventions)),('intervention_mean',np.mean(interventions)),('intervention_median',np.median(interventions)),('intervention_p95',np.percentile(interventions,95)),('intervention_max',max(interventions))]:near(s[key],v);near(c[key],v)
 for key in ['policy_calls','flow_calls','elapsed_seconds','inference_seconds','environment_seconds','monitor_seconds','shadow_context_DG0_seconds']:
  near(s[key+'_known_total'],sum(ep[key] for ep in eps));near(c[key+'_known_total'],sum(ep[key] for ep in eps))
 a=np.array([core[h,mode,x['source_id']]['success'] for x in ordered],dtype=np.int64);b=np.array([base[h,x['source_id']]['success']=='True' for x in ordered],dtype=np.int64)
 delta=(a-b).reshape(50,10);boot=delta[np.arange(50)[None,:,None],draws].sum((1,2))/5;lo,hi=np.quantile(boot,[.025,.975])
 p=dict(cell_id=cell,H=h,mode=mode,paired_valid=500,left_successes=int(a.sum()),right_successes=int(b.sum()),rescued=int(((a==1)&(b==0)).sum()),harmed=int(((a==0)&(b==1)).sum()),both_success=int(((a==1)&(b==1)).sum()),both_failed=int(((a==0)&(b==0)).sum()),delta_pp=float(delta.sum()/5),bootstrap95_low_pp=float(lo),bootstrap95_high_pp=float(hi))
 for k,v in p.items():
  if k not in ['cell_id','H','mode']:near(paired_saved[cell][k],v)
 pairs.append(p);br=[base[h,x['source_id']] for x in ordered]
 policy=sum(x['policy_calls'] for x in eps);once_policy=sum(int(x['policy_calls']) for x in br);new_success=sum(x['success'] for x in eps);old_success=sum(x['success']=='True' for x in br)
 costs.append(dict(cell_id=cell,H=h,mode=mode,valid=500,policy_calls=policy,once_policy_calls=once_policy,policy_calls_per_episode=policy/500,once_policy_calls_per_episode=once_policy/500,delta_policy_calls_per_episode=(policy-once_policy)/500,policy_call_ratio=policy/once_policy,flow_calls=policy*10,once_flow_calls=once_policy*10,policy_calls_on_success=sum(x['policy_calls'] for x in eps if x['success']),policy_calls_conditional_success_mean=sum(x['policy_calls'] for x in eps if x['success'])/new_success,once_policy_calls_conditional_success_mean=sum(int(x['policy_calls']) for x in br if x['success']=='True')/old_success,all_policy_calls_per_success=policy/new_success,once_all_policy_calls_per_success=once_policy/old_success,action_gradients=0,Q_ensemble_forward=0,shadow_context_DG0_seconds=sum(x['shadow_context_DG0_seconds'] for x in eps)))
workers=[read(p) for p in R.glob('chain/workers/*/WORKER_EXIT.json')];assert len(workers)==8 and all(x['fatal'] is None and not x['cleanup'] for x in workers)
for k,v in totals.items():assert sum(x['method_counts'][k] for x in workers)==v,(k,v)
assert len(list(R.glob('runs/*/RESULT.json')))==500 and len(list(R.glob('cells/*/PUBLICATION.json')))==10
runtime=read(R/'evidence/TERMINAL_RUNTIME_AUDIT.json');assert runtime['all_formal_identities_absent'] and runtime['formal_group_empty'] and runtime['all8_holders_live']
dumpcsv(R/'COST_COMPARISONS.csv',sorted(costs,key=lambda x:(x['H'],x['mode'])))
d=dict(event_id=EID,task_id=TASK,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='passed',outcome='audited',event_path=str(EVENT),claim_sha256=sha(R/'CLAIM.json'),existing_claim_verified=True,valid_first_entries=5000,per_cell=counts,technical_failures=0,unknown_entered=0,not_started=0,scientific_retries=0,prior_C_attempts=2013,cumulative_C_attempts=7013,independently_recomputed_pairs=sorted(pairs,key=lambda x:(x['H'],x['mode'])),cost_comparisons=str(R/'COST_COMPARISONS.csv'),actual_counters=totals,all8_workers_exited_cleanly=True,formal_group_empty=True,all8_holders_restored=True,runtime_audit=str(R/'evidence/TERMINAL_RUNTIME_AUDIT.json'),scope='All5000 current terminal scalar records/claims and executed-cut metadata, frozen source joins, ten independent stratified bootstrap contrasts and actual call totals; no RGB, trajectories, weight rehash or historical replay audit',script=str(Path(__file__).resolve()),script_sha256=sha(__file__),callback_scientific_launches=0,prior_completed_source_replays=0,recursive_wakeup_events=0,uncertainty='Pointwise fixed50-task intervals, no multiplicity adjustment or training-seed/new-task population uncertainty. Trigger rates differ, so these are strategy effects rather than pure timing effects at equal realized counts.')
write(R/'FINAL_AUDIT.json',d);write(AUDIT,d)
print(json.dumps({'audit':str(AUDIT),'status':'passed','valid':5000,'pairs':d['independently_recomputed_pairs'],'costs':costs},indent=2))
