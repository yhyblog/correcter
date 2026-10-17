"""Small synthetic metadata-contract checks; no real model or source access."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from . import policy5_round2_pending_v1 as module


@pytest.fixture
def metadata(tmp_path, monkeypatch):
    root = tmp_path/'outputs'; root.mkdir()
    monkeypatch.setattr(module.storage, 'PACKAGE', tmp_path)
    monkeypatch.setattr(module.storage, 'ROOT', root)
    ids = [f'{module.TASKS[index % 5]}__{2026111600+index}' for index in range(100)]
    row = dict(scope='round1_development_policy', stage='round1_development_policy',
        simulator_attempts_limit=2100, expected_simulator_attempts=1995, optimizer_updates_limit=0,
        capture_attempts_limit=0, initialization_replacements_allowed=False,
        development_primary_slots=100, evaluation_unique_initial_states_per_task=20,
        reached_cut_sources=95, common_no_alarm_sources=5, common_success_sources=4,
        common_failure_sources=1, paired_suffixes_per_state=4, per_arm_outcome_denominator=400,
        arms=module.ARMS, episode_ids=ids, episode_ids_canonical_sha256=module.IDS_SHA,
        statistics=dict(bootstrap_draws=10000, bootstrap_seed=2026091622, ci='percentile95',
                        quantile_method='linear'),
        guard_cpu_evidence={'old': 'must not become new evidence'},
        selected_critic=dict(path='B', step=200),
        development_dataset={'original': 'unchanged'}, future_stages_locked=['old'])
    references = {}
    for key, value in dict(decision={'preparation_only': True}, model_review={'status': 'passed'},
        historical_ready=dict(version=7, round1_development_policy=row),
        historical_policy_config={'original': True}, historical_inputs={'status': 'complete'}).items():
        path = tmp_path/(key+'.json');path.write_text(json.dumps(value))
        references[key] = (path.name, module.storage.sha256(path))
    monkeypatch.setattr(module, 'REFERENCES', references)
    sources = [dict(case=dict(episode_id=identity, round=None, split='development'),
                    cuts=[15] if index < 95 else [], common_outcome=None if index < 95 else index < 99)
               for index, identity in enumerate(ids)]
    original_binding = dict(old_collection={'bank_version': 'round1_labels_v1'},
                            source_bindings={identity: {'original': True} for identity in ids})
    critic = dict(path='A', step=4000, members=4, model_review={'path': 'review', 'sha256': 'a'*64})
    trained = dict(path='final/final_fit_v1', seal_sha256=module.MODEL_SEAL,
        selected_seal_sha256=module.SELECTED_SEAL, selected_reload_audit_sha256='b'*64,
        model_review=critic['model_review'])
    monkeypatch.setattr(module, '_original_inputs', lambda *args: (original_binding, sources, ids[:95]))
    monkeypatch.setattr(module, '_selected', lambda *args: (critic, trained))
    return dict(root=root, row=row, references=references, sources=sources,
                original_binding=original_binding, trained=trained)


def test_pending_preserves_sources_and_never_releases(metadata):
    out = module.pending(version='synthetic')
    folder = Path(out['path'])
    result = module.read(folder/'result.json');contract = module.read(out['ready_contract_path'])
    binding = module.read(out['binding_path'])
    assert out['status'] == 'pending' and out['runnable'] is False
    assert result['released_scope'] == [] and result['historical_ready_is_authorization'] is False
    assert {result[key] for key in ('simulator_calls', 'optimizer_updates', 'model_calls')} == {0}
    assert not (folder/'config.json').exists() and not (folder/'NATIVE10_ANALYSIS_READY.json').exists()
    assert contract['stage'] == contract['scope'] == module.STAGE
    assert contract['status'] == 'pending_engineering_no_release'
    assert contract['guard_cpu_evidence'] is None
    assert contract['selected_critic']['path'] == 'A' and contract['selected_critic']['step'] == 4000
    assert contract['statistics'] == metadata['row']['statistics']
    assert contract['development_dataset'] == metadata['row']['development_dataset']
    assert binding['schema'] == module.SCHEMA
    assert binding['old_collection'] == metadata['original_binding']['old_collection']
    assert binding['source_bindings'] == metadata['original_binding']['source_bindings']
    assert binding['selected_training'] == metadata['trained']
    assert module.read(out['sources_path']) == metadata['sources']
    assert module._seal(folder, out['seal_sha256'], verify_files=True)['runnable'] is False
    assert module.read(folder/'provenance.json')['references']['historical_ready']['sha256'] == metadata['references']['historical_ready'][1]
    with pytest.raises(FileExistsError):
        module.pending(version='synthetic')


def test_changed_review_rejected_before_output(metadata):
    Path(module.storage.PACKAGE/metadata['references']['model_review'][0]).write_text('{}')
    with pytest.raises(ValueError, match='SHA changed'):
        module.pending(version='changed')
    assert not (metadata['root']/'policy_preparations/changed').exists()


@pytest.mark.parametrize('field,value', [('optimizer_updates_limit', 1), ('capture_attempts_limit', 1),
                                       ('paired_suffixes_per_state', 8)])
def test_altered_historical_contract_rejected(metadata, field, value):
    path = module.storage.PACKAGE/metadata['references']['historical_ready'][0]
    original = module.read(path);original['round1_development_policy'][field] = value
    path.write_text(json.dumps(original))
    module.REFERENCES['historical_ready'] = (path.name, module.storage.sha256(path))
    with pytest.raises(ValueError, match='original five-arm'):
        module.pending(version='changed')


def test_current_ready_cannot_replace_historical_template(metadata):
    path = module.storage.PACKAGE/metadata['references']['historical_ready'][0]
    original = module.read(path);original['version'] = 10
    path.write_text(json.dumps(original))
    module.REFERENCES['historical_ready'] = (path.name, module.storage.sha256(path))
    with pytest.raises(ValueError, match='historical READY v7'):
        module.pending(version='changed')


def test_unsafe_output_path_rejected_before_access(metadata):
    with pytest.raises(ValueError, match='isolated'):
        module.pending(version='../models')


def test_metadata_seal_checks_byte_identity_without_deserialization(tmp_path):
    path = tmp_path/'opaque.pt';path.write_bytes(b'not a model; only bytes')
    assert module.checked(path, module.storage.sha256(path)) == path
    with pytest.raises(ValueError, match='SHA changed'):
        module.checked(path, '0'*64)
