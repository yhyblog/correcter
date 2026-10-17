"""Immutable exact claim join; derived table failures cannot affect science."""
import math
from pathlib import Path
from paths import ROOT,EVIDENCE_ROOTS
from qio import read

class EvidenceConflict(ValueError):pass
def identity(row):return row['cell_id'],row.get('source_id',row.get('source',{}).get('source_id'))

def finite_values(value):
    reasons={}
    def visit(x,p):
        if isinstance(x,float) and not math.isfinite(x):reasons[p]='non-finite descriptive statistic';return None
        if isinstance(x,dict):return {k:visit(v,p+'.'+str(k)) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [visit(v,p+f'[{i}]') for i,v in enumerate(x)]
        return x
    row=visit(value,'$')
    if reasons and isinstance(row,dict):row['non_finite_null_reasons']=reasons
    return row

def merge_event(ep,event):
    owned={k:ep[k] for k in ('source_id','task','cell_id','H','mode','branch')}
    row=dict(owned)
    for k,v in event.items():
        if k in owned and v!=owned[k]:raise EvidenceConflict('event identity conflict: '+k)
        if k not in owned and not isinstance(v,(dict,list)):row[k]=v
    return finite_values(row)

def _load_root(root,only=None):
    claims={};attempts=[];jobs=[]
    def claim(p):
        c=read(p);key=identity(c)
        if p.name!=c['cell_id']+'__'+c['source']['source_id']+'.json':raise EvidenceConflict('claim identity/path mismatch')
        if c['unit_id']!=p.stem or c['attempt']!=0:raise EvidenceConflict('claim attempt mismatch')
        if key in claims and claims[key]!=dict(c,claim_path=str(p)):raise EvidenceConflict('duplicate changed claim')
        claims[key]=dict(c,claim_path=str(p));return c
    for jp in (root/'runs').glob('*/RESULT.json'):
        j=read(jp)
        if only and j['cell_id']!=only:continue
        jobs.append({k:j[k] for k in ('job_id','cell_id','stage','status','entered_episodes','terminal_episodes','technical_failures')})
    for p in (root/'runs').glob('*/episodes/*/RESULT.json'):
        # A fully committed per-episode result is authoritative even if a
        # concurrent directory listing has not yet observed its earlier claim.
        if only and not p.parents[2].name.startswith(only+'_'):continue
        compact=p.with_name('SUMMARY_ROW.json');x=read(compact if compact.exists() else p)
        if only and x['cell_id']!=only:continue
        cp=root/'unit_claims'/(x['cell_id']+'__'+x['source_id']+'.json');c=claim(cp)
        if identity(x)!=identity(c) or x['attempt_index']!=c['attempt']:raise EvidenceConflict('result/claim identity mismatch')
        for name in ('source_id','task','ordinal','env_seed','policy_seed'):
            if x[name]!=c['source'][name]:raise EvidenceConflict('result/claim '+name+' mismatch')
        attempts.append(dict({k:v for k,v in x.items() if k not in ('events','plans')},result_path=str(p)))
    for p in (root/'unit_claims').glob('*.json'):
        if only and not p.name.startswith(only+'__'):continue
        claim(p)
    if len({identity(x) for x in attempts})!=len(attempts):raise EvidenceConflict('completed/failed unit replay')
    return jobs,attempts,list(claims.values()),attempts

def load_evidence(only=None):
    jobs=[];attempts=[];claims=[]
    for root in EVIDENCE_ROOTS:
        j,a,c,_=_load_root(root,only);jobs.extend(j);attempts.extend(a);claims.extend(c)
    if len({identity(x) for x in attempts})!=len(attempts):raise EvidenceConflict('original/continuation terminal replay')
    if len({identity(x) for x in claims})!=len(claims):raise EvidenceConflict('original/continuation claim replay')
    return jobs,attempts,claims,attempts
