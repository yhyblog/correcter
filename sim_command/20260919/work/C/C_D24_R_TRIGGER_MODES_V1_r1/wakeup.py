"""C host-scoped terminal observer; resumes only the original executor UUID."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
import d24_common as d

STATE = d.C/'persistent_queue/nodes/C/wakeup'
CODEX = '/home/tiger/.local/bin/codex'
CD = Path('/home/tiger/.codex')
THREAD = '01a0c793-10d2-7791-a250-fd65d88e1ccb'
CHILDREN = {}


def query(name, sql, args=()):
    db=sqlite3.connect('file:'+str(CD/name)+'?mode=ro',uri=True,timeout=3)
    db.row_factory=sqlite3.Row
    try:return [dict(row) for row in db.execute(sql,args)]
    finally:db.close()


def thread_state():
    return query('thread_history_1.sqlite',
        'select turn_id,status from thread_turns where thread_id=? order by rollout_ordinal desc limit 1',(THREAD,))[0]


def profile():
    return query('state_5.sqlite',
        'select id,model,reasoning_effort,cwd,sandbox_policy,approval_mode from threads where id=?',(THREAD,))[0]


def check_identity():
    ident=d.load(d.C/'nodes/C/identity.json')
    if ident['hostname']!=os.uname().nodename or ident['executor_thread_id']!=THREAD:
        raise RuntimeError('C notification host/thread mismatch')
    if ident['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise RuntimeError('C reboot requires explicit recovery reconciliation')


def writer_locked():
    p=CD/'thread-writer-locks'/(THREAD+'.lock')
    if not p.exists():return False
    with p.open('r') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
        fcntl.flock(f,fcntl.LOCK_UN)
    return False


def emit(job, result, synthetic=False, route='auto'):
    token=json.dumps(dict(node='C',thread=THREAD,job=job['job_id'],run=job['run_id'],
                         outcome=result['status'],route=route),sort_keys=True)
    eid='C_'+hashlib.sha256(token.encode()).hexdigest()[:32]
    p=STATE/'outbox'/(eid+'.json')
    if not p.exists():
        d.exclusive(p,dict(event_id=eid,node='C',hostname=d.HOST,executor_thread_id=THREAD,
            created_at_utc=d.utc(),job=job,result=result,synthetic=synthetic,required_transport=route))
    return eid


def register(manifest):
    check_identity()
    job=d.load(manifest)
    if job['task_id'] not in ('C_D24_MW_VELOCITY_V1','C_D24_BASELINE_GAPS_E8_TABLES_V1','C_D24_R_H40_H50_V1','C_D24_R_TRIGGER_MODES_V1'):raise ValueError('Wrong C task')
    if not Path(job['result_path']).is_relative_to(d.C/'results/C'):raise ValueError('Not a C result')
    job['armed_from_turn_id']=thread_state()['turn_id']
    p=STATE/'jobs'/(job['job_id']+'.json')
    if not p.exists():d.exclusive(p,job)
    return str(p)


def message(event):
    eid=event['event_id'];p=STATE/'outbox'/(eid+'.json')
    command=f'/usr/bin/python {d.W}/wakeup.py ack --event-id {eid}'
    if event['synthetic']:
        return (f'C 本机授权的短终局通知自检，synthetic=true。固定原线程 {THREAD}；事件 {p}。'
                f'请只核对事件并执行 {command} --outcome selftest_ack_only，然后简短结束本轮。'
                '不启动实验，不做 GPU 探针，不轮询，不再投递唤醒事件。')
    return (f'C 本机批次终局事件 {eid}。读取 {p} 和所引用的小结果，核对 C 既有 claim、'
            '每源终局、正式后代退出与占卡恢复，禁止重复计算。按事件 task_id 完成对应 C 任务：C_D24_R_TRIGGER_MODES_V1 汇总 R 两种触发模式的五H共5000回合及每格相对冻结 G0-once 的配对、触发和调用成本；C_D24_R_H40_H50_V1 需汇总 R_H40/H50 各500源并与已完成同H N/Post/Velocity 配对；C_D24_BASELINE_GAPS_E8_TABLES_V1 处理原E8表格依赖。已完成1000条Velocity、5条N补跑和5个未知源禁止重放；'
            f'将审计写在 C 自有目录后执行 {command} --outcome audited --audit PATH。'
            '遵守各源最多一次明确修正重试；已成功源不重放。正常队列无需分析放行。不要因回调结束递归唤醒。')


def dispatch(event):
    eid=event['event_id'];record=STATE/'delivery'/(eid+'.json')
    if (STATE/'handler_acks'/(eid+'.json')).exists():return
    if record.exists():
        prev=d.load(record);proc=CHILDREN.get(eid)
        if proc is not None and proc.poll() is not None:
            prev.update(status='transport_accepted' if proc.returncode==0 else 'transport_failed',
                        exit_code=proc.returncode,at_utc=d.utc())
            d.atomic(record,prev);del CHILDREN[eid]
        return  # Never blindly resend an uncertain notification.
    for other in (STATE/'delivery').glob('*.json'):
        if not (STATE/'handler_acks'/other.name).exists():
            return  # One outstanding delivery owns the original session.
    turn=thread_state()
    if turn['status'] not in ('completed','failed','interrupted'):return
    locked=writer_locked()
    if event['required_transport']=='exec_resume' and locked:return
    if profile()!=d.load(STATE/'ORIGINAL_THREAD_PROFILE.json'):
        raise RuntimeError('Original thread profile changed; no permission override')
    route='queue' if locked else 'exec_resume'
    prompt=message(event)
    argv=([CODEX,'queue','--thread',THREAD,'--message',prompt] if locked else
          [CODEX,'exec','resume',THREAD,prompt,'--json'])
    entered=dict(event_id=eid,status='dispatch_entered',route=route,at_utc=d.utc(),
                 original_turn=turn,writer_locked=locked,automatic_resend=False)
    d.exclusive(record,entered)
    with (STATE/'delivery'/(eid+'.log')).open('ab') as log:
        proc=subprocess.Popen(argv,cwd=d.ROOT,stdin=subprocess.DEVNULL,stdout=log,
            stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
    CHILDREN[eid]=proc
    entered.update(status='execution_in_progress',process=d.identity(proc.pid))
    d.atomic(record,entered)


def ack(eid,outcome,audit=None):
    check_identity()
    if os.environ.get('CODEX_THREAD_ID')!=THREAD:raise RuntimeError('ACK requires the original thread')
    if not eid.startswith('C_') or not eid[2:].isalnum():raise ValueError('Invalid event ID')
    e=d.load(STATE/'outbox'/(eid+'.json'));turn=thread_state()
    items=query('thread_history_1.sqlite','select item_json from thread_items where thread_id=? and turn_id=? and item_type=?',
                (THREAD,turn['turn_id'],'userMessage'))
    if turn['status']!='inProgress' or not any(eid in x['item_json'] for x in items):
        raise RuntimeError('No event-bearing active original handler turn')
    if turn['turn_id']==e['job'].get('armed_from_turn_id'):
        raise RuntimeError('Arming turn cannot acknowledge its own future callback')
    if e['synthetic']:
        if outcome!='selftest_ack_only':raise ValueError('Synthetic ACK only')
    else:
        if audit is None or not Path(audit).resolve().is_relative_to(d.C):raise ValueError('C audit required')
        if not any(Path(audit).resolve().is_relative_to(d.C/p) for p in ['work/C','results/C','receipts/C']):
            raise ValueError('Audit must be C-owned')
    value=dict(event_id=eid,node='C',executor_thread_id=THREAD,handler_turn_id=turn['turn_id'],
        at_utc=d.utc(),outcome=outcome,audit=audit,synthetic=e['synthetic'],
        actual_original_handler_verified=True,transport=d.load(STATE/'delivery'/(eid+'.json')))
    p=STATE/'handler_acks'/(eid+'.json')
    if not p.exists():d.exclusive(p,value)
    return value


def daemon():
    check_identity()
    with (STATE/'notifier.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        d.atomic(STATE/'PROCESS.json',d.identity())
        running=True
        def stop(*_):
            nonlocal running
            running=False
        for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
        while running and not (STATE/'STOP.json').exists():
            try:
                check_identity()
                for p in sorted((STATE/'jobs').glob('*.json')):
                    job=d.load(p)
                    if d.alive(job['process_identity']):continue
                    result=d.load(job['result_path']) if Path(job['result_path']).exists() else dict(status='execution_unknown',reason='supervisor exited without terminal publication')
                    emit(job,result)
                for p in sorted((STATE/'outbox').glob('*.json')):
                    dispatch(d.load(p))
                proofs=[d.load(p) for p in (STATE/'handler_acks').glob('*.json')]
                d.atomic(STATE/'HEARTBEAT.json',dict(at_utc=d.utc(),process=d.identity(),status='supervising',
                    original_thread=THREAD,actual_handler_ACKs=len(proofs),
                    unattended_fixed_thread_resume_verified=any(x['transport']['route']=='exec_resume' for x in proofs),
                    interactive_queue_ACK_verified=any(x['transport']['route']=='queue' for x in proofs)))
            except Exception as exc:
                d.atomic(STATE/'ERROR.json',dict(at_utc=d.utc(),error=repr(exc)))
            time.sleep(5)


def start():
    check_identity()
    p=STATE/'PROCESS.json'
    if p.exists() and d.alive(d.load(p)):
        return dict(status='already_running',process=d.load(p))
    if profile()!=d.load(STATE/'ORIGINAL_THREAD_PROFILE.json'):
        raise RuntimeError('Original profile changed; no override')
    with (STATE/'notifier.log').open('a') as log:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(Path(__file__).resolve()),'daemon'],cwd=d.W,
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    result=dict(status='C_task_extension_preserving_original_thread',process=d.identity(proc.pid),
                node='C',hostname=d.HOST,executor_thread_id=THREAD,at_utc=d.utc(),
                new_synthetic_events=0, preserved_pending_events=True)
    d.atomic(STATE/'SERVICE_REGISTRATION.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['start','daemon','register','ack'])
    p.add_argument('--manifest');p.add_argument('--event-id');p.add_argument('--outcome');p.add_argument('--audit')
    a=p.parse_args()
    result=register(a.manifest) if a.command=='register' else ack(a.event_id,a.outcome,a.audit) if a.command=='ack' else globals()[a.command]()
    print(json.dumps(result,indent=2))
