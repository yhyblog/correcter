"""One bounded CPU-only terminal-file observer. Never starts scientific work."""
import datetime as dt
import fcntl
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

from paper_results import BASE, ROOT, WORK, WS, TASK, THREAD, DEADLINE, RECEIPTS, atomic, utc, publish, normalize

OBS=ROOT/'observer'
NODES={
    'B':dict(task='B_D24_R_H20_H30_V1',horizons=[20,30],summary='FINAL_SUMMARY.json',episodes='FINAL_EPISODES.csv'),
    'C':dict(task='C_D24_R_H40_H50_V1',horizons=[40,50],summary='SUMMARY.json',episodes='EPISODES.csv'),
}


def load(path):
    if path.stat().st_size>64*1024**2:raise ValueError('Scalar control file unexpectedly large')
    return json.loads(path.read_text())


def identity(pid=None):
    pid=os.getpid() if pid is None else pid
    fields=Path('/proc',str(pid),'stat').read_text().rsplit(') ',1)[1].split()
    return dict(pid=pid,start_ticks=int(fields[19]),host=socket.gethostname(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),state=fields[0])


def notify(pub, kind, error=None):
    """Actual dispatch to the fixed original thread, not an invented handler ACK."""
    event_id=f'{TASK}_{kind}_r{pub["revision"]}'
    outbox=ROOT/'outbox';outbox.mkdir(exist_ok=True)
    ep=outbox/(event_id+'.json')
    rec=ROOT/'notifications'/event_id;rec.mkdir(parents=True,exist_ok=True)
    if ep.exists():return
    event=dict(event_id=event_id,synthetic=False,kind=kind,task_id=TASK,utc=utc(),
        publication=pub['path'],revision=pub['revision'],scientific_compute=0,
        error=error,executor_thread_id=THREAD,
        handler_scope='Read publication, deduplicate event and write CPU receipt/ACK only; never launch experiments')
    with ep.open('x') as f:json.dump(event,f,ensure_ascii=False,indent=2)
    message=(f'Corrector A 论文表图 CPU 增补通知。固定原会话 {THREAD}。读取 {ep}，按 event_id 去重并写 '
        f'{rec / "HANDLER_ACK.json"}。仅核对已发布表图并补短回执；scientific_compute=0。'
        '本事件不授权模型、仿真、训练、LIBERO重跑、R评测或占卡变更。后台观察器若仍在运行继续原实例，不重复部署。')
    transport=dict(utc=utc(),attempts=1,handler_ACK_observed=False,event_id=event_id)
    try:
        lock_path=Path('/home/tiger/.codex/thread-writer-locks')/(THREAD+'.lock')
        with lock_path.open('rb') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);busy=False;fcntl.flock(lock,fcntl.LOCK_UN)
            except BlockingIOError:busy=True
        if busy:
            r=subprocess.run(['codex','queue','--thread',THREAD,'--message',message],cwd=WS,
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
            transport.update(state='queued_not_handler_ACK' if r.returncode==0 else 'transport_failed',
                returncode=r.returncode,stdout=r.stdout[:8192],stderr=r.stderr[:8192])
        else:
            with (rec/'resume.jsonl').open('xb') as so,(rec/'resume.stderr').open('xb') as se:
                p=subprocess.Popen(['codex','exec','resume',THREAD,'--json','--skip-git-repo-check',message],
                    cwd=WS,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,close_fds=True)
            transport.update(state='original_thread_resume_started_not_handler_ACK',process=identity(p.pid))
    except Exception as exc:
        transport.update(state='transport_failed',error=repr(exc))
    atomic(rec/'TRANSPORT.json',transport)


def latest_root(node):
    spec=NODES[node];root=BASE/'results'/node/spec['task'];marker=root/'LATEST_RUN.json'
    saved=marker.read_bytes() if marker.exists() else None
    if saved:
        meta=json.loads(saved);candidate=Path(meta['results']).resolve()
        candidate.relative_to(root.resolve())
        if meta.get('task_id')!=spec['task']:raise ValueError('Latest-run task identity mismatch')
        root=candidate
    return root,marker,saved


def terminal(node):
    import csv
    spec=NODES[node];root,marker,old=latest_root(node)
    result_path=root/'RESULT.json';summary_path=root/spec['summary'];csv_path=root/spec['episodes']
    if not result_path.exists():return None
    result=load(result_path)
    if result.get('task_id')!=spec['task']:raise ValueError('Wrong terminal task_id')
    if not (result.get('all_owned_descendants_exited') is True and result.get('publication_completed') is True):
        return None
    if result.get('status') not in ['complete','partial_or_failed','failed','partial','SCIENTIFIC_GAP']:
        return None
    if not summary_path.exists() or not csv_path.exists():return None
    summary=load(summary_path)
    if summary.get('task_id')!=spec['task']:raise ValueError('Wrong summary task identity')
    if node=='C' and summary.get('terminal') is not True:return None
    if node=='B' and summary.get('status') not in ['complete','partial_or_failed','failed','partial']:return None
    if csv_path.stat().st_size>64*1024**2:raise ValueError('Episode CSV too large for scalar-only observer')
    with csv_path.open(newline='') as f:data=list(csv.DictReader(f))
    if (marker.read_bytes() if marker.exists() else None)!=old:return None
    cells=summary['cells'];cells=list(cells.values()) if isinstance(cells,dict) else cells
    good={h:[] for h in spec['horizons']};keys=set()
    for raw in data:
        h=int(raw['H']);sid=raw['source_id']
        if h not in good or raw['method']!='R':raise ValueError('Unexpected source-method unit')
        if (h,sid) in keys:raise ValueError('Duplicate terminal source in CSV')
        keys.add((h,sid))
        if raw.get('status')=='complete' and raw.get('technical_failure') in (None,''):
            r=normalize(raw)
            if (float(r['control_hz']),float(r['physics_hz']),float(r['action_scale']),int(r['max_interventions']))!=(30,400,.015,1):
                raise ValueError('Native scalar protocol mismatch')
            good[h].append(r)
    tech={};attempts={};valid={};success={}
    for c in cells:
        h=int(c['H'])
        if h not in good:raise ValueError('Wrong summary H')
        expected=int(c['valid']);observed=good[h]
        if len(observed)!=expected or sum(x['success'] for x in observed)!=int(c['successes']):
            raise ValueError('Published CSV denominator/success mismatch')
        tech[str(h)]=c.get('technical_failures');attempts[str(h)]=c.get('attempts',c.get('entered_episodes'))
        valid[str(h)]=expected;success[str(h)]=c['successes']
    if len(valid)!=2:raise ValueError('Missing cell in terminal summary')
    return dict(state='consumed',node=node,task_id=spec['task'],horizons=spec['horizons'],
        consumed_at_utc=utc(),run_directory=str(root),terminal_path=str(result_path),summary_path=str(summary_path),
        episodes_path=str(csv_path),terminal_status=result['status'],terminal_utc=result.get('utc',result.get('at_utc')),
        terminal_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
        episodes_sha256=hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        valid_by_H=valid,success_by_H=success,technical_failures_by_H=tech,attempts_by_H=attempts,
        scientific_compute=0,reason=None if sum(valid.values())==1000 else 'Terminal valid subset; missing outcomes remain NR')


def receipt(pub, state, observer_status):
    rev=pub['revision'];result=ROOT/f'APPEND_RESULT_r{rev}.json'
    payload=dict(task_id=TASK,utc=utc(),status=observer_status,publication=str(ROOT/'PUBLICATION.json'),
        publication_snapshot=str(ROOT/'revisions'/f'r{rev:02d}'/'PUBLICATION.json'),
        complete_main_cells=pub['complete_main_cells'],valid_main_episodes=pub['valid_main_episodes'],
        terminal_consumptions=state,observer=identity(),scientific_compute=0,holder_changes=0)
    atomic(result,payload)
    atomic(RECEIPTS/f'{TASK}_OBSERVER_RESULT_r{rev}.json',payload)
    return dict(revision=rev,path=payload['publication_snapshot'])


def main():
    OBS.mkdir(parents=True,exist_ok=True)
    # Independent CPU control lock, never the GPU guard's formal.lock.
    with Path('/tmp/A_D24_PAPER_RESULTS_ASSEMBLY_V1_observer.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Existing CPU observer owns this task')
        if (OBS/'TERMINAL.json').exists():raise SystemExit('Observer already terminal; not restarting')
        state=load(OBS/'CONSUMPTIONS.json') if (OBS/'CONSUMPTIONS.json').exists() else {}
        me=identity();deadline=dt.datetime.fromisoformat(DEADLINE).timestamp()
        ready=dict(task_id=TASK,utc=utc(),status='CPU_OBSERVER_READY',process=me,deadline_utc=DEADLINE,
            poll_seconds=60,one_instance=True,formal_lock=False,scientific_compute=0,holder_changes=0,
            watched_nodes=NODES,original_thread=THREAD,no_callback_ACK_claim=True)
        atomic(OBS/'READY.json',ready)
        while True:
            now=time.time();expired=now>=deadline
            for node in NODES:
                if node in state:continue
                try:
                    data=terminal(node)
                    if data is None and not expired:continue
                    if data is None:data=dict(state='deadline_expired',reason='No true latest-run terminal with published episode CSV by deadline',node=node,utc=utc())
                    state[node]=data
                    # Persist one consumption before output publication; a publication exception is not retried as science.
                    atomic(OBS/'CONSUMPTIONS.json',state)
                    pub=publish(state)
                    ref=receipt(pub,state,'CPU_TERMINAL_APPEND_PUBLISHED')
                    notify(ref,'terminal_append')
                except Exception as exc:
                    error=dict(node=node,error=repr(exc),traceback=traceback.format_exc(),utc=utc())
                    atomic(OBS/(node+'_ERROR.json'),error)
                    state[node]=dict(state='failed',reason='CPU terminal validation/publication failed; inspect '+node+'_ERROR.json',**error)
                    atomic(OBS/'CONSUMPTIONS.json',state)
                    cur=load(ROOT/'CURRENT.json')
                    notify(dict(revision=cur['revision'],path=cur['publication']),'observer_failure_'+node,error)
            atomic(OBS/'HEARTBEAT.json',dict(utc=utc(),process=me,status='watching' if len(state)<2 else 'terminal',
                consumed_nodes={k:v['state'] for k,v in state.items()},deadline_utc=DEADLINE,scientific_compute=0))
            if len(state)==2:
                atomic(OBS/'TERMINAL.json',dict(utc=utc(),status='all_nodes_handled',process=me,state=state,
                    deadline_utc=DEADLINE,scientific_compute=0,holder_changes=0))
                return
            time.sleep(min(60,max(.1,deadline-time.time())))


if __name__=='__main__':main()
