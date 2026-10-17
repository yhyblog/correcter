"""Finite CPU coordinator for the documented B-only graphics initialization repair.

No model imports, GPU probes, holder controls, or formal locks here. The existing
formal service owns all GPU lifecycle work and keeps its own completion trigger.
"""
import argparse
import collections
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R = C/'results/B/B_D24_L11_RETEST_V1'
REC = R/'recovery/pi05_r2'
OUT = R/'recovery_queue'
sys.path.insert(0, str(R/'code'))
from qio import read, new_json, atomic_json, process_identity, same_process, utc, ref
from process_family import group_members
from admission import authority
from support import register_manifest
from publish import write_csv

RUN = 'D24_B_L11_CONTINUATION_r1'
TASK = 'B_D24_L11_RETEST_V1'
stopping = False


def heartbeat(status, **extra):
    row = dict(status=status, at_utc=utc(), process=process_identity(),
               task_id=TASK, run_id=RUN, CPU_only=True, **extra)
    atomic_json(OUT/'HEARTBEAT.json', row)
    atomic_json(C/'receipts/B/B_D24_L11_RETEST_V1_CONTINUATION_RUNNING.json', row)


def identity(row):
    return dict(row, host=row.get('host', row.get('hostname')))


def exited(root):
    """Require terminal publication and the actual local owned family to be gone."""
    result = root/'RESULT.json'
    if not result.exists():
        return False
    claim = read(root/'CLAIM.json')
    own = identity(claim['process'])
    here = process_identity()
    if (own['host'], own['boot_id']) != (here['host'], here['boot_id']):
        raise RuntimeError('predecessor host/boot differs; local recovery inspection required')
    if same_process(own):
        return False
    final = read(result)
    if not final.get('all_owned_descendants_exited'):
        raise RuntimeError('predecessor has no all-descendants-exited confirmation')
    peer_path = root/'chain/SAME_LOCK_FD_RETAINED.json'
    if peer_path.exists():
        peer = read(peer_path)['peer']
        if group_members(peer['pgid'], -1):
            return False
    if not final.get('occupancy_handoff_complete'):
        raise RuntimeError('predecessor occupancy restoration unresolved')
    return True


def check_wait(deadline):
    if stopping:
        raise RuntimeError('CPU continuation coordinator was stopped')
    if time.time() >= deadline:
        raise TimeoutError('finite continuation supervision deadline')


def wait_exit(root, deadline, label):
    last = 0
    while not exited(root):
        check_wait(deadline)
        claim_path = root/'CLAIM.json'
        if claim_path.exists():
            own = identity(read(claim_path)['process'])
            if not same_process(own) and not (root/'RESULT.json').exists():
                raise RuntimeError('claimed service exited without a terminal result: '+str(root))
        if time.monotonic()-last >= 15:
            heartbeat(label, waiting_for=str(root/'RESULT.json'),
                      healthy_work_untouched=True, next_package=str(REC))
            last = time.monotonic()
        time.sleep(5)


