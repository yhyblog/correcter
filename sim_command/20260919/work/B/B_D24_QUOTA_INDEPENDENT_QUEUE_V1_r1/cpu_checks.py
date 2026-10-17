"""Focused synthetic CPU checks. No subprocess launch, model, or GPU access."""
import ast
import tempfile
from pathlib import Path
from unittest.mock import patch
import quota_runtime as q
import supervisor as s

def run():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='B_quota_CPU_') as temp:
        tmp=Path(temp);root=tmp/'native';out=tmp/'control'
        cases=[('complete',False),('complete',True),('technical_failure',None)]
        for i,(status,success) in enumerate(cases):
            sid='synthetic_'+str(i)
            q.new_json(root/'evaluation/Post'/sid/'RESULT.json',dict(method='Post',source_id=sid,status=status,success=success,synthetic=True))
            q.new_json(root/'claims/attempts'/(sid+'.json'),dict(identity='Post/'+sid))
        with patch.object(q,'Q',out),patch.object(q,'BASES',{'native':root}):
            valid,latest,claimed,history=q.outcomes('native')
            assert len(valid)==2 and valid['Post/synthetic_0'][0]['success'] is False
            assert 'Post/synthetic_2' not in valid and latest['Post/synthetic_2'][0]['success'] is None
            assert len(claimed)==3
        checks.append('dedup preserves valid scientific failure and success; technical null remains unresolved')
        assert q.choose_recipe('CUDA out of memory',24,False,True)['target_workers']==16
        assert q.choose_recipe('CUDA out of memory',16,False,True)['target_workers']==8
        assert q.choose_recipe('CUDA out of memory',8,False,True) is None
        assert q.choose_recipe('unclassified protocol fault',24,False,True) is None
        assert q.choose_recipe('unclassified worker fault',24,True,True)['never_entered_only']
        checks.append('OOM steps 24 to 16 to 8; unknown initial fault does not blindly restart')
        with patch.object(q.subprocess,'run',side_effect=TimeoutError('synthetic transport timeout')):
            record=q.register_manifest(tmp/'registration.json')
            assert record['registered'] is False and record['science_blocks'] is False
        checks.append('notification timeout returns durable failure without throwing or launching science')
        issue=tmp/'nodes/B/issues/case.json'
        # Timers inspect B_recovery_ names, and retain the original first-report deadline.
        issue=issue.with_name('B_recovery_synthetic.json')
        q.new_json(issue,dict(status='reported',reported_at_unix=1,analysis_response_due_unix=1801,response_path=str(tmp/'no_decision.json')))
        with patch.object(q,'C',tmp):s.timers()
        row=q.read(issue);assert row['status']=='blocked_deferred' and row['analysis_response_due_unix']==1801
        checks.append('1800-second issue timeout defers without resetting the timer')
        # A healthy original parent has launch rights even when no unit was claimed yet.
        with patch.object(q,'roots',return_value=[root]),patch.object(q,'reconcile_dead'),patch.object(q,'alive',return_value=False),patch.object(s,'parent_owns',return_value=True),patch.object(q,'launch',side_effect=AssertionError('duplicate launch')):
            result=s.schedule('native');assert result['status']=='existing_unique_parent_owns_stage'
        checks.append('healthy unique parent prevents a competing launch')
    for path in q.W.glob('*.py'):ast.parse(path.read_text())
    native=q.snapshot(q.F/'SELECTION_LOCK.json')
    actual=q.gates.selection()
    assert native['chosen_loss']==actual['chosen_loss']=='L01' and native['fit_seed']==9101
    transfer=q.gates.transfer();assert transfer['nodes']['B']['task_id']==q.P.name
    checks.append('actual Post-only L01/fit9101 accepted by original native queue; exact B transfer consumed in CPU validation')
    report=dict(status='PASS',utc=q.utc(),checks=checks,synthetic_tests=True,scientific_model_calls=0,GPU_probes=0,fault_recovery_in_production_claimed=False)
    q.atomic_json(q.Q/'CPU_CHECKS.json',report)
    print(__import__('json').dumps(report,ensure_ascii=False))

if __name__=='__main__':run()
