"""Finite local successor queue; waits for complete once output, then owns multi."""
import argparse
import fcntl
import os
import signal
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path
import paths
from paths import ROOT,CAMPAIGN,CONFIG,AUTH_SHA
from qio import read,new_json,atomic_json,utc,process_identity,same_process,ref,sha,optional_snapshot
from admission import release_valid

def control():
    c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json');grant=CAMPAIGN/CONFIG['grant']
    if sha(grant)!=AUTH_SHA or not release_valid(c,q,read(grant),CONFIG['task_id'],AUTH_SHA):raise RuntimeError('multi grant revoked, stopped, disabled, or absent')
    if socket.gethostname()!=c['roles']['B']['hostname']:raise RuntimeError('wrong local host')

def serve():
    local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    lock=(local/'queue.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    control();own=process_identity();proc=None;stopping=False;phase='waiting_once';fatal=None;terminal=None
    identity=dict(hostname=own['host'],boot_id=own['boot_id'],pid=own['pid'],start_ticks=own['start_ticks'],session_id=os.getsid(0))
    new_json(ROOT/'QUEUE_CLAIM.json',dict(task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],process=identity,
        authorization=ref(CAMPAIGN/CONFIG['grant']),source_index=ref(ROOT/'SOURCE_INDEX.json'),method=ref(ROOT/'METHOD_FROZEN.json'),
        formal_predecessor=CONFIG['predecessor_root'],scientific_launches_so_far=0,at_utc=utc()))
    manifest=dict(job_id=CONFIG['run_id'],task_id=CONFIG['task_id'],revision=1,run_id=CONFIG['run_id'],attempt=1,
        claim_identity=ref(ROOT/'QUEUE_CLAIM.json'),process_identity=identity,result_path=str(ROOT/'QUEUE_RESULT.json'),error_summary_path=str(ROOT/'queue.stderr.log'))
    new_json(ROOT/'WAKEUP_REGISTRATION.json',manifest)
    subprocess.run(['/usr/bin/python',str(CAMPAIGN/'work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py'),'register','--manifest',str(ROOT/'WAKEUP_REGISTRATION.json')],check=True)
    def stop(*_):
        nonlocal stopping
        stopping=True
        if proc and proc.poll() is None:proc.send_signal(signal.SIGTERM)
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    new_json(ROOT/'QUEUE_READY.json',dict(status='waiting_once',at_utc=utc(),process=own,terminal_trigger=ref(ROOT/'WAKEUP_REGISTRATION.json'),
        scientific_launches=0,predecessor=CONFIG['predecessor_root'],code=ref(ROOT/'PREP_CODE_MANIFEST.json'),A_waits_for_B=False))
    try:
        predecessor=Path(CONFIG['predecessor_root']);dead_since=None
        while True:
            control()
            if stopping:raise RuntimeError('owned queue stopped')
            if time.time()>=1790164800:raise RuntimeError('scientific admission deadline passed')
            result=optional_snapshot(predecessor/'RESULT.json')
            claim=read(predecessor/'CLAIM.json');p=claim['process'];alive=same_process(dict(p,host=p.get('hostname',p.get('host'))))
            if not alive and result.get('all_owned_descendants_exited'):
                if result.get('status')!='complete':raise RuntimeError('once predecessor terminal incomplete; preserve gap for original-thread handling')
                summary=read(predecessor/'FINAL_SUMMARY.json')
                if not all(c['valid']==500 for c in summary['cells']):raise RuntimeError('once valid coverage incomplete')
                break
            if not alive:
                dead_since=dead_since or time.monotonic()
                if time.monotonic()-dead_since>90:raise RuntimeError('once execution_unknown; no automatic scientific replay')
            else:dead_since=None
            try:atomic_json(ROOT/'QUEUE_HEARTBEAT.json',dict(status='waiting_once',at_utc=utc(),process=own,predecessor_alive=alive,predecessor=CONFIG['predecessor_root'],formal_started=False))
            except OSError as exc:print('QUEUE_TELEMETRY_PENDING',repr(exc),flush=True)
            time.sleep(10)
        if (ROOT/'CLAIM.json').exists() or (ROOT/'CHAIN_COMMAND.json').exists():raise RuntimeError('existing formal claim; do not duplicate')
        cfg=read(ROOT/'config/CONFIG.json');cfg.update(planned_prior_attempts=summary['cumulative_B_attempts'],original_prior_B_attempts=summary['cumulative_B_attempts'],
            prior_attempts_fixed=True,activation_finalized=True,absolute_wall_deadline_unix=min(time.time()+12*3600,1790164800),formal_activation_utc=utc())
        if cfg['planned_prior_attempts']+cfg['stage_attempt_cap']>20000:raise RuntimeError('node cumulative budget unavailable')
        atomic_json(ROOT/'config/CONFIG.json',cfg)
        new_json(ROOT/'ACTIVATION.json',dict(at_utc=utc(),actual_once_terminal=ref(predecessor/'RESULT.json'),actual_once_summary=ref(predecessor/'FINAL_SUMMARY.json'),
            config=ref(ROOT/'config/CONFIG.json'),new_training_updates=0,once_and_multi_separate=True))
        new_json(ROOT/'CODE_MANIFEST.json',dict(at_utc=utc(),preparation=ref(ROOT/'PREP_CODE_MANIFEST.json'),files=[ref(p) for p in sorted((ROOT/'code').glob('*.py'))]+[ref(p) for p in sorted((ROOT/'config').glob('*.json'))]))
        phase='formal_multi'
        with (ROOT/'formal.stdout.log').open('xb') as so,(ROOT/'formal.stderr.log').open('xb') as se:
            proc=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/service.py'),'serve'],cwd=ROOT,stdin=subprocess.DEVNULL,
                stdout=so,stderr=se,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),start_new_session=True)
        new_json(ROOT/'FORMAL_SERVICE_STARTED.json',dict(process=process_identity(proc.pid),at_utc=utc(),one_formal_launch=True))
        while proc.poll() is None:
            try:
                atomic_json(ROOT/'QUEUE_HEARTBEAT.json',dict(status=phase,at_utc=utc(),process=own,formal_process=process_identity(proc.pid),
                    progress=optional_snapshot(ROOT/'HEARTBEAT.json'),terminal_trigger=ref(ROOT/'WAKEUP_REGISTRATION.json')))
            except OSError as exc:print('QUEUE_TELEMETRY_PENDING',repr(exc),flush=True)
            if time.time()>=cfg['absolute_wall_deadline_unix'] and proc.poll() is None:proc.send_signal(signal.SIGTERM)
            time.sleep(10)
        terminal=read(ROOT/'RESULT.json')
    except BaseException as exc:fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    finally:
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            proc.wait()
        if terminal is None:
            terminal=dict(status='blocked' if phase=='waiting_once' else 'execution_unknown',exit_code=3,fatal=fatal,
                all_owned_descendants_exited=proc is None,publication_completed=False,occupancy_handoff_complete=proc is None,
                task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],scientific_task_complete=False)
            atomic_json(CAMPAIGN/CONFIG['result_receipt'],dict(terminal,at_utc=utc(),phase=phase,queue_result=str(ROOT/'QUEUE_RESULT.json')))
        atomic_json(ROOT/'QUEUE_RESULT.json',dict(terminal,queue_phase=phase,queue_error=fatal,at_utc=utc(),A_waits_for_B=False,
            scientific_task_complete=terminal['status']=='complete',formal_result=str(ROOT/'RESULT.json') if (ROOT/'RESULT.json').exists() else None))
    return 0 if terminal['status']=='complete' else 3

def start():
    control()
    ready=ROOT/'QUEUE_READY.json'
    if ready.exists() and same_process(read(ready)['process']):print('ALREADY_QUEUED');return 0
    if (ROOT/'QUEUE_CLAIM.json').exists() or (ROOT/'CLAIM.json').exists():raise RuntimeError('existing queue/formal claim; no implicit replay')
    with (ROOT/'queue.stdout.log').open('ab') as so,(ROOT/'queue.stderr.log').open('ab') as se:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/successor_queue.py'),'serve'],cwd=ROOT,stdin=subprocess.DEVNULL,
            stdout=so,stderr=se,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),start_new_session=True)
    print('QUEUE_SPAWNED_NOT_YET_READY',proc.pid);return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args();raise SystemExit(start() if a.action=='start' else serve())
