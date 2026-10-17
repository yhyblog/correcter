"""Injected arithmetic stubs; these tests never create MuJoCo/VLA/GPU runtimes."""
import json
from types import SimpleNamespace
import numpy as np
import pytest
from . import adapter, storage
from .adapter import Native10Collector


class RuntimeStub:
    def __init__(self, success_at=None):
        self.success_at = success_at
        self.backend = SimpleNamespace(encode_instruction=lambda text: np.zeros(2, np.float32))
        self.instruction = 'stub'
        self.horizons = []

    def reset(self, case, horizon):
        self.horizons.append(horizon)
        self.t = 0
        self.state = np.zeros(4, np.float64)

    def physics_state(self):
        return np.r_[self.t, self.state].copy()

    def fingerprint(self):
        return adapter.digest(self.physics_state())

    def frame(self):
        return np.full((2,2,3), self.t % 255, np.uint8)

    def proprio(self):
        return self.state.astype(np.float32)

    def step(self, command):
        self.state += np.asarray(command, np.float64)
        self.t += 1
        return dict(reward=0., success=self.t == self.success_at, done=False)


class EngineStub:
    def __init__(self, gate=.1, success_at=None):
        self.runtime = RuntimeStub(success_at)
        self.gate = gate
        self.calls = []

    def propose(self, seed, loss=None):
        self.calls.append((self.runtime.t, seed))
        plan = np.random.default_rng(seed).uniform(-.1,.1,(50,4)).astype(np.float32)
        # First-ten and tail must remain distinguishable; raw must not be clipped.
        plan[:10,3] = 1.4
        plan[10:,3] = 9.
        return plan, dict(policy_calls=1, seconds=0.)

    def context(self, *args):
        return {'history':np.zeros((1,5,4096),np.float32),'history_mask':np.ones((1,5),bool),
                'proprio':np.zeros((1,5,4),np.float32),'proprio_mask':np.ones((1,5),bool),
                'past_actions':np.zeros((1,4,4),np.float32),'language':np.zeros((1,2048),np.float32),
                'remaining':np.asarray([1.],np.float32)}

    def monitor(self, batch, next_five):
        assert next_five.shape == (5,4)
        return dict(gate=self.gate)

    def make_bank(self, observed, case, cut):
        from corrector.candidates import construct
        from .commands import preserve_raw_anchor
        raw,_=self.propose(13)
        base=np.clip(raw,-1,1)
        cfg=dict(xyz_rms=.05,gripper_rms=.1,xyz_linf=.15,gripper_linf=.4,
                 boundary_clearance=.05,tolerance=1e-6,zero_threshold=1e-10)
        gradient=np.ones((10,4),np.float32)
        plans,matching=construct(base,np.clip(base+.1,-1,1),np.clip(base+.2,-1,1),gradient,12,cfg)
        plans={key:preserve_raw_anchor(raw,base,p) for key,p in plans.items() if not key.endswith('_native')}
        return plans,{'matching':matching},{'raw_a0':raw,'post_internal_metric_direction':gradient}

    def verify(self):
        return True


class LedgerStub:
    def __init__(self):
        self.rows=[]

    def reserve(self, stage, kind, identity):
        row=dict(number=len(self.rows)+1, stage=stage, kind=kind, identity=str(identity))
        self.rows.append(row)
        return row


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(adapter, 'ROOT', tmp_path)
    config=dict(seed_namespace='unit_stub', control_budget=300, source_horizon=10,
                gate_threshold=.05, replicates=4, methods=['continue_native10','alarm_replan10','velocity','direct','post'], analysis_approval={'protocol_sha256':'stub'})
    case=dict(case_id='disassemble-v3__99', episode_id='disassemble-v3__99',
              task='disassemble-v3', env_seed=99, split='p0')
    config['episode_manifest']=[case]
    config['matching']=dict(xyz_rms=.05,gripper_rms=.1,xyz_linf=.15,gripper_linf=.4,
                            boundary_clearance=.05,tolerance=1e-6,zero_threshold=1e-10,
                            algorithm='extra descriptive settings must be filtered for thirteen-candidate builder')
    def make(**kwargs):
        engine=EngineStub(**kwargs)
        ledger=LedgerStub()
        return Native10Collector(engine,config,ledger,'p0'), engine, ledger, case
    return make


