"""Future A-only PV release claim and all-holder lifecycle; no auto retry."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from core.contracts import CAMPAIGN, PACKAGE, ContractError, Meter, claim, load_authorization, read, reconcile, write_new
from core.handoff import require_handoff_environment
from core.identity import verify_device
from core.wave_timing import stamp,mark,run_forwarded,observe_restoration,timing_summary

def child_environment(cfg,cache,parent=None):
    env=dict(os.environ if parent is None else parent)
    if env.get('NVIDIA_VISIBLE_DEVICES')!=cfg['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:
        raise ContractError('Container physical visibility differs; do not rewrite it')
    require_handoff_environment(cfg,env)
    env.update(cfg['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=cfg['hf_home'],
        OMP_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',
        XDG_CACHE_HOME=str(cache/'xdg'),CUDA_CACHE_PATH=str(cache/'cuda'),TORCH_HOME=str(cache/'torch'),
        LD_LIBRARY_PATH=cfg['LD_LIBRARY_PATH'])
    for k in ['LD_PRELOAD','MUJOCO_GL','PYOPENGL_PLATFORM','__EGL_VENDOR_LIBRARY_FILENAMES','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH']:
        env.pop(k,None)
    return env

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);a=parser.parse_args()
    start=stamp();r,p=load_authorization(a.release,full=False)
    claim_path=claim(r)  # any claim consumes the release, even pre-load failure
    out=CAMPAIGN/'results/A/P10_PV_V3_launcher_runs'/r['run_id'];out.mkdir(parents=True,exist_ok=False)
    mark(out,'launcher_started',claim=str(claim_path))
    write_new(out/'launch_identity.json',dict(release=r,proposal_sha256=p['_sha256'],claim=str(claim_path),started_at=start))
    meter=Meter(out/'launcher_events.jsonl',p['launcher_caps'])
    result=None;error=None;restoration=None;entered=False
    try:
        checked,p=load_authorization(a.release,full=True)
        if checked['_sha256']!=r['_sha256']:raise ContractError('Release changed after claim')
        cfg=read(p['config']['path'])
        handoff=require_handoff_environment(cfg,os.environ)
        write_new(out/'handoff_environment.json',handoff)
        rows=meter.call('pre_reservation_NVML_identity',lambda:verify_device({**r,**cfg['device']},cfg),{'native_nvml_identity_queries':1})
        write_new(out/'pre_reservation_device.json',dict(rows=rows,target=cfg['device']))
        guard=Path(cfg['occupancy_lifecycle']).with_name('gpu_occupancy_guard.py')
        subprocess.run(['/usr/bin/python',str(guard),'active'],check=True)
        cache=CAMPAIGN/'work/A/P10_PV_V3_runtime_cache'/r['run_id'];cache.mkdir(parents=True,exist_ok=False)
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
        if not entered:
            restoration=dict(status='lifecycle_not_entered_holders_unchanged');mark(out,'preparation_failed',error=error)
        launch_ledger=reconcile(out/'launcher_events.jsonl',p['launcher_caps'])
        diagnostic_ledger=reconcile(out/'diagnostic/events.jsonl',p['diagnostic_caps'])
        total={k:launch_ledger['entered'].get(k,0)+diagnostic_ledger['entered'].get(k,0) for k in p['resource_caps']}
        returned={k:launch_ledger['returned'].get(k,0)+diagnostic_ledger['returned'].get(k,0) for k in p['resource_caps']}
        cleanup_path=out/'process_family_cleanup.json';cleanup=read(cleanup_path) if cleanup_path.exists() else None
        counts_complete=launch_ledger['counts_complete'] and diagnostic_ledger['counts_complete']
        success=result==0 and error is None and restoration['status']=='occupancy_resolved' and counts_complete and total==p['resource_caps'] and returned==total and cleanup is not None and cleanup['status']=='all_formal_group_members_exited'
        marks=[__import__('json').loads(x) for x in (out/'wave_timing.jsonl').read_text().splitlines()]
        timing=timing_summary(marks);timing['timeout_scope']='GNU timeout child: repeated complete SHA verification, imports, model loads, one-snapshot encoder/Post/Velocity and in-process cleanup; reservation wrapper also drains entire process group'
        write_new(out/'LAUNCH_RESULT.json',dict(status='complete' if success else 'failed',returncode=result,error=error,
            release_consumed=True,claim=str(claim_path),remaining_caps_reusable=False,automatic_retry=False,
            launch_ledger=launch_ledger,diagnostic_ledger=diagnostic_ledger,total_entered=total if counts_complete else None,total_returned=returned if counts_complete else None,
            known_entered_lower_bound=total,known_returned_lower_bound=returned,counts_complete=counts_complete,
            process_family_cleanup=cleanup,restoration=restoration,timing=timing,
            GPU_utilization_seconds=None,GPU_seconds_missing_reason='No device utilization integral; this is not a deployment cost comparison'))
    return 0 if success else 3

if __name__=='__main__':sys.exit(main())
