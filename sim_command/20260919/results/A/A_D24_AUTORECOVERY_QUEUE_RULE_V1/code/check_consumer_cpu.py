"""Actual next-stage validator with synthetic files and fake exit/authority only."""
import ast
import json
import tempfile
from pathlib import Path
import next_stage as ns
from policy import ROOT,POST_SHA,collect_evidence,update_issue
from qio import read,new_json,atomic_json,ref,sha,utc


def run():
    results=[]
    with tempfile.TemporaryDirectory(prefix='corrector_recovery_consumer_') as tmp:
        campaign=Path(tmp)/'campaign';out=campaign/'results/A'
        control=out/'control';old=out/'old';live=out/'live';future=out/'future';issues=campaign/'nodes/A/issues'
        for p in [control,old,live,future,issues]:p.mkdir(parents=True)
        for p in [old,live]:(p/'unit_claims').mkdir()
        source=dict(source_id='s0',task='synthetic-v3',env_seed=1,policy_seed=2)
        job=dict(job_id='DEV_one',cell_id='DEV_one',stage='DEV',H=10,mode='G0-multi',method='Post',loss='L01',fit_seed=9101,ensemble_key='L01_s9101',sources=[source])
        uid='DEV_one__s0'
        new_json(future/'jobs/one.json',job)
        new_json(future/'JOB_INDEX.json',dict(jobs=[ref(future/'jobs/one.json')]))
        new_json(control/'REGISTRY.json',dict(evidence_roots=[str(old),str(live)]))
        for root in [live,future]:
            for name in ['controller.py','numeric_engine.py','resident_worker.py','selection.py']:
                p=root/'code'/name;p.parent.mkdir(exist_ok=True);p.write_text('# synthetic frozen scientific code\n')
        (future/'START_A.sh').write_text('#!/bin/sh\nexit 0\n')
        (live/'old_control.py').write_text('old = 1\n');(future/'new_control.py').write_text('new = 2\n')
        new_json(future/'CHECK.json',dict(status='PASS',synthetic=True))
        new_json(future/'BUDGET.json',dict(prior_A_attempts=14896,new_first=1,new_attempt_cap=1,cumulative_cap=27000,original_stage_end_unix=3000))
        fix=dict(classification='engineering_diagnosis',fault_signature='serialization',diagnosis='correct explicit field collision',affected_units=[uid],old_code_sha256=sha(live/'old_control.py'),new_code_sha256=sha(future/'new_control.py'),old_code_ref=ref(live/'old_control.py'),new_code_ref=ref(future/'new_control.py'),targeted_CPU_check_passed=True,targeted_CPU_check_ref=ref(future/'CHECK.json'),scientific_configuration_changed=False)
        candidate=dict(candidate_id='one',owner='A',task_id='A_D24_FULL_Q_AUTORUN_HANDOFF_V2',status='ready',units=[uid],absolute_end_unix=3000,attempt_limit=1,selection_required=False,result_root=str(future),entry=ref(future/'START_A.sh'),job_index=ref(future/'JOB_INDEX.json'),required_refs=[ref(future/'CHECK.json')],budget_envelope=ref(future/'BUDGET.json'),lifecycle='existing_service_single_formal_lock_all8_off',repair=fix)
        path=control/'candidates/one.json';new_json(path,candidate)
        saved={k:getattr(ns,k) for k in ['ROOT','CAMPAIGN','ORIGINAL','LIVE','ISSUES','live_admission','canonical_units','wave_state','selection_ready']}
        try:
            ns.ROOT=control;ns.CAMPAIGN=campaign;ns.ORIGINAL=old;ns.LIVE=live;ns.ISSUES=issues
            ns.live_admission=lambda now:3000
            ns.canonical_units=lambda:{uid:(job,source)}
            ns.wave_state=lambda root:dict(root=str(root),confirmed_formal_exit=True,final={'compute_complete':False})
            ns.selection_ready=lambda:True
            good=ns.validate(path,now=2000);assert good['ready'] and good['units']==1
            results.append('actual_validator_reads_isolated_patch_job_budget_refs_no_launch')
            new_json(issues/'block.json',dict(issue_id='block',owner='A',units=[uid],status='blocked_deferred'))
            assert ns.validate(path,now=2000)['reason']=='unresolved_scientific_issue_even_after_timeout'
            row=read(issues/'block.json');row.update(status='decision_received_pending_safe_boundary',decision=dict(action='resume_with_reference',candidate_ref=ref(path)))
            atomic_json(issues/'block.json',row)
            assert ns.validate(path,now=2000)['ready']
            results.append('actual_validator_timeout_cannot_bypass_issue_exact_decision_restores_boundary')
            envelope=read(future/'BUDGET.json');envelope['prior_A_attempts']=0
            atomic_json(future/'BUDGET.json',envelope);candidate['budget_envelope']=ref(future/'BUDGET.json');atomic_json(path,candidate)
            row['decision']['candidate_ref']=ref(path);atomic_json(issues/'block.json',row)
            try:ns.validate(path,now=2000)
            except ValueError as e:assert 'budget envelope' in str(e)
            else:raise AssertionError('budget reset accepted')
            results.append('actual_validator_rejects_budget_reset')
        finally:
            for key,value in saved.items():setattr(ns,key,value)
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    results.append('final_changed_sources_AST')
    result=dict(utc=utc(),status='PASS',checks=results,synthetic=True,scientific_compute=0,
                actual_launcher_executed=False,actual_process_GPU_probes=False,actual_failure_recovery_tested=False)
    new_json(ROOT/'CPU_CONSUMER_CHECK.json',result)
    return result


if __name__=='__main__':print(json.dumps(run()))
