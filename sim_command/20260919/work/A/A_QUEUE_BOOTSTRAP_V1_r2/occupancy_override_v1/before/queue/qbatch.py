"""A single batch inside the already-held node reservation; never calls guard.run."""
import os
import signal
import time
from pathlib import Path
from qio import new_json, read, ref, utc
from qjobs import mark_entered, snapshot
from qvalidate import validate_batch, artifact_manifest, failure_signature
from authorization import load_authorization, gate
from core.contracts import Meter, reconcile, configure_store
from core.identity import verify_device
from core.handoff import require_handoff_environment
from core.event_recorder import EventRecorder
from core.failure_evidence import record_failure
from core.process_family import drain_group
from process_backend import ProcessBackend
from batch_scheduler import run_schedule, GlobalFault
from batch_storage import BatchMonitor
from controller import branch_allows_next
from pool_protocol import ARMS
from storage import Store


class QueueBackend(ProcessBackend):
    def __init__(self,*args,monitor,**kwargs):
        super().__init__(*args,**kwargs);self.monitor=monitor;self.next_monitor=0
        self.completed=[];self.breaker=snapshot()['node_breakers'].get('A',{}).copy()

    def refresh(self):
        super().refresh()
        if time.monotonic()>=self.next_monitor:
            self.monitor.check();self.next_monitor=time.monotonic()+5

    def record_exit(self,parent,job,row):
        super().record_exit(parent,job,row)
        if not branch_allows_next(job,row) or job==ARMS[-1]:
            path=Path(parent['paths']['output'])/job[0]/'RESOURCE_LEDGER.json'
            error=read(path).get('primary') if path.exists() else None
            signature=failure_signature(error)
            item=dict(parent_key=parent['parent_key'],technical_failure_signature=signature)
            self.completed.append(item)
            if signature:
                n=self.breaker.get('consecutive',0)+1 if self.breaker.get('signature')==signature else 1
                self.breaker.update(signature=signature,consecutive=n)
                if n>=3:raise GlobalFault('three consecutive completed parents share a technical failure signature')
            else:self.breaker.update(signature=None,consecutive=0)


