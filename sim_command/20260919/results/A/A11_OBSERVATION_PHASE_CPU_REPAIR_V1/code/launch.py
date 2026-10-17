import inheritance
"""One future first-parent command. CPU preparation never calls main()."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
from authorization import load_authorization,claim,exclusive_record,quota_gate,gate
from core.contracts import PACKAGE,ContractError,read,Meter,reconcile,configure_store
from core.handoff import require_handoff_environment
from core.identity import verify_device
from core.wave_timing import observe_restoration
from core.failure_evidence import record_failure
from budget import PARENT,TIMEOUTS,STORAGE
from storage import Store
from execution import run
def child_environment(cfg,private_root):
    env=dict(os.environ)
    if env.get('NVIDIA_VISIBLE_DEVICES')!=cfg['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise ContractError('physical visibility changed')
    require_handoff_environment(cfg,env);env.update(cfg['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=cfg['hf_home'],
        OMP_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',
        XDG_CACHE_HOME=str(private_root/'cache'),TORCH_HOME=str(private_root/'cache'),
        TMPDIR=str(private_root/'temporary'),CUDA_CACHE_PATH=str(private_root/'cache/cuda'),
        TORCHINDUCTOR_CACHE_DIR=str(private_root/'cache/inductor'),TRITON_CACHE_DIR=str(private_root/'cache/triton'),LD_LIBRARY_PATH=cfg['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',
        __EGL_VENDOR_LIBRARY_FILENAMES=cfg['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for key in ('LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH'):env.pop(key,None)
    return env
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);a=parser.parse_args()
    # Files here are exclusively future identity paths, not this CPU task's paths.
    r,p=load_authorization(a.release,False)
    exclusive_record(p['paths']['command_record'],dict(started=time.time(),release_sha256=r['_sha256'],command_opportunity_consumed=True))
    claimed=claim(r,p);parent=Path(p['paths']['output']);parent.mkdir(parents=True,exist_ok=False)
    out=parent/'launcher';out.mkdir();store=Store(out,byte_limit=32*1024**2,record_limit=1024**2,file_limit=128);configure_store(store)
    monitor=None
    meter=Meter(out/'events.jsonl',PARENT);error=None;restoration=None;entered=False;returncode=None;phase='full_input_check';started=time.monotonic()
    def preparation_expired(sig,frame):raise TimeoutError('900s preparation deadline')
    old=signal.signal(signal.SIGALRM,preparation_expired);signal.alarm(TIMEOUTS['preparation_seconds'])
    try:
        checked,_=load_authorization(a.release,True)
        if checked['_sha256']!=r['_sha256']:raise ContractError('release changed after claim')
        phase='bounded_first_parent_admission';store.json('STORAGE_ADMISSION.json',quota_gate(r,p))
        cfg=read(p['config']['path']);store.json('HANDOFF_ENVIRONMENT.json',require_handoff_environment(cfg,os.environ))
        phase='NVML';rows=meter.call('pre_reservation_NVML_identity',lambda:verify_device({**r,**cfg['device']},cfg),PARENT)
        store.json('NVML_IDENTITY.json',dict(rows=rows,target=cfg['device']))
        phase='active_guard';subprocess.run(['/usr/bin/python',cfg['occupancy_handoff']['guard_path'],'active'],check=True,timeout=30)
        cache=Path(p['paths']['cache']);cache.mkdir(parents=True,exist_ok=False)
        (cache/'temporary').mkdir();(cache/'cache').mkdir()
        env=child_environment(cfg,cache)
        from storage_admission import PrivateMonitor
        monitor=PrivateMonitor(cache,STORAGE,store);monitor.check()
        signal.alarm(0);signal.signal(signal.SIGALRM,old)
        store.json('LIFECYCLE_REQUESTED.json',dict(time=time.time(),elapsed_preparation=time.monotonic()-started))
        entered=True;phase='lifecycle'
        returncode=run([cfg['occupancy_lifecycle'],'run','--',cfg['python'],'-B',str(PACKAGE/'code/reserved.py'),'--release',a.release],
            cwd=PACKAGE/'code',env=env,new_session=True,stdout=out/'lifecycle.stdout',stderr=out/'lifecycle.stderr',monitor=monitor)
    except BaseException as e:
        error=record_failure(e,branch=None,stage=phase,category='primary')
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,old)
        # Lifecycle only returns after the reserved group is gone. The inherited
        # guard also retains its own drain barrier; no release/reacquire here.
        if entered:
            try:restoration=observe_restoration(time.time(),TIMEOUTS['restoration_observation_seconds'])
            except BaseException as e:restoration=dict(status='observation_failed',error=record_failure(e,branch=None,stage='holder_restore',category='cleanup'))
        else:restoration=dict(status='lifecycle_not_entered_holders_unchanged')
        exits=read(parent/'reserved/WAVE_EXIT.json') if (parent/'reserved/WAVE_EXIT.json').exists() else None
        cleanup=read(parent/'reserved/PROCESS_GROUP_EXIT.json') if (parent/'reserved/PROCESS_GROUP_EXIT.json').exists() else None
        complete=returncode==0 and error is None and cleanup is not None and cleanup['status']=='all_formal_group_members_exited' and restoration['status']=='occupancy_resolved'
        store.json('LAUNCH_RESULT.json',dict(status='complete' if complete else 'failed',returncode=returncode,primary=error,
            claim=claimed,command_opportunity_consumed=True,release_consumed=True,unused_caps_reusable=False,
            actual_children=exits,process_group_exit=cleanup,restoration=restoration,launcher_ledger=reconcile(out/'events.jsonl',PARENT),
            storage_monitor=monitor.summary() if monitor else None,
            no_retry=True,coverage_must_be_read_per_attempt=True,timeouts=TIMEOUTS,elapsed_seconds=time.monotonic()-started,
            successful_handoff_raw_poll_count=None,handoff_missing_reason='existing guard retains no successful raw poll series; no additional probe'),emergency=True)
        from audit_indices import launcher_cost_index
        launcher_cost_index(store,synthetic=False)
    return 0 if complete else 3
if __name__=='__main__':sys.exit(main())
