"""Prepare an isolated, finite continuation of only technically missing units."""
import ast
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
N = C/'results/B/B_D24_CROSSBASE_H_SWEEP_V1'
R = N/'recovery/velocity_r2'
def read(p): return json.loads(p.read_text())
def write(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, sort_keys=True)+'\n')
def change(name, old, new):
    p=R/'code'/name;s=p.read_text()
    assert old in s, (name, old[:100])
    p.write_text(s.replace(old,new,1))

assert not R.exists(), 'Never overwrite an existing recovery claim or package'
missing=read(N/'FINAL_MISSING.json');original=read(N/'SOURCE_INDEX.json')
summary=read(N/'FINAL_SUMMARY.json');assert summary['valid']==3055 and summary['attempts']==3439
assert Counter(x['status'] for x in missing)=={'technical_failure':384,'unstarted':561}
assert all(x['method']=='Velocity' for x in missing)
by_id={x['unit_id']:x for x in missing}
selected=[u for u in original['units'] if u['unit_id'] in by_id]
assert len(selected)==945 and len(by_id)==945
R.mkdir(parents=True)
shutil.copytree(N/'code',R/'code',ignore=shutil.ignore_patterns('__pycache__'))
shutil.copytree(N/'config',R/'config')
for name in ['ASSETS.json','H10_REUSE_POLICY.json','CAPACITY_PREPARATION.json','METHOD_FROZEN.json']:
    shutil.copyfile(N/name,R/name)
write(R/'PREDECESSOR_RECEIPT.json',read(C/'receipts/B/B_D24_CROSSBASE_H_SWEEP_V1_RESULT_r1.json'))
write(R/'SOURCE_INDEX.json',dict(original,units=selected,technical_recovery_only=True,original_root=str(N)))
lineage={}
for u in selected:
    key=hashlib.sha256(u['unit_id'].encode()).hexdigest();old=by_id[u['unit_id']]
    claim=N/'unit_claims'/(key+'.json');result=N/'episodes'/key/'SUMMARY_ROW.json'
    if old['status']=='technical_failure':
        assert claim.exists() and result.exists()
        observed=read(result)
        assert observed['status']=='technical_failure' and observed['success'] is None
        assert 'Inference tensors cannot be saved for backward' in observed['error']
    else: assert not claim.exists() and not result.exists()
    lineage[u['unit_id']]=dict(prior_status=old['status'],previous_claim=str(claim) if claim.exists() else None,
        previous_result=str(result) if result.exists() else None,attempt_ordinal=2 if claim.exists() else 1)
write(R/'RECOVERY_MANIFEST.json',dict(units=lineage,prior_attempts=3439,prior_valid=3055,new_maximum_attempts=961,
    predecessor=str(N),fault='cached inference-mode normalization tensors rejected by action-only autograd',same_fault_repair_restart=1))
cfg=read(R/'config/CONFIG.json')
cfg.update(run_id='D24_B_SMOL_H40_H50_VELOCITY_RECOVERY_r2',revision=2,
    local_dir='/tmp/corrector_B_smol_H40_H50_velocity_r2',methods=['Velocity'],planned_current=945,planned_episodes=945,
    planned_prior_attempts=25561,stage_attempt_cap=961,parent_root=str(N),parent_roots=cfg['parent_roots']+[str(N)],
    recovery_root=str(N),publication_methods=['N','Post','R','Velocity'],original_stage_attempts=3439,
    original_stage_attempt_cap=4400,activation_finalized=False,
    result_receipt='receipts/B/B_D24_CROSSBASE_H_SWEEP_V1_RESULT_r2.json',
    running_receipt='receipts/B/B_D24_CROSSBASE_H_SWEEP_V1_RECOVERY_RUNNING.json')
write(R/'config/CONFIG.json',cfg)
base=read(R/'config/SMOL_BASE.json');base.update(output=str(R),run_id=cfg['run_id']);write(R/'config/SMOL_BASE.json',base)

# Restore the previously proven action-transform initialization for Velocity.
change('smol_server.py',"if cfg['method']=='Post':", "if cfg['method'] in ('Post','Velocity'):")
# Defensive private adaptation: preserve exact stats values, but remove inference-only
# tensor identity before action-only backward. Shared/vendor code is untouched.
change('native_velocity.py',"            physical = self.post(leaf[0, :10, :4])",'''            for step in self.post.steps:
                for stats in getattr(step, '_tensor_stats', {}).values():
                    for name, tensor in list(stats.items()):
                        if torch.is_tensor(tensor) and torch.is_inference(tensor):
                            stats[name] = tensor.clone()
            physical = self.post(leaf[0, :10, :4])''')

