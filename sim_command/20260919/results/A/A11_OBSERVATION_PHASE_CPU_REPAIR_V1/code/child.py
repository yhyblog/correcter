import inheritance
"""Future single collector attempt. Never executed in CPU preparation."""
import argparse,json,os,sys,time
from pathlib import Path
from authorization import load_authorization,gate
from core.contracts import PACKAGE,ContractError,read,Meter,reconcile,configure_store
from core.identity import verify_device
from core.event_recorder import EventRecorder
from core.failure_evidence import record_failure
from core.wave_timing import held_reservation_fds
from budget import numeric_caps,attempt_caps,sum_units,STORAGE
from native.initialization import InitializationAudit,EXPECTED_CAPS
from native.graphics_contract import reconcile as graphics_reconcile
from native.native_egl import NativeEGL
from storage import Store
from pool_protocol import ARMS
from controller import run_attempt
def main():
    p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--branch',required=True,choices=[j[0] for j in ARMS]);a=p.parse_args()
    r,proposal=load_authorization(a.release,True)
    if not held_reservation_fds():raise ContractError('inherited reservation required')
    claim=read(proposal['paths']['claim'])
    if claim['release_sha256']!=r['_sha256'] or claim['run_id']!=r['identity']['run_id']:raise ContractError('claim mismatch')
    parent=Path(proposal['paths']['output']);out=parent/a.branch;out.mkdir(exist_ok=False)
    store=Store(out);configure_store(store);gate_fn=lambda:gate(a.release,r['_sha256'],proposal)
    job=next(j for j in ARMS if j[0]==a.branch);cfg=read(proposal['config']['path'])
    cfg['_normal_output']=str(parent/'normal')
    reference=None
    if a.branch!='normal':
        reference=read(parent/'normal/CUT_REFERENCE.json')
        from shared_plans import prepare_bank_reference
        prepare_bank_reference(cfg,parent,synthetic=False)
    identity=dict(r['identity'],campaign_id=r['campaign_id'],hostname=r['owner_host'],driver=cfg['device']['driver'],
        runtime='torch2.7.1+cu126_mujoco3.6.0_metaworld3.0.0',gpu_model=cfg['device']['gpu_model'],
        code_sha256=proposal['code_manifest']['sha256'],config_sha256=proposal['config']['sha256'],
        data_manifest_sha256=proposal['input_manifest']['sha256'],model_sha256=cfg['model_sha256'])
    identity.pop('release_path',None);identity.pop('task_revision',None)
    meter=Meter(out/'numeric_events.jsonl',numeric_caps(a.branch),gate_fn)
    init=InitializationAudit(out/'initialization_events.jsonl',EXPECTED_CAPS,gate_fn)
    egl=NativeEGL(cfg['native'],out,gate_fn);engine=None;error=None;cleanup=[];phase='start';result=None;started=time.monotonic()
    recorder=EventRecorder(out/'events.jsonl',branch=a.branch,source_id=cfg['source']['source_id'],
        parent_source_id=cfg['source']['parent_source_id'],split='train',synthetic=False,writer=store)
    try:
        meter.call('collector_attempt',lambda:None,{'simulator_attempts':1})
        phase='NVML';rows=meter.call('reserved_NVML_identity',lambda:verify_device({**r,**cfg['device']},cfg),{'native_nvml_identity_queries':1})
        store.json('NVML_IDENTITY.json',dict(rows=rows,target=cfg['device']))
        phase='EGL';egl.prepare()
        phase='runtime_import';sys.path.insert(0,str(inheritance.BASE_CODE/'vendor_vla/src'))
        from runtime_engine import Engine
        phase='model_load';engine=Engine(cfg,out,meter,egl,init,job,store,identity);engine.recorder=recorder
        phase='controller';result=run_attempt(engine,job,recorder,reference)
    except BaseException as e:
        error=record_failure(e,branch=a.branch,stage=phase,category='primary')
        try:store.json('FAILURE.json',error,emergency=True)
        except BaseException:pass  # external parent retains exit/missing evidence; never claim saved
    finally:
        store.emergency_mode=True
        for name,fn in [('environment_close',lambda:engine.close() if engine else None),('graphics_finish',egl.finish),('unhook',init.uninstall)]:
            try:fn()
            except BaseException as e:cleanup.append(record_failure(e,branch=a.branch,stage=name,category='cleanup'))
        n=reconcile(out/'numeric_events.jsonl',numeric_caps(a.branch));i=init.summary();g=graphics_reconcile(out/'graphics_events.jsonl')
        okay=not error and not cleanup and n['counts_complete'] and not n.get('failed') and not n.get('unresolved') and not i['incomplete_event_ids'] and not i['failed_events'] and not g['incomplete'] and not g['failed']
        store.json('RESOURCE_LEDGER.json',dict(status='complete' if okay else 'failed',result=result,primary=error,cleanup=cleanup,
            numeric=n,initialization=i,graphics=g,total_entered=sum_units(n['entered'],i['entered_budget_usage'],g['entered_budget_usage']),
            caps=attempt_caps(a.branch),elapsed_seconds=time.monotonic()-started,writer_reserved_bytes=store.used,
            ledger_scope='private three ledgers; no public UUID concatenation',synthetic=False,
            intervention_evidence=getattr(engine,'intervention_evidence',None)),emergency=True)
    return 0 if okay else 3
if __name__=='__main__':sys.exit(main())
