"""Post-run CPU audit of saved files only. No runtime/project imports or probes."""
import collections
import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
B = ROOT / 'Corrector/sim_command/20260919'
TASK = 'A11_COMMON_POOL_FIRST_PARENT_V3'
W = B / 'work/A' / (TASK + '_r1')
OUT = B / 'results/A' / TASK
PREP = B / 'results/A/A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1'
RELEASE = B / 'releases/P11_A_COMMON_POOL_FIRST_PARENT_V3.json'


def read(p):
    return json.loads(Path(p).read_text())


def ref(p):
    p = Path(p)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return {'path': str(p), 'realpath': str(p.resolve()),
            'sha256': h.hexdigest(), 'size_bytes': p.stat().st_size}


def write(name, obj):
    p = OUT / name
    with p.open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    return ref(p)


def ledger(path, kind):
    starts, ends, issues = {}, {}, []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            row = json.loads(line)
            key, phase = row['event_id'], row['phase']
            if phase == 'entered':
                assert key not in starts, 'duplicate entry'
                units = row.get('units', row.get('resource_units'))
                assert isinstance(units, dict)
                assert all(k in caps and type(v) is int and v >= 0 for k, v in units.items())
                starts[key] = (row, units)
            else:
                assert phase in ('returned', 'failed', 'raised'), 'invalid phase'
                assert key in starts and key not in ends, 'orphan/duplicate terminal'
                first, units = starts[key]
                if kind == 'initialization':
                    assert all(row[k] == first[k] for k in ('units', 'source', 'stage', 'wall_start'))
                if kind == 'graphics':
                    assert row['operation'] == first['operation']
                    assert row['resource_units'] == units
                ends[key] = row
        except Exception as e:
            issues.append({'line': line_number, 'error': type(e).__name__ + ': ' + str(e)})
    counts = {phase: dict.fromkeys(caps, 0) for phase in ('entered', 'returned', 'failed', 'incomplete')}
    failed, missing = [], []
    for key, (row, units) in starts.items():
        terminal = ends.get(key)
        phase = 'incomplete' if terminal is None else ('returned' if terminal['phase'] == 'returned' else 'failed')
        if phase == 'incomplete':
            missing.append(key)
        if phase == 'failed':
            failed.append(key)
        for k, v in units.items():
            counts['entered'][k] += v
            counts[phase][k] += v
    return {'reference': ref(path), 'kind': kind, 'identity_scope': str(path),
            'events_entered': len(starts), 'events_returned': sum(x['phase'] == 'returned' for x in ends.values()),
            'events_failed': len(failed), 'events_incomplete': len(missing),
            'failed_ids': failed, 'incomplete_ids': missing, 'record_errors': issues,
            'counts_complete': not issues and not missing, **counts}


OUT.mkdir(exist_ok=False)
r = read(RELEASE)
assert ref(RELEASE)['sha256'] == '55812df54865d7773e600f4ffedef26413f3e372fd7deb42bd3060a2ed0e5734'
run = Path(r['paths']['output'])
outer = read(W / 'OUTER_EXECUTION_RESULT.json')
launch = read(run / 'launcher/LAUNCH_RESULT.json')
resource = read(run / 'normal/RESOURCE_LEDGER.json')
coverage = read(run / 'reserved/ATTEMPT_COVERAGE.json')
wave = read(run / 'reserved/WAVE_EXIT.json')
failure = read(run / 'normal/FAILURE.json')
proposal = read(PREP / 'proposal/PROPOSAL.json')
cfg = read(PREP / 'config/CONFIG.json')
caps = r['resource_caps']
assert len(caps) == 116 and outer['returncode'] == launch['returncode'] == 3
assert len(wave['rows']) == 1 and wave['rows'][0]['branch'] == 'normal'

scopes = [ledger(run / 'launcher/events.jsonl', 'launcher_numeric'),
          ledger(run / 'normal/numeric_events.jsonl', 'child_numeric'),
          ledger(run / 'normal/initialization_events.jsonl', 'initialization'),
          ledger(run / 'normal/graphics_events.jsonl', 'graphics')]
comparisons = []
for scope, saved in [(scopes[0], launch['launcher_ledger']['entered']),
                     (scopes[1], resource['numeric']['entered']),
                     (scopes[2], resource['initialization']['entered_budget_usage']),
                     (scopes[3], resource['graphics']['entered_budget_usage'])]:
    equal = all(scope['entered'][k] == v for k, v in saved.items())
    comparisons.append({'scope': scope['identity_scope'], 'saved_entered_matches': equal})
    assert equal
