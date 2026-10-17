"""Release-only branch entry. This file is AST-checked, never run in CPU prep."""
import argparse,json,os,sys,time
from pathlib import Path
from core.contracts import CAMPAIGN,PACKAGE,RELEASE,ContractError,Meter,read,write_new,sha,reconcile,load_authorization,gate
from core.identity import verify_device
from core.wave_timing import held_reservation_fds
from core.failure_evidence import save_failure,branch_stage
from budget import numeric_caps,branch_caps,sum_units,validate_dynamic_counts
from native.graphics_contract import CAPS,reconcile as graphics_reconcile
from native.initialization import EXPECTED_CAPS,InitializationAudit
from native.native_egl import NativeEGL

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);parser.add_argument('--launch-directory',required=True)
    parser.add_argument('--branch',required=True,choices=['Post','Velocity']);a=parser.parse_args()
    r,p=load_authorization(a.release,full=True)
    if not held_reservation_fds():raise ContractError('Missing inherited whole-host occupancy reservation')
    claim=read(CAMPAIGN/'results/A/P10_CAUSAL_C10_V2_release_claims'/(RELEASE+'.json'))
    if claim['release_sha256']!=r['_sha256'] or claim['run_id']!=r['run_id']:raise ContractError('Matching exclusive claim missing')
    parent=Path(a.launch_directory).resolve()
    if parent!=CAMPAIGN/'results/A/P10_CAUSAL_C10_V2_launcher_runs'/r['run_id']:raise ContractError('Output identity mismatch')
    out=parent/a.branch;out.mkdir(exist_ok=False)
    meter=Meter(out/'numeric_events.jsonl',numeric_caps(a.branch),lambda:gate(a.release,r['_sha256']))
    init=InitializationAudit(out/'initialization_events.jsonl',EXPECTED_CAPS,lambda:gate(a.release,r['_sha256']))
    cfg=read(p['config']['path']);egl=NativeEGL(cfg['native'],out,lambda:gate(a.release,r['_sha256']))
    engine=None;failure=None;result=None;started=time.monotonic();cleanup_errors=[];phase='branch_attempt'
    try:
        meter.call('independent_branch_attempt',lambda:None,{'simulator_attempts':1})
        phase='NVML_identity'
        rows=meter.call('reserved_NVML_identity',lambda:verify_device({**r,**cfg['device']},cfg),{'native_nvml_identity_queries':1})
        write_new(out/'nvml_identity.json',dict(rows=rows,target=cfg['device']))
        phase='EGL_prepare';egl.prepare()
        phase='runtime_import'
        sys.path.insert(0,str(PACKAGE/'code/vendor_vla/src'))
        from runtime_engine import Engine
        from causal_contract import run_branch
        phase='model_setup';engine=Engine(cfg,out,meter,egl,init,a.branch)
        phase='controller'
        result=run_branch(engine,a.branch,scheduled=cfg['control']['scheduled_engineering_intervention'])
    except BaseException as error:
        failure=save_failure(out/'failure.json',error,branch=a.branch,stage=branch_stage(phase,engine),category='primary')
    finally:
        for name,fn in [('environment_close',lambda:engine.close() if engine else None),('graphics_finish',egl.finish),('initialization_unhook',init.uninstall)]:
            try:fn()
            except BaseException as error:
                cleanup_errors.append(save_failure(out/('cleanup_failure__'+name+'.json'),error,
                    branch=a.branch,stage=branch_stage('cleanup',engine),category='cleanup',operation=name))
        n=reconcile(out/'numeric_events.jsonl',numeric_caps(a.branch));i=init.summary();g=graphics_reconcile(out/'graphics_events.jsonl')
        total=sum_units(n['entered'],i['entered_budget_usage'],g['entered_budget_usage'])
        complete=not failure and not cleanup_errors and not n['unresolved'] and not n['failed'] and not n['corrupt_records'] and not i['incomplete_event_ids'] and not i['failed_events'] and not g['incomplete'] and not g['failed']
        if complete:
            try:validate_dynamic_counts(total,a.branch,result['controls'],result['restoration_coverage'])
            except Exception as error:
                failure=save_failure(out/'failure.json',error,branch=a.branch,
                    stage=branch_stage('dynamic_count_validation',engine),category='primary');complete=False
        write_new(out/'RESOURCE_LEDGER.json',dict(status='complete' if complete else 'failed',failure=failure,cleanup_errors=cleanup_errors,
            numeric=n,initialization=i,graphics=g,total_entered=total,counts_complete=n['counts_complete'],elapsed_seconds=time.monotonic()-started,
            budget=branch_caps(a.branch),release_consumed=True,remaining_caps_reusable=False,automatic_retry=False,
            ledger_scope='private numeric integers / initialization UUID / graphics UUID; never concatenate into public v1',
            cleanup_attempted=True,source=cfg['source']))
        write_new(out/'ARTIFACT_MANIFEST.json',dict(files=[dict(path=str(x),size_bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(out.iterdir()) if x.is_file()]))
    return 0 if complete else 3
if __name__=='__main__':sys.exit(main())
