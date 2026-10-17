"""Single formal family, finite Post-first stages, 24 independent contexts/GPU."""
import argparse
import copy
import hashlib
import os
import signal
import subprocess
import time
import traceback
from pathlib import Path
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from common import reservation_fds,runtime_command
from admission import authority,boundary,worker_environment,AdmissionStop
from reservation import send_existing_fd,holder_exit_ack
from process_family import drain_group

def main(chain):
    chain=Path(chain);authority();own=process_identity();fds=reservation_fds()
    if own['pid']!=own['pgid']:raise RuntimeError('lifecycle process group required')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(utc=utc(),process=own,single_reservation=True))
    base=read(ROOT/'config/BASE.json');native=read(ROOT/'config/SMOL_BASE.json');units=read(ROOT/'SOURCE_INDEX.json')['units']
    local=Path(CONFIG['local_dir']);auth='819018e3731b093a735ed938bd4c64db';stopping=False;phases=[];fatal=None;blocked_models=set()
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)
    def check():
        if stopping:raise AdmissionStop('owned manager stop')
        boundary()
    def launch(script,cfg,pi=False,server=False):
        out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=False)
        for name in ('tmp','cache','xdg'):(out/name).mkdir(mode=0o700)
        path=out/'CONFIG.json';new_json(path,cfg)
        if pi:
            argv=[base['python'],'-B',str(ROOT/'code'/script),'--config',str(path)];env=worker_environment(base,out)
        else:
            runtime='mw-pi05-legacy' if script=='encoder_server.py' else 'mw-smolvla-lr044'
            argv=runtime_command(runtime,script,'--config',path)
            env=dict(os.environ,CUDA_VISIBLE_DEVICES=base['device_list'][cfg['slot']]['gpu_uuid'],VLA_RENDERER='mesa',VLA_CPU_THREADS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',LP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(out/'tmp'),XDG_RUNTIME_DIR=str(out/'xdg'))
        with (out/'stdout.log').open('xb') as so,(out/'stderr.log').open('xb') as se:
            proc=subprocess.Popen(argv,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=so,stderr=se,pass_fds=fds,start_new_session=False)
        new_json(out/'PROCESS.json',process_identity(proc.pid));return dict(proc=proc,root=out,cfg=cfg,server=server)
    def await_models(items):
        end=time.monotonic()+1200
        while not all((x['root']/'MODEL_READY.json').exists() for x in items):
            check()
            for x in items:
                if x['proc'].poll() is not None:raise RuntimeError('model service failed: '+str(x['root']))
            atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),status='model_loading',phase=phase,model_servers_ready=sum((x['root']/'MODEL_READY.json').exists() for x in items),target_logical_branches=192,holders='all8off_entire_formal_family'))
            if time.monotonic()>end:raise TimeoutError('model load deadline')
            time.sleep(2)
    try:
        for phase,model,method in [('01_pi05_Post','pi05','Post'),('02_Smol_Post','SmolVLA','Post'),('03_pi05_Velocity','pi05','Velocity'),('04_Smol_Velocity','SmolVLA','Velocity')]:
            check();boundary(True)
            selected=[u for u in units if u['model']==model and u['method']==method and not (ROOT/'unit_claims'/(hashlib.sha256(u['unit_id'].encode()).hexdigest()+'.json')).exists()]
            if model in blocked_models:
                phases.append(dict(phase=phase,status='deferred_same_unknown_failure',unstarted=len(selected)));continue
            phase_root=ROOT/'phases'/phase;phase_root.mkdir(exist_ok=False);servers=[];clients=[];error=None;started=time.monotonic();max_active={str(g):0 for g in range(8)};max_total=0
            new_json(phase_root/'PHASE.json',dict(phase=phase,model=model,method=method,planned=len(selected),utc=utc(),logical_branches_per_GPU_target=24))
            try:
                for g in range(8):
                    shared=dict(slot=g,ipc_auth=auth,phase=phase)
                    if model=='pi05':
                        cfg=dict(shared,output=str(phase_root/f'model_{g}'),socket_path=str(local/f'{phase}_{g}.sock'))
                        servers.append(launch('pi_server.py',cfg,pi=True,server=True))
                    else:
                        cfg=dict(shared,output=str(phase_root/f'encoder_{g}'),socket_path=str(local/f'{phase}_{g}_enc.sock'))
                        servers.append(launch('encoder_server.py',cfg,server=True))
                await_models(servers)
                if model=='SmolVLA':
                    for g in range(8):
                        cfg=dict(slot=g,ipc_auth=auth,phase=phase,output=str(phase_root/f'model_{g}'),socket_path=str(local/f'{phase}_{g}.sock'),encoder_socket=str(local/f'{phase}_{g}_enc.sock'))
                        servers.append(launch('smol_server.py',cfg,server=True))
                    await_models(servers)
                source_index=read(native['source_table'])['sources'] if model=='SmolVLA' else []
                source_positions={x['source_id']:i for i,x in enumerate(source_index)}
                def client_cfg(g,lane):
                    out=phase_root/f'branch_{g}_{lane}'
                    cfg=dict(slot=g,lane=lane,phase=phase,branch_id=f'{phase}_{g}_{lane}',output=str(out),socket_path=str(local/f'{phase}_{g}.sock'),ipc_auth=auth)
                    if model=='pi05':cfg['units']=selected[g*24+lane::192]
                    else:
                        shard=[u for u in selected if source_positions[u['source_id']]%8==g];lane_units=shard[lane::24];construction={}
                        for source in source_index[g::8]:construction.setdefault(source['task'],source['reset_seed'])
                        cfg=dict(native,**cfg);cfg.update(phase='evaluate',methods=[method],sources_by_method={method:[u['native_source_record'] for u in lane_units]},construction_seed_by_task=construction,units=lane_units)
                    return cfg
                # First eight are planned formal episodes, then fill the 192-context target.
                for g in range(8):clients.append(launch('pi_client.py' if model=='pi05' else 'native_client.py',client_cfg(g,0),pi=model=='pi05'))
                ramp_end=time.monotonic()+600
                while True:
                    check();passed=[]
                    for x in clients:
                        p=x['root']/'PROGRESS.json';progress=read(p) if p.exists() else {}
                        passed.append(progress.get('step',0)>=5 or progress.get('status')=='complete')
                        if x['proc'].poll() not in (None,0):raise RuntimeError('first planned rollout client failed: '+str(x['root']))
                    if all(passed):break
                    if time.monotonic()>ramp_end:raise TimeoutError('first planned branch progress deadline')
                    time.sleep(2)
                new_json(phase_root/'FIRST_PLANNED_PROGRESS.json',dict(utc=utc(),no_extra_preflight_episodes=True,first_active_branches=8,passed=True))
                for lane in range(1,24):
                    for g in range(8):
                        check();cfg=client_cfg(g,lane)
                        if cfg['units']:clients.append(launch('pi_client.py' if model=='pi05' else 'native_client.py',cfg,pi=model=='pi05'))
                last=0.
                while any(x['proc'].poll() is None for x in clients):
                    check()
                    if any(x['proc'].poll() is not None for x in servers):raise RuntimeError('shared server exited during phase')
                    if time.monotonic()-last>=5:
                        active={str(g):0 for g in range(8)};steps=0;ready=0
                        for x in clients:
                            ready+=int((x['root']/'MODEL_READY.json').exists() and x['proc'].poll() is None)
                            path=x['root']/'PROGRESS.json';progress=read(path) if path.exists() else {}
                            if x['proc'].poll() is None and progress.get('active_environment'):
                                active[str(x['cfg']['slot'])]+=1;steps+=progress.get('step',0)
                        for g,n in active.items():max_active[g]=max(max_active[g],n)
                        max_total=max(max_total,sum(active.values()))
                        heartbeat=dict(utc=utc(),manager=own,status='formal_rollouts',phase=phase,model=model,method=method,living_branch_processes=sum(x['proc'].poll() is None for x in clients),loaded_branches=ready,active_environments_by_GPU=active,active_environments=sum(active.values()),peak_simultaneous_active_environments=max_total,peak_active_by_GPU=max_active,observed_environment_steps=steps,model_replicas_per_GPU=1,external_encoder_replicas_per_GPU=1 if model=='SmolVLA' else 0,inference_batch_size=1,target_logical_branches=192,holders='all8off_entire_formal_family')
                        atomic_json(chain/'HEARTBEAT.json',heartbeat);atomic_json(phase_root/'CONCURRENCY.json',heartbeat);last=time.monotonic()
                    time.sleep(1)
            except BaseException as exc:
                error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());blocked_models.add(model)
                new_json(phase_root/'FAILURE.json',dict(utc=utc(),error=error,science_outcome=None,original_attempts_preserved=True,blind_retry=False))
            finally:
                for x in clients:
                    if x['proc'].poll() is None:x['proc'].terminate()
                for x in clients:
                    try:x['proc'].wait(timeout=30)
                    except subprocess.TimeoutExpired:x['proc'].kill();x['proc'].wait()
                for x in servers:atomic_json(x['root']/'STOP.json',dict(utc=utc(),reason='finite phase clients exited'))
                for x in reversed(servers):
                    try:x['proc'].wait(timeout=120)
                    except subprocess.TimeoutExpired:x['proc'].terminate();x['proc'].wait(timeout=30)
                status='partial' if error or any(x['proc'].returncode for x in clients+servers) else 'complete'
                item=dict(phase=phase,status=status,error=error,utc=utc(),elapsed_seconds=time.monotonic()-started,peak_simultaneous_active_environments=max_total,peak_active_by_GPU=max_active,client_exit_codes=[x['proc'].returncode for x in clients],server_exit_codes=[x['proc'].returncode for x in servers])
                new_json(phase_root/'RESULT.json',item);phases.append(item);atomic_json(ROOT/'PHASE_RESULTS.json',phases)
            if stopping:break
    except BaseException as exc:fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    finally:
        cleanup=drain_group(own['pgid'],own['pid']);new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,phases=phases,cleanup=cleanup,all_owned_processes_exited=cleanup.get('status')=='all_formal_group_members_exited'))
    return 3 if fatal or any(x['status']!='complete' for x in phases) else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);raise SystemExit(main(p.parse_args().chain))
