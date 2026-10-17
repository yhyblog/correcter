"""CPU-only merging of immutable attempts and derived publication fields."""
import math
from pathlib import Path
from paths import ROOT,OLD_ROOT
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


def load_evidence(only=None):
    jobs=[];attempts=[];claims=[];claimed=set()
    for root in (OLD_ROOT,ROOT):
        for p in sorted((root/'unit_claims').glob('*.json')):
            c=read(p)
            if only and f"Velocity_{c['mode']}_H{c['H']}"!=only:continue
            key=(*identity(c),c['attempt'])
            if key in claimed:raise EvidenceConflict('duplicate physical claim')
            claimed.add(key);claims.append(dict(c,claim_path=str(p)))
        for p in sorted((root/'runs').glob('*/RESULT.json')):
            j=read(p)
            if not only or f"Velocity_{j['mode']}_H{j['H']}"==only:
                jobs.append(dict(j,run_root=str(root),result_path=str(p)))
        for p in sorted((root/'runs').glob('*/episodes/*/RESULT.json')):
            x=read(p)
            if only and f"Velocity_{x['mode']}_H{x['H']}"!=only:continue
            attempt=0 if root==OLD_ROOT else x['attempt_index']
            key=(*identity(x),attempt)
            if key not in claimed:raise EvidenceConflict('result without same source attempt claim')
            attempts.append(dict(x,attempt_index=attempt,result_path=str(p),run_root=str(root),job_id=p.parents[2].name))
    return jobs,attempts,claims,choose_unique(attempts)
