"""Prepare C-private recovery from exact authorization; CPU only."""
import collections,csv,hashlib,json,shutil,sys
from pathlib import Path
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=C/'results/C/C_D24_L11_RENDER_RECOVERY_V1'
OLD=C/'results/C/C_D24_L11_RETEST_V1'
BASE=OLD/'continuations/r5'
B=C/'results/B/B_D24_L11_RETEST_V1/recovery/pi05_r2'
sys.path.insert(0,str(BASE/'code'))
from qio import read,new_json,ref,utc
for name in ['code','xcode','config','units','claims/units','issues','evidence']:(R/name).mkdir(parents=True,exist_ok=True)
for sub in ['code','xcode']:
    for p in (BASE/sub).glob('*.py'):shutil.copy2(p,R/sub/p.name)
for f in ['pi_client.py','pi_server.py','mux.py','counts.py','controller.py','resident_egl.py']:
    shutil.copy2(B/'code'/f,R/'code'/f)
for p in (BASE/'config').glob('*.json'):shutil.copy2(p,R/'config'/p.name)
shutil.copy2(BASE/'ASSETS.json',R/'ASSETS.json')
grantpath=C/'deadline_20260924/L11_RECOVERY_V1/AUTHORIZATION.json'
grant=read(grantpath);sha=ref(grantpath)['sha256'];assert sha=='ca6f92258260815495a016d8c25eb079e9e0949a38a2c5ece6b836c2ef6d0ccc'
manifest=C/grant['nodes']['C']['units']['path'];assert ref(manifest)['sha256']==grant['nodes']['C']['units']['sha256']
units=[json.loads(l) for l in manifest.open()];oldunits={u['unit_id']:u for u in read(OLD/'UNIT_INDEX.json')}
oldrows={v['unit_id']:v for v in csv.DictReader((OLD/'task_summary/EPISODES.csv').open())}
protected=[key for key,v in oldrows.items() if v['disposition']=='valid']
assert len(units)==1764 and len(protected)==736 and {u['unit_id'] for u in units}==set(oldrows)-set(protected)
new_json(R/'PROTECTED_VALID_UNITS.json',dict(unit_ids=protected,count=736,source=ref(OLD/'task_summary/EPISODES.csv')))
lineage=[];unknown=[];prepared=[]
for frozen in units:
    uid=frozen['unit_id'];original=oldunits[uid]
    for field in ['model','source_id','task','env_seed','policy_seed','method','mode','H','owner','Q_loss','Q_fit_seed']:
        assert frozen[field]==original[field],(uid,field)
    assert uid not in protected and frozen['owner']=='C'
    u=dict(frozen,storage_key=original['storage_key'],cell_id=original['cell_id'],runtime_source=original['runtime_source'])
    histories=[]
    for root in [OLD]+[OLD/'continuations'/s for s in ['r2','r3','r4','r5']]:
        cp=root/'claims/units'/(u['storage_key']+'.json')
        if not cp.exists():continue
        rp=root/'evaluation'/u['method']/u['source_id']/'RESULT.json' if u['model']=='X-VLA' else root/'pi_evaluation'/u['cell_id']/u['source_id']/'RESULT.json'
        raw=read(rp) if rp.exists() else {}
        histories.append(dict(run=str(root),claim=ref(cp),result_path=str(rp),status=raw.get('status'),raw_success=raw.get('success')))
    u['prior_attempt_count']=len(histories);u['prior_disposition']=oldrows[uid]['disposition']
    assert histories and u['prior_disposition']!='valid'
    lineage.append(dict(unit_id=uid,prior_disposition=u['prior_disposition'],prior_attempts=histories))
    if u['prior_disposition']=='unknown_entered':
        p=Path(histories[-1]['result_path']);raw=read(p)
        # An interrupted prefix without a terminal outcome cannot establish a
        # completed episode; the old renderer's integrity is also unverified.
        unknown.append(dict(unit_id=uid,status=raw.get('status'),success=raw.get('success'),steps=raw.get('steps'),
                            existing_files=[q.name for q in p.parent.iterdir()],recoverable_from_saved_terminal=False,
                            reason='Saved interruption prefix, no legal terminal outcome; old render-integrity issue not repaired retroactively.'))
        assert raw.get('status')=='budget_truncated' and raw.get('success') is None
    prepared.append(u);new_json(R/'units'/(u['storage_key']+'.json'),u)
