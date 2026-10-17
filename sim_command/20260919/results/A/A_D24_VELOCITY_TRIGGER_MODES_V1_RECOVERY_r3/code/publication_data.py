"""CPU-only merging of immutable attempts and derived publication fields."""
import math
from pathlib import Path
from paths import EVIDENCE_ROOTS
from qio import read


class EvidenceConflict(ValueError):
    pass


def identity(row):
    return row['mode'],row['H'],row.get('source_id',row.get('source',{}).get('source_id'))


def merge_event(ep,event):
    owned={k:ep[k] for k in ('source_id','task','H','mode')}
    owned.update(branch='Velocity',planned_random_cut=ep.get('planned_random_cut'))
    result=dict(owned)
    for k,v in event.items():
        if k in owned:
            if v!=owned[k]:raise EvidenceConflict('event identity conflict: '+k)
        elif not isinstance(v,(list,dict)):
            result[k]=v
    return result


def finite_values(value):
    reasons={}
    def visit(x,path):
        if isinstance(x,float) and not math.isfinite(x):
            reasons[path]='non-finite descriptive statistic; preserved as null, not zero'
            return None
        if isinstance(x,dict):return {k:visit(v,path+'.'+str(k)) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [visit(v,path+f'[{i}]') for i,v in enumerate(x)]
        return x
    clean=visit(value,'$')
    if reasons and isinstance(clean,dict):clean['non_finite_null_reasons']=reasons
    return clean


def choose_unique(attempts):
    groups={}
    for x in attempts:groups.setdefault(identity(x),[]).append(x)
    selected=[]
    for key,rows in groups.items():
        rows.sort(key=lambda x:x['attempt_index'])
        if len(rows)>2 or len({x['attempt_index'] for x in rows})!=len(rows):
            raise EvidenceConflict('duplicate attempt or retry cap: '+str(key))
        good=[x for x in rows if x['status']=='complete']
        if len(good)>1 or (good and good[0] is not rows[-1]):
            raise EvidenceConflict('completed unit replay: '+str(key))
        selected.append(good[0] if good else rows[-1])
    return selected


def load_evidence(only=None,*,roots=None):
    """Read a monotonic partial snapshot without treating later commits as orphans.

    Each discovered immutable result is joined to its exact immutable claim on
    disk, never to membership in an earlier directory listing. Later claim
    discovery includes in-flight work; later results wait for the next snapshot.
    True missing claims, mismatched identities, duplicate physical attempts and
    completed-unit replays still fail with the offending key and file paths.
    """
    jobs=[];attempts=[];claims=[];claimed={}
    def include_claim(root,p):
        try:
            c=read(p)
        except FileNotFoundError as error:
            raise EvidenceConflict('missing immutable claim: '+str(p)) from error
        key=(*identity(c),c['attempt'])
        expected=f"{c['mode']}_H{c['H']:02d}_{c['source']['source_id']}"
        if c['unit_id']!=expected or p!=root/'unit_claims'/(expected+'.json'):
            raise EvidenceConflict('claim path/identity conflict: '+str((key,str(p))))
        if key in claimed:
            prior=claimed[key]
            if prior['claim_path']!=str(p) or {k:v for k,v in prior.items() if k!='claim_path'}!=c:
                raise EvidenceConflict('duplicate or changed physical claim: '+str((key,prior['claim_path'],str(p))))
            return prior
        row=dict(c,claim_path=str(p));claimed[key]=row;claims.append(row)
        return row
    for root in EVIDENCE_ROOTS if roots is None else roots:
        root=Path(root)
        result_paths=sorted((root/'runs').glob('*/episodes/*/RESULT.json'))
        for p in sorted((root/'runs').glob('*/RESULT.json')):
            j=read(p)
            if not only or f"Velocity_{j['mode']}_H{j['H']}"==only:
                jobs.append(dict(j,run_root=str(root),result_path=str(p)))
        for p in result_paths:
            x=read(p)
            if only and f"Velocity_{x['mode']}_H{x['H']}"!=only:continue
            attempt=x.get('attempt_index',0)
            key=(*identity(x),attempt)
            cp=root/'unit_claims'/f"{x['mode']}_H{x['H']:02d}_{x['source_id']}.json"
            c=include_claim(root,cp)
            if key!=(*identity(c),c['attempt']):
                raise EvidenceConflict('result/claim attempt conflict: '+str((key,str(p),str(cp))))
            for name in ('source_id','task','ordinal','env_seed','policy_seed'):
                if name not in x or name not in c['source'] or x[name]!=c['source'][name]:
                    raise EvidenceConflict('result/claim '+name+' conflict: '+str((key,str(p),str(cp))))
            attempts.append(dict(x,attempt_index=attempt,result_path=str(p),run_root=str(root),job_id=p.parents[2].name))
        for p in sorted((root/'unit_claims').glob('*.json')):
            c=read(p)
            if only and f"Velocity_{c['mode']}_H{c['H']}"!=only:continue
            include_claim(root,p)
    return jobs,attempts,claims,choose_unique(attempts)
