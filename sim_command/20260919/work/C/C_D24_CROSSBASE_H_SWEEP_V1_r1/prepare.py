from pathlib import Path
import sys,json,shutil,hashlib,datetime
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');OLD=C/'results/C/C_D24_L11_RENDER_RECOVERY_V1';R=C/'results/C/C_D24_CROSSBASE_H_SWEEP_V1';D=C/'deadline_20260924/CROSSBASE_H_SWEEP_V1'
sys.path.insert(0,str(OLD/'code'))
from qio import read,new_json,ref,utc
for n in ('code','xcode','config','units','claims/units','issues'):(R/n).mkdir(parents=True,exist_ok=True)
for folder in ('code','xcode'):
 for p in (OLD/folder).glob('*.py'):shutil.copyfile(p,R/folder/p.name)
for p in (OLD/'config').glob('*.json'):shutil.copyfile(p,R/'config'/p.name)
shutil.copyfile(OLD/'ASSETS.json',R/'ASSETS.json')
a=read(D/'AUTHORIZATION.json');rows=[json.loads(x) for x in (D/'UNITS_C.jsonl').read_text().splitlines()]
assert len(rows)==len({x['unit_id'] for x in rows})==4000
sources=read(OLD/'config/TEST_SOURCES.json') if (OLD/'config/TEST_SOURCES.json').exists() else read(C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/config/TEST_SOURCES.json')
src={s['source_id']:s for s in sources['sources']}
for u in rows:
 assert u['owner']=='C' and u['H'] in (20,30) and u['model']=='X-VLA' and u['C']==(None if u['method']=='N' else 10)
 assert u['native_source_record']==src[u['source_id']]
 assert u['mode']==('native' if u['method']=='N' else 'G0-multi')
 assert u['Q_loss']==('L11' if u['method'] in ('Post','Velocity') else None)
 u.update(storage_key=hashlib.sha256(u['unit_id'].encode()).hexdigest(),cell_id=f"X-VLA_{u['method']}_H{u['H']}",runtime_source=u['native_source_record'])
 new_json(R/'units'/(u['storage_key']+'.json'),u)
new_json(R/'UNIT_INDEX.json',rows)
def timestamp(t):return datetime.datetime.fromisoformat(t.replace('Z','+00:00')).timestamp()
config=dict(task_id='C_D24_CROSSBASE_H_SWEEP_V1',run_id='D24_C_CROSSBASE_H_SWEEP_r1',grant_sha256='4f8406e67e2d0b73beda277b3bc633749060f30e8420e8513285780a06952c5f',stage_attempt_cap=4400,node_cumulative_attempt_cap=25150,planned_prior_attempts=19457,planned_units=4000,cutoff_unix=timestamp(a['stop_starting_new_units_utc']),absolute_wall_deadline_unix=timestamp(a['formal_exit_and_publication_target_utc']),local_dir='/tmp/corrector_C_CROSSBASE_H_SWEEP_r1',seed_namespace='corrector_native10_training_20260916_v1',model_workers=24,branches_per_worker=8,logical_concurrency=192,stages=[dict(model='X-VLA',method=m) for m in ('N','Post','R','Velocity')],normal_H=[20,30],raw_plan_length=30,commitment_C=10,max_interventions=None,no_extra_GPU_preflight=True)
(R/'config/CONFIG.json').write_text(json.dumps(config,indent=2)+'\n')
x=read(R/'config/X_NATIVE.json');x.update(task_id=config['task_id'],normal_H=[20,30],raw_plan_length=30,commitment_C=10,methods=['N','Post','R','Velocity'],mode='per_unit',absolute_wall_deadline_unix=config['absolute_wall_deadline_unix'],deadline_utc=a['stop_starting_new_units_utc'],stage_attempt_cap=4400,node_cumulative_attempt_cap=25150,planned_prior_attempts=19457,new_collection_attempts=0,small_network_update_cap=0,selection_dependency=None)
(R/'config/X_NATIVE.json').write_text(json.dumps(x,indent=2)+'\n')
# Keep only effective scientific engine fields; old mixed pi05 metadata is not an execution contract.
e=read(OLD/'config/X_ENGINE.json');engine={k:e[k] for k in ('matching','guidance','seed_namespace') if k in e};engine.update(raw_plan_length=30,normal_H=[20,30],commitment_C=10,max_interventions=None,gate_threshold=.05,monitor_interval=5,loss='L11',fit_seed=9101,Post_metric='frozen pi05 S squared returned by the existing X feature server')
(R/'config/X_ENGINE.json').write_text(json.dumps(engine,indent=2)+'\n')
new_json(R/'METHOD_FROZEN.json',dict(utc=utc(),authorization=ref(D/'AUTHORIZATION.json'),source_manifest=ref(C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/config/TEST_SOURCES.json'),Q=read(D/'Q_ASSETS.json')['assets']['X-VLA'],D_G0_root=str(C/'results/C/C_D24_XVLA_AUX_RETRAIN_V1'),base=x['checkpoint'],normal_H=[20,30],raw_H=30,C=10,NFE=10,normal_H_restored_only_after_new_natural_sample=True,N_disables_monitor_and_trigger_and_Q=True,R_uses_G0_and_C10_without_Q=True,source_context_keys='full unit_id including H/method; RNG still uses original source/policy/cut only',rendering='per-environment Mesa llvmpipe contexts and explicit owner binding; native80Hz/.01',stage_order=['N both H','Post both H','R both H','Velocity both H'],H10_replay=False,new_training_updates=0,new_collection=0))
print(json.dumps(dict(prepared_units=len(rows),per_method=1000,new_GPU_calls=0)))