def test_source_starts_native10_and_captures_first_eligible_midpoint(setup):
    collector, engine, ledger, case=setup()
    source=collector.capture(case)
    meta=json.loads((source/'summary.json').read_text())
    assert meta['cuts']==[5]
    assert meta['events'][0]['exceeds_threshold']
    assert not meta['events'][0]['interruption_eligible']
    assert engine.runtime.horizons==[10]
    with np.load(source/'trajectory.npz') as z:
        assert z['actions'].shape==(5,4)
        assert np.all(z['actions'][:,3]==np.float32(1.4))
    assert len(ledger.rows)==1


def test_normal_remainder_and_corrected_cadence_pair_suffix_indices(setup):
    collector, engine, ledger, case=setup()
    source=collector.capture(case)
    normal=collector.branch(case,source,5,'continue_native10',None,0)
    raw,_=engine.propose(111)
    replan=collector.branch(case,source,5,'alarm_replan10',raw,0)
    post=collector.branch(case,source,5,'post',raw,0)
    n,r,p=[json.loads((path/'summary.json').read_text()) for path in (normal,replan,post)]
    assert n['actual_prefix_steps']==5 and n['first_actual_resample']==10
    assert r['actual_prefix_steps']==10 and r['first_actual_resample']==15
    assert [x['seed'] for x in n['suffix_seeds'][:3]]==[x['seed'] for x in r['suffix_seeds'][:3]]
    assert r['suffix_seeds']==p['suffix_seeds']
    with np.load(replan/'trajectory.npz') as a,np.load(post/'trajectory.npz') as b:
        for key in a.files:np.testing.assert_array_equal(a[key],b[key])
    with np.load(normal/'trajectory.npz') as z:
        assert np.all(z['actions'][:,3]==np.float32(1.4)) # never old plan tail
    assert len(ledger.rows)==4
    assert set(engine.runtime.horizons)=={10}


def test_no_alarm_early_success_keeps_planned_source(setup):
    collector,engine,ledger,case=setup(gate=0.,success_at=12)
    source=collector.capture(case)
    row=json.loads((source/'summary.json').read_text())
    assert row['no_alarm'] and row['cuts']==[] and row['success']
    assert row['full_episode_outcome_available'] and row['planned_episode_retained']
    assert [t for t,_ in engine.calls]==[0,10]
    assert len(ledger.rows)==1


def test_scheduled_cut_uses_preregistered_time_without_outcome_selection(setup):
    collector,engine,ledger,case=setup(gate=0.)
    case['cut_rule']={'kind':'scheduled','step':25}
    source=collector.capture(case)
    row=json.loads((source/'summary.json').read_text())
    assert row['cuts']==[25] and row['no_alarm']
    assert [t for t,_ in engine.calls]==[0,10,20]


def test_early_success_before_schedule_is_retained_without_replacement(setup):
    collector,engine,ledger,case=setup(gate=0.,success_at=12)
    case['cut_rule']={'kind':'scheduled','step':95}
    row=json.loads((collector.capture(case)/'summary.json').read_text())
    assert row['cuts']==[] and row['end_reason']=='success'
    assert len(ledger.rows)==1


def test_modified_split_or_unregistered_case_rejected_before_attempt(setup):
    collector,engine,ledger,case=setup()
    for override in ({'split':'heldout'},{'case_id':'alias'},{'cut_rule':{'kind':'scheduled','step':25}}):
        with pytest.raises(ValueError,match='preregistered'):
            collector.capture(dict(case,**override))
    assert not ledger.rows


def test_invalid_repeat_rejected_even_before_early_termination(setup):
    collector,engine,ledger,case=setup()
    for repeat in (-1,4,True):
        with pytest.raises(ValueError,match='Repeat'):
            collector.branch(case,'unused',5,'continue_native10',None,repeat)
    assert not ledger.rows


def test_real_adapter_bank_wiring_and_thirteen_candidate_preview_are_cpu_tested(setup):
    collector,engine,ledger,case=setup()
    source=collector.capture(case)
    bank=collector.prepare_bank(case,source,5)
    with np.load(bank/'plans.npz') as z:
        assert {'alarm_replan10','velocity','direct','post'} <= set(z.files)
        assert z['alarm_replan10'][0,3]==np.float32(1.4)
    preview=json.loads((bank/'preview13_metadata.json').read_text())
    assert preview['candidate_count']==13 and preview['retained_all']
    with np.load(bank/'preview13_directions.npz') as z:
        assert z['actual_deltas'].shape==(13,10,4)
    assert len(ledger.rows)==2 and ledger.rows[-1]['kind']=='candidate_restore'
