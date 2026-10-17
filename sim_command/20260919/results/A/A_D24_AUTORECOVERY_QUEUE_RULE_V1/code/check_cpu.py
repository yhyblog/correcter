"""Targeted true-component synthetic checks. No model, GPU or callback probes."""
import ast
import copy
import json
import tempfile
from pathlib import Path
from policy import (ROOT,POST_SHA,partition_units,collect_evidence,repair_gate,new_issue,
                    update_issue,candidate_gate,selected_rule,fault_kind)
from qio import new_json,read,utc


def run():
    checks=[]
    def mark(name):checks.append(dict(name=name,status='PASS',synthetic=True))
    with tempfile.TemporaryDirectory(prefix='corrector_recovery_cpu_') as tmp:
        root=Path(tmp);a=root/'r1';b=root/'r2'
        for runroot in [a,b]:
            (runroot/'unit_claims').mkdir(parents=True)
        rows=[dict(unit_id='a',status='complete',success=True),dict(unit_id='b',status='complete',success=False),dict(unit_id='c',status='technical_failure',success=None)]
        for row in rows:
            new_json(a/'unit_claims'/(row['unit_id']+'.json'),row)
            new_json(a/'runs/job/episodes'/row['unit_id']/'RESULT.json',row)
        # Whole-job RESULT says complete, but d has never entered; c has no
        # lawful terminal. The actual collector ignores that job shortcut.
        new_json(a/'runs/job/RESULT.json',dict(status='complete'))
        evidence=collect_evidence([a,b],['a','b','c','d'])
        assert set(evidence['valid'])=={'a','b'} and evidence['unentered']==['d']
        assert evidence['requires_terminal_log_review']==['c']
        assert evidence['preserved_scientific_failure_count']==1 and evidence['actual_attempts']==3
        mark('actual_files_collector_partial_job_false_terminal_and_log_review')
        try:partition_units(['a'],[rows[0],rows[0]],['a'],[])
        except ValueError:pass
        else:raise AssertionError('duplicate valid terminal accepted')
        mark('duplicate_valid_terminal_rejected')
        directory=root/'issues'
        issue=new_issue('x',task='task',units=['c'],error='semantic gap',attempted_fixes=[],decision_needed='decide source semantics',blocked_tasks=['task'],runnable_tasks=['independent'],evidence=['saved'],now=100,directory=directory)
        same=new_issue('x',task='task',units=['c'],error='redelivery',attempted_fixes=[],decision_needed='same',blocked_tasks=[],runnable_tasks=[],evidence=[],now=500,directory=directory)
        assert same==issue and issue['analysis_response_due_at']=='1970-01-01T00:31:40+00:00'
        ack=dict(issue_id='x',status='ACK',action='resume_with_reference',rationale='received')
        assert update_issue(issue,ack,1899)['status']=='waiting_analysis'
        deferred=update_issue(issue,ack,1900)
        assert deferred['status']=='blocked_deferred' and deferred['reported_at']==issue['reported_at']
        mark('actual_persistent_issue_1800s_ACK_redelivery_do_not_reset')
        decision=dict(issue_id='x',status='actionable',action='resume_with_reference',rationale='fixed metadata',candidate_ref={'path':'candidate','sha256':'abc'})
        resolved=update_issue(deferred,decision,2000)
        assert resolved['status']=='decision_received_pending_safe_boundary'
        assert update_issue(resolved,decision,2015)==resolved
        mark('late_actionable_decision_safe_boundary_idempotent')
    fix=dict(classification='engineering_diagnosis',fault_signature='f',diagnosis='duplicate serialization key',affected_units=['c'],old_code_sha256='old',new_code_sha256='new',targeted_CPU_check_passed=True,scientific_configuration_changed=False)
    assert repair_gate(fix,[])[0]
    assert not repair_gate(fix,[fix])[0]
    fix2=dict(fix,new_code_sha256='new2');assert repair_gate(fix2,[fix])[0]
    assert not repair_gate(dict(fix,new_code_sha256='new3'),[fix,fix2])[0]
    assert not repair_gate(dict(fix,new_code_sha256='old'),[])[0]
    assert not repair_gate(dict(fix,scientific_configuration_changed=True),[])[0]
    mark('two_documented_distinct_repairs_no_blind_retry_or_scientific_change')
    candidate=dict(candidate_id='x',task_id='A_D24_FULL_Q_AUTORUN_HANDOFF_V2',owner='A',status='ready',units=['c'],attempt_limit=1,absolute_end_unix=3000,selection_required=True,repair=fix)
    args=dict(now=2000,alive_formal=False,exit_verified=True,selection=True,valid_units=['a','b'],allowed_units=['a','b','c','d'],attempts_remaining=1,prior_repairs=[])
    assert candidate_gate(candidate,**args)[0]
    for delta,why in [({'alive_formal':True},'healthy wave'),({'exit_verified':False},'unconfirmed descendants'),({'selection':False},'Post incomplete'),({'attempts_remaining':0},'cap'),({'now':3000},'deadline')]:
        assert not candidate_gate(candidate,**dict(args,**delta))[0],why
    for delta in [dict(owner='B'),dict(units=['a']),dict(units=['new']),dict(units=['c','c']),dict(cancelled=True)]:
        assert not candidate_gate(dict(candidate,**delta),**args)[0]
    mark('true_candidate_gate_exit_selection_ownership_unit_budget_deadline')
    # An unrelated outstanding issue is not an execution prerequisite. The
    # ready independent task passes immediately, before that issue's timeout.
    independent=dict(candidate,units=['d'],repair=None,unentered_only=True,selection_required=False)
    assert candidate_gate(independent,**dict(args,now=101,selection=False))[0]
    mark('independent_ready_task_does_not_wait_1800s')
    selection=dict(status='selected_locked',Post_only=True,Post_development_valid=1200,Velocity_selection_weight=0,fixed_fit_seed=9101,Post_selection_override_sha256=POST_SHA,test_used=False)
    assert selected_rule(selection,'same','same')
    for delta in [dict(Post_only=False),dict(Post_development_valid=1199),dict(Velocity_selection_weight=1),dict(fixed_fit_seed=9102),dict(test_used=True)]:
        assert not selected_rule(dict(selection,**delta),'same','same')
    assert not selected_rule(selection,'x','y')
    mark('complete_Post_only_fixed_fit_immutable_selection')
    assert fault_kind('observation semantic gap')=='scientific_decision'
    assert fault_kind('CUDA out of memory')=='resource_engineering'
    assert fault_kind('TypeError duplicate keys')=='engineering_diagnosis'
    mark('fault_classification_does_not_treat_scientific_change_as_repair')
    for p in (ROOT/'code').glob('*.py'):
        tree=ast.parse(p.read_text(),filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                assert all(x.name.split('.')[0] not in ['torch','mujoco','pynvml','ctypes','OpenGL'] for x in node.names)
            elif isinstance(node,ast.ImportFrom):
                assert (node.module or '').split('.')[0] not in ['torch','mujoco','pynvml','ctypes','OpenGL']
    src=(ROOT/'code/next_stage.py').read_text()
    assert 'formal.lock' in src and "['bash',checked['entry']]" in src
    assert 'live_priority_unchanged=True' in (ROOT/'code/supervisor.py').read_text()
    mark('changed_python_AST_CPU_only_no_live_priority_mutation')
    return dict(utc=utc(),status='PASS',checks=checks,check_count=len(checks),scientific_compute=0,
                actual_failure_recovery_tested=False,callback_tested=False,real_locks_processes_GPU_used=False)


if __name__=='__main__':
    result=run();new_json(ROOT/'CPU_CHECK.json',result);print(json.dumps(result))
