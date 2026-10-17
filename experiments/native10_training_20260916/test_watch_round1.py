"""Reproducible CPU-only watcher checks; no real queue, status, process or GPU calls."""
from pathlib import Path
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from . import watch_round1 as watcher


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def sealed(path, name, value):
    put(path/name, value)
    put(path/'complete.json', dict(status='complete', protocol_sha256='a'*64,
                                  files={name: watcher.sha(path/name)}))


def config():
    cases = [dict(episode_id=f'train{i}', case_id=f'train{i}', split='train') for i in range(55)]
    cases.insert(7, dict(episode_id='dev0', case_id='dev0', split='development'))
    return dict(episode_manifest=cases,
        main_collection={'banks': {'bank': {'episode_ids': [row['episode_id'] for row in cases],
                                          'stage': 'round1_labels', 'kind': 'labels13'}}},
        analysis_approval={'protocol_sha256': 'a'*64},
        budget={'hard_total': 50000, 'stages': {'p0': {'simulator_attempts': 600},
                'round1_labels': {'simulator_attempts': 23200}, 'technical_reserve': {'simulator_attempts': 1200}}})


def progress():
    return dict(updated_at='test-only', global_simulator_attempts=1234, reserve_remaining=1199,
        holder={'guard_running': True, 'holder_count': 0}, attempts_by_stage={'p0': 564, 'round1_labels': 670},
        completed_primary_slots=10, worker_failures=[], metadata_errors=[], duplicate_accepted_scenes=0,
        budget_within_limits=True, training_updates=0)


@pytest.fixture(autouse=True)
def isolate_every_external_effect(tmp_path, monkeypatch):
    """Any unexpected external queue/read/subprocess invocation fails the test."""
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    monkeypatch.setattr(watcher, 'ROOT', tmp_path/'outputs')
    monkeypatch.setattr(watcher, 'STATUS', tmp_path/'status.json')
    monkeypatch.setattr(watcher.subprocess, 'run', Mock(side_effect=AssertionError('Real queue/process forbidden')))
    monkeypatch.setattr(watcher.subprocess, 'Popen', Mock(side_effect=AssertionError('Real subprocess forbidden')))
    monkeypatch.setattr(watcher, 'process_identity', Mock(side_effect=AssertionError('Real process inspection forbidden')))
    monkeypatch.setattr(watcher, 'holder_snapshot', Mock(return_value={'all_eight_holders_reported': False}))
    monkeypatch.setattr(watcher, 'jsonlines_snapshot', Mock(side_effect=AssertionError('Real ledger/scene access forbidden')))
    # The shared-status helper uses a fixed /tmp lock. Redirect it as well as the
    # explicitly supplied temporary status path; no real shared file is opened.
    def isolated_path(value):
        if str(value) == '/tmp/corrector_native10_executor_status.lock':
            return tmp_path/'executor_status.lock'
        return Path(value)
    monkeypatch.setattr(watcher, 'Path', isolated_path)


def test_cohort_fixed_train_order():
    _, identities, first = watcher.fixed_cohort(config(), 'bank')
    assert first == [f'train{i}' for i in range(50)]
    assert 'dev0' in identities


def test_short_cohort_rejected():
    cfg = config()
    cfg['main_collection']['banks']['bank']['episode_ids'] = ['train0']
    with pytest.raises(ValueError):
        watcher.fixed_cohort(cfg, 'bank')


def test_progress_never_deserializes_success_values(tmp_path, monkeypatch):
    root = tmp_path/'artifact_root'
    sealed(root/'slot_resolution/train0', 'resolution.json',
           dict(status='resolved', planned_slot_id='train0', resolved_episode_id='train0'))
    collection = root/'collections/round1_labels/bank/train0'
    collection.mkdir(parents=True)
    (collection/'summary.json').write_text('Deliberately not JSON: progress hashes, never deserializes outcomes.')
    put(collection/'complete.json', dict(status='complete', protocol_sha256='a'*64,
                                         files={'summary.json': watcher.sha(collection/'summary.json')}))
    rows = [dict(stage='p0', resource='simulator_attempts', amount=564, kind='x', identity='p0'),
            dict(stage='round1_labels', resource='simulator_attempts', amount=3,
                 kind='source_capture', identity='train0')]
    monkeypatch.setattr(watcher, 'jsonlines_snapshot', Mock(side_effect=[rows, []]))
    result = watcher.snapshot(config(), 'bank', root/'wave', root)
    assert result['completed_primary_ids'] == ['train0']
    assert result['global_simulator_attempts'] == 567
    assert not result['first50_all_complete']
    assert not result['scientific_success_statistics_computed']


