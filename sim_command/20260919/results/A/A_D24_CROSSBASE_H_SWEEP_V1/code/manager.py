"""One host reservation, shared models, eight finite cells, real isolated environments."""
import argparse,os,signal,subprocess,time,traceback,secrets,hashlib
from pathlib import Path
import paths
from paths import ROOT,CONFIG,EVENT_PREFIX,TASK
from qio import read,new_json,atomic_json,utc,process_identity
from common import reservation_fds,runtime_command
from admission import authority,boundary,admissions_allowed,AdmissionStop,frozen_units,unit_hash,cell_id
from reservation import send_existing_fd,holder_exit_ack
from process_family import drain_group
from publication import publish,summarize

def main(chain):
    chain=Path(chain);authority();own=process_identity();fds=reservation_fds()
    if own['pid']!=own['pgid']:raise RuntimeError('formal group leader required')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(utc=utc(),process=own,single_reservation=True))
    base=read(ROOT/'config/BASE.json');native=read(ROOT/'config/SMOL_BASE.json');all_units=list(frozen_units().values())
    source_index=read(native['source_table'])['sources'];positions={x['source_id']:i for i,x in enumerate(source_index)}
    local=Path(CONFIG['local_dir']);auth=secrets.token_hex(16);servers=[];all_clients=[];phases=[];stopping=False;fatal=None;encoder_ready=False;peak=0;last_pub=0
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    def check():
        if stopping:raise AdmissionStop('owned manager stopping')
        boundary()
    def launch(script,cfg,server=False):
        out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=False)
        for name in ('tmp','cache','xdg'):(out/name).mkdir(mode=0o700)
        cp=out/'CONFIG.json';new_json(cp,cfg)
        runtime='mw-pi05-legacy' if script=='encoder_server.py' else 'mw-smolvla-lr044'
        argv=runtime_command(runtime,script,'--config',cp)
        env=dict(os.environ,CUDA_VISIBLE_DEVICES=base['device_list'][cfg['slot']]['gpu_uuid'],VLA_RENDERER='mesa',VLA_CPU_THREADS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',LP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(out/'tmp'),XDG_RUNTIME_DIR=str(out/'xdg'))
        # runtime.sh owns the accepted Mesa configuration; do not inherit A pi05 overrides.
        for key in ('LD_PRELOAD','__EGL_VENDOR_LIBRARY_FILENAMES','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH'):env.pop(key,None)
        with (out/'stdout.log').open('xb') as so,(out/'stderr.log').open('xb') as se:
            proc=subprocess.Popen(argv,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=so,stderr=se,pass_fds=fds,start_new_session=False)
        new_json(out/'PROCESS.json',process_identity(proc.pid));return dict(proc=proc,root=out,cfg=cfg,server=server)
    def model_wait(items):
        end=time.monotonic()+1200
        while not all((x['root']/'MODEL_READY.json').exists() for x in items):
            check()
            if any(x['proc'].poll() is not None for x in items):raise RuntimeError('model service exited while loading')
            atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),status='model_loading',models_ready=sum((x['root']/'MODEL_READY.json').exists() for x in servers),logical_target=192,holder_policy='all8_off_entire_wave'))
            if time.monotonic()>end:raise TimeoutError('model loading1200s')
            time.sleep(2)
    def snapshot(phase,clients):
        nonlocal peak,last_pub
        active={str(g):0 for g in range(8)};steps=0
        for x in clients:
            p=x['root']/'PROGRESS.json';v=read(p) if p.exists() else {}
            if x['proc'].poll() is None and v.get('active_environment'):active[str(x['cfg']['slot'])]+=1;steps+=v.get('step',0)
        peak=max(peak,sum(active.values()))
        hb=dict(utc=utc(),manager=own,status='formal_rollouts',phase=phase,active_environments=sum(active.values()),active_environments_by_GPU=active,peak_simultaneous_active_environments=peak,logical_target=192,loaded_workers=8,policy_replicas=8,external_encoder_replicas=8 if encoder_ready else 0,inference_batch_size=1,environment_state_shared=False,observed_environment_steps=steps,living_branch_processes=sum(x['proc'].poll() is None for x in clients),holder_policy='all8_off_entire_wave')
        atomic_json(chain/'HEARTBEAT.json',hb)
        if time.monotonic()-last_pub>45:publish();last_pub=time.monotonic()
        summary=read(ROOT/'SUMMARY.json') if (ROOT/'SUMMARY.json').exists() else {}
        if summary.get('valid_new',0)>0 and not (ROOT/'STABLE_HANDOFF.json').exists():
            new_json(ROOT/'STABLE_HANDOFF.json',dict(status='STABLE_HANDOFF',task_id=TASK,utc=utc(),manager=own,model_ready=8,valid_new=summary['valid_new'],actual_active_snapshot=sum(active.values()),peak_active=peak,logical_target=192,current_stage=phase,background_continues=True,no_LLM_gate=True,completion_event=str(ROOT/'outbox/chain_terminal.json'),callback_thread=CONFIG['thread_id'],environment_process_isolation=True))
            new_json(ROOT/'outbox/startup_progress.json',dict(event_id=EVENT_PREFIX+'_startup_progress',kind='startup_progress',synthetic=False,result=str(ROOT/'STABLE_HANDOFF.json'),utc=utc()))
    def finish_clients(items):
        # Normal cell barrier waits for useful clients; signals only on stop/deadline/error.
        for x in items:
            if x['proc'].poll() is None:x['proc'].terminate()
        end=time.monotonic()+30
        for x in items:
            try:x['proc'].wait(timeout=max(.1,end-time.monotonic()))
            except subprocess.TimeoutExpired:x['proc'].kill();x['proc'].wait()
            atomic_json(x['root']/'PROCESS_EXIT.json',dict(utc=utc(),exit_code=x['proc'].returncode,original_identity=read(x['root']/'PROCESS.json')))
    try:
        for g in range(8):
            cfg=dict(slot=g,ipc_auth=auth,output=str(chain/f'models/{g}'),socket_path=str(local/f'policy{g}.sock'),encoder_socket=str(local/f'encoder{g}.sock'))
            servers.append(launch('smol_server.py',cfg,True))
        model_wait(servers);new_json(ROOT/'MODELS_READY.json',dict(utc=utc(),policy_services=[read(x['root']/'MODEL_READY.json') for x in servers],source='actual model loader',Q_selection='Smol L11 fixed; encoder loads at first monitored cell'))
        for index,(method,H) in enumerate(CONFIG['stage_order']):
            check()
            if not admissions_allowed():break
            phase=f'{index+1:02d}_{method}_H{H}';pr=ROOT/'phases'/phase;pr.mkdir(parents=True,exist_ok=False)
            selected=[u for u in all_units if u['method']==method and u['H']==H and not (ROOT/'unit_claims'/(unit_hash(u)+'.json')).exists()]
            clients=[];error=None;start=time.monotonic()
            new_json(pr/'PHASE.json',dict(phase=phase,utc=utc(),method=method,H=H,planned=len(selected),raw_plan_length=50,commitment_C=10 if method!='N' else None))
            try:
                if method!='N' and not encoder_ready:
                    enc=[]
                    for g in range(8):
                        x=launch('encoder_server.py',dict(slot=g,ipc_auth=auth,output=str(chain/f'encoders/{g}'),socket_path=str(local/f'encoder{g}.sock')),True);servers.append(x);enc.append(x)
                    model_wait(enc);encoder_ready=True
                    new_json(ROOT/'ENCODERS_READY.json',dict(utc=utc(),identities=[read(x['root']/'MODEL_READY.json') for x in enc],Q_bindings=[read(x['root']/'Q_BINDING.json') for x in enc]))
                def client_cfg(g,lane):
                    shard=[u for u in selected if positions[u['source_id']]%8==g];lane_units=shard[lane::24];construction={}
                    for s in source_index[g::8]:construction.setdefault(s['task'],s['reset_seed'])
                    return dict(native,slot=g,lane=lane,phase='evaluate',stage=phase,branch_id=f'{phase}_{g}_{lane}',normal_H=H,output=str(pr/f'branch_{g}_{lane}'),socket_path=str(local/f'policy{g}.sock'),ipc_auth=auth,methods=[method],construction_seed_by_task=construction,units=lane_units)
                first=[]
                for g in range(8):
                    cfg=client_cfg(g,0)
                    if cfg['units']:x=launch('native_client.py',cfg);clients.append(x);first.append(x);all_clients.append(x)
                # Latch first planned progress once; never require different episodes to reach step5 simultaneously.
                observed=set();ramp=time.monotonic()+600;last=0
                while len(observed)<len(first):
                    check()
                    for x in first:
                        p=x['root']/'PROGRESS.json';v=read(p) if p.exists() else {}
                        if v.get('step',0)>=5 or v.get('status')=='complete':observed.add(str(x['root']))
                        if x['proc'].poll() not in (None,0):raise RuntimeError('first planned client failed '+str(x['root']))
                    if time.monotonic()-last>5:snapshot(phase,clients);last=time.monotonic()
                    if time.monotonic()>ramp:raise TimeoutError('first planned episode progress600s')
                    time.sleep(1)
                new_json(pr/'FIRST_PLANNED_PROGRESS.json',dict(utc=utc(),planned_branches=len(first),no_extra_preflight_episodes=True))
                for lane in range(1,24):
                    for g in range(8):
                        check();cfg=client_cfg(g,lane)
                        if cfg['units']:x=launch('native_client.py',cfg);clients.append(x);all_clients.append(x)
                last=0
                while any(x['proc'].poll() is None for x in clients):
                    check()
                    if any(x['proc'].poll() is not None for x in servers):raise RuntimeError('shared model server exited')
                    if time.monotonic()-last>5:snapshot(phase,clients);last=time.monotonic()
                    time.sleep(1)
            except BaseException as exc:
                error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
                new_json(pr/'FAILURE.json',dict(utc=utc(),error=error,science_outcome=None,no_blind_replay=True,analysis_deadline_unix=time.time()+1800))
            finally:
                finish_clients(clients);publish(force=True)
                item=dict(phase=phase,status='partial' if error or any(x['proc'].returncode for x in clients) else 'complete',error=error,utc=utc(),elapsed_seconds=time.monotonic()-start,client_count=len(clients),client_exit_codes=[x['proc'].returncode for x in clients])
                new_json(pr/'RESULT.json',item);phases.append(item);atomic_json(ROOT/'PHASE_RESULTS.json',phases)
            if any(x['proc'].poll() is not None for x in servers):raise RuntimeError('server fault requires private repair; retained incomplete units')
            if stopping:break
    except BaseException as exc:fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    finally:
        finish_clients(all_clients)
        for x in servers:atomic_json(x['root']/'STOP.json',dict(utc=utc(),reason='finite queue ended; all environment clients exited'))
        # Smol sockets disconnect from external encoders before encoders terminate.
        end=time.monotonic()+120
        for x in servers:
            try:x['proc'].wait(timeout=max(.1,end-time.monotonic()))
            except subprocess.TimeoutExpired:x['proc'].terminate()
        cleanup=drain_group(own['pgid'],own['pid'])
        for x in servers:x['proc'].wait()
        state=publish(force=True)
        if (ROOT/'SUMMARY.json').exists():new_json(ROOT/'COMPUTE_SUMMARY.json',read(ROOT/'SUMMARY.json'))
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,phases=phases,cleanup=cleanup,all_owned_processes_exited=cleanup.get('status')=='all_formal_group_members_exited',clients=[dict(path=str(x['root']),exit_code=x['proc'].returncode) for x in all_clients],servers=[dict(path=str(x['root']),exit_code=x['proc'].returncode) for x in servers],publication=state))
    return 3 if fatal or any(p['status']!='complete' for p in phases) else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);raise SystemExit(main(p.parse_args().chain))
