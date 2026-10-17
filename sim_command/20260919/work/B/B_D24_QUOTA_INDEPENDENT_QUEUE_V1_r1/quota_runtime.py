"""B-only finite continuation of existing grants; no model imports or LLM dependency."""
import csv
import fcntl
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from qio import read, ref, sha, new_json, atomic_json, utc, process_identity, same_process
import gates

C = gates.C
P = gates.P
F = C/'results/B/B_D24_FULL_Q_LOSS_REFRESH_V1'
Q = C/'results/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1'
W = Path(__file__).resolve().parent
OLD_R = C/'results/B/B_D24_SMOL_MULTI_EVAL_V1/R_unstarted_r2'
BASES = {'native': F/'evaluation_r1', 'R': P/'R_cancelled_r3',
         'H20': P/'H20_r1', 'H30': P/'H30_r1'}
CAPS = {'native': 1100, 'R': 24, 'H20': 1100, 'H30': 1100}
CUTOFF = 1790164800
DRAIN_END = CUTOFF + 10800
AUTH = C/'deadline_20260924/QUOTA_INDEPENDENT_AUTORUN_AUTHORIZATION_V1.json'
AUTH_SHA = '651a1b85faf16e3d13e0a722f1253fc465f5fcbeeab99b692f51f674de30af98'
TASK = 'B_D24_QUOTA_INDEPENDENT_QUEUE_V1'
RUN = 'D24_B_QUOTA_INDEPENDENT_r1'
THREAD = '01a0b9c5-1e4b-7b73-9336-229e6df349a2'
LOCAL = Path('/tmp/corrector_B_quota_independent_r1')
WAKE = C/'work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py'
_wave_lock = None

def snapshot(path):
    return read(path, retry_seconds=.75) if Path(path).is_file() else {}

def authority():
    a=read(AUTH); c=read(C/'CONTROL.json'); q=read(C/'persistent_queue/CONTROL.json')
    if sha(AUTH)!=AUTH_SHA or a['status']!='released': raise ValueError('quota authority changed')
    if a['nodes']['B']['host']!=socket.gethostname() or a['nodes']['B']['thread_id']!=THREAD:
        raise ValueError('B host/thread mismatch')
    if c.get('stop_requested') or q.get('global_stop') or not q['nodes']['B']['enabled']:
        raise RuntimeError('live stop/disabled')
    if not any(v['task_id']==TASK and v['authorization']['sha256']==AUTH_SHA for v in q['nodes']['B'].get('control_plane_followups',[])):
        raise ValueError('quota task not registered')
    gates.authority()
    return a

def normalized(row):
    return dict(row,host=row.get('host',row.get('hostname')))

def alive(root):
    for name in ['CLAIM.json','QUEUE_CLAIM.json','FORMAL_SERVICE_STARTED.json','LAUNCH.json']:
        row=snapshot(Path(root)/name)
        if row and row.get('process') and same_process(normalized(row['process'])):return True
    return False

def roots(key):
    extras=sorted((Q/'waves').glob(key+'_*')) if (Q/'waves').exists() else []
    return [BASES[key]]+extras

def all_roots():
    return [r for k in BASES for r in roots(k)]

def attempts(root):
    row=snapshot(Path(root)/'ATTEMPT_COUNTER.json')
    return row.get('reserved_attempts',row.get('count',0))

def total_attempts():return 15598+sum(attempts(r) for r in all_roots())

def stage_attempts(key):return sum(attempts(r) for r in roots(key))

def clean_exit(root):
    root=Path(root)
    if alive(root):return False
    result=snapshot(root/'RESULT.json')
    if not result.get('all_owned_descendants_exited') or not result.get('occupancy_handoff_complete'):return False
    # Verify the actual old formal group, not only its summary flags.
    peer=snapshot(root/'chain/SAME_LOCK_FD_RETAINED.json').get('peer')
    if peer:
        from process_family import group_members
        if process_identity(peer['pid']) and same_process(normalized(peer)):return False
        if group_members(peer['pgid'],peer['pid']):return False
    return True

