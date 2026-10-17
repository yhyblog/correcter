"""CPU fixtures for no-replay, timer and real legacy-consumer compatibility."""
import ast,copy,hashlib,json,tempfile,time
from pathlib import Path
from fractions import Fraction
import c_recovery_policy as policy
import selection_bridge as bridge
from ops_io import read,new_json,atomic_json,ref,sha,utc
from post_choice_validator import validate_selection
from legacy_selection_snapshot import validate_selection as legacy

def reject(fn):
    try:fn()
    except (ValueError,KeyError):return
    raise AssertionError('invalid fixture accepted')

def main():
    work=Path(__file__).resolve().parent
    for p in work.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    for root in [policy.X,policy.P]:
        for name in ['manager.py','operational_hook.py','common.py' if root==policy.X else 'admission.py']:
            ast.parse((root/'code'/name).read_text(),filename=name)
    row=dict(issue_id='CPU_fixture',status='reported',reported_at_unix=1000,analysis_response_due_unix=2800,attempted_repairs=[])
    assert policy.advance_issue(row,dict(status='ACK'),2799)==row
    late=policy.advance_issue(row,dict(status='ACK'),2801)
    assert late['status']=='blocked_deferred' and late['analysis_response_due_unix']==2800 and late['reported_at_unix']==1000
    assert policy.advance_issue(row,dict(issue_id='another',status='actionable',action='apply_documented_fix',evidence=['fixture']),2801)['status']=='blocked_deferred'
    decision=dict(issue_id='CPU_fixture',status='actionable',action='apply_documented_fix',evidence=['fixture'])
    assert policy.advance_issue(row,decision,2000)['status']=='actionable_decision_available'
    fix=dict(change='CPU fixture of a specific engineering correction',evidence=[dict(path='/tmp/fixture',sha256='fixture')],science_changed=False)
    done={'good':dict(status='complete',success=True),'scientific_failure':dict(status='complete',success=False),'technical':dict(status='technical_failure',success=None)}
    for u in ['good','scientific_failure']:reject(lambda u=u:policy.validate_repair(row,fix,[u],done,10,family_exited=True))
    reject(lambda:policy.validate_repair(row,fix,['technical'],done,10,family_exited=False))
    reject(lambda:policy.validate_repair(row,fix,['technical','technical'],done,10,family_exited=True))
    reject(lambda:policy.validate_repair(row,fix,['technical'],done,0,family_exited=True))
    reject(lambda:policy.validate_repair(dict(row,attempted_repairs=[{},{}]),fix,['technical'],done,10,family_exited=True))
    reject(lambda:policy.validate_repair(row,fix,['technical'],done,10,family_exited=True,attempts_by_unit={'technical':2}))
    fingerprint=policy.validate_repair(row,fix,['technical'],done,10,family_exited=True)
    reject(lambda:policy.validate_repair(dict(row,attempted_repairs=[dict(fix_fingerprint=fingerprint)]),fix,['technical'],done,10,family_exited=True))
    tasks=sorted({s['task'] for s in read(policy.P/'SOURCE_INDEX.json')['source_sets']['DEV']});losses=['L00','L10','L01','L11']
    selection=dict(task_id='A_D24_FULL_Q_LOSS_SELECTION_V1',status='selected_locked',test_used=False,no_test_based_change=True,fixed_fit_seed=9101,chosen_loss='L10',selection_criterion='Post_only_complete_development',development_valid=2400,development_technical_missing=0,scores=[],loss_scores={})
    for loss in losses:
        total=Fraction(0)
        for seed in [9101,9102,9103]:
            for method in ['Post','Velocity']:
                for task in tasks:
                    n=18 if method=='Post' and loss=='L10' else 20 if method=='Velocity' and loss=='L00' else 10
                    selection['scores'].append(dict(loss=loss,fit_seed=seed,method=method,task=task,valid=20,successes=n));total+=Fraction(n,600)
        selection['loss_scores'][loss]=dict(valid=600,score_numerator=total.numerator,score_denominator=total.denominator)
    assert validate_selection(selection)=='L10';reject(lambda:legacy(selection))
    with tempfile.TemporaryDirectory(prefix='C_recovery_CPU_fixture_') as tmp:
        t=Path(tmp);x=t/'X';a=t/'A';control=t/'control';p=t/'Pi'
        for d in [x,a,control,p]:d.mkdir()
        new_json(a/'SELECTION.json',selection);new_json(a/'SELECTION_LOCK.json',dict(immutable=True,selection=ref(a/'SELECTION.json')))
        member_hashes={str(n):f'fixture_{n}' for n in [1041,1042,1043,1044]};assets=x/'ensembles/L10_s9101'
        new_json(assets/'ranking.json',dict(model_hashes=member_hashes))
        ensemble=dict(loss='L10',fit_seed=9101,assets=str(assets),ranking=ref(assets/'ranking.json'),members=[dict(member=int(n),sha256=h) for n,h in member_hashes.items()])
        new_json(x/'CANDIDATES_READY.json',dict(status='CANDIDATES_READY',fits=16,actual_optimizer_updates=64000,ensembles={'L10':ensemble},CPU_fixture_only=True))
        new_json(x/'PROCESS.json',dict(pid=0,CPU_fixture_only=True));new_json(x/'HEARTBEAT.json',dict(status='selection_dependency'));new_json(x/'CLAIM.json',dict(CPU_fixture_only=True));new_json(x/'STAGE_DEADLINE.json',dict(deadline_unix=time.time()+60))
        saved=(bridge.X,bridge.A,bridge.ROOT,bridge.authority,bridge.live_identity)
        try:
            bridge.X=x;bridge.A=a;bridge.ROOT=control;bridge.authority=lambda:None;bridge.live_identity=lambda _:True
            result=bridge.maybe_adapt_native();assert result['metadata_adaptations']==1
            # Execute the exact still-running consumer's early-existing-record path
            # against isolated fixture files. No live process or claim is touched.
            original=(policy.X/'code/selection.py').read_text();tree=ast.parse(original)
            funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['try_consume','consumed_selection']]
            context=dict(ROOT=x,SELECTION=a/'SELECTION.json',read=read,sha=sha,Path=Path)
            exec(compile(ast.Module(body=funcs,type_ignores=[]),'CPU_legacy_consumer_fixture','exec'),context)
            assert context['try_consume']()['chosen_loss']=='L10'
            assert bridge.maybe_adapt_native()['metadata_adaptations']==0
            before=sha(x/'SELECTION_CONSUMED.json');assert bridge.create_record(x/'SELECTION_CONSUMED.json',dict(wrong=True)) is False;assert sha(x/'SELECTION_CONSUMED.json')==before
        finally:bridge.X,bridge.A,bridge.ROOT,bridge.authority,bridge.live_identity=saved
        # A partial five-source job preserves both booleans and its unentered tail.
        sources=[dict(source_id=f's{i}',task='fixture',env_seed=i,policy_seed=i) for i in range(5)];cell='MAIN_SELECTED_Post_H40';jid='fixture_job'
        new_json(p/'jobs'/f'{jid}.json',dict(job_id=jid,cell_id=cell,H=40,method='Post',sources=sources));new_json(p/'JOB_INDEX.json',dict(jobs=[dict(path=str(p/'jobs'/f'{jid}.json'))]))
        for i in range(3):new_json(p/'unit_claims'/f'{i}.json',dict(unit_id=cell+'__'+sources[i]['source_id']))
        for i,success in [(0,True),(1,False)]:
            r=dict(sources[i],unit_id=cell+'__'+sources[i]['source_id'],status='complete',success=success,terminal=True)
            new_json(p/'runs'/jid/'episodes'/sources[i]['source_id']/'RESULT.json',r)
        new_json(p/'runs'/jid/'RESULT.json',dict(episodes=[]))
        savedP=policy.P;policy.P=p
        try:
            units=policy.unfinished_units(p);assert len(units['remaining'])==3
            assert [r['status'] for r in units['remaining']]==['unknown_entered','not_started','not_started']
        finally:policy.P=savedP
    report=dict(status='passed',utc=utc(),scope='isolated CPU fixtures and syntax only',checks=['complete Post choice differs from legacy joint choice','compatibility publication consumed by exact legacy early-record branch','atomic no-overwrite and repeated-call idempotence','30min deadline is not reset by ACK','actionable decision must match issue','valid success=false preserved','unknown distinct from scientific failure','partial job tail retained','unique unit and unchanged budget gates','same-fault max2 and failed-source max1 corrected retry','own-family-exit gate','documented-change required'],GPU_calls=0,new_scientific_claims=0,real_failure_recovery_tested=False,live_waiter_restarted=False)
    atomic_json(policy.ROOT/'CPU_CHECK.json',report);print(report)

if __name__=='__main__':main()
