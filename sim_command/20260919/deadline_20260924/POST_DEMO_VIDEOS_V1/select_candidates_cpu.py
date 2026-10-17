from pathlib import Path
import csv,json,collections,datetime
BASE=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
D=BASE/'deadline_20260924'
ensemble_ref=BASE/'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/ENSEMBLES.json'
ensemble=json.load(ensemble_ref.open())['ensembles']['L11_s9101']
assert [x['member'] for x in ensemble['members']]==[1041,1042,1043,1044]
rollup=D/'L11_FINAL_ROLLUP_20260923/FINAL_EPISODES.csv'
post=[r for r in csv.DictReader(rollup.open()) if r['model']=='pi05' and r['method']=='Post' and r['mode']=='G0-multi']
assert len(post)==2500
assert len({(r['source_id'],r['H']) for r in post})==2500
roster=sorted({r['source_id'][len('D24_NEW_TEST_'):].rsplit('_',1)[0] for r in post})
assert len(roster)==50
n={}; refs=[]
for H in [10,20,30,40,50]:
 for task in roster:
  f=D/f'A/runs/N_H{H}_{task}/RESULT.json'; x=json.load(f.open());refs.append(str(f))
  assert x['method']=='N' and x['H']==H and x['task']==task and x['technical_failures']==0
  for ix,e in enumerate(x['episodes']):
   assert e['status']=='complete' and e['terminal'] and e['technical_failure'] is None
   key=(e['source_id'],H);assert key not in n
   n[key]=(e,str(f),ix)
assert len(n)==2500
res=[]; exclusions=[]
for r in post:
 H=int(r['H']); e,np,idx=n[(r['source_id'],H)]
 if r['success'].lower()!='true' or e['success']: continue
 p=json.load(open(r['result_path']))
 checks={
  'same_source':p['source_id']==e['source_id'],
  'same_task':p['task']==e['task'],
  'same_env_seed':p['env_seed']==e['env_seed'],
  'same_policy_seed':p['policy_seed']==e['policy_seed'],
  'same_H':p['H']==e['H'],
  'same_action_scale':p['action_scale']==e['action_scale']==.015,
  'same_control_hz':p['control_hz']==e['control_hz']==30,
  'same_physics_hz':p['physics_hz']==e['physics_hz']==400,
  'valid_post':p.get('terminal') is True and p.get('status')=='complete' and p.get('success') is True and p.get('technical_failure') is None,
  'post_L11':p.get('Q_loss',p.get('loss'))=='L11',
  'post_fit9101':p.get('Q_fit_seed',p.get('fit_seed'))==9101,
  'post_four_members':p.get('Q_members')==[1041,1042,1043,1044] or (r['reused_ablation50'].lower()=='true' and '/A_D24_FULL_Q_AUTORUN_POST_LED_V1/' in r['result_path'] and ensemble['fit_seed']==9101 and ensemble['loss']=='L11'),
  'post_G0_multi':p.get('mode')=='G0-multi'
 }
 item={'task':e['task'],'source_id':e['source_id'],'ordinal':e['ordinal'],'H':H,'env_seed':e['env_seed'],'policy_seed':e['policy_seed'],'split':'test','same_initial_state_protocol':'same task + env_seed; re-record both arms from fresh reset and verify initial observation/state before execution; do not claim full hidden-state proof','N':{'success':False,'result_path':np,'json_pointer':f'/episodes/{idx}','steps':e['steps'],'terminal_reason':e.get('terminal_reason'),'policy_calls':e['policy_calls']},'Post':{'success':True,'result_path':r['result_path'],'unit_id':r['unit_id'],'steps':p['steps'],'terminal_reason':p.get('terminal_reason'),'interventions':p.get('interventions'),'intervention_cuts':p.get('intervention_cuts'),'Q_loss':'L11','Q_fit_seed':9101,'Q_members':[1041,1042,1043,1044],'mode':'G0-multi','result_source_table':r['source_table'],'input_group':r['input_group'],'Q_member_identity_evidence': 'episode Q_members' if p.get('Q_members') else str(ensemble_ref)+'#/ensembles/L11_s9101','reused_ablation50':r['reused_ablation50'].lower()=='true'},'checks':checks}
 if not all(checks.values()):exclusions.append(item)
 else:res.append(item)
