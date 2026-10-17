"""Release-only process backend: every cold child inherits the one wave group/lock."""
import os,signal,subprocess,time
from contextlib import contextmanager
from pathlib import Path
from core.contracts import PACKAGE,read,configure_store
from core.process_family import drain_group
from batch_scheduler import GlobalFault
from pool_protocol import ARMS
from storage import Store
from execution import limits
from runtime_environment import child_environment

@contextmanager
def publication_deadline(deadline):
    """Bound all publication calls together without extending the wave alarm."""
    now=time.monotonic();remaining=deadline-now
    if remaining<=0:raise GlobalFault('whole-batch publication timeout')
    previous=signal.getitimer(signal.ITIMER_REAL)
    signal.setitimer(signal.ITIMER_REAL,min(remaining,previous[0]) if previous[0]>0 else remaining)
    try:yield
    finally:
        restore=max(1e-6,previous[0]-(time.monotonic()-now)) if previous[0]>0 else 0
        signal.setitimer(signal.ITIMER_REAL,restore,previous[1])

def process_row(pid):
    try:
        fields=Path('/proc',str(pid),'stat').read_text().rsplit(') ',1)[1].split()
        return dict(pid=int(pid),state=fields[0],ppid=int(fields[1]),pgid=int(fields[2]),start_ticks=int(fields[19]))
    except (OSError,ValueError,IndexError):return None

def group_snapshot(pgid,owner):
    result=[]
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit() and int(entry.name)!=owner:
            row=process_row(int(entry.name))
            if row and row['pgid']==pgid and row['state']!='Z':result.append(row)
    return result

class ProcessBackend:
    def __init__(self,release_path,proposal,fds):
        self.release_path=str(release_path);self.p=proposal;self.fds=fds
        self.owner=os.getpid();self.pgid=os.getpgrp()
        if not fds or self.owner!=self.pgid:raise GlobalFault('one guard-created isolated group and inherited lock required')
        self.handles={};self.owners={};self.snapshot=[];self.stores={};self.scan_count=0;self.cleanup=None;self.publish_deadline=None

    def refresh(self):
        self.scan_count+=1
        if self.scan_count>self.p['scheduler_caps']['ownership_scans']:raise GlobalFault('ownership scan budget')
        rows=group_snapshot(self.pgid,self.owner);unknown={r['pid']:r for r in rows}
        for row in rows:
            owner=self.owners.get(row['pid'])
            if owner and owner['start_ticks']==row['start_ticks']:unknown.pop(row['pid'],None)
        for _ in range(len(rows)+1):
            changed=False
            for pid,row in list(unknown.items()):
                parent=self.owners.get(row['ppid'])
                if parent:
                    self.owners[pid]=dict(start_ticks=row['start_ticks'],root=parent['root'])
                    del unknown[pid];changed=True
            if not changed:break
        if unknown:raise GlobalFault('unattributed process in owned formal group; refuse parent-local completion')
        self.snapshot=rows

    def start(self,parent,job):
        key=parent['parent_key'];out=Path(parent['paths']['output'])
        if key not in self.stores:
            out.mkdir(exist_ok=False);(out/'reserved').mkdir()
            self.stores[key]=Store(out/'reserved',byte_limit=64*1024**2,record_limit=32*1024**2,file_limit=128)
        store=self.stores[key];cfg=read(parent['config']['path']);name=job[0]
        if (out/name).exists():raise GlobalFault('branch already exists: no retry')
        env=child_environment(cfg,Path(parent['paths']['cache']))
        cmd=['timeout','--foreground','--signal=TERM','--kill-after=30s','1800s',cfg['python'],'-B',
            str(PACKAGE/'code/child.py'),'--release',self.release_path,'--parent',key,'--branch',name]
        so=(out/'reserved'/(name+'.stdout')).open('xb');se=(out/'reserved'/(name+'.stderr')).open('xb')
        try:
            proc=subprocess.Popen(cmd,cwd=PACKAGE/'code',env=env,pass_fds=self.fds,
                start_new_session=False,stdout=so,stderr=se,preexec_fn=limits)
        finally:so.close();se.close()
        handle=dict(process=proc,parent=parent,job=job,started=time.monotonic(),root_exited_at=None)
        self.handles[proc.pid]=handle
        row=process_row(proc.pid)
        if row is None or row['pgid']!=self.pgid:raise GlobalFault('child escaped owned wave group')
        self.owners[proc.pid]=dict(start_ticks=row['start_ticks'],root=proc.pid)
        store.json(name+'_START.json',dict(parent_key=key,branch=name,argv=cmd,pid=proc.pid,
            start_ticks=row['start_ticks'],pgid=self.pgid,gpu_uuid=parent['device']['gpu_uuid'],
            inherited_reservation=True,no_nested_lifecycle=True))
        return handle

    def poll(self,handle):
        proc=handle['process'];code=proc.poll()
        if code is None:return None
        # Refresh after wait/reap, before permitting a subsequent cold child.
        self.refresh()
        remaining=[r for r in self.snapshot if self.owners.get(r['pid'],{}).get('root')==proc.pid]
        if remaining:
            handle['root_exited_at']=handle['root_exited_at'] or time.monotonic()
            if time.monotonic()-handle['root_exited_at']>30:raise GlobalFault('orphaned branch descendants require owned wave drain')
            return None
        parent=handle['parent'];name=handle['job'][0];out=Path(parent['paths']['output'])/name
        result=read(out/'BRANCH_RESULT.json') if (out/'BRANCH_RESULT.json').exists() else None
        ledger=read(out/'RESOURCE_LEDGER.json') if (out/'RESOURCE_LEDGER.json').exists() else None
        errors=[ledger.get('primary')]+ledger.get('cleanup',[]) if ledger else []
        # Identity/full-SHA failures can precede a child ledger. Never classify
        # missing evidence as an ordinary local model failure and keep going.
        scope='wave' if ledger is None or any(e and e.get('failure_scope')=='wave' for e in errors) else 'parent'
        row=dict(branch=name,returncode=code,result=result,remaining_group=[],cleanup_complete=True,
            failure_scope=scope,elapsed_seconds=time.monotonic()-handle['started'],
            resource_ledger_present=ledger is not None)
        for pid,owner in list(self.owners.items()):
            if owner['root']==proc.pid:del self.owners[pid]
        self.handles.pop(proc.pid,None)
        return row

    def record_exit(self,parent,job,row):
        self.stores[parent['parent_key']].json(job[0]+'_EXIT.json',row)

    def drain(self):
        result=drain_group(self.pgid,self.owner)
        for handle in self.handles.values():handle['process'].wait()
        self.cleanup=dict(result,ownership_scans_before_drain=self.scan_count,
            drain_scan_hard_cap=None,drain_scope='retain inherited reservation until all live formal group members exit')
        return self.cleanup

    def was_started(self,parent):return parent['parent_key'] in self.stores

    def publish(self,parent):
        if self.publish_deadline is None:self.publish_deadline=time.monotonic()+self.p['timeouts']['publication_seconds']
        with publication_deadline(self.publish_deadline):
            if group_snapshot(self.pgid,self.owner):raise GlobalFault('publish before whole-wave compute exit')
            from batch_publication import publish_parent
            return publish_parent(parent,self.stores[parent['parent_key']],self.cleanup,synthetic=False)
