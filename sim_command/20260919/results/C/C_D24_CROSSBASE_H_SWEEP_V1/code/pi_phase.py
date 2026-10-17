"""B-proven per-environment process isolation, one shared model per physical GPU."""
import os,secrets,signal,subprocess,time,traceback
from pathlib import Path
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,admissions_allowed
from process_family import drain_group

def run(chain,stage_root,stage,units,base,fds,environment,stopping):
    own=process_identity();local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    servers=[];clients=[];peak=0;by_gpu={str(g):0 for g in range(8)};error=None;started=time.monotonic();last=0.
    def launch(script,cfg,server=False):
        out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=False)
        for name in ('tmp','cache','xdg'):(out/name).mkdir(mode=0o700)
        new_json(out/'CONFIG.json',cfg)
        argv=[base['python'],'-B',str(ROOT/'code'/script),'--config',str(out/'CONFIG.json')]
        with (out/'stdout.log').open('xb') as so,(out/'stderr.log').open('xb') as se:
            proc=subprocess.Popen(argv,cwd=ROOT,env=environment(base,out),stdin=subprocess.DEVNULL,stdout=so,stderr=se,pass_fds=fds,start_new_session=False)
        new_json(out/'PROCESS_STARTED.json',dict(utc=utc(),process=process_identity(proc.pid),argv=argv,GPU=base['device_list'][cfg['slot']],formal=True))
        return dict(proc=proc,root=out,cfg=cfg,server=server)
    def health():
        authority()
        if stopping() or time.time()>=CONFIG['absolute_wall_deadline_unix']:raise RuntimeError('owned finite phase stop/deadline')
        if any(x['proc'].poll() is not None for x in servers):raise RuntimeError('shared model server exited')
    def heartbeat(status='formal_rollouts'):
        nonlocal peak,last
        active={str(g):0 for g in range(8)};steps=0;ready=0
        for x in clients:
            living=x['proc'].poll() is None
            ready+=living and (x['root']/'MODEL_READY.json').exists()
            p=x['root']/'PROGRESS.json';r=read(p) if p.exists() else {}
            if living and r.get('active_environment'):
                active[str(x['cfg']['slot'])]+=1;steps+=r.get('step',0)
        for g,n in active.items():by_gpu[g]=max(by_gpu[g],n)
        peak=max(peak,sum(active.values()))
        h=dict(utc=utc(),status=status,stage=stage,stage_id=stage_root.name,living_workers=sum(x['proc'].poll() is None for x in clients),loaded_model_workers=sum(x['proc'].poll() is None and (x['root']/'MODEL_READY.json').exists() for x in servers),loaded_branches=ready,active_rollout_contexts=sum(active.values()),peak_active_rollout_contexts=peak,active_contexts_by_GPU=active,peak_contexts_by_GPU=by_gpu,physical_step_snapshot=steps,logical_target=192,model_workers_target=8,contexts_per_model_target=24,branch_batch_size=1,concurrency_kind='independent renderer/controller processes with serialized shared model RPC',holder_policy='all8_off_entire_formal_wave')
        atomic_json(chain/'HEARTBEAT.json',h);atomic_json(stage_root/'CONCURRENCY.json',h);last=time.monotonic()
    try:
        auth=secrets.token_hex(16);sockets={g:str(local/f'pi_{stage_root.name}_{g}.sock') for g in range(8)}
        for g in range(8):
            cfg=dict(slot=g,output=str(stage_root/f'model_{g}'),socket_path=sockets[g],ipc_auth=auth)
            servers.append(launch('pi_server.py',cfg,True))
        deadline=time.monotonic()+1200
        while not all((x['root']/'MODEL_READY.json').exists() for x in servers):
            health()
            if time.monotonic()>deadline:raise TimeoutError('model load deadline')
            if time.monotonic()-last>5:heartbeat('model_loading')
            time.sleep(1)
        def client_cfg(g,lane):
            return dict(slot=g,lane=lane,branch_id=f'{stage_root.name}_{g}_{lane}',output=str(stage_root/f'branch_{g}_{lane}'),socket_path=sockets[g],ipc_auth=auth,units=units[g*24+lane::192],observation_evidence=lane==0)
        # These first eight are exact planned recovery episodes, without extra
        # samples or model calls. Their observed pre-Q frames admit the other lanes.
        for g in range(8):clients.append(launch('pi_client.py',client_cfg(g,0)))
        deadline=time.monotonic()+900;validated=False
        while True:
            health();proofs=[]
            for x in clients:
                p=x['root']/'FIRST_PLANNED_OBSERVATION.json';proofs.append(read(p).get('passed') if p.exists() else False)
            if all(proofs):validated=True;break
            if not admissions_allowed('pi05') or any(x['proc'].poll() not in (None,0) for x in clients):
                error=dict(message='first planned recovery validation/technical fault; no unchanged retry');break
            if time.monotonic()>deadline:raise TimeoutError('first planned observation deadline')
            if time.monotonic()-last>5:heartbeat('first_planned_observation')
            time.sleep(1)
        new_json(stage_root/'FIRST_PLANNED_PROGRESS.json',dict(utc=utc(),passed=validated,first_active_branches=8,extra_scientific_units=0,proofs=[str(x['root']/'FIRST_PLANNED_OBSERVATION.json') for x in clients]))
        if validated:
            for lane in range(1,24):
                for g in range(8):
                    health()
                    if not admissions_allowed('pi05'):break
                    cfg=client_cfg(g,lane)
                    if cfg['units']:clients.append(launch('pi_client.py',cfg))
        while any(x['proc'].poll() is None for x in clients):
            health()
            if time.monotonic()-last>5:heartbeat()
            time.sleep(1)
    except BaseException as exc:error=dict(message=repr(exc),traceback=traceback.format_exc())
    finally:
        for x in clients:
            if x['proc'].poll() is None:x['proc'].terminate()
        for x in clients:
            try:x['proc'].wait(timeout=30)
            except subprocess.TimeoutExpired:x['proc'].kill();x['proc'].wait()
        for x in servers:atomic_json(x['root']/'STOP.json',dict(utc=utc(),reason='all finite clients exited'))
        for x in servers:
            try:x['proc'].wait(timeout=120)
            except subprocess.TimeoutExpired:
                x['proc'].terminate()
                try:x['proc'].wait(timeout=30)
                except subprocess.TimeoutExpired:x['proc'].kill();x['proc'].wait()
        cleanup=drain_group(own['pgid'],own['pid'])
    codes={x['root'].name:x['proc'].returncode for x in clients+servers}
    row=dict(utc=utc(),stage=stage,workers=codes,error=error,peak_live_rollout_contexts=peak,peak_contexts_by_GPU=by_gpu,cleanup=cleanup,elapsed_seconds=time.monotonic()-started)
    new_json(stage_root/'RESULT.json',row)
    if error or any(codes.values()):
        from faults import pause
        pause('pi05|stage',stage_root/'RESULT.json',error or 'owned worker technical failure')
    return row
