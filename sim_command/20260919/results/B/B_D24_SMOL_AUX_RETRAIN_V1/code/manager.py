"""Finite collection -> data -> new heads -> evaluation under one reservation."""
import argparse
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import traceback
import paths
from paths import ROOT,CAMPAIGN
from qio import read,new_json,atomic_json,utc,process_identity,ref,sha,optional_snapshot
from common import LOCAL,reservation_fds,runtime_command,boundary
from admission import authority
from reservation import send_existing_fd,holder_exit_ack
from process_family import drain_group

def main(chain):
    chain=Path(chain);authority();own=process_identity();fds=reservation_fds()
    if own['pgid']!=own['pid']:raise RuntimeError('manager must own lifecycle process group')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,at_utc=utc(),single_reservation=True))
    stopping=False;fatal=None;phase='setup';phase_results=[]
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)
    def run_jobs(label,specs):
        nonlocal phase
        phase=label;processes=[];last=0
        for spec in specs:
            boundary(admission=True)
            if stopping:raise RuntimeError('manager stop before next job')
            new_json(ROOT/'claims/jobs'/(spec['id']+'.json'),dict(job_id=spec['id'],phase=label,slot=spec.get('slot'),
                command=spec['argv'],at_utc=utc(),owner=own))
            work=LOCAL/spec['id'];work.mkdir(parents=True,exist_ok=False);os.chmod(work,0o700)
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',VLA_RENDERER='mesa',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',TMPDIR=str(work),XDG_RUNTIME_DIR=str(work))
            if spec.get('slot') is not None:env['CUDA_VISIBLE_DEVICES']=str(spec['slot'])
            logfile=chain/(spec['id']+'.log')
            with logfile.open('xb') as log:
                proc=subprocess.Popen(spec['argv'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                    env=env,pass_fds=fds,start_new_session=False)
            new_json(chain/(spec['id']+'_PROCESS.json'),dict(process=process_identity(proc.pid),spec=spec,at_utc=utc()))
            processes.append((proc,spec))
        while any(p.poll() is None for p,s in processes):
            boundary()
            if stopping:raise RuntimeError('owned manager stopping')
            failures=[(p.returncode,s['id']) for p,s in processes if p.poll() not in (None,0)]
            if failures:raise RuntimeError('stage job failed: '+repr(failures))
            if time.monotonic()-last>=5:
                ready=[];progress={}
                for proc,spec in processes:
                    folder=Path(spec['output']);r=folder/'MODEL_READY.json'
                    if r.exists() and proc.poll() is None:ready.append(read(r))
                    progress[spec['id']]=optional_snapshot(folder/('PROGRESS.json' if label in ['collect','evaluate'] else 'PROGRESS.json'))
                atomic_json(chain/'HEARTBEAT.json',dict(at_utc=utc(),utc=utc(),manager=own,status='running',phase=phase,
                    living_workers=sum(p.poll() is None for p,s in processes),loaded_workers=len(ready),ready_workers=ready,
                    jobs={s['id']:dict(pid=p.pid,exit_code=p.poll(),slot=s.get('slot')) for p,s in processes},progress=progress,
                    holder_policy='all8off through the entire collection/training/evaluation family'))
                last=time.monotonic()
            time.sleep(1)
        results=[dict(job_id=s['id'],exit_code=p.wait()) for p,s in processes]
        new_json(chain/(label+'_RESULT.json'),dict(at_utc=utc(),jobs=results))
        phase_results.append(dict(phase=label,jobs=results))
        if any(x['exit_code'] for x in results):raise RuntimeError('failed '+label)
    def gpu_specs(phase,rows,methods=None):
        specs=[];base=read(ROOT/'config/BASE.json')
        for slot in range(8):
            ident=phase+'_'+str(slot);output=ROOT/'runs'/ident;config=ROOT/'jobs'/(ident+'.json')
            cfg=dict(base,phase=phase,slot=slot,output=str(output),socket_path=str(LOCAL/(ident+'.sock')),
                ipc_auth='ef78c986d6c242818caf193562f46351')
            if phase=='collect':cfg['parents']=rows[slot::8]
            else:cfg.update(sources=rows[slot::8],methods=methods)
            new_json(config,cfg)
            specs.append(dict(id=ident,slot=slot,output=str(output),argv=['/usr/bin/python','-B',str(ROOT/'code/gpu_job.py'),'--config',str(config)]))
        return specs
    def fit_specs(kinds):
        return [dict(id=kind+'_'+str(seed),slot=slot,output=str(ROOT/'fits'/(kind+'_'+str(seed))),
            argv=runtime_command('mw-pi05-legacy','train_head.py','--kind',kind,'--seed',seed)) for kind,seed,slot in kinds]
    try:
        frozen=read(ROOT/'METHOD_FROZEN.json')
        if sha(ROOT/'SOURCE_MANIFEST.json')!=frozen['source_manifest']['sha256']:raise RuntimeError('frozen source manifest changed')
        sources=read(ROOT/'SOURCE_MANIFEST.json')['parents'];run_jobs('collect',gpu_specs('collect',sources))
        run_jobs('prepare_data',[dict(id='prepare_data',slot=None,output=str(ROOT/'dataset'),argv=runtime_command('mw-pi05-legacy','prepare_data.py'))])
        data=read(ROOT/'DATA_SUMMARY.json');initial=[('D',1241,0),('D',1242,1)]
        if data['Q_ready']:initial += [('Q',19301+i,4+i) for i in range(4)]
        run_jobs('fit_D_Q',fit_specs(initial))
        if data['G0_ready']:run_jobs('fit_G0',fit_specs([('G0',1341,2),('G0',1342,3)]))
        fits=[read(p) for p in sorted((ROOT/'fits').glob('*/RESULT.json'))]
        if any(x['status']!='complete' or x['updates']!=4000 for x in fits):raise RuntimeError('incomplete fit')
        if sum(x['updates'] for x in fits)>32000:raise RuntimeError('update cap exceeded')
        if data['Q_ready']:
            selected=ROOT/'models/Q_selected';hashes={}
            for i,seed in enumerate(range(19301,19305)):
                p=selected/'models/refit'/('member_'+str(i))/'selected.pt';p.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/'fits'/('Q_'+str(seed))/'final.pt',p);hashes[str(i)]=sha(p)
            new_json(selected/'ranking.json',dict(horizon=10,model_hashes=hashes,selection='fixed4000 all four scratch members',base='SmolVLA',retraining='all7058parameters'))
            new_json(selected/'config.json',dict(training_source_manifest=ref(ROOT/'SOURCE_MANIFEST.json'),seed_group=list(range(19301,19305))))
        fit_summary=dict(status='complete' if data['G0_ready'] and data['Q_ready'] else 'scientific_gap',at_utc=utc(),fits=fits,
            total_updates=sum(x['updates'] for x in fits),update_cap=32000,D_ready=True,G0_ready=data['G0_ready'],Q_ready=data['Q_ready'],
            scientific_gaps=data['scientific_gaps'],fixed_final_checkpoint=True,base_updates=0,external_encoder_updates=0)
        atomic_json(ROOT/'FIT_SUMMARY.json',fit_summary)
        if data['G0_ready']:
            methods=['R']+(['Post','Velocity'] if data['Q_ready'] else [])
            test=read(CAMPAIGN/'work/B/B_D24_E8_POST_V1_r1/POST_SOURCES.json')['sources']
            run_jobs('evaluate',gpu_specs('evaluate',test,methods))
        else:
            new_json(ROOT/'EVALUATION_SCIENTIFIC_GAP.json',dict(at_utc=utc(),skipped=['R','Post','Velocity'],reasons=data['scientific_gaps'],forced_trigger=False))
    except BaseException as exc:
        fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    finally:
        cleanup=drain_group(own['pgid'],own['pid'])
        new_json(chain/'MANAGER_EXIT.json',dict(at_utc=utc(),fatal=fatal,phase=phase,phase_results=phase_results,cleanup=cleanup,all_owned_processes_exited=True))
    return 3 if fatal else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);sys.exit(main(p.parse_args().chain))
