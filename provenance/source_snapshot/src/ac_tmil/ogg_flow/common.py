"""Immutable registration and counted simulator budget for flow mechanism study."""
from __future__ import annotations
import argparse
import fcntl
import json
import subprocess
import time
from pathlib import Path
from ac_tmil.ogg_research_v3.common import REPO,BASE,ROOT as V3,OGG,RG
from ac_tmil.ogg_research_v2.common import freeze,read,dump,save_arrays,seed_for,file_sha256

ROOT=REPO/'outputs/act_recap_ogg_flow_20260916'
DOC=REPO/'docs/ogg_flow_20260916'
METHODS=['replan','velocity_matched','direct_matched','post_matched','reverse_matched','random_matched','velocity_native','direct_native']
MATCHED=METHODS[1:6]

def verify_old():
    expected={}
    for name in ['provenance/final_source.json','audits/delivery.json','learning/audits/delivery.json']:
        p=V3/name;data=json.loads(p.read_text())
        expected[str(p)]=file_sha256(p)
        for key in ['old_files_verified','files']:
            for name,sha in data.get(key,{}).items():
                path=Path(name) if Path(name).is_absolute() else REPO/name
                assert file_sha256(path)==sha,str(path)
                expected[str(path)]=sha
    dependencies=json.loads((V3/'audits/frozen_dependencies.json').read_text())['files']
    for name,sha in dependencies.items():
        assert file_sha256(Path(name))==sha,name
    return dict(old_files=expected,dependencies=dependencies)