assert all(scopes[0]['returned'][k] == v for k, v in launch['launcher_ledger']['returned'].items())
assert all(scopes[1]['returned'][k] == v for k, v in resource['numeric']['returned'].items())
assert all(scopes[2]['returned'][k] == v for k, v in resource['initialization']['returned_operation_units'].items())
assert scopes[3]['events_returned'] == resource['graphics']['returned']
assert all(sum(s['entered'][k] for s in scopes[1:]) == v for k, v in resource['total_entered'].items())
totals = {phase: {k: sum(s[phase][k] for s in scopes) for k in caps}
          for phase in ('entered', 'returned', 'failed', 'incomplete')}
violations = {k: {'actual': v, 'cap': caps[k]} for k, v in totals['entered'].items() if v > caps[k]}
assert not violations and all(s['counts_complete'] for s in scopes)
write('INDEPENDENT_LEDGER_AUDIT.json', {
    'status': 'PASS', 'method': 'stdlib parse of four saved private journals; entered charged once; terminal repeats add zero',
    'private_scopes': scopes, 'saved_comparisons': comparisons, 'release_caps': caps,
    'wave_operation_totals_only': totals, 'counts_complete': True, 'within_all_116_caps': True,
    'cap_violations': violations, 'public_UUID_bridge': False,
    'scope_warning': 'Operation-vector sums only; parent/child event identities remain separate. Formal guard-client polling is not the NVML identity ledger.',
    'primary_failure_outside_metered_call': failure['message'],
    'primary_failure_not_hidden_by_zero_failed_meter_events': True})

rows = []
for row in coverage['planned']:
    name, started = row['role'], row['started']
    assert started == (name == 'normal')
    assert not row['result_present'] and not row['sidecar_present']
    rows.append({**row, 'actual_attempts': 1 if started else 0,
                 'execution_status': 'technical_failure_before_diagnostic_reset' if started else 'not_started_after_normal_failure',
                 'legal_cut_reached': False, 'cut_state_saved': False,
                 'controls_returned': 0, 'observations_returned': 0,
                 'commitment_steps_returned': 0, 'tail_discarded': False,
                 'H10_suffix_entered': False, 'absolute_s300_reached': False,
                 'legal_terminal_record_present': False, 'single_outcome_qualified': False,
                 'success': None, 'success_missing_reason': 'No complete task outcome; technical failure is not success=0.',
                 'full_state_verified': None, 'full_state_missing_reason': 'cut5 capture/comparison not entered',
                 'MJB_qualified': None, 'MJB_missing_reason': 'no capture; mj_saveModel not entered',
                 'repeat_pair_qualified': False, 'gain_target_qualified': False})
labels = read(run / 'reserved/PAIRED_LABELS.json')
assert not labels['records'] and all(x['target'] is None and x['target_mask'] is False for x in labels['labels'].values())
write('BRANCH_COVERAGE.json', {'planned_attempts': 15, 'started_attempts': 1,
    'started_branches': ['normal'], 'not_started_branches': [x['role'] for x in rows if not x['started']],
    'completed_rollouts': 0, 'legal_cuts': 0, 'full_state_qualified_attempts': 0,
    'single_outcome_qualified_attempts': 0, 'complete_repeat_pairs': 0,
    'valid_Q_or_G0_targets': 0, 'per_branch': rows, 'saved_labels': labels,
    'source_ref': ref(run / 'reserved/ATTEMPT_COVERAGE.json'), 'paired_labels_ref': ref(run / 'reserved/PAIRED_LABELS.json')})

runtime = PREP / 'code/runtime_engine.py'
native = B / 'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code/native/native_egl.py'
def excerpt(p, a, z):
    lines = p.read_text().splitlines()
    return {'source': ref(p), 'lines': [{'line': i + 1, 'text': lines[i]} for i in range(a-1, z)]}
assert "self.egl.observation_scope('step0')" in runtime.read_text()
assert 'step0' not in cfg['native']['observation_phases']
write('FAILURE_ANALYSIS.json', {'classification': 'technical integration failure; no task/method outcome',
    'primary': failure, 'failure_ref': ref(run / 'normal/FAILURE.json'),
    'cleanup_failures': resource['cleanup'], 'failure_traceback_is_current_runtime_evidence': True,
    'immediate_static_mismatch': {'caller': 'step0', 'configured_phases': cfg['native']['observation_phases'],
        'caller_in_allowed_set': False, 'config_ref': ref(PREP / 'config/CONFIG.json'),
        'caller_excerpt': excerpt(runtime, 37, 45), 'guard_excerpt': excerpt(native, 226, 234)},
    'diagnostic_reset_entered': False, 'render_entered': False,
    'earlier_completed_work': {'model_initializations': 1, 'language_embedding_forwards': 1,
        'environment_instances': 2, 'environment_reset_calls': 51, 'reset_model_calls': 102,
        'initialization_physics_substeps': 25500},
    'full_s300_observation_phase_coverage_measured': False,
    'implementation_modified': False, 'retry_performed': False, 'future_action_owner': 'analysis'})

