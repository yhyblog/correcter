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
DISCOVERY = None


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
    if job['task_id'] not in ('C_D24_MW_VELOCITY_V1','C_D24_BASELINE_GAPS_E8_TABLES_V1','C_D24_R_H40_H50_V1','C_D24_R_TRIGGER_MODES_V1','C_D24_XVLA_AUX_RETRAIN_V1','C_D24_XVLA_MULTI_EVAL_V1','C_D24_FULL_Q_LOSS_REFRESH_V1','C_D24_PI05_SELECTED_H40_H50_V1','C_D24_AUTORECOVERY_QUEUE_RULE_V1','C_D24_QUOTA_INDEPENDENT_QUEUE_V1','C_D24_L11_RETEST_V1','C_D24_L11_RENDER_RECOVERY_V1'):raise ValueError('Wrong C task')
    if not Path(job['result_path']).is_relative_to(d.C/'results/C'):raise ValueError('Not a C result')
    job['armed_from_turn_id']=thread_state()['turn_id']
    p=STATE/'jobs'/(job['job_id']+'.json')
    if not p.exists():d.exclusive(p,job)
    return str(p)


def message(event):
    if event.get('event_type')=='task_available':
        from task_discovery import task_message
        return task_message(event,d.W)
    eid=event['event_id'];p=STATE/'outbox'/(eid+'.json')
    command=f'/usr/bin/python {d.W}/wakeup.py ack --event-id {eid}'
    if event['synthetic']:
        return (f'C 本机授权的短终局通知自检，synthetic=true。固定原线程 {THREAD}；事件 {p}。'
                f'请只核对事件并执行 {command} --outcome selftest_ack_only，然后简短结束本轮。'
                '不启动实验，不做 GPU 探针，不轮询，不再投递唤醒事件。')
    if event['job']['task_id']=='C_D24_L11_RENDER_RECOVERY_V1':
        return (f'C L11 渲染恢复终局事件 {eid}。读取 {p} 和引用的小结果，核对唯一claim、1764条授权恢复清单、736条既有有效结果保护、累计尝试预算、L11/fit9101、观测归属和干预前证据、实际并发与全部调用成本、正式全族退出及holder恢复。'
                '完成C_D24_L11_RENDER_RECOVERY_V1的逐源唯一有效结果、原始尝试链和五cell汇总；Post入当前论文，Velocity单独保存。旧L01、旧raw和失败均保留，未知与技术故障不算任务失败；禁止重训/采集/重跑合法终局，必要私有修正接续依现行授权。'
                f'将审计写在C自有目录后执行 {command} --outcome audited --audit PATH。正常授权队列无需二次放行。不要因本回调结束递归唤醒。')
    if event['job']['task_id']=='C_D24_L11_RETEST_V1':
        return (f'C L11 正式重测终局事件 {eid}。读取 {p} 和引用的小结果，核对唯一claim、owner=C的2500单元、L11/fit9101、实际并发/成本、逐源终局、正式全族退出及holder恢复。'
                '汇总C_D24_L11_RETEST_V1的X Post/Velocity H10、pi05 Post/Velocity H40及Velocity H50，保留旧L01，Post入当前论文、Velocity单独保存；未知不算失败，禁止重训/采集/重跑合法终局。'
                f'将审计写在C自有目录后执行 {command} --outcome audited --audit PATH。正常授权队列无需二次放行。不要因回调结束递归唤醒。')
    if event['job']['task_id']=='C_D24_QUOTA_INDEPENDENT_QUEUE_V1':
        return (f'C CPU自动队列监督终局事件 {eid}。读取 {p} 和引用的小结果，核查原科学claim、后台自动衔接、逐源去重、有限修正接续及CPU表。'
                '任务 C_D24_QUOTA_INDEPENDENT_QUEUE_V1：只核查/修复已授权控制逻辑；所有合法终局禁止重跑，未知不计失败。通知不是科学队列的启动条件。'
                f'将审计写在C自有目录后执行 {command} --outcome audited --audit PATH。不要因本回调结束再投递唤醒。')
    if event['job']['task_id']=='C_D24_AUTORECOVERY_QUEUE_RULE_V1':
        return (f'C CPU伴随任务终局事件 {eid}。读取 {p} 和引用的小结果，核对控制服务claim、issue计时和投递、Post选择兼容记录与已有队列实际状态。'
                '任务 C_D24_AUTORECOVERY_QUEUE_RULE_V1：只审计/修复CPU监督逻辑，新增GPU调用与科学计算为0；保持健康科学队列，禁止重跑已完成源。'
                f'将审计写在C自有目录后执行 {command} --outcome audited --audit PATH。不要仅因本回调结束再投递唤醒。')
    if event['job']['task_id']=='C_D24_PI05_SELECTED_H40_H50_V1':
        return (f'C 本机批次终局事件 {eid}。读取 {p} 和引用的小结果，核对 C 唯一claim、A Post-only开发选择锁、精确TRANSFER_READY源归属、原X任务全族退出、H40/H50各Post/Velocity终局和全部正式后代退出及占卡恢复。'
                '完成 C_D24_PI05_SELECTED_H40_H50_V1：汇总所选A π0.5 Q fit9101的H40/H50结果和既有N/R配对、逐次cut/C10/first_cut及所有调用成本。Post进入当前论文，Velocity单独保存。不得重训、重采或重跑已完成源。技术故障和未知不算任务失败，必要修正接续遵守现行授权和预算。'
                f'将审计写在C自有目录后执行 {command} --outcome audited --audit PATH。正常授权队列无需分析放行；不要因回调结束递归唤醒。')
    if event['job']['task_id']=='C_D24_FULL_Q_LOSS_REFRESH_V1':
        return (f'C 本机批次终局事件 {eid}。读取 {p} 和引用的小结果，核对既有claim、完整Q16fits/64000更新、A锁定开发选择和本机同loss四成员、Post/Velocity各500终局、正式后代退出及占卡恢复。'
                '任务 C_D24_FULL_Q_LOSS_REFRESH_V1：完成新Q验证汇总及与已有N/R和旧Q结果配对；禁止重复已完成源、旧N/R或训练。未完成不算失败，每失败源最多一次明确修正重试。'
                f'将审计写在C自有目录后执行 {command} --outcome audited --audit PATH。正常队列无需分析放行；不要因回调结束递归唤醒。')
    if event['job']['task_id']=='C_D24_XVLA_MULTI_EVAL_V1':
        return (f'C 本机批次终局事件 {eid}。读取 {p} 和引用的小结果，核对 C 既有 claim、每源终局、正式后代退出与占卡恢复，禁止重复计算。'
                '完成 C_D24_XVLA_MULTI_EVAL_V1：固定专属 D2/G02/Q4 的 R/Post/Velocity G0-multi 各500，与对应 once/N 配对，汇总逐次触发与全部调用成本。'
                '核对 C10 禁止重入、first_cut 和每次 cut 的记录；不得重采、重训、重跑旧N或任何已完成源。未知结果不算失败，每失败源最多一次明确修正重试。'
                f'将审计写在 C 自有目录后执行 {command} --outcome audited --audit PATH。'
                '正常队列无需分析放行。不要因回调结束递归唤醒。')
    return (f'C 本机批次终局事件 {eid}。读取 {p} 和所引用的小结果，核对 C 既有 claim、'
            '每源终局、正式后代退出与占卡恢复，禁止重复计算。按事件 task_id 完成对应 C 任务：C_D24_XVLA_AUX_RETRAIN_V1 按任务书核对专属采集、D/G0/Q训练及新R/Post/Velocity验证，禁止重跑旧N；C_D24_R_TRIGGER_MODES_V1 汇总 R 两种触发模式的五H共5000回合及每格相对冻结 G0-once 的配对、触发和调用成本；C_D24_R_H40_H50_V1 需汇总 R_H40/H50 各500源并与已完成同H N/Post/Velocity 配对；C_D24_BASELINE_GAPS_E8_TABLES_V1 处理原E8表格依赖。已完成1000条Velocity、5条N补跑和5个未知源禁止重放；'
            f'将审计写在 C 自有目录后执行 {command} --outcome audited --audit PATH。'
            '遵守各源最多一次明确修正重试；已成功源不重放。正常队列无需分析放行。不要因回调结束递归唤醒。')


