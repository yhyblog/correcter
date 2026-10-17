#!/usr/bin/python
"""B-only persistent completion observer; no GPU or experiment-launch code.

The existing TUI consumes `codex queue` after its active turn ends. When its
writer lock is free, `codex exec resume` resumes exactly the original UUID.
Transport acceptance is never promoted to handler acknowledgement.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timezone

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang')
C=ROOT/'Corrector/sim_command/20260919'
Q=C/'persistent_queue'
HERE=Path(__file__).resolve().parent
STATE=Q/'nodes/B/wakeup'
CODEX=Path('/home/tiger/.local/bin/codex')
CD=Path('/home/tiger/.codex')
HOST='trial-303225685-trialrun-303225685-worker-0'
THREAD='01a0b9c5-1e4b-7b73-9336-229e6df349a2'
AUTH_SHA='6cd1233b0e345bbea2a8320f6126897364c89c6964e92975be4d80c1291766f6'
SCIENCE_SHA='d73448042b71ecb06940e8d891caf0ef8bef005018f155ee2743903981992928'


def utc():return datetime.now(timezone.utc).isoformat()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def sha(p):return digest(Path(p).read_bytes())
def small(p):
    p=Path(p)
    if p.stat().st_size>4*1024*1024:raise ValueError('control-plane file exceeds 4MiB')
    return load(p)
def atomic(p,v,exclusive=False):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp.'+uuid.uuid4().hex)
    with t.open('x') as f:
        json.dump(v,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    try:
        if exclusive:os.link(t,p)
        else:os.replace(t,p)
        fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:t.unlink(missing_ok=True)
def identity(pid=None):
    pid=pid or os.getpid();v=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return dict(hostname=os.uname().nodename,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),pid=pid,start_ticks=int(v[19]),session_id=os.getsid(pid))
def alive(v):
    try:
        if Path(f"/proc/{v['pid']}/stat").read_text().rsplit(')',1)[1].split()[0]=='Z':return False
        a=identity(v['pid'])
        return all(v.get(k)==a[k] for k in ['hostname','boot_id','pid','start_ticks'])
    except (OSError,KeyError,ValueError):return False
def local_lock(name):
    p=Path('/tmp/corrector_B_event_wakeup')/name;p.parent.mkdir(exist_ok=True)
    return p.open('a')
def validate_id(v):
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,120}',v):raise ValueError('invalid identifier')
    return v


def authority():
    if os.uname().nodename!=HOST:raise PermissionError('B host mismatch')
    ctrl=load(Q/'CONTROL.json');ref=ctrl['completion_event_policy']
    if ref['sha256']!=AUTH_SHA or sha(C/ref['path'])!=AUTH_SHA:raise PermissionError('current event authorization mismatch')
    a=load(C/ref['path'])
    for ref in [a['contract'],a['base_scientific_authorization'],a['task_briefs']['B']]:
        if sha(C/ref['path'])!=ref['sha256']:raise PermissionError('frozen event contract changed')
    if a['nodes']['B']!={'hostname':HOST,'executor_thread_id':THREAD,'task':'B_LONG_TASK_WAKEUP_V1'}:raise PermissionError('original executor identity mismatch')
    if ctrl['authorization']['sha256']!=SCIENCE_SHA:raise PermissionError('science authority changed; reconcile observer')
    return ctrl


def read_sql(name,sql,args):
    con=sqlite3.connect('file:'+str(CD/name)+'?mode=ro',uri=True,timeout=3);con.row_factory=sqlite3.Row
    try:return [dict(r) for r in con.execute(sql,args)]
    finally:con.close()
def thread_state():
    rows=read_sql('thread_history_1.sqlite','select turn_id,status,started_at,completed_at from thread_turns where thread_id=? order by rollout_ordinal desc limit 1',(THREAD,))
    if not rows:raise RuntimeError('original thread turn history unavailable')
    return rows[0]
def thread_profile():
    rows=read_sql('state_5.sqlite','select id,model,reasoning_effort,cwd,sandbox_policy,approval_mode,cli_version from threads where id=?',(THREAD,))
    if not rows:raise RuntimeError('original thread missing')
    row=rows[0];row['sandbox_policy']=json.loads(row['sandbox_policy'])
    expected=load(HERE/'ORIGINAL_THREAD_PROFILE.json')
    for k in ['id','model','reasoning_effort','cwd','sandbox_policy','approval_mode']:
        if row[k]!=expected[k]:raise PermissionError('original thread profile changed: '+k)
    return row
def writer_locked():
    p=CD/'thread-writer-locks'/(THREAD+'.lock')
    if not p.exists():return False
    with p.open('r') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
        fcntl.flock(f,fcntl.LOCK_UN);return False
def transport_choice(turn,locked,required='auto'):
    if turn.get('status')=='inProgress':return None,'original turn active; preserve single writer'
    if turn.get('status') not in ('completed','interrupted','failed'):return None,'unknown original turn state'
    if required=='exec_resume' and locked:return None,'offline self-test waits until original writer releases normally'
    return ('queue' if locked else 'exec_resume'),None


def emit(state,job,outcome,terminal_token,*,synthetic=False,required_transport='auto',extra=None):
    identity_data=dict(node='B',thread=THREAD,job=job['job_id'],run=job['run_id'],attempt=job.get('attempt',1),terminal=terminal_token)
    event_id='B_'+digest(json.dumps(identity_data,sort_keys=True).encode())[:32]
    p=state/'outbox'/f'{event_id}.json'
    if p.exists():return load(p)
    value=dict(schema='corrector_terminal_event_v1',event_id=event_id,node='B',hostname=HOST,executor_thread_id=THREAD,
        task_id=job['task_id'],revision=job.get('revision',1),run_id=job['run_id'],attempt=job.get('attempt',1),job_id=job['job_id'],
        claim_identity=job.get('claim_identity'),authorization_sha256=AUTH_SHA,science_authorization_sha256=SCIENCE_SHA,
        code_ref=dict(path=str(Path(__file__).resolve()),sha256=sha(__file__)),outcome=outcome,exit_code=None,
        process_family_exited=None,publication_complete=None,occupancy_handoff_complete=None,
        result_path=job.get('result_path'),error_summary_path=job.get('error_summary_path'),
        created_at_utc=utc(),created_at_unix=time.time(),synthetic=synthetic,
        required_transport=required_transport,armed_from_turn_id=job.get('armed_from_turn_id'))
    value.update(extra or {})
    atomic(p,value,exclusive=True);return value


def message(event):
    ep=STATE/'outbox'/(event['event_id']+'.json')
    if event['synthetic']:
        return (f"B_LONG_TASK_WAKEUP_V1 授权的短控制面自检，synthetic=true。固定原线程 {THREAD}，event_id={event['event_id']}。"
                f"只核对事件 {ep}，在原会话调用 /usr/bin/python {HERE/'wakeup.py'} ack --event-id {event['event_id']} --outcome selftest_ack_only，"
                "然后简短结束本轮。不要运行实验、GPU探针、全量盘点或轮询，也不要再投递唤醒消息；后台自己保存 ACK/验收状态。")
    return (f"B 本机持久完成事件 event_id={event['event_id']}；task={event['task_id']}，run={event['run_id']}，outcome={event['outcome']}。"
            f"读取 {ep} 及其小结果引用，先核对当前 CONTROL、既有 claim 和正在运行的队列，不重复启动。按既有授权审计/继续；"
            f"把审计写入 B 自有文件后调用 /usr/bin/python {HERE/'wakeup.py'} ack --event-id {event['event_id']} --outcome audited_complete --audit PATH。"
            "若仍阻塞用 --outcome blocked，unknown 用 execution_unknown。只在后台稳定且触发器登记后结束轮次；A不等待B。")


def dispatch(state,event,turn,locked):
    event_id=event['event_id'];directory=state/'delivery'/event_id;directory.mkdir(parents=True,exist_ok=True)
    record=directory/'STATE.json'
    if (state/'handler_acks'/f'{event_id}.json').exists():return 'handler_acknowledged'
    if record.exists():
        previous=load(record)
        if previous['status'] in ['transport_accepted','execution_in_progress','delivery_unknown','transport_failed','dispatch_entered']:
            return previous['status']  # No blind resend on uncertain delivery.
    route,reason=transport_choice(turn,locked,event.get('required_transport','auto'))
    if route is None:return reason
    if event.get('armed_from_turn_id')==turn['turn_id'] and turn['status']=='inProgress':return 'arming turn still active'
    # Metadata/profile checks happen before creating a durable notification
    # claim. CLI and built-in thread writer lock are the final atomic race gate.
    thread_profile();authority()
    prompt=message(event)
    argv=[str(CODEX),'queue','--thread',THREAD,'--message',prompt] if route=='queue' else [str(CODEX),'exec','resume',THREAD,prompt,'--json']
    claim=dict(status='dispatch_entered',event_id=event_id,route=route,attempts=1,max_attempts=1 if event['synthetic'] else 3,
        entered_at_utc=utc(),before_turn=turn,writer_locked=locked,argv=argv,cwd=str(ROOT),
        automatic_resend=False,reason='uncertain dispatch requires reconciliation; notification retry never repeats compute')
    atomic(record,claim,exclusive=True)
    with (directory/'transport.log').open('ab',buffering=0) as log:
        try:
            proc=subprocess.Popen(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
            claim.update(status='execution_in_progress',process_identity=identity(proc.pid))
            atomic(record,claim)
            # Keep only the owned transport subprocess in memory. No child or
            # unrelated writer is signaled by this notifier.
            TRANSPORTS[event_id]=proc
        except Exception as exc:
            claim.update(status='delivery_unknown',error=type(exc).__name__+': '+str(exc));atomic(record,claim)
    return claim['status']


TRANSPORTS={}
def reconcile_transports(state):
    for p in sorted((state/'delivery').glob('*/STATE.json')):
        v=load(p);event_id=v['event_id'];ack=state/'handler_acks'/f'{event_id}.json'
        if ack.exists():
            if v['status']!='handler_acknowledged':v.update(status='handler_acknowledged',handler_ack=str(ack));atomic(p,v)
            child=TRANSPORTS.get(event_id)
            if child and child.poll() is not None:TRANSPORTS.pop(event_id,None)
            continue
        child=TRANSPORTS.get(event_id)
        if child is not None:
            code=child.poll()
            if code is not None:
                v.update(status='transport_accepted' if code==0 else 'transport_failed',exit_code=code,transport_exited_at_utc=utc())
                atomic(p,v);TRANSPORTS.pop(event_id,None)
        elif v['status']=='execution_in_progress' and not alive(v.get('process_identity',{})):
            v.update(status='delivery_unknown',reason='notifier restarted or transport exited without durable exit status; reconcile, never infer ACK')
            atomic(p,v)
        elif v['status']=='dispatch_entered':
            v.update(status='delivery_unknown',reason='crash across transport enter; do not automatically resend');atomic(p,v)


def dependency_snapshot():
    ctrl=load(Q/'CONTROL.json');ready=Q/'package/READY.json'
    board=load(C/'TASK_BOARD.json');items=board.get('tasks',[])
    if isinstance(items,dict):items=[dict(v,id=k) for k,v in items.items()]
    tasks=[]
    for t in items:
        if t.get('owner')!='B' or t.get('id')=='B_LONG_TASK_WAKEUP_V1' or t.get('status')!='ready' or not t.get('release'):continue
        expected=t.get('expected_result',t.get('result'))
        if expected and (C/expected).exists():continue
        tasks.append({k:t.get(k) for k in ['id','revision','release','brief','expected_result']})
    grants=ctrl.get('stage_authorizations',[])
    return dict(package_sha256=sha(ready) if ready.is_file() and ready.stat().st_size<=4*1024*1024 else None,
                B_ready_tasks=tasks,stage_authorizations=grants)
def observe_dependencies(state):
    current=dependency_snapshot();p=state/'DEPENDENCIES.json'
    if not p.exists():atomic(p,current);return
    previous=load(p)
    if previous!=current:
        token=digest(json.dumps(current,sort_keys=True).encode())
        snapshot=state/'dependency_changes'/f'{token}.json';atomic(snapshot,current)
        job=dict(task_id='B_QUEUE_JOIN_V1',revision=2,job_id='B_dependency_change',run_id=token,result_path=str(snapshot))
        emit(state,job,'dependency_changed',token)
        atomic(p,current)
def terminal_job(job,is_alive,result):
    if result is not None:
        status=result.get('status')
        if status in ('complete','completed','failed','partial','blocked','timeout','cancelled') and not is_alive:return status
    if not is_alive:return 'execution_unknown'
    return None
def observe_jobs(state):
    for path in sorted((state/'jobs').glob('*.json')):
        job=load(path);p=Path(job['result_path']);result=small(p) if p.is_file() else None
        outcome=terminal_job(job,alive(job['process_identity']),result)
        if outcome:
            # One stable terminal ID per admitted attempt, even if later audit
            # augments result bytes. Terminal accounting is not inferred from PID.
            extra=dict(exit_code=(result or {}).get('exit_code'),root_process_exited=True,
                process_family_exited=(result or {}).get('all_owned_descendants_exited'),
                publication_complete=(result or {}).get('publication_completed'),
                occupancy_handoff_complete=(result or {}).get('occupancy_handoff_complete'))
            emit(state,job,outcome,'terminal_for_registered_attempt',extra=extra)


def acknowledge(event_id,outcome,audit=None):
    validate_id(event_id);authority()
    if os.environ.get('CODEX_THREAD_ID')!=THREAD:raise PermissionError('ACK must run in original executor thread')
    ep=STATE/'outbox'/f'{event_id}.json';e=load(ep);turn=thread_state()
    if turn['status']!='inProgress' or turn['turn_id']==e.get('armed_from_turn_id'):raise PermissionError('ACK needs a new active original-thread callback turn')
    items=read_sql('thread_history_1.sqlite','select item_json from thread_items where thread_id=? and turn_id=? and item_type=?',(THREAD,turn['turn_id'],'userMessage'))
    if not any(event_id in r['item_json'] for r in items):raise PermissionError('event ID absent from original handler turn input')
    if e['synthetic'] and outcome!='selftest_ack_only':raise PermissionError('synthetic callback is ACK only')
    audit_ref=None
    if not e['synthetic']:
        if audit is None:raise PermissionError('real event needs an audit/result reference')
        audit=Path(audit).resolve()
        if not any(audit.is_relative_to((C/x).resolve()) for x in ['work/B','results/B','receipts/B','persistent_queue/nodes/B']):raise PermissionError('B-owned audit only')
        audit_ref=dict(path=str(audit),sha256=sha(audit))
    p=STATE/'handler_acks'/f'{event_id}.json'
    if p.exists():return load(p)
    ack=dict(schema='corrector_original_handler_ack_v1',event_id=event_id,node='B',hostname=HOST,executor_thread_id=THREAD,
        handler_turn_id=turn['turn_id'],event_id_verified_in_original_turn_input=True,at_utc=utc(),outcome=outcome,synthetic=e['synthetic'],
        event_sha256=sha(ep),audit=audit_ref,scientific_operations=0 if e['synthetic'] else None)
    claim=STATE/'handler_claims'/f'{event_id}.json'
    # Single-writer original thread plus a verified new input permits finishing
    # a pure metadata ACK interrupted after its claim. Never rerun compute.
    if not claim.exists():atomic(claim,dict(turn_id=turn['turn_id'],at_utc=utc()),exclusive=True)
    else:ack['prior_handler_claim']=load(claim)
    atomic(p,ack,exclusive=True);atomic(STATE/'handled'/f'{event_id}.json',ack,exclusive=True)
    return ack


def readiness(state):
    proofs=[]
    for p in (state/'handler_acks').glob('*.json'):
        ack=load(p)
        if ack.get('synthetic'):
            delivery=load(state/'delivery'/ack['event_id']/'STATE.json')
            proofs.append(dict(event_id=ack['event_id'],route=delivery['route'],handler_ack_path=str(p),handler_ack_sha256=sha(p),handler_turn_id=ack['handler_turn_id']))
    queue_ok=any(p['route']=='queue' for p in proofs);offline_ok=any(p['route']=='exec_resume' for p in proofs)
    value=dict(node='B',executor_thread_id=THREAD,status='ready' if offline_ok else 'original_thread_ACK_verified_offline_pending' if queue_ok else 'installed_waiting_real_handler_ACK',
        real_handler_ACK_verified=bool(proofs),unattended_after_turn_verified=bool(proofs),
        fixed_UUID_headless_resume_verified=offline_ok,interactive_writer_route_verified=queue_ok,
        physical_terminal_disconnect_observed=False,proofs=proofs,at_utc=utc(),
        limitation='No forced terminal close; headless selftest waits for normal original writer exit. Host reboot requires verified restart; no OS autostart installed.')
    atomic(state/'WAKEUP_STATUS.json',value)
    if offline_ok and not (state/'WAKEUP_READY.json').exists():atomic(state/'WAKEUP_READY.json',value,exclusive=True)
    return value


def publish_validation_status(value):
    install=HERE/'INSTALL_RESULT.json'
    if not install.exists():return
    target=C/'receipts/B/B_LONG_TASK_WAKEUP_V1_RESULT.json'
    previous=load(target) if target.exists() else {}
    key=dict(status=value['status'],proofs=value['proofs'])
    if previous.get('live_validation')==key:return
    result=load(install)
    result.update(status='complete' if value['status']=='ready' else 'pending_live_validation',
        live_validation=key,updated_at_utc=utc(),actual_handler_ACK_verified=value['real_handler_ACK_verified'],
        headless_original_thread_resume_verified=value['fixed_UUID_headless_resume_verified'],
        wakeup_ready=(STATE/'WAKEUP_READY.json').exists(),
        remaining=[] if value['status']=='ready' else ['real original-thread callback ACK; offline resume after normal writer release' if not value['proofs'] else 'offline fixed-thread resume validation after normal original writer release'])
    atomic(target,result)


def daemon():
    authority();STATE.mkdir(parents=True,exist_ok=True)
    for d in ['outbox','delivery','handler_acks','handler_claims','handled','jobs','dependency_changes']:(STATE/d).mkdir(exist_ok=True)
    with local_lock('singleton.lock') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        atomic(STATE/'PROCESS.json',identity());stop=False;cycles=0
        def halt(*_):
            nonlocal stop
            stop=True
        for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,halt)
        while not stop and not (STATE/'STOP.json').exists():
            try:
                authority();observe_jobs(STATE);observe_dependencies(STATE);reconcile_transports(STATE)
                turn=thread_state();locked=writer_locked();notes={}
                handoff=STATE/'STABLE_HANDOFF.json'
                if handoff.exists():
                    for path in sorted((STATE/'outbox').glob('*.json')):
                        event=load(path)
                        # At most one notification may own/queue this original
                        # thread at once. Reconcile an actual ACK before another.
                        inflight=[load(p) for p in (STATE/'delivery').glob('*/STATE.json') if load(p).get('status') in ('execution_in_progress','transport_accepted','dispatch_entered','delivery_unknown') and not (STATE/'handler_acks'/(p.parent.name+'.json')).exists()]
                        if inflight and event['event_id'] not in [i['event_id'] for i in inflight]:notes[event['event_id']]='another event awaiting original-handler ACK';continue
                        notes[event['event_id']]=dispatch(STATE,event,turn,locked)
                        if notes[event['event_id']]=='execution_in_progress':break
                cycles+=1;ready=readiness(STATE)
                publish_validation_status(ready)
                atomic(STATE/'HEARTBEAT.json',dict(at_utc=utc(),identity=identity(),cycles=cycles,state='supervising',original_turn=turn,writer_locked=locked,event_states=notes,wakeup_readiness=ready['status'],scientific_model_calls=0))
            except Exception as exc:
                atomic(STATE/'HEARTBEAT.json',dict(at_utc=utc(),identity=identity(),cycles=cycles,state='blocked_control_plane',error=type(exc).__name__+': '+str(exc),scientific_model_calls=0))
            for _ in range(15):
                if stop or (STATE/'STOP.json').exists():break
                time.sleep(1)
        atomic(STATE/'STOPPED.json',dict(at_utc=utc(),identity=identity(),scope='notifier only; no transport/experiment/guard signaled'))


def start():
    authority();STATE.mkdir(parents=True,exist_ok=True)
    with local_lock('startup.lock') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        p=STATE/'PROCESS.json'
        if p.exists() and alive(load(p)):return dict(status='already_running',identity=load(p))
        if (STATE/'STOP.json').exists():raise RuntimeError('explicit notifier STOP present; reconcile before resume')
        with (STATE/'notifier.log').open('ab',buffering=0) as log:
            child=subprocess.Popen(['/usr/bin/python',str(HERE/'wakeup.py'),'daemon'],cwd=HERE,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
        for _ in range(50):
            if p.exists() and load(p).get('pid')==child.pid and alive(load(p)):return dict(status='started',identity=load(p))
            if child.poll() is not None:break
            time.sleep(.1)
        raise RuntimeError('notifier start not confirmed')


def arm():
    authority();turn=thread_state()
    if turn['status']!='inProgress':raise RuntimeError('arm from the active authorized original turn')
    existing=[load(p) for p in (STATE/'outbox').glob('*.json') if load(p).get('synthetic')]
    if existing:return dict(status='already_armed',events=[e['event_id'] for e in existing])
    events=[]
    for number,route in [(1,'auto'),(2,'exec_resume')]:
        job=dict(task_id='B_LONG_TASK_WAKEUP_V1',revision=1,job_id=f'B_wakeup_selftest_{number}',run_id=f'B_original_thread_callback_{number}',attempt=1,armed_from_turn_id=turn['turn_id'])
        events.append(emit(STATE,job,'synthetic_callback','fixed_selftest_'+str(number),synthetic=True,required_transport=route)['event_id'])
    return dict(status='armed',events=events,max_live_synthetic_events=2)


def register(path):
    authority();path=Path(path).resolve()
    if not any(path.is_relative_to((C/x).resolve()) for x in ['work/B','results/B','persistent_queue/nodes/B']):raise PermissionError('B-owned manifest only')
    job=small(path);validate_id(job['job_id']);validate_id(job['run_id'])
    if job['task_id']=='B_LONG_TASK_WAKEUP_V1':raise PermissionError('never watch notifier/callback completion')
    for k in ['task_id','revision','run_id','attempt','claim_identity','process_identity','result_path']:
        if k not in job:raise ValueError('missing registry field: '+k)
    for key in ['result_path','error_summary_path']:
        if job.get(key) and not any(Path(job[key]).resolve().is_relative_to((C/x).resolve()) for x in ['work/B','results/B','receipts/B','persistent_queue/nodes/B']):raise PermissionError('result reference must be B-owned')
    if not alive(job['process_identity']):raise PermissionError('register only identity-verified live admitted process')
    job['registration_manifest']=dict(path=str(path),sha256=sha(path));job['registered_at_utc']=utc()
    target=STATE/'jobs'/(job['job_id']+'__'+job['run_id']+'__'+str(job['attempt'])+'.json')
    if target.exists():return dict(status='already_registered',path=str(target))
    atomic(target,job,exclusive=True);return dict(status='registered',path=str(target))


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['start','daemon','status','stop','arm-selftests','ack','register']);p.add_argument('--event-id');p.add_argument('--outcome',choices=['selftest_ack_only','audited_complete','audited_partial','blocked','execution_unknown']);p.add_argument('--audit');p.add_argument('--manifest');a=p.parse_args()
    if a.command=='daemon':daemon();return
    if a.command=='start':value=start()
    elif a.command=='arm-selftests':value=arm()
    elif a.command=='register':value=register(a.manifest)
    elif a.command=='ack':value=acknowledge(a.event_id,a.outcome,a.audit)
    elif a.command=='stop':atomic(STATE/'STOP.json',dict(at_utc=utc(),scope='B notifier only'));value=dict(status='stop_requested')
    else:
        value=load(STATE/'HEARTBEAT.json') if (STATE/'HEARTBEAT.json').exists() else dict(state='not_started')
        value['alive']=alive(load(STATE/'PROCESS.json')) if (STATE/'PROCESS.json').exists() else False
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