def reserve_branch(kind,identity):
    """Count every begun branch including incomplete/repeated preflight attempts."""
    folder=ROOT/'budget';folder.mkdir(parents=True,exist_ok=True)
    # The mounted workspace does not implement flock. All workers share this
    # host; keep the mutex local and the persistent ledger in the workspace.
    with Path('/tmp/act_recap_ogg_flow_20260916_budget.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=folder/'attempts.jsonl'
        count=sum(1 for _ in path.open()) if path.exists() else 0
        if count>=3000:raise RuntimeError('Hard 3000 branch budget reached')
        row=dict(number=count+1,kind=kind,identity=str(identity),unix=time.time())
        with path.open('a') as f:f.write(json.dumps(row)+'\n')
        return row

def prepare():
    if (ROOT/'config.json').exists():return read(ROOT/'config.json')
    tasks=sorted({c['task'] for c in read(V3/'config.json')['cases']})
    cases=[]
    for split,start,n in [('preflight',2026103900,5),('development',2026104000,30)]:
        for i in range(n):
            seed=start+i;task=tasks[i%5]
            cases.append(dict(case_id=f'{task}__{seed}',task=task,env_seed=seed,split=split,source_horizon=50,cut_steps=[]))
    pattern=r'(?:__|"(?:env_seed|seed)"\s*:\s*)(?:202610390[0-4]|20261040[0-2][0-9])(?:[^0-9]|$)'
    scan=subprocess.run([RG,'-n','--glob','*.json',pattern,str(REPO/'outputs')],capture_output=True,text=True)
    assert scan.returncode in (0,1) and not scan.stdout,(scan.stdout+scan.stderr)[:1000]
    prior=verify_old()
    cfg=dict(experiment='frozen_v3_flow_mechanism',created_unix=time.time(),cases=cases,methods=METHODS,
        prefix_steps=10,replicates=8,preflight_replicates=2,control_budget=300,
        source='first frozen G0 alarm threshold .05, same v3 observation path, source horizon50',
        no_alarm='retain all 30 planned sources with common observed outcome for every arm',
        objective='mean member sigmoid probability(candidate; fixed state,a0) minus probability(a0; fixed state,a0)',
        anchor='slot0 always detached specified a0; only slot1 candidate differentiable',
        guidance=dict(alpha=10.,times=[.3,.2,.1],clip_derivative='true clamp through same T',
            velocity='v-alpha*tau*grad_u R(T(u))',direct='v-alpha*grad_u R(T(u))',
            clean='u=x_tau-tau*v; sampler Euler dt=-.1',no_step_backtracking=True),
        matching=dict(xyz_rms=.05,gripper_rms=.10,xyz_linf=.15,gripper_linf=.4,
            boundary_clearance=.05,tolerance=1e-6,zero_threshold=1e-10,
            algorithm='shared mask:1-abs(a0)>=.05; normalize each group direction to unit RMS; common radius=min(target, all direction feasible radii); bounds=min(group cap,1-abs(a0)); final float32 check',
            amplitude_can_expand_native=True,native_arms_separately_executed=True,
            post_metric='environment grad times ((q99-q01)/2)^2, matching internal clean-action Euclidean gradient',
            random='independent Gaussian three knots per action dimension, linear interpolation over ten steps',
            reverse='negative of projected direct command delta',
            zero_group='if any primary direction has zero norm, all matched arms use zero for that group; never drop source'),
        fallbacks='nonfinite guidance: same-seed a0 via inherited Engine; matching retains source and zero group; report all fallback counts',
        candidate_seed_namespace='ogg_flow_replan',suffix_seed_namespace='ogg_flow_suffix',random_seed_namespace='ogg_flow_random',
        branch_order_seed_namespace='ogg_flow_branch_order',suffix_pairing='source,cut,replicate,decision_index',
        continuation='execute ten prefix commands or terminate; clear queue; frozen fixed10 to total300',
        budget=dict(hard_maximum=3000,development_max=1920,preflight_max=80,concurrency_checks=32,source_captures=35,planned_total=2067,
            failed_attempts_count=True,remaining_is_failure_reserve_not_outcome_search=True),
        jacobian=dict(enabled=False,reason='focus fixed eight arms; no conditional addition based on development outcomes'),
        primary_comparisons=[['direct_matched','replan'],['direct_matched','velocity_matched'],['post_matched','replan'],['direct_matched','post_matched'],['direct_matched','reverse_matched'],['direct_matched','random_matched']],
        inference=dict(unit='complete source',bootstrap=10000,bootstrap_seed=29015,stratified_by='task',paired_suffixes=8,
            interpretation='development mechanism screening; nominal intervals, multiple methods not multiplicity corrected; no independent confirmation'),
        formal_freeze='separate formal_freeze.json after preflight commands audit and before any development source capture',
        sources_collision_checked=True,critic_ranking_sha256=file_sha256(V3/'learning/ranking.json'),
        guidance_brief_sha256=file_sha256(REPO/'ACT_RECAP_FLOW_GUIDANCE_EXECUTION_BRIEF_20260916.md'))
    freeze(ROOT/'config.json',cfg);freeze(ROOT/'provenance/previous.json',prior)
    return cfg

def implementation_hashes():
    paths=sorted((REPO/'src/ac_tmil/ogg_flow').glob('*.py'))+[REPO/'scripts/run_recap_ogg_flow.sh',
        REPO/'tests/test_ogg_flow_guidance.py',REPO/'tests/test_ogg_flow_matching.py',DOC/'method_review.md']
    return {str(p.relative_to(REPO)):file_sha256(p) for p in paths}

def formal_freeze():
    cfg=read(ROOT/'config.json');assert not (ROOT/'rollouts/development').exists()
    audit=json.loads((ROOT/'audits/preflight.json').read_text());assert audit['status']=='passed'
    inputs=[REPO/'ACT_RECAP_FLOW_GUIDANCE_PROTOCOL_20260916.md',ROOT/'audits/cpu_checks.json',
        REPO/'analysis/ogg_flow_checkpoint_check.py',REPO/'analysis/ogg_flow_20260916_legacy.py',
        *sorted(DOC.glob('*')),*sorted((ROOT/'implementation_amendments').rglob('*'))]
    value=dict(unix=time.time(),config_sha256=file_sha256(ROOT/'config.json'),code_hashes=implementation_hashes(),
        supporting_artifact_hashes={str(p.relative_to(REPO)):file_sha256(p) for p in inputs if p.is_file()},
        preflight_audit_sha256=file_sha256(ROOT/'audits/preflight.json'),
        development_sources_absent=not any((ROOT/'sources/single'/c['case_id']).exists() for c in cfg['cases'] if c['split']=='development'),
        preflight_outcomes_used_for_settings=False,settings_unchanged_from_preflight=True)
    assert value['development_sources_absent'];freeze(ROOT/'formal_freeze.json',value)
    dump(DOC/'parameters.json',dict(cfg,formal_freeze=value))

def launch(stage):
    cfg=read(ROOT/'config.json');workers=1 if stage=='preflight' else 4
    if stage=='development':read(ROOT/'formal_freeze.json')
    attempt=f'{stage}_{time.time_ns()}';execution=ROOT/'waves'/f'{attempt}_execution.json'
    hashes=implementation_hashes()
    if stage=='preflight':hashes={k:v for k,v in hashes.items() if not k.endswith(('evaluation.py','report.py'))}
    freeze(execution,dict(stage=stage,workers_per_gpu=workers,total_workers=8*workers,
        config_sha256=file_sha256(ROOT/'config.json'),code_hashes=hashes,
        worker_logs=str(ROOT/'logs'/attempt/'workers'),checks=str(ROOT/'checks'/attempt)))
    spec=ROOT/'waves'/f'{attempt}.json'
    jobs=[dict(devices=[i],command=['bash',str(REPO/'scripts/run_recap_ogg_flow.sh'),'collection','--rank',str(i),'--execution',str(execution)]) for i in range(8)]
    dump(spec,dict(jobs=jobs,hold_idle=False,log_root=str(ROOT/'logs'/attempt)))
    print(spec,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','freeze','launch']);p.add_argument('--stage',default='preflight');a=p.parse_args()
    {'prepare':prepare,'freeze':formal_freeze,'launch':lambda:launch(a.stage)}[a.action]()
