"""CPU-only read of planned terminals, rendering fix and trigger/cost invariants."""
import json,sys
from pathlib import Path
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_L11_RETEST_V1/continuations/r3')
sys.path.insert(0,str(ROOT/'code'))
from qio import read,atomic_json,ref,utc

def main():
    units={u['unit_id']:u for u in read(ROOT/'UNIT_INDEX.json')}
    records=[];faults=[]
    for path in sorted((ROOT/'evaluation').glob('*/*/RESULT.json')):
        row=read(path)
        if row.get('status')!='complete':
            faults.append(dict(path=str(path),status=row.get('status'),error=row.get('error')));continue
        unit=units[row['unit_id']]
        assert row['loss']=='L11' and row['fit_seed']==9101 and type(row['success']) is bool
        assert row['source_id']==unit['source_id'] and row['policy_seed']==unit['policy_seed']
        assert row['claim']['unit_id']==unit['unit_id']
        render=row['render_context']
        assert render['explicit_owning_context_binding'] and render['owning_renderer_bind_count']>=row['steps']+1
        cuts=[e for e in row['events'] if e.get('trigger')];times=[e['step'] for e in cuts]
        assert row['interventions']==len(cuts) and row['first_cut']==(times[0] if times else None)
        assert all(b-a>=10 for a,b in zip(times,times[1:]))
        assert all(e['step']%5==0 and e['legal_cut'] and e['gate']>.05 and e['commit_until']==e['step']+10 for e in cuts)
        c=row['counters'];q=row['encoder_counters']
        assert c['policy_flow_calls']==10*c['policy_queries']
        assert q.get('Q_member_forward_calls',0)==4*q.get('Q_ensemble_forward_calls',0)
        if row['method']=='Post':
            assert q.get('action_gradient_calls',0)==len(cuts)
            assert q.get('Q_ensemble_forward_calls',0)==len(cuts)
        records.append(dict(result=ref(path),source_id=row['source_id'],success=row['success'],steps=row['steps'],cuts=times,renderer_bind_count=render['owning_renderer_bind_count'],flow=c['policy_flow_calls'],sampling=c['policy_queries'],action_gradients=q.get('action_gradient_calls',0),attempt=row['claim']['attempt']))
    result=dict(utc=utc(),status='planned_terminal_invariants_verified' if records and not faults else 'no_valid_terminal_yet' if not records and not faults else 'technical_gaps_present',checked_terminals=len(records),technical_or_unknown=faults,checks=records,per_source_render_context_binding=True,C10_no_reentry=True,first_cut_verified=True,frozen_NFE_and_Q_costs_verified=True,new_scientific_units=0,new_GPU_calls=0,not_a_new_blind_test=True)
    atomic_json(ROOT/'evidence/PLANNED_PROGRESS_VALIDATION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
if __name__=='__main__':main()
