"""Arithmetic CPU fixtures only; no real environment, GPU or optimizer calls."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from . import adapter, main_collection, main_runner, storage
from .candidates13 import CANDIDATE_ORDER, DEFAULT_CONFIG
from .main_collection import MainCollector, MainSourceRejected, SPLIT_REPLICATES, create_main_collector, select_cut
from .protocol import pending_protocol, protocol_digest, candidate_seed
from .test_adapter import EngineStub, LedgerStub


class MainEngineStub(EngineStub):
    def __init__(self, config, critic_hashes, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.selector = SimpleNamespace(ranking={'model_hashes': deepcopy(critic_hashes)})

    def propose(self, seed, loss=None):
        raw, stats = super().propose(seed, loss)
        stats['noise_sha256'] = hashlib.sha256(str(seed).encode()).hexdigest()
        return raw, stats

    def make_bank(self, observed, case, cut):
        plans, metadata, directions = super().make_bank(observed, case, cut)
        metadata['base_seed'] = candidate_seed(case, cut, namespace=self.config['seed_namespace'])
        return plans, metadata, directions


def approve(config, document, ready_path, *, release_main=True):
    h = hashlib.sha256(document.read_bytes()).hexdigest()
    ready = dict(task_id='native10-training-20260916', status='approved',
                 task_document=str(document), protocol_review=str(document),
                 task_document_sha256=h, protocol_review_sha256=h,
                 released_scope=['p0_anchor_and_native10_diagnostics']+(['main_collection', 'technical_replacements'] if release_main else []),
                 new_simulator_attempts_hard_limit=50000, p0_attempts_hard_limit=600)
    ready_path.write_text(json.dumps(ready))
    config['analysis_ready'] = dict(path=str(ready_path), sha256=hashlib.sha256(ready_path.read_bytes()).hexdigest())
    config['analysis_approval'] = dict(status='approved', approved_by='analysis', document_path=str(document),
                                     document_sha256=h, protocol_sha256=protocol_digest(config))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    for module in (storage, adapter, main_collection, main_runner):
        monkeypatch.setattr(module, 'ROOT', tmp_path/'outputs')
    monkeypatch.setattr(main_collection, '_score_bank', lambda engine, observed, raw, plans:
                        {name: {'mean_gain': 0., 'member_probabilities': [[.5, .5]]*4} for name in plans})
    def scene(runtime, case, attempt, config, destination):
        destination.mkdir(parents=True)
        record = dict(status='accepted', scene_fingerprint='e'*64, exact_state_sha256='f'*64)
        storage.dump(destination/'identity.json', record)
        storage.seal(destination)
        return record
    monkeypatch.setattr(main_collection, '_capture_scene', scene)
    case = dict(case_id='disassemble-v3__9001', episode_id='disassemble-v3__9001', task='disassemble-v3',
                env_seed=9001, split='train', round=1, source_horizon=10, cut_rule={'kind': 'first_alarm'})
    config = pending_protocol()
    critic = {str(member): str(member)*64 for member in range(1, 5)}
    models = dict(vla='a'*64, d='b'*64, g0='c'*64, implementation='d'*64,
                  **{'critic_'+key: value for key, value in critic.items()})
    registration = dict(stage='collect', kind='labels13', episode_ids=[case['episode_id']], generation_round=1,
        model_hashes=models, critic_member_hashes=critic, random_seed_domain='main_candidates13',
        cut_selection_policy='analysis_lead_v1', channel_radius_by_episode={case['episode_id']: 1.})
    config.update(status='frozen', episode_manifest=[case], control_budget=300, gate_threshold=.05,
        replicates=4, split_replicates=dict(SPLIT_REPLICATES), matching=dict(DEFAULT_CONFIG), methods=list(main_collection.POLICY_METHODS),
        cpu=dict(worker_threads=1, critic_threads=2),
        budget=dict(hard_total=50000, training_update_total=0, count_failures=True, count_retries=True,
                    stages={'p0': dict(simulator_attempts=600, training_updates=0),
                            'collect': dict(simulator_attempts=1000, training_updates=0)}),
        stage_release_scopes={'p0': 'p0_anchor_and_native10_diagnostics', 'collect': 'main_collection'},
        main_collection={'banks': {'labels_round1': registration}})
    document, ready = tmp_path/'CPU_TEST_ONLY.md', tmp_path/'NATIVE10_ANALYSIS_READY.json'
    document.write_text('Synthetic authorization for arithmetic CPU stubs only. No real compute.\n')

    def build(*, version='labels_round1', release_main=True, **kwargs):
        approve(config, document, ready, release_main=release_main)
        engine, ledger = MainEngineStub(config, critic, **kwargs), LedgerStub()
        collector = MainCollector(engine, config, ledger, 'collect', bank_version=version)
        return collector, engine, ledger

    return config, case, build, document, ready


def test_current_p0_scope_cannot_release_main_even_with_a_budget(setup):
    config, _, build, _, _ = setup
    with pytest.raises(ValueError, match='released'):
        build(release_main=False)
    with pytest.raises(ValueError, match='P0'):
        MainCollector(None, config, None, 'p0', bank_version='labels_round1')
    with pytest.raises(ValueError, match='released'):
        create_main_collector(config, 'collect', bank_version='labels_round1')


def test_labels_have_13_plus_normal_and_bind_all_provenance(setup):
    config, case, build, _, _ = setup
    collector, engine, ledger = build(success_at=17)
    dest = collector.collect_episode(case)
    result = json.loads((dest/'summary.json').read_text())
    assert result['actual_branch_count'] == 56
    assert len(ledger.rows) == 58  # capture + bank restoration + 56 branches
    assert result['methods'] == list(CANDIDATE_ORDER)+['continue_native10']
    bank = collector.bank_path(case, 5)
    metadata = json.loads((bank/'metadata.json').read_text())
    assert metadata['candidate_count'] == 13 and metadata['a0_slot'] == 0
    assert bank.parts[-4] == 'banks'
    assert not (main_collection.ROOT/'candidates').exists()
    normal = json.loads((collector.branch_path(case, 5, 'continue_native10', 0)/'summary.json').read_text())
    a0 = json.loads((collector.branch_path(case, 5, 'a0', 0)/'summary.json').read_text())
    reverse = json.loads((collector.branch_path(case, 5, 'reverse_post', 0)/'summary.json').read_text())
    assert normal['actual_prefix_steps'] == 5 and normal['first_actual_resample'] == 10
    assert a0['actual_prefix_steps'] == 10 and a0['first_actual_resample'] == 15
    assert normal['suffix_seeds'][0]['seed'] == a0['suffix_seeds'][0]['seed']
    assert normal['suffix_seeds'][0]['noise_sha256'] == a0['suffix_seeds'][0]['noise_sha256']
    assert not normal['critic_candidate'] and a0['candidate_slot'] == 0
    assert reverse['execution_role'] == 'alarm_replan10' and reverse['method'] == 'reverse_post'
    assert a0['paired_suffix_id'] == normal['paired_suffix_id'] == case['episode_id']+':cut5:repeat0'
    for row in (normal, a0, reverse):
        assert row['candidate_bank_sha256'] == storage.sha256(bank/'complete.json')
        assert row['source_seal_sha256'] == result['source_seal_sha256']
        assert row['protocol_sha256'] == config['analysis_approval']['protocol_sha256']
        assert row['model_hashes'] == result['model_hashes']
        assert not row['physical_outcome_reused']
    # Every logical slot has its own counted run, even exact raw aliases.
    assert len({row['budget_attempt'] for row in result['branch_records']}) == 56
    assert collector.collect_episode(case) == dest
    assert len(ledger.rows) == 58


def test_no_cut_and_unreached_schedule_keep_complete_episode_without_critic_inputs(setup):
    _, case, build, _, _ = setup
    case['cut_rule'] = {'kind': 'scheduled', 'step': 95, 'fallback': 'none_pending_analysis_review'}
    collector, _, ledger = build(gate=0., success_at=4)
    dest = collector.collect_episode(case)
    result = json.loads((dest/'summary.json').read_text())
    assert result['no_cut'] and result['common_outcome'] is True
    assert result['actual_branch_count'] == 0 and result['planned_episode_retained']
    assert result['candidate_bank_sha256'] is None and result['bank_path'] is None
    assert not result['fabricate_critic_input_for_no_cut'] and not result['source_replaced']
    assert result['cut_selection_policy'] == 'analysis_lead_v1'
    assert result['requested_cut'] == 95 and result['actual_cut'] is None
    assert result['selection_reason'] == 'no_legal_cut'
    assert result['missing_cut_reason'] == 'success' and len(ledger.rows) == 1
    assert not (main_collection.ROOT/'banks').exists()


def test_scheduled_reached_cut_and_raw_commands_keep_native10_semantics(setup):
    _, case, build, _, _ = setup
    case['cut_rule'] = {'kind': 'scheduled', 'step': 15}
    collector, _, ledger = build(gate=0., success_at=28)
    source = collector.capture(case)
    assert json.loads((source/'summary.json').read_text())['cuts'] == [15]
    bank = collector.prepare_bank(case, source, 15)
    with np.load(bank/'plans.npz') as archive:
        raw = archive['random_full_positive'].copy()
    path = collector.branch(case, source, 15, 'random_full_positive', raw, 2)
    summary = json.loads((path/'summary.json').read_text())
    assert summary['first_actual_resample'] == 25 and summary['actual_prefix_steps'] == 10
    with np.load(path/'trajectory.npz') as archive:
        assert np.all(archive['actions'][:, 3] == np.float32(1.4))
    assert len(ledger.rows) == 3


def test_separate_policy_versions_share_source_but_not_banks_or_branches(setup):
    config, case, build, document, ready = setup
    case.update(split='development', round=None)
    first = config['main_collection']['banks']['labels_round1']
    first.update(kind='policy5')
    config['main_collection']['banks']['policy_round2'] = dict(deepcopy(first), generation_round=2)
    one, engine, ledger = build(success_at=17)
    first_dest = one.collect_episode(case)
    two = MainCollector(engine, config, ledger, 'collect', bank_version='policy_round2')
    second_dest = two.collect_episode(case)
    assert first_dest != second_dest
    assert one.bank_path(case, 5) != two.bank_path(case, 5)
    assert one.branch_path(case, 5, 'post', 0) != two.branch_path(case, 5, 'post', 0)
    assert len(ledger.rows) == 43  # one source + two banks + 40 policy branches
    for path in (first_dest, second_dest):
        row = json.loads((path/'summary.json').read_text())
        assert row['actual_branch_count'] == 20 and row['methods'] == list(main_collection.POLICY_METHODS)
    assert all(row['kind'] != 'source_capture' for row in ledger.rows[1:])


def test_wrong_plan_repeat_case_or_active_critic_rejected_before_attempt(setup):
    _, case, build, _, _ = setup
    collector, engine, ledger = build(success_at=17)
    source = collector.capture(case)
    bank = collector.prepare_bank(case, source, 5)
    with np.load(bank/'plans.npz') as archive:
        raw = archive['a0'].copy()
    changed = raw.copy()
    changed[0, 3] = 1.
    for name, plan, repeat in [('a0', changed, 0), ('a0', raw, 4), ('a0', raw, True), ('continue_native10', raw, 0)]:
        with pytest.raises(ValueError):
            collector.branch(case, source, 5, name, plan, repeat)
    with pytest.raises(ValueError, match='preregistered'):
        collector.capture(dict(case, env_seed=9002))
    engine.selector.ranking['model_hashes']['1'] = '9'*64
    with pytest.raises(ValueError, match='Loaded critic'):
        collector.branch(case, source, 5, 'a0', raw, 0)
    assert len(ledger.rows) == 2


def test_bank_mutation_and_unsealed_partial_work_never_resume_silently(setup):
    _, case, build, _, _ = setup
    collector, _, ledger = build(success_at=17)
    source = collector.capture(case)
    bank = collector.prepare_bank(case, source, 5)
    (bank/'metadata.json').write_text('{}')
    with pytest.raises(ValueError, match='SHA'):
        collector.collect_episode(case)
    assert len(ledger.rows) == 2


@pytest.mark.parametrize('target,available,expected,reason', [
    (15, [5, 15], 15, 'scheduled_target_reached'),
    (15, [5], 5, 'scheduled_prior_anchor_fallback'),
    (45, [5, 15], 15, 'scheduled_prior_anchor_fallback'),
    (45, [5], 5, 'scheduled_prior_anchor_fallback'),
    (95, [5, 15, 45], 45, 'scheduled_prior_anchor_fallback'),
    (95, [5, 15], 15, 'scheduled_prior_anchor_fallback'),
    (95, [5], 5, 'scheduled_prior_anchor_fallback'),
    (95, [], None, 'no_legal_cut'),
])
def test_scheduled_fallback_uses_fixed_priority_and_only_live_saved_cuts(target, available, expected, reason):
    case = dict(split='train', cut_rule={'kind': 'scheduled', 'step': target})
    selected = select_cut(case, available, None)
    assert selected['requested_cut'] == target and selected['actual_cut'] == expected
    assert selected['selection_reason'] == reason
    assert not selected['selection_audit']['selection_uses_outcome_labels']


@pytest.mark.parametrize('split,available,alarm,expected,reason', [
    ('train', [5, 15, 35], 35, 35, 'first_legal_alarm'),
    ('train', [5, 15, 45, 95], None, 15, 'no_alarm_training_anchor_fallback'),
    ('train', [5], None, 5, 'no_alarm_training_anchor_fallback'),
    ('train', [], None, None, 'no_legal_cut'),
    ('development', [5, 15], None, None, 'no_alarm_policy_common_outcome'),
    ('calibration', [5, 15], None, None, 'no_alarm_policy_common_outcome'),
    ('heldout', [5, 15], None, None, 'no_alarm_policy_common_outcome'),
])
def test_first_alarm_fallback_is_training_only(split, available, alarm, expected, reason):
    selected = select_cut(dict(split=split, cut_rule={'kind': 'first_alarm'}), available, alarm)
    assert selected['requested_cut'] is None and selected['actual_cut'] == expected
    assert selected['selection_reason'] == reason


def test_terminal_before_scheduled_target_selects_saved_earlier_anchor_and_replays_it(setup):
    _, case, build, _, _ = setup
    case['cut_rule'] = {'kind': 'scheduled', 'step': 95}
    collector, _, ledger = build(gate=0., success_at=50)
    source = collector.capture(case)
    summary = json.loads((source/'summary.json').read_text())
    assert summary['available_legal_cuts'] == [5, 15, 45]
    assert summary['requested_cut'] == 95 and summary['actual_cut'] == 45
    assert summary['cuts'] == [45] and summary['steps'] == 50 and summary['success']
    assert summary['selection_reason'] == 'scheduled_prior_anchor_fallback'
    assert summary['full_episode_outcome_available'] and summary['selection_category'] == 'fallback'
    bank = collector.prepare_bank(case, source, 45)
    with np.load(bank/'plans.npz') as archive:
        plan = archive['a0'].copy()
    branch = collector.branch(case, source, 45, 'a0', plan, 0)
    result = json.loads((branch/'summary.json').read_text())
    assert result['actual_prefix_steps'] == 5 and result['terminal_step'] == 50
    assert len(ledger.rows) == 3


def test_terminal_exactly_at_anchor_clock_does_not_create_a_live_anchor(setup):
    _, case, build, _, _ = setup
    case['cut_rule'] = {'kind': 'scheduled', 'step': 45}
    collector, _, _ = build(gate=0., success_at=15)
    row = json.loads((collector.capture(case)/'summary.json').read_text())
    assert row['available_legal_cuts'] == [5]
    assert row['actual_cut'] == 5 and not (main_collection.ROOT/'sources'/case['case_id']/'cut015').exists()


def test_no_alarm_training_runs_whole_episode_before_offline_fallback(setup):
    _, case, build, _, _ = setup
    collector, _, ledger = build(gate=0.)
    row = json.loads((collector.capture(case)/'summary.json').read_text())
    assert row['steps'] == 300 and row['full_episode_outcome_available']
    assert row['available_legal_cuts'] == [5, 15, 45, 95] and row['actual_cut'] == 15
    assert row['no_alarm'] and row['selection_reason'] == 'no_alarm_training_anchor_fallback'
    assert len(ledger.rows) == 1


def test_no_alarm_development_keeps_common_outcome_even_with_early_anchors(setup):
    _, case, build, _, _ = setup
    case.update(split='development', round=None)
    collector, _, ledger = build(gate=0., success_at=18)
    dest = collector.collect_episode(case)
    row = json.loads((dest/'summary.json').read_text())
    assert row['actual_cut'] is None and row['common_outcome'] is True
    assert row['selection_reason'] == 'no_alarm_policy_common_outcome'
    assert row['selection_audit']['available_legal_cuts'] == [5, 15]
    assert row['actual_branch_count'] == 0 and len(ledger.rows) == 1


def test_heldout_policy_has_four_repeats_only_in_explicitly_registered_main_bank(setup):
    config, case, build, _, _ = setup
    case.update(split='heldout', round=None)
    config['main_collection']['banks']['labels_round1']['kind'] = 'policy5'
    collector, _, ledger = build(success_at=7)
    row = json.loads((collector.collect_episode(case)/'summary.json').read_text())
    assert row['replicates'] == 4 and row['actual_branch_count'] == 20
    assert len(ledger.rows) == 22


def test_completed_collection_rechecks_referenced_branch_seals(setup):
    _, case, build, _, _ = setup
    collector, _, ledger = build(success_at=7)
    collector.collect_episode(case)
    branch = collector.branch_path(case, 5, 'a0', 0)
    (branch/'summary.json').write_text('{}')
    with pytest.raises(ValueError, match='SHA'):
        collector.collect_episode(case)
    assert len(ledger.rows) == 58


def test_calibration_policy_uses_two_repeats_per_distinct_state(setup):
    config, case, build, _, _ = setup
    case.update(split='calibration', round=None)
    config['main_collection']['banks']['labels_round1']['kind'] = 'policy5'
    collector, _, ledger = build(success_at=7)
    row = json.loads((collector.collect_episode(case)/'summary.json').read_text())
    assert row['replicates'] == 2 and row['actual_branch_count'] == 10
    assert len(ledger.rows) == 12


def test_duplicate_scene_rejected_before_any_policy_action_and_attempt_retained(setup, monkeypatch):
    _, case, build, _, _ = setup
    collector, engine, ledger = build()
    monkeypatch.setattr(main_collection, '_capture_scene', lambda *args: dict(
        status='duplicate', scene_fingerprint='e'*64, exact_state_sha256='f'*64,
        duplicate_of={'episode_id': 'earlier', 'split': 'development'}))
    with pytest.raises(MainSourceRejected) as error:
        collector.collect_episode(case)
    assert error.value.reason == 'duplicate_initial_scene' and error.value.before_first_action
    assert len(ledger.rows) == 1 and not engine.calls and engine.runtime.t == 0
    assert (main_collection.ROOT/'sources'/case['case_id']/'rejection.json').exists()
    with pytest.raises(MainSourceRejected):
        collector.collect_episode(case)
    assert len(ledger.rows) == 1, 'Resume must not silently reset a rejected primary again'


def test_initialization_failure_is_the_only_other_preaction_replacement_reason(setup, monkeypatch):
    _, case, build, _, _ = setup
    collector, engine, ledger = build()
    def fail(*args):
        raise RuntimeError('synthetic reset failure')
    monkeypatch.setattr(engine.runtime, 'reset', fail)
    with pytest.raises(MainSourceRejected) as error:
        collector.capture(case)
    assert error.value.reason == 'initialization_failed'
    assert len(ledger.rows) == 1 and not engine.calls


def test_only_ordered_preaction_backup_uses_reserve_capture_and_keeps_primary_slot(setup, monkeypatch):
    config, case, build, _, _ = setup
    backup = dict(case, case_id='disassemble-v3__9101', episode_id='disassemble-v3__9101', env_seed=9101,
                  replacement_of=case['episode_id'])
    config['episode_manifest'].append(backup)
    config['main_collection']['replacement_candidates'] = {case['episode_id']: [backup['episode_id']]}
    config['budget']['stages']['technical_reserve'] = dict(simulator_attempts=100, training_updates=0)
    config['stage_release_scopes']['technical_reserve'] = 'technical_replacements'
    collector, engine, ledger = build(success_at=7)
    with pytest.raises(FileNotFoundError):
        collector.capture(backup)
    real_scene = main_collection._capture_scene
    monkeypatch.setattr(main_collection, '_capture_scene', lambda *args: {'status': 'duplicate'})
    with pytest.raises(MainSourceRejected):
        collector.capture(case)
    monkeypatch.setattr(main_collection, '_capture_scene', real_scene)
    dest = collector.collect_episode(backup)
    row = json.loads((dest/'summary.json').read_text())
    assert row['planned_slot_id'] == case['episode_id'] and row['episode_id'] == backup['episode_id']
    assert ledger.rows[0]['stage'] == 'collect' and ledger.rows[1]['stage'] == 'technical_reserve'
    assert all(attempt['stage'] == 'collect' for attempt in ledger.rows[2:])
    assert len(ledger.rows) == 59  # rejected primary + backup capture + bank + 56 labels


@pytest.mark.parametrize('per_gpu,total', [(1, 8), (2, 16), (4, 32)])
def test_runner_parallelism_is_explicitly_frozen_and_slot_assignment_has_no_overlap(per_gpu, total):
    cases = [dict(episode_id=f'case_{index}') for index in range(37)]
    config = dict(episode_manifest=cases, main_collection=dict(concurrency={'workers_per_gpu': per_gpu},
                  banks={'bank': {'episode_ids': [case['episode_id'] for case in cases]}}))
    assert main_runner.worker_layout(config, total) == (per_gpu, total)
    groups = [main_runner.assigned_slots(config, 'bank', rank, total) for rank in range(total)]
    assigned = [row['episode_id'] for group in groups for row in group]
    assert len(assigned) == len(set(assigned)) == 37
    assert set(assigned) == {case['episode_id'] for case in cases}
    for rank, group in enumerate(groups):
        assert group == cases[rank::total]
    with pytest.raises(ValueError, match='frozen'):
        main_runner.worker_layout(config, total+1)


def test_runner_does_not_choose_unregistered_concurrency():
    for config in ({}, {'main_collection': {'concurrency': {'workers_per_gpu': 3}}}):
        with pytest.raises(ValueError, match='Freeze measured'):
            main_runner.worker_layout(config)


def test_runner_resolves_one_primary_slot_to_registered_backup_without_outcome_filter(setup, monkeypatch):
    config, case, build, _, _ = setup
    backup = dict(case, case_id='disassemble-v3__9101', episode_id='disassemble-v3__9101', env_seed=9101,
                  replacement_of=case['episode_id'])
    config['episode_manifest'].append(backup)
    config['main_collection']['replacement_candidates'] = {case['episode_id']: [backup['episode_id']]}
    config['budget']['stages']['technical_reserve'] = dict(simulator_attempts=100, training_updates=0)
    config['stage_release_scopes']['technical_reserve'] = 'technical_replacements'
    # No legal cut on the accepted backup remains its valid common outcome; it
    # cannot trigger yet another replacement or force a simulated candidate bank.
    collector, _, ledger = build(gate=0., success_at=4)
    actual_scene = main_collection._capture_scene
    def scene(runtime, current, *args):
        if current['episode_id'] == case['episode_id']:
            return {'status': 'duplicate'}
        return actual_scene(runtime, current, *args)
    monkeypatch.setattr(main_collection, '_capture_scene', scene)
    monkeypatch.setattr(main_runner, '_slot_lock', lambda identity: __import__('contextlib').nullcontext())
    result = main_runner.resolve_slot(collector, case)
    assert result['status'] == 'complete' and result['no_cut']
    assert result['planned_slot_id'] == case['episode_id']
    assert result['resolved_episode_id'] == backup['episode_id']
    assert len(result['ordered_rejections']) == 1 and len(ledger.rows) == 2
    assert main_runner.resolve_slot(collector, case) == result
    assert len(ledger.rows) == 2


def test_runner_exhausted_initial_scenes_are_missing_never_fake_failures(setup, monkeypatch):
    _, case, build, _, _ = setup
    collector, engine, ledger = build()
    monkeypatch.setattr(main_collection, '_capture_scene', lambda *args: {'status': 'duplicate'})
    monkeypatch.setattr(main_runner, '_slot_lock', lambda identity: __import__('contextlib').nullcontext())
    row = main_runner.resolve_slot(collector, case)
    assert row['status'] == 'missing_unique_initial_scene' and row['outcome_unknown']
    assert row['resolved_episode_id'] is None and len(ledger.rows) == 1
    assert not engine.calls


@pytest.mark.parametrize('failure_kind', ['initialization_failed', 'duplicate_initial_scene'])
def test_three_identical_reset_errors_stop_wave_but_duplicate_chain_only_reports_missing(setup, monkeypatch, failure_kind):
    config, case, build, _, _ = setup
    backups = [dict(case, case_id=f'disassemble-v3__{seed}', episode_id=f'disassemble-v3__{seed}',
                    env_seed=seed, replacement_of=case['episode_id']) for seed in (9101, 9102)]
    config['episode_manifest'].extend(backups)
    config['main_collection']['replacement_candidates'] = {case['episode_id']: [row['episode_id'] for row in backups]}
    config['budget']['stages']['technical_reserve'] = dict(simulator_attempts=100, training_updates=0)
    config['stage_release_scopes']['technical_reserve'] = 'technical_replacements'
    collector, engine, ledger = build()
    monkeypatch.setattr(main_runner, '_slot_lock', lambda identity: __import__('contextlib').nullcontext())
    if failure_kind == 'initialization_failed':
        def fail(*args):
            raise RuntimeError('synthetic global reset dependency unavailable')
        monkeypatch.setattr(engine.runtime, 'reset', fail)
        with pytest.raises(main_runner.SystemicInitializationFailure) as error:
            main_runner.resolve_slot(collector, case)
        assert len(error.value.failure_chain) == 3
        with pytest.raises(main_runner.SystemicInitializationFailure):
            main_runner.resolve_slot(collector, case)  # Preserved chain is fatal on resume too.
    else:
        monkeypatch.setattr(main_collection, '_capture_scene', lambda *args: {'status': 'duplicate'})
        row = main_runner.resolve_slot(collector, case)
        assert row['status'] == 'missing_unique_initial_scene' and row['outcome_unknown']
    assert len(ledger.rows) == 3 and not engine.calls
    for current in [case]+backups:
        path = main_collection.ROOT/'sources'/current['episode_id']
        main_collection._sealed(path, [config['analysis_approval']['protocol_sha256']])
        rejected = json.loads((path/'rejection.json').read_text())
        assert rejected['outcome_not_observed'] and rejected['control_steps_executed'] == 0
