"""Synthetic CPU tests: freeze metadata only, never real data/PCA/optimizers."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from . import prepare_fit, storage, training_pipeline
from .artifact_loader import AUDIT_SCHEMA, CHECK_NAMES
from .protocol import canonical_hash, pending_protocol, protocol_digest, require_stage_budget, validate_protocol


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def hashes(directory):
    return {str(path.relative_to(directory)): storage.sha256(path)
            for path in directory.rglob('*') if path.is_file()}


def make_ready(directory, scopes):
    directory.mkdir(parents=True, exist_ok=True)
    task, review = directory/'NATIVE10_TRAINING_TASK.md', directory/'NATIVE10_SYNTHETIC_REVIEW.md'
    task.write_text('Synthetic CPU fixture; never real authorization.\n')
    review.write_text('Synthetic metadata review only.\n')
    value = dict(task_id='native10-training-20260916', status='approved', released_scope=list(scopes),
        task_document='coordination/'+task.name, task_document_sha256=storage.sha256(task),
        protocol_review='coordination/'+review.name, protocol_review_sha256=storage.sha256(review),
        new_simulator_attempts_hard_limit=50000, p0_attempts_hard_limit=600)
    path = directory/'NATIVE10_ANALYSIS_READY.json'
    put(path, value)
    return path


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root = tmp_path/'outputs'
    monkeypatch.setattr(storage, 'ROOT', root)
    code = tmp_path/'synthetic_code'; code.mkdir()
    put(code/'training_design_v2.json', dict(schema_version=2, task_id='native10-training-20260916',
        status='synthetic_pending', sources={}, approved_parameters={'loss': {'bce': 1., 'gain': 1., 'pair': .5}},
        candidate_schema={'slots': ['a0', 'xyz_positive'], 'clearance': .05},
        old_weight_import={'read_only': True, 'files': {'mock_checkpoint': 'a'*64}},
        budget={'training_update_total': 51200}, execution_gate={}, implementation_status={}))
    (code/'training_implementation.py').write_text('# CPU fixture only\n')
    monkeypatch.setattr(prepare_fit, 'CODE', code)
    code_files = {str(code/'training_implementation.py'): storage.sha256(code/'training_implementation.py')}
    monkeypatch.setattr(training_pipeline, 'training_code_files', Mock(return_value=code_files))
    for name in ('preflight', 'run', 'fit_member', 'fit_train_preprocessing',
                 'load_audited_dataset', 'initialize_model', 'FrozenSelector'):
        monkeypatch.setattr(training_pipeline, name, Mock(side_effect=AssertionError('No data/PCA/model/optimizer execution')))
    monkeypatch.setattr(np, 'load', Mock(side_effect=AssertionError('No feature/outcome array reads')))
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    base = root/'main_protocols/base_v1/config.json'
    old_ready = make_ready(base.parent/'coordination', ['round1_native10_local_labels'])
    cfg = pending_protocol()
    cfg.update(status='frozen', replicates=4, cpu={'worker_threads': 2, 'critic_threads': 2},
        episode_manifest=[dict(episode_id=f'disassemble-v3__{index}', case_id=f'disassemble-v3__{index}',
            task='disassemble-v3', env_seed=index, split=split, round=1 if split == 'train' else None)
            for index, split in ((1, 'train'), (2, 'development'))],
        budget=dict(hard_total=50000, training_update_total=51200, count_failures=True, count_retries=True,
            stages={'round1_labels': {'simulator_attempts': 23200, 'training_updates': 0},
                    'training_round1': {'simulator_attempts': 0, 'training_updates': 19200}}),
        stage_release_scopes={'round1_labels': 'round1_native10_local_labels', 'training_round1': 'not_released_training_round1'},
        main_collection={'banks': {'labels': {'stage': 'round1_labels'}}},
        analysis_ready={'path': str(old_ready), 'sha256': storage.sha256(old_ready)})
    task = old_ready.parent/'NATIVE10_TRAINING_TASK.md'
    cfg['analysis_approval'] = dict(status='approved', approved_by='analysis', document_path=str(task),
        document_sha256=storage.sha256(task), protocol_sha256=protocol_digest(cfg))
    put(base, cfg); validate_protocol(cfg, require_runnable=True)
    put(base.with_name('freeze.json'), dict(config_sha256=storage.sha256(base), files={str(base): storage.sha256(base)}))
    current_ready = make_ready(tmp_path/'live/coordination', ['round1_fit_preflight'])
    decision = prepare_fit.read(current_ready)
    decision['round1_fit_preflight'] = dict(stage='round1_fit_preflight', scope='round1_fit_preflight',
        simulator_attempts_limit=0, optimizer_updates_limit=0, training_updates=0,
        input_config_sha256=storage.sha256(base), input_freeze_sha256=storage.sha256(base.with_name('freeze.json')))
    put(current_ready, decision)
    bindings, audit_paths = {}, {}
    for purpose in ('train', 'development'):
        dataset = root/'datasets'/purpose; dataset.mkdir(parents=True)
        (dataset/'features.npy').write_bytes(b'not a real array; metadata-only preparation must not deserialize')
        storage.seal(dataset)
        audit_dir = root/'dataset_audits'/purpose
        audit = dict(schema=AUDIT_SCHEMA, status='passed', purpose=purpose, manifest_sha256=canonical_hash(cfg['episode_manifest']),
            dataset_seal_sha256=storage.sha256(dataset/'complete.json'),
            protocol_sha256=cfg['analysis_approval']['protocol_sha256'], checks={name: True for name in CHECK_NAMES})
        put(audit_dir/'input_audit.json', audit); storage.seal(audit_dir)
        binding = dict(path=str(dataset), seal_sha256=storage.sha256(dataset/'complete.json'),
            input_audit_path=str(audit_dir/'input_audit.json'), input_audit_sha256=storage.sha256(audit_dir/'input_audit.json'),
            input_protocol_sha256=cfg['analysis_approval']['protocol_sha256'])
        bindings[purpose] = root/'bindings'/f'{purpose}.json'; put(bindings[purpose], binding)
        audit_paths[purpose] = audit_dir/'input_audit.json'
    return SimpleNamespace(root=root, code=code, base=base, cfg=cfg, ready=current_ready,
                           bindings=bindings, audits=audit_paths, tmp=tmp_path)


def freeze(fixture, **changes):
    arguments = dict(base_config=fixture.base, ready_path=fixture.ready,
        train_binding=fixture.bindings['train'], development_binding=fixture.bindings['development'],
        mode='preflight', version='new_v1')
    arguments.update(changes)
    return prepare_fit.freeze(**arguments)


def release(fixture, scopes):
    value = prepare_fit.read(fixture.ready); value['released_scope'] = scopes; put(fixture.ready, value)


def make_preflight(fixture, **updates):
    path = fixture.root/'fit_preflight/round1/cpu_v1'
    design = path/'training_design.json'
    put(design, prepare_fit.read(fixture.code/'training_design_v2.json'))
    result = dict(role='native10_fit_preflight_zero_updates', status='passed', optimizer_updates=0, phase='round1',
        design={'path': str(design), 'sha256': storage.sha256(design)},
        manifest_sha256=canonical_hash(fixture.cfg['episode_manifest']), seed_namespace=fixture.cfg['seed_namespace'],
        dataset_bindings={purpose: prepare_fit.read(path) for purpose, path in fixture.bindings.items()},
        code_files=training_pipeline.training_code_files(), stop_after={'A': 2400, 'B': 2400},
        collection=dict(config_path=str(fixture.base), config_sha256=storage.sha256(fixture.base),
            freeze_path=str(fixture.base.with_name('freeze.json')),
            freeze_sha256=storage.sha256(fixture.base.with_name('freeze.json'))))
    result.update(updates)
    put(path/'result.json', result); storage.seal(path)
    binding = fixture.root/'bindings/preflight.json'
    put(binding, dict(path=str(path), seal_sha256=storage.sha256(path/'complete.json')))
    return binding, path


@pytest.mark.parametrize('mode,scopes', [
    ('preflight', ['round1_critic_training']), ('fit', ['round1_fit_preflight']),
    ('preflight', ['cpu_protocol_checks']), ('fit', ['round1_native10_local_labels'])])
def test_missing_exact_scope_rejects_before_base_or_dataset_reads(fixture, monkeypatch, mode, scopes):
    release(fixture, scopes)
    original_read = prepare_fit.read
    def read_ready_only(path):
        assert Path(path) == fixture.ready, 'Unreleased preparation attempted base/data read'
        return original_read(path)
    monkeypatch.setattr(prepare_fit, 'read', read_ready_only)
    monkeypatch.setattr(prepare_fit, 'dataset_binding', Mock(side_effect=AssertionError('Dataset read before scope')))
    with pytest.raises(ValueError, match='has not released'):
        freeze(fixture, mode=mode)
    assert not (fixture.root/'fit_protocols').exists()


def test_preflight_freeze_preserves_inputs_and_self_contained_ready(fixture):
    before_base, before_ready = hashes(fixture.base.parent), hashes(fixture.ready.parent)
    original_design = fixture.code/'training_design_v2.json'
    original_design_sha = storage.sha256(original_design)
    result = freeze(fixture); cfg = prepare_fit.read(result)
    assert hashes(fixture.base.parent) == before_base and hashes(fixture.ready.parent) == before_ready
    assert Path(cfg['analysis_ready']['path']).parent == result.parent/'coordination'
    assert Path(cfg['analysis_approval']['document_path']).parent == result.parent/'coordination'
    assert (result.parent/'coordination/NATIVE10_ANALYSIS_READY.json').read_bytes() == fixture.ready.read_bytes()
    assert cfg['main_collection']['banks']['labels']['bank_protocol_sha256'] == fixture.cfg['analysis_approval']['protocol_sha256']
    assert cfg['stage_release_scopes']['training_round1'] == 'not_released_training_round1'
    assert cfg['budget']['stages']['round1_fit_preflight'] == dict(simulator_attempts=0, training_updates=0)
    assert cfg['stage_release_scopes']['round1_fit_preflight'] == 'round1_fit_preflight'
    assert cfg['training_pipeline']['collection'] == dict(config_path=str(fixture.base),
        config_sha256=storage.sha256(fixture.base), freeze_path=str(fixture.base.with_name('freeze.json')),
        freeze_sha256=storage.sha256(fixture.base.with_name('freeze.json')))
    frozen_design = Path(cfg['training_pipeline']['design']['path'])
    assert frozen_design.parent == result.parent and frozen_design.name == 'training_design.json'
    assert storage.sha256(frozen_design) == cfg['training_pipeline']['design']['sha256']
    assert storage.sha256(original_design) == original_design_sha
    for field in ('approved_parameters', 'candidate_schema', 'old_weight_import', 'budget'):
        assert prepare_fit.read(frozen_design)[field] == prepare_fit.read(original_design)[field]
    with pytest.raises(ValueError, match='released'):
        require_stage_budget(cfg, 'training_round1', resource='training_updates')
    release(fixture, ['not_a_release'])
    validate_protocol(cfg, require_runnable=True)
    frozen = prepare_fit.read(result.parent/'freeze.json')
    assert frozen['optimizer_updates'] == frozen['simulator_calls'] == 0
    assert frozen['full_dataset_audit_required_at_execution'] is True
    assert frozen['config_sha256'] == storage.sha256(result)
    assert all(storage.sha256(path) == digest for path, digest in frozen['files'].items())


@pytest.mark.parametrize('missing_check', ['scene_identity', 'replacement_chain'])
def test_missing_scene_or_replacement_audit_cannot_bind(fixture, missing_check):
    path = fixture.audits['train']; audit = prepare_fit.read(path)
    audit['checks'].pop(missing_check); put(path, audit)
    binding = prepare_fit.read(fixture.bindings['train'])
    binding['input_audit_sha256'] = storage.sha256(path); put(fixture.bindings['train'], binding)
    with pytest.raises(ValueError):
        freeze(fixture)
    assert not (fixture.root/'fit_protocols').exists()


@pytest.mark.parametrize('field,value', [('purpose', 'heldout'), ('manifest_sha256', 'f'*64),
                                       ('dataset_seal_sha256', 'f'*64), ('protocol_sha256', 'f'*64)])
def test_wrong_dataset_metadata_bindings_rejected(fixture, field, value):
    path = fixture.audits['train']; audit = prepare_fit.read(path); audit[field] = value; put(path, audit)
    binding = prepare_fit.read(fixture.bindings['train'])
    binding['input_audit_sha256'] = storage.sha256(path); put(fixture.bindings['train'], binding)
    with pytest.raises(ValueError):
        freeze(fixture)


def test_existing_version_cannot_be_overwritten(fixture):
    result = freeze(fixture); before = hashes(result.parent)
    with pytest.raises(FileExistsError):
        freeze(fixture)
    assert hashes(result.parent) == before


def test_fit_requires_distinct_sealed_preflight(fixture):
    release(fixture, ['round1_critic_training'])
    with pytest.raises(ValueError, match='zero-update preflight'):
        freeze(fixture, mode='fit')
    assert not (fixture.root/'fit_protocols').exists()


@pytest.mark.parametrize('change', [dict(optimizer_updates=1), dict(status='failed'), dict(phase='final'), dict(role='other')])
def test_fit_rejects_nonzero_or_wrong_preflight(fixture, change):
    release(fixture, ['round1_critic_training'])
    binding, _ = make_preflight(fixture, **change)
    with pytest.raises(ValueError):
        freeze(fixture, mode='fit', preflight_binding=binding)


def test_fit_binds_passed_preflight_and_releases_only_fit_stage(fixture):
    release(fixture, ['round1_critic_training'])
    binding, source = make_preflight(fixture); before = hashes(source)
    result = freeze(fixture, mode='fit', preflight_binding=binding); cfg = prepare_fit.read(result)
    assert hashes(source) == before
    assert cfg['training_pipeline']['preflight']['round1'] == prepare_fit.read(binding)
    assert cfg['training_pipeline']['design'] == prepare_fit.read(source/'result.json')['design']
    assert cfg['stage_release_scopes']['training_round1'] == 'round1_critic_training'
    require_stage_budget(cfg, 'training_round1', resource='training_updates')
    with pytest.raises(ValueError, match='released'):
        require_stage_budget(cfg, 'round1_labels')


def test_fit_rejects_result_modified_outside_original_seal(fixture):
    release(fixture, ['round1_critic_training'])
    binding, source = make_preflight(fixture, optimizer_updates=1)
    result = prepare_fit.read(source/'result.json'); result['optimizer_updates'] = 0
    put(source/'result.json', result)
    with pytest.raises(ValueError):
        freeze(fixture, mode='fit', preflight_binding=binding)


def test_dataset_incomplete_seal_cannot_bind_with_matching_outer_sha(fixture):
    binding = prepare_fit.read(fixture.bindings['train']); dataset = Path(binding['path'])
    seal = prepare_fit.read(dataset/'complete.json'); seal['status'] = 'incomplete'; put(dataset/'complete.json', seal)
    binding['seal_sha256'] = storage.sha256(dataset/'complete.json')
    audit = prepare_fit.read(fixture.audits['train']); audit['dataset_seal_sha256'] = binding['seal_sha256']
    put(fixture.audits['train'], audit); binding['input_audit_sha256'] = storage.sha256(fixture.audits['train'])
    put(fixture.bindings['train'], binding)
    with pytest.raises(ValueError):
        freeze(fixture)


def test_preflight_cannot_consume_another_preflight(fixture):
    binding, _ = make_preflight(fixture)
    with pytest.raises(ValueError, match='does not consume'):
        freeze(fixture, preflight_binding=binding)


@pytest.mark.parametrize('version', ['../old', '/absolute', 'bad/slash'])
def test_unsafe_versions_rejected_before_input_reads(fixture, monkeypatch, version):
    monkeypatch.setattr(prepare_fit, 'read', Mock(side_effect=AssertionError('Read for unsafe output path')))
    with pytest.raises(ValueError, match='safe NEW version'):
        freeze(fixture, version=version)


def test_ready_document_changes_rejected_before_version_creation(fixture):
    (fixture.ready.parent/'NATIVE10_SYNTHETIC_REVIEW.md').write_text('changed')
    with pytest.raises(ValueError, match='SHA mismatch'):
        freeze(fixture)
    assert not (fixture.root/'fit_protocols').exists()


@pytest.mark.parametrize('field,value', [('input_config_sha256', 'f'*64), ('input_freeze_sha256', 'f'*64),
    ('simulator_attempts_limit', 1), ('optimizer_updates_limit', 1), ('training_updates', 1),
    ('scope', 'round1_critic_training')])
def test_preflight_ready_collection_or_zero_budget_mismatch_rejects_before_data(fixture, monkeypatch, field, value):
    ready = prepare_fit.read(fixture.ready); ready['round1_fit_preflight'][field] = value; put(fixture.ready, ready)
    monkeypatch.setattr(prepare_fit, 'dataset_binding', Mock(side_effect=AssertionError('Data read before valid zero gate')))
    with pytest.raises(ValueError, match='exact zero resources'):
        freeze(fixture)


def test_collection_freeze_must_bind_original_config(fixture, monkeypatch):
    original = prepare_fit.read(fixture.base.with_name('freeze.json'))
    original['config_sha256'] = 'f'*64; put(fixture.base.with_name('freeze.json'), original)
    monkeypatch.setattr(prepare_fit, 'dataset_binding', Mock(side_effect=AssertionError('Read before collection binding')))
    with pytest.raises(ValueError, match='collection freeze'):
        freeze(fixture)


@pytest.mark.parametrize('field,value', [('collection', {}), ('dataset_bindings', {}), ('code_files', {}),
    ('stop_after', {'A': 200, 'B': 200}), ('seed_namespace', 'other'), ('manifest_sha256', 'f'*64)])
def test_fit_cannot_reuse_preflight_with_changed_source_or_training_identity(fixture, field, value):
    release(fixture, ['round1_critic_training'])
    binding, _ = make_preflight(fixture, **{field: value})
    with pytest.raises(ValueError, match='exact preflight input/code/design/seed identity'):
        freeze(fixture, mode='fit', preflight_binding=binding)
    assert not (fixture.root/'fit_protocols').exists()