def reconcile_dead(root):
    """Publish only provable cleanup after a queue/CPU process dies; never kill work."""
    root=Path(root)
    if alive(root) or (root/'RESULT.json').exists():return
    if not any((root/n).exists() for n in ['CLAIM.json','LAUNCH.json','FORMAL_SERVICE_STARTED.json']):return
    chain=snapshot(root/'chain/CHAIN_RESULT.json')
    no_entry=not (root/'CHAIN_COMMAND.json').exists()
    cleaned=chain.get('cleanup',{}).get('status') in ['all_formal_group_members_exited','no_formal_entry']
    restored=chain.get('restoration',{}).get('status')=='occupancy_resolved'
    if not no_entry and not (cleaned and restored):return
    peer=snapshot(root/'chain/SAME_LOCK_FD_RETAINED.json').get('peer')
    if peer:
        from process_family import group_members
        if same_process(normalized(peer)) or group_members(peer['pgid'],peer['pid']):return
    new_json(root/'RESULT.json',dict(status='failed',success=None,utc=utc(),
        reason='CPU supervisor exited; actual no-entry or formal cleanup verified',
        all_owned_descendants_exited=True,occupancy_handoff_complete=True,
        reconciled_from_actual_cleanup=True,chain_result=str(root/'chain/CHAIN_RESULT.json')))

def stage_key(root):
    root=Path(root)
    for key,base in BASES.items():
        if root==base:return key
    return read(root/'config/CONFIG.json')['quota_stage']

def outcomes(key,exclude=None):
    """Read only actual terminal units. Both valid success and valid failure are final."""
    valid={}; latest={}; claimed=set(); history=[]
    for root in roots(key):
        if root==exclude:continue
        if key in ['native','R']:
            pattern='evaluation/*/*/RESULT.json'
            for p in (root/'claims/attempts').glob('*.json'):
                row=read(p);claimed.add(row.get('identity',row.get('method','')+'/'+row.get('source_id','')))
        else:
            pattern='runs/*/episodes/*/RESULT.json'
            claimed.update(p.stem for p in (root/'unit_claims').glob('*.json'))
        for p in root.glob(pattern):
            row=read(p);uid=(row['method']+'/'+row['source_id']) if key in ['native','R'] else row['unit_id']
            if row.get('status')=='complete':
                if type(row.get('success')) is not bool:raise ValueError('malformed scientific terminal '+str(p))
                if uid in valid:raise ValueError('duplicate valid terminal '+uid)
                valid[uid]=(row,p)
            elif row.get('success') is not None:raise ValueError('technical result must retain null success')
            latest[uid]=(row,p);history.append(dict(unit_id=uid,status=row['status'],result=str(p)))
    return valid,latest,claimed,history

def register(root,own,task,run):
    identity=dict(hostname=own['host'],boot_id=own['boot_id'],pid=own['pid'],start_ticks=own['start_ticks'],session_id=os.getsid(0))
    manifest=dict(job_id=run,task_id=task,revision=1,run_id=run,attempt=1,
        claim_identity=ref(root/'CLAIM.json'),process_identity=identity,
        result_path=str(root/'RESULT.json'),error_summary_path=str(root/'stderr.log'))
    new_json(root/'WAKEUP_REGISTRATION.json',manifest)
    return register_manifest(root/'WAKEUP_REGISTRATION.json')

def register_manifest(path):
    """Notification side effect is bounded and cannot abort scientific entry."""
    path=Path(path);record=dict(utc=utc(),manifest=str(path),science_blocks=False)
    try:
        p=subprocess.run(['/usr/bin/python',str(WAKE),'register','--manifest',str(path)],capture_output=True,text=True,timeout=25)
        record.update(exit_code=p.returncode,stdout=p.stdout[-2000:],stderr=p.stderr[-2000:],registered=p.returncode==0)
    except Exception as exc:record.update(registered=False,error=repr(exc))
    atomic_json(path.parent/'TRIGGER_REGISTRATION_STATUS.json',record)
    return record

