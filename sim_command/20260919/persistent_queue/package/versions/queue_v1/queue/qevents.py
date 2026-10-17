"""Durable terminal outbox. Same app-server writer, fixed original thread only."""
import json
import fcntl
import os
import select
import socket
import subprocess
import time
from pathlib import Path
from qio import PACKAGE, QUEUE, CAMPAIGN, read, ref, verify, new_json, atomic_json, utc, process_identity, same_process
from qauthority import AUTH_SHA
WAKE_SHA='6cd1233b0e345bbea2a8320f6126897364c89c6964e92975be4d80c1291766f6'

def policy_document():
    return read(verify(dict(path='persistent_queue/LONG_TASK_EVENT_WAKEUP_V1.json',sha256=WAKE_SHA)))


def enqueue(node,job_id,*,outcome,proposal=None,launch=None,results=(),synthetic=False):
    policy=policy_document();binding=policy['nodes'][node]
    if socket.gethostname()!=binding['hostname']:raise ValueError('notification host mismatch')
    event_id=node+'__'+job_id+'__terminal_v1';root=QUEUE/'nodes'/node/'outbox'/event_id
    event=dict(schema='corrector_terminal_event_v1',event_id=event_id,node=node,hostname=socket.gethostname(),
        executor_thread_id=binding['executor_thread_id'],job_id=job_id,synthetic=synthetic,outcome=outcome,
        created_utc=utc(),authorization_sha256=AUTH_SHA,code_manifest=ref(PACKAGE/'RUNTIME_MANIFEST.json'),
        task_id=proposal['task_id'] if proposal else 'A_LONG_TASK_WAKEUP_V1' if node=='A' else 'B_LONG_TASK_WAKEUP_V1',
        task_revision=1,run_id=proposal['authorization_identity']['run_id'] if proposal else job_id,
        claim=proposal['paths']['claim'] if proposal else None,attempt='whole_batch_terminal',
        exit_code=None,process_group_exit=launch.get('process_exit_proven') if launch else None,
        publication_complete=launch.get('publication_complete') if launch else True,
        occupancy=launch.get('restoration') if launch else 'unchanged_CPU_callback',result_refs=list(results),
        error_summary=launch.get('primary') if launch else None)
    path=root/'EVENT.json'
    if path.exists():
        old=read(path)
        if any(old[k]!=event[k] for k in ('event_id','job_id','node','synthetic','outcome')):raise ValueError('terminal event identity conflict')
        return path
    if synthetic:
        prior=[p for p in (QUEUE/'nodes'/node/'outbox').glob('*/EVENT.json') if read(p).get('synthetic')]
        if len(prior)>=2:raise ValueError('two live CPU callback events per node maximum')
    new_json(path,event);new_json(root/'TRANSPORT.json',dict(state='pending',attempts=0,next_attempt_unix=time.time()+30))
    return path


