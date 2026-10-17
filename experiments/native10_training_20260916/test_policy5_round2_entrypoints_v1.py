"""Small synthetic stage/model and actual runner-wiring regression checks."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from . import policy5_round2_prepare_v1 as prepare
from . import policy5_round2_runner_v1 as runner
from . import policy5_round2_audit_v1 as audit
from . import policy5_audit_v1 as original_audit
from . import storage
from .protocol import canonical_hash


@pytest.fixture
def ready(tmp_path):
    files = {}
    for key in ('training_model_seal', 'selected_seal', 'selected_reload_audit', 'model_review'):
        path = tmp_path/key
        path.write_text('synthetic bound metadata')
        files[key] = dict(path=str(path), sha256=storage.sha256(path))
    ids = [f'source{i}' for i in range(100)]
    row = dict(scope=prepare.STAGE, stage=prepare.STAGE,
        simulator_attempts_limit=2100, expected_simulator_attempts=1995,
        optimizer_updates_limit=0, capture_attempts_limit=0,
        initialization_replacements_allowed=False, development_primary_slots=100,
        evaluation_unique_initial_states_per_task=20, reached_cut_sources=95,
        common_no_alarm_sources=5, common_success_sources=4, common_failure_sources=1,
        paired_suffixes_per_state=4, per_arm_outcome_denominator=400,
        arms=list(prepare.POLICY_METHODS), selected_critic=dict(path='A', step=4000, members=4, **files),
        episode_ids=ids, episode_ids_canonical_sha256=canonical_hash(ids),
        statistics=dict(bootstrap_draws=10000, bootstrap_seed=2026091622,
                        ci='percentile95', quantile_method='linear'))
    record = dict(task_id='native10-training-20260916', status='protocol_approved_synthetic',
                  released_scope=[prepare.STAGE], **{prepare.STAGE: row})
    path = tmp_path/'ready.json'
    path.write_text(json.dumps(record))
    return path, record


def test_future_release_exact_selected_model_and_counts(ready):
    path, _ = ready
    _, row, _ = prepare.release(path)
    assert row['selected_critic']['path'] == 'A'
    assert row['selected_critic']['step'] == 4000
    assert row['expected_simulator_attempts'] == 95 + 95*5*4
    assert row['optimizer_updates_limit'] == row['capture_attempts_limit'] == 0


def test_training_only_ready_denied_before_any_bound_input(ready):
    path, record = ready
    record['released_scope'] = ['final_critic_training']
    path.write_text(json.dumps(record))
    with patch.object(prepare, 'checked', side_effect=AssertionError('must reject before access')):
        with pytest.raises(ValueError, match='explicitly release'):
            prepare.inputs('unused', path, 'unused')


@pytest.mark.parametrize('field,value', [
    ('simulator_attempts_limit', 2101), ('optimizer_updates_limit', 1),
    ('capture_attempts_limit', 1), ('initialization_replacements_allowed', True),
    ('paired_suffixes_per_state', 8), ('arms', list(prepare.POLICY_METHODS)+['oldcritic'])])
def test_changed_budget_capture_replacement_or_arms_denied(ready, field, value):
    path, record = ready
    record[prepare.STAGE][field] = value
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        prepare.release(path)


def test_old_b200_or_altered_selected_review_denied(ready):
    path, record = ready
    changed = deepcopy(record)
    changed[prepare.STAGE]['selected_critic'].update(path='B', step=200)
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='A4000'):
        prepare.release(path)
    path.write_text(json.dumps(record))
    Path(record[prepare.STAGE]['selected_critic']['model_review']['path']).write_text('changed')
    with pytest.raises(ValueError):
        prepare.release(path)


@pytest.mark.parametrize('failed_slot', [None, 'e32'])
def test_actual_worker_uses_new_factory_lifecycle_existing_only(tmp_path, monkeypatch, failed_slot):
    root = tmp_path/'outputs'
    for module in (runner, runner.legacy, storage):
        monkeypatch.setattr(module, 'ROOT', root)
    cases = [dict(episode_id=f'e{i}', case_id=f'e{i}', split='development') for i in range(100)]
    config = dict(cpu={'worker_threads':4}, episode_manifest=cases,
        analysis_approval={'protocol_sha256':'a'*64},
        main_collection={'concurrency':{'workers_per_gpu':4},
                         'banks':{'round2':{'episode_ids':[c['episode_id'] for c in cases]}}})
    root.mkdir()
    cp, fp = root/'config.json', root/'freeze.json'
    cp.write_text(json.dumps(config)); fp.write_text('{}')
    args = SimpleNamespace(config=cp, freeze=fp, stage=runner.STAGE,
        bank_version='round2', workers=32, wave_id='synthetic', rank=0)
    calls = []
    monkeypatch.setattr(runner, 'verify_frozen', lambda *a: config)
    monkeypatch.setattr(runner.legacy, '_require_lifecycle', lambda: calls.append('lifecycle'))
    monkeypatch.setattr(runner.legacy, 'resolve_slot', lambda *a: pytest.fail('capture/replacement path'))
    monkeypatch.setattr(runner.legacy, 'create_main_collector', lambda *a, **k: pytest.fail('unguarded factory'))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(set_num_threads=lambda n: None,
        cuda=SimpleNamespace(set_device=lambda n: calls.append('cuda_stub'))))
    collector = SimpleNamespace(engine=SimpleNamespace(close=lambda: calls.append('close')),
                                loaded_critic_identity={'status':'synthetic_only'})
    def factory(cfg, stage, *, bank_version):
        assert stage == 'round2_development_policy' and bank_version == 'round2'
        calls.append('new_guard_factory')
        return collector
    def slot(received, case):
        assert received is collector
        calls.append(case['episode_id'])
        if case['episode_id'] == failed_slot:
            raise RuntimeError('synthetic failure')
        common = case['episode_id'] == 'e96'
        return dict(status='complete', planned_slot_id=case['episode_id'],
            resolved_episode_id=case['episode_id'], ordered_rejections=[],
            actual_branch_count=0 if common else 20, no_cut=common)
    monkeypatch.setattr(runner, 'create_policy_collector', factory)
    monkeypatch.setattr(runner, 'collect_existing_slot', slot)
    if failed_slot:
        with pytest.raises(RuntimeError, match='synthetic failure'):
            runner.worker(args)
    else:
        runner.worker(args)
    assert calls[:3] == ['lifecycle', 'cuda_stub', 'new_guard_factory']
    assert calls[-1] == 'close'
    folder = runner.execution_root(args.stage, args.bank_version, args.wave_id)/'workers/worker_00'
    row = json.loads((folder/('failure.json' if failed_slot else 'status.json')).read_text())
    if failed_slot:
        assert calls[3:-1] == ['e0', 'e32']
        assert row['attempts_not_rolled_back'] and not row['automatic_retry']
        assert not row['source_capture_allowed'] and not row['replacement_allowed']
    else:
        assert calls[3:-1] == ['e0', 'e32', 'e64', 'e96']
        assert row['actual_branch_count'] == 60 and row['source_captures'] == 0
        assert row['no_cut_sources'] == 1 and row['attempted_replacement_records'] == 0


def test_only_round2_stage_before_any_runner_reads(monkeypatch):
    monkeypatch.setattr(runner.legacy, 'verify_frozen', lambda *a: pytest.fail('stage must reject first'))
    for stage in ('round1_development_policy', 'calibration', 'heldout', 'training_final'):
        with pytest.raises(ValueError, match='only round2_development_policy'):
            runner.verify_frozen('unused', 'unused', stage, 'unused', 32)
    assert 'policy5_round2_runner_v1' in (runner.CODE/'run_policy5_round2_gpu_v1.sh').read_text()


def test_auditor_reuses_exact_statistics_and_complete_common_denominator():
    assert audit.summarize is original_audit.summarize
    assert audit.audit_suffix_identities is original_audit.audit_suffix_identities
    rows = [dict(episode_id=f'e{i}', task=f't{i%5}', no_cut=i>=95) for i in range(100)]
    outcomes = np.zeros((100,5,4), dtype=np.uint8)
    outcomes[95:99] = 1
    summary = audit.summarize(outcomes, rows, bootstrap_replicates=20)
    assert summary['overall']['sources'] == 100
    assert summary['overall']['logical_outcomes_per_arm'] == 400
    assert len(summary['comparisons']) == 7
    assert summary['no_cut_common_outcomes']['sources'] == 5
    assert all(x['gain'] == 0 for x in summary['comparisons'].values())