def finalize_activation():
    grant = authority()
    config = read(REC/'config/CONFIG.json')
    parent_cfg = read(R/'config/CONFIG.json')
    if time.time() >= min(config['admission_cutoff_unix'], config['absolute_wall_deadline_unix']):
        raise RuntimeError('admission deadline passed before corrected continuation')
    if (REC/'CLAIM.json').exists() or (REC/'CHAIN_COMMAND.json').exists():
        raise RuntimeError('continuation already claimed; never start a second service')
    parent_attempts = read(R/'ATTEMPT_COUNTER.json')['reserved_attempts'] if (R/'ATTEMPT_COUNTER.json').exists() else 0
    units = read(REC/'SOURCE_INDEX.json')['units']
    for unit in units:
        key = hashlib.sha256(unit['unit_id'].encode()).hexdigest()
        if (R/'unit_claims'/(key+'.json')).exists() or (R/'episodes'/key/'ENTERED.json').exists():
            raise RuntimeError('pi05 unit entered in predecessor; reconcile exact unit first')
    assert len(units) == 1500 and all(u['model'] == 'pi05' for u in units)
    available = grant['nodes']['B']['stage_attempt_cap'] - parent_attempts
    prior = parent_cfg['planned_prior_attempts'] + parent_attempts
    if available < len(units) or prior+len(units) > grant['nodes']['B']['cumulative_attempt_cap']:
        raise RuntimeError('remaining grant does not cover original unentered units')
    config.update(activation_finalized=True, activation_utc=utc(),
                  planned_prior_attempts=prior, stage_attempt_cap=available,
                  parent_actual_attempts=parent_attempts,
                  activation_evidence=str(OUT/'ACTIVATION.json'))
    atomic_json(REC/'config/CONFIG.json', config)
    evidence = dict(at_utc=utc(), status='ready', repair=ref(REC/'REPAIR.json'),
                    predecessor_result=ref(R/'RESULT.json'),
                    actual_parent_attempts=parent_attempts,
                    original_pi05_entered_attempts=0, remaining_original_units=1500,
                    remaining_stage_attempt_cap=available, cumulative_prior_B_attempts=prior,
                    config=ref(REC/'config/CONFIG.json'),
                    original_wall_deadline_preserved=True, duplicate_units_admitted=0)
    new_json(OUT/'ACTIVATION.json', evidence)