class RPC:
    def __init__(self):
        self.p=subprocess.Popen(['codex','app-server','proxy'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,text=True,bufsize=1)
        self.n=0
        self.call('initialize',dict(clientInfo=dict(name='corrector-event-wakeup',version='1')))
        self.p.stdin.write(json.dumps(dict(jsonrpc='2.0',method='initialized',params={}))+'\n');self.p.stdin.flush()
    def call(self,method,params):
        self.n+=1;n=self.n
        self.p.stdin.write(json.dumps(dict(jsonrpc='2.0',id=n,method=method,params=params))+'\n');self.p.stdin.flush()
        end=time.monotonic()+15
        while time.monotonic()<end:
            if not select.select([self.p.stdout],[],[],1)[0]:continue
            line=self.p.stdout.readline()
            if not line:raise RuntimeError('local app-server proxy disconnected')
            row=json.loads(line)
            if row.get('id')==n:
                if 'error' in row:raise RuntimeError('local app-server RPC rejected: '+str(row['error']))
                return row['result']
        raise TimeoutError('local app-server RPC deadline')
    def close(self):
        if self.p.stdin:self.p.stdin.close()
        try:self.p.wait(timeout=2)
        except subprocess.TimeoutExpired:self.p.terminate();self.p.wait(timeout=5)


def writer_busy(thread_id):
    path=Path('/home/tiger/.codex/thread-writer-locks')/(thread_id+'.lock')
    with path.open('rb') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
        fcntl.flock(lock,fcntl.LOCK_UN)
    return False


def deliver(path, *, busy_fn=writer_busy, now=time.time):
    """CLI queue for the existing writer; native-lock-protected resume when unloaded.

    Checking flock does not grant ownership. codex exec resume must still acquire
    its native writer lock itself and is allowed to refuse the race. No bypass.
    """
    path=Path(path);root=path.parent;event=read(path);state=read(root/'TRANSPORT.json')
    binding=policy_document()['nodes'][event['node']]
    if event['hostname']!=socket.gethostname() or event['hostname']!=binding['hostname'] or event['executor_thread_id']!=binding['executor_thread_id'] or event['authorization_sha256']!=AUTH_SHA:
        raise ValueError('event node/host/fixed original thread/current authority mismatch')
    verify(event['code_manifest'])
    if (root/'HANDLER_ACK.json').exists():
        ack=read(root/'HANDLER_ACK.json')
        if ack.get('event_id')!=event['event_id'] or ack.get('executor_thread_id')!=event['executor_thread_id']:
            raise ValueError('callback ACK does not bind original event/thread')
        state.update(state='handler_acknowledged',handler_ack=ref(root/'HANDLER_ACK.json'))
        atomic_json(root/'TRANSPORT.json',state)
        return state
    if state['attempts']>=3 or now()<state['next_attempt_unix']:return state
    if state.get('resume_process') and same_process(state['resume_process']):return state
    attempted=False
    try:
        busy=busy_fn(event['executor_thread_id'])
        ackpath=root/'HANDLER_ACK.json'
        if event['synthetic']:
            message=('Corrector 后台唤醒自检，synthetic=true。仅执行以下控制面动作后结束，不运行实验：读取 '+str(path)+
                '，核对 event_id 与本会话 '+event['executor_thread_id']+'，若 '+str(ackpath)+
                ' 不存在则以排他创建写入小 JSON：event_id='+event['event_id']+', executor_thread_id='+event['executor_thread_id']+
                ', synthetic=true, handled=true, scientific_compute=0，并带 UTC。存在则核对后不重复。回复一句自检 ACK 即结束。')
        else:
            message=('Corrector 队列终局事件 '+event['event_id']+'，原会话自动唤醒。读取 '+str(path)+
                ' 核对本批身份/真实账本/退出发布和占卡；先按事件去重，写 '+str(ackpath)+
                '（绑定 event_id/executor_thread_id），补短 REPORT/RESULT。daemon可能已续批，不重复 launcher，不暂停正常续批；遵循当前授权门。')
        # Persist an attempt before sending; an ambiguous response is never a compute retry.
        state.update(state='transmitting',attempts=state['attempts']+1,next_attempt_unix=now()+[30,120,600][state['attempts']])
        atomic_json(root/'TRANSPORT.json',state);attempted=True
        if busy:
            argv=['codex','queue','--thread',event['executor_thread_id'],'--message',message]
            result=subprocess.run(argv,cwd=CAMPAIGN.parents[2],stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
            new_json(root/('ATTEMPT_%d.json'%state['attempts']),dict(transport='queue_existing_writer',exit_code=result.returncode,
                stdout=result.stdout[:16384],stderr=result.stderr[:16384],utc=utc(),handler_acknowledged=False))
            if result.returncode:raise RuntimeError('queue CLI returned '+str(result.returncode))
            state.update(state='transport_accepted',transport='queue_existing_writer',handler_acknowledged=False)
        else:
            argv=['codex','exec','resume',event['executor_thread_id'],'--json','--skip-git-repo-check',message]
            with (root/('RESUME_%d.jsonl'%state['attempts'])).open('xb') as so,(root/('RESUME_%d.stderr'%state['attempts'])).open('xb') as se:
                proc=subprocess.Popen(argv,cwd=CAMPAIGN.parents[2],stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
            state.update(state='resume_started_not_handler_ACK',transport='exec_resume_native_writer_lock',resume_process=process_identity(proc.pid))
        state.update(next_attempt_unix=max(state['next_attempt_unix'],now()+600),preserved_model_and_permissions=True)
    except BaseException as e:
        if not attempted:state['attempts']+=1
        state.update(state='transport_blocked',error=dict(type=type(e).__name__,message=str(e)),next_attempt_unix=now()+120)
    atomic_json(root/'TRANSPORT.json',state);return state


def pump(node):
    root=QUEUE/'nodes'/node
    if not (root/'WAKEUP_ARMED.json').exists():return
    for path in sorted((root/'outbox').glob('*/EVENT.json')):
        state=deliver(path)
        if state['state']=='handler_acknowledged' and read(path)['synthetic']:
            ready=root/'WAKEUP_READY.json'
            if not ready.exists():new_json(ready,dict(status='READY',node=node,host=socket.gethostname(),
                utc=utc(),authorization_sha256=AUTH_SHA,event=ref(path),transport=ref(path.parent/'TRANSPORT.json'),
                handler_ack=ref(path.parent/'HANDLER_ACK.json'),scope='same original app-server thread, detached notifier and disconnected RPC client',
                physical_terminal_window_closed_during_test=None,host_restart_survival=False))
