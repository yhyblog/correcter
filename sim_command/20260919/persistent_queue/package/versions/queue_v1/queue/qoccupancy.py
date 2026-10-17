"""Per-card auxiliary ownership and pre-Popen exit barrier. No hardware probes.

Auxiliary processes have private sessions; science retains its original node
lock/group. Every auxiliary session is published before it receives permission
to exec gpu_hold, so the outer supervisor can clean it after a manager failure.
"""
import os
import signal
import subprocess
import time
from pathlib import Path
from qio import PACKAGE,QUEUE,CAMPAIGN,read,verify,ref,new_json,append,utc,process_identity,same_process

OVERRIDE_SHA='0e896062a9c69dc51e6d1332eca5413c683d2c9bbed113b9346f8dba27310916'
BASE_SHA='d73448042b71ecb06940e8d891caf0ef8bef005018f155ee2743903981992928'
HOLDER_SHA='3f75a84145092f2c6beb342f8ea9ae445905c6e0549693c5aa78f525c0436a2e'

def policy(control=None,node='A'):
    ctl=read(QUEUE/'CONTROL.json') if control is None else control
    row=dict(path='persistent_queue/OCCUPANCY_OVERRIDE_V1.json',sha256=OVERRIDE_SHA)
    if row not in ctl.get('operational_overrides',[]):raise RuntimeError('occupancy override is not bound')
    doc=read(verify(row));verify(doc['contract'])
    if (doc['base_queue_authorization']['sha256']!=BASE_SHA or
        ctl['authorization']!=doc['base_queue_authorization'] or node not in doc['nodes'] or
        not doc['allow_idle_subset_holders_during_formal_wave'] or doc['formal_compute_on_same_GPU_with_holder_authorized']):
        raise RuntimeError('occupancy precedence or base authority mismatch')
    verify(doc['base_queue_authorization'])
    return dict(id=doc['id'],sha256=OVERRIDE_SHA,mode='formal_priority_per_GPU_exit_ACK',
        holder_on_loading_GPU=False,auxiliary_costs_separate=True,science_budget_changed=False)

def session_members(saved):
    """A private session cannot acquire unrelated external process members."""
    current=process_identity()
    if any(saved[k]!=current[k] for k in ('host','boot_id')):raise RuntimeError('holder belongs to another host/boot')
    leader=process_identity(saved['pid'])
    if leader and leader['start_ticks']!=saved['start_ticks']:raise RuntimeError('holder PID reused; ownership unproven')
    rows=[]
    for f in Path('/proc').iterdir():
        if not f.name.isdigit():continue
        try:
            bits=(f/'stat').read_text().rsplit(') ',1)[1].split()
            if int(bits[3])==saved['pid'] and bits[0]!='Z':
                row=process_identity(int(f.name))
                if row:rows.append(row)
        except (OSError,ValueError,IndexError):continue
    if any(r['start_ticks']<saved['start_ticks'] for r in rows):raise RuntimeError('invalid holder session ancestry')
    return rows

def signal_owned(saved,sig):
    if same_process(saved):os.kill(saved['pid'],sig)

