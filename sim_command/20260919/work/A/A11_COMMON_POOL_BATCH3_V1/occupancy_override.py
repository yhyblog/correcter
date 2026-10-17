"""User-requested temporary idle GPU holders, separate from formal accounting.

Never touches the formal reservation or frozen launcher. Reads saved scheduling
and existing guard status; terminates only its own Popen process groups.
"""
from pathlib import Path
import datetime, hashlib, json, os, signal, subprocess, time

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
B = ROOT/'Corrector/sim_command/20260919'
W = B/'work/A/A11_COMMON_POOL_BATCH3_V1'
E = W/'OCCUPANCY_OVERRIDE'
R = json.loads((W/'authorization/P11_A_COMMON_POOL_BATCH3_V1.json').read_text())
RUN = Path(R['paths']['output'])
GUARD = Path('/tmp/gpu_occupancy_guard/status.json')
owned = {}
last_external = {}
running = True

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def event(name, **kw):
    with (E/'EVENTS.jsonl').open('a') as f:
        f.write(json.dumps(dict(at_utc=now(), event=name, **kw))+'\n')
def read(p):
    try: return json.loads(p.read_text())
    except (OSError, ValueError): return None
def whole_wave_exit():
    return any((RUN/p).exists() for p in ['reserved/PROCESS_GROUP_EXIT.json',
        'reserved/WAVE_EXIT.json','launcher/LAUNCH_RESULT.json']) or (B/'results/A/A11_COMMON_POOL_BATCH3_V1/OUTER_EXIT.json').exists()
def eligible(parent):
    reserved = Path(parent['paths']['output'])/'reserved'
    starts = list(reserved.glob('*_START.json'))
    exits = list(reserved.glob('*_EXIT.json'))
    if not starts: return True, 'not_yet_admitted_yield_on_first_START'
    if len(starts)==15 and len(exits)==15 and all((read(p) or {}).get('cleanup_complete') is True for p in exits):
        return True, 'all15_cold_branches_exited_and_cleanup_recorded'
    return False, 'formal_parent_active_or_pending_branches'
def stop_many(indices, reason):
    targets = [(i,owned[i]) for i in indices if i in owned]
    for i,p in targets:
        if p.poll() is None:
            assert os.getpgid(p.pid)==p.pid
            os.killpg(p.pid, signal.SIGTERM)
            event('own_holder_TERM', gpu_index=i, manager_pid=p.pid, reason=reason)
    until = time.monotonic()+6
    while any(p.poll() is None for _,p in targets) and time.monotonic()<until:
        time.sleep(.1)
    for i,p in targets:
        if p.poll() is None:
            assert os.getpgid(p.pid)==p.pid
            os.killpg(p.pid, signal.SIGKILL)
            event('own_holder_KILL_after_grace', gpu_index=i, manager_pid=p.pid, reason=reason)
        p.wait()
        event('own_holder_exited', gpu_index=i, manager_pid=p.pid, returncode=p.returncode, reason=reason)
        owned.pop(i, None)
def halt(*_):
    global running
    running = False

def main():
    E.mkdir(exist_ok=True)
    with (E/'SUPERVISOR_STARTED.json').open('x') as f:
        json.dump(dict(at_utc=now(),pid=os.getpid(),pgid=os.getpgrp(),user_override='2026-09-21 use all8 GPUs; keep idle GPU holders to prevent server reclamation',formal_concurrency_changed=False,formal_lock_touched=False,shared_guard_modified=False,target_duty_cycle=.95,holder_path=str(ROOT/'gpu_hold.py'),holder_sha256=hashlib.sha256((ROOT/'gpu_hold.py').read_bytes()).hexdigest()), f,indent=2)
    signal.signal(signal.SIGTERM,halt);signal.signal(signal.SIGINT,halt)
    error = None
    try:
        while running and not whole_wave_exit():
            status=read(GUARD)
            fresh=status is not None and 0<=time.time()-status.get('updated',0)<20
            wants={}
            for parent in R['parents']:
                i=str(parent['device']['gpu_index']);yes,why=eligible(parent)
                wants[i]=(yes and fresh,why,parent)
            stop_many([i for i in owned if not wants[i][0]], 'formal_START_or_guard_status_stale')
            for i,(yes,why,parent) in wants.items():
                if not yes:continue
                gpu=status.get('gpus',{}).get(i)
                if gpu is None:continue
                pids=gpu.get('pids',[])
                proc=owned.get(i)
                if proc is not None and proc.poll() is not None:
                    event('own_holder_unexpected_exit',gpu_index=i,returncode=proc.returncode)
                    owned.pop(i);proc=None
                if proc is not None and len(pids)>1:
                    stop_many([i], 'additional_compute_PID_observed_in_existing_guard_status')
                    continue
                if proc is None and not pids:
                    # Re-read admission immediately before starting a holder.
                    if whole_wave_exit() or not eligible(parent)[0]:continue
                    env=dict(os.environ,CUDA_VISIBLE_DEVICES=parent['device']['gpu_uuid'],CUDA_DEVICE_ORDER='PCI_BUS_ID',PYTHONDONTWRITEBYTECODE='1')
                    cmd=['/usr/bin/python','-B',str(ROOT/'gpu_hold.py'),'--devices','0','--size','8192','--dtype','bf16','--target-util','0.95','--period-seconds','0.20','--log-interval','60']
                    with (E/('GPU_'+i+'.log')).open('ab') as out:
                        proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,env=env)
                    owned[i]=proc
                    event('own_holder_started',gpu_index=i,gpu_uuid=parent['device']['gpu_uuid'],manager_pid=proc.pid,command=cmd,eligibility=why,existing_guard_status_updated=status['updated'])
            temporary=E/'STATUS.tmp'
            temporary.write_text(json.dumps(dict(at_utc=now(),pid=os.getpid(),holders={i:p.pid for i,p in owned.items()},formal_wave_complete=whole_wave_exit(),formal_concurrency=2),indent=2)+'\n')
            temporary.replace(E/'STATUS.json')
            time.sleep(.5)
    except BaseException as exc:
        import traceback
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        event('supervisor_error',**error)
    finally:
        stop_many(list(owned),'wave_exit_or_supervisor_exit_return_to_persistent_guard')
        with (E/'SUPERVISOR_EXIT.json').open('x') as f:
            json.dump(dict(at_utc=now(),pid=os.getpid(),whole_wave_exit_saved=whole_wave_exit(),own_holders_remaining=len(owned),error=error,formal_lock_touched=False,shared_guard_modified=False),f,indent=2)
    return 0 if error is None else 1

if __name__=='__main__': raise SystemExit(main())
