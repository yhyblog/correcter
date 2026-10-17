"""One future Batch1 command. CPU task never calls main or lifecycle."""
import inheritance
import argparse,os,signal,subprocess,sys,time
from pathlib import Path
from authorization import load_authorization,claim,exclusive_record,quota_gate
from core.contracts import PACKAGE,read,Meter,reconcile,configure_store
from core.identity import verify_device
from core.handoff import require_handoff_environment
from core.wave_timing import observe_restoration
from core.failure_evidence import record_failure
from batch_scheduler import lifecycle_driver,OnceObservation
from batch_storage import BatchMonitor
from execution import run
from storage import Store

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);a=parser.parse_args()
    r,p=load_authorization(a.release,False)
    exclusive_record(p['paths']['command_record'],dict(started=time.time(),release_sha256=r['_sha256'],command_opportunity_consumed=True))
    claimed=claim(r,p);parent=Path(p['paths']['output']);parent.mkdir(parents=True,exist_ok=False)
    out=parent/'launcher';out.mkdir();store=Store(out,byte_limit=p['storage']['root_bytes'],record_limit=p['storage']['monitor_log_hard_bytes'],file_limit=256)
    configure_store(store);caps={'native_nvml_identity_queries':len(p['parents'])};meter=Meter(out/'events.jsonl',caps)
    monitor=None;primary=None;life=None;entered=False;started=time.monotonic();phase='full_input_check'
    restoration=OnceObservation(lambda:observe_restoration(time.time(),p['timeouts']['restoration_observation_seconds']))
    def expire(sig,frame):raise TimeoutError('batch preparation timeout')
    previous=signal.signal(signal.SIGALRM,expire);signal.alarm(p['timeouts']['preparation_seconds'])
    try:
        checked,_=load_authorization(a.release,True)
        if checked['_sha256']!=r['_sha256']:raise ValueError('release changed after claim')
        phase='batch_capacity';store.json('STORAGE_ADMISSION.json',quota_gate(r,p))
        cfg=read(p['parents'][0]['config']['path']);store.json('HANDOFF_ENVIRONMENT.json',require_handoff_environment(cfg,os.environ))
        phase='fixed_identities'
        for item in p['parents']:
            pcfg=read(item['config']['path'])
            rows=meter.call('pre_reservation_NVML_identity',lambda pcfg=pcfg:verify_device({**r,**pcfg['device']},pcfg),{'native_nvml_identity_queries':1})
            store.json('NVML_IDENTITY_'+item['parent_key']+'.json',dict(rows=rows,target=pcfg['device']))
        phase='active_guard';subprocess.run(['/usr/bin/python',cfg['occupancy_handoff']['guard_path'],'active'],check=True,timeout=30)
        cache=Path(p['paths']['cache']);cache.mkdir(parents=True,exist_ok=False)
        for item in p['parents']:
            c=Path(item['paths']['cache']);c.mkdir();(c/'temporary').mkdir();(c/'cache').mkdir()
        monitor=BatchMonitor(p,store);monitor.check()
        signal.alarm(0);signal.signal(signal.SIGALRM,previous)
        store.json('LIFECYCLE_REQUESTED.json',dict(time=time.time(),elapsed_preparation=time.monotonic()-started,
            reservation_count=1,holders_reserved='all8',concurrency=p['concurrency']))
        entered=True;phase='one_lifecycle'
        command=lambda:run([cfg['occupancy_lifecycle'],'run','--',cfg['python'],'-B',str(PACKAGE/'code/reserved.py'),'--release',a.release],
            cwd=PACKAGE/'code',env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),new_session=True,
            stdout=out/'lifecycle.stdout',stderr=out/'lifecycle.stderr',monitor=monitor)
        exit_reader=lambda:read(parent/'reserved/PROCESS_GROUP_EXIT.json') if (parent/'reserved/PROCESS_GROUP_EXIT.json').exists() else None
        life=lifecycle_driver(command,exit_reader,restoration)
    except BaseException as e:primary=record_failure(e,branch=None,stage=phase,category='primary')
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,previous)
        # run() forwards failure to the guard and waits; the guard owns drain/release.
        if entered and life is None:
            cleanup=read(parent/'reserved/PROCESS_GROUP_EXIT.json') if (parent/'reserved/PROCESS_GROUP_EXIT.json').exists() else None
            restored=restoration()
            life=dict(returncode=None,process_group_exit=cleanup,restoration=restored)
        okay=primary is None and life and life['returncode']==0 and life['restoration']['status']=='occupancy_resolved'
        store.emergency_mode=True
        store.json('LAUNCH_RESULT.json',dict(status='complete' if okay else 'failed',primary=primary,lifecycle=life,
            claim=claimed,command_opportunity_consumed=True,release_consumed=True,unused_caps_reusable=False,
            launcher_ledger=reconcile(out/'events.jsonl',caps),storage_monitor=monitor.summary() if monitor else None,
            no_retry=True,coverage_must_be_read_per_parent_and_branch=True,timeouts=p['timeouts'],
            elapsed_seconds=time.monotonic()-started,successful_handoff_raw_poll_count=None,
            handoff_missing_reason='existing guard retains no successful raw poll series; no extra probe',
            lifecycle_not_entered_holders_unchanged=not entered),emergency=True)
        from batch_publication import launcher_index
        launcher_index(store,parent,synthetic=False)
    return 0 if okay else 3
if __name__=='__main__':sys.exit(main())
