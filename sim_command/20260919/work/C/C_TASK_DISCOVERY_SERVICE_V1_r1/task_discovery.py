"""CPU-only dispatch discovery. Emits metadata events; has no scientific launcher."""
import datetime,hashlib,json,re
from pathlib import Path
import d24_common as d

META=('nodes/C/NEXT_TASK.json','DISPATCH_C.json','TASK_BOARD.json','CONTROL.json','persistent_queue/CONTROL.json')
CLOSED={'closed','cancelled','canceled','complete','completed','deferred','disabled','paused','blocked','rejected','superseded'}
READY={'ready','running','released','published','accepted','ACK_received_private_implementation'}
STOP_DISPATCH='2026-09-23T15:30:00+00:00'
SCIENCE_CUTOFF='2026-09-23T12:00:00+00:00'

def load(p):
    p=Path(p)
    if p.stat().st_size>8*1024**2:raise ValueError('metadata exceeds small-file limit')
    return json.loads(p.read_text())

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def key_for(task):return hashlib.sha256(json.dumps(['C',task['task_id'],task['revision'],task['authorization']['sha256']],separators=(',',':')).encode()).hexdigest()
def inside(root,rel):
    p=(root/rel).resolve()
    if not p.is_relative_to(root.resolve()):raise ValueError('metadata reference escapes campaign')
    return p

def normalized(row):
    tid=row.get('task_id',row.get('id'));auth=row.get('authorization');rev=row.get('task_revision',row.get('revision',1))
    if not isinstance(tid,str) or not tid.startswith('C_') or not isinstance(auth,dict):return None
    if not isinstance(rev,int) or rev<1:return None
    return dict(task_id=tid,revision=rev,node=row.get('node',row.get('owner','C')),task=row.get('task',row.get('brief','tasks/'+tid+'.md')),
                authorization=auth,status=row.get('status'),scope=row.get('scope'),predecessor=row.get('predecessor'),start_condition=row.get('start_condition'))


