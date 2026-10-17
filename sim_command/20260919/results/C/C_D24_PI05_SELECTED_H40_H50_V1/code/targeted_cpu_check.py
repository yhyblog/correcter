"""Bounded CPU checks for the new selection, ownership and ordering gates."""
import ast,copy
from pathlib import Path
import paths
from paths import ROOT,ORIGINAL,AUTH_SHA,TASK
from qio import read,sha,atomic_json,utc,ref
from selection import validate_selection,LOSSES,POST_RULE_SHA
from transfer import validate_partition

def rejects(fn):
    try:fn()
    except (ValueError,KeyError):return
    raise AssertionError('invalid fixture was admitted')

def main():
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    refs=read(ROOT/'PLANNED_JOB_INDEX.json')['jobs'];planned={r['job_id']:read(r['path']) for r in refs}
    assert len(refs)==len(planned)==400
    units={j['cell_id']+'__'+s['source_id'] for j in planned.values() for s in j['sources']}
    assert len(units)==2000
    for r in refs:
        assert sha(r['path'])==r['sha256']==r['original']['sha256']
    source_set={s['source_id']:s for s in read(ROOT/'SOURCE_INDEX.json')['source_sets']['MAIN']}
    assert len(source_set)==500
    cfg=read(ROOT/'config/CONFIG.json')
    for j in planned.values():
        assert j['configuration_sha256']==cfg['original_A_configuration']['sha256']
        assert j['H'] in [40,50] and j['method'] in ['Post','Velocity'] and j['mode']=='G0-multi'
        assert all(s==source_set[s['source_id']] for s in j['sources'])
    base=read(ROOT/'config/BASE.json');a_base=read(ORIGINAL/'config/BASE.json')
    for k in ['checkpoint','model_sha256','projection','runtime_packages','tokenizer_name','tokenizer_revision','action_signature','feature_signature','state_contract_sha256']:
        assert base[k]==a_base[k],k
    assert len({base['device_list'][slot%8]['gpu_uuid'] for slot in range(24)})==8
    assert all(sum(slot%8==gpu for slot in range(24))==3 for gpu in range(8))
    tasks=sorted({s['task'] for s in read(ROOT/'SOURCE_INDEX.json')['source_sets']['DEV']})
    row=dict(task_id='A_D24_FULL_Q_LOSS_SELECTION_V1',status='selected_locked',test_used=False,no_test_based_change=True,fixed_fit_seed=9101,chosen_loss='L10',selection_criterion='Post_only_complete_development',scores=[])
    for loss in LOSSES:
        for seed in [9101,9102,9103]:
            for method in ['Post','Velocity']:
                for t in tasks:
                    n=18 if method=='Post' and loss=='L10' else 20 if method=='Velocity' and loss=='L00' else 10
                    row['scores'].append(dict(loss=loss,fit_seed=seed,method=method,task=t,valid=20,successes=n))
    assert validate_selection(row)=='L10' # Joint scoring would choose L00.
    bad=copy.deepcopy(row);bad['test_used']=True;rejects(lambda:validate_selection(bad))
    bad=copy.deepcopy(row);bad['chosen_loss']='L00';rejects(lambda:validate_selection(bad))
    bad=copy.deepcopy(row);bad['selection_criterion']='joint_Post_Velocity';rejects(lambda:validate_selection(bad))
    bad=copy.deepcopy(row);bad['scores'].append(copy.deepcopy(bad['scores'][0]));rejects(lambda:validate_selection(bad))
    bad=copy.deepcopy(row);bad['scores']=[r for r in bad['scores'] if r['method']=='Post'];assert validate_selection(bad)=='L10'
    chosen={j['job_id']:j for j in [next(j for j in planned.values() if j['H']==h and j['method']=='Post') for h in [40,50]]}
    selected=dict(A_selection=dict(sha256='selection_fixture'),A_lock=dict(sha256='lock_fixture'),chosen_loss='L10',ensemble=dict(key='L10_s9101'))
    grants=[];grant_units=[]
    for j in chosen.values():
        ids=[j['cell_id']+'__'+s['source_id'] for s in j['sources']]
        grants.append(dict(job_id=j['job_id'],owner='C',cell_id=j['cell_id'],method=j['method'],H=j['H'],mode=j['mode'],sources=j['sources'],source_ids=[s['source_id'] for s in j['sources']],unit_ids=ids))
        for uid,s in zip(ids,j['sources']):grant_units.append(dict(unit_id=uid,job_id=j['job_id'],cell_id=j['cell_id'],source_id=s['source_id'],source=s,method=j['method'],H=j['H'],mode=j['mode'],fit_seed=9101))
    transfer=dict(status='TRANSFER_READY',authorization_sha256=AUTH_SHA,old_manager_cannot_dispatch=True,A_new_manager_contains_remote_jobs=False,selection=selected['A_selection'],selection_lock=selected['A_lock'],chosen_loss='L10',fixed_fit_seed=9101,ensemble=selected['ensemble'],owners=dict(C=grants),nodes=dict(C=dict(task_id=TASK,Hs=[40,50],attempt_cap=2200,jobs=grants,units=grant_units,first_count=10)),excluded_A_units=[])
    assert len(validate_partition(transfer,chosen,selected)[1])==10
    bad=copy.deepcopy(transfer);bad['nodes']['B']=dict(units=[bad['nodes']['C']['units'][0]]);rejects(lambda:validate_partition(bad,chosen,selected))
    bad=copy.deepcopy(transfer);bad['nodes']['C']['jobs'][0]['sources'][0]['policy_seed']+=1;rejects(lambda:validate_partition(bad,chosen,selected))
    partial=copy.deepcopy(transfer);g=partial['nodes']['C']['jobs'][0];s=g['sources'].pop();uid=g['unit_ids'].pop();g['source_ids'].pop()
    partial['excluded_A_units'].append(dict(owner='C',unit_id=uid,job_id=g['job_id'],source=s));partial['nodes']['C']['units']=[u for u in partial['nodes']['C']['units'] if u['unit_id']!=uid];partial['nodes']['C']['first_count']=9
    assert len(validate_partition(partial,chosen,selected)[1])==9
    bad=copy.deepcopy(partial);bad['excluded_A_units']=[];rejects(lambda:validate_partition(bad,chosen,selected))
    from manager import pending
    rows=[(j['H'],j['chunk'],j['task_order'],j['method'],j['job_id'],Path(r['path']),j) for r in refs for j in [planned[r['job_id']]]]
    assert len(pending(rows,40))==200 and all(r[0]==40 for r in pending(rows,40))
    assert len(pending(rows,50))==200
    for name in ['controller.py','numeric_engine.py','resident_egl.py']:assert sha(ROOT/'code'/name)==sha(ORIGINAL/'code'/name)
    result=dict(status='passed',utc=utc(),scope='CPU synthetic fixtures only; no GPU/model/environment calls and no scientific claims',planned_jobs=400,planned_original_units=2000,original_sources=500,checks=['AST','byte-identical frozen algorithm','C base scientific metadata matches A','24 UUID slots map3perGPU','Post-only selection disagrees with joint fixture correctly','reject joint/test/incomplete/duplicate choices','exact transfer and A-retained partition','reject overlap/seed drift/missing exclusions','H40/H50 dispatch filtering'],scientific_compute=0,real_failure_recovery_tested=False)
    atomic_json(ROOT/'CPU_CHECK.json',result);print(result)

if __name__=='__main__':main()