# Read only the existing manager log; no guard/status/NVML/process probes.
log = ROOT / 'gpu_occupancy_guard.log'
start = outer['started_at_utc'][:19]
end = outer['ended_at_utc'][:19]
with log.open('rb') as f:
    offset = max(0, log.stat().st_size - 800000)
    f.seek(offset)
    tail = f.read().decode(errors='replace')
lines = [x for x in tail.splitlines() if start <= x[:19] <= end]
with (OUT / 'HOLDER_MANAGER_LOG_WINDOW.txt').open('x') as f:
    f.write('\n'.join(lines) + '\n')
yielded = sorted({int(m.group(1)) for x in lines if (m := re.search(r'GPU (\d): yielded;', x))})
restored = sorted({int(m.group(1)) for x in lines if (m := re.search(r'GPU (\d): started holder manager', x))})
assert yielded == restored == list(range(8))
gpus = launch['restoration']['guard_status']['gpus']
assert all(gpus[str(i)]['state'] == 'holder' for i in range(8))
group = read(run / 'reserved/PROCESS_GROUP_EXIT.json')
assert group['status'] == 'all_formal_group_members_exited'
assert wave['rows'][0]['cleanup_complete'] and not wave['rows'][0]['remaining_group']
write('EXIT_AND_RESTORATION.json', {'raw_outer_execution': outer, 'reserved_wave_exit': wave,
    'process_group_exit': group, 'saved_restoration': launch['restoration'],
    'holder_count_restored': 8, 'manager_log_yielded_GPUs': yielded, 'manager_log_restored_GPUs': restored,
    'manager_log_window': ref(OUT / 'HOLDER_MANAGER_LOG_WINDOW.txt'),
    'log_slice': {'source': str(log), 'read_tail_start_byte': offset, 'start_utc': start, 'end_utc': end},
    'log_semantics': 'Manager timestamps, not successful raw GPU handoff poll samples.',
    'successful_handoff_raw_poll_count': launch['successful_handoff_raw_poll_count'],
    'handoff_missing_reason': launch['handoff_missing_reason'],
    'timeouts_by_scope': r['timeouts'], 'observed_child_command_seconds': wave['rows'][0]['elapsed_seconds'],
    'observed_child_body_seconds': resource['elapsed_seconds'],
    'observed_preparation_seconds': read(run / 'launcher/LIFECYCLE_REQUESTED.json')['elapsed_preparation'],
    'observed_launcher_seconds': launch['elapsed_seconds'],
    'GPU_seconds': None, 'GPU_seconds_missing_reason': 'Wall time is not a GPU-compute measurement.',
    'postrun_live_probes': 0, 'no_manual_kills_or_guard_restart': True,
    'early_extractor_note': 'Two work/*.window.txt files were empty due to a date-format filter error; superseded by the UTC-T manager window above, not restoration evidence.'})

files = [p for p in run.rglob('*') if p.is_file()]
inodes = {}
for p in files:
    st = p.stat()
    inodes.setdefault((st.st_dev, st.st_ino), (st.st_size, st.st_blocks * 512))
storage_polls = [json.loads(x) for x in (run / 'launcher/STORAGE_MONITOR.jsonl').read_text().splitlines()]
write('STORAGE_AUDIT.json', {'admission': read(run / 'launcher/STORAGE_ADMISSION.json'),
    'frozen_storage': r['storage'], 'saved_monitor_summary': launch['storage_monitor'],
    'monitor_saved_record_count': len(storage_polls), 'monitor_last': storage_polls[-1],
    'saved_runtime_file_paths': len(files), 'saved_runtime_unique_inodes': len(inodes),
    'saved_runtime_file_path_bytes_including_hardlink_aliases': sum(p.stat().st_size for p in files),
    'saved_runtime_unique_inode_payload_bytes': sum(x[0] for x in inodes.values()),
    'reported_unique_inode_allocated_bytes': sum(x[1] for x in inodes.values()),
    'child_writer_reserved_bytes_at_ledger_write': resource['writer_reserved_bytes'],
    'postrun_new_capacity_or_quota_query': False, 'private_temp_or_shared_cache_deleted': False,
    'unknowns_preserved': ['project quota', 'exclusive future reservation', 'shared HF/native outside-path writes',
        'unlinked open files', 'monitor scan/drain overshoot', 'process-group RSS peak'],
    'storage_is_not_all_system_write_accounting': True})