class Discovery:
    def __init__(self,root=None,state=None):
        self.root=Path(root or d.C);self.wakeup=Path(state or self.root/'persistent_queue/nodes/C/wakeup')
        self.folder=self.wakeup/'task_discovery';self.folder.mkdir(parents=True,exist_ok=True)
        self.state_path=self.folder/'STATE.json';self.state=load(self.state_path) if self.state_path.exists() else dict(entries={},revision_bindings={})
        self.last_scan=None;self.fresh=False;self.eligible={};self.decisions={}
    def claimed(self,task):
        tid=task['task_id'];rev=task['revision']
        p=self.root/'receipts/C'/(tid+'_ACK.json')
        if p.exists() and load(p).get('revision',1)>=rev:return True
        for p in (self.root/'receipts/C').glob(tid+'_RESULT*.json'):
            if load(p).get('revision',1)>=rev:return True
        return (self.root/'results/C'/tid/'CLAIM.json').exists()
    def snapshot(self):return {name:load(self.root/name) for name in META}
    def evaluate(self,meta,now):
        next_task=meta[META[0]];dispatch=meta[META[1]];board=meta[META[2]];control=meta[META[3]];queue=meta[META[4]]
        stopped=bool(control.get('stop_requested') or queue.get('global_stop') or not queue.get('nodes',{}).get('C',{}).get('enabled'))
        board_rows=board['tasks'].values() if isinstance(board['tasks'],dict) else board['tasks']
        board_rows=[x for x in board_rows if x.get('owner',x.get('node'))=='C'];board_map={x.get('id',x.get('task_id')):x for x in board_rows}
        candidates=[]
        for source in [next_task,dispatch]:
            if source.get('node')!='C':continue
            candidates.append(source)
            for field in ['control_plane_followups','authorized_followups']:candidates.extend(source.get(field,[]))
        candidates.extend(board_rows)
        by_key={};bindings={}
        for raw in candidates:
            task=normalized(raw)
            if not task or task['node']!='C':continue
            key=key_for(task);token=task['task_id']+':'+str(task['revision']);bindings.setdefault(token,set()).add(task['authorization'].get('sha256'))
            # Prefer explicit NEXT/DISPATCH source information over board defaults.
            if key not in by_key:by_key[key]=task
        valid={};decisions={}
        for key,task in by_key.items():
            reason=None;tid=task['task_id'];token=tid+':'+str(task['revision']);ref=task['authorization'];row=board_map.get(tid)
            if stopped:reason='control_disabled'
            elif len(bindings[token])!=1:reason='same_revision_metadata_conflict'
            elif token in self.state['revision_bindings'] and self.state['revision_bindings'][token]!=ref['sha256']:reason='same_revision_authorization_changed'
            elif row and row.get('revision',1)!=task['revision']:reason='revision_mismatch'
            elif row and row.get('status') in CLOSED:reason='board_closed_or_deferred'
            elif row and row.get('status') not in READY:reason='board_not_ready_or_released'
            elif task.get('status') in CLOSED:reason='dispatch_closed_or_deferred'
            elif ref not in control.get('stage_authorizations',[]) or ref not in queue.get('stage_authorizations',[]):reason='authorization_not_registered'
            if reason is None:
                ap=inside(self.root,ref['path']);auth=load(ap)
                if sha(ap)!=ref['sha256']:reason='authorization_hash_mismatch'
                elif auth.get('status')!='released':reason='authorization_not_released'
                else:
                    node=auth.get('nodes',{}).get('C',{})
                    owned=(auth.get('node')=='C' and auth.get('task_id')==tid) or node.get('task_id')==tid
                    ar=node.get('revision',auth.get('revision',1))
                    if not owned or ar!=task['revision']:reason='authorization_owner_task_revision_mismatch'
                    else:
                        task['CPU_only']=auth.get('scientific_compute_added')==0 and auth.get('new_GPU_claims')==0
                        if task['CPU_only'] and any(auth.get(k,0)!=0 for k in ['scientific_compute_added','new_GPU_claims']):reason='CPU_scope_mismatch'
                        elif not task['CPU_only'] and now>=datetime.datetime.fromisoformat(SCIENCE_CUTOFF):reason='science_admission_cutoff'
                        elif not task['CPU_only'] and control.get('formal_gpu_runs_enabled') is False:reason='formal_GPU_disabled'
                        tp=inside(self.root,task['task'])
                        if not tp.is_file() or tp!=self.root/'tasks'/(tid+'.md'):reason='task_reference_mismatch'
                        task_ref=auth.get('task') if task['CPU_only'] else node.get('brief')
                        if isinstance(task_ref,dict) and (inside(self.root,task_ref['path'])!=tp or sha(tp)!=task_ref['sha256']):reason='task_hash_mismatch'
                        expected_host=node.get('host',auth.get('target_hostname'));expected_thread=node.get('thread_id',auth.get('target_thread'))
                        if expected_host and expected_host!=d.HOST:reason='wrong_host'
                        if expected_thread and expected_thread!='01a0c793-10d2-7791-a250-fd65d88e1ccb':reason='wrong_thread'
            if reason is None and self.claimed(task):reason='already_ACKed_completed_or_claimed'
            decisions[key]=dict(task_id=tid,revision=task['revision'],reason=reason or 'eligible')
            if reason is None:valid[key]=task
        return valid,decisions
    def poll(self,now=None):
        now=now or datetime.datetime.now(datetime.timezone.utc)
        if now>=datetime.datetime.fromisoformat(STOP_DISPATCH):
            self.fresh=False;self.last_scan=dict(at_utc=now.isoformat(),status='new_dispatch_monitoring_deadline');return []
        try:
            meta=self.snapshot();valid,decisions=self.evaluate(meta,now)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            # A partial metadata write is not a cancellation. Keep all durable state.
            self.fresh=False;self.last_scan=dict(at_utc=now.isoformat(),status='metadata_temporarily_unavailable',error=repr(exc),old_state_preserved=True);return []
        self.fresh=True;self.eligible=valid;self.decisions=decisions;new=[]
        for key,task in valid.items():
            if key in self.state['entries']:continue
            token=task['task_id']+':'+str(task['revision']);self.state['revision_bindings'][token]=task['authorization']['sha256']
            eid='C_'+hashlib.sha256(('task_available|'+key).encode()).hexdigest()[:32]
            event=dict(event_id=eid,event_type='task_available',node='C',hostname=d.HOST,executor_thread_id='01a0c793-10d2-7791-a250-fd65d88e1ccb',
                       created_at_utc=now.isoformat(),detected_at=now.isoformat(),dedup_key=key,task=task,
                       current_primary_task=meta[META[0]].get('task_id'),synthetic=False,required_transport='auto',scientific_compute_added_by_notifier=0)
            p=self.wakeup/'outbox'/(eid+'.json')
            if not p.exists():d.exclusive(p,event)
            self.state['entries'][key]=dict(event_id=eid,task=task,detected_at=now.isoformat());new.append(eid)
        for key,entry in self.state['entries'].items():
            eid=entry['event_id'];ack=self.wakeup/'handler_acks'/(eid+'.json');delivery=self.wakeup/'delivery'/(eid+'.json')
            if ack.exists():entry['handler_ACK']=str(ack);entry['status']='handler_ACKed';continue
            decision=decisions.get(key,{});eligible=key in valid
            suppression=self.folder/(eid+'_SUPPRESSION.json')
            if not eligible and not delivery.exists():d.atomic(suppression,dict(active=True,at_utc=now.isoformat(),reason=decision.get('reason','no_longer_dispatched')))
            elif eligible and suppression.exists():d.atomic(suppression,dict(active=False,at_utc=now.isoformat()))
            if delivery.exists():
                transport=load(delivery);entry['transport_status']=transport['status'];entry['transport']=str(delivery)
                stamp=transport.get('transport_entered',transport.get('at_utc'))
                if stamp and (now-datetime.datetime.fromisoformat(stamp)).total_seconds()>300:
                    entry['status']='DELIVERY_STALLED';d.atomic(self.folder/(eid+'_DELIVERY_STALLED.json'),dict(event_id=eid,at_utc=now.isoformat(),reason='five_minutes_without_actual_handler_ACK',automatic_resend=False,scientific_launches=0))
            else:entry['status']='eligible_pending_transport' if eligible else 'suppressed'
        d.atomic(self.state_path,self.state)
        self.last_scan=dict(at_utc=now.isoformat(),status='monitoring',new_events=new,eligible_unclaimed=len(valid),decisions=decisions,
                            stalled=[x['event_id'] for x in self.state['entries'].values() if x.get('status')=='DELIVERY_STALLED'])
        return new
    def event_allowed(self,event):return self.fresh and event.get('dedup_key') in self.eligible


def task_message(event,work):
    task=event['task'];eid=event['event_id'];scope='仅CPU伴随任务，新增科学计算/GPU调用均0' if task['CPU_only'] else '已授权的新科学任务；GPU只可在本机现有正式家族退出后衔接'
    return (f'C 新派单 task_available，事件 {eid}，不是科学终局。读取 {d.C}/persistent_queue/nodes/C/wakeup/outbox/{eid}.json。'
            f'任务 {task["task_id"]} revision {task["revision"]}；任务书 {d.C/task["task"]}；授权 {d.C/task["authorization"]["path"]} SHA256 {task["authorization"]["sha256"]}。'
            f'{scope}。当前派单主任务 {event.get("current_primary_task")}，先核对实际claim/退出与既有ACK，已完成源禁止重放。'
            '先写新任务ACK，再直接完成其已授权范围；正常队列无二次分析放行，现有科学队列照常后台运行。'
            f'用 /usr/bin/python {work}/wakeup.py ack --event-id {eid} --outcome claimed --audit 新任务ACK绝对路径 确认本原线程实际领取。'
            '稳定运行且终局通知已登记后结束LLM等待。不要因回调结束递归唤醒。')
