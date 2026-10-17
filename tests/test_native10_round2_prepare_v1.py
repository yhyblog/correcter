"""Round2 CPU preparation: immutable identity, fallback and zero-work gates."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from unittest.mock import patch
import pytest
from experiments.native10_training_20260916 import round2_prepare_v1 as prepare
from experiments.native10_training_20260916.main_collection import select_cut
from experiments.native10_training_20260916.protocol import canonical_hash

@pytest.fixture
def original():
    return prepare.read(prepare.storage.ROOT/'main_protocols/round1_v1/config.json')

def test_primary_identity(original):
    rows = prepare.original_slots(original)
    assert len(rows) == 300 and not any(r.get('replacement_of') for r in rows)
    assert canonical_hash([r['episode_id'] for r in rows]) == '9c1891d17b8c438162c4c2ab4ba245864e743b42cd4aa8b813baf298c922f78a'

@pytest.mark.parametrize('change', ['reordered', 'seed', 'split', 'cut'])
def test_identity_mutations_rejected(original, change):
    rows = prepare.original_slots(original)
    if change == 'reordered':
        a, b = [original['episode_manifest'].index(r) for r in rows[:2]]
        original['episode_manifest'][a], original['episode_manifest'][b] = original['episode_manifest'][b], original['episode_manifest'][a]
    elif change == 'seed': rows[0]['env_seed'] += 1
    elif change == 'split': rows[0]['split'] = 'development'
    else: rows[0]['cut_rule'] = dict(kind='scheduled', step=15)
    with pytest.raises(ValueError): prepare.original_slots(original)

def test_radius_balanced_within_each_cut(original):
    rows = prepare.original_slots(original); values = prepare.radii(rows); counts = defaultdict(Counter)
    for row in rows:
        rule = row['cut_rule']; group = 'alarm' if rule['kind'] == 'first_alarm' else rule['step']
        counts[(row['task'], group)][values[row['episode_id']]] += 1
    assert Counter(values.values()) == {.5: 150, 1.: 150}
    assert all(c[.5] == c[1.] == (15 if g == 'alarm' else 5) for (_, g), c in counts.items())
    assert canonical_hash(values) == '27b7d171cb439dea68408203011eefebbf918161d6a3f4ce78d8eb6b7afb6362'

def test_placeholder_preserved_but_effective_fallback_applied(original):
    rows = prepare.original_slots(original)
    for step, expected in [(15, [15, 5]), (45, [45, 15, 5]), (95, [95, 45, 15, 5])]:
        row = next(r for r in rows if r['cut_rule'].get('step') == step)
        before = deepcopy(row)
        assert row['cut_rule']['fallback'] == 'none_pending_analysis_review'
        assert prepare.CUT_POLICY['scheduled_priority'][str(step)] == expected
        selected = select_cut(row, [5], None)
        assert selected['actual_cut'] == 5 and selected['selection_category'] == 'fallback'
        assert row == before
    row = next(r for r in rows if r['cut_rule']['kind'] == 'first_alarm')
    assert select_cut(row, [5, 15], None)['actual_cut'] == 15
    assert select_cut(row, [], None)['actual_cut'] is None

@pytest.fixture
def released(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, 'release_assets', lambda row, config: None)
    config = dict(round2_preparation={'original_primary_ids_canonical_sha256': 'a'*64})
    row = dict(scope=prepare.SCOPE, stage=prepare.STAGE, bank_version=prepare.BANK, train_primary_slots=300,
        simulator_attempts_limit=17400, training_updates=0, optimizer_updates_limit=0,
        initialization_replacement_stage='technical_reserve', initialization_replacement_workflow_limit=1200,
        execution_policy=dict(validated_workers=32, gpu_count=8, workers_per_gpu=4),
        episode_ids_canonical_sha256='a'*64)
    ready = dict(task_id='native10-training-20260916', version=8, status='protocol_approved_test',
        released_scope=[prepare.SCOPE, prepare.RESERVE_SCOPE], round2_collection=row)
    path = tmp_path/'NATIVE10_ANALYSIS_READY.json'; path.write_text(json.dumps(ready))
    return config, ready, path

def test_exact_release(released):
    config, _, path = released
    ready, refs = prepare.release(path, config)
    assert ready['round2_collection']['training_updates'] == 0 and not refs

@pytest.mark.parametrize('key,value', [('stage', 'round1_labels'), ('train_primary_slots', 301),
    ('training_updates', 1), ('simulator_attempts_limit', 17401), ('optimizer_updates_limit', 1),
    ('bank_version', 'round1_labels_v1'), ('episode_ids_canonical_sha256', 'b'*64)])
def test_changed_release_rejected(released, key, value):
    config, ready, path = released; ready['round2_collection'][key] = value; path.write_text(json.dumps(ready))
    with pytest.raises(ValueError): prepare.release(path, config)

def test_version_number_is_not_release(released):
    config, ready, path = released; ready['version'] = 100; ready['released_scope'] = ['round1_development_policy']
    path.write_text(json.dumps(ready))
    with pytest.raises(ValueError, match='explicitly'): prepare.release(path, config)

def test_unreleased_freeze_creates_nothing(tmp_path, released):
    config, ready, path = released; ready['released_scope'] = ['round1_development_policy']; path.write_text(json.dumps(ready))
    with patch.object(prepare, 'build_pending', return_value=config), patch.object(prepare, '_new', side_effect=AssertionError('must not create output')):
        with pytest.raises(ValueError, match='explicitly'):
            prepare.freeze(tmp_path/'config.json', path, [], version='unit_unused')

def test_final_entry_evidence_required():
    with pytest.raises(ValueError, match='omits actual'): prepare.cpu_checks([])

def test_release_requires_labels13_capture_contract():
    with pytest.raises(ValueError, match='capture contract'):
        prepare.release_assets(dict(kind='policy5', capture_allowed=False), {})

def test_real_pending_matches_explicit_ready_and_remains_nonrunnable():
    from experiments.native10_training_20260916.protocol import validate_protocol
    path = prepare.storage.ROOT/'preparation/round2_pending_v1/config.json'
    config = prepare.read(path)
    ready, _ = prepare.release(prepare.storage.PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json', config)
    assert ready['round2_collection']['episode_ids'] == config['main_collection']['banks'][prepare.BANK]['episode_ids']
    assert validate_protocol(config)['runnable'] is False
    with pytest.raises(ValueError): validate_protocol(config, require_runnable=True)

def test_real_release_does_not_allow_another_selected_checkpoint():
    config = prepare.read(prepare.storage.ROOT/'preparation/round2_pending_v1/config.json')
    row = deepcopy(prepare.read(prepare.storage.PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json')['round2_collection'])
    row['selected_critic']['step'] = 2400
    with pytest.raises(ValueError, match='B200'): prepare.release_assets(row, config)

def test_new_freeze_cannot_override_old_dependency_sha():
    assert prepare.merge_frozen_files({'old': 'a'}, {'old': 'a', 'new': 'b'}) == {'old': 'a', 'new': 'b'}
    with pytest.raises(ValueError, match='replace any old'):
        prepare.merge_frozen_files({'old': 'a'}, {'old': 'b'})

def test_new_scene_snapshot_must_match_ready_starting_evidence(tmp_path):
    import hashlib
    snapshot = tmp_path/'scene.jsonl'; snapshot.write_bytes(b'{}\n')
    ready = dict(round2_collection=dict(scene_identity=dict(registry_before=dict(sha256=hashlib.sha256(b'{}\n').hexdigest()))))
    prepare.check_registry_snapshot(snapshot, ready)
    snapshot.write_bytes(b'{}\n{}\n')
    with pytest.raises(ValueError): prepare.check_registry_snapshot(snapshot, ready)

def test_self_sealed_alternative_base_cannot_replace_original_registration(tmp_path):
    path = tmp_path/'config.json'; path.write_text('{}')
    with patch.object(prepare, 'read', side_effect=AssertionError('must reject before trusting alternate rows')):
        with pytest.raises(ValueError): prepare.build_pending(path, tmp_path/'ready.json')
