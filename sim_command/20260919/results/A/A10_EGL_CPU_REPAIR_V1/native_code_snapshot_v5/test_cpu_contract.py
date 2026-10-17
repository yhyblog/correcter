"""CPU-only semantic checks. All artificial actions/events remain synthetic=True."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest

from core.validation import ContractError, validate, validate_parent_splits, chain_transitions, build_transition_view
from core.scheduling import CoreQueue, Protocol, legal_cuts, paired_seed
from core.accounting import EventJournal, ResourceBudget, summarize, costs_per_success, RESOURCE_KEYS
from core.entry import IndependentEntry, MATCHING
from core.vendor_solo import project_solo, audit_solo, bit_equal
from core.resume import RunStore, validate_shards, core_cells
from core.release import authorize, verify_device
from core.runner import run_core

HERE = Path(__file__).resolve().parent
INTERFACE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10/interface_v1')
SCHEMA = json.loads((INTERFACE / 'interface.schema.json').read_text())
EXAMPLES = {r['record_type']: r for r in map(json.loads, (INTERFACE / 'examples.jsonl').read_text().splitlines())}


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def journal(tmp_path, caps=None, clock=None):
    kwargs = {} if clock is None else {'clock': clock}
    return EventJournal(tmp_path / 'events.jsonl', EXAMPLES['event'],
                        None if caps is None else ResourceBudget(caps), **kwargs)


@pytest.mark.parametrize('kind', list(EXAMPLES))
def test_published_examples(kind):
    validate(EXAMPLES[kind], SCHEMA)


@pytest.mark.parametrize('H', [10, 20, 30, 40, 50])
def test_all_legal_windows_match_execution(H):
    q, observed = CoreQueue(Protocol(H=H), 'R'), []
    for step in range(300):
        if q.needs_plan:
            q.install_natural(np.zeros((50, 4), np.float32), str(step))
            assert not q.monitor_eligible()
        if q.monitor_eligible():
            observed.append(step)
        q.advance()
    assert observed == legal_cuts(H)
    assert observed[-1] == (285 if H == 10 else 290)
    assert q.terminal and not q.monitor_eligible() and not q.needs_plan


@pytest.mark.parametrize('H', [10, 20, 30, 40, 50])
def test_C10_discards_tail_and_recovers_nativeH(H):
    q = CoreQueue(Protocol(H=H), 'Velocity')
    q.install_natural(np.full((50, 4), 1.2, np.float32), 'old')
    for _ in range(5):
        assert q.command()[0] == np.float32(1.2)
        q.advance()
    assert not q.alarm(.05) and q.alarm(.051)
    replacement = np.arange(200, dtype=np.float32).reshape(50, 4)
    q.install_intervention(replacement, 'entry', .051)
    for i in range(10):
        np.testing.assert_array_equal(q.command(), replacement[i])
        reason = q.advance()
    assert reason == 'intervention_complete' and q.step == 15 and q.needs_plan
    assert q.commitment == H and q.phase == 'normal'
    with pytest.raises(ContractError):
        q.command()
    q.install_natural(np.full((50, 4), -2., np.float32), 'new')
    assert q.remaining == H and q.interventions == 1
    for _ in range(5):
        q.advance()
    assert not q.monitor_eligible()


@pytest.mark.parametrize('terminal', ['success', 'terminated', 'truncated'])
def test_terminal_precedes_alarm(terminal):
    q = CoreQueue(Protocol(H=50), 'Post')
    q.install_natural(np.zeros((50, 4), np.float32), 'first')
    for _ in range(4): q.advance()
    q.advance(**{terminal: True})
    assert q.step == 5 and q.terminal and not q.monitor_eligible()


def test_projection_original_raw_bits_and_own_radius():
    raw = np.zeros((50, 4), np.float32)
    raw[0, 0], raw[1, 1], raw[0, 3], raw[40, 2] = -0., .98, 1.2, -0.
    direction = np.full((10, 4), 1e-4, np.float64)
    direction[:, 3] = 0
    plan, metadata, arrays = project_solo(raw, direction, MATCHING)
    assert metadata['groups']['xyz']['expanded']
    assert metadata['groups']['gripper']['zero_group']
    assert bit_equal(plan[10:], raw[10:]) and plan[1, 1] == raw[1, 1]
    assert plan[0, 3] == raw[0, 3] == np.float32(1.2)
    assert audit_solo(raw, plan, direction, MATCHING)['status'] == 'passed'
    zero_plan, _, _ = project_solo(raw, np.zeros((10, 4)), MATCHING)
    assert bit_equal(zero_plan, raw)
    with pytest.raises(ValueError):
        project_solo(raw, direction, {**MATCHING, 'xyz_rms': .1})


class FakeObjective:
    def gradient(self):
        return np.ones((10, 4), np.float32), {'value': 0}
    def verify(self): pass


@pytest.mark.parametrize('method,expected', [('R', 1), ('Post', 1), ('Velocity', 2)])
def test_independent_entry_calls_and_noise(tmp_path, method, expected):
    calls = []
    def sampler(**kwargs):
        calls.append(kwargs)
        kwargs['journal'].invoke('flow_forward', lambda: None, methods=[method],
                                units={'flow_forward_calls': 1}, parent=kwargs['parent_event'])
        raw = np.full((50, 4), .1 if kwargs['objective'] else 0., np.float32)
        raw[0, 3] = 1.2
        return raw, {'policy_calls': 1, 'fallback': None, 'automatic_retry': False, 'noise_sha256': '0' * 64}
    j = journal(tmp_path)
    e = IndependentEntry(sampler, lambda *args: FakeObjective(), [1, 1, 1, 0], j, lambda: 'same')
    plan, metadata, arrays = e.generate(method, {}, 42, 5)
    assert len(calls) == metadata['actual_policy_calls'] == expected
    assert all(c['seed'] == 42 for c in calls)
    assert plan[0, 3] == np.float32(1.2)
    totals = summarize(rows(j.path))
    assert totals['counts']['vla_sampling_calls'] == expected
    assert totals['counts']['flow_forward_calls'] == expected  # instrumented one per fake call, never assumed ten
    for row in rows(j.path): validate(row, SCHEMA)


def test_failure_counts_entry_once_no_retry(tmp_path):
    seen = []
    def failed_sampler(**kwargs):
        seen.append(kwargs)
        raise RuntimeError('synthetic injected failure')
    j = journal(tmp_path, {'vla_sampling_calls': 1})
    e = IndependentEntry(failed_sampler, lambda *a: None, np.ones(4), j, lambda: 'same')
    with pytest.raises(RuntimeError): e.generate('Velocity', {}, 42, 5)
    report = summarize(rows(j.path))
    assert len(seen) == report['counts']['vla_sampling_calls'] == 1
    assert report['failed_events'] == 2 and not report['incomplete_events']
    with pytest.raises(ContractError): e.generate('R', {}, 42, 5)
    assert len(seen) == 1


def test_noise_drift_is_failure(tmp_path):
    call = []
    def sampler(**kwargs):
        call.append(1)
        return np.zeros((50, 4), np.float32), {'policy_calls': 1, 'fallback': None,
            'automatic_retry': False, 'noise_sha256': str(len(call)) * 64}
    j = journal(tmp_path)
    e = IndependentEntry(sampler, lambda *a: FakeObjective(), np.ones(4), j, lambda: 'same')
    with pytest.raises(ContractError): e.generate('Velocity', {}, 42, 5)
    assert len(call) == 2 and summarize(rows(j.path))['counts']['vla_sampling_calls'] == 2


def test_shadow_two_ledgers_and_interval_union(tmp_path):
    ticks = iter([0, 1, 2, 3, 4, 5])
    j = journal(tmp_path, clock=lambda: next(ticks))
    p = j.enter('natural_plan', methods=['N', 'R'], units={'vla_sampling_calls': 1})
    child = j.enter('flow_forward', methods=['N', 'R'], units={'flow_forward_calls': 1}, parent=p)
    j.finish(child)
    j.finish(p)
    shadow = j.enter('monitor', methods=[], research_only=True, units={'monitor_calls': 1})
    j.finish(shadow)
    actual, deployN = summarize(rows(j.path)), summarize(rows(j.path), method='N')
    assert actual['counts']['monitor_calls'] == 1 and deployN['counts']['monitor_calls'] == 0
    assert deployN['wall_union_by_clock']['synthetic-clock'] == 3
    assert actual['wall_union_by_clock']['synthetic-clock'] == 4
    assert summarize(rows(j.path), method='R')['counts']['vla_sampling_calls'] == 1
    with pytest.raises(ContractError): summarize(rows(j.path) + rows(j.path)[:1])
    with pytest.raises(ContractError): summarize(rows(j.path), event_refs=['absent'])


def test_incomplete_counts_and_zero_success(tmp_path):
    j = journal(tmp_path)
    event = j.enter('anchor_sample', methods=['Post'], units={'vla_sampling_calls': 1})
    assert summarize(rows(j.path))['incomplete_events'] == [event]
    data = [{'task': 'a', 'calls': 10, 'success': False, 'technical_status': 'complete'}]
    assert costs_per_success(data)['calls_per_success'] is None
    data.append({'task': 'b', 'calls': 2, 'success': True, 'technical_status': 'complete'})
    assert costs_per_success(data)['calls_per_success'] == 12
    data.append({'task': 'a', 'calls': 5, 'success': None, 'technical_status': 'failed'})
    assert costs_per_success(data)['calls_per_success'] is None
    assert costs_per_success(data)['tasks']['a']['calls'] == 15


def test_device_parent_time_not_added_twice(tmp_path):
    j = journal(tmp_path)
    parent = j.enter('anchor_sample', methods=['Post'], units={'vla_sampling_calls': 1})
    child = j.enter('flow_forward', methods=['Post'], units={'flow_forward_calls': 1}, parent=parent)
    j.finish(child, device_elapsed=.2)
    j.finish(parent, device_elapsed=.5)
    result = summarize(rows(j.path), method='Post')
    assert result['outermost_measured_device_seconds_by_clock'] == {'synthetic-clock': .5}
    assert 'estimate' in result['time_scope']


def test_transition_gaps_leakage_future_and_splicing():
    transition = deepcopy(EXAMPLES['transition'])
    bad = deepcopy(transition); bad['next_step'] = 55
    with pytest.raises(ContractError): validate(bad, SCHEMA)
    bad = deepcopy(transition); bad['observation_ref'] = None
    with pytest.raises(ContractError): validate(bad, SCHEMA)
    bad['missing_reasons']['observation_ref'] = 'old trajectory did not save images'
    validate(bad, SCHEMA)
    view = build_transition_view([bad], ['observation_ref'], 'vla-corrector-adapted', 'latent regression', 1)
    assert view['transition_count'] == 0 and len(view['excluded']) == 1
    leak = deepcopy(transition); leak['split'] = 'test'
    with pytest.raises(ContractError): validate_parent_splits([transition, leak])
    branch = deepcopy(transition); branch['source']['suffix_id'] = 'other'
    with pytest.raises(ContractError): chain_transitions([transition, branch])
    held = deepcopy(transition); held.update(data_origin='historical_revealed_held', split='test')
    with pytest.raises(ContractError): validate(held, SCHEMA)
    future = deepcopy(EXAMPLES['context']); future['observation_max_step'] = future['environment_step'] + 1
    with pytest.raises(ContractError): validate(future, SCHEMA)


def test_external_native_frequency_not_restricted_by_single_cut_summary():
    row = deepcopy(EXAMPLES['episode'])
    row['method']['name'] = 'GAF-v1-adapted'
    row['cut_step'] = None
    row['entry_generation_id'] = None
    row['missing_reasons'].update(cut_step='multiple native guidance decisions; read complete event stream',
                                  entry_generation_id='multiple native entries; read complete event stream')
    validate(row, SCHEMA)
    row['method']['name'] = 'Post'
    with pytest.raises(ContractError): validate(row, SCHEMA)


def run_identity():
    return {k: 'test-' + k for k in ['campaign_id', 'task_id', 'task_revision', 'release_id', 'code_sha256',
            'config_sha256', 'data_sha256', 'model_sha256', 'shard_sha256', 'hostname', 'source_id']}


def test_resume_reuse_hash_mismatch_and_no_takeover(tmp_path):
    store = RunStore(tmp_path, run_identity())
    assert store.claim()['status'] == 'claimed'
    with pytest.raises(ContractError): RunStore(tmp_path, run_identity()).claim()
    artifact = store.path / 'data.json'; artifact.write_text('{}')
    store.complete([artifact], dict.fromkeys(RESOURCE_KEYS, 0))
    reused = RunStore(tmp_path, run_identity()).claim()
    assert reused['status'] == 'reuse_complete' and reused['new_physical_attempts'] == 0
    artifact.write_text('{"changed":true}')
    with pytest.raises(ContractError): RunStore(tmp_path, run_identity()).claim()


def test_explicit_shards_pairing_and_seeds():
    row = {'source_id': 's1', 'parent_episode_id': 'p1', 'split': 'development',
           'methods': ['N', 'R', 'Post', 'Velocity'], 'Hs': [10, 20],
           'seed': 1, 'host': 'A', 'node_role': 'A'}
    a = {'identity': {'shard_id': 'a', 'hostname': 'A', 'release_id': 'P10', 'node_role': 'A'},
         'sources': [row], 'assignment_rule': 'explicit_analysis_manifest'}
    assert len(validate_shards([a])) == 1
    b = deepcopy(a); b['identity']['hostname'] = 'B'; b['sources'][0]['host'] = 'B'
    with pytest.raises(ContractError): validate_shards([a, b])
    b['sources'][0]['source_id'] = 's2'; b['sources'][0]['split'] = 'test'
    with pytest.raises(ContractError): validate_shards([a, b])
    cells = core_cells([10, 20, 30, 40, 50])
    assert len(cells) == 16 and [x['H'] for x in cells if x['method'] == 'R'] == [10]
    assert paired_seed('p00', 's1', 20, 5, 0, 1, 'entry') == paired_seed('p00', 's1', 20, 5, 0, 1, 'entry')
    assert paired_seed('p00', 's1', 20, 5, 0, 1, 'entry') != paired_seed('p00', 's1', 10, 5, 0, 1, 'entry')


def test_prepare_gate_denies_real_work():
    campaign = INTERFACE.parents[3]
    control = json.loads((campaign / 'CONTROL.json').read_text())
    release = json.loads((campaign / 'releases/P00_PREP_V1.json').read_text())
    with pytest.raises(ContractError): authorize(control, release, {})


def test_release_exact_caps_host_and_identity():
    from core.initialization import EXPECTED_CAPS, CONTROL_MINIMUM_LIMITS
    caps = dict.fromkeys(RESOURCE_KEYS, 0); caps.update(simulator_attempts=1, env_steps=1, vla_sampling_calls=5, flow_forward_calls=50)
    proposal = {'task_id': 'A10_PREFLIGHT_NATIVE_V1', 'task_revision': 1, '_sha256': 'a'*64,
                'max_retries': 0, 'resource_caps': caps, 'timeout_seconds': 1800}
    control = {'campaign_id': 'corrector-sim-20260919', 'stop_requested': False,
               'formal_gpu_runs_enabled': True, 'mode': 'preflight', 'active_compute_release_id': 'P10-TEST',
               'allowed_task_ids': [proposal['task_id']], 'current_compute_limits':
               {'model_gpu_inference_calls': 5, 'simulator_attempts': 1, 'training_updates': 0}}
    release = dict(campaign_id=control['campaign_id'], release_id='P10-TEST', task_id=proposal['task_id'],
        owner_host='A', node_role='A', task_revision=1, proposal_sha256='a'*64, status='released', max_retries=0,
        resource_caps=caps, wave_id='w', shard_id='s', run_id='r', gpu_uuid='uuid', gpu_index=0, driver='d',
        runtime='r', gpu_model='g', timeout_seconds=1800, wave_participants=['A'])
    proposal.update(initialization_caps=EXPECTED_CAPS, control_minimum_limits=CONTROL_MINIMUM_LIMITS,
                    kill_grace_seconds=30, timeout_scope='diagnostic_process', external_source_manifest_sha256='c'*64)
    release.update(initialization_caps=EXPECTED_CAPS, kill_grace_seconds=30,
                   timeout_scope='diagnostic_process', external_source_manifest_sha256='c'*64)
    control['current_compute_limits'] = dict(CONTROL_MINIMUM_LIMITS)
    assert authorize(control, release, proposal, hostname='A') == caps
    for field, bad_value in [('owner_host', 'B'), ('max_retries', 1), ('proposal_sha256', 'b'*64),
                             ('wave_participants', ['A', 'B'])]:
        with pytest.raises(ContractError): authorize(control, {**release, field: bad_value}, proposal, hostname='A')
    with pytest.raises(ContractError): authorize({**control, 'mode': 'prepare'}, release, proposal, hostname='A')


def test_actual_device_identity_must_match_release():
    release = dict(gpu_index=3, gpu_uuid='GPU-example', gpu_model='H100', driver='535')
    assert verify_device(release, '3, GPU-example, H100, 535\n') == ['3', 'GPU-example', 'H100', '535']
    for changed in ['3, GPU-example, H100, 536\n', '0, GPU-example, H100, 535\n', '3, other, H100, 535\n']:
        with pytest.raises(ContractError): verify_device(release, changed)


@pytest.mark.parametrize('H', [10, 20, 30, 40, 50])
def test_sampling_quote_matches_every_legal_cut(H):
    from math import ceil
    for cut in legal_cuts(H):
        q = CoreQueue(Protocol(H=H), 'R')
        calls = 0
        while not q.terminal:
            if q.needs_plan:
                q.install_natural(np.zeros((50,4), np.float32), str(calls)); calls += 1
            if q.step == cut:
                q.install_intervention(np.zeros((50,4), np.float32), 'entry', .1); calls += 1
            q.advance()
        assert calls == ceil(cut/H) + 1 + ceil((300-cut-10)/H)


def test_runner_early_success_no_alarm_or_extra_sampler(tmp_path):
    class Backend:
        step_index = 0
        samples = 0
        monitors = 0
        closed = False
        def reset(self, source): return {'success': False, 'terminated': False, 'truncated': False}
        def sample_natural(self, *args):
            self.samples += 1
            return np.zeros((50, 4), np.float32)
        def step(self, action):
            self.step_index += 1
            return {'success': self.step_index == 5, 'terminated': False, 'truncated': False}
        def monitor(self, *args):
            self.monitors += 1
            return 1.
        def close(self): self.closed = True
    backend = Backend()
    j = journal(tmp_path)
    result = run_core(backend=backend, entry=None, journal=j, protocol=Protocol(H=50), method='Post',
                      source={'source_id': 's', 'repeat': 0}, seed_namespace='synthetic')
    assert result['success'] and result['executed_steps'] == 5 and not result['intervened']
    assert backend.samples == 1 and backend.monitors == 0 and backend.closed
    assert result['chunks'][0]['actual_executed_length'] == 5