def entry_prepare(root):
    """Called only before a future formal claim; healthy services never reload code."""
    root=Path(root);authority()
    if (root/'CLAIM.json').exists():raise RuntimeError('existing claim; no replay')
    cfg=read(root/'config/CONFIG.json');key=stage_key(root)
    cfg['planned_prior_attempts']=total_attempts()
    # A separate pure CPU waiter may extend to the admission cutoff; a begun wave cannot.
    cfg['admission_cutoff_unix']=CUTOFF
    valid,latest,claimed,history=outcomes(key,exclude=root)
    if key in ['native','R']:
        index=read(root/'SOURCE_INDEX.json');allowed=index['pending'];retained=index.get('retained',[])
        by_id={x['method']+'/'+x['source_id']:x for x in retained}
        for uid,(row,path) in latest.items():
            by_id[uid]=dict(method=row['method'],source_id=row['source_id'],result=ref(path),disposition=row['status'])
        pending=[]
        retry_allowed=set(cfg.get('quota_retry_units',[]))
        for unit in allowed:
            uid=unit['method']+'/'+unit['source_id']
            if uid in valid:continue
            if uid in claimed and uid not in retry_allowed:continue
            by_id.pop(uid,None);pending.append(unit)
        index.update(pending=pending,retained=list(by_id.values()),external_claimed=[{'method':u.split('/')[0],'source_id':u.split('/',1)[1]} for u in sorted(claimed)])
        atomic_json(root/'SOURCE_INDEX.json',index)
        cfg['planned_current']=len(pending)
    else:
        index=read(root/'JOB_INDEX.json');jobs=[];retry_allowed=set(cfg.get('quota_retry_units',[]))
        for item in index['jobs']:
            j=read(item['path']);ss=[]
            for source in j['sources']:
                uid=j['cell_id']+'__'+source['source_id']
                if uid not in valid and (uid not in claimed or uid in retry_allowed):ss.append(source)
            if not ss:continue
            if ss!=j['sources']:
                j=dict(j,sources=ss);atomic_json(item['path'],j)
            jobs.append(dict(job_id=j['job_id'],**ref(item['path'])))
        index['jobs']=jobs;atomic_json(root/'JOB_INDEX.json',index)
        cfg['planned_current']=sum(len(read(j['path'])['sources']) for j in jobs)
    remaining=CAPS[key]-stage_attempts(key)
    cfg['stage_attempt_cap']=min(cfg['stage_attempt_cap'],remaining)
    if cfg['planned_current']>remaining:raise ValueError('existing stage cap exhausted')
    node_cap=20000 if key=='native' else 22000
    cfg['node_cumulative_attempt_cap']=node_cap
    if cfg['planned_prior_attempts']+cfg['stage_attempt_cap']>node_cap:raise ValueError('existing node cap exhausted')
    atomic_json(root/'config/CONFIG.json',cfg)
    atomic_json(root/'QUOTA_ENTRY.json',dict(utc=utc(),stage=key,authority=ref(AUTH),pending=cfg['planned_current'],stage_attempts_already=stage_attempts(key),retained_valid=len(valid),LLM_required=False))
    atomic_json(root/'CODE_MANIFEST.json',dict(utc=utc(),files=[ref(p) for p in sorted((root/'code').glob('*.py'))]+[ref(root/'config/CONFIG.json')]))
    return cfg