new_json(R/'UNIT_INDEX.json',prepared)
new_json(R/'ATTEMPT_LINEAGE.json',lineage)
new_json(R/'evidence/LOG_RECOVERY_REVIEW.json',dict(utc=utc(),unknown_reviewed=len(unknown),rows=unknown,
         recovered_valid=0,all_existing_accepted_excluded=True,raw_status_complete_does_not_override_analysis_quality_disposition=True))
engine=read(R/'config/PI_ENGINE.json')
cfg=dict(task_id='C_D24_L11_RENDER_RECOVERY_V1',run_id='D24_C_L11_RENDER_RECOVERY_r1',grant_sha256=sha,
         stage_attempt_cap=2000,node_cumulative_attempt_cap=20750,planned_prior_attempts=17693,planned_recovery_units=1764,
         cutoff_unix=1790164800,absolute_wall_deadline_unix=1790175600,wall_seconds=43200,local_dir='/tmp/corrector_C_L11_RENDER_RECOVERY_r1',
         seed_namespace=engine['seed_namespace'],model_workers=24,branches_per_worker=8,logical_concurrency=192,
         stages=[dict(model='X-VLA',method='Post',H=10),dict(model='pi05',method='Post'),dict(model='pi05',method='Velocity')])
(R/'config/CONFIG.json').write_text(json.dumps(cfg,indent=2)+'\n')
new_json(R/'REPAIR.json',dict(utc=utc(),authorization=ref(grantpath),manifest=ref(manifest),prior_quality_diagnostic=ref(OLD/'event_audits/C_4834113fcd0b6f4d5d6f6ba9fff7b341/PREINTERVENTION_DIAGNOSTIC.json'),
          engineering_defect='Concurrent pi05 environments shared one EGL context; per-viewer framebuffer state was not restored before drawing. Pre-Q G0 divergence is confirmed, exact GL causal chain is not runtime-proven.',
          pi05_repair='Use proven B process-isolated environment/controller with serialized shared model RPC. Each branch owns its EGL/MjrContext, physics, history and action queue. Restore owning framebuffer before render; no concurrent viewer sharing.',
          pi05_proven_implementation=ref(B/'RESULT.json'),
          X_repair='Reuse r3/r5 verified native per-environment GL binding and MjrContext-before-GL destruction; preserve isolated global RNG and branch state.',
          X_validation=ref(OLD/'event_audits/C_4834113fcd0b6f4d5d6f6ba9fff7b341/R5_EXISTING_RESULT_AUDIT.json'),
          protected_valid=736,planned_recovery=1764,new_training_updates=0,new_collection=0,new_unique_scientific_units=0,
          first_planned_episode_validation=True,extra_GPU_preflight=False,weights_or_science_changed=False,
          observation_evidence='Two actual frames (steps0/5) for first planned branch per GPU; source/process/renderer attribution and pre-Q G0 comparison to existing same-source L01 at step0/5. No full-state or all-frame audit.'))
new_json(R/'METHOD_FROZEN.json',dict(task_id=cfg['task_id'],loss='L11',fit_seed=9101,members=[1041,1042,1043,1044],
          prior_method=ref(BASE/'METHOD_FROZEN.json'),assets=ref(R/'ASSETS.json'),authorization=ref(grantpath),
          source_manifest=ref(manifest),old_raw_preserved=True,Post_current_paper=True,Velocity_separate=True,
          revealed_sources=True,independent_blind_test=False,threshold=.05,monitor_interval=5,C10=10,
          pi05_concurrency='8 model RPC servers,24 isolated environment processes/GPU,192 target;batch1',
          X_concurrency='24 native/encoder model pairs,8 isolated GL/environment contexts per pair,192 target;batch1',
          new_training_updates=0,new_collection=0,repair=ref(R/'REPAIR.json')))
print(json.dumps(dict(prepared=len(prepared),protected=len(protected),unknown_log_reviewed=len(unknown),cells=dict(collections.Counter(u['cell_id'] for u in prepared)))))
