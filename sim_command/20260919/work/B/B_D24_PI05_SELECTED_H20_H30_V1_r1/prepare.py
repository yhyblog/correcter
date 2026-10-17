"""CPU preparation only. Never launches a scientific process."""
import copy,json,shutil,time
from pathlib import Path
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=C/'results/B/B_D24_PI05_SELECTED_H20_H30_V1'
F=C/'results/B/B_D24_FULL_Q_LOSS_REFRESH_V1'
M=C/'results/B/B_D24_SMOL_MULTI_EVAL_V1'
R=M/'R_unstarted_r2'
A=C/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1'
GRANT='deadline_20260924/FULL_Q_AUTORUN_AUTHORIZATION_V2.json'
SHA='fb15e23ad4ed75eaa1b9490784d58dc9dc925e440194e99cab066ae11af6414f'
TASK=P.name
def read(p):return json.loads(p.read_text())
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
def code(root,name,source):
 (root/'code').mkdir(parents=True,exist_ok=True);shutil.copyfile(source,root/'code'/name)
assert not (P/'QUEUE_CLAIM.json').exists()
P.mkdir(parents=True,exist_ok=True)
ownbase=read(C/'results/B/B_D24_R_H20_H30_V1/config/BASE.json')
base=read(A/'config/BASE.json')
for key in ['cuda_environment','device','device_list','physical_inventory','LD_LIBRARY_PATH','python']:
 base[key]=copy.deepcopy(ownbase[key])
for key in ['cuda_environment','device','physical_inventory','isolation_root']:
 base['native'][key]=copy.deepcopy(ownbase['native'][key])
write(P/'BASE_LOCAL.json',base)
for name in ['qio.py','process_family.py','qoccupancy.py','reservation.py','wave_timing.py','qmetrics.py']:
 code(P,name,F/'code'/name)
write(P/'CONFIG.json',dict(task_id=TASK,run_id='D24_B_PI05_SELECTED_CHAIN_r1',grant=GRANT,grant_sha256=SHA,
 predecessor_root=str(F),selection_path=str(A/'SELECTION.json'),selection_lock=str(A/'SELECTION_LOCK.json'),
 transfer_ready=str(C/'results/A/A_D24_FULL_Q_AUTORUN_HANDOFF_V2/TRANSFER_READY.json'),
 deadline_unix=min(time.time()+43200,1790164800),stage_hours=12,first_maximum=2000,stage_attempt_cap=2200,
 cumulative_attempt_cap=22000,local_dir='/tmp/corrector_B_pi05_selected_chain_r1',
 executor_thread_id='01a0b9c5-1e4b-7b73-9336-229e6df349a2',original_native_waiter_preserved=True))
