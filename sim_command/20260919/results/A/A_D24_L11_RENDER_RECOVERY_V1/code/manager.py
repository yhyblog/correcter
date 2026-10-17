"""One formal reservation; 8 model services and up to 192 isolated render clients."""
import argparse,os,secrets,signal,subprocess,sys,time,traceback
from pathlib import Path
from paths import ROOT,TASK,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,admissions_allowed,before_cutoff,worker_environment,original_exit_verified,frozen_units,AdmissionClosed
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from publication import publish

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--chain',required=True);args=parser.parse_args();chain=Path(args.chain)
    authority();original_exit_verified();own=process_identity();fds=held_reservation_fds()
    if own['pid']!=own['pgid'] or len(fds)!=1:raise ValueError('single inherited formal reservation required')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(utc=utc(),process=own,single_reservation=True,rendering='one environment process/EGL context, model-only RPC'))
    base=read(ROOT/'config/BASE.json');units=list(frozen_units().values());local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    auth=secrets.token_hex(24);servers=[];clients=[];all_clients=[];phases=[];fatal=None;stopping=False;last_pub=0.;phase=None;peak=0
    def signal_stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,signal_stop)
    def check():
        if stopping or not before_cutoff():raise AdmissionClosed('owned finite manager stop')
        for server in servers:
            if server['proc'].poll() is not None:raise RuntimeError('shared model service exited before clients: '+str(server['root']))
        for client in clients:
            if client['proc'].poll() not in (None,0):raise RuntimeError('isolated client failed; stop affected family before any replay: '+str(client['root']))
    def launch(script,cfg,server=False):
        out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=False)
        for n in ('tmp','cache','xdg'):(out/n).mkdir(mode=0o700)
        cp=out/'CONFIG.json';new_json(cp,cfg)
        with (out/'stdout.log').open('xb') as so,(out/'stderr.log').open('xb') as se:
            p=subprocess.Popen([base['python'],'-B',str(ROOT/'code'/script),'--config',str(cp)],cwd=ROOT,env=worker_environment(base,out),stdin=subprocess.DEVNULL,stdout=so,stderr=se,pass_fds=fds,start_new_session=False)
        new_json(out/'PROCESS.json',process_identity(p.pid))
        return dict(proc=p,root=out,cfg=cfg,server=server)
    def snapshot(method,force=False):
        nonlocal peak,last_pub
        active={str(g):0 for g in range(8)};steps=0;ready=0
        for x in clients:
            if x['proc'].poll() is not None:continue
            ready+=int((x['root']/'MODEL_READY.json').exists());p=x['root']/'PROGRESS.json';pr=read(p) if p.exists() else {}
            if pr.get('active_environment'):
                active[str(x['cfg']['slot'])]+=1;steps+=int(pr.get('step',0))
        count=sum(active.values());peak=max(peak,count)
        beat=dict(utc=utc(),manager=own,status='formal_rollouts',phase=phase,stage=method,model='pi05',loaded_workers=sum(x['proc'].poll() is None and (x['root']/'MODEL_READY.json').exists() for x in servers),living_branch_processes=sum(x['proc'].poll() is None for x in clients),loaded_branches=ready,active_environments=count,active_environments_by_GPU=active,peak_simultaneous_active_environments=peak,observed_environment_steps=steps,model_replicas=8,model_replicas_per_GPU=1,inference_batch_size=1,logical_target=192,environment_state_shared=False,holder_policy='all8_off_entire_wave')
        atomic_json(chain/'HEARTBEAT.json',beat)
        if phase:atomic_json(ROOT/'phases'/phase/'CONCURRENCY.json',beat)
        if count==192 and not (ROOT/'CONCURRENCY_OBSERVED_192.json').exists():new_json(ROOT/'CONCURRENCY_OBSERVED_192.json',dict(beat,meaning='192 live isolated environment processes; model RPC serialized batch1, not192 simultaneous kernels'))
        if time.monotonic()-last_pub>60 or force:
            published=publish();last_pub=time.monotonic()
            if beat['loaded_workers']==8 and published.get('valid_new',0)>0 and not (ROOT/'STABLE_HANDOFF.json').exists():
                row=dict(utc=utc(),task_id=TASK,status='STABLE_HANDOFF',manager=own,valid_new=published['valid_new'],logical_target=192,actual_active_snapshot=count,peak_active=peak,model_ready=8,environment_process_isolation=True,current_stage=method,background_continues=True,completion_event=str(ROOT/'outbox/chain_terminal.json'),callback_thread='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',no_LLM_gate=True)
                new_json(ROOT/'STABLE_HANDOFF.json',row);new_json(ROOT/'outbox/startup_progress.json',dict(event_id=TASK+'_startup_progress',kind='startup_progress',synthetic=False,utc=utc(),result=str(ROOT/'STABLE_HANDOFF.json')))
        return beat
    try:
        if not admissions_allowed():raise AdmissionClosed('new recovery admission closed')
        for g in range(8):
            cfg=dict(slot=g,output=str(chain/'models'/str(g)),socket_path=str(local/f'model_{g}.sock'),ipc_auth=auth)
            servers.append(launch('pi_server.py',cfg,server=True))
        end=time.monotonic()+1200
        while not all((x['root']/'MODEL_READY.json').exists() for x in servers):
            check()
            atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),status='model_loading',manager=own,loaded_workers=sum((x['root']/'MODEL_READY.json').exists() for x in servers),logical_target=192,holder_policy='all8_off_entire_wave'))
            if time.monotonic()>end:raise TimeoutError('planned model load deadline')
            time.sleep(2)
        new_json(ROOT/'MODELS_READY.json',dict(utc=utc(),model_services=[str(x['root']/'MODEL_READY.json') for x in servers],count=8,model_replicas_per_GPU=1))
        for method in ('Post','Velocity'):
            check()
            if not admissions_allowed():break
            phase='01_Post' if method=='Post' else '02_Velocity';pr=ROOT/'phases'/phase;pr.mkdir(parents=True,exist_ok=False)
            selected=[u for u in units if u['method']==method];clients=[];started=time.monotonic();phase_error=None
            new_json(pr/'PHASE.json',dict(utc=utc(),phase=phase,method=method,planned=len(selected),clients_per_GPU=24,total_target=192))
            def client_cfg(g,lane):return dict(slot=g,lane=lane,phase=phase,branch_id=f'{phase}_{g}_{lane}',output=str(pr/f'branch_{g}_{lane}'),socket_path=str(local/f'model_{g}.sock'),ipc_auth=auth,units=selected[g*24+lane::192])
            for g in range(8):
                c=client_cfg(g,0)
                if c['units']:
                    x=launch('pi_client.py',c);clients.append(x);all_clients.append(x)
            # These are the first eight authorized recovery units, not additional probes.
            end=time.monotonic()+600
            while True:
                check();passed=[]
                for x in clients:
                    p=x['root']/'PROGRESS.json';v=read(p) if p.exists() else {}
                    passed.append(v.get('step',0)>=5 or v.get('status')=='complete')
                snapshot(method)
                if all(passed):break
                if time.monotonic()>end:raise TimeoutError('first planned recovery branch progress deadline')
                time.sleep(2)
            new_json(pr/'FIRST_PLANNED_PROGRESS.json',dict(utc=utc(),eight_actual_planned_clients=True,extra_episodes=0,passed_step5_or_terminal=True))
            for lane in range(1,24):
                for g in range(8):
                    check()
                    if not admissions_allowed():break
                    c=client_cfg(g,lane)
                    if c['units']:
                        x=launch('pi_client.py',c);clients.append(x);all_clients.append(x)
            last=0.
            while any(x['proc'].poll() is None for x in clients):
                check()
                if time.monotonic()-last>5:snapshot(method);last=time.monotonic()
                time.sleep(1)
            check();snapshot(method,force=True)
            item=dict(utc=utc(),phase=phase,status='complete',client_exit_codes=[x['proc'].wait() for x in clients],elapsed_seconds=time.monotonic()-started)
            new_json(pr/'RESULT.json',item);phases.append(item)
            if method=='Post':new_json(chain/'POST_STAGE_DRAINED.json',dict(utc=utc(),all_Post_clients_exited=True,priority='Post all exits before any Velocity environment'))
    except BaseException as exc:
        fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        new_json(chain/'FAILURE.json',dict(utc=utc(),phase=phase,fatal=fatal,unchanged_retry=False,science_success=None))
    finally:
        for x in all_clients:
            if x['proc'].poll() is None:x['proc'].terminate()
        end=time.monotonic()+30
        while any(x['proc'].poll() is None for x in all_clients) and time.monotonic()<end:time.sleep(.2)
        for x in all_clients:
            if x['proc'].poll() is None:x['proc'].kill()
            x['proc'].wait()
            if not (x['root']/'PROCESS_EXIT.json').exists():new_json(x['root']/'PROCESS_EXIT.json',dict(utc=utc(),exit_code=x['proc'].returncode))
        for x in servers:atomic_json(x['root']/'STOP.json',dict(utc=utc(),reason='all own environment clients exited'))
        end=time.monotonic()+120
        while any(x['proc'].poll() is None for x in servers) and time.monotonic()<end:time.sleep(.5)
        for x in servers:
            if x['proc'].poll() is None:x['proc'].terminate()
        cleanup=drain_group(own['pgid'],own['pid'])
        for x in servers:x['proc'].wait()
        publish(terminal=True);summary=read(ROOT/'SUMMARY.json') if (ROOT/'SUMMARY.json').exists() else None
        if summary:atomic_json(ROOT/'COMPUTE_SUMMARY.json',summary)
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,phases=phases,clients=[dict(path=str(x['root']),exit_code=x['proc'].returncode) for x in all_clients],servers=[dict(path=str(x['root']),exit_code=x['proc'].returncode) for x in servers],cleanup=cleanup,all_owned_processes_exited=cleanup['status']=='all_formal_group_members_exited',summary=summary))
    return 3 if fatal or any(x['proc'].returncode for x in all_clients+servers) else 0

if __name__=='__main__':sys.exit(main())
