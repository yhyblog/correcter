"""Fit three frozen critics then evaluate 500 once, under one original reservation."""
import argparse,signal,subprocess,time,traceback,csv
from pathlib import Path
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,worker_environment,before_cutoff
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group


def summarize():
    rows=[read(p) for p in (ROOT/'runs').glob('*/RESULT.json')];valid=[r for r in rows if r['status']=='complete']
    attempts=len(list((ROOT/'runs').glob('*/ENTERED.json')))
    summary=dict(utc=utc(),method='GAF-v1 adapted',H=10,attempts=attempts,planned_episodes=500,
        terminal_episodes=len(valid),successes=sum(r['success'] is True for r in valid),
        technical_failures=len(rows)-len(valid),entered_without_RESULT=attempts-len(rows),
        complete=len(valid)==500,policy_calls=sum(r['policy_calls'] for r in rows),
        flow_calls=sum(r['flow_calls'] for r in rows),control_steps=sum(r['steps'] for r in rows),
        critic_forward_calls=sum(r['gaf_counts']['entered'].get('critic_forward',0) for r in rows),
        action_backward_calls=sum(r['gaf_counts']['entered'].get('critic_backward',0) for r in rows),
        episode_seconds_sum=sum(r['elapsed_seconds'] for r in rows),same_A_main500_sources=True,
        no_G0_or_once_gate=True,training_scope='15 existing training parents / 2 fixed internal holdout; adapted, not official reproduction or full MT50 training')
    atomic_json(ROOT/'SUMMARY.json',summary);return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);a=p.parse_args();chain=Path(a.chain)
    authority();own=process_identity();fds=held_reservation_fds()
    if own['pid']!=own['pgid'] or len(fds)!=1:raise RuntimeError('own isolated group and one inherited reservation required')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0])
    new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request));new_json(chain/'MANAGER_STARTED.json',dict(utc=utc(),process=own,single_reservation=True))
    base=read(ROOT/'config/BASE.json');workers={};stopping=False;fatal=None;stage='fit';fit_results={};fit_complete=False;last=0
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    def launch(key,output,script,args):
        if stopping or not before_cutoff():raise RuntimeError('new work admission stopped')
        output.mkdir(parents=True,exist_ok=False)
        for name in ['tmp','cache']:(output/name).mkdir()
        with (output/'stdout.log').open('xb') as so,(output/'stderr.log').open('xb') as se:
            proc=subprocess.Popen([base['python'],'-B',str(ROOT/'code'/script),*args,'--root',str(output)],
                cwd=ROOT,stdin=subprocess.DEVNULL,stdout=so,stderr=se,env=worker_environment(base,output),pass_fds=fds,start_new_session=False)
        workers[key]=dict(proc=proc,root=output,start=time.monotonic(),term_at=None,exit_saved=False,stage=stage)
    def wait_stage(keys,timeout):
        nonlocal last
        while any(workers[k]['proc'].poll() is None for k in keys):
            now=time.monotonic()
            for key in keys:
                w=workers[key];proc=w['proc']
                if proc.poll() is not None:
                    if not w['exit_saved']:new_json(w['root']/'PROCESS_EXIT.json',dict(utc=utc(),exit_code=proc.returncode));w['exit_saved']=True
                    continue
                loading=not (w['root']/'MODEL_READY.json').exists()
                if stopping or now-w['start']>timeout or (loading and now-w['start']>900):
                    if w['term_at'] is None:proc.send_signal(signal.SIGTERM);w['term_at']=now
                    elif now-w['term_at']>30:proc.kill()
            if now-last>=10:
                status={}
                if stage=='fit':status={k:read(workers[k]['root']/'status.json') for k in keys if (workers[k]['root']/'status.json').exists()}
                atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),stage=stage,manager=own,
                    living_workers=sum(workers[k]['proc'].poll() is None for k in keys),
                    loaded_workers=sum((workers[k]['root']/'MODEL_READY.json').exists() for k in keys),
                    fits=status,summary=summarize(),holder_policy='all8off_entire_wave'))
                last=now
            time.sleep(1)
        for key in keys:
            w=workers[key];w['proc'].wait()
            if not w['exit_saved']:new_json(w['root']/'PROCESS_EXIT.json',dict(utc=utc(),exit_code=w['proc'].returncode));w['exit_saved']=True
    try:
        fit_keys=[]
        for slot,seed in enumerate([9201,9202,9203]):
            key=f'fit_{seed}';fit_keys.append(key);launch(key,ROOT/f'fits/{seed}','fit_worker.py',['--seed',str(seed),'--slot',str(slot)])
        wait_stage(fit_keys,3630)
        for seed,key in zip([9201,9202,9203],fit_keys):
            w=workers[key];result=read(w['root']/'RESULT.json') if (w['root']/'RESULT.json').exists() else None;fit_results[str(seed)]=result
            if w['proc'].returncode!=0 or not result or result['status']!='complete' or result['counts']['optimizer_updates']!=10000:raise RuntimeError('three-member frozen fit incomplete; no evaluation')
        fit_complete=True
        new_json(ROOT/'FIT_SUMMARY.json',dict(utc=utc(),status='complete',members=fit_results,optimizer_updates=30000,
            selection='fixed internal parent-holdout MSE; no test selection',test_model_selection=False))
        new_json(ROOT/'outbox/fit_complete.json',dict(event_id='D24_A_GAF_internal_holdout_fit_complete_v1',kind='fit_complete',synthetic=False,utc=utc(),result=str(ROOT/'FIT_SUMMARY.json'),eval_autocontinues=True))
        stage='evaluation';eval_keys=[]
        for slot in range(8):
            key=f'eval_{slot}';eval_keys.append(key);launch(key,chain/'workers'/str(slot),'resident_worker.py',['--slot',str(slot)])
        wait_stage(eval_keys,21600)
    except BaseException as e:
        fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    finally:
        for w in workers.values():
            if w['proc'].poll() is None:w['proc'].send_signal(signal.SIGTERM)
        cleanup=drain_group(own['pgid'],own['pid'])
        for w in workers.values():w['proc'].wait()
        summary=summarize();summary.update(all_owned_workers_exited=True,worker_nonzero_exits=sum(w['proc'].returncode!=0 for w in workers.values()),fit_complete=fit_complete)
        new_json(ROOT/'FINAL_SUMMARY.json',summary)
        rows=[read(p) for p in sorted((ROOT/'runs').glob('*/RESULT.json'))];new_json(ROOT/'EPISODES.json',rows)
        with (ROOT/'PER_TASK.csv').open('x') as f:
            writer=csv.DictWriter(f,fieldnames=['task','episodes','successes','technical_failures','success_rate']);writer.writeheader()
            for task in sorted({s['task'] for s in read(ROOT/'config/EVAL_SOURCES_V1.json')['rows']}):
                subset=[r for r in rows if r['task']==task];valid=[r for r in subset if r['status']=='complete'];success=sum(r['success'] is True for r in valid)
                writer.writerow(dict(task=task,episodes=len(valid),successes=success,technical_failures=len(subset)-len(valid),success_rate=success/len(valid) if valid else None))
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,stage=stage,cleanup=cleanup,summary=summary,
            workers={k:w['proc'].returncode for k,w in workers.items()},all_owned_processes_exited=True,auxiliary_exit=[]))
    return 0 if fatal is None and summary['complete'] and not summary['worker_nonzero_exits'] else 3

if __name__=='__main__':raise SystemExit(main())
