"""Eight GPU model servers with 24 active contexts each; global Post then V."""
import argparse,os,signal,subprocess,sys,time,traceback
from pathlib import Path
from paths import ROOT,TASK
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,admissions_allowed,before_cutoff,worker_environment,original_exit_verified
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from publication import publish

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--chain',required=True);args=parser.parse_args();chain=Path(args.chain)
 authority();own=process_identity();fds=held_reservation_fds()
 if own['pid']!=own['pgid'] or len(fds)!=1:raise ValueError('original single reservation required')
 request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
 original_exit_verified();new_json(chain/'MANAGER_STARTED.json',dict(utc=utc(),process=own,one_reservation=True))
 base=read(ROOT/'config/BASE.json');workers={};fatal=None;stopping=False;lastbeat=lastpub=0;stage='Post'
 def stop(*_):
  nonlocal stopping
  stopping=True
 for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
 try:
  if not admissions_allowed():raise ValueError('no new L11 admission')
  for slot in range(8):
   wr=chain/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
   for n in ['tmp','cache','xdg']:(wr/n).mkdir()
   with (wr/'stdout.log').open('xb') as so,(wr/'stderr.log').open('xb') as se:
    proc=subprocess.Popen([base['python'],'-B',str(ROOT/'code/cooperative_worker.py'),'--slot',str(slot),'--root',str(wr)],cwd=ROOT,env=worker_environment(base,wr),stdin=subprocess.DEVNULL,stdout=so,stderr=se,pass_fds=fds,start_new_session=False)
   workers[slot]=dict(proc=proc,root=wr,start=time.monotonic(),exit_recorded=False)
  while True:
   alive=0;loaded=0;active=0;peak_total=0;progress={}
   for slot,w in workers.items():
    proc,wr=w['proc'],w['root']
    if proc.poll() is not None:
     if not w['exit_recorded']:new_json(wr/'PROCESS_EXIT.json',dict(utc=utc(),exit_code=proc.returncode));w['exit_recorded']=True
     continue
    alive+=1
    if not before_cutoff():stopping=True
    if stopping:
     if not (wr/'STOP.json').exists():new_json(wr/'STOP.json',dict(utc=utc(),reason='bounded own drain'))
    if (wr/'MODEL_READY.json').exists():
     loaded+=1
     if not stopping and not (wr/(stage+'_GO.json')).exists():new_json(wr/(stage+'_GO.json'),dict(utc=utc(),method=stage))
    elif time.monotonic()-w['start']>1200:raise RuntimeError('planned model load timeout')
    if (wr/'PROGRESS.json').exists():
     pr=read(wr/'PROGRESS.json');progress[str(slot)]=pr;active+=pr['active_environments'];peak_total+=pr['peak_active_environments']
   if stage=='Post' and all((w['root']/'Post_DONE.json').exists() or w['proc'].poll() is not None for w in workers.values()):
    new_json(chain/'POST_STAGE_DRAINED.json',dict(utc=utc(),method='Post',workers=len(workers),priority_barrier='all live Post contexts drained before any Velocity entry'));publish();stage='Velocity'
   now=time.monotonic()
   if now-lastbeat>5:
    beat=dict(utc=utc(),manager=own,stage=stage,living_workers=alive,loaded_workers=loaded,model_replicas=loaded,logical_target=192,active_environments=active,sum_worker_peak_contexts=peak_total,batch_size=1,per_GPU={k:dict(active_environments=v['active_environments'],completed=v['completed'],control_iterations=v['control_iterations'],GPU_reserved_bytes=v['GPU_reserved_bytes']) for k,v in progress.items()},holder_policy='all8_off_entire_wave')
    atomic_json(chain/'HEARTBEAT.json',beat)
    if loaded==8 and sum(v['control_iterations'] for v in progress.values())>0 and not (ROOT/'MODEL_PROGRESS.json').exists():new_json(ROOT/'MODEL_PROGRESS.json',beat)
    if active==192 and not (ROOT/'CONCURRENCY_OBSERVED_192.json').exists():new_json(ROOT/'CONCURRENCY_OBSERVED_192.json',dict(beat,meaning='192 independent actual environments with control-step progress; one GPU execution thread/model per device, batch1; per-worker bounded snapshots, not192 simultaneous kernels'))
    lastbeat=now
   if now-lastpub>120:
    state=publish();lastpub=now
    if loaded==8 and state.get('valid_new',0)>0 and not (ROOT/'STABLE_HANDOFF.json').exists():
     row=dict(utc=utc(),status='STABLE_HANDOFF',task_id=TASK,manager=own,valid_new=state['valid_new'],logical_target=192,concurrency_observed=(ROOT/'CONCURRENCY_OBSERVED_192.json').exists(),current_stage=stage,background_continues=True,completion_event=str(ROOT/'outbox/chain_terminal.json'),callback_thread='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',no_LLM_gate=True)
     new_json(ROOT/'STABLE_HANDOFF.json',row);new_json(ROOT/'outbox/startup_progress.json',dict(event_id=TASK+'_startup_progress',kind='startup_progress',synthetic=False,utc=utc(),result=str(ROOT/'STABLE_HANDOFF.json')))
   if not alive:break
   time.sleep(1)
 except BaseException as e:fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
 finally:
  for w in workers.values():
   if w['proc'].poll() is None:w['proc'].send_signal(signal.SIGTERM)
  cleanup=drain_group(own['pgid'],own['pid'])
  for w in workers.values():w['proc'].wait()
  publish(terminal=True)
  summary=read(ROOT/'SUMMARY.json') if (ROOT/'SUMMARY.json').exists() else None
  if summary:atomic_json(ROOT/'COMPUTE_SUMMARY.json',summary)
  new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,summary=summary,workers={str(k):w['proc'].returncode for k,w in workers.items()},all_owned_processes_exited=cleanup['status']=='all_formal_group_members_exited'))
 return 3 if fatal or any(w['proc'].returncode for w in workers.values()) else 0

if __name__=='__main__':sys.exit(main())