def merge_results():
    units = read(R/'SOURCE_INDEX.json')['units']
    rows, missing, cells = [], [], []
    for unit in units:
        key = hashlib.sha256(unit['unit_id'].encode()).hexdigest()
        candidates = [root/'episodes'/key/'SUMMARY_ROW.json' for root in (R, REC)]
        paths = [p for p in candidates if p.exists()]
        if len(paths) > 1:
            raise RuntimeError('multiple actual outcomes for one original unit: '+unit['unit_id'])
        if paths:
            p = paths[0]
            row = read(p)
            for k in ('unit_id', 'source_id', 'method', 'policy_seed', 'task', 'H', 'model'):
                if row.get(k, unit[k]) != unit[k]:
                    raise RuntimeError('scientific identity mismatch: '+k)
            if row.get('env_seed', row.get('reset_seed')) != unit['env_seed']:
                raise RuntimeError('environment seed mismatch')
            complete = row.get('status') == 'complete'
            if complete and not isinstance(row.get('success'), bool):
                raise RuntimeError('completed outcome lacks actual boolean success')
            if not complete and row.get('success') is not None:
                raise RuntimeError('technical outcome must remain missing')
            result = dict(unit, **{k:v for k,v in row.items() if k not in unit})
            result.update(status=row['status'], success=row.get('success'),
                          summary_path=str(p), result_path=str(p.parent/'RESULT.json'))
            rows.append(result)
            if not complete:
                missing.append(dict(unit_id=unit['unit_id'],status=row['status'],success=None,summary_path=str(p)))
        else:
            entered = any((p.parent/'ENTERED.json').exists() for p in candidates)
            missing.append(dict(unit_id=unit['unit_id'], status='execution_unknown' if entered else 'unstarted', success=None))
    keys = sorted({(u['model'],u['method'],u['H']) for u in units})
    for key in keys:
        planned = sum((u['model'],u['method'],u['H']) == key for u in units)
        actual = [r for r in rows if (r['model'],r['method'],r['H']) == key]
        valid = [r for r in actual if r['status'] == 'complete']
        success = sum(r['success'] for r in valid)
        costs = {}
        for name in ('counters','numeric_counters','encoder_counters'):
            counter = collections.Counter()
            for row in actual:
                counter.update(row.get(name, {}))
            costs[name] = dict(counter)
        cells.append(dict(model=key[0],method=key[1],H=key[2],loss='L11',fit_seed=9101,
                          planned=planned,valid=len(valid),missing=planned-len(valid),successes=success,
                          success_rate=success/len(valid) if valid else None,
                          current_paper=key[1]=='Post',actual_costs=costs,
                          sum_episode_wall_seconds=sum(r.get('elapsed_seconds',0) for r in actual),
                          wall_sum_includes_RPC_wait_and_is_not_GPU_hours=True))
    attempts = sum(read(root/'ATTEMPT_COUNTER.json')['reserved_attempts']
                   for root in (R,REC) if (root/'ATTEMPT_COUNTER.json').exists())
    config = read(R/'config/CONFIG.json')
    summary = dict(task_id=TASK,run_id=RUN,revision=2,at_utc=utc(),
                   status='complete' if not missing else 'partial',planned=len(units),
                   valid=sum(c['valid'] for c in cells),missing=len(missing),attempts=attempts,
                   cells=cells,cumulative_B_attempts=config['planned_prior_attempts']+attempts,
                   stage_attempt_cap=2750,node_cumulative_attempt_cap=24750,
                   selected_loss='L11',fit_seed=9101,new_training_updates=0,new_collection=0,
                   missing_not_failure=True,old_L01_results_preserved=True,
                   revealed_source_retest=True,independent_new_blind_test=False,
                   occupancy_cost_excluded=True,initial_wave_result=ref(R/'RESULT.json'),
                   correction_result=ref(REC/'RESULT.json'),
                   initial_graphics_failure_preserved=ref(R/'phases/01_pi05_Post/FAILURE.json'),
                   concurrency=[dict(read(p),package=str(root)) for root in (R,REC)
                                for p in (root/'phases').glob('*/CONCURRENCY.json')])
    merged = OUT/'merged'
    merged.mkdir(exist_ok=True)
    atomic_json(R/'FINAL_RECOVERED_SUMMARY_r2.json',summary)
    atomic_json(merged/'MISSING.json',missing)
    write_csv(merged/'EPISODES.csv',rows)
    write_csv(merged/'CELLS.csv',cells)
    write_csv(merged/'MISSING.csv',missing)
    write_csv(merged/'POST_PAPER.csv',[r for r in rows if r['method']=='Post'])
    write_csv(merged/'VELOCITY_OTHER_WORK.csv',[r for r in rows if r['method']=='Velocity'])
    receipt = dict(summary,root=str(R),final_summary=ref(R/'FINAL_RECOVERED_SUMMARY_r2.json'),
                   merged_exports=str(merged),A_waits_for_B=False,
                   all_owned_descendants_exited=True,occupancy_handoff_complete=True)
    canonical = C/'receipts/B/B_D24_L11_RETEST_V1_RESULT_r1.json'
    if canonical.exists():
        archive = OUT/'INITIAL_WAVE_RECEIPT_r1.json'
        new_json(archive,read(canonical))
        receipt['initial_wave_receipt_archive'] = ref(archive)
    atomic_json(C/'receipts/B/B_D24_L11_RETEST_V1_RESULT_r2.json',receipt)
    # The requested receipt is the current aggregate. All original wave outputs,
    # failures and its initial receipt remain separately preserved above.
    atomic_json(canonical,receipt)
    atomic_json(R/'RESULT_LATEST.json',receipt)
    (OUT/'REPORT.md').write_text(
        '# B L11 continuation result\n\nStatus: '+summary['status']+'; valid '+str(summary['valid'])+
        '/2500; missing '+str(summary['missing'])+'.\n\nThe first pi05 load failed before any pi05 episode. '+
        'The private graphics journal compatibility fix resumed only its 1500 original unentered units '+
        'after the independent Smol formal family exited. Original failures and L01 outputs are retained. '+
        'Post and Velocity exports are separate. Sources were already revealed; this is not a blind test.\n')
    return summary