device = read(run / 'normal/policy_device.json')
loader = read(run / 'normal/policy_loader.json')
assert device['accepted'] and device['normalized_uuid'] == r['device']['gpu_uuid']
assert loader['state_calls'][0]['strict'] and loader['state_calls'][0]['returned']
assert not loader['state_calls'][0]['missing_keys'] and not loader['state_calls'][0]['unexpected_keys']
small_input_refs = [ref(PREP / 'proposal/PROPOSAL.json'), ref(PREP / 'config/CONFIG.json'),
                   ref(PREP / 'proposal/SOURCE_PROPOSAL.json'), ref(PREP / 'INPUT_MANIFEST.json'),
                   ref(PREP / 'code/CODE_MANIFEST.json')]
source_ref = cfg.get('source_manifest_ref')
if isinstance(source_ref, dict) and 'path' in source_ref:
    assert Path(source_ref['path']).stat().st_size < 1024 * 1024
    small_input_refs.append(ref(source_ref['path']))
assert cfg['source'] == r['source'] == proposal['source']
write('IDENTITY_AND_INPUTS.json', {'release': ref(RELEASE), 'identity': r['identity'], 'source': r['source'],
    'source_identical_across_release_proposal_config': True, 'input_metadata_refs': small_input_refs,
    'model_sha256_from_frozen_config': cfg['model_sha256'], 'large_model_postrun_rehash': False,
    'runtime_strict_loader': loader, 'policy_device': device,
    'raw_policy_UUID_type_evidence_ref': ref(run / 'normal/policy_device_type.json'),
    'loader_identity_ref': ref(run / 'normal/loader_identity.json'),
    'device_mapping_ref': ref(run / 'normal/device_mapping.json'),
    'raw_plans_saved': 0, 'noise_draws': 0, 'candidate_bank_saved': False,
    'plan_and_noise_missing_reason': 'Sampling and legal cut never entered; seed metadata is not a saved plan.',
    'seed_replacements': 0, 'B_participated': False})

# Verify SHA references actually published by this run, without traversing old model manifests.
found = []
def walk(x, source, pointer=''):
    if isinstance(x, dict):
        if isinstance(x.get('path'), str) and isinstance(x.get('sha256'), str):
            path = Path(x['path'])
            if path.is_relative_to(run):
                actual = ref(path)
                found.append({'source': source, 'pointer': pointer, 'expected': x['sha256'],
                              'actual': actual, 'matches': x['sha256'] == actual['sha256']})
        for k, v in x.items():
            walk(v, source, pointer + '/' + str(k))
    elif isinstance(x, list):
        for k, v in enumerate(x):
            walk(v, source, pointer + '/' + str(k))
for p in files:
    if p.suffix == '.json':
        walk(read(p), str(p))
assert all(x['matches'] for x in found)
write('RUNTIME_REFERENCE_AUDIT.json', {'status': 'PASS', 'runtime_reference_count': len(found),
    'runtime_unique_referenced_files': len({x['actual']['path'] for x in found}), 'checks': found,
    'large_weight_refs_not_rehashed': True})
with (OUT / 'LAUNCH_RESULT.json').open('xb') as f:
    f.write((run / 'launcher/LAUNCH_RESULT.json').read_bytes())
assert ref(OUT / 'LAUNCH_RESULT.json')['sha256'] == ref(run / 'launcher/LAUNCH_RESULT.json')['sha256']
summary = {'task_id': TASK, 'status': 'TECHNICAL_FAILURE', 'command_invocations': 1, 'claims': 1,
    'exit_code': 3, 'elapsed_seconds': outer['elapsed_seconds'], 'started_branches': ['normal'],
    'ledger_event_pairs': {x['kind']: x['events_entered'] for x in scopes},
    'actual_nonzero_operation_units': {k: v for k, v in totals['entered'].items() if v},
    'actual_failed_meter_events': sum(x['events_failed'] for x in scopes),
    'actual_incomplete_meter_events': sum(x['events_incomplete'] for x in scopes),
    'primary_failure': failure['message'], 'cleanup_failures': 0,
    'resource_counts_complete': True, 'within_116_caps': True, 'holder_count_restored': 8,
    'runtime_reference_count': len(found), 'run_files': len(files),
    'source_refs': small_input_refs, 'release_consumed': True, 'retries': 0}
write('AUDIT_SUMMARY.json', summary)
print(json.dumps(summary, ensure_ascii=False))