def acquire_wave(root):
    """Serialize GPU entry, using a CPU mutex distinct from the original formal.lock."""
    global _wave_lock
    root=Path(root);cfg=read(root/'config/CONFIG.json');LOCAL.mkdir(exist_ok=True)
    _wave_lock=(LOCAL/'entry.lock').open('a')
    while True:
        authority()
        if time.time()>=min(CUTOFF,cfg['absolute_wall_deadline_unix']):raise TimeoutError('no new formal admission after cutoff')
        try:fcntl.flock(_wave_lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
        except BlockingIOError:
            atomic_json(root/'QUOTA_ENTRY_WAIT.json',dict(utc=utc(),reason='existing own formal wave',GPU_work_started=False));time.sleep(5)
    unresolved=[]
    for other in all_roots():
        if other==root or not (other/'CHAIN_COMMAND.json').exists():continue
        if not clean_exit(other):unresolved.append(str(other))
    if unresolved:raise RuntimeError('prior formal cleanup unknown: '+repr(unresolved))
    new_json(root/'QUOTA_WAVE_ADMISSION.json',dict(utc=utc(),process=process_identity(),CPU_mutex_only=True,formal_lock_acquisitions=0,all_prior_owned_formal_families_exited=True))

def empty_stage(root):
    """A canonical later stage consumes earlier independent results without model loads."""
    root=Path(root);cfg=read(root/'config/CONFIG.json');own=process_identity()
    new_json(root/'CLAIM.json',dict(process=own,task_id=cfg['task_id'],run_id=cfg['run_id'],utc=utc(),CPU_only_all_units_already_attempted=True))
    register(root,own,cfg['task_id'],cfg['run_id'])
    base=read(root/'config/BASE.json')
    p=subprocess.run([base['python'],'-B',str(root/'code/publish.py')],cwd=root,capture_output=True,text=True,timeout=600,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'))
    atomic_json(root/'PUBLICATION_PROCESS.json',dict(exit_code=p.returncode,stdout=p.stdout[-2000:],stderr=p.stderr[-2000:],utc=utc()))
    final=snapshot(root/'FINAL_SUMMARY.json')
    new_json(root/'RESULT.json',dict(status=final.get('status','failed'),all_owned_descendants_exited=True,occupancy_handoff_complete=True,CPU_only=True,science_attempts=0,publication_completed=p.returncode==0,utc=utc()))
    return 0 if final.get('status')=='complete' else 3

def issue(error,root=Q,kind=None):
    import recovery_policy
    return recovery_policy.issue(root,error,kind=kind,evidence=[str(root)],continuable=['independent remaining authorized stages with verified own cleanup'])

def choose_recipe(text,workers,has_valid,never_entered):
    value=str(text).lower()
    if any(s in value for s in ['out of memory','cuda error: memory allocation','insufficient ordinary host ram','ordinary ram below']) and workers>8:
        return dict(kind='reduce_concurrency',target_workers=workers-8,change='reduce resident workers by one per GPU after recorded OOM; numerical configuration unchanged',science_changed=False)
    if any(x in value for x in ['stale file handle','input/output error','jsondecodeerror','connectionreseterror','brokenpipeerror']):
        return dict(kind='restored_io',target_workers=workers,change='readable frozen inputs and fresh private IPC/output paths after recorded I/O fault',science_changed=False)
    if has_valid and never_entered:
        return dict(kind='resume_unstarted',target_workers=workers,change='isolate remaining never-entered units after proven successful model execution and complete old family cleanup',science_changed=False,never_entered_only=True)
    return None

def expected(key):
    if key in ['native','R']:
        return {x['method']+'/'+x['source_id']:x for x in read(Q/'contracts'/(key+'.json'))['pending']}
    t=gates.transfer();out={}
    for row in t['nodes']['B']['jobs']:
        if row['H']!=int(key[1:]):continue
        j=read(row['path'])
        for s in row['sources']:out[j['cell_id']+'__'+s['source_id']]=dict(job=row,source=s)
    return out

def build_wave(key,units,predecessor,reason,recipe=None):
    authority();base=BASES[key];seen=list((Q/'waves').glob(key+'_*')) if (Q/'waves').exists() else []
    if len(seen)>=3:raise ValueError('finite per-stage continuation count reached')
    root=Q/'waves'/(key+'_%02d'%(len(seen)+1));root.mkdir(parents=True,exist_ok=False)
    template=Q/'templates'/key
    shutil.copytree((template if template.exists() else base)/'code',root/'code');shutil.copytree(base/'config',root/'config')
    for name in ['SOURCE_INDEX.json','METHOD_FROZEN.json']:
        shutil.copy2(base/name,root/name)
    cfg=read(root/'config/CONFIG.json');cfg.update(activation_finalized=True,quota_new_wave=True,quota_stage=key,
        quota_retry_units=list(units),completion_via_queue=False,predecessor_root=str(predecessor),
        predecessor_required_complete=False,local_dir='/tmp/corrector_B_quota_'+root.name,
        run_id='D24_B_QUOTA_'+root.name,planned_prior_attempts=total_attempts(),
        absolute_wall_deadline_unix=min(time.time()+43200,DRAIN_END),planned_current=len(units),
        stage_attempt_cap=CAPS[key]-stage_attempts(key),
        running_receipt='receipts/B/B_D24_QUOTA_'+root.name+'_RUNNING.json',
        result_receipt='receipts/B/B_D24_QUOTA_'+root.name+'_RESULT.json')
    if recipe:
        cfg['target_workers']=recipe['target_workers'];cfg['workers_per_gpu']=cfg['target_workers']//8
        cfg['workers_per_GPU']=cfg['workers_per_gpu'];cfg['evaluation_workers']=cfg['target_workers']
    entered=[read(r/'config/CONFIG.json')['absolute_wall_deadline_unix'] for r in roots(key) if (r/'CLAIM.json').exists() and (r/'CHAIN_COMMAND.json').exists()]
    if entered:cfg['absolute_wall_deadline_unix']=min(cfg['absolute_wall_deadline_unix'],min(entered))
    if key in ['native','R']:
        index=read(Q/'contracts'/(key+'.json'));index['pending']=[u for u in index['pending'] if u['method']+'/'+u['source_id'] in units]
        atomic_json(root/'SOURCE_INDEX.json',index)
        if key=='native':
            choice=gates.selection();loss=choice['chosen_loss'];cfg.update(selected_loss=loss,selected_fit_seed=9101,selected_Q_assets=str(F/'models'/loss),selection_lock=str(root/'SELECTION_LOCK.json'))
            new_json(root/'SELECTION_LOCK.json',dict(status='locked',chosen_loss=loss,fit_seed=9101,A_published_selection=ref(gates.A/'SELECTION.json'),own_candidate=read(F/'CANDIDATES_READY.json')['candidate_assets'][loss],no_test_selection=True))
            cfg['carried_stage_attempts']=stage_attempts(key)
        else:cfg['carried_stage_attempts']=500+stage_attempts(key)
    else:
        choice=gates.selection();t=gates.transfer();cfg.update(selected_loss=choice['chosen_loss'],selected_fit_seed=9101,selection_sha256=sha(gates.A/'SELECTION.json'))
        jobs=[]
        for row in t['nodes']['B']['jobs']:
            if row['H']!=cfg['H']:continue
            original=read(row['path']);ss=[s for s in row['sources'] if original['cell_id']+'__'+s['source_id'] in units]
            if not ss:continue
            job=dict(original,sources=ss,transfer_owner='B');dest=root/'jobs'/(job['job_id']+'.json');new_json(dest,job);jobs.append(dict(job_id=job['job_id'],**ref(dest)))
        new_json(root/'JOB_INDEX.json',dict(jobs=jobs,transfer=ref(gates.AH/'TRANSFER_READY.json')))
        new_json(root/'TRANSFER_SNAPSHOT.json',t)
    atomic_json(root/'config/CONFIG.json',cfg)
    new_json(root/'CONTINUATION.json',dict(utc=utc(),stage=key,reason=reason,recipe=recipe,source_root=str(base),unit_ids=sorted(units),original_failures_preserved=True,scientific_configuration_changed=False,authority=ref(AUTH)))
    return root

def launch(root):
    if (root/'LAUNCH.json').exists() or (root/'CLAIM.json').exists():raise RuntimeError('no replay existing launch')
    with (root/'stdout.log').open('xb') as so,(root/'stderr.log').open('xb') as se:
        p=subprocess.Popen(['/usr/bin/python','-B',str(root/'code/service.py'),'serve'],cwd=root,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    new_json(root/'LAUNCH.json',dict(utc=utc(),process=process_identity(p.pid),argv=['/usr/bin/python','-B',str(root/'code/service.py'),'serve']))
    return p

def collect_error(root):
    pieces=[str(snapshot(root/'RESULT.json')),str(snapshot(root/'chain/MANAGER_EXIT.json'))]
    logs=[root/'stderr.log',root/'daemon.stderr.log',root/'formal.stderr.log']+list((root/'chain').glob('evaluate_*.log'))+list((root/'chain/workers').glob('*/stderr.log'))
    for path in logs:
        if path.exists():
            with path.open('rb') as stream:
                stream.seek(max(0,path.stat().st_size-8000));pieces.append(stream.read().decode(errors='replace'))
    return '\n'.join(pieces)

def publish():
    rows=[];history=[];missing=[]
    for key in BASES:
        valid,latest,claimed,h=outcomes(key);history.extend(dict(stage=key,**v) for v in h)
        # Historical retained R results remain part of the original 500 denominator.
        if key=='R':
            for item in read(BASES[key]/'SOURCE_INDEX.json').get('retained',[]):
                r=read(item['result']['path']);uid='R/'+r['source_id']
                if r['status']=='complete' and uid not in valid:valid[uid]=(r,Path(item['result']['path']))
        for uid,(r,path) in valid.items():
            rows.append(dict(stage=key,unit_id=uid,method=r['method'],source_id=r['source_id'],status='complete',success=r['success'],result=str(path),current_paper=r['method']!='Velocity'))
        try:units=expected(key)
        except (FileNotFoundError,ValueError,KeyError):
            missing.append(dict(stage=key,status='scientific_dependency_pending',success=None));continue
        for uid in units.keys()-valid.keys():
            missing.append(dict(stage=key,unit_id=uid,status=latest[uid][0]['status'] if uid in latest else 'execution_unknown' if uid in claimed else 'unstarted',success=None))
    atomic_json(Q/'FINAL_MISSING.json',missing);atomic_json(Q/'RAW_ATTEMPT_INDEX.json',history)
    atomic_json(Q/'AGGREGATE.json',dict(utc=utc(),rows=rows,missing=missing,cumulative_B_attempts=total_attempts(),new_training_updates=0,original_results_preserved=True,missing_not_failure=True,occupancy_cost_excluded=True))
    for name,subset in [('POST_PAPER.csv',[r for r in rows if r['method']=='Post']),('VELOCITY_OTHER_WORK.csv',[r for r in rows if r['method']=='Velocity']),('FINAL_MISSING.csv',missing)]:
        fields=sorted({k for r in subset for k in r})
        with (Q/name).open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(subset)
    return dict(valid=len(rows),missing=len(missing))
