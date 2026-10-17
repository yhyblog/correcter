"""One finite eight-worker evaluation wave; immutable explicit pending units."""
import argparse
import os
import signal
import subprocess
import time
import traceback
from pathlib import Path
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity,optional_snapshot
from common import LOCAL,reservation_fds,boundary
from admission import authority
from reservation import send_existing_fd,holder_exit_ack
from process_family import drain_group

def main(chain):
    chain=Path(chain);authority();own=process_identity();fds=reservation_fds()
    if own['pgid']!=own['pid']:raise RuntimeError('manager must own lifecycle process group')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0])
    new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,at_utc=utc(),single_reservation=True))
    stopping=False;fatal=None;processes=[];last=0
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)
    try:
        index=read(ROOT/'SOURCE_INDEX.json');all_sources=read(index['full_sources']['path'])['sources']
        pending={(x['method'],x['source_id']) for x in index['pending']};base=read(ROOT/'config/BASE.json')
        assert len(pending)==CONFIG['planned_current']
        concurrency=int(CONFIG.get('workers_per_gpu',1))
        if concurrency not in [1,2,3] or CONFIG.get('target_workers',8)!=8*concurrency:raise RuntimeError('unapproved worker concurrency')
        for slot in range(8):
            original_shard=all_sources[slot::8];construction={}
            for source in original_shard:construction.setdefault(source['task'],source['reset_seed'])
            for lane in range(concurrency):
                boundary(admission=True)
                if stopping:raise RuntimeError('manager stopped before next job')
                ident='evaluate_'+str(slot)+'_lane'+str(lane);output=ROOT/'runs'/ident;config=ROOT/'jobs'/(ident+'.json')
                lane_sources=original_shard[lane::concurrency]
                by_method={method:[source for source in lane_sources if (method,source['source_id']) in pending] for method in CONFIG['methods']}
                if not any(by_method.values()):continue
                cfg=dict(base,phase='evaluate',mode=CONFIG['mode'],slot=slot,lane=lane,workers_per_gpu=concurrency,output=str(output),
                    socket_path=str(LOCAL/(ident+'.sock')),ipc_auth='ef78c986d6c242818caf193562f46351',methods=CONFIG['methods'],
                    sources_by_method=by_method,construction_seed_by_task=construction,exact_original_shard_constructor_inputs=True)
                new_json(config,cfg)
                argv=['/usr/bin/python','-B',str(ROOT/'code/gpu_job.py'),'--config',str(config)]
                new_json(ROOT/'claims/jobs'/(ident+'.json'),dict(job_id=ident,phase='evaluate',slot=slot,lane=lane,command=argv,at_utc=utc(),owner=own))
                work=LOCAL/ident;work.mkdir(parents=True,exist_ok=False);os.chmod(work,0o700)
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',VLA_RENDERER='mesa',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',
                    TMPDIR=str(work),XDG_RUNTIME_DIR=str(work),CUDA_VISIBLE_DEVICES=CONFIG['gpu_uuid_by_slot'][str(slot)])
                with (chain/(ident+'.log')).open('xb') as log:
                    proc=subprocess.Popen(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,pass_fds=fds,start_new_session=False)
                new_json(chain/(ident+'_PROCESS.json'),dict(process=process_identity(proc.pid),slot=slot,lane=lane,job_id=ident,at_utc=utc()))
                processes.append((proc,ident,slot,output))
        while any(p.poll() is None for p,*_ in processes):
            boundary()
            if stopping:raise RuntimeError('owned manager stopping')
            failures=[(p.returncode,ident) for p,ident,*_ in processes if p.poll() not in (None,0)]
            if failures:raise RuntimeError('evaluation job failed: '+repr(failures))
            if time.monotonic()-last>=5:
                progress={};loaded=0
                for p,ident,slot,output in processes:
                    loaded+=int((output/'MODEL_READY.json').exists() and p.poll() is None)
                    progress[ident]=optional_snapshot(output/'PROGRESS.json')
                try:
                    atomic_json(chain/'HEARTBEAT.json',dict(at_utc=utc(),utc=utc(),manager=own,status='running',phase='evaluate',mode=CONFIG['mode'],
                        living_workers=sum(p.poll() is None for p,*_ in processes),loaded_workers=loaded,target_workers=CONFIG.get('target_workers',8),workers_per_gpu=concurrency,
                        jobs={ident:dict(pid=p.pid,slot=slot,exit_code=p.poll()) for p,ident,slot,_ in processes},progress=progress,
                        holder_policy='all8off throughout entire formal family'))
                except OSError as exc:print('TELEMETRY_PENDING',repr(exc),flush=True)
                last=time.monotonic()
            time.sleep(1)
        results=[dict(job_id=ident,exit_code=p.wait()) for p,ident,*_ in processes]
        new_json(chain/'evaluate_RESULT.json',dict(at_utc=utc(),jobs=results))
        if any(x['exit_code'] for x in results):raise RuntimeError('failed evaluation worker')
    except BaseException as exc:fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    finally:
        cleanup=drain_group(own['pgid'],own['pid'])
        new_json(chain/'MANAGER_EXIT.json',dict(at_utc=utc(),fatal=fatal,phase='evaluate',cleanup=cleanup,all_owned_processes_exited=True))
    return 3 if fatal else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);raise SystemExit(main(p.parse_args().chain))
