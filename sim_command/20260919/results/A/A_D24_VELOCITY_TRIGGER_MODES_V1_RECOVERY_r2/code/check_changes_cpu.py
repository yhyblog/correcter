"""Narrow real-controller synthetic checks; no Torch/hardware/environment imports."""
import ast
import json
import sys
from pathlib import Path
import numpy as np
import paths
from paths import ROOT
from qio import read,atomic_json,sha,utc
from controller import run_episode,seed_for
from admission import validate_job


class Runtime:
    def __init__(self,terminal=300,success=False):self.t=0;self.terminal=terminal;self.success=success
    def frame(self):return np.zeros((2,2,3),dtype=np.uint8)
    def proprio(self):return np.zeros(4,dtype=np.float32)
    def step(self,action,t):
        assert t==self.t;self.t+=1
        return dict(reward=0.,done=self.t==self.terminal,success=self.success and self.t==self.terminal)


class Engine:
    namespace='corrector_native10_training_20260916_v1'
    def __init__(self,gate):self.gate=gate;self.seeds=[];self.natural=[];self.contexts=[]
    def language(self):return None
    def start_natural_stream(self,seed):self.rng=np.random.default_rng(seed)
    def propose_natural(self):
        value=self.rng.standard_normal((50,4)).astype(np.float32);self.natural.append(value.copy())
        return value,dict(policy_calls=1,seconds=0.)
    def context(self,frames,props,past,language,t):self.contexts.append(t);return dict(step=t)
    def monitor(self,observed,next_five):return dict(gate=self.gate,member_benefits={'241':self.gate,'242':self.gate})
    def intervene(self,method,observed,seed,t):
        assert method=='Velocity';self.seeds.append((t,seed))
        return np.zeros((50,4),dtype=np.float32),dict(policy_calls=2,seconds=0.)


def run(mode,H=10,cut=5,gate=.06,terminal=300,success=False):
    source=read(ROOT/'config/TEST_SOURCES_V1.json')['rows'][0];engine=Engine(gate);events=[]
    row=run_episode(Runtime(terminal,success),engine,source,'Velocity',H,lambda k,v:events.append((k,dict(v))),
        mode=mode,random_cut=cut)
    return row,engine,events


def main():
    checks=[];cfg=read(ROOT/'config/CONFIG.json');schedule=read(ROOT/'config/RANDOM_ONCE_SCHEDULE_V1.json')
    for h,n in [(10,29),(20,44),(30,49),(40,51),(50,53)]:
        slots=[t for t in range(5,291,5) if 0<t%h<=h-5]
        assert len(slots)==n and schedule['potential_legal_slots'][str(h)]==slots
    checks.append('five authoritative slot sets and counts')
    jobs=sorted((ROOT/'jobs').glob('*.json'));assert len(jobs)==500
    for p in jobs:validate_job(read(p))
    assert len({(s['source_id'],s['H']) for s in schedule['rows']})==2500
    checks.append('500 real jobs cover exact500 ordinal0..9 sources and2500 frozen source/H schedule rows')
    for h in [10,30,50,20,40]:
        cut=next(x['selected_cut'] for x in schedule['rows'] if x['source_id']==read(jobs[0])['sources'][0]['source_id'] and x['H']==h)
        row,eng,ev=run('Random-once',h,cut,gate=-.1)
        assert row['intervention_cuts']==[cut] and row['first_cut']==row['last_cut']==cut
        assert row['random_schedule_disposition']=='executed_at_selected_cut' and row['shadow_DG0_contexts']>0
        assert all(not x['true_G0_trigger'] for x in row['events'])
    checks.append('Random fires at table time despite negative shadow G0, once only for each H')
    early,_,_=run('Random-once',cut=5,terminal=5,success=True)
    assert early['steps']==5 and early['interventions']==0 and early['no_intervention_reason']=='terminal_before_selected_cut'
    checks.append('t means completed steps; early terminal never forced, redrawn or shifted')
    multi,eng,events=run('G0-multi')
    assert len(multi['intervention_cuts'])>=2 and multi['first_cut']==5 and multi['last_cut']==multi['intervention_cuts'][-1]
    assert multi['interventions']==len(multi['intervention_cuts']) and all(y-x>=15 for x,y in zip(multi['intervention_cuts'],multi['intervention_cuts'][1:]))
    executed=[e for e in multi['events'] if e['intervention_executed']]
    assert all(e['C10_steps_executed']==10 and e['C10_complete'] for e in executed)
    assert all(e['native_H_restored'] and e['native_restore_step']==e['step']+10 for e in executed[:-1])
    assert all(not e['legal_cut'] for e in multi['events'] if e['queue_age']==0)
    checks.append('multi real controller repeated events, immutable first_cut, C10 lock, native refill and age0 rejection')
    zero,_,_=run('G0-multi',gate=.05);assert zero['interventions']==0
    checks.append('G0 threshold is strictly greater than .05')
    partial,_,_=run('Random-once',cut=5,terminal=7,success=True)
    ev=next(x for x in partial['events'] if x['intervention_executed'])
    assert ev['C10_steps_executed']==2 and not ev['C10_complete'] and not ev['native_H_restored']
    checks.append('early success inside C10 retains partial coverage without extra actions')
    random,er,_=run('Random-once',cut=5)
    assert eng.seeds[0]==er.seeds[0]
    src=read(ROOT/'config/TEST_SOURCES_V1.json')['rows'][0]
    assert er.seeds[0][1]==seed_for('D24_designated_a0',src['source_id'],src['policy_seed'],5,namespace=er.namespace)
    assert all(np.array_equal(x,y) for x,y in zip(er.natural,eng.natural))
    checks.append('same absolute-cut candidate domain; precomputed random schedule consumes no natural RNG draws')
    try:run('Random-multi')
    except ValueError:pass
    else:raise AssertionError('undeclared mode accepted')
    checks.append('undeclared mode rejected')
    old=ROOT.parents[1]/'A_D24_MAIN_ONCE_V1/code/numeric_engine.py'
    # The numeric engine is copied byte-for-byte; only timing/controller plumbing changed.
    old=ROOT.parent/'A_D24_MAIN_ONCE_V1/code/numeric_engine.py'
    assert sha(old)==sha(ROOT/'code/numeric_engine.py')
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text())
    manager=(ROOT/'code/manager.py').read_text()
    assert 'WorkerOccupancy' not in manager and 'occupancy.refresh' not in manager and 'occupancy.close' not in manager
    assert 'torch' not in sys.modules
    atomic_json(ROOT/'CPU_CHANGE_CHECKS.json',dict(utc=utc(),status='PASS',checks=checks,synthetic=True,
        numeric_engine_sha256=sha(old),science_calls=0,GPU_probes=0,real_environment_resets=0,holder_changes=0,
        simulated_multi_cuts=multi['intervention_cuts'],scope='Only new trigger-mode real controller plus fake runtime/engine and new metadata/AST'))
    print(json.dumps(dict(status='PASS',checks=len(checks),simulated_multi_cuts=multi['intervention_cuts'])))


if __name__=='__main__':main()
