"""Prepare the new, isolated L11 queue using existing frozen scientific code."""
import ast, hashlib, json, shutil
from pathlib import Path
C=Path(__file__).resolve().parents[3]
ROOT=C/'results/C/C_D24_L11_RETEST_V1'
X=C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1'
P=C/'results/C/C_D24_PI05_SELECTED_H40_H50_V1'
A=C/'deadline_20260924/L11_RETEST_V1'
def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def replace(text,old,new,count=1):
    assert text.count(old)==count,(old,text.count(old));return text.replace(old,new)
for d in ['code','xcode','config','units','evidence','claims','evaluation','pi_evaluation','issues']:(ROOT/d).mkdir(exist_ok=True)
for name in ['qio.py','process_family.py','reservation.py','qoccupancy.py','wave_timing.py','qmetrics.py','numeric_engine.py','resident_egl.py','renderer_cleanup.py','recorder.py','publication_data.py']:
    shutil.copyfile(P/'code'/name,ROOT/'code'/name)
shutil.copyfile(X/'code/episode_runtime.py',ROOT/'code/episode_runtime.py')
for name in ['native_velocity.py','projector.py']:
    shutil.copyfile(X/'code'/name,ROOT/'xcode'/name)
paths=(P/'code/paths.py').read_text().split('AUTH_SHA=')[0]
paths += "AUTH_SHA='a978519ba24dfb3aba22cf5ce8472d9b855e788e44266a28e0d006be876d5e87'\nTASK='C_D24_L11_RETEST_V1'\nJOB='D24_C_L11_RETEST_r1'\nHEADS=CAMPAIGN/'results/C/C_D24_XVLA_AUX_RETRAIN_V1'\n"
paths += "for p in (WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src'):\n    if str(p) not in sys.path:sys.path.insert(0,str(p))\nsys.path.insert(0,str(ROOT/'code'))\n"
paths += "def external_encoder_paths():\n    for p in (ACCEPTED,ACCEPTED/'vendor_vla/src'):\n        if str(p) not in sys.path:sys.path.insert(0,str(p))\n    sys.path.insert(0,str(ROOT/'code'))\n"
(ROOT/'code/paths.py').write_text(paths);(ROOT/'xcode/paths.py').write_text(paths)
controller=(P/'code/controller.py').read_text()
controller=replace(controller,"        emit('step',dict(step=t+1,success=bool(step['success']),interventions=count))", "        emit('step',dict(step=t+1,success=bool(step['success']),interventions=count))\n        yield dict(step=t+1,source_id=source['source_id'])")
(ROOT/'code/controller.py').write_text(controller)
episode=(P/'code/resident_worker.py').read_text().split('\ndef main():')[0]
episode=replace(episode,'row=run_episode(runtime,engine,source,method,H,emit,stop,mode=mode)','row=yield from run_episode(runtime,engine,source,method,H,emit,stop,mode=mode)')
(ROOT/'code/pi_episode.py').write_text(episode)

assets=read(A/'prepared_by_analysis/ASSET_REFERENCES.json')['assets']
units=[json.loads(x) for x in (A/'prepared_by_analysis/NEW_UNITS_C.jsonl').read_text().splitlines()]
assert len(units)==len({u['unit_id'] for u in units})==2500
assert all(u['owner']=='C' and u['Q_loss']=='L11' and u['Q_fit_seed']==9101 for u in units)
sources={s['source_id']:s for s in read(P/'SOURCE_INDEX.json')['source_sets']['MAIN']}
for u in units:
    if u['model']=='pi05':
        s=sources[u['source_id']]
        assert (s['env_seed'],s['policy_seed'],s['task'])==(u['env_seed'],u['policy_seed'],u['task'])
        u['runtime_source']=s
    else:u['runtime_source']=u['native_source_record']
    u['storage_key']=hashlib.sha256(u['unit_id'].encode()).hexdigest()
    u['cell_id']=f"{u['model']}_{u['method']}_H{u['H']}_L11"
    write(ROOT/'units'/(u['storage_key']+'.json'),u)
write(ROOT/'UNIT_INDEX.json',units)
shutil.copyfile(P/'config/BASE.json',ROOT/'config/BASE.json')
shutil.copyfile(X/'config/ENCODER_BASE.json',ROOT/'config/ENCODER_BASE.json')
shutil.copyfile(X/'config/ENGINE_CONFIG.json',ROOT/'config/X_ENGINE.json')
shutil.copyfile(X/'config/CONFIG.json',ROOT/'config/X_NATIVE.json')
pc=read(P/'config/CONFIG.json');e=assets['pi05']
pc.update(critic_assets=e['assets'],selected_model={'member_hashes':e['member_hashes'],'ensemble':e},loss='L11',fit_seed=9101)
write(ROOT/'config/PI_ENGINE.json',pc)
write(ROOT/'ASSETS.json',assets)
write(ROOT/'config/CONFIG.json',dict(task_id='C_D24_L11_RETEST_V1',stage_attempt_cap=2750,node_cumulative_attempt_cap=18750,planned_prior_attempts=14943,cutoff_unix=1790164800,wall_seconds=43200,model_workers=24,branches_per_worker=8,logical_concurrency=192,stages=[dict(model='X-VLA',method='Post',H=10),dict(model='pi05',method='Post',H=40),dict(model='X-VLA',method='Velocity',H=10),dict(model='pi05',method='Velocity',H=40),dict(model='pi05',method='Velocity',H=50)]))
write(ROOT/'METHOD_FROZEN.json',dict(task_id='C_D24_L11_RETEST_V1',loss='L11',fit_seed=9101,members=[1041,1042,1043,1044],only_scientific_change='already trained L11 Q in place of L01',X_protocol='Mesa80Hz/.01/raw30/K10/NFE10; dedicated X D2/G02/Q4 and frozen external features',pi05_protocol='NVIDIA EGL30Hz/400Hz/.015/raw50/NFE10; native H40/H50,C10 restore',gate_threshold=.05,monitor_interval=5,commitment=10,source_identity='exact owner=C NEW_UNITS_C.jsonl',old_results_immutable=True,Post_current_paper=True,Velocity_separate=True,revealed_source_retest=True,new_blind_test=False,training_updates=0,collection=0,scheduling='3 resident replicas per GPU,8 independent cooperative rollout contexts per replica,192 target active contexts; batch1 per-sample gradients',RNG_isolation='save/restore CPU torch,CUDA,Python,NumPy per context; pi05 natural torch.Generator per context; unchanged candidate seed namespace',model_replicas_per_GPU=3,logical_branches_per_GPU=24))
write(ROOT/'evidence/REUSED_SCIENTIFIC_CODE.json',dict(sources=[str(X/'code'),str(P/'code')],changes=['yield at physical step boundary','per-context environment/history/RNG/counters','source-keyed external feature contexts','new isolated unit claims and L11 assets'],no_retraining=True,no_extra_samples=True))
print(ROOT)
