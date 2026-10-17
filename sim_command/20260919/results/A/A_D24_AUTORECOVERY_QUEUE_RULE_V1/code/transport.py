"""Existing fixed-thread queue/resume transport; no callback self-test."""
import fcntl
import subprocess
import time
from pathlib import Path
from policy import ROOT, WORKSPACE, THREAD, ANALYSIS_THREAD, TASK
from qio import read, new_json, atomic_json, same_process, process_identity, utc


def emit(event_id, kind, evidence, *, analysis=False):
    target = ROOT/'outbox'/(event_id+'.json')
    if target.exists():
        return target
    new_json(target, dict(event_id=event_id, kind=kind, evidence=evidence, utc=utc(),
                         synthetic=False, scientific_compute_added=0,
                         target_thread=ANALYSIS_THREAD if analysis else THREAD,
                         task_id=TASK))
    return target


def pump():
    for p in sorted((ROOT/'outbox').glob('*.json')):
        event = read(p); thread = event['target_thread']
        if thread not in [THREAD, ANALYSIS_THREAD]:
            raise ValueError('foreign notification thread')
        rec = ROOT/'notifications'/p.stem; rec.mkdir(exist_ok=True)
        if (rec/'HANDLER_ACK.json').exists():
            continue
        state = read(rec/'TRANSPORT.json') if (rec/'TRANSPORT.json').exists() else dict(attempts=0,next=0)
        cap = 1 if thread == ANALYSIS_THREAD else 3
        if state['attempts'] >= cap or time.time() < state['next']:
            continue
        if state.get('process') and same_process(state['process']):
            continue
        message = ('Corrector A 自主恢复控制面事件。读取 '+str(p)+'，按 event_id 去重写 '
                   +str(rec/'HANDLER_ACK.json')+'。按 AUTONOMOUS_RECOVERY_AND_SKIP_V1 处理已有授权未完成 unit；'
                   '先核对真实进程/合法终局，健康链不重复、不停止。工程故障私有修复后注册带依据的有限接续包；'
                   '科学决定需 issue，普通ACK不是决定。Post完整dev选loss、fit9101及所有权/预算不变。'
                   '这是故障/依赖通知，不新增科学范围；禁止递归回调或创建替代会话。')
        if thread == ANALYSIS_THREAD:
            message = 'Corrector A 问题上报（一次投递）：'+str(p)+'。issue内1800秒期限固定；普通ACK不重置期限。请在issue旁 .decision.json 写可执行决定及引用。'
        state.update(attempts=state['attempts']+1, next=time.time()+600, utc=utc())
        atomic_json(rec/'TRANSPORT.json',state)
        try:
            busy = True
            lockpath=Path('/home/tiger/.codex/thread-writer-locks')/(thread+'.lock')
            if thread == THREAD and lockpath.exists():
                with lockpath.open('rb') as lock:
                    try:
                        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        busy=False;fcntl.flock(lock,fcntl.LOCK_UN)
                    except BlockingIOError:
                        pass
            if busy or thread == ANALYSIS_THREAD:
                r=subprocess.run(['codex','queue','--thread',thread,'--message',message],cwd=WORKSPACE,
                                 stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 text=True,timeout=30)
                new_json(rec/f"attempt{state['attempts']}.json",dict(exit_code=r.returncode,stdout=r.stdout[-8192:],stderr=r.stderr[-8192:],transport='queue'))
                state['status']='transport_accepted_not_handler_ACK' if r.returncode==0 else 'transport_failed'
            else:
                with (rec/f"attempt{state['attempts']}.jsonl").open('xb') as out,(rec/f"attempt{state['attempts']}.stderr").open('xb') as err:
                    proc=subprocess.Popen(['codex','exec','resume',thread,'--json','--skip-git-repo-check',message],cwd=WORKSPACE,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
                state.update(status='original_thread_resume_started_not_handler_ACK',process=process_identity(proc.pid))
        except Exception as e:
            state.update(status='transport_failed',error=dict(type=type(e).__name__,message=str(e)))
        atomic_json(rec/'TRANSPORT.json',state)
