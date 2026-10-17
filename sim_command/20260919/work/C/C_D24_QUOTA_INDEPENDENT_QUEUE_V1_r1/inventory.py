"""Exact source inventory across original and explicitly linked continuations."""
import hashlib
from queue_common import *

def inventory(root):
    root=Path(root); expected={}; claims={}; states={}; attempts=[]; log_derived=[]
    if root==X:
        for method in ['Post','Velocity']:
            for s in read(root/'config/TEST_SOURCES.json')['sources']:
                expected[method+'/'+s['source_id']]=dict(unit_id=method+'/'+s['source_id'],source=s,method=method,H=30)
    elif root==P:
        for jr in snapshot(root/'JOB_INDEX.json').get('jobs',[]):
            j=read(verify(jr,base=C))
            for s in j['sources']:
                uid=j['cell_id']+'__'+s['source_id']; expected[uid]=dict(unit_id=uid,source=s,job_id=j['job_id'],cell_id=j['cell_id'],H=j['H'],method=j['method'])
    else: raise ValueError('Only current X and pi05 tasks can continue')
    for run in runs(root):
        cp=run/'claims/attempts' if root==X else run/'unit_claims'
        for p in cp.glob('*.json'):
            r=read(p); uid=r.get('identity') if root==X else r.get('unit_id')
            if uid not in expected: raise ValueError('claim outside frozen scope')
            # A first-entry claim is mirrored at the original and run roots. The
            # parent task's attempt ordinal identifies that single admission.
            ordinal=r.get('number') if root==X else r.get('stage_ordinal')
            claims.setdefault(uid,{})[ordinal]=dict(r,claim_path=str(p))
        paths=(run/'evaluation').glob('*/*/RESULT.json') if root==X else (run/'runs').glob('*/episodes/*/RESULT.json')
        for p in paths:
            r=read(p); uid=(p.parents[1].name+'/'+p.parent.name) if root==X else r.get('unit_id')
            if uid not in expected: raise ValueError('result outside frozen scope')
            source=expected[uid]['source']; keys=['source_id','task','policy_seed','reset_seed' if root==X else 'env_seed']
            if any(r.get(k)!=source[k] for k in keys) or r.get('method')!=expected[uid]['method']: raise ValueError('result source/seed mismatch')
            r=dict(r,result_path=str(p),unit_id=uid,run_root=str(run)); attempts.append(r)
            if policy.legal_terminal(states.get(uid,{})):
                raise ValueError('duplicate legal scientific outcome; no silent overwrite')
            states[uid]=r
        if root==P:
            for p in (run/'runs').glob('*/RESULT.json'):
                for r in read(p).get('episodes',[]):
                    uid=r.get('unit_id')
                    if uid not in expected or uid in states or not policy.legal_terminal(r) or r.get('terminal') is not True: continue
                    s=expected[uid]['source']
                    if any(r.get(k)!=s[k] for k in ['source_id','task','env_seed','policy_seed']): raise ValueError('embedded source identity')
                    states[uid]=dict(r,result_path=str(p),unit_id=uid,run_root=str(run),log_derived=True)
                    attempts.append(states[uid]);log_derived.append(str(p))
    remaining=[]
    for uid,item in expected.items():
        r=states.get(uid,{})
        if policy.legal_terminal(r) or r.get('status') in ['user_cancelled','cancelled']: continue
        remaining.append(dict(item,prior_attempts=len(claims.get(uid,{})),status=r.get('status','unknown_entered' if uid in claims else 'not_started')))
    return dict(expected=expected,claims=claims,states=states,attempts=attempts,remaining=remaining,log_derived=log_derived)

def allowed_units(inv,service_fault,io_fixed=False):
    """Unknown source outcomes are retained. Only a narrow encoded fault retries."""
    allowed=[];deferred=[]
    for row in inv['remaining']:
        raw=inv['states'].get(row['unit_id'],{}); text=str(raw.get('error',''))+str(raw.get('traceback',''))+str(raw.get('technical_failure',''))
        io_case=any(s in text for s in ['[Errno 5]','[Errno 116]','[Errno 107]']) and 'qio.py' in text and any(s in text for s in ['new_json','atomic_json'])
        if row['prior_attempts']==0 and service_fault:
            allowed.append(dict(row,correction='filtered_partial_job_continuation'))
        elif row['prior_attempts']==1 and io_case and io_fixed:
            allowed.append(dict(row,correction='atomic_exclusive_JSON_commit_with_bounded_transient_IO_retry'))
        else: deferred.append(dict(row,reason='unknown/unencoded fault or corrected retry exhausted'))
    return allowed,deferred

