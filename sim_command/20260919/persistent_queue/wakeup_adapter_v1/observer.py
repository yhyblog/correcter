"""CPU-only sidecar: durable wakeup evidence, without owning scientific jobs.

The live experiment notifier is left intact. This sidecar owns only its second
synthetic callback and emergencies absent from that notifier. A busy original
writer gets one queued message; further opportunities are reserved for native
resume after that writer releases its lock. Queue acceptance is never an ACK.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

PACKAGE = Path(__file__).resolve().parent
QUEUE = PACKAGE.parent
BASE = QUEUE.parent
WORKSPACE = BASE.parents[2]
THREAD = '01a0b91f-7443-71b1-915d-6cdb6d6a1a13'
HOST = 'trial-303224955-trialrun-303224955-worker-0'
WAKE_SHA = '6cd1233b0e345bbea2a8320f6126897364c89c6964e92975be4d80c1291766f6'
ROOT = QUEUE / 'nodes/A/wakeup_adapter_v1'


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def ref(path):
    p = Path(path)
    return dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def write(path, value, exclusive=False):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p if exclusive else p.with_name(p.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    if not exclusive:
        os.replace(temp, p)
    fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def identity(pid=None):
    pid = os.getpid() if pid is None else int(pid)
    try:
        st = Path('/proc', str(pid), 'stat').read_text().rsplit(') ', 1)[1].split()
        return dict(pid=pid, start_ticks=int(st[19]), pgid=int(st[2]),
                    ppid=int(st[1]), state=st[0], host=socket.gethostname(),
                    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    except FileNotFoundError:
        return None


def alive(saved):
    current = identity(saved['pid'])
    return bool(current and current['state'] not in ('Z', 'X') and
                all(current[k] == saved[k] for k in ('pid', 'start_ticks', 'host', 'boot_id')))


def verify():
    policy = QUEUE / 'LONG_TASK_EVENT_WAKEUP_V1.json'
    if ref(policy)['sha256'] != WAKE_SHA or socket.gethostname() != HOST:
        raise ValueError('fixed host / authorization mismatch')
    binding = read(policy)['nodes']['A']
    if binding['executor_thread_id'] != THREAD or binding['hostname'] != HOST:
        raise ValueError('original thread binding mismatch')
    for item in read(PACKAGE / 'CODE_MANIFEST.json')['files']:
        if ref(item['path'])['sha256'] != item['sha256']:
            raise ValueError('sidecar code mismatch')


def writer_busy():
    # This does not acquire session ownership. The native resume command must
    # acquire its own lock again and may reject a race. Never remove the lock.
    lockpath = Path('/home/tiger/.codex/thread-writer-locks') / (THREAD + '.lock')
    try:
        with lockpath.open('rb') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(lock, fcntl.LOCK_UN)
            return False
    except FileNotFoundError:
        return False


def choose(state, *, busy, now, resume_alive=False):
    if state.get('handler_acknowledged'):
        return 'handled'
    if state.get('attempts', 0) >= 3:
        return 'notification_budget_exhausted'
    if resume_alive or now < state.get('next_unix', 0):
        return 'pending'
    if busy:
        return 'waiting_for_original_writer_release' if state.get('queue_sent') else 'queue'
    return 'native_resume'


def valid_ack(event, ack):
    return (ack.get('event_id') == event['event_id'] and
            ack.get('executor_thread_id') == THREAD and
            ack.get('challenge') == event['challenge'] and
            ack.get('synthetic') is event['synthetic'] and
            ack.get('handled') is True and
            (not event['synthetic'] or ack.get('scientific_compute') == 0))


def prompt(event_path, event):
    ack = event_path.parent / 'HANDLER_ACK.json'
    if event['synthetic']:
        return (
            'Corrector A 后台原会话回调自检，synthetic=true。固定原会话 ' + THREAD +
            '。仅读取 ' + str(event_path) + '，核对 event_id/challenge。以排他创建写 ' + str(ack) +
            '：event_id=' + event['event_id'] + ', executor_thread_id=' + THREAD +
            ', challenge=' + event['challenge'] + ', synthetic=true, handled=true, scientific_compute=0, '
            'callback_received_as_message=true，记录 UTC；已存在则核对，不覆盖。'
            '只写此小ACK并回复一句后结束，不调用任何模型/硬件/实验，不改REPORT或启动下一任务。'
            '后台observer会登记实际ACK；不要将投递ID当成ACK，不声称物理窗口已关闭。')
    return (
        'Corrector A 后台异常事件，固定原会话 ' + THREAD + '。读取 ' + str(event_path) +
        '，核对冻结身份和已保存退出/发布/占卡证据，再以排他创建写 ' + str(ack) +
        '（event_id=' + event['event_id'] + ', executor_thread_id=' + THREAD + ', challenge=' +
        event['challenge'] + ', synthetic=false, handled=true, UTC）。补短REPORT/RESULT。'
        '事件不授权重跑；现有daemon可能继续工作，不重复launch，不终止无关进程，不回到旧475采集。')


def deliver(event_path, now=None):
    now = time.time() if now is None else now
    event_path = Path(event_path)
    event = read(event_path)
    if (event['executor_thread_id'] != THREAD or event['hostname'] != HOST or
            event['authorization_sha256'] != WAKE_SHA):
        raise ValueError('outbox identity mismatch')
    folder = event_path.parent
    tp = folder / 'TRANSPORT.json'
    state = read(tp) if tp.exists() else dict(attempts=0, next_unix=event.get('deliver_after_unix', 0))
    ackpath = folder / 'HANDLER_ACK.json'
    if ackpath.exists():
        ack = read(ackpath)
        if not valid_ack(event, ack):
            raise ValueError('invalid original-thread callback ACK')
        if state.get('attempts', 0) == 0:
            raise ValueError('ACK without any callback transport')
        if not state.get('handler_acknowledged'):
            state.update(state='handler_acknowledged', handler_acknowledged=True,
                         handler_ack=ref(ackpath), observed_utc=utc())
            write(tp, state)
        if event['synthetic'] and not (ROOT / 'WAKEUP_READY.json').exists():
            write(ROOT / 'WAKEUP_READY.json', dict(
                status='ACTUAL_CALLBACK_ACK_OBSERVED', node='A', executor_thread_id=THREAD,
                utc=utc(), event=ref(event_path), transport=ref(tp), handler_ack=ref(ackpath),
                original_writer_release_observed=bool(state.get('native_resume_started')),
                native_resume_started=bool(state.get('native_resume_started')),
                original_session_callback_verified=True, physical_window_closed_test=None,
                host_reboot_survival=False, scientific_compute=0), True)
        return state
    # Uncertainty after interrupted notification means reconcile by ACK/process
    # first; never launch a second writer just because a retry timer elapsed.
    process_alive = bool(state.get('resume_process') and alive(state['resume_process']))
    busy = writer_busy()
    action = choose(state, busy=busy, now=now, resume_alive=process_alive)
    if action not in ('queue', 'native_resume'):
        if state.get('state') != action:
            state.update(state=action, observed_utc=utc())
            write(tp, state)
        return state
    state.update(attempts=state.get('attempts', 0) + 1, state='sending',
                 next_unix=now + 600, utc=utc(), original_writer_busy=busy)
    # Persist intent before a possibly ambiguous response; restart won't replay
    # this send immediately. Only one sidecar holds daemon.lock.
    if action == 'queue':
        state['queue_sent'] = True
    write(tp, state)
    attempt = state['attempts']
    try:
        message = prompt(event_path, event)
        if action == 'queue':
            argv = ['codex', 'queue', '--thread', THREAD, '--message', message]
            r = subprocess.run(argv, cwd=WORKSPACE, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            write(folder / ('ATTEMPT_%d.json' % attempt), dict(
                transport='queue_existing_writer', exit_code=r.returncode,
                stdout=r.stdout[:8192], stderr=r.stderr[:8192], utc=utc()), True)
            if r.returncode:
                raise RuntimeError('queue CLI exit ' + str(r.returncode))
            state.update(state='transport_accepted_not_handler_ack', transport='queue_existing_writer')
        else:
            argv = ['codex', 'exec', 'resume', THREAD, '--json', '--skip-git-repo-check', message]
            with (folder / ('RESUME_%d.jsonl' % attempt)).open('xb') as so, \
                    (folder / ('RESUME_%d.stderr' % attempt)).open('xb') as se:
                p = subprocess.Popen(argv, cwd=WORKSPACE, stdin=subprocess.DEVNULL,
                                     stdout=so, stderr=se, start_new_session=True)
            state.update(state='native_resume_started_not_handler_ack', transport='native_resume',
                         native_resume_started=True, resume_process=identity(p.pid))
            write(folder / ('ATTEMPT_%d.json' % attempt), dict(
                transport='native_resume', argv=argv[:-1] + ['<persisted_event_prompt>'],
                process=state['resume_process'], utc=utc(), original_writer_busy=False), True)
    except Exception as error:
        state.update(state='transport_failed', error=dict(type=type(error).__name__, message=str(error)))
    write(tp, state)
    return state


def classify(reg, *, now, daemon_alive, heartbeat, result):
    if result is not None:
        return 'terminal_existing_notifier_owner'
    if not daemon_alive:
        return 'execution_unknown'
    stamp = datetime.datetime.fromisoformat(heartbeat['utc']).timestamp()
    if now - stamp > reg['heartbeat_stale_seconds']:
        return 'blocked_heartbeat_stale'
    if heartbeat.get('status') == 'blocked_retaining_reservation':
        return 'blocked_retaining_reservation'
    return 'running'


def observe(reg):
    job = Path(reg['root'])
    heartbeat = read(job / 'HEARTBEAT.json')
    result_path = job / 'chain/CHAIN_RESULT.json'
    result = read(result_path) if result_path.exists() else None
    kind = classify(reg, now=time.time(), daemon_alive=alive(reg['daemon']),
                    heartbeat=heartbeat, result=result)
    snapshot = dict(kind=kind, utc=utc(), heartbeat=heartbeat, result=ref(result_path) if result else None,
                    notification_owner=reg['notification_owner'], scientific_processes_modified=False)
    write(ROOT / 'OBSERVATION.json', snapshot)
    if kind == 'terminal_existing_notifier_owner':
        # No duplicate notification; the frozen service owns chain_terminal.
        if not (ROOT / 'TERMINAL_OBSERVED.json').exists():
            write(ROOT / 'TERMINAL_OBSERVED.json', dict(snapshot, outcome=result,
                  event_path=str(job / 'outbox/chain_terminal.json')), True)
        return
    if kind == 'running':
        return
    # A single urgent event coalesces both lost heartbeat and vanished daemon.
    event_path = ROOT / 'outbox/A_D24_MAIN_ONCE_V1_execution_unknown/EVENT.json'
    if not event_path.exists():
        write(event_path, dict(
            schema='corrector_terminal_event_v1', event_id='A_D24_MAIN_ONCE_V1_execution_unknown',
            node='A', hostname=HOST, executor_thread_id=THREAD, task_id='A_D24_MAIN_ONCE_V1',
            task_revision=1, run_id='A_D24_MAIN_ONCE_V1', attempt='whole_chain', synthetic=False,
            claim=reg['command'], authorization_sha256=WAKE_SHA,
            scientific_authorization=reg['scientific_authorization'], code=reg['code'],
            outcome=kind, exit_code=None, process_family_exit=None, publication_complete=None,
            occupancy_handoff=None, result_paths=[str(job / 'HEARTBEAT.json')],
            error_summary='Observer cannot establish terminal exit; never infer success or rerun.',
            utc=utc(), challenge=uuid.uuid4().hex), True)


def serve():
    verify()
    local = Path('/tmp/corrector_A_wakeup_adapter_v1')
    local.mkdir(exist_ok=True)
    lock = (local / 'daemon.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    own = identity()
    if own is None:
        raise RuntimeError('host process identity unavailable')
    ready = dict(status='OBSERVER_RUNNING_CALLBACK_UNVERIFIED', process=own, utc=utc(),
                 node='A', session=os.getsid(0), scientific_compute=0, hardware_queries=0,
                 notification_owner='own outbox only; main frozen notifier remains separate',
                 code=ref(PACKAGE / 'CODE_MANIFEST.json'), authorization_sha256=WAKE_SHA)
    write(ROOT / 'deployments' / (str(own['start_ticks']) + '.json'), ready, True)
    write(ROOT / 'DAEMON_READY.json', ready)
    while True:
        try:
            reg = read(ROOT / 'REGISTRATION.json')
            observe(reg)
            for event_path in sorted((ROOT / 'outbox').glob('*/EVENT.json')):
                deliver(event_path)
            write(ROOT / 'HEARTBEAT.json', dict(utc=utc(), process=own,
                  status='observing_existing_job', original_thread=THREAD, hardware_queries=0,
                  formal_launches=0, callback_ACK_observed=(ROOT / 'WAKEUP_READY.json').exists()))
        except Exception as error:
            write(ROOT / 'OBSERVER_ERROR.json', dict(utc=utc(), type=type(error).__name__, message=str(error)))
        time.sleep(15)


def start():
    verify()
    ready = ROOT / 'DAEMON_READY.json'
    if ready.exists() and alive(read(ready)['process']):
        print('ALREADY_RUNNING', read(ready)['process'])
        return 0
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'stdout.log').open('ab') as so, (ROOT / 'stderr.log').open('ab') as se:
        p = subprocess.Popen(['/usr/bin/python', '-B', str(Path(__file__).resolve()), 'serve'],
                             cwd=WORKSPACE, stdin=subprocess.DEVNULL, stdout=so, stderr=se,
                             start_new_session=True)
    print('SPAWNED_CPU_OBSERVER', p.pid)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'serve'])
    args = parser.parse_args()
    sys.exit(start() if args.action == 'start' else serve())