change('admission.py',"        if any((Path(p)/'unit_claims'/(key+'.json')).exists() for p in CONFIG['parent_roots']):\n            raise AdmissionStop('unit already entered by predecessor; no duplicate continuation')",'''        lineage=read(ROOT/'RECOVERY_MANIFEST.json')['units'][unit['unit_id']]
        for parent in CONFIG['parent_roots']:
            old_claim=Path(parent)/'unit_claims'/(key+'.json')
            if not old_claim.exists():continue
            if str(old_claim)!=lineage.get('previous_claim'):
                raise AdmissionStop('unit has an unrelated predecessor claim')
            previous=read(lineage['previous_result'])
            if previous['status']!='technical_failure' or previous['success'] is not None:
                raise AdmissionStop('valid or unknown predecessor cannot be replayed')
            if 'Inference tensors cannot be saved for backward' not in previous.get('error',''):
                raise AdmissionStop('recovery fault differs from frozen manifest')''')
change('admission.py',"process=process_identity(),utc=utc(),attempt=0)","process=process_identity(),utc=utc(),attempt=lineage['attempt_ordinal'],lineage=lineage)")
change('admission.py',"    a = read(CONFIG['grant']);", "    if not read(ROOT/'PREDECESSOR_EXIT_CHECK.json')['all_predecessor_processes_exited']:raise AdmissionStop('predecessor exit unproven')\n    if (ROOT/'ENGINEERING_FAILURE.json').exists():raise AdmissionStop('recorded recovery fault; no additional entries')\n    a = read(CONFIG['grant']);")

# Planned branch episodes validate the actual native guidance, not merely t=5.
change('native_client.py',"                            clock.commit(t,event);row['interventions']+=1",'''                            clock.commit(t,event);row['interventions']+=1
                            if method=='Velocity' and not (out/'NATIVE_GUIDANCE_VERIFIED.json').exists():
                                assert len(gstats['updates'])==3
                                new_json(out/'NATIVE_GUIDANCE_VERIFIED.json',dict(utc=utc(),unit_id=unit['unit_id'],step=t,
                                    normal_H=normal_H,updates=gstats['updates'],noise_sha256=gstats['noise_sha256'],
                                    original_candidate_noise_verified=True,intervention_record=str(ep/('intervention_'+str(t)+'.npz'))))''')
change('native_client.py',"step=t+1,active_environment=True)","step=t+1,interventions=row['interventions'],active_environment=True)")
change('native_client.py',"        except BaseException as exc:row.update(status='budget_truncated' if isinstance(exc,AdmissionStop) else 'technical_failure',success=None,error=repr(exc),traceback=traceback.format_exc())",'''        except BaseException as exc:
            row.update(status='budget_truncated' if isinstance(exc,AdmissionStop) else 'technical_failure',success=None,error=repr(exc),traceback=traceback.format_exc())
            if 'Inference tensors cannot be saved for backward' in str(exc):
                atomic_json(ROOT/'ENGINEERING_FAILURE.json',dict(utc=utc(),unit_id=unit['unit_id'],error=repr(exc),stop_remaining_admissions=True))''')
change('manager.py',"        if (ROOT/'RENDER_FAILURE.json').exists():", "        if (ROOT/'ENGINEERING_FAILURE.json').exists():raise AdmissionStop('same engineering fault recurred; no blind continuation')\n        if (ROOT/'RENDER_FAILURE.json').exists():")
change('manager.py',"                        passed.append(progress.get('step',0)>=5 or progress.get('status')=='complete')", "                        passed.append((x['root']/'NATIVE_GUIDANCE_VERIFIED.json').exists())")
change('manager.py',"no_extra_preflight_episodes=True,first_active_branches=8,passed=True", "no_extra_preflight_episodes=True,first_active_branches=8,passed=True,real_native_guidance_verified_on_all8=True")

