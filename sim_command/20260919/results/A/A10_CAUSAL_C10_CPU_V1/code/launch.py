"""Future single A-only C10 command. Metadata/claim precede hardware access."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from core.contracts import CAMPAIGN,PACKAGE,ContractError,Meter,claim,load_authorization,read,reconcile,write_new
from core.handoff import require_handoff_environment
from core.identity import verify_device
from core.wave_timing import stamp,mark,run_forwarded,observe_restoration
from budget import numeric_caps,branch_caps,sum_units
from native.initialization import EXPECTED_CAPS,summarize_initialization
from native.graphics_contract import CAPS,reconcile as graphics_reconcile

def child_environment(cfg,cache,parent=None):
    env=dict(os.environ if parent is None else parent)
    if env.get('NVIDIA_VISIBLE_DEVICES')!=cfg['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:
        raise ContractError('Container physical visibility differs; do not rewrite it')
    require_handoff_environment(cfg,env);env.update(cfg['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=cfg['hf_home'],
        OMP_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',
        XDG_CACHE_HOME=str(cache/'xdg'),CUDA_CACHE_PATH=str(cache/'cuda'),TORCH_HOME=str(cache/'torch'),
        LD_LIBRARY_PATH=cfg['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',
        __EGL_VENDOR_LIBRARY_FILENAMES=cfg['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH']:env.pop(k,None)
    return env

def branch_evidence(out,branch):
    path=out/branch;n=reconcile(path/'numeric_events.jsonl',numeric_caps(branch))
    init_path=path/'initialization_events.jsonl';graphics_path=path/'graphics_events.jsonl'
    i=summarize_initialization([json.loads(x) for x in init_path.read_text().splitlines()],EXPECTED_CAPS) if init_path.exists() else dict(entered_budget_usage=dict.fromkeys(EXPECTED_CAPS,0),returned_operation_units=dict.fromkeys(EXPECTED_CAPS,0),incomplete_event_ids=[],failed_events=0)
    g=graphics_reconcile(graphics_path) if graphics_path.exists() else dict(entered_budget_usage=dict.fromkeys(CAPS,0),incomplete=0,failed=0,returned=0)
    result=read(path/'BRANCH_RESULT.json') if (path/'BRANCH_RESULT.json').exists() else None
    ledger=read(path/'RESOURCE_LEDGER.json') if (path/'RESOURCE_LEDGER.json').exists() else None
    return dict(branch=branch,numeric=n,initialization=i,graphics=g,result=result,ledger=ledger,
        total_entered=sum_units(n['entered'],i['entered_budget_usage'],g['entered_budget_usage']))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);a=parser.parse_args()
    start=stamp();r,p=load_authorization(a.release,full=False)
    claim_path=claim(r)
    out=CAMPAIGN/'results/A/P10_CAUSAL_C10_V1_launcher_runs'/r['run_id'];out.mkdir(parents=True,exist_ok=False)
    mark(out,'launcher_started',claim=str(claim_path))
    write_new(out/'launch_identity.json',dict(release=r,proposal_sha256=p['_sha256'],claim=str(claim_path),started_at=start))
    meter=Meter(out/'launcher_events.jsonl',p['launcher_caps'])
    result=None;error=None;restoration=None;entered=False
    try:
        checked,p=load_authorization(a.release,full=True)
        if checked['_sha256']!=r['_sha256']:raise ContractError('Release changed after claim')
        cfg=read(p['config']['path']);write_new(out/'handoff_environment.json',require_handoff_environment(cfg,os.environ))
        rows=meter.call('pre_reservation_NVML_identity',lambda:verify_device({**r,**cfg['device']},cfg),{'native_nvml_identity_queries':1})
        write_new(out/'pre_reservation_device.json',dict(rows=rows,target=cfg['device']))
        guard=Path(cfg['occupancy_lifecycle']).with_name('gpu_occupancy_guard.py')
        subprocess.run(['/usr/bin/python',str(guard),'active'],check=True)
        cache=CAMPAIGN/'work/A/P10_CAUSAL_C10_V1_runtime_cache'/r['run_id'];cache.mkdir(parents=True,exist_ok=False)
        env=child_environment(cfg,cache)
        cmd=[cfg['occupancy_lifecycle'],'run','--',cfg['python'],'-B',str(PACKAGE/'code/reserved.py'),
             '--release',str(Path(a.release).resolve()),'--launch-directory',str(out)]
        mark(out,'lifecycle_requested');entered=True
        try:result=run_forwarded(cmd,cwd=PACKAGE/'code',env=env,new_session=True)
        finally:
            ended=mark(out,'lifecycle_returned',returncode=result)
            restoration=observe_restoration(ended['unix_seconds'],120)
            mark(out,'restoration_observed',status=restoration['status'])
    except BaseException as e:error=dict(type=type(e).__name__,message=str(e))
    finally:
        if not entered:restoration=dict(status='lifecycle_not_entered_holders_unchanged');mark(out,'preparation_failed',error=error)
        launch=reconcile(out/'launcher_events.jsonl',p['launcher_caps']);branches=[];reconciliation_errors=[]
        for branch in ['Post','Velocity']:
            try:branches.append(branch_evidence(out,branch))
            except Exception as e:reconciliation_errors.append(dict(branch=branch,type=type(e).__name__,message=str(e)))
        counts_complete=not reconciliation_errors and launch['counts_complete'] and all(x['numeric']['counts_complete'] for x in branches)
        total=sum_units(launch['entered'],*[x['total_entered'] for x in branches]) if counts_complete else None
        cleanup=read(out/'process_family_cleanup.json') if (out/'process_family_cleanup.json').exists() else None
        exits=read(out/'branch_process_exit.json') if (out/'branch_process_exit.json').exists() else None
        entered_branches=[x for x in branches if x['result'] is not None]
        success=(result==0 and error is None and counts_complete and bool(entered_branches)
            and all(x['ledger'] and x['ledger']['status']=='complete' for x in entered_branches)
            and restoration['status']=='occupancy_resolved' and cleanup is not None and cleanup['status']=='all_formal_group_members_exited')
        write_new(out/'LAUNCH_RESULT.json',dict(status='complete' if success else 'failed',returncode=result,error=error,
            release_consumed=True,claim=str(claim_path),remaining_caps_reusable=False,automatic_retry=False,
            launch_ledger=launch,branch_private_ledgers=branches,total_entered=total,counts_complete=counts_complete,reconciliation_errors=reconciliation_errors,
            completed_C10_branches=[x['branch'] for x in entered_branches if x['result']['restoration_coverage']],
            process_family_cleanup=cleanup,branch_process_exit=exits,restoration=restoration,
            timeouts=dict(handoff_nominal_seconds=300,per_branch_timed_child_seconds=1800,per_branch_kill_grace_seconds=30,
                sequential_children_max=2,nominal_child_total_max=3660,restoration_observation_seconds=120,end_to_end_strict_max=None),
            handoff_successful_raw_poll_count=None,handoff_poll_count_reason='Existing guard does not persist successful raw polling sequence; no supplemental probe',
            GPU_utilization_seconds=None,cost_scope='private finite integration; deployment Post1/Velocity2 unchanged; no success-rate sample'))
    return 0 if success else 3
if __name__=='__main__':sys.exit(main())
