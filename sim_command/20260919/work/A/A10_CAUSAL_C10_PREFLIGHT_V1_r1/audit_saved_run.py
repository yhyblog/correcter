"""Post-exit read-only CPU ledger/stage audit; never imports runtime packages."""
from pathlib import Path
from datetime import datetime,timezone
import ast,collections,hashlib,json,struct,zlib,zipfile
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');T='A10_CAUSAL_C10_PREFLIGHT_V1'
W=B/'work/A'/(T+'_r1');O=B/'results/A'/T;R=B/'results/A/P10_CAUSAL_C10_V1_launcher_runs'/(T+'_r1_A_wave09')
REL=B/'releases/P10_A_CAUSAL_C10_PREFLIGHT_V1.json'
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size_bytes=p.stat().st_size)
def put(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
def ledger(path,caps,key,phasefailed):
 starts={};ends={};errors=[];entered=dict.fromkeys(caps,0);returned=dict.fromkeys(caps,0)
 for index,line in enumerate(path.read_text().splitlines() if path.exists() else [],1):
  try:
   row=json.loads(line);eid=row['event_id'];phase=row['phase']
   if phase=='entered':
    units=row[key]
    if eid in starts:raise ValueError('duplicate entry')
    if any(k not in caps or type(v)is not int or v<0 for k,v in units.items()):raise ValueError('invalid units')
    starts[eid]=row
    for k,v in units.items():entered[k]+=v
   else:
    if eid not in starts or eid in ends or phase not in ['returned',phasefailed]:raise ValueError('invalid terminal')
    if key in row and row[key]!=starts[eid][key]:raise ValueError('terminal unit identity mismatch')
    ends[eid]=row
    if phase=='returned':
     for k,v in starts[eid][key].items():returned[k]+=v
  except Exception as e:errors.append(dict(line=index,error=str(e),raw=line))
 missing=sorted(set(starts)-set(ends),key=str);fail=[dict(event_id=e,name=starts[e].get('name',starts[e].get('source',starts[e].get('operation'))),units=starts[e][key],terminal=r) for e,r in ends.items() if r['phase']==phasefailed]
 return dict(path=str(path),file_exists=path.exists(),entered=entered,returned=returned,entered_events=len(starts),terminal_events=len(ends),failed=fail,unresolved=missing,
  corrupt_records=errors,counts_complete=not errors,within_caps=all(v<=caps[k] for k,v in entered.items()),
  last_entry=next(reversed(starts.values())) if starts else None,charge='entered once; returned/failed repeat adds zero, no refunds')
def sum_units(items,keys):return {k:sum(row.get(k,0) for row in items) for k in keys}
assert (W/'COMMAND_RESULT.json').exists(),'Only audit after outer command returns'
cmd=read(W/'COMMAND_RESULT.json');release=read(REL);launch=read(R/'LAUNCH_RESULT.json') if (R/'LAUNCH_RESULT.json').exists() else None
proposal=read(B/'results/A/A10_CAUSAL_C10_CPU_V1/proposal/PROPOSAL.json');budget=read(Path(proposal['budget']['path']))
parent=ledger(R/'launcher_events.jsonl',release['launcher_caps'],'units','raised');branches={};coverage=[]
marks=rows(R/'wave_timing.jsonl')
for branch in ['Post','Velocity']:
 d=R/branch;numeric=ledger(d/'numeric_events.jsonl',budget['per_branch'][branch]['numeric'],'units','raised')
 init=ledger(d/'initialization_events.jsonl',budget['per_branch'][branch]['initialization'],'units','failed')
 graphics=ledger(d/'graphics_events.jsonl',budget['per_branch'][branch]['graphics'],'resource_units','failed')
 events=rows(d/'causal_events.jsonl');transitions=[x for x in events if x['event']=='native_transition_returned']
 starts=[x for x in marks if x['phase']=='timed_process_started' and x.get('branch')==branch]
 br=read(d/'BRANCH_RESULT.json') if (d/'BRANCH_RESULT.json').exists() else None
 fail=read(d/'failure.json') if (d/'failure.json').exists() else None
 step_entries=numeric['entered'].get('env_steps',0);step_returns=numeric['returned'].get('env_steps',0)
 cut=next((x for x in events if x['event']=='cut_legality'),None)
 trigger=next((x for x in events if x['event']=='trigger_decision'),None)
 discard=next((x for x in events if x['event']=='C10_tail_discarded'),None)
 restored=next((x for x in events if x['event']=='native_H20_restored'),None)
 c10=[x for x in transitions if x['plan_id']==branch+'_C10'];prefix=[x for x in transitions if x['plan_id']=='native_prefix_H20'];restore_steps=[x for x in transitions if x['plan_id']=='restored_native_H20']
 causal_complete=(len(transitions)==step_returns and not numeric['unresolved'])
 stage=dict(branch=branch,planned=True,process_started=bool(starts),diagnostic_attempt_entered=numeric['entered'].get('simulator_attempts',0),
  legal_cut_reached=bool(cut and cut['legal']),cut_record=cut,real_G0_trigger=None if trigger is None else trigger['real_G0_trigger'],
  forced_engineering_intervention=None if trigger is None else trigger['forced_engineering_intervention'],trigger_record=trigger,
  native_controls_entered=step_entries,native_controls_returned=step_returns,causal_transition_records=len(transitions),causal_transition_count_complete=causal_complete,
  prefix_steps_saved=len(prefix),C10_steps_saved=len(c10),C10_steps_actual=len(c10) if causal_complete else None,C10_tail_discarded=discard is not None,
  H20_refill_raw_plan_saved=(d/'restore_raw50.npy').exists(),H20_first_steps_saved=len(restore_steps),H20_restored=restored is not None,
  H20_remaining=None if restored is None else restored['remaining'],completed_C10_and_H20=bool(br and br['status']=='C10_and_H20_checked'),
  branch_result=br,failure=fail,missing_stage_reason=None if br and br['status']=='C10_and_H20_checked' else (str(fail) if fail else (br['status'] if br else 'branch did not enter or did not return final receipt')))
 if not starts:stage['missing_stage_reason']='not started: first branch did not complete C10_and_H20_checked or launcher failed before branch entry'
 scopes=[numeric,init,graphics];caps=release['branch_caps'][branch]
 branches[branch]=dict(numeric=numeric,initialization=init,graphics=graphics,total_entered=sum_units([x['entered'] for x in scopes],caps),total_returned=sum_units([x['returned'] for x in scopes],caps),coverage=stage)
 coverage.append(stage)
total=sum_units([parent['entered']]+[x['total_entered'] for x in branches.values()],release['resource_caps'])
returned=sum_units([parent['returned']]+[x['total_returned'] for x in branches.values()],release['resource_caps'])
all_scopes=[parent]+[b[k] for b in branches.values() for k in ['numeric','initialization','graphics']]
claim=B/'results/A/P10_CAUSAL_C10_V1_release_claims/P10_A_CAUSAL_C10_PREFLIGHT_V1.json'
cleanup=read(R/'process_family_cleanup.json') if (R/'process_family_cleanup.json').exists() else None
exit_rows=read(R/'branch_process_exit.json') if (R/'branch_process_exit.json').exists() else None
put(O/'BRANCH_COVERAGE.json',dict(planned=['Post','Velocity'],branches=coverage,completed_C10_branches=[x['branch'] for x in coverage if x['completed_C10_and_H20']],
 launch_reported_completed=None if launch is None else launch.get('completed_C10_branches'),LAUNCH_RESULT_complete_is_not_stage_coverage=True))
put(O/'INDEPENDENT_LEDGER_AUDIT.json',dict(status='CPU_RECONCILED',at_utc=datetime.now(timezone.utc).isoformat(),parent=parent,branches=branches,
 total_entered=total,total_returned=returned,counts_complete=all(x['counts_complete'] for x in all_scopes),all_within_caps=all(total[k]<=v for k,v in release['resource_caps'].items()),
 agrees_with_launcher=None if launch is None else total==launch.get('total_entered'),command_invocations=cmd['command_invocations'],claim_count=int(claim.exists()),
 private_scope_boundaries_preserved=True,public_UUID_stream_created=False,remaining_caps_reusable=False,hardware_queries_by_auditor=0))
put(O/'EXIT_AND_RESTORATION.json',dict(command=cmd,branch_process_exit=exit_rows,process_family_cleanup=cleanup,
 restoration=None if launch is None else launch.get('restoration'),wave_timing=marks,
 successful_guard_poll_count=None,poll_scope='existing guard raw successful poll data not retained; no extra GPU probe',
 baseline_file_snapshot=ref(W/'guard_status_before.json') if (W/'guard_status_before.json').exists() else None))
print(json.dumps(dict(command_exit=cmd['exit_code'],launcher_status=None if launch is None else launch['status'],command_count=1,claim_count=int(claim.exists()),
 complete_branches=[x['branch'] for x in coverage if x['completed_C10_and_H20']],coverage=[{k:x[k] for k in ['branch','process_started','legal_cut_reached','C10_steps_actual','H20_restored','failure','missing_stage_reason']} for x in coverage],
 nonzero_counts={k:v for k,v in total.items() if v},within_caps=all(total[k]<=v for k,v in release['resource_caps'].items()),
 restore_status=None if launch is None else launch.get('restoration',{}).get('status')),indent=2,ensure_ascii=False))