def dispatch(event):
    task_event=event.get('event_type')=='task_available'
    if task_event and (DISCOVERY is None or not DISCOVERY.event_allowed(event)):return
    eid=event['event_id'];record=STATE/'delivery'/(eid+'.json')
    if (STATE/'handler_acks'/(eid+'.json')).exists():return
    if record.exists():
        prev=d.load(record);proc=CHILDREN.get(eid)
        if proc is not None and proc.poll() is not None:
            prev.update(status='transport_accepted' if proc.returncode==0 else 'transport_failed',
                        exit_code=proc.returncode,at_utc=d.utc(),transport_accepted=d.utc() if proc.returncode==0 else None)
            d.atomic(record,prev);del CHILDREN[eid]
        return  # Never blindly resend an uncertain notification.
    for other in (STATE/'delivery').glob('*.json'):
        if not task_event and not (STATE/'handler_acks'/other.name).exists():
            return  # One outstanding delivery owns the original session.
    turn=thread_state()
    busy=turn['status'] not in ('completed','failed','interrupted')
    if busy and not task_event:return
    locked=writer_locked()
    if event['required_transport']=='exec_resume' and locked:return
    if profile()!=d.load(STATE/'ORIGINAL_THREAD_PROFILE.json'):
        raise RuntimeError('Original thread profile changed; no permission override')
    active_transport=any(proc.poll() is None for proc in CHILDREN.values())
    for other in (STATE/'delivery').glob('*.json'):
        prior=d.load(other)
        if prior.get('route')=='exec_resume' and prior.get('process') and d.alive(prior['process']):active_transport=True
    route='queue' if locked or busy or active_transport else 'exec_resume'
    prompt=message(event)
    argv=([CODEX,'queue','--thread',THREAD,'--message',prompt] if locked else
          [CODEX,'exec','resume',THREAD,prompt,'--json'])
    entered=dict(event_id=eid,status='dispatch_entered',route=route,at_utc=d.utc(),
                 original_turn=turn,writer_locked=locked,automatic_resend=False,transport_entered=d.utc(),event_type=event.get('event_type','batch_terminal'))
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
    event_turn=turn['turn_id'] if any(eid in x['item_json'] for x in items) else None
    # An explicit "continue" can resume the immediately preceding failed
    # task-delivery turn. Require the real event in that original thread's
    # user input; never substitute transport success or a fabricated message.
    if event_turn is None and e.get('event_type')=='task_available' and not e['synthetic']:
        texts=[part.get('text','').strip().lower() for x in items
               for part in json.loads(x['item_json']).get('content',[]) if part.get('type')=='text']
        recent=query('thread_history_1.sqlite',
            'select turn_id,status from thread_turns where thread_id=? order by rollout_ordinal desc limit 2',(THREAD,))
        if texts and all(t in ('继续','continue','resume') for t in texts) and len(recent)==2 and recent[0]['turn_id']==turn['turn_id'] and recent[1]['status'] in ('failed','interrupted'):
            previous=query('thread_history_1.sqlite','select item_json from thread_items where thread_id=? and turn_id=? and item_type=?',
                           (THREAD,recent[1]['turn_id'],'userMessage'))
            if any(eid in x['item_json'] for x in previous):event_turn=recent[1]['turn_id']
    if turn['status']!='inProgress' or event_turn is None:
        raise RuntimeError('No event-bearing active original handler turn')
    if turn['turn_id']==e.get('job',{}).get('armed_from_turn_id'):
        raise RuntimeError('Arming turn cannot acknowledge its own future callback')
    if e['synthetic']:
        if outcome!='selftest_ack_only':raise ValueError('Synthetic ACK only')
    else:
        if audit is None or not Path(audit).resolve().is_relative_to(d.C):raise ValueError('C audit required')
        if not any(Path(audit).resolve().is_relative_to(d.C/p) for p in ['work/C','results/C','receipts/C']):
            raise ValueError('Audit must be C-owned')
    value=dict(event_id=eid,node='C',executor_thread_id=THREAD,handler_turn_id=turn['turn_id'],
        at_utc=d.utc(),outcome=outcome,audit=audit,synthetic=e['synthetic'],
        actual_original_handler_verified=True,event_input_turn_id=event_turn,
        continued_after_failed_event_turn=event_turn!=turn['turn_id'],
        transport=d.load(STATE/'delivery'/(eid+'.json')))
    p=STATE/'handler_acks'/(eid+'.json')
    if not p.exists():d.exclusive(p,value)
    if e.get('event_type')=='task_available':
        proof=dict(event_id=eid,task_id=e['task']['task_id'],handler_ACK=str(p),
                   actual_original_handler_verified=True,at_utc=d.load(p)['at_utc'])
        d.atomic(STATE/'task_discovery'/(eid+'_HANDLER_ACK_OBSERVED.json'),proof)
        result=d.C/'receipts/C/C_TASK_DISCOVERY_SERVICE_V1_RESULT.json'
        if result.exists():
            summary=d.load(result)
            summary.update(end_to_end_task_available_ACK_verified=True,actual_task_available_ACK=proof,
                           verification_status='actual new dispatch ACK verified on original thread')
            d.atomic(result,summary)
    return value