def execute(release_path, proposal, fds, holder_ack):
    p=proposal;root=Path(p['paths']['output']);root.mkdir(parents=True,exist_ok=False)
    out=root/'launcher';out.mkdir();reserved=root/'reserved';reserved.mkdir()
    store=Store(out,byte_limit=p['storage']['root_bytes'],record_limit=32*1024**2,file_limit=256)
    manager=Store(reserved,byte_limit=p['storage']['reserved_root_bytes'],record_limit=32*1024**2,file_limit=256)
    new_json(out/'HOLDER_EXIT_ACK.json',holder_ack)
    mark_entered(p);configure_store(store)
    meter=Meter(out/'events.jsonl',{'native_nvml_identity_queries':len(p['parents'])})
    backend=None;monitor=None;wave=None;cleanup=None;primary=None;validation=None;manifest=None
    phase='full_identity';started=time.monotonic()
    def stop(sig,frame):raise GlobalFault('queue batch signal/phase deadline '+str(sig))
    previous={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP,signal.SIGALRM)}
    try:
        signal.alarm(p['timeouts']['preparation_seconds'])
        r,checked=load_authorization(release_path,True)
        if checked['_sha256']!=ref(r['proposal']['path'])['sha256']:raise GlobalFault('proposal drift')
        cfg=read(p['parents'][0]['config']['path']);require_handoff_environment(cfg,os.environ)
        phase='fixed_NVML_identity'
        for parent in p['parents']:
            cfg=read(parent['config']['path'])
            rows=meter.call('reserved_prechild_NVML_identity',lambda cfg=cfg:verify_device({**r,**cfg['device']},cfg),{'native_nvml_identity_queries':1})
            store.json('NVML_IDENTITY_'+parent['parent_key']+'.json',dict(rows=rows,target=cfg['device']))
        cache=Path(p['paths']['cache']);cache.mkdir(parents=True,exist_ok=False)
        for parent in p['parents']:
            child=Path(parent['paths']['cache']);child.mkdir();(child/'temporary').mkdir();(child/'cache').mkdir()
        monitor=BatchMonitor(p,store);monitor.check()
        backend=QueueBackend(release_path,p,fds,monitor=monitor)
        recorder=EventRecorder(reserved/'SCHEDULER_EVENTS.jsonl',branch='batch_manager',source_id=p['job_id'],
            parent_source_id='not_applicable:batch',split='mixed_fixed_source_splits',synthetic=False,writer=manager)
        phase='cold_parent_wave';signal.alarm(p['timeouts']['reserved_wave_seconds']+p['timeouts']['reserved_wave_grace_seconds'])
        wave=run_schedule(p['parents'],p['concurrency'],backend,gate=lambda:gate(release_path,r['_sha256'],p),
            emit=recorder.emit,limits=p['scheduler_caps'],timeouts=p['timeouts'])
        cleanup=wave['cleanup'];signal.alarm(0)
        new_json(reserved/'PROCESS_GROUP_EXIT.json',cleanup);new_json(reserved/'WAVE_EXIT.json',wave)
        configure_store(None);phase='post_exit_technical_validation'
        signal.alarm(p['timeouts']['technical_validation_seconds'])
        validation=validate_batch(p,wave)
        validation['completion_order_failure_signatures']=backend.completed
        new_json(root/'MACHINE_VALIDATION.json',validation)
        manifest=artifact_manifest(root,root/'FILES.jsonl')
        new_json(root/'DATA_MANIFEST.json',manifest)
    except BaseException as error:
        primary=record_failure(error,branch=None,stage=phase,category='primary')
    finally:
        signal.alarm(0)
        for s in previous:signal.signal(s,signal.SIG_IGN)
        if cleanup is None:
            cleanup=backend.drain() if backend is not None else drain_group(os.getpgrp(),os.getpid())
        configure_store(None)
        if not (reserved/'PROCESS_GROUP_EXIT.json').exists():new_json(reserved/'PROCESS_GROUP_EXIT.json',cleanup)
        if not (reserved/'WAVE_EXIT.json').exists():new_json(reserved/'WAVE_EXIT.json',dict(result=wave,primary=primary,cleanup=cleanup))
        launcher=reconcile(out/'events.jsonl',{'native_nvml_identity_queries':len(p['parents'])})
        okay=primary is None and validation is not None and manifest is not None
        result=dict(schema='queue_batch_launch_result_v1',job_id=p['job_id'],status='complete' if okay else 'failed',
            primary=primary,wave_ref=ref(reserved/'WAVE_EXIT.json'),process_group_exit_ref=ref(reserved/'PROCESS_GROUP_EXIT.json'),
            launcher_private_ledger=launcher,storage_monitor=monitor.summary() if monitor else None,
            validation_ref=ref(root/'MACHINE_VALIDATION.json') if (root/'MACHINE_VALIDATION.json').exists() else None,
            data_manifest_ref=ref(root/'DATA_MANIFEST.json') if (root/'DATA_MANIFEST.json').exists() else None,
            command_opportunity_consumed=True,claim_consumed=True,unused_caps_reusable=False,
            elapsed_seconds=time.monotonic()-started,restoration='deferred_to_queue',no_retry=True,
            private_cost_scopes_not_public_UUIDs=True,publication_is_not_analysis_acceptance=True,
            process_exit_proven=cleanup['status']=='all_formal_group_members_exited',
            publication_complete=bool(okay or (wave is not None and not wave.get('publication_failures'))))
        new_json(out/'LAUNCH_RESULT.json',result)
        new_json(root/'TERMINAL_MANIFEST.json',dict(files=[ref(out/'LAUNCH_RESULT.json'),ref(reserved/'PROCESS_GROUP_EXIT.json'),ref(reserved/'WAVE_EXIT.json')],
            data_manifest=result['data_manifest_ref'],validation=result['validation_ref']))
        for s,handler in previous.items():signal.signal(s,handler)
    return result,validation