def stop_session(folder,reason,timeout=30):
    folder=Path(folder);started=folder/'STARTED.json'
    if not started.exists():
        # A spawned CPU wrapper has no permission to enter GPU code until its
        # own identity and GO record both exist. Still reap its private session.
        started=folder/'SPAWNED.json'
        if not started.exists():
            if (folder/'GO_RECORDED.json').exists():raise RuntimeError('orphan GO record without holder identity')
            if (folder/'SPAWN_INTENT.json').exists():raise RuntimeError('holder spawn outcome unknown; retain reservation')
            return dict(status='not_started',GPU_compute_entered=False)
    if (folder/'EXIT_ACK.json').exists():
        result=read(folder/'EXIT_ACK.json')
        if session_members(result['manager']):raise RuntimeError('acknowledged holder session is live again')
        return result
    saved=read(started)['process'];begin=time.monotonic();deadline=begin+timeout;seen={};exits={}
    if not (folder/'STOP_REQUEST.json').exists():
        new_json(folder/'STOP_REQUEST.json',dict(utc=utc(),monotonic=begin,reason=reason,manager=saved))
    first=session_members(saved)
    for row in first:seen[(row['pid'],row['start_ticks'])]=row
    signal_owned(saved,signal.SIGTERM)
    manager_exit=None
    while True:
        rows=session_members(saved);now=time.monotonic();live={(x['pid'],x['start_ticks']) for x in rows}
        for row in rows:seen[(row['pid'],row['start_ticks'])]=row
        for key in seen:
            if key not in live and key not in exits:exits[key]=dict(observed_utc=utc(),observed_monotonic=now)
        if manager_exit is None and not same_process(saved):manager_exit=dict(observed_utc=utc(),observed_monotonic=now)
        if not rows:break
        if now>=deadline:raise RuntimeError('holder descendants remain: formal entry/release forbidden')
        # gpu_hold normally reaps its own children. If the manager exits early,
        # only this positively identified private session may be cleaned up.
        if manager_exit is not None:
            for row in rows:signal_owned(row,signal.SIGTERM)
        time.sleep(.1)
    launch=read(folder/'GO_RECORDED.json') if (folder/'GO_RECORDED.json').exists() else None
    result=dict(status='all_owned_holder_session_processes_exited',manager=saved,reason=reason,
        manager_exit=manager_exit,all_descendants_exit_observed_utc=utc(),all_descendants_exit_observed_monotonic=time.monotonic(),
        descendants=[dict(identity=v,exit=exits.get(k)) for k,v in seen.items() if v['pid']!=saved['pid']],
        elapsed_seconds=time.monotonic()-begin,extra_GPU_queries=0,no_unrelated_process_signals=True,
        holder_manager_interval_seconds=(time.monotonic()-launch['monotonic']) if launch else 0,
        interval_scope='GO permission to observed full private-session exit; not kernel time or energy',
        GPU_uuid=launch.get('GPU_uuid') if launch else None,configured_duty=launch.get('duty') if launch else None,
        measured_utilization=None)
    new_json(folder/'EXIT_ACK.json',result);return result

def stop_tree(root,reason):
    records=[]
    folders={p.parent for name in ('SPAWN_INTENT.json','STARTED.json','SPAWNED.json','GO_RECORDED.json') for p in Path(root).glob('**/'+name)}
    for folder in sorted(folders):records.append(stop_session(folder,reason))
    return records

