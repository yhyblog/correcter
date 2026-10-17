"""Authorized persistent CPU control plane. This program cannot launch experiments.

It observes shared JSON, publishes a real process heartbeat and routes bounded
synthetic callback tests to the original node's executor. No GPU/holder command,
formal lock, experiment claim, model or environment import exists here.
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

PACKAGE=Path(__file__).resolve().parent
QUEUE=PACKAGE.parent
AUTH_SHA='d73448042b71ecb06940e8d891caf0ef8bef005018f155ee2743903981992928'
WAKE_SHA='6cd1233b0e345bbea2a8320f6126897364c89c6964e92975be4d80c1291766f6'


def read(path):return json.loads(Path(path).read_text())
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value,exclusive=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path if exclusive else path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    if not exclusive:os.replace(temp,path)


def identity(pid=None):
    pid=os.getpid() if pid is None else pid
    try:
        st=Path('/proc',str(pid),'stat').read_text().rsplit(') ',1)[1].split()
        return dict(pid=pid,start_ticks=int(st[19]),pgid=int(st[2]),ppid=int(st[1]),state=st[0],
            boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),host=socket.gethostname())
    except OSError:return None


def alive(saved):
    row=identity(saved['pid'])
    return bool(row and row['state']!='Z' and all(row[k]==saved[k] for k in ('pid','start_ticks','boot_id','host')))


def verify(node):
    path=QUEUE/'AUTHORIZATION_V2.json'
    if sha(path)!=AUTH_SHA:raise ValueError('unknown control authority')
    auth=read(path)
    if auth['hosts'][node]!=socket.gethostname():raise ValueError('wrong node host')
    wake=QUEUE/'LONG_TASK_EVENT_WAKEUP_V1.json'
    if sha(wake)!=WAKE_SHA:raise ValueError('unknown notification policy')
    return read(wake)['nodes'][node]


def callbacks(node,root,binding):
    events=list((root/'outbox').glob('*/EVENT.json'))
    if len(events)>2:raise RuntimeError('at most two CPU callback tests')
    thread=binding['executor_thread_id']
    for path in sorted(events):
        event=read(path);folder=path.parent;ack=folder/'HANDLER_ACK.json'
        if event.get('synthetic') is not True or event['executor_thread_id']!=thread:raise ValueError('only fixed-thread CPU synthetic events here')
        if ack.exists():
            a=read(ack)
            if a.get('event_id')!=event['event_id'] or a.get('executor_thread_id')!=thread:raise ValueError('callback ACK identity mismatch')
            write(root/'WAKEUP_READY.json',dict(status='ACK_OBSERVED',event_id=event['event_id'],executor_thread_id=thread,
                event=str(path),handler_ack=str(ack),utc=utc(),scientific_compute=0,
                physical_window_closed_test=None,host_reboot_survival=False))
            continue
        transport=folder/'TRANSPORT.json'
        state=read(transport) if transport.exists() else dict(attempts=0,next_unix=event.get('deliver_after_unix',0))
        if state['attempts']>=3 or time.time()<state['next_unix']:continue
        if state.get('process') and alive(state['process']):continue
        with (Path('/home/tiger/.codex/thread-writer-locks')/(thread+'.lock')).open('rb') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);busy=False;fcntl.flock(lock,fcntl.LOCK_UN)
            except BlockingIOError:busy=True
        state.update(attempts=state['attempts']+1,state='sending',next_unix=time.time()+600,utc=utc());write(transport,state)
        message=('Corrector 后台控制面 synthetic 唤醒自检。原会话 '+thread+'。仅读取 '+str(path)+'，以排他创建写 '+str(ack)+
            '：event_id='+event['event_id']+', executor_thread_id='+thread+', synthetic=true, handled=true, scientific_compute=0 和 UTC；若存在则核对。'
            '不执行实验，不改变任何计算授权；这不是对 D24 评测审批问题的用户回复。完成短 ACK 后保持原任务状态。')
        try:
            if busy:
                result=subprocess.run(['codex','queue','--thread',thread,'--message',message],
                    stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
                write(folder/('ATTEMPT_'+str(state['attempts'])+'.json'),dict(exit_code=result.returncode,stdout=result.stdout[:8192],stderr=result.stderr[:8192],transport='existing_writer_queue'),True)
                if result.returncode:raise RuntimeError('queue transport refused')
                state.update(state='transport_accepted_not_handler_ack',transport='existing_writer_queue')
            else:
                with (folder/('RESUME_'+str(state['attempts'])+'.jsonl')).open('xb') as so,(folder/('RESUME_'+str(state['attempts'])+'.stderr')).open('xb') as se:
                    proc=subprocess.Popen(['codex','exec','resume',thread,'--json','--skip-git-repo-check',message],
                        stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
                state.update(state='resume_started_not_handler_ack',process=identity(proc.pid),transport='native_locked_same_thread_resume')
        except BaseException as e:state.update(state='transport_failed',error=dict(type=type(e).__name__,message=str(e)))
        write(transport,state)


def serve(node):
    binding=verify(node);root=QUEUE/'nodes'/node/'control_only_v1';root.mkdir(parents=True,exist_ok=True)
    local=Path('/tmp')/('corrector_queue_control_only_'+node);local.mkdir(exist_ok=True)
    lock=(local/'daemon.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    own=identity();ready=dict(status='READY_CONTROL_ONLY',node=node,process=own,utc=utc(),
        authorization_sha256=AUTH_SHA,program_sha256=sha(__file__),scientific_dispatch_enabled=False,
        formal_claims_created=0,GPU_or_holder_calls=0,stdin='DEVNULL',session=os.getsid(0),host_restart_requires_start=True)
    write(root/'deployments'/(str(own['start_ticks'])+'.json'),ready,True);write(root/'DAEMON_READY.json',ready)
    while True:
        control=read(QUEUE/'CONTROL.json')
        write(root/'HEARTBEAT.json',dict(node=node,process=own,utc=utc(),status='CPU_CONTROL_ONLY',
            observed_control_revision=control['revision'],observed_priority_task=control['nodes'][node].get('priority_task'),
            scientific_dispatch_enabled=False,formal_claims_created=0,GPU_or_holder_calls=0))
        try:callbacks(node,root,binding)
        except BaseException as e:write(root/'CALLBACK_ERROR.json',dict(type=type(e).__name__,message=str(e),utc=utc()))
        time.sleep(5)


def start(node):
    verify(node);root=QUEUE/'nodes'/node/'control_only_v1';root.mkdir(parents=True,exist_ok=True)
    ready=root/'DAEMON_READY.json'
    if ready.exists() and alive(read(ready)['process']):print('ALREADY_RUNNING',read(ready)['process']);return 0
    with (root/'stdout.log').open('ab') as so,(root/'stderr.log').open('ab') as se:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(Path(__file__).resolve()),'serve','--node',node],
            stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    print('SPAWNED_CPU_CONTROL_ONLY',proc.pid);return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','serve']);parser.add_argument('--node',choices=['A','B'],required=True)
    a=parser.parse_args();sys.exit(start(a.node) if a.action=='start' else serve(a.node))