def daemon():
    global DISCOVERY
    from task_discovery import Discovery
    DISCOVERY=Discovery()
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
                DISCOVERY.poll()
                for p in sorted((STATE/'jobs').glob('*.json')):
                    job=d.load(p)
                    if job.get('notification_coalesced_into'):
                        next_job=d.load(STATE/'jobs'/(job['notification_coalesced_into']+'.json'))
                        if next_job['task_id']!=job['task_id'] or next_job['revision']!=job['revision']:
                            raise RuntimeError('Invalid cross-task notification coalescing')
                        continue
                    if d.alive(job['process_identity']):continue
                    result=d.load(job['result_path']) if Path(job['result_path']).exists() else dict(status='execution_unknown',reason='supervisor exited without terminal publication')
                    emit(job,result)
                for p in sorted((STATE/'outbox').glob('*.json')):
                    dispatch(d.load(p))
                proofs=[d.load(p) for p in (STATE/'handler_acks').glob('*.json')]
                d.atomic(STATE/'HEARTBEAT.json',dict(at_utc=d.utc(),process=d.identity(),status='supervising',
                    original_thread=THREAD,actual_handler_ACKs=len(proofs),
                    unattended_fixed_thread_resume_verified=any(x['transport']['route']=='exec_resume' for x in proofs),
                    interactive_queue_ACK_verified=any(x['transport']['route']=='queue' for x in proofs),
                    task_discovery=DISCOVERY.last_scan,scientific_launches_by_discovery=0,
                    actual_task_available_ACKs=sum(1 for x in proofs if (STATE/'outbox'/(x['event_id']+'.json')).exists() and d.load(STATE/'outbox'/(x['event_id']+'.json')).get('event_type')=='task_available')))
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