plan=read(C/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json')
write(P/'PLANNED_OWNERSHIP.json',dict(status='planned_not_admitted',jobs=plan['owners']['B']))
cells=read(A/'config/CONFIG.json')['cells']
for H in [20,30]:
 root=P/f'H{H}_r1'
 for folder in ['config','jobs','claims','unit_claims','runs','failures','deployments']:(root/folder).mkdir(parents=True,exist_ok=True)
 for name in ['service.py','qio.py','process_family.py','qoccupancy.py','reservation.py','wave_timing.py','qmetrics.py']:
  code(root,name,F/'code'/name)
 for name in ['controller.py','numeric_engine.py','recorder.py','resident_egl.py','renderer_cleanup.py']:
  code(root,name,A/'code'/name)
 code(root,'paths.py',F/'code/paths.py')
 s=(root/'code/paths.py').read_text();s+='\nTASK=CONFIG["task_id"]\n';(root/'code/paths.py').write_text(s)
 worker=(A/'code/resident_worker.py').read_text().replace("first=next(c for c in read(ROOT/'config/CONFIG.json')['cells'] if c['stage']=='DEV')","first=read(ROOT/'config/CONFIG.json')['cells'][0]")
 (root/'code/resident_worker.py').write_text(worker)
 cfg=read(A/'config/CONFIG.json');cfg.update(task_id=TASK,run_id=f'D24_B_PI05_H{H}_r1',grant=GRANT,grant_sha256=SHA,
  artifact_root=str(P),pipeline_root=str(P),local_dir=f'/tmp/corrector_B_pi05_H{H}_r1',activation_finalized=False,
  H=H,cells=[v for v in cells if v['stage']=='MAIN' and v['H']==H],planned_current=1000,
  target_workers=24,workers_per_gpu=3,node_cumulative_attempt_cap=22000,stage_attempt_cap=1100,
  whole_pi05_attempt_cap=2200,absolute_wall_deadline_unix=1790164800,
  running_receipt=f'receipts/B/{TASK}_H{H}_RUNNING.json',result_receipt=f'receipts/B/{TASK}_H{H}_RESULT_r1.json',
  completion_via_queue=False,Post_paper_primary=True,Velocity_current_paper=False)
 write(root/'config/CONFIG.json',cfg);write(root/'config/BASE.json',base)
 write(root/'METHOD_FROZEN.json',dict(source=str(A/'METHOD_FROZEN.json'),H=H,configuration=cfg,
  model='pi05_MT50_SFT030000',Q='A selected Post-only loss fixed fit9101; never B Smol Q',
  adaptation='B observed UUID/driver libraries only; original A numerical controller/engine/seed stream'))
 write(root/'SOURCE_INDEX.json',dict(source_index=str(A/'SOURCE_INDEX.json'),planned_jobs=[v for v in plan['owners']['B'] if read(Path(v['path']))['H']==H],
  activation_requires_exact_TRANSFER_READY=True))
# Authorized single continuation of the 24 original cancelled R units.
rr=P/'R_cancelled_r3'
for folder in ['code','config','jobs','claims/attempts','claims/jobs','runs','evaluation/R','deployments']:(rr/folder).mkdir(parents=True,exist_ok=True)
for p in (R/'code').glob('*.py'):code(rr,p.name,p)
idx=read(R/'SOURCE_INDEX.json');valid=read(R/'VALID_RESULT_INDEX.json')['rows'];sources=read(Path(idx['full_sources']['path']))['sources'];byid={s['source_id']:s for s in sources}
cancelled=[x for x in idx['retained'] if x.get('disposition')=='user_cancelled']
assert len(valid)==476 and len(cancelled)==24
pending=[]
for item in cancelled:
 old=read(Path(item['result']['path']));assert old['success'] is None and old['status']=='budget_truncated' and old['steps']<300
 pending.append(dict(method='R',source_id=item['source_id'],source=byid[item['source_id']],previous_result=item['result'],attempt_kind='one_authorized_user_cancelled_continuation'))
assert not ({v['source_id'] for v in valid}&{v['source_id'] for v in pending})
write(rr/'SOURCE_INDEX.json',dict(full_sources=idx['full_sources'],pending=pending,retained=valid,known_interrupted=cancelled))
write(rr/'METHOD_FROZEN.json',read(R/'METHOD_FROZEN.json'));write(rr/'config/BASE.json',read(R/'config/BASE.json'))
cfg=read(R/'config/CONFIG.json');cfg.update(run_id='D24_B_SMOL_R_CANCELLED_r3',grant=GRANT,grant_sha256=SHA,
 grant_task_id=TASK,local_dir='/tmp/corrector_B_smol_R_cancelled_r3',pipeline_root=str(P),
 activation_finalized=False,planned_current=24,stage_attempt_cap=24,carried_stage_attempts=500,original_stage_attempt_cap=1650,
 node_cumulative_attempt_cap=22000,predecessor_required_complete=False,completion_via_queue=False,
 running_receipt='receipts/B/B_D24_SMOL_R_CANCELLED_r3_RUNNING.json',result_receipt='receipts/B/B_D24_SMOL_R_CANCELLED_r3_RESULT.json')
write(rr/'config/CONFIG.json',cfg)
pub=(rr/'code/publish.py').read_text().replace("<=20000","<=CONFIG['node_cumulative_attempt_cap']")
(rr/'code/publish.py').write_text(pub)
write(P/'ORDERED_STAGES.json',dict(stages=[dict(stage='existing_Smol_selected_PV1000',root=str(F),ownership='existing pipeline only'),
 dict(stage='R_cancelled_once',root=str(rr),maximum=24),dict(stage='PI05_H20',root=str(P/'H20_r1'),maximum=1000),
 dict(stage='PI05_H30',root=str(P/'H30_r1'),maximum=1000),dict(stage='CPU_publication')],
 dependencies=['complete Post-only development selection before new selected tests','own predecessor family exit','A exact unit ownership before pi05'],
 no_cross_host_runtime_barrier=True,all_holders_off_entire_formal_wave=True,waiter_original_deadline_preserved=True))
print(json.dumps(dict(root=str(P),pi05_planned_jobs=len(plan['owners']['B']),R_cancelled=len(pending),retained_R=len(valid))))