def serve():
    global stopping
    local=Path('/tmp/corrector_B_L11_continuation_r1')
    local.mkdir(exist_ok=True)
    lock=(local/'coordinator.lock').open('a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    authority()
    own=process_identity()
    callback_identity=dict(hostname=own['host'],boot_id=own['boot_id'],pid=own['pid'],
                           start_ticks=own['start_ticks'],session_id=os.getsid(0))
    claim=OUT/'CLAIM.json'
    new_json(claim,dict(task_id=TASK,run_id=RUN,at_utc=utc(),process=callback_identity,
                        CPU_only=True,scientific_claim=False,repair=ref(REC/'REPAIR.json')))
    manifest=dict(job_id=RUN,task_id=TASK,revision=1,run_id=RUN,attempt=1,
                  claim_identity=ref(claim),process_identity=callback_identity,
                  result_path=str(OUT/'RESULT.json'),error_summary_path=str(OUT/'stderr.log'))
    new_json(OUT/'WAKEUP_REGISTRATION.json',manifest)
    trigger=register_manifest(OUT/'WAKEUP_REGISTRATION.json')
    new_json(OUT/'READY.json',dict(process=own,at_utc=utc(),status='READY',
                                  trigger_registered=trigger.get('registered'),CPU_only=True,
                                  original_B_thread=os.environ.get('CODEX_THREAD_ID'),
                                  next_package=str(REC),no_nested_formal_lock=True))
    def stop(*_):
        global stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):
        signal.signal(sig,stop)
    try:
        deadline=read(R/'config/CONFIG.json')['absolute_wall_deadline_unix']+600
        wait_exit(R,deadline,'waiting_own_healthy_formal_family')
        finalize_activation()
        launch=['/usr/bin/python','-B',str(REC/'code/service.py'),'start']
        new_json(OUT/'LAUNCH.json',dict(at_utc=utc(),argv=launch,one_shot=True))
        result=subprocess.run(launch,cwd=REC,capture_output=True,text=True,timeout=30)
        new_json(OUT/'LAUNCH_RESULT.json',dict(at_utc=utc(),exit_code=result.returncode,
                                             stdout=result.stdout,stderr=result.stderr))
        if result.returncode:
            raise RuntimeError('corrected continuation launcher rejected; no automatic repeat')
        start_deadline=time.time()+90
        while not (REC/'DAEMON_READY.json').exists():
            check_wait(start_deadline)
            time.sleep(2)
        wait_exit(REC,deadline,'corrected_pi05_formal_family')
        summary=merge_results()
        final=dict(status=summary['status'],exit_code=0 if summary['status']=='complete' else 3,
                   task_id=TASK,run_id=RUN,at_utc=utc(),
                   final_summary=str(R/'FINAL_RECOVERED_SUMMARY_r2.json'),
                   receipt=str(C/'receipts/B/B_D24_L11_RETEST_V1_RESULT_r2.json'),
                   all_owned_descendants_exited=True,occupancy_handoff_complete=True,
                   A_waits_for_B=False)
    except BaseException as exc:
        final=dict(status='execution_unknown',exit_code=3,task_id=TASK,run_id=RUN,at_utc=utc(),
                   error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()),
                   no_implicit_scientific_restart=True,original_results_preserved=True,
                   predecessor_result=str(R/'RESULT.json'),recovery_result=str(REC/'RESULT.json'),
                   A_waits_for_B=False)
    atomic_json(OUT/'RESULT.json',final)
    heartbeat('terminal',result=final)
    return final['exit_code']


def start():
    authority()
    OUT.mkdir(exist_ok=True)
    if (OUT/'READY.json').exists() and same_process(read(OUT/'READY.json')['process']):
        print('ALREADY_RUNNING',read(OUT/'READY.json')['process'])
        return 0
    if (OUT/'CLAIM.json').exists():
        raise RuntimeError('existing CPU coordinator claim; inspect instead of duplicating')
    with (OUT/'stdout.log').open('ab') as out,(OUT/'stderr.log').open('ab') as err:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(Path(__file__).resolve()),'serve'],
                              cwd=R,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),
                              stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
    print('SPAWNED_CPU_COORDINATOR',proc.pid)
    return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['start','serve'])
    args=parser.parse_args()
    sys.exit(start() if args.action=='start' else serve())
