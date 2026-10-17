"""Bounded CPU synthetic checks for the two newly authorized trigger modes."""
import ast
import json
import random
import sys
import numpy as np
import paths
from paths import ROOT, CAMPAIGN
from qio import read, atomic_json, sha, utc
from admission import authority, validate_job, resource_admission
from trigger_controller import run_episode
from experiments.native10_training_20260916.protocol import seed_for


class Runtime:
    def __init__(self, end=None): self.n=0; self.end=end
    def frame(self): return np.asarray([self.n])
    def proprio(self): return np.full(4, self.n, np.float32)
    def step(self, action, step):
        assert step == self.n
        self.n += 1
        return dict(reward=0., success=self.n == self.end, done=False)


class Engine:
    namespace='corrector_native10_training_20260916_v1'
    def __init__(self, gate): self.gate=gate; self.natural_values=[]; self.candidates=[]
    def language(self): return np.zeros(2)
    def start_natural_stream(self, seed): self.rng=random.Random(seed)
    def propose_natural(self):
        value=self.rng.random(); self.natural_values.append(value)
        return np.full((50,4),value,np.float32),dict(policy_calls=1,seconds=0.)
    def context(self, frames, props, past, language, step):
        assert frames[-1][0] == step and len(past) == min(step,4)
        return {'step':step}
    def monitor(self, observed, block):
        assert block.shape == (5,4)
        return {'gate':self.gate}
    def intervene(self, method, observed, seed, step):
        assert method == 'Post'
        self.candidates.append((step,seed))
        return np.full((50,4),-.2,np.float32),dict(policy_calls=1,seconds=0.)


def main():
    authority(); checks=[]; source=read(ROOT/'config/TEST_SOURCES_V1.json')['rows'][0]
    schedule=read(ROOT/'config/RANDOM_ONCE_SCHEDULE_V1.json')
    assert len(schedule['rows']) == 2500
    lookup={(x['H'],x['source_id']):x['selected_cut'] for x in schedule['rows']}
    assert len(lookup) == 2500
    sources=read(ROOT/'config/TEST_SOURCES_V1.json')['rows']
    assert len(sources)==500 and all(s['ordinal']<10 for s in sources)
    for H in [10,20,30,40,50]:
        slots=[t for t in range(5,291,5) if 0<t%H<=H-5]
        assert slots==schedule['potential_legal_slots'][str(H)]
        assert all(lookup[(H,s['source_id'])] in slots for s in sources)
        cut=lookup[(H,source['source_id'])]
        E=Engine(-1.); row=run_episode(Runtime(),E,source,'Post',H,lambda *_:None,mode='Random-once',random_cut=cut)
        assert row['intervention_cuts']==[cut] and row['first_cut']==row['last_cut']==cut
        assert row['random_schedule_outcome']=='executed' and all(e['shadow_G0'] for e in row['events'])
        expected=seed_for('D24_designated_a0',source['source_id'],source['policy_seed'],cut,namespace=E.namespace)
        assert E.candidates==[(cut,expected)]
        early=run_episode(Runtime(cut),Engine(99.),source,'Post',H,lambda *_:None,mode='Random-once',random_cut=cut)
        assert early['success'] and early['interventions']==0 and early['random_schedule_outcome']=='terminal_before_scheduled_decision'
        quiet_engine=Engine(.05)
        quiet=run_episode(Runtime(),quiet_engine,source,'Post',H,lambda *_:None,mode='G0-multi')
        assert quiet['interventions']==0 and [p['step'] for p in quiet['plans']]==list(range(0,300,H))
        # The table uses no RNG draw in the controller, and intervention does not consume natural RNG.
        assert E.natural_values[:min(len(E.natural_values),len(quiet_engine.natural_values))]==quiet_engine.natural_values[:min(len(E.natural_values),len(quiet_engine.natural_values))]
        many=run_episode(Runtime(),Engine(.051),source,'Post',H,lambda *_:None,mode='G0-multi')
        cuts=many['intervention_cuts']; assert len(cuts)>=2 and cuts==list(range(5,291,15))
        assert many['first_cut']==cuts[0] and many['last_cut']==cuts[-1] and many['interventions']==len(cuts)
        assert all(e['total_cap_allows'] for e in many['events'])
        for entry in many['commitments']:
            t=entry['cut']; assert entry['committed_steps']==10
            assert np.all(many['arrays']['actions'][t:t+10]==np.float32(-.2))
            assert not any(t<e['step']<t+10 for e in many['events'])
            if t+10<300:assert entry['restored_at']==t+10 and entry['restored_H']==H
        assert all(not e['intervention_executed'] for e in many['events'] if e['queue_age']==0)
        locked_end=run_episode(Runtime(8),Engine(.1),source,'Post',H,lambda *_:None,mode='G0-multi')
        assert locked_end['intervention_cuts']==[5] and locked_end['commitments'][0]['committed_steps']==3
    invalid=run_episode(Runtime(),Engine(99.),source,'Post',10,lambda *_:None,mode='Random-once',random_cut=10)
    assert invalid['interventions']==0 and invalid['random_schedule_outcome']=='scheduled_cut_ineligible'
    checks += ['all2500 frozen slots valid and original500 sources only',
               'Random triggers at table time even negative shadowG0; early terminal or illegal slot never shifted/resampled',
               'strict multi >.05, no count cap,20 synthetic cuts and first/last/full records',
               'C10 lock, nativeH restoration age0,early success retained',
               'natural stream independent of schedule/candidates; unchanged absolute-cut candidate seed']
    jobs=list((ROOT/'jobs').glob('*.json')); assert len(jobs)==500
    for p in jobs: validate_job(read(p))
    assert sum(len(read(p)['sources']) for p in jobs)==5000
    from manager import available_jobs
    pending=available_jobs();assert len(pending)==50 and all(x[4]['mode']=='Random-once' and x[4]['H']==10 for x in pending)
    frozen=CAMPAIGN/'results/A/A_D24_MAIN_ONCE_V1/code'
    for name in ['numeric_engine.py','resident_egl.py']:
        assert (ROOT/'code'/name).read_bytes()==(frozen/name).read_bytes()
    assert sha(ROOT/'config/RANDOM_ONCE_SCHEDULE_V1.json')=='2a51139a422c3c5b88fdfc5d32c803db345619650e466fb1780f8da732e54a5f'
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text())
    assert not any(x in sys.modules for x in ['torch','mujoco','pynvml','OpenGL.EGL'])
    checks += ['500 jobs,5000 new episodes,firstcellRandomH10,no old job reuse',
               'numeric engine and NVIDIA renderer unchanged from A; no GPU/model imports']
    atomic_json(ROOT/'evidence/CPU_TRIGGER_CHECKS.json',dict(status='PASS',checks=checks,synthetic=True,
        at_utc=utc(),real_model_calls=0,GPU_probes=0,resource_admission=resource_admission()))
    print(json.dumps(dict(status='PASS',checks=len(checks),jobs=500,episodes=5000)))

if __name__=='__main__':main()
