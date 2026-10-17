"""Synthetic metadata only; never read real calibration or instantiate a model."""
from copy import deepcopy
import json

import pytest

from . import final_selection_v1 as selection


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    monkeypatch.setattr(selection.storage, 'ROOT', tmp_path/'workflow')
    root = selection.storage.ROOT
    root.mkdir()
    evidence = root/'known_completed_evidence.json'
    selection.storage.dump(evidence, {'status': 'passed', 'net': 14})
    science = dict(source_horizon=10, prefix_horizon=10, suffix_horizon=10,
        control_budget=300, gate_threshold=.05, guidance={'alpha': 10},
        matching={'xyz_rms': .05, 'all_directions': ['velocity', 'direct', 'post', 'reverse', 'random']},
        command_semantics='raw native a0 + feasible matched delta', seed_namespace='synthetic')
    payload = dict(schema=selection.SCHEMA, status='pending_selection_seal',
        stage=selection.STAGE, scope=selection.SCOPE, method='post', post_enabled_on_alarm=True,
        primary_comparison='post_minus_alarm_replan10', physical_methods=list(selection.ARMS),
        scientific_parameters=science, matching=deepcopy(science['matching']),
        guidance=deepcopy(science['guidance']), command_semantics=science['command_semantics'],
        calibration_evidence={'result_review': selection.reference(evidence),
                              'completion_review': selection.reference(evidence)},
        selection_basis={'source_denominator': 100, 'logical_outcomes_per_arm': 200,
                         'net_success_difference': 14, 'mean_source_difference': .07},
        expected_directory=str(selection.expected_directory()), heldout_release=False,
        **selection.ZERO)
    monkeypatch.setattr(selection, 'build_payload', lambda **kwargs: deepcopy(payload))
    cpu = root/'preparation/cpu_test'
    cpu.mkdir(parents=True)
    coverage = selection.code_files()
    selection.storage.dump(cpu/'result.json', dict(status='passed', returncode=0,
        code_sha256_before=coverage, code_sha256_after=coverage, **selection.ZERO))
    selection.storage.dump(cpu/'command.json', {'synthetic_test_evidence': True})
    selection.storage.seal(cpu, role='synthetic_cpu_evidence')
    binding = selection.prepare_pending()
    ready = dict(task_id='native10-training-20260916', status='approved',
        released_scope=[selection.SCOPE],
        **{selection.STAGE: selection.ready_contract(binding, [cpu])})
    ready_path = root/'NATIVE10_ANALYSIS_READY.json'
    selection.storage.dump(ready_path, ready)
    return dict(root=root, cpu=cpu, binding=binding, ready=ready, ready_path=ready_path,
                payload=payload, evidence=evidence)


def write_ready(fixture, ready):
    selection.storage.dump(fixture['ready_path'], ready, exclusive=False)


def test_pending_is_explicitly_not_a_selection(synthetic):
    s = synthetic
    assert selection.validate_pending_binding(s['binding']) == s['payload']
    assert not selection.expected_directory().exists()
    assert s['binding']['status'] == 'pending_selection_seal'
    with pytest.raises((KeyError, ValueError)):
        selection.validate_selection_binding(s['binding'])


def test_old_scope_denied_before_inputs(synthetic, monkeypatch):
    ready = deepcopy(synthetic['ready']); ready['released_scope'] = ['calibration']
    write_ready(synthetic, ready)
    def unexpected(*args, **kwargs):
        pytest.fail('Unreleased entry inspected pending inputs')
    monkeypatch.setattr(selection, 'validate_pending_binding', unexpected)
    with pytest.raises(ValueError, match='explicitly released'):
        selection.seal_selection({}, synthetic['ready_path'], [])
    assert not selection.expected_directory().exists()


@pytest.mark.parametrize('key', ['simulator_attempts_limit', 'optimizer_updates_limit',
    'training_updates', 'model_calls_limit', 'pca_fits_limit'])
def test_nonzero_resource_denied(synthetic, key):
    ready = deepcopy(synthetic['ready']); ready[selection.STAGE][key] = 1
    write_ready(synthetic, ready)
    with pytest.raises(ValueError, match='zero resources'):
        selection.seal_selection(synthetic['binding'], synthetic['ready_path'], [synthetic['cpu']])


def test_tampered_ready_identity_denied(synthetic):
    ready = deepcopy(synthetic['ready'])
    ready[selection.STAGE]['pending']['payload']['sha256'] = '0'*64
    write_ready(synthetic, ready)
    with pytest.raises(ValueError, match='exact payload'):
        selection.seal_selection(synthetic['binding'], synthetic['ready_path'], [synthetic['cpu']])
    assert not selection.expected_directory().exists()


def test_matching_or_radius_dependency_cannot_change(synthetic):
    payload = deepcopy(synthetic['payload'])
    payload['matching']['xyz_rms'] = .1
    with pytest.raises(ValueError, match='scientific payload'):
        selection.validate_payload(payload)
    payload = deepcopy(synthetic['payload'])
    payload['scientific_parameters']['matching']['all_directions'] = ['post']
    with pytest.raises(ValueError, match='scientific payload'):
        selection.validate_payload(payload)


def test_complete_metadata_seal_roundtrip_and_double_write_denied(synthetic):
    s = synthetic
    binding = selection.seal_selection(s['binding'], s['ready_path'], [s['cpu']])
    result = selection.validate_selection_binding(binding)
    assert result['status'] == 'sealed'
    assert result['heldout_release'] is False
    assert all(result[k] == 0 for k in selection.ZERO)
    assert result['scientific_parameters'] == s['payload']['scientific_parameters']
    assert result['selection_basis']['net_success_difference'] == 14
    assert selection.load_selection(binding) == result
    assert result['authorization_reference_count'] > 0
    with pytest.raises(FileExistsError):
        selection.seal_selection(s['binding'], s['ready_path'], [s['cpu']])


def test_actual_seal_dependency_tamper_rejected(synthetic):
    s = synthetic
    binding = selection.seal_selection(s['binding'], s['ready_path'], [s['cpu']])
    s['evidence'].write_text(json.dumps({'status': 'changed'}))
    with pytest.raises(ValueError, match='SHA mismatch'):
        selection.validate_selection_binding(binding)


def test_ready_reference_inventory_includes_relative_and_nested(synthetic, monkeypatch):
    s = synthetic
    monkeypatch.setattr(selection.storage, 'PACKAGE', s['root'])
    doc = s['root']/'decision.md'; doc.write_text('synthetic approved decision')
    ready = deepcopy(s['ready'])
    ready['nested_provenance'] = {'decision_path': 'decision.md',
                                'decision_sha256': selection.storage.sha256(doc)}
    write_ready(s, ready)
    binding = selection.seal_selection(s['binding'], s['ready_path'], [s['cpu']])
    result = selection.validate_selection_binding(binding)
    frozen = selection.read(result['dependency_freeze']['path'])
    assert str(doc) in frozen['files']
    inventory = selection.read(result['authorization_context']['calibration_preparation']['authorization_inventory']['path'])
    matches = [x for x in inventory['references'] if x['original_path'] == str(doc)]
    assert len(matches) == 1
    assert selection.storage.sha256(matches[0]['snapshot_path']) == selection.storage.sha256(doc)