assert not exclusions,exclusions[:1]
by=collections.defaultdict(list)
for r in res:by[r['task']].append(r)
tasks=[]; primary=[]; reserve=[]
for task in roster:
 rows=sorted(by[task],key=lambda x:(x['H'],x['ordinal']))
 distinct=[];seen=set()
 for x in rows:
  if x['source_id'] not in seen:
   seen.add(x['source_id']);distinct.append(x)
 chosen=distinct[:5]
 for i,x in enumerate(chosen):
  x['candidate_id']=f"{task}_H{x['H']}_source{x['ordinal']:02d}"
  x['task_rank']=i+1;x['recording_priority']='primary' if i<3 else 'reserve'
  (primary if i<3 else reserve).append(x)
 tasks.append({'task':task,'rescue_pairs_across_H':len(rows),'distinct_rescued_initial_states':len(distinct),'primary_count':min(3,len(chosen)),'reserve_count':max(0,len(chosen)-3),'H10_rescue_pairs':sum(x['H']==10 for x in rows),'candidate_ids':[x['candidate_id'] for x in chosen]})
summary={'n_reference_episodes':2500,'post_reference_episodes':2500,'historical_rescue_pairs_across_H':len(res),'distinct_rescued_task_source_pairs':len({x['source_id'] for x in res}),'task_coverage':sum(bool(v) for v in by.values()),'tasks_with_at_least_3_distinct_initial_states':sum(x['distinct_rescued_initial_states']>=3 for x in tasks),'tasks_with_less_than_3_but_nonzero':sum(0<x['distinct_rescued_initial_states']<3 for x in tasks),'primary_candidates':len(primary),'reserve_candidates':len(reserve),'maximum_candidate_pairs':len(primary)+len(reserve),'maximum_rollouts_if_all_candidates_recorded':2*(len(primary)+len(reserve)),'zero_rescue_tasks':[x['task'] for x in tasks if x['rescue_pairs_across_H']==0],'historical_rescue_pairs_by_H':dict(sorted(collections.Counter(x['H'] for x in res).items()))}
out={'schema':'post_demo_candidate_pairs_v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Qualitative success-selected demonstration only; not new aggregate evaluation or an unbiased success-rate sample. Actual re-recorded N failure and Post success must be checked before publishing paired video.','post_config':{'model':'pi05','method':'Post','mode':'G0-multi','Q_loss':'L11','Q_fit_seed':9101,'Q_members':[1041,1042,1043,1044]},'selection_rule':'Per task: H10 before H20/30/40/50, ordinal ascending; unique initial state across H; first 3 primary plus up to2 reserve. No new seed search in this CPU selection.','summary':summary,'task_summary':tasks,'primary_candidates':primary,'reserve_candidates':reserve,'all_historical_rescues':res,'source_refs':{'post_rollup':str(rollup),'N_result_files':refs},'seed_and_unit_checks':'All historical rescue candidates passed explicit result-field equality and L11 identity checks. No new model/render/rollout was run.'}
Path('/tmp/post_demo_candidates.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
md=['# Post qualitative comparison candidates','','Historical N failure / Post L11 multi success; actual video reruns must reconfirm outcomes.','',f"{len(res)} historical same-H rescue pairs across {sum(bool(v) for v in by.values())}/50 tasks; {summary['distinct_rescued_task_source_pairs']} distinct task/initial states. Priority {len(primary)} pairs, reserve {len(reserve)} pairs; at most {summary['maximum_rollouts_if_all_candidates_recorded']} rollouts if every reserve is needed.",'','| Task | Rescue pairs (all H) | Distinct sources | H10 pairs | Primary | Reserve |','|---|---:|---:|---:|---:|---:|']
md += [f"| {x['task']} | {x['rescue_pairs_across_H']} | {x['distinct_rescued_initial_states']} | {x['H10_rescue_pairs']} | {x['primary_count']} | {x['reserve_count']} |" for x in tasks]
md+=['','Zero-rescue tasks: '+', '.join(summary['zero_rescue_tasks']), '', 'Ordering is H10 first, then H20/30/40/50; unique source IDs. These are selected demonstrations and must not change the existing aggregate success-rate tables. Preserve failed re-recordings, and use reserves only within the fixed list.','', 'All explicit task/env_seed/policy_seed/H/action-unit/control-frequency/Q identity checks passed for all historical rescues. Same seeds identify the intended initial-state protocol, not proof of arbitrary hidden-state equality. No GPU/model/render call performed.']
Path('/tmp/post_demo_candidates.md').write_text('\n'.join(md)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