class PerGPU:
    def __init__(self,root,devices,initial_ack,*,pending_gpus=(),holder_factory=None,holder_stopper=stop_session):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.devices={d['gpu_uuid']:d for d in devices};self.states={key:'idle' for key in self.devices}
        self.parents={};self.holders={};self.handles={};self.sequence=0;self.stopper=holder_stopper
        self.factory=holder_factory or self._spawn
        for gpu in pending_gpus:
            if gpu not in self.devices:raise RuntimeError('pending GPU outside fixed node map')
            self.states[gpu]='pending_formal'
        if initial_ack.get('status')!='all8_holder_processes_exited_before_formal_child':raise RuntimeError('original node guard handoff required')
        new_json(self.root/'POLICY.json',dict(effective=policy(),initial_guard_ack=initial_ack))

    def event(self,name,**values):append(self.root/'AUXILIARY_EVENTS.jsonl',dict(event=name,utc=utc(),monotonic=time.monotonic(),**values))

    def _spawn(self,gpu,folder):
        holder=CAMPAIGN.parents[2]/'gpu_hold.py'
        verify(dict(path=str(holder),sha256=HOLDER_SHA))
        read_fd,write_fd=os.pipe();proc=None
        try:
            env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu)
            new_json(folder/'SPAWN_INTENT.json',dict(utc=utc(),GPU_uuid=gpu,GPU_permission_requires_durable_GO=True))
            with (folder/'stdout.log').open('xb') as out,(folder/'stderr.log').open('xb') as err:
                proc=subprocess.Popen(['/usr/bin/python','-B',str(PACKAGE/'queue/qholder_entry.py'),
                    '--root',str(folder),'--go-fd',str(read_fd),'--holder',str(holder)],
                    stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=env,start_new_session=True,pass_fds=(read_fd,))
            self.handles[gpu]=proc
            identity=process_identity(proc.pid)
            if identity is None or identity['pgid']!=proc.pid:raise RuntimeError('holder CPU wrapper identity missing')
            new_json(folder/'SPAWNED.json',dict(process=identity,utc=utc(),monotonic=time.monotonic(),GPU_compute_entered=False))
            end=time.monotonic()+10
            while not (folder/'STARTED.json').exists():
                if proc.poll() is not None or time.monotonic()>end:raise RuntimeError('holder CPU entry acknowledgement failed')
                time.sleep(.02)
            saved=read(folder/'STARTED.json')['process']
            if saved['pid']!=proc.pid or saved['pgid']!=proc.pid or not same_process(saved):raise RuntimeError('holder session identity mismatch')
            new_json(folder/'GO_RECORDED.json',dict(utc=utc(),monotonic=time.monotonic(),GPU_uuid=gpu,manager=saved,duty=.95,measured_utilization=None))
            os.write(write_fd,b'GO\n')
        finally:
            os.close(read_fd);os.close(write_fd)
        return folder

    def fill_idle(self,gpu,cached_guard):
        if self.states[gpu]!='idle' or gpu in self.holders:return False
        device=self.devices[gpu];row=cached_guard.get('gpus',{}).get(str(device['gpu_index']),{})
        if (time.time()-cached_guard.get('updated',0)>12 or row.get('state')!='reserved' or
            not isinstance(row.get('pids'),list) or row['pids']):
            self.event('idle_fill_deferred',gpu_uuid=gpu,reason='fresh_empty_reserved_guard_snapshot_required');return False
        self.sequence+=1;folder=self.root/('holder_%05d'%self.sequence);folder.mkdir()
        self.holders[gpu]=folder
        self.factory(gpu,folder);self.event('holder_started',gpu_uuid=gpu,registry=str(folder),target_duty=.95)
        return True

    def monitor_cached(self,cached_guard):
        # Cached guard queries already exist. Never interpret low utilization as
        # idle. More than one GPU context or stale ownership yields OUR holder.
        for gpu,folder in list(self.holders.items()):
            row=cached_guard.get('gpus',{}).get(str(self.devices[gpu]['gpu_index']),{})
            owned={r['pid'] for r in session_members(read(folder/'STARTED.json')['process'])}
            unknown=set(row.get('pids',[]))-owned
            if (time.time()-cached_guard.get('updated',0)>12 or row.get('state')!='reserved' or
                unknown or not owned):
                ack=self.stopper(folder,'cached_guard_conflict_or_stale')
                proc=self.handles.pop(gpu,None)
                if proc is not None:proc.wait(timeout=1)
                self.holders.pop(gpu,None);self.event('holder_yielded',gpu_uuid=gpu,ack=ack)

    def before_formal(self,gpu,parent):
        if self.states[gpu]=='formal':
            if self.parents[gpu]!=parent:raise RuntimeError('GPU already owned by another formal parent')
            return
        self.states[gpu]='handoff'  # Filling becomes impossible before any stop is requested.
        folder=self.holders.get(gpu)
        ack=self.stopper(folder,'formal_GPU_entry_before_Popen') if folder else dict(status='no_auxiliary_holder_started')
        if ack['status'] not in ('all_owned_holder_session_processes_exited','no_auxiliary_holder_started'):raise RuntimeError('holder exit not proven')
        proc=self.handles.pop(gpu,None)
        if proc is not None:proc.wait(timeout=1)
        self.holders.pop(gpu,None);self.parents[gpu]=parent;self.states[gpu]='formal'
        self.event('formal_entry_permitted_after_holder_exit_ACK',gpu_uuid=gpu,parent=parent,ack=ack)

    def formal_exited(self,gpu,parent,proof):
        if self.states[gpu]!='formal' or self.parents[gpu]!=parent:raise RuntimeError('formal owner mismatch')
        if not proof.get('cleanup_complete') or proof.get('remaining_group')!=[]:raise RuntimeError('formal descendant exit not proven')
        self.states[gpu]='idle';self.parents.pop(gpu)
        self.event('formal_parent_exited_GPU_eligible',gpu_uuid=gpu,parent=parent,proof=proof)

    def close(self):
        # Called before original formal group drain and before outer lock release.
        records=stop_tree(self.root,'wave_end_before_original_guard_restoration')
        for proc in self.handles.values():proc.wait(timeout=1)
        self.handles.clear();self.holders.clear()
        self.event('all_auxiliary_holders_exited',records=records)
        return records
