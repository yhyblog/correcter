"""CPU-only private runtime assembly; never claims or launches a science unit."""
import copy, datetime, hashlib, json, shutil
from pathlib import Path

C=Path(__file__).resolve().parents[3]
ROOT=C/'results/C/C_D24_PI05_SELECTED_H40_H50_V1'
A=C/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1'
X=C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1'
TASK=ROOT.name
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2);f.write('\n')
def ref(p):return dict(path=str(p),sha256=digest(p))

if (ROOT/'CLAIM.json').exists():raise RuntimeError('Do not mutate a deployed queue')
copies=[]
for parent,names in [(A,['controller','numeric_engine','resident_egl','resident_worker','renderer_cleanup','recorder','publication_data','analysis_tools']),
                     (X,['qio','reservation','process_family','qoccupancy','wave_timing','qmetrics','wave'])]:
    for name in names:
        src=parent/'code'/(name+'.py');dst=ROOT/'code'/src.name
        shutil.copyfile(src,dst);copies.append(dict(source=ref(src),copy=str(dst),byte_identical_at_copy=True))
worker=ROOT/'code/resident_worker.py'
s=worker.read_text().replace("first=next(c for c in read(ROOT/'config/CONFIG.json')['cells'] if c['stage']=='DEV')", "first=next(c for c in read(ROOT/'config/CONFIG.json')['cells'] if c['stage']=='MAIN' and c['H']==40)")
s=s.replace("Q='complete fresh Q per frozen cell / dev selection'", "Q='A pi05 selected full Q, fixed fit9101, immutable dev selection'")
worker.write_text(s)
base=read(C/'results/C/C_D24_R_TRIGGER_MODES_V1/config/BASE.json')
write(ROOT/'config/BASE.json',base)
cfg=read(A/'config/CONFIG.json')
cfg['cells']=[c for c in cfg['cells'] if c['stage']=='MAIN' and c['H'] in [40,50]]
cfg['cells'].sort(key=lambda c:(c['H'],c['method']))
cfg.update(task_id=TASK,max_episodes=2200,planned_episodes=2000,stage_attempt_cap=2200,
    node_cumulative_attempt_cap=16000,planned_prior_attempts=None,evaluation_workers=24,
    workers_per_GPU=3,run_stage='transferred_selected_pi05_H40_then_H50',modes=['G0-multi'],
    stages=['MAIN_H40','MAIN_H50'],original_A_configuration=ref(A/'config/CONFIG.json'),
    absolute_wall_deadline_unix=datetime.datetime(2026,9,23,12,tzinfo=datetime.timezone.utc).timestamp(),
    source_first_cap=2000,new_training_updates=0,new_collection=0)
cfg.pop('overall_A_attempt_cap')
write(ROOT/'config/CONFIG.json',cfg)
sources=read(A/'SOURCE_INDEX.json')
write(ROOT/'SOURCE_INDEX.json',dict(source_sets={k:sources['source_sets'][k] for k in ['MAIN','DEV']},original=ref(A/'SOURCE_INDEX.json')))
ownership=read(C/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json')
jobs=[];units=set()
for r in ownership['owners']['C']:
    p=Path(r['path']);j=read(p)
    assert digest(p)==r['sha256'] and j['stage']=='MAIN' and j['H'] in [40,50]
    target=ROOT/'planned_jobs'/p.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(p,target)
    jobs.append(dict(job_id=j['job_id'],path=str(target),sha256=digest(target),original=r))
    for source in j['sources']:
        u=j['cell_id']+'__'+source['source_id'];assert u not in units;units.add(u)
assert len(jobs)==400 and len(units)==2000
write(ROOT/'PLANNED_JOB_INDEX.json',dict(jobs=jobs,scientific_units=2000,claimed_units=0,requires_exact_transfer=True))
write(ROOT/'SOURCE_PROVENANCE.json',dict(copied_modules=copies,base=ref(C/'results/C/C_D24_R_TRIGGER_MODES_V1/config/BASE.json'),
    ownership_plan=ref(C/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json'),original_A_configuration=ref(A/'config/CONFIG.json'),
    original_source_index=ref(A/'SOURCE_INDEX.json'),changes=['C host/boot and UUID binding','C ownership and finite budgets','A selected pi05 ensemble only','H40 before H50','C notification and reports'],
    algorithm_modules_unchanged=['controller.py','numeric_engine.py','resident_egl.py'],new_scientific_units=0))
print('prepared',ROOT,len(jobs),len(units))
