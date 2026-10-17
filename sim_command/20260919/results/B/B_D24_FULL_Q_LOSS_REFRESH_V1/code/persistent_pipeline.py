"""One host-scoped finite queue: own Q fits, Q-free unstarted R, selected native P/V."""
import argparse
import fcntl
import os
import signal
import subprocess
import time
import traceback
from pathlib import Path
import paths
from paths import ROOT,CONFIG,CAMPAIGN
from qio import read,new_json,atomic_json,utc,process_identity,same_process,ref,optional_snapshot
from admission import authority

def normalized(p):return dict(p,host=p.get('host',p.get('hostname')))

def serve():
    local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    lock=(local/'pipeline.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    authority();own=process_identity();child=None;active=None;stopping=False;phase='existing_Q_fit';fatal=None
    identity=dict(hostname=own['host'],boot_id=own['boot_id'],pid=own['pid'],start_ticks=own['start_ticks'],session_id=os.getsid(0))
    new_json(ROOT/'QUEUE_CLAIM.json',dict(task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],process=identity,
        authorization=ref(CAMPAIGN/CONFIG['grant']),at_utc=utc(),no_duplicate_existing_fit=True))
    manifest=dict(job_id=CONFIG['run_id'],task_id=CONFIG['task_id'],revision=1,run_id=CONFIG['run_id'],attempt=1,
        claim_identity=ref(ROOT/'QUEUE_CLAIM.json'),process_identity=identity,result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'queue.stderr.log'))
    new_json(ROOT/'WAKEUP_REGISTRATION.json',manifest)
    subprocess.run(['/usr/bin/python',str(CAMPAIGN/'work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py'),'register','--manifest',str(ROOT/'WAKEUP_REGISTRATION.json')],check=True)
    new_json(ROOT/'QUEUE_READY.json',dict(status='ready',phase=phase,at_utc=utc(),process=own,terminal_trigger=ref(ROOT/'WAKEUP_REGISTRATION.json'),
        existing_fit=ref(ROOT/'fit_r1/CLAIM.json'),code=ref(ROOT/'CODE_MANIFEST.json'),A_waits_for_B=False))
    def stop(*_):
        nonlocal stopping
        stopping=True
        if active and (active/'DAEMON_READY.json').exists():
            p=read(active/'DAEMON_READY.json')['process']
            if same_process(p):os.kill(p['pid'],signal.SIGTERM)
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)
    def check():
        authority()
        if stopping or (ROOT/'STOP.json').exists():raise RuntimeError('user stopped owned pipeline')
        if time.time()>=CONFIG['absolute_wall_deadline_unix']:raise TimeoutError('finite pipeline deadline')
    def heartbeat(**extra):
        value=dict(status='running',phase=phase,at_utc=utc(),process=own,
            active_root=str(active) if active else None,selection_dependency=CONFIG['selection_path'],A_waits_for_B=False,**extra)
        try:
            atomic_json(ROOT/'QUEUE_HEARTBEAT.json',value)
            atomic_json(CAMPAIGN/CONFIG['running_receipt'],dict(value,task_id=CONFIG['task_id'],run_id=CONFIG['run_id']))
        except OSError as exc:print('TELEMETRY_PENDING',repr(exc),flush=True)
    def wait_wave(root):
        nonlocal active
        active=root;dead_since=None
        while True:
            check();claim=read(root/'CLAIM.json');alive=same_process(normalized(claim['process']))
            terminal=optional_snapshot(root/'RESULT.json')
            if not alive and terminal.get('all_owned_descendants_exited'):
                if not terminal.get('occupancy_handoff_complete'):raise RuntimeError('formal exit published without occupancy resolution')
                heartbeat(active_alive=False,terminal=terminal)
                active=None;return terminal
            if not alive:
                dead_since=dead_since or time.monotonic()
                if time.monotonic()-dead_since>120:raise RuntimeError('phase execution_unknown; no implicit replay')
            else:dead_since=None
            heartbeat(active_alive=alive,progress=optional_snapshot(root/'chain/HEARTBEAT.json'))
            time.sleep(10)
    def start_wave(root,prior_root,prior_attempts,selection=None):
        nonlocal active,child
        check()
        assert not (root/'CLAIM.json').exists() and not (root/'CHAIN_COMMAND.json').exists()
        cfg=read(root/'config/CONFIG.json')
        cfg.update(predecessor_root=str(prior_root),predecessor_required_complete=False,
            planned_prior_attempts=prior_attempts,activation_finalized=True,
            absolute_wall_deadline_unix=min(time.time()+12*3600,CONFIG['absolute_wall_deadline_unix'],1790164800),formal_activation_utc=utc())
        if selection:
            cfg.update(selected_loss=selection['chosen_loss'],selected_fit_seed=9101,selected_Q_assets=str(ROOT/'models'/selection['chosen_loss']),selection_lock=str(ROOT/'SELECTION_LOCK.json'))
        assert prior_attempts+cfg['stage_attempt_cap']<=20000
        atomic_json(root/'config/CONFIG.json',cfg)
        if cfg.get('completion_via_queue'):new_json(root/'WAKEUP_REGISTRATION.json',manifest)
        new_json(root/'CODE_MANIFEST.json',dict(at_utc=utc(),files=[ref(p) for p in sorted((root/'code').glob('*.py'))]+[ref(p) for p in sorted((root/'config').glob('*.json'))]))
        with (root/'formal.stdout.log').open('xb') as so,(root/'formal.stderr.log').open('xb') as se:
            child=subprocess.Popen(['/usr/bin/python','-B',str(root/'code/service.py'),'serve'],cwd=root,
                stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        active=root;new_json(root/'FORMAL_SERVICE_STARTED.json',dict(process=process_identity(child.pid),at_utc=utc()))
        ready_deadline=time.monotonic()+60
        while not (root/'CLAIM.json').exists():
            if child.poll() is not None or time.monotonic()>=ready_deadline:raise RuntimeError('new service did not establish claim')
            time.sleep(1)
        return wait_wave(root)
    def consume_selection():
        source=Path(CONFIG['selection_path'])
        while True:
            check()
            if source.exists():
                value=read(source);chosen=value.get('chosen_loss')
                status=str(value.get('status','')).lower()
                if chosen in CONFIG['losses'] and not any(x in status for x in ['partial','failed','blocked','pending','unknown']):
                    fit=value.get('fixed_fit_seed',value.get('final_fit_seed',value.get('deployment_fit_seed',value.get('fit_seed',9101))))
                    if int(fit)!=9101:raise RuntimeError('A selection conflicts with predeclared fit9101')
                    if any(value.get(k,0) for k in ['unresolved_development','development_missing','development_unresolved']):raise RuntimeError('A published selection has unresolved development cells')
                    ready=read(ROOT/'CANDIDATES_READY.json');assert len(ready['candidate_assets'])==4
                    snapshot=ROOT/'SELECTION_SOURCE_SNAPSHOT.json';new_json(snapshot,value)
                    selected=dict(chosen_loss=chosen,fit_seed=9101,status='locked',at_utc=utc(),
                        authority=ref(CAMPAIGN/CONFIG['grant']),A_published_selection=ref(source),snapshot=ref(snapshot),
                        own_candidate=ready['candidate_assets'][chosen],no_test_selection=True,no_A_Q_weights_loaded=True)
                    new_json(ROOT/'SELECTION_LOCK.json',selected);return selected
                heartbeat(selection_status='awaiting_valid_published_choice',observed_status=value.get('status'),chosen_loss=chosen)
            else:heartbeat(selection_status='waiting_for_scientific_loss_selection')
            time.sleep(15)
    try:
        fit=wait_wave(ROOT/'fit_r1')
        if fit['status']!='complete' or not (ROOT/'CANDIDATES_READY.json').exists():raise RuntimeError('candidate fit incomplete; no partial ensemble deployment')
        phase='R_unstarted_multi';r=Path(CONFIG['R_continuation_root'])
        r_terminal=start_wave(r,ROOT/'fit_r1',CONFIG['planned_prior_attempts'])
        r_summary=read(r/'FINAL_SUMMARY.json');prior=r_summary['cumulative_B_attempts']
        # R historical cancellation does not block the newly authorized Q tests.
        phase='waiting_A_scientific_selection';selection=consume_selection()
        phase='selected_Smol_PV_multi';test=ROOT/'evaluation_r1'
        test_terminal=start_wave(test,r,prior,selection)
        summary=read(test/'FINAL_SUMMARY.json')
        result=dict(status=test_terminal['status'],task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],at_utc=utc(),
            all_owned_descendants_exited=True,occupancy_handoff_complete=test_terminal['occupancy_handoff_complete'],
            candidates=ref(ROOT/'CANDIDATES_READY.json'),selection=ref(ROOT/'SELECTION_LOCK.json'),Q_new_updates=64000,
            evaluation=ref(test/'FINAL_SUMMARY.json'),R_continuation=ref(r/'FINAL_SUMMARY.json'),cumulative_B_attempts=summary['cumulative_B_attempts'],
            new_test_attempts=summary['current_run_attempts'],new_collection=0,A_waits_for_B=False)
        atomic_json(ROOT/'RESULT.json',result);atomic_json(CAMPAIGN/CONFIG['result_receipt'],result)
    except BaseException as exc:
        fatal=dict(error=repr(exc),traceback=traceback.format_exc())
        if active:
            stop();deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                t=optional_snapshot(active/'RESULT.json')
                if t.get('all_owned_descendants_exited') and t.get('occupancy_handoff_complete'):break
                time.sleep(5)
        resolved=active is None or bool(optional_snapshot(active/'RESULT.json').get('all_owned_descendants_exited'))
        result=dict(status='blocked' if phase=='waiting_A_scientific_selection' else 'execution_unknown',at_utc=utc(),phase=phase,fatal=fatal,
            task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],all_owned_descendants_exited=resolved,occupancy_handoff_complete=resolved,
            preserved_candidates=(ROOT/'CANDIDATES_READY.json').exists(),no_implicit_replay=True,A_waits_for_B=False)
        atomic_json(ROOT/'RESULT.json',result);atomic_json(CAMPAIGN/CONFIG['result_receipt'],result)
    return 0 if fatal is None else 3

def start():
    if (ROOT/'QUEUE_CLAIM.json').exists():
        p=normalized(read(ROOT/'QUEUE_CLAIM.json')['process'])
        print('ALREADY_RUNNING' if same_process(p) else 'EXISTING_CLAIM_NO_REPLAY');return 0 if same_process(p) else 3
    authority()
    with (ROOT/'queue.stdout.log').open('ab') as so,(ROOT/'queue.stderr.log').open('ab') as se:
        p=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/persistent_pipeline.py'),'serve'],cwd=ROOT,
            stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    print('PIPELINE_SPAWNED_NOT_YET_READY',p.pid);return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args();raise SystemExit(start() if a.action=='start' else serve())
