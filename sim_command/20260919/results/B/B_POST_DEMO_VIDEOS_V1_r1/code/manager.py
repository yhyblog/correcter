"""One finite all-holder-off formal process family, shared models and fixed recording pairs."""
import argparse,os,signal,subprocess,time,traceback
from pathlib import Path
from collections import Counter
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from common import reservation_fds
from admission import authority,boundary,worker_environment,claim_unit,AdmissionStop
from reservation import send_existing_fd,holder_exit_ack
from process_family import drain_group
from demo_publication import publish_incremental

def main(chain):
 chain=Path(chain);authority();own=process_identity();fds=reservation_fds()
 if own['pid']!=own['pgid']:raise RuntimeError('lifecycle process group required')
 request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request));new_json(chain/'MANAGER_STARTED.json',dict(utc=utc(),process=own,single_reservation=True))
 base=read(ROOT/'config/BASE.json');units=sorted(read(ROOT/'SOURCE_INDEX.json')['units'],key=lambda u:(u['task_rank'],u['task']));local=Path(CONFIG['local_dir']);auth=os.urandom(16).hex()
 servers=[];clients=[];running=[];done={};dispositions={};stopping=False;fatal=None;max_active=0;last=0.;ramped=False
 def stop(*_):
  nonlocal stopping
  stopping=True
 for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)
 def check():
  if stopping:raise AdmissionStop('owned manager stopping')
  boundary()
 def launch(script,cfg):
  out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=False)
  for name in ('tmp','cache','xdg'):(out/name).mkdir(mode=0o700)
  path=out/'CONFIG.json';new_json(path,cfg)
  with (out/'stdout.log').open('xb') as so,(out/'stderr.log').open('xb') as se:
   proc=subprocess.Popen([base['python'],'-B',str(ROOT/'code'/script),'--config',str(path)],cwd=ROOT,env=worker_environment(base,out),stdin=subprocess.DEVNULL,stdout=so,stderr=se,pass_fds=fds)
  new_json(out/'PROCESS.json',process_identity(proc.pid));return dict(proc=proc,root=out,cfg=cfg)
 def spawn_pair(unit,g):
  boundary(True);claim_unit(unit)
  cfg=dict(slot=g,branch_id=unit['candidate_id'],unit=unit,output=str(ROOT/'pairs'/unit['candidate_id']),socket_path=str(local/f'pi_{g}.sock'),ipc_auth=auth)
  item=launch('pair_worker.py',cfg);clients.append(item);running.append(item)
 def update():
  nonlocal max_active
  active=Counter();steps=0
  for x in running:
   p=x['root']/'PROGRESS.json';v=read(p) if p.exists() else {}
   if v.get('active_environment'):active[str(x['cfg']['slot'])]+=1;steps+=v.get('step',0)
  max_active=max(max_active,sum(active.values()))
  h=dict(utc=utc(),status='formal_recording',phase='paired_capture',manager=own,living_pair_workers=len(running),completed_pairs=len(done),qualified_pairs=sum(r.get('qualified',False) for r in done.values()),model_servers_ready=sum((x['root']/'MODEL_READY.json').exists() for x in servers),active_environments_by_GPU=dict(active),active_environments=sum(active.values()),peak_active_environments=max_active,observed_environment_steps=steps,logical_branch_target=192,actual_pair_capacity=CONFIG['target_workers'],capacity_constraint='finite fixed candidates and two sequential arms per pair; bounded CPU encoding',holders='all8off_entire_formal_family')
  atomic_json(chain/'HEARTBEAT.json',h)
 try:
  for g in range(8):servers.append(launch('pi_server.py',dict(slot=g,ipc_auth=auth,phase='paired_capture',output=str(ROOT/'phases'/f'model_{g}'),socket_path=str(local/f'pi_{g}.sock'))))
  end=time.monotonic()+900
  while not all((x['root']/'MODEL_READY.json').exists() for x in servers):
   check()
   if any(x['proc'].poll() is not None for x in servers):raise RuntimeError('shared pi05 model load failed')
   if time.monotonic()>end:raise TimeoutError('model load deadline')
   update();time.sleep(2)
  for g,u in enumerate(units[:8]):spawn_pair(u,g)
  ramp_end=time.monotonic()+600
  while True:
   check()
   if any(x['proc'].poll() is not None for x in servers):raise RuntimeError('model server exited during recording')
   changed=False
   for x in list(running):
    if x['proc'].poll() is None:continue
    p=x['root']/'PAIR_RESULT.json'
    if not p.exists():new_json(p,dict(candidate_id=x['cfg']['unit']['candidate_id'],task=x['cfg']['unit']['task'],H=x['cfg']['unit']['H'],source_id=x['cfg']['unit']['source_id'],status='technical_failure',qualified=False,error='worker exited without terminal record',exit_code=x['proc'].returncode))
    row=read(p);done[row['candidate_id']]=row;running.remove(x);changed=True
   if not ramped:
    passed=[]
    for x in clients[:8]:
     p=x['root']/'PROGRESS.json';v=read(p) if p.exists() else {};passed.append(v.get('step',0)>=5 or x['cfg']['unit']['candidate_id'] in done)
    if any(done.get(x['cfg']['unit']['candidate_id'],{}).get('status')=='technical_failure' for x in clients[:8]):raise RuntimeError('first planned recording failed; no unchanged blind family retry')
    if all(passed):ramped=True;new_json(ROOT/'FIRST_PLANNED_PROGRESS.json',dict(utc=utc(),branches=8,no_extra_GPU_preflight=True,actual_recording_progress=True))
    elif time.monotonic()>ramp_end:raise TimeoutError('first planned recording progress deadline')
   if ramped:
    active_by_task=Counter(x['cfg']['unit']['task'] for x in running);qualified_by_task=Counter(r['task'] for r in done.values() if r.get('qualified'));started={x['cfg']['unit']['candidate_id'] for x in clients};per_gpu=Counter(x['cfg']['slot'] for x in running)
    for u in units:
     cid=u['candidate_id'];task=u['task']
     if cid in started or cid in dispositions:continue
     if qualified_by_task[task]>=3:dispositions[cid]=dict(status='not_needed',reason='three qualified fixed candidates already recorded');changed=True;continue
     if len(running)>=CONFIG['target_workers'] or active_by_task[task]+qualified_by_task[task]>=3:continue
     g=min(range(8),key=lambda i:per_gpu[i])
     if per_gpu[g]>=CONFIG['workers_per_gpu']:continue
     spawn_pair(u,g);started.add(cid);per_gpu[g]+=1;active_by_task[task]+=1
   if changed:
    atomic_json(ROOT/'DISPOSITIONS.json',dispositions);publish_incremental()
   if time.monotonic()-last>=5:update();last=time.monotonic()
   if ramped and not running:break
   time.sleep(1)
 except BaseException as exc:
  fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());new_json(ROOT/'MANAGER_FAILURE.json',dict(utc=utc(),fatal=fatal,blind_retry=False))
 finally:
  for x in running:
   if x['proc'].poll() is None:x['proc'].terminate()
  until=time.monotonic()+30
  for x in running:
   try:x['proc'].wait(timeout=max(.1,until-time.monotonic()))
   except subprocess.TimeoutExpired:x['proc'].kill();x['proc'].wait()
  for x in servers:atomic_json(x['root']/'STOP.json',dict(utc=utc(),reason='all recording and encoding branches exited'))
  until=time.monotonic()+45
  for x in servers:
   try:x['proc'].wait(timeout=max(.1,until-time.monotonic()))
   except subprocess.TimeoutExpired:x['proc'].terminate()
  cleanup=drain_group(own['pgid'],own['pid']);atomic_json(ROOT/'DISPOSITIONS.json',dispositions)
  new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,peak_active_environments=max_active,all_owned_processes_exited=cleanup.get('status')=='all_formal_group_members_exited'))
 return 3 if fatal or any(x['proc'].returncode for x in clients) else 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--chain',required=True);raise SystemExit(main(p.parse_args().chain))
