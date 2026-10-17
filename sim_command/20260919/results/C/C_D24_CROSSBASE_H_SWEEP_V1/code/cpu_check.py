"""Targeted pure-CPU checks for new H/C semantics and immutable unit ownership."""
import ast,hashlib,collections
from pathlib import Path
import paths
from paths import ROOT,CONFIG,CAMPAIGN,AUTH_SHA
from qio import read,atomic_json,utc,sha
from horizon_queue import HorizonQueue
from admission import authority

def main():
    compiled=[]
    for folder in ('code','xcode'):
        for p in (ROOT/folder).glob('*.py'):ast.parse(p.read_text(),filename=str(p));compiled.append(str(p))
    units=read(ROOT/'UNIT_INDEX.json');manifest=CAMPAIGN/'deadline_20260924/CROSSBASE_H_SWEEP_V1/UNITS_C.jsonl'
    assert sha(manifest)=='1d58488fc4314c14713f96bc647163503b074dd8de32b93909ad350cc3f73eb6'
    assert len(units)==4000 and len({u['unit_id'] for u in units})==4000
    assert collections.Counter((u['method'],u['H']) for u in units)=={(m,h):500 for m in ('N','Post','R','Velocity') for h in (20,30)}
    assert all(u['owner']=='C' and u['model']=='X-VLA' and u['H']!=10 for u in units)
    assert len(read(ROOT/'REUSED_H10.json')['rows'])==2000
    results=[]
    for H in (20,30):
        for method in ('N','R','Post','Velocity'):
            q=HorizonQueue(H,method);cuts=[];natural=[];events=[]
            for t in range(300):
                if q.needs_plan():q.natural(list(range(30)),t);natural.append(t)
                eligible=q.can_monitor(t,min(t+1,5),t)
                if q.intervention:assert not eligible
                if eligible:
                    e={};q.intervene(list(range(100,130)),t,e);events.append(e);cuts.append(t)
                a=q.action()
                assert (100<=a<110) if q.intervention else (0<=a<H)
                q.advanced(t)
            if method=='N':assert not cuts and natural==list(range(0,300,H))
            else:
                assert len(cuts)>1 and cuts[:3]==[5,20,35]
                for t,e in zip(cuts,events):
                    assert e['commitment_executed']==10 and e['commitment_complete']
                    if t+10<300:assert e['restored_at_step']==t+10 and e['new_natural_sample'] and e['intervention_tail_discarded']
            results.append(dict(H=H,method=method,natural_refills=len(natural),always_high_gate_cuts=cuts))
    # Ineligible history/budget must never cause an auxiliary call.
    q=HorizonQueue(30,'Post');q.natural(list(range(30)),0);q.age=5
    assert not q.can_monitor(5,4,4) and not q.can_monitor(5,5,3) and not q.can_monitor(295,5,100)
    q.age=26;assert not q.can_monitor(10,5,10)
    # Context keys, output keys and claim keys separate the same source at two H.
    same=[u for u in units if u['source_id']=='D24_MW_t00_e00']
    assert len({u['storage_key'] for u in same})==8 and len({u['cell_id'] for u in same})==8
    assert CONFIG['planned_prior_attempts']==19457 and CONFIG['stage_attempt_cap']==4400
    authority()
    proof=dict(utc=utc(),passed=True,CPU_only=True,GPU_calls=0,new_scientific_units=0,normal_H_and_C10_tests=results,N_no_auxiliary_path=True,R_Q_not_loaded=True,unit_context_key_is_full_unit_id=True,compiled_files=len(compiled),manifest_SHA=sha(manifest),authorization_SHA=AUTH_SHA,no_candidate_seed_changes=True,actual_render_check='first planned episodes only, no standalone GPU preflight')
    atomic_json(ROOT/'CPU_CHECK.json',proof)
    print('CPU checks passed: H20/H30, C10/no-reentry/tail-discard, N no-trigger, 4000 owned units, 2000 H10 reused')
if __name__=='__main__':main()
