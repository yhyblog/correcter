"""Operational CPU observer for an existing, separately frozen round2 wave.

No models, environments, branch outcomes, source success labels, training or
scientific statistics. Notifications are opt-in. No retry or next-stage launch
of experiment work occurs. --self-test uses only synthetic temporary metadata.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest
from unittest import mock
import uuid


PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE/'outputs/native10_training_20260916'
STATUS = PACKAGE/'coordination/NATIVE10_EXECUTOR_STATUS.json'
STAGE, BANK = 'round2_labels', 'round2_labels_v1'
MODULE = 'experiments.native10_training_20260916.round2_runner_v1'
ANALYSIS_THREAD = '01a0a551-9ed3-7f53-9f39-b60d8674819d'
BUDGET_LOCK = Path('/tmp/corrector_native10_training_20260916_budget.lock')
STATUS_LOCK = Path('/tmp/corrector_native10_executor_status.lock')


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, value):
    path=Path(path);path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_name(path.name+'.writing.'+uuid.uuid4().hex)
    with temporary.open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def component(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',value):
        raise ValueError('Unsafe wave path component')
    return value


def cohort(config):
    bank=config['main_collection']['banks'][BANK]
    ids=bank['episode_ids'];lookup={r['episode_id']:r for r in config['episode_manifest']}
    if (bank['kind']!='labels13' or bank['stage']!=STAGE or bank['generation_round']!=2
            or len(ids)!=300 or len(set(ids))!=300
            or any(lookup[k]['split']!='train' or lookup[k]['round']!=2 or lookup[k].get('replacement_of') for k in ids)):
        raise ValueError('Observer only supports the frozen 300 primary round2 training slots')
    return ids,lookup


def process(pid):
    try:
        base=Path('/proc')/str(pid);fields=(base/'stat').read_text().rsplit(')',1)[1].split()
        args=[part.decode(errors='replace') for part in (base/'cmdline').read_bytes().split(b'\0') if part]
        return dict(pid=pid,start_ticks=int(fields[19]),state=fields[0],args=args)
    except (OSError,ValueError,IndexError):
        return None


def launch_alive(pid,ticks):
    actual=process(pid)
    return actual is not None and actual['start_ticks']==ticks and actual['state']!='Z'


def validate_process(actual,pid,ticks,config_path,wave_id):
    if (actual is None or actual['pid']!=pid or actual['start_ticks']!=ticks or actual['state']=='Z'
            or MODULE not in actual['args'] or 'launch' not in actual['args']
            or str(config_path) not in actual['args'] or wave_id not in actual['args']):
        raise ValueError('PID/start_ticks does not identify the supplied round2 launch')


def ledger_snapshot(path,lock_path=BUDGET_LOCK):
    # Same lock as the writer; a read never reserves or discounts an attempt.
    with Path(lock_path).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        raw=Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Partial ledger record')
    rows=[json.loads(line) for line in raw.splitlines()]
    numbers=[row['number'] for row in rows]
    if len(set(numbers))!=len(numbers) or any(type(n) is not int or n<1 for n in numbers):
        raise ValueError('Duplicate/invalid ledger attempt number')
    return rows,hashlib.sha256(raw).hexdigest()


def metadata(folder,name,protocol):
    """Read only a specified technical metadata file from a completed artifact."""
    seal=read(Path(folder)/'complete.json')
    if (seal.get('status')!='complete' or seal.get('protocol_sha256')!=protocol
            or seal.get('files',{}).get(name)!=sha(Path(folder)/name)):
        raise ValueError('Technical metadata seal mismatch: '+str(folder))
    return read(Path(folder)/name)


def collection_complete(folder,protocol,expected_sha):
    # The summary contains outcomes: hash its bytes for identity, never parse it.
    seal_path=Path(folder)/'complete.json'
    if sha(seal_path)!=expected_sha:
        raise ValueError('Completed collection seal SHA differs from worker slot')
    seal=read(seal_path)
    if (seal.get('status')!='complete' or seal.get('protocol_sha256')!=protocol
            or seal.get('files',{}).get('summary.json')!=sha(Path(folder)/'summary.json')):
        raise ValueError('Completed collection summary SHA mismatch')


def loaded_identity(record,config):
    selected=Path(config['critic_assets']).resolve()
    hashes=config['main_collection']['banks'][BANK]['critic_member_hashes']
    expected=[str(selected/f'models/refit/member_{member}/selected.pt') for member in hashes]
    required={'actual_selector_paths','checkpoint_file_sha','frozen_parameter_buffer_versions','eval_cpu_no_parameter_grad'}
    if (record.get('status')!='passed' or Path(record.get('selected_path','')).resolve()!=selected
            or record.get('model_hashes')!=hashes or record.get('model_paths')!=expected
            or record.get('selected_seal_sha256')!=config['round2_collection']['selected_training']['selected_seal_sha256']
            or not required <= set(record.get('checks',[])) or record.get('optimizer_updates')!=0
            or record.get('candidate_generation_only') is not True):
        raise ValueError('Actual loaded model identity differs from frozen B200')
    return dict(status='passed',selected_path=str(selected),model_hashes=hashes,
                selected_seal_sha256=record['selected_seal_sha256'],checks=record['checks'])


def snapshot(config,wave,*,root=ROOT,ledger_lock=BUDGET_LOCK,expected_training_updates=19200):
    ids,lookup=cohort(config);wave=Path(wave);root=Path(root)
    protocol=config['analysis_approval']['protocol_sha256'];errors=[];pending=[]
    workers=sorted((wave/'workers').glob('worker_[0-9][0-9]'))
    loaded=[];statuses=Counter();failures=[];terminal={};completed=[];missing=[]
    for folder in workers:
        try:
            rank=int(folder.name[-2:])
            if rank not in range(32):raise ValueError('Worker rank outside frozen 32-worker layout')
            assigned=set(ids[rank::32])
            path=folder/'loaded_model_identity.json'
            if path.exists():
                identity=loaded_identity(read(path),config)
                loaded.append(dict(worker=folder.name,path=str(path),sha256=sha(path),**identity))
            if (folder/'failure.json').exists():
                record=read(folder/'failure.json')
                failures.append(dict(worker=folder.name,path=str(folder/'failure.json'),
                    error_type=record.get('error_type'),message=str(record.get('error',''))[:400],
                    attempts_not_rolled_back=record.get('attempts_not_rolled_back'),automatic_retry=False))
            if (folder/'status.json').exists():
                record=read(folder/'status.json')
                statuses[record.get('status','unknown')]+=1
                if record.get('status') not in ('complete','complete_with_missing_slots'):
                    raise ValueError('Unexpected worker final status')
            for path in sorted((folder/'slots').glob('*.json')):
                slot=read(path);primary=slot.get('planned_slot_id');actual=slot.get('resolved_episode_id')
                if primary not in assigned or path.stem!=primary or primary in terminal:
                    raise ValueError('Worker slot identity/assignment/uniqueness mismatch')
                chain=[primary]+config['main_collection'].get('replacement_candidates',{}).get(primary,[])
                if slot.get('status')=='complete':
                    if actual not in chain:raise ValueError('Unregistered resolved source')
                    resolution=metadata(root/'slot_resolution'/primary,'resolution.json',protocol)
                    if resolution.get('planned_slot_id')!=primary or resolution.get('resolved_episode_id')!=actual or resolution.get('status')!='resolved':
                        raise ValueError('Slot resolution metadata differs')
                    dest=root/'collections'/STAGE/BANK/lookup[actual]['case_id']
                    if Path(slot.get('completion_path','')).resolve()!=dest.resolve():
                        raise ValueError('Slot points outside its registered collection')
                    collection_complete(dest,protocol,slot['completion_sha256'])
                    completed.append(primary)
                elif slot.get('status')=='missing_unique_initial_scene':
                    if actual is not None or slot.get('outcome_unknown') is not True:
                        raise ValueError('Missing slot cannot claim a resolved outcome')
                    if [r.get('episode_id') for r in slot.get('ordered_rejections',[])]!=chain:
                        raise ValueError('Missing source must exhaust the registered pre-action chain')
                    for episode in chain:
                        rejection=metadata(root/'sources'/lookup[episode]['case_id'],'rejection.json',protocol)
                        if (rejection.get('before_first_action') is not True or rejection.get('outcome_not_observed') is not True
                                or rejection.get('control_steps_executed')!=0
                                or rejection.get('reason') not in ('initialization_failed','duplicate_initial_scene')):
                            raise ValueError('Missing-source chain is not pre-action only')
                    missing.append(primary)
                else:
                    raise ValueError('Unknown terminal slot status')
                terminal[primary]=slot['status']
        except json.JSONDecodeError:
            # A writer creates JSON exclusively, then flushes: incomplete
            # unsealed metadata may be transient for one polling interval.
            pending.append(str(folder))
        except (OSError,ValueError,KeyError,TypeError) as error:
            errors.append(dict(path=str(folder),error_type=type(error).__name__,message=str(error)[:500]))
    rows,ledger_sha=ledger_snapshot(root/'budget/attempts.jsonl',ledger_lock)
    totals=Counter();stages=defaultdict(Counter);kinds=Counter();captures=[]
    for row in rows:
        amount=row['amount']
        if type(amount) is not int or amount<1:raise ValueError('Invalid charged ledger amount')
        resource=row['resource'];totals[resource]+=amount;stages[row['stage']][resource]+=amount
        if row['stage']==STAGE and resource=='simulator_attempts':
            kinds[row['kind']]+=amount
            if row['kind']=='source_capture':
                captures.append({key:row.get(key) for key in ('number','identity','unix','stage')})
    limits=config['budget']['stages'];budget_ok=totals['simulator_attempts']<=config['budget']['hard_total']
    budget_ok=budget_ok and totals['training_updates']<=config['budget']['training_update_total']
    for stage,resources in stages.items():
        for resource,amount in resources.items():
            budget_ok=budget_ok and stage in limits and amount<=limits.get(stage,{}).get(resource,-1)
    progress=dict(updated_at=utc(),stage=STAGE,bank_version=BANK,wave_id=wave.name,
        planned_primary_slots=300,worker_directories=len(workers),expected_workers=32,
        actual_loaded_model_identity_count=len(loaded),actual_loaded_models=loaded,
        loading_directories_without_identity=len(workers)-len(loaded),worker_status_counts=dict(statuses),
        source_capture_attempts_reserved=len(captures),first_source_capture=captures[0] if captures else None,
        completed_primary_collections=len(completed),terminal_primary_slots=len(terminal),
        completed_primary_ids=sorted(completed,key=ids.index),missing_unique_initial_scene_ids=sorted(missing,key=ids.index),
        all_300_terminal=len(terminal)==300,all_300_collections_complete=len(completed)==300,
        ledger_records=len(rows),ledger_sha256=ledger_sha,resource_totals=dict(totals),
        resources_by_stage={stage:dict(value) for stage,value in stages.items()},stage_attempts_by_kind=dict(kinds),
        stage_simulator_attempts=stages[STAGE]['simulator_attempts'],stage_limit=limits[STAGE]['simulator_attempts'],
        stage_training_updates=stages[STAGE]['training_updates'],expected_global_training_updates=expected_training_updates,
        unexpected_training_updates=totals['training_updates']!=expected_training_updates,
        technical_reserve_used=stages['technical_reserve']['simulator_attempts'],
        technical_reserve_limit=limits['technical_reserve']['simulator_attempts'],budget_within_limits=bool(budget_ok),
        worker_failures=failures,metadata_errors=errors,unsealed_metadata_pending=pending,
        scientific_outcomes_read=False,branch_results_read=False,scientific_statistics_computed=False,
        automatic_experiment_retry=False,next_stage_automatically_started=False,
        completion_note='Technical progress only; failed attempts stay charged and full static dataset audit is still required.')
    problems=[]
    if failures:problems.append('worker_failure')
    if errors:problems.append('metadata_error')
    if not budget_ok:problems.append('budget_violation')
    if progress['unexpected_training_updates'] or progress['stage_training_updates']:problems.append('unexpected_training_updates')
    progress['technical_problems']=problems
    return progress


def merge_status(progress,path=STATUS,lock_path=STATUS_LOCK):
    """Own only round2_runtime. Other status fields remain byte-value equivalent."""
    with Path(lock_path).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        status=read(path)
        old=status.get('round2_runtime',{})
        if old.get('wave_id') not in (None,progress['wave_id']):
            raise ValueError('A different round2 wave owns shared operational status')
        status['round2_runtime']=progress
        atomic(path,status)


def record_event(state,state_path,folder,key,progress):
    if key in state['events']:return
    destination=Path(folder)/'notifications'/key
    event=dict(event=key,created_at=utc(),wave_id=state['wave_id'],config_sha256=state['config_sha256'],
        watcher_sha256=state['watcher_sha256'],progress=progress,
        instruction='请复核技术状态；完整阶段后执行静态数据审计。watcher不自动重试、训练或启动下一阶段。',
        simulator_attempts=0,optimizer_updates=0,scientific_outcomes_read=False)
    if destination.exists():
        saved=read(destination/'event.json');seal=read(destination/'complete.json')
        if (saved.get('event')!=key or saved.get('config_sha256')!=state['config_sha256']
                or seal.get('status')!='complete' or seal.get('files',{}).get('event.json')!=sha(destination/'event.json')):
            raise ValueError('Existing notification evidence differs')
    else:
        destination.mkdir(parents=True,exist_ok=False)
        with (destination/'event.json').open('x') as stream:json.dump(event,stream,ensure_ascii=False,indent=2)
        with (destination/'complete.json').open('x') as stream:
            json.dump(dict(status='complete',role='round2_technical_notification_evidence',
                files={'event.json':sha(destination/'event.json')},simulator_attempts=0,optimizer_updates=0),stream,indent=2)
    state['events'][key]=dict(evidence_path=str(destination),seal_sha256=sha(destination/'complete.json'),recipients={})
    atomic(state_path,state)


def deliver(state,state_path,*,notify=False,codex='codex',runner=subprocess.run):
    if not notify:return
    for key,event in state['events'].items():
        for role,thread in state['targets'].items():
            old=event['recipients'].get(role,{})
            if old.get('status') in ('sent','ambiguous') or time.time()<old.get('retry_after_unix',0):continue
            if old.get('status')=='inflight':
                old.update(status='ambiguous',error='Prior dispatch interrupted; inspect event ID before manual retry')
                atomic(state_path,state);continue
            item=dict(status='inflight',thread=thread,attempts=old.get('attempts',0)+1,started_at=utc())
            event['recipients'][role]=item;atomic(state_path,state)
            message=f"[round2 watcher {state['wave_id']}:{key}] 技术通知：{event['evidence_path']}。未读取部分成功率；请复核并在阶段完成后安排静态数据审计，不自动启动下一阶段。"
            try:
                done=runner([codex,'queue','--thread',thread,'--message',message],text=True,capture_output=True,timeout=20)
                output=(done.stdout+'\n'+done.stderr)[-1500:]
                if done.returncode==0 and re.search(r'Queued message \S+ for thread ',output):
                    item.update(status='sent',sent_at=utc(),response=output[-500:])
                else:item.update(status='failed',error=output,returncode=done.returncode,retry_after_unix=time.time()+60)
            except subprocess.TimeoutExpired:
                item.update(status='ambiguous',error='Queue timeout; no automatic duplicate delivery')
            except OSError as error:
                item.update(status='failed',error=str(error),retry_after_unix=time.time()+60)
            atomic(state_path,state)


def event_keys(progress,launch_result,alive):
    keys=[]
    if progress['technical_problems']:keys.append('runtime_technical_failure')
    if progress['all_300_terminal']:keys.append('all_300_slots_terminal')
    if launch_result is not None:
        okay=launch_result.get('status')=='complete' and launch_result.get('returncode')==0
        if okay and progress['all_300_terminal'] and not progress['technical_problems']:
            keys.append('wave_exited_complete_requires_dataset_audit')
        else:keys.append('wave_exited_failed_or_incomplete')
    elif alive is False:keys.append('launch_process_exited_without_result')
    return keys


def observe(args):
    config_path=args.config.resolve();config=read(config_path);cohort(config)
    freeze_path=args.freeze.resolve() if args.freeze else config_path.with_name('freeze.json')
    freeze=read(freeze_path);config_sha=sha(config_path)
    if freeze.get('config_sha256')!=config_sha or freeze.get('files',{}).get(str(config_path))!=config_sha:
        raise ValueError('Watcher config is not bound by supplied freeze')
    wave=ROOT/'round2_execution'/STAGE/BANK/component(args.wave_id)
    spec=read(wave/'wave_spec.json')
    if (spec.get('config_sha256')!=config_sha or spec.get('freeze_sha256')!=sha(freeze_path)
            or spec.get('stage')!=STAGE or spec.get('bank_version')!=BANK or spec.get('workers')!=32):
        raise ValueError('Wave spec/config/freeze identity differs')
    folder=ROOT/'progress_audits/round2_runtime'/args.wave_id
    folder.mkdir(parents=True,exist_ok=True);state_path=folder/'state.json'
    lock_path=Path('/tmp/round2_runtime_watch_'+hashlib.sha256(str(folder).encode()).hexdigest()+'.lock')
    with lock_path.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another watcher already owns this wave')
        identity=dict(wave_id=args.wave_id,config_sha256=config_sha,freeze_sha256=sha(freeze_path),
            watcher_sha256=sha(__file__),wave_pid=args.wave_pid,wave_start_ticks=args.wave_start_ticks,
            expected_training_updates=args.expected_training_updates,
            targets=dict(analysis=args.analysis_thread,executor=args.executor_thread))
        if state_path.exists():
            state=read(state_path)
            if any(state.get(k)!=v for k,v in identity.items()):raise ValueError('Watcher resume identity changed')
        else:
            if not (wave/'launch_result.json').exists():
                validate_process(process(args.wave_pid),args.wave_pid,args.wave_start_ticks,config_path,args.wave_id)
            state=dict(identity,started_at=utc(),events={});atomic(state_path,state)
        while True:
            try:
                if sha(config_path)!=config_sha or sha(freeze_path)!=state['freeze_sha256']:
                    raise ValueError('Observed frozen config/freeze changed')
                progress=snapshot(config,wave,expected_training_updates=args.expected_training_updates)
            except (OSError,ValueError,KeyError,TypeError) as error:
                progress=dict(updated_at=utc(),wave_id=args.wave_id,stage=STAGE,bank_version=BANK,
                    all_300_terminal=False,technical_problems=['observer_metadata_failure'],
                    error_type=type(error).__name__,message=str(error)[:700],scientific_outcomes_read=False)
            alive=launch_alive(args.wave_pid,args.wave_start_ticks)
            result_path=wave/'launch_result.json';result=None
            if result_path.exists():
                try:
                    data=read(result_path)
                    result={k:data.get(k) for k in ('status','returncode','wall_seconds_including_lifecycle','next_stage_automatically_started')}
                except (OSError,json.JSONDecodeError):progress['launch_result_pending']=True
            progress.update(launch_process_alive=alive,launch_result=result,config_sha256=config_sha,
                observer_only=True,notifications_enabled=args.notify)
            atomic(folder/'latest.json',progress);merge_status(progress)
            for key in event_keys(progress,result,alive if not progress.get('launch_result_pending') else None):
                record_event(state,state_path,folder,key,progress)
            deliver(state,state_path,notify=args.notify,codex=args.codex)
            ended=result is not None or not alive and not progress.get('launch_result_pending')
            if args.once:return
            # Notification transport failures may retry, experiment work never does.
            pending_delivery=args.notify and any(item.get('status')=='failed' for event in state['events'].values() for item in event['recipients'].values())
            if ended and not pending_delivery:return
            time.sleep(args.interval)


def self_test():
    class Checks(unittest.TestCase):
        def test_status_merge_preserves_other_scopes(self):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'status.json';atomic(p,dict(state='unchanged',models={'id':1},round1={'done':True}))
                merge_status(dict(wave_id='w',count=3),p,Path(d)/'lock')
                self.assertEqual(read(p),dict(state='unchanged',models={'id':1},round1={'done':True},round2_runtime=dict(wave_id='w',count=3)))
        def test_other_wave_rejected(self):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'status';atomic(p,dict(round2_runtime=dict(wave_id='old')))
                with self.assertRaises(ValueError):merge_status(dict(wave_id='new'),p,Path(d)/'lock')
        def test_pid_reuse(self):
            with self.assertRaises(ValueError):validate_process(dict(pid=1,start_ticks=3,state='S',args=[]),1,2,Path('/x'),'w')
        def test_no_notify_no_subprocess(self):
            runner=mock.Mock();deliver({'events':{'x':{}}},Path('/not-written'),runner=runner);runner.assert_not_called()
        def test_notifications_once_and_sealed(self):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d);state=dict(wave_id='w',config_sha256='x',watcher_sha256='y',targets={'analysis':'a','executor':'b'},events={})
                record_event(state,p/'state',p,'completed',{'scientific_outcomes_read':False})
                record_event(state,p/'state',p,'completed',{})
                runner=mock.Mock(return_value=subprocess.CompletedProcess([],0,'Queued message m for thread t',''))
                deliver(state,p/'state',notify=True,runner=runner);deliver(state,p/'state',notify=True,runner=runner)
                self.assertEqual(runner.call_count,2)
                self.assertEqual(read(p/'notifications/completed/complete.json')['status'],'complete')
        def test_queue_timeout_not_retried(self):
            with tempfile.TemporaryDirectory() as d:
                state=dict(wave_id='w',targets={'executor':'e'},events={'failure':dict(evidence_path='e',recipients={})})
                runner=mock.Mock(side_effect=subprocess.TimeoutExpired('mock',20))
                deliver(state,Path(d)/'state',notify=True,runner=runner);deliver(state,Path(d)/'state',notify=True,runner=runner)
                self.assertEqual(runner.call_count,1);self.assertEqual(state['events']['failure']['recipients']['executor']['status'],'ambiguous')
        def test_queue_failure_retry_preserved(self):
            with tempfile.TemporaryDirectory() as d:
                state=dict(wave_id='w',targets={'executor':'e'},events={'failure':dict(evidence_path='e',recipients={})})
                runner=mock.Mock(return_value=subprocess.CompletedProcess([],1,'','failure'))
                deliver(state,Path(d)/'state',notify=True,runner=runner)
                self.assertEqual(state['events']['failure']['recipients']['executor']['status'],'failed')
                deliver(state,Path(d)/'state',notify=True,runner=runner);self.assertEqual(runner.call_count,1)
        def test_exit_without_result(self):
            self.assertEqual(event_keys(dict(technical_problems=[],all_300_terminal=False),None,False),['launch_process_exited_without_result'])
        def test_full_terminal_not_automatic_next_stage(self):
            keys=event_keys(dict(technical_problems=[],all_300_terminal=True),dict(status='complete',returncode=0),False)
            self.assertEqual(keys,['all_300_slots_terminal','wave_exited_complete_requires_dataset_audit'])
        def test_failure_immediate(self):
            self.assertIn('runtime_technical_failure',event_keys(dict(technical_problems=['worker_failure'],all_300_terminal=False),None,True))
        def test_ledger_failure_stays_charged(self):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'ledger';p.write_text(json.dumps(dict(number=1,amount=1,status='failed'))+'\n')
                rows,_=ledger_snapshot(p,Path(d)/'lock');self.assertEqual(rows[0]['amount'],1)
        def test_duplicate_ledger_rejected(self):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'ledger';p.write_text('{"number":1}\n{"number":1}\n')
                with self.assertRaises(ValueError):ledger_snapshot(p,Path(d)/'lock')
        def test_collection_outcomes_not_deserialized(self):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d);(p/'summary.json').write_text('NOT JSON; watcher must only hash these bytes')
                atomic(p/'complete.json',dict(status='complete',protocol_sha256='p',files={'summary.json':sha(p/'summary.json')}))
                collection_complete(p,'p',sha(p/'complete.json'))
        def test_model_identity_not_directory_existence(self):
            cfg=dict(critic_assets='/model',main_collection=dict(banks={BANK:dict(critic_member_hashes={'0':'h'})}),round2_collection=dict(selected_training=dict(selected_seal_sha256='s')))
            with self.assertRaises(ValueError):loaded_identity(dict(status='passed',selected_path='/model'),cfg)
        def test_snapshot_loading_and_first_attempt_separate(self):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);wave=root/'wave';(wave/'workers/worker_00').mkdir(parents=True)
                ids=[f'task__{i}' for i in range(300)]
                cfg=dict(main_collection=dict(banks={BANK:dict(kind='labels13',stage=STAGE,generation_round=2,episode_ids=ids)}),
                    episode_manifest=[dict(episode_id=i,case_id=i,split='train',round=2) for i in ids],
                    analysis_approval=dict(protocol_sha256='p'),budget=dict(hard_total=50000,training_update_total=51200,
                        stages={STAGE:dict(simulator_attempts=17400,training_updates=0),technical_reserve:dict(simulator_attempts=1200,training_updates=0)}))
                path=root/'budget/attempts.jsonl';path.parent.mkdir();path.write_text(json.dumps(dict(number=1,amount=1,stage=STAGE,kind='source_capture',resource='simulator_attempts',identity=ids[0],unix=1))+'\n')
                progress=snapshot(cfg,wave,root=root,ledger_lock=root/'lock',expected_training_updates=0)
                self.assertEqual((progress['worker_directories'],progress['actual_loaded_model_identity_count'],progress['source_capture_attempts_reserved']),(1,0,1))
                self.assertFalse(progress['scientific_outcomes_read']);self.assertEqual(progress['completed_primary_collections'],0)
    # A constant variable keeps fixture dictionaries explicit and valid Python.
    technical_reserve='technical_reserve'
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    if not result.wasSuccessful():raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path);parser.add_argument('--freeze',type=Path)
    parser.add_argument('--wave-id');parser.add_argument('--wave-pid',type=int);parser.add_argument('--wave-start-ticks',type=int)
    parser.add_argument('--analysis-thread',default=ANALYSIS_THREAD);parser.add_argument('--executor-thread')
    parser.add_argument('--notify',action='store_true',help='Opt-in authorized Codex queue notifications to both supplied threads')
    parser.add_argument('--codex',default='codex');parser.add_argument('--interval',type=float,default=60.)
    parser.add_argument('--expected-training-updates',type=int,default=19200)
    parser.add_argument('--once',action='store_true');parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test:
        if any((args.config,args.freeze,args.wave_id,args.wave_pid,args.wave_start_ticks,args.executor_thread,args.notify,args.once)):
            parser.error('Synthetic self-test cannot use live inputs, notifications or state')
        self_test();return
    if not all((args.config,args.wave_id,args.wave_pid,args.wave_start_ticks,args.executor_thread)):
        parser.error('Supply existing --config --wave-id --wave-pid --wave-start-ticks --executor-thread')
    if args.interval<60 or args.analysis_thread==args.executor_thread:
        parser.error('Use interval>=60 and two distinct authorized threads')
    observe(args)


if __name__=='__main__':main()