def test_corrupt_seal_is_error_not_complete(tmp_path, monkeypatch):
    root = tmp_path/'artifact_root'
    sealed(root/'slot_resolution/train0', 'resolution.json',
           dict(status='resolved', planned_slot_id='train0', resolved_episode_id='train0'))
    (root/'slot_resolution/train0/resolution.json').write_text('{}')
    monkeypatch.setattr(watcher, 'jsonlines_snapshot', Mock(side_effect=[[], []]))
    result = watcher.snapshot(config(), 'bank', root/'wave', root)
    assert result['completed_primary_slots'] == 0
    assert len(result['metadata_errors']) == 1


def test_status_merge_preserves_protocol_fields_and_updates_top_counts(tmp_path):
    path = tmp_path/'status.json'
    put(path, dict(main_wave='wave', main_config='fixed', planned_episode_counts={'train': 600}, training_started=False))
    watcher.update_shared_status(progress(), 'wave', 'round1_collection_running', path)
    result = watcher.read(path)
    assert result['main_config'] == 'fixed'
    assert result['planned_episode_counts'] == {'train': 600}
    assert result['training_started'] is False
    assert result['main_complete_collections'] == 10
    assert result['attempts_by_stage'] == progress()['attempts_by_stage']


def test_status_other_wave_rejected(tmp_path):
    path = tmp_path/'status.json'
    put(path, dict(main_wave='other'))
    with pytest.raises(ValueError):
        watcher.update_shared_status(progress(), 'wave', 'round1_collection_running', path)


def test_queue_success_once(tmp_path, monkeypatch):
    state = {'wave_id': 'wave'}
    watcher.event(state, 'event', 'short')
    send = Mock(return_value=SimpleNamespace(returncode=0, stdout='Queued message abc for thread target', stderr=''))
    monkeypatch.setattr(watcher.subprocess, 'run', send)
    watcher.deliver(state, tmp_path/'state.json', {'analysis': 'target'}, 'mock-codex-only')
    watcher.deliver(state, tmp_path/'state.json', {'analysis': 'target'}, 'mock-codex-only')
    assert send.call_count == 1


def test_queue_failure_kept_and_retry(tmp_path, monkeypatch):
    state = {'wave_id': 'wave'}
    watcher.event(state, 'event', 'short')
    path = tmp_path/'state.json'
    send = Mock(return_value=SimpleNamespace(returncode=1, stdout='', stderr='offline'))
    monkeypatch.setattr(watcher.subprocess, 'run', send)
    watcher.deliver(state, path, {'analysis': 'target'}, 'mock-codex-only')
    watcher.deliver(state, path, {'analysis': 'target'}, 'mock-codex-only')
    assert send.call_count == 1
    assert state['events']['event']['recipients']['analysis']['status'] == 'failed'
    assert 'offline' in state['events']['event']['recipients']['analysis']['error']
    state['events']['event']['recipients']['analysis']['retry_after_unix'] = 0
    monkeypatch.setattr(watcher.subprocess, 'run', Mock(return_value=
        SimpleNamespace(returncode=0, stdout='Queued message abc for thread target', stderr='')))
    watcher.deliver(state, path, {'analysis': 'target'}, 'mock-codex-only')
    assert state['events']['event']['recipients']['analysis']['attempts'] == 2


def test_inflight_is_ambiguous_without_resend(tmp_path):
    state = dict(wave_id='wave', events={'x': {'message': 'short', 'recipients': {'a': {'status': 'inflight'}}}})
    watcher.deliver(state, tmp_path/'state.json', {'a': 't'}, 'mock-codex-only')
    watcher.subprocess.run.assert_not_called()
    assert state['events']['x']['recipients']['a']['status'] == 'ambiguous'


def test_incomplete_threshold_never_launches(tmp_path):
    watcher.audit_tick({}, tmp_path/'state.json', tmp_path/'config.json', 'bank', tmp_path,
                       {'first50_all_complete': False})
    watcher.subprocess.Popen.assert_not_called()


def test_pid_reuse_fails_closed():
    launch = dict(start_ticks=123, state='S', args=[watcher.MODULE, 'launch', 'wave', 'bank', '/cfg'])
    watcher.validate_launch_identity(launch, 123, Path('/cfg'), 'bank', 'wave')
    with pytest.raises(ValueError):
        watcher.validate_launch_identity(launch, 124, Path('/cfg'), 'bank', 'wave')


def test_all_five_integrity_alert_categories():
    snapshot = progress()
    assert watcher.integrity_problems(snapshot) == []
    snapshot.update(worker_failures=[{}], metadata_errors=[{}], duplicate_accepted_scenes=1,
                    budget_within_limits=False, training_updates=1)
    assert len(watcher.integrity_problems(snapshot)) == 5


def test_integrity_event_is_once():
    state = {}
    watcher.event(state, 'runtime_integrity_alert', 'first')
    watcher.event(state, 'runtime_integrity_alert', 'second')
    assert len(state['events']) == 1
    assert state['events']['runtime_integrity_alert']['message'] == 'first'
