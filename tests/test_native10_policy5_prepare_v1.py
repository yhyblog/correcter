"""CPU protocol gates only: no engine, policy, optimizer or environment."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.native10_training_20260916 import policy5_prepare_v1 as prepare
from experiments.native10_training_20260916.protocol import canonical_hash


@pytest.fixture
def ready(tmp_path):
    paths = {}
    for name in ('training_model_seal', 'selected_seal', 'selected_reload_audit'):
        path = tmp_path/name;path.write_text('immutable synthetic file')
        paths[name] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    ids = [f'disassemble-v3__{i}' for i in range(100)]
    release = dict(scope=prepare.STAGE, stage=prepare.STAGE, simulator_attempts_limit=2100,
        expected_simulator_attempts=1995, optimizer_updates_limit=0, capture_attempts_limit=0,
        initialization_replacements_allowed=False, development_primary_slots=100,
        evaluation_unique_initial_states_per_task=20, reached_cut_sources=95,
        common_no_alarm_sources=5, common_success_sources=4, common_failure_sources=1,
        paired_suffixes_per_state=4, per_arm_outcome_denominator=400, arms=list(prepare.POLICY_METHODS),
        selected_critic=dict(path='B', step=200, members=4, **paths),
        episode_ids=ids, episode_ids_canonical_sha256=canonical_hash(ids),
        statistics=dict(bootstrap_draws=10000, bootstrap_seed=2026091622, ci='percentile95', quantile_method='linear'))
    record = dict(task_id='native10-training-20260916', status='protocol_approved_test',
                  released_scope=[prepare.STAGE], **{prepare.STAGE: release})
    path = tmp_path/'NATIVE10_ANALYSIS_READY.json';path.write_text(json.dumps(record))
    return path, record


def test_released_exact_resources_and_model(ready):
    path, record = ready
    _, release, references = prepare.release(path)
    assert release['selected_critic']['step'] == 200
    assert release['optimizer_updates_limit'] == release['capture_attempts_limit'] == 0
    assert not references


@pytest.mark.parametrize('field,value', [('simulator_attempts_limit', 2101), ('optimizer_updates_limit', 1),
    ('capture_attempts_limit', 1), ('initialization_replacements_allowed', True), ('paired_suffixes_per_state', 8),
    ('scope', 'round1_critic_training'), ('stage', 'round1_labels')])
def test_changed_scope_budget_or_sampling_denied(ready, field, value):
    path, record = ready;record[prepare.STAGE][field] = value;path.write_text(json.dumps(record))
    with pytest.raises(ValueError):prepare.release(path)


def test_v6_cannot_release_policy_before_input_access(ready):
    path, record = ready;record['released_scope'] = ['round1_critic_training'];path.write_text(json.dumps(record))
    with patch.object(prepare, 'checked', side_effect=AssertionError('must fail before model bindings')):
        with pytest.raises(ValueError):prepare.release(path)


def test_only_selected_checkpoint_and_exact_manifest(ready):
    path, original = ready
    for edit in ('step', 'ids', 'seed'):
        record = deepcopy(original)
        if edit == 'step':record[prepare.STAGE]['selected_critic']['step'] = 2400
        elif edit == 'ids':record[prepare.STAGE]['episode_ids'][0] = record[prepare.STAGE]['episode_ids'][1]
        else:record[prepare.STAGE]['statistics']['bootstrap_seed'] += 1
        path.write_text(json.dumps(record))
        with pytest.raises(ValueError):prepare.release(path)


def test_changed_bound_model_file_rejected(ready):
    path, record = ready
    Path(record[prepare.STAGE]['selected_critic']['selected_seal']['path']).write_text('changed')
    with pytest.raises(ValueError):prepare.release(path)


def test_empty_or_old_generic_cpu_evidence_cannot_freeze(tmp_path):
    with pytest.raises(ValueError, match='omits actual'):prepare.cpu_checks([])
    result = dict(status='passed', returncode=0, code_sha256_before={}, code_sha256_after={},
                  model_calls=0, simulator_calls=0, optimizer_updates=0)
    (tmp_path/'complete.json').write_text('{}');(tmp_path/'result.json').write_text(json.dumps(result))
    (tmp_path/'pytest.log').write_text('31 passed')
    with patch.object(prepare, 'sealed_directory', return_value={}):
        with pytest.raises(ValueError, match='fixed code'):prepare.cpu_checks([tmp_path])


def test_historical_dataset_audit_required_for_original_source_bindings(tmp_path):
    old = dict(episode_manifest=[]);ids = ['source0']
    audit = dict(status='passed', purpose='development', dataset_seal_sha256='a'*64,
        manifest_sha256=canonical_hash([]), episode_ids=ids, missing_artifacts=[], completed_collections_only=False,
        checks={key: True for key in ('source_seals', 'bank_seals', 'scene_identity', 'replacement_chain', 'complete_labels')},
        artifacts=[dict(path='/original/source/complete.json', sha256='b'*64)],
        slot_resolutions=[dict(planned_slot_id='source0', resolved_episode_id='source0', preceding_rejections=[])])
    path = tmp_path/'input_audit.json';path.write_text(json.dumps(audit))
    binding = dict(input_audit_path=str(path), input_audit_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), seal_sha256='a'*64)
    artifacts, resolved = prepare.historical_audit(binding, old, ids)
    assert artifacts['/original/source/complete.json'] == 'b'*64 and set(resolved) == set(ids)
    changed = deepcopy(audit);changed['purpose'] = 'train';path.write_text(json.dumps(changed))
    binding['input_audit_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='Original complete development'):
        prepare.historical_audit(binding, old, ids)
