"""One original all-card reservation; eight pinned native Corrector workers."""
import argparse,signal,subprocess,sys,time,traceback
from pathlib import Path
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,process_identity
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from admission import authority,worker_environment,before_cutoff

def summarize():
    rows=[read(p) for p in (ROOT/'runs').glob('*/RESULT.json')]
    valid=[r for r in rows if r['status']=='complete']
    attempts=len(list((ROOT/'runs').glob('*/ENTERED.json')))
    planned=read(ROOT/'SOURCE_ADMISSION.json')['eligible_count']
    result=dict(utc=utc(),method='VLA-Corrector',H=10,attempts=attempts,
        terminal_episodes=len(valid),successes=sum(r['success'] is True for r in valid),
        technical_failures=len(rows)-len(valid),publication_failures=attempts-len(rows),planned_episodes=planned,complete=len(rows)==len(valid)==planned,
        source_claims=len(list((ROOT/'claims').glob('*.json'))),command_type='continuation_of_unstarted_sources',old_entered47_replayed=0,
        policy_calls=sum(r['policy_calls'] for r in rows),interventions=sum(r['interventions'] for r in rows),
        flow_calls=sum(r['counters'].get('flow_calls',0) for r in rows),
        episode_seconds_sum=sum(r['elapsed_seconds'] for r in rows),same_A_main500_sources=True,
        native_repeated_intervention=True,our_G0_once_applied=False,
        training_data='existing corrector_pi05_mt50/latents_pi05_mt50 lineage; not a common-final-pool comparison')
    atomic_json(ROOT/'SUMMARY.json',result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);a=p.parse_args();chain=Path(a.chain)
    authority();own=process_identity();fds=held_reservation_fds()
    if own['pid']!=own['pgid'] or len(fds)!=1:raise RuntimeError('single inherited reservation and own group required')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);ack=holder_exit_ack(request)
    new_json(chain/'HOLDER_EXIT_ACK.json',ack);new_json(chain/'MANAGER_STARTED.json',dict(utc=utc(),process=own,single_reservation=True))
    workers={};fatal=None;stopping=False;last=0;begin=time.monotonic();base=read(ROOT/'config/BASE.json')
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    try:
        for slot in range(8):
            wr=chain/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
            for name in ['tmp','cache']:(wr/name).mkdir()
            with (wr/'stdout.log').open('xb') as so,(wr/'stderr.log').open('xb') as se:
                proc=subprocess.Popen([base['python'],'-B',str(ROOT/'code/resident_worker.py'),'--slot',str(slot),'--root',str(wr)],
                    cwd=ROOT,stdin=subprocess.DEVNULL,stdout=so,stderr=se,env=worker_environment(base,wr),pass_fds=fds,start_new_session=False)
            workers[slot]=dict(proc=proc,root=wr,term_at=None,exit_saved=False)
        while any(w['proc'].poll() is None for w in workers.values()):
            now=time.monotonic()
            for slot,w in workers.items():
                proc=w['proc']
                if proc.poll() is not None:
                    if not w['exit_saved']:
                        new_json(w['root']/'PROCESS_EXIT.json',dict(utc=utc(),exit_code=proc.returncode));w['exit_saved']=True
                    continue
                loading=not (w['root']/'MODEL_READY.json').exists()
                if stopping or (loading and now-begin>900) or now-begin>21600:
                    if w['term_at'] is None:proc.send_signal(signal.SIGTERM);w['term_at']=now
                    elif now-w['term_at']>30:proc.kill()
            if now-last>=10:
                atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),manager=own,status='running',
                    living_workers=sum(w['proc'].poll() is None for w in workers.values()),
                    loaded_workers=sum((w['root']/'MODEL_READY.json').exists() for w in workers.values()),
                    holder_policy='all8_off_whole_wave_no_auxiliary',summary=summarize()))
                last=now
            time.sleep(1)
    except BaseException as error:
        fatal=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    finally:
        for w in workers.values():
            if w['proc'].poll() is None:w['proc'].send_signal(signal.SIGTERM)
        cleanup=drain_group(own['pgid'],own['pid'])
        for w in workers.values():w['proc'].wait()
        summary=summarize()
        new_json(ROOT/'FINAL_SUMMARY.json',summary)
        from final_merge import publish_combined
        publish_combined()
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,summary=summary,
            workers={str(k):w['proc'].returncode for k,w in workers.items()},all_owned_processes_exited=True,auxiliary_exit=[]))
    return 0 if fatal is None and summary['complete'] and all(w['proc'].returncode==0 for w in workers.values()) else 3

if __name__=='__main__':sys.exit(main())