# Publish all 4000 units; keep r1 raw results intact and account for both attempts.
change('sweep_publication.py',"def summarize(units, rows):", "def summarize(units, rows, all_attempt_rows=None):")
change('sweep_publication.py',"    for method in CONFIG['methods']:", "    for method in CONFIG.get('publication_methods',CONFIG['methods']):")
change('sweep_publication.py',"            totals={}", "            cost_rows=[r for r in (all_attempt_rows if all_attempt_rows is not None else rows) if r['method']==method and r['H']==horizon]\n            totals={}")
change('sweep_publication.py',"                for row in observed:counts.update(row.get(field,{}))", "                for row in cost_rows:counts.update(row.get(field,{}))")
change('sweep_publication.py',"                sum_episode_wall_seconds=sum(r.get('elapsed_seconds',0) for r in observed),", "                sum_episode_wall_seconds=sum(r.get('elapsed_seconds',0) for r in cost_rows),\n                cost_attempt_rows=len(cost_rows),missing_encoder_counter_attempts=sum('encoder_counters' not in r for r in cost_rows),")
change('sweep_publication.py',"    units=read(ROOT/'SOURCE_INDEX.json')['units'];rows=[];missing=[]",'''    predecessor=__import__('pathlib').Path(CONFIG['recovery_root'])
    units=read(predecessor/'SOURCE_INDEX.json')['units'];rows=[];missing=[];all_attempt_rows=[]
    for attempt_root in (predecessor,ROOT):
        for path in (attempt_root/'episodes').glob('*/SUMMARY_ROW.json'):
            all_attempt_rows.append(dict(read(path),attempt_root=str(attempt_root),summary_path=str(path)))''')
change('sweep_publication.py',"        if not path.exists():\n            missing.append",'''        old_ep=predecessor/'episodes'/ep.name;old_path=old_ep/'SUMMARY_ROW.json'
        if old_path.exists() and read(old_path)['status']=='complete':
            if path.exists():raise ValueError('completed predecessor was duplicated')
            ep,path=old_ep,old_path
        elif not path.exists() and old_path.exists():ep,path=old_ep,old_path
        if not path.exists():
            missing.append''')
change('sweep_publication.py',"cells=summarize(units,rows);attempts=", "cells=summarize(units,rows,all_attempt_rows);recovery_attempts=")
change('sweep_publication.py',"    summary=dict(task_id=", "    attempts=CONFIG['original_stage_attempts']+recovery_attempts\n    if attempts>CONFIG['original_stage_attempt_cap']:raise ValueError('combined stage attempt cap exceeded')\n    summary=dict(task_id=")
change('sweep_publication.py',"cumulative_B_attempts=CONFIG['planned_prior_attempts']+attempts,attempt_cap=CONFIG['stage_attempt_cap']", "cumulative_B_attempts=CONFIG['planned_prior_attempts']+recovery_attempts,attempt_cap=CONFIG['original_stage_attempt_cap'],recovery_attempts=recovery_attempts,prior_attempts=CONFIG['original_stage_attempts'],recovery_attempt_cap=CONFIG['stage_attempt_cap']")
change('sweep_publication.py',"        phase_results=read(ROOT/'PHASE_RESULTS.json') if (ROOT/'PHASE_RESULTS.json').exists() else [],", "        phase_results=read(predecessor/'PHASE_RESULTS.json')+(read(ROOT/'PHASE_RESULTS.json') if (ROOT/'PHASE_RESULTS.json').exists() else []),\n        prior_summary=ref(predecessor/'FINAL_SUMMARY.json'),attempt_lineage=ref(ROOT/'RECOVERY_MANIFEST.json'),\n        raw_failed_attempts_preserved=True,costs_include_both_attempts=True,unknown_failure_encoder_costs_not_imputed=True,")
change('sweep_publication.py',"    write_csv(ROOT/'FINAL_EPISODES.csv',rows);", "    write_csv(ROOT/'ALL_ATTEMPTS.csv',all_attempt_rows)\n    write_csv(ROOT/'FINAL_EPISODES.csv',rows);")
change('sweep_publication.py',"    lines=['# B SmolVLA H40/H50 sweep'",'''    aggregate=read(CAMPAIGN/CONFIG['result_receipt'])
    aggregate.update(aggregate_revision=2,original_receipt_preserved=ref(ROOT/'PREDECESSOR_RECEIPT.json'),original_run_result=ref(predecessor/'RESULT.json'))
    atomic_json(CAMPAIGN/'receipts/B/B_D24_CROSSBASE_H_SWEEP_V1_RESULT_r1.json',aggregate)
    atomic_json(predecessor/'RESULT_LATEST.json',dict(root=str(ROOT),summary=ref(ROOT/'FINAL_SUMMARY.json'),utc=utc(),original_r1_result_unchanged=True))
    lines=['# B SmolVLA H40/H50 sweep' ''')

for p in (R/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
print(json.dumps(dict(root=str(R),planned=len(selected),prior_statuses=dict(Counter(x['status'] for x in missing)))))
