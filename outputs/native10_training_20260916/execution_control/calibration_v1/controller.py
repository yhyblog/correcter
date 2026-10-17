"""Run exactly one frozen calibration wave; monitor technical metadata only."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import fcntl, hashlib, json, os, subprocess, sys, time, traceback

PACKAGE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
ROOT = PACKAGE/'outputs/native10_training_20260916'
CONTROL = ROOT/'execution_control/calibration_v1'
STAGE, BANK, WAVE = 'calibration', 'calibration_policy_v1', 'calibration_v1_01'
READY_SHA = '5cec3558223d18ba9f2b160c478590b8d0ec9b161989f794e6dbcd7983f10138'
THREAD = '01a0a551-9ed3-7f53-9f39-b60d8674819d'

def read(p): return json.loads(Path(p).read_text())
def utc(): return datetime.now(timezone.utc).isoformat()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, value, replace=False):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2)+'\n'
    if replace:
        tmp=p.with_name(p.name+'.writing.'+str(os.getpid()));tmp.write_text(payload);tmp.replace(p)
    else:
        with p.open('x') as stream: stream.write(payload)

def resources():
    with open('/tmp/corrector_native10_training_20260916_budget.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        payload=(ROOT/'budget/attempts.jsonl').read_bytes()
    total=Counter(); stages=defaultdict(Counter); kinds=Counter(); reserve_kinds=Counter();records=0
    for line in payload.splitlines():
        row=json.loads(line);records+=1;total[row['resource']]+=row['amount'];stages[row['stage']][row['resource']]+=row['amount']
        if row['stage']==STAGE:kinds[row['kind']]+=row['amount']
        if row['stage']=='technical_reserve':reserve_kinds[row['kind']]+=row['amount']
    return dict(global_totals=dict(total),stage=dict(stages[STAGE]),by_kind=dict(kinds),
        by_stage={k:dict(v) for k,v in stages.items()},technical_reserve=dict(stages['technical_reserve']),
        reserve_by_kind=dict(reserve_kinds),records=records,ledger_sha256=hashlib.sha256(payload).hexdigest())

def status(state, **info):
    p=PACKAGE/'coordination/NATIVE10_EXECUTOR_STATUS.json'
    with open('/tmp/corrector_native10_executor_status.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);s=read(p);now=utc();s['state']=state;s['blocking_reason']=None
        s['calibration_execution'].update(state=state,updated_utc=now,stage=STAGE,bank_version=BANK,
            wave_id=WAVE,ready_sha256=READY_SHA,controller_pid=os.getpid(),**info)
        totals=info.get('resources',{}).get('global_totals')
        if totals:
            s['global_simulator_attempts']=s['new_simulator_attempts']=totals['simulator_attempts']
            s['actual_optimizer_updates']=s['optimizer_updates']=totals['training_updates']
        for key in ('updated_at','updated_at_utc','updated_utc'):s[key]=now
        write(p,s,True)

def queue(name,message):
    result=subprocess.run(['/home/tiger/.local/bin/codex','queue','--thread',THREAD,'--message',message],capture_output=True,text=True)
    write(CONTROL/(name+'_queue.json'),dict(utc=utc(),message=message,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))

def progress(execution,ids,cases):
    workers=execution/'workers';slots=[]
    for p in workers.glob('worker_*/slots/*.json'):
        try:row=read(p)
        except (FileNotFoundError,json.JSONDecodeError):continue
        if row.get('planned_slot_id') not in ids:raise ValueError('Unregistered calibration primary in runtime output')
        # Worker slot records contain completion metadata, not per-arm success.
        slots.append({k:row.get(k) for k in ('planned_slot_id','resolved_episode_id','status')})
    return dict(loaded_worker_count=len(list(workers.glob('worker_*/loaded_model_identity.json'))),
        completed_worker_count=len(list(workers.glob('worker_*/complete.json'))),
        terminal_primary_slots=len(slots),completed_primary_slots=sum(x['status']=='complete' for x in slots),
        missing_primary_slots=[x['planned_slot_id'] for x in slots if x['status']!='complete'],
        source_initial_scene_seals=sum((ROOT/'sources'/identity/'initial_scene/complete.json').is_file() for identity in cases),
        failure_paths=[str(p) for p in execution.rglob('failure.json')],
        scientific_outcomes_read=False,resources=resources())

def run():
    write(CONTROL/'started.json',dict(pid=os.getpid(),utc=utc(),stage=STAGE,bank_version=BANK,wave_id=WAVE))
    frozen=read(CONTROL/'freeze_result.json')
    if frozen.get('status')!='passed' or frozen['ready_sha256']!=READY_SHA:raise ValueError('Exact corrected READY freeze is required')
    from experiments.native10_training_20260916 import calibration_runner_v1 as runner
    config=runner.verify_frozen(frozen['config'],frozen['freeze'],STAGE,BANK,32)
    if sha(config['analysis_ready']['path'])!=READY_SHA:raise ValueError('Frozen READY identity changed')
    ids=config['main_collection']['banks'][BANK]['episode_ids'];backups=config['main_collection']['replacement_candidates']
    cases=ids+[backup for identity in ids for backup in backups[identity]]
    before=resources()
    if before['global_totals']!={'simulator_attempts':44869,'training_updates':51200} or before['stage'] or before['technical_reserve']:
        raise ValueError('Previously attempted calibration or changed starting budget; no repeat')
    command=[sys.executable,'-u','-m','experiments.native10_training_20260916.calibration_runner_v1','launch',
        '--config',frozen['config'],'--freeze',frozen['freeze'],'--stage',STAGE,'--bank-version',BANK,'--wave-id',WAVE,'--workers','32']
    started=utc();begin=time.perf_counter();execution=runner.execution_root(STAGE,BANK,WAVE)
    with (CONTROL/'wave.log').open('x') as log:
        process=subprocess.Popen(command,cwd=PACKAGE,stdout=log,stderr=subprocess.STDOUT)
        write(CONTROL/'actual_launch.json',dict(started_utc=started,pid=process.pid,controller_pid=os.getpid(),
            command=command,config_sha256=frozen['config_sha256'],freeze_sha256=frozen['freeze_sha256'],
            ready_sha256=READY_SHA,stage_cap=1200,optimizer_updates=0,primary_capture_limit=100,
            bank_restore_limit=100,branch_limit=1000,lifecycle_owned_by_runner=True,loaded_workers_at_launch=0))
        status('calibration_wave_running',actual_started=True,started_utc=started,pid=process.pid,frozen=frozen,
            loaded_worker_count=0,completed_primary_slots=0,resources=before)
        queue('actual_launch',f'[native10 calibration actual launch] UTC{started} PID{process.pid}; corrected READYv12 {READY_SHA}; config {frozen["config_sha256"]}; freeze {frozen["freeze_sha256"]}. A4000原cal100/五任务20/五个未加门臂×2，cal1200sim/0opt，共用reserve1200仅预登记初始替补。lifecycle8GPU×4worker入口已启动，当前装载不等于已产数据。{CONTROL}。完整100审计后仅proposal，未授权选择封存/held。')
        while process.poll() is None:
            snapshot=dict(utc=utc(),phase='running',wall_seconds=time.perf_counter()-begin,**progress(execution,ids,cases))
            write(CONTROL/'progress.json',snapshot,True);status('calibration_wave_running',**{k:v for k,v in snapshot.items() if k not in ('utc','phase')})
            time.sleep(30)
        rc=process.wait()
    after=resources();snapshot=dict(utc=utc(),phase='exited',wall_seconds=time.perf_counter()-begin,**progress(execution,ids,cases))
    write(CONTROL/'progress.json',snapshot,True)
    write(CONTROL/'wave_result.json',dict(returncode=rc,started_utc=started,finished_utc=utc(),wall_seconds=time.perf_counter()-begin,
        resources=after,attempts_preserved=True,automatic_retry=False,**{k:snapshot[k] for k in ('completed_primary_slots','terminal_primary_slots','missing_primary_slots')}))
    holder=read('/tmp/gpu_occupancy_guard/status.json')
    for _ in range(15):
        if len(holder.get('gpus',{}))==8 and all(x.get('state')=='holder' for x in holder['gpus'].values()):break
        time.sleep(2);holder=read('/tmp/gpu_occupancy_guard/status.json')
    write(CONTROL/'gpu_after_wave.json',holder)
    if rc:raise RuntimeError('Calibration wave failed; attempts preserved, no automatic retry')
    if snapshot['completed_primary_slots']!=100 or snapshot['terminal_primary_slots']!=100 or snapshot['failure_paths']:
        raise RuntimeError('Incomplete calibration slots: no selection proposal is permitted')
    kinds=after['by_kind'];banks=kinds.get('candidate_restore',0)
    if (kinds.get('source_capture')!=100 or kinds.get('branch_including_restore',0)!=10*banks
            or after['stage']!={'simulator_attempts':100+11*banks} or banks>100
            or after['technical_reserve'].get('simulator_attempts',0)>1200
            or after['global_totals']['training_updates']!=51200
            or after['global_totals']['simulator_attempts']>50000):
        raise RuntimeError('Calibration resource closure differs from capture/bank/five-arm accounting')
    result=dict(status='wave_complete_pending_full_audit',frozen=frozen,resources=after,completed_primary_slots=100,
        scientific_outcomes_read=False,selection_seal_created=False,heldout_started=False,automatic_next_stage=False)
    write(CONTROL/'result.json',result);status('calibration_wave_complete_pending_full_audit',resources=after,completed_primary_slots=100)
    queue('wave_complete',f'[native10 calibration wave complete] 全100主槽技术完成，lifecycle rc0；cal{after["stage"]["simulator_attempts"]}attempts {kinds}，global{after["global_totals"]}，reserve{after["technical_reserve"]}。{CONTROL}/result.json。root继续已授权全量只读审计与proposal；未读取中途收益，未封存选择/启动held。')

if __name__=='__main__':
    try:run()
    except BaseException as error:
        failure=dict(status='failed_no_automatic_retry',utc=utc(),error=repr(error),traceback=traceback.format_exc(),resources=resources())
        write(CONTROL/'controller_failure.json',failure);status('calibration_technical_failure',failure_path=str(CONTROL/'controller_failure.json'),resources=failure['resources'])
        queue('technical_failure',f'[native10 calibration technical failure] {error}; attempts/logs preserved, no automatic retry. {CONTROL}/controller_failure.json')
        raise
