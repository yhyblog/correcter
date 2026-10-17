"""Focused synthetic control-flow checks; no model, environment or GPU is loaded."""
import ast
import json
import random
from pathlib import Path
import numpy as np
import paths
from paths import ROOT, CAMPAIGN
from qio import read, sha, atomic_json, utc
from admission import validate_job
from controller import run_episode, seed_for
from trigger_policy import selected_cut


class Runtime:
    def __init__(self, stop_at=300):self.stop_at=stop_at
    def frame(self):return np.zeros((2,2,3), np.uint8)
    def proprio(self):return np.zeros(4, np.float32)
    def step(self, action, step):return dict(reward=0., success=False, done=step+1>=self.stop_at)


class Engine:
    namespace='corrector_native10_training_20260916_v1'
    def __init__(self, gate):self.gate=gate;self.draws=[];self.candidates=[]
    def language(self):return None
    def start_natural_stream(self, seed):self.rng=np.random.default_rng(seed)
    def propose_natural(self):
        draw=self.rng.normal(size=(50,4)).astype(np.float32);self.draws.append(draw.copy())
        return draw,dict(policy_calls=1,seconds=0.)
    def context(self, frames, props, past, language, step):return step
    def monitor(self, observed, next_five):return dict(gate=self.gate, member_benefits={'241':self.gate,'242':self.gate})
    def intervene(self, method, observed, seed, step):
        self.candidates.append((step,seed))
        return np.zeros((50,4),np.float32),dict(policy_calls=1,seconds=0.,method=method)


def run(source, h, mode, cut=None, gate=1., end=300):
    e=Engine(gate)
    result=run_episode(Runtime(end),e,source,'R',h,lambda *_:None,mode=mode,random_cut=cut)
    return result,e


def main():
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    old=CAMPAIGN/'results/C/C_D24_R_H40_H50_V1/r2/code'
    for name in ['numeric_engine.py','resident_egl.py','reservation.py','process_family.py']:
        assert sha(ROOT/'code'/name)==sha(old/name)
    jobs=sorted((ROOT/'jobs').glob('*.json'))
    assert len(jobs)==500
    for p in jobs:validate_job(read(p))
    rows=read(ROOT/'config/TEST_SOURCES_V1.json')['rows'];source=rows[0]
    assert len(rows)==500 and all(0<=x['ordinal']<10 for x in rows)
    py_state=random.getstate();np_state=np.random.get_state()
    for h in (10,20,30,40,50):
        for source_row in rows:
            cut=selected_cut(source_row,h,'Random-once')
            assert 0<cut%h<=h-5 and 5<=cut<=290 and cut%5==0
            assert selected_cut(source_row,h,'G0-multi') is None
    assert random.getstate()==py_state
    assert np.array_equal(np.random.get_state()[1],np_state[1])
    checks=[]
    for h in (10,20,30,40,50):
        random_row,e=run(source,h,'Random-once',5,gate=-1.)
        assert random_row['intervention_cuts']==[5] and random_row['first_cut']==random_row['last_cut']==5
        assert random_row['random_schedule_outcome']=='executed_at_frozen_cut'
        assert not next(x for x in random_row['events'] if x['intervention_executed'])['true_G0_trigger']
        high,e_high=run(source,h,'Random-once',5,gate=1.)
        assert high['intervention_cuts']==[5]
        assert len(e.draws)==len(e_high.draws) and all(np.array_equal(a,b) for a,b in zip(e.draws,e_high.draws))
        early,_=run(source,h,'Random-once',5,end=5)
        assert early['interventions']==0 and early['steps']==5 and early['random_schedule_outcome']=='terminal_before_scheduled_cut'
        multi,e_multi=run(source,h,'G0-multi')
        # This is the derived limit of the frozen clock, not an implementation cap.
        assert multi['intervention_cuts']==list(range(5,291,15))
        assert multi['first_cut']==5 and multi['last_cut']==290 and multi['interventions']==20
        assert multi['restorations'][0]['step']==15
        for ev in multi['events']:
            if ev['intervention_executed']:
                assert ev['queue_age']>0 and ev['commit_until']==ev['step']+10 and ev['legal_cut']
        assert all(y['step']>=x['step']+10 for x,y in zip([v for v in multi['events'] if v['intervention_executed']],[v for v in multi['events'] if v['intervention_executed']][1:]))
        for step,seed in e_multi.candidates:
            assert seed==seed_for('D24_designated_a0',source['source_id'],source['policy_seed'],step,namespace=e_multi.namespace)
        assert e.candidates[0]==e_multi.candidates[0]
        reference=np.random.default_rng(source['policy_seed'])
        assert all(np.array_equal(draw,reference.normal(size=(50,4)).astype(np.float32)) for draw in e_multi.draws)
        threshold,_=run(source,h,'G0-multi',gate=.05)
        assert threshold['interventions']==0 and threshold['first_cut'] is None
        checks.append(dict(H=h,random_below_threshold_cut=5,multi_cuts=multi['intervention_cuts'],early_terminal_not_forced=True,native_RNG_unchanged=True))
    ineligible,_=run(source,10,'Random-once',cut=10)
    assert ineligible['interventions']==0 and ineligible['random_schedule_outcome']=='scheduled_cut_ineligible'
    from report import validate_baselines, compare
    validate_baselines()
    baseline={x['source_id']:dict(x,success=False,interventions=0) for x in rows}
    same={sid:dict(x) for sid,x in baseline.items()}
    comparison=compare(same,baseline,rows)
    assert comparison['paired_valid']==500 and comparison['both_failed']==500 and comparison['delta_pp']==0
    assert comparison['bootstrap95_low_pp']==comparison['bootstrap95_high_pp']==0
    result=dict(utc=utc(),status='passed',synthetic_CPU_checks=True,GPU_calls=0,model_loads=0,physical_test_episodes=0,
                frozen_science_functions_unchanged=True,job_count=500,source_count=500,random_schedule_entries=2500,
                checks=checks,invalid_random_slot_not_shifted=True,paired_calculation_check=True,training_updates=0)
    atomic_json(ROOT/'CPU_CHECK.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))


if __name__=='__main__':main()
