"""Durable fixed-thread notifications; transport receipt is not a handler ACK."""
import fcntl
import json
import socket
import subprocess
import time
from pathlib import Path
from paths import ROOT,WORKSPACE
from qio import read,new_json,atomic_json,process_identity,same_process,utc

THREAD='01a0b91f-7443-71b1-915d-6cdb6d6a1a13'


def pump():
    for event_path in sorted((ROOT/'outbox').glob('*.json')):
        event=read(event_path);rec=ROOT/'notifications'/event_path.stem;rec.mkdir(parents=True,exist_ok=True)
        state=read(rec/'TRANSPORT.json') if (rec/'TRANSPORT.json').exists() else dict(attempts=0,state='pending',next=0)
        if (rec/'HANDLER_ACK.json').exists():continue
        if state['attempts']>=3 or time.time()<state['next']:continue
        if state.get('process') and same_process(state['process']):continue
        try:
            with (Path('/home/tiger/.codex/thread-writer-locks')/(THREAD+'.lock')).open('rb') as lock:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);busy=False;fcntl.flock(lock,fcntl.LOCK_UN)
                except BlockingIOError:busy=True
            message=('Corrector A 持久后台终局通知。固定原会话 '+THREAD+'。读取 '+str(event_path)+
                '，按 event_id 去重并写 '+str(rec/'HANDLER_ACK.json')+'。synthetic=true 时仅核对并写ACK后结束，实际计算为0。'
                '真实事件按已保存结果补短回执；不要重复已完成episode、不要停止正常后台任务。当前任务 A_D24_MULTI_PRIMARY_VALIDATION_V1；保持原后台链，禁止重复已完成单元或自行新增配置。')
            state.update(attempts=state['attempts']+1,state='sending',next=time.time()+600,utc=utc())
            atomic_json(rec/'TRANSPORT.json',state)
            if busy:
                result=subprocess.run(['codex','queue','--thread',THREAD,'--message',message],cwd=WORKSPACE,
                    stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
                new_json(rec/('attempt%d.json'%state['attempts']),dict(exit_code=result.returncode,stdout=result.stdout[:8192],stderr=result.stderr[:8192],transport='existing_writer_queue'))
                if result.returncode:raise RuntimeError('queue CLI failed')
                state.update(state='transport_accepted_not_handler_ack')
            else:
                with (rec/('attempt%d.jsonl'%state['attempts'])).open('xb') as so,(rec/('attempt%d.stderr'%state['attempts'])).open('xb') as se:
                    proc=subprocess.Popen(['codex','exec','resume',THREAD,'--json','--skip-git-repo-check',message],cwd=WORKSPACE,
                        stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
                state.update(state='original_thread_resume_started_not_handler_ack',process=process_identity(proc.pid))
        except BaseException as e:state.update(state='transport_failed',error=dict(type=type(e).__name__,message=str(e)),next=time.time()+600)
        atomic_json(rec/'TRANSPORT.json',state)

