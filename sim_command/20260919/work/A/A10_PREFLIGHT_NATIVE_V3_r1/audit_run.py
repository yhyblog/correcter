"""CPU reconciliation of the one consumed V3 run; no runtime re-entry."""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import re
import sys

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'A10_PREFLIGHT_NATIVE_V3'
W = B/'work/A'/f'{TASK}_r1'
RUN = B/'results/A/P10_launcher_runs/A10_PREFLIGHT_NATIVE_V3_r1_A_wave05'
P = B/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1'


def forbidden(event, args):
    if event.startswith(('ctypes.dlopen', 'ctypes.dlsym')):
        raise RuntimeError('No driver loading in receipt audit')
    if event == 'import' and args[0].split('.')[0] in {'torch', 'mujoco', 'metaworld', 'gymnasium', 'OpenGL', 'pynvml'}:
        raise RuntimeError('No heavy runtime imports in receipt audit')


sys.addaudithook(forbidden)
sys.dont_write_bytecode = True
sys.path.insert(0, str(P/'code'))
from core.accounting import summarize
from core.initialization import summarize_initialization
from core.graphics_contract import reconcile


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=sha(path), size_bytes=path.stat().st_size)


def write(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


R = read(W/'inputs/releases__P10_A_NATIVE_PREFLIGHT_V3.json')
D = Path(read(RUN/'diagnostic_link.json')['path'])
launch = read(RUN/'LAUNCH_RESULT.json')
failure = read(D/'failure.json') if (D/'failure.json').exists() else None
resource = read(D/'resource_receipt.json')
events = rows(D/'events.jsonl')
public = summarize(events)
initialization = summarize_initialization(rows(D/'initialization_events.jsonl'), R['initialization_caps'])
graphics = reconcile(D/'graphics_events.jsonl')
assert public == launch['resources']['public_events']
assert initialization == launch['resources']['initialization'] == read(D/'initialization_receipt.json')
assert graphics == launch['resources']['graphics'] == read(D/'graphics_receipt.json')
assert resource == launch['resources']['diagnostic_receipt']
assert launch['release_consumed'] and not launch['remaining_caps_reusable']
for key, cap in R['resource_caps'].items():
    assert 0 <= public['counts'][key] <= cap
for key, cap in R['initialization_caps'].items():
    assert 0 <= initialization['entered_budget_usage'][key] <= cap
for key, cap in R['graphics_caps'].items():
    assert 0 <= graphics['entered_budget_usage'][key] <= cap
if launch['status'] == 'complete':
    assert failure is None and launch['diagnostic_returncode'] == 0
    assert public['counts'] == R['resource_caps']
    assert initialization['entered_budget_usage'] == R['initialization_caps']
    assert graphics['entered_budget_usage'] == R['graphics_caps']
    assert graphics['returned'] == 108 and graphics['failed'] == graphics['incomplete'] == 0
else:
    assert failure is not None and launch['diagnostic_returncode'] != 0

ledger = rows(D/'graphics_events.jsonl')
entries = {r['event_id']: r for r in ledger if r['phase'] == 'entered'}
terminals = {r['event_id']: r for r in ledger if r['phase'] != 'entered'}
totals = {phase: collections.Counter() for phase in ('returned', 'failed', 'incomplete')}
for eid, entry in entries.items():
    if eid in terminals:
        terminal = terminals[eid]
        assert terminal['resource_units'] == entry['resource_units']
        totals[terminal['phase']].update(entry['resource_units'])
    else:
        totals['incomplete'].update(entry['resource_units'])
with (W/'GRAPHICS_COUNTS.csv').open('x') as stream:
    stream.write('operation,cap,entered,returned,failed,incomplete\n')
    for key, cap in R['graphics_caps'].items():
        stream.write(f"{key},{cap},{graphics['entered_budget_usage'][key]},{totals['returned'][key]},{totals['failed'][key]},{totals['incomplete'][key]}\n")
api = rows(D/'graphics_api_results.jsonl')
errors = [row for row in api if row['operation'] == 'egl_error_queries']
cleanup = read(D/'graphics_cleanup.json')
mapping, policy, raw_type, loader = [read(D/name) for name in (
    'device_mapping.json', 'policy_device.json', 'policy_device_type.json', 'loader_identity.json')]
assert mapping['stage'] == 'unique_mapping_complete' and len(mapping['devices']) == 8
expected = {row['gpu_uuid']: row['pci_bus_id'] for row in R['physical_inventory']}
observed = {row['mapping']['gpu_uuid']: row['mapping']['pci_bus_id'] for row in mapping['devices']}
assert expected == observed
selected = [row for row in mapping['devices'] if row['decision'] == 'target']
assert len(selected) == 1 and selected[0]['mapping'] == {k: R[k] for k in ('gpu_uuid', 'pci_bus_id')}
assert raw_type['raw_type_module'] == policy['raw_type_module'] == 'torch._C'
assert raw_type['raw_type_qualname'] == policy['raw_type_qualname'] == '_CUuuid'
assert raw_type['conversion_calls'] == 0 and raw_type['torch_uuid_text'] is None
assert policy['trusted_class_identity_match'] and policy['conversion_calls'] == 1
assert policy['conversion_status'] == 'returned' and policy['conversion_error'] is None
assert policy['format_valid'] and policy['expected_format_valid'] and policy['target_matches'] and policy['accepted']
assert policy['normalized_uuid'] == R['gpu_uuid'] and 'after_torch_device_binding' in loader

claim_path = B/'results/A/P10_native_release_claims/P10_A_NATIVE_PREFLIGHT_V3.json'
claim = read(claim_path)
assert claim['release_sha256'] == '5c431d7d44e10630354d3349cf7c8d5c2367da1c25826dd9f2de5df0fe088f5f'
command_exit = read(W/'COMMAND_EXIT.json')
assert command_exit['real_sh_invocations'] == 1 and command_exit['automatic_retries'] == 0
family = read(RUN/'process_family_cleanup.json')
assert family['status'] == 'all_formal_group_members_exited'
assert read(W/'POST_COMMAND_PROCESSES.json')['matching_native_processes'] == []
restoration = launch['restoration']
assert restoration['status'] == 'occupancy_resolved'
gpus = restoration['guard_status']['gpus']
assert set(gpus) == set(map(str, range(8)))
assert all(row['state'] == 'holder' and row['driver_pids'] for row in gpus.values())
marks = rows(RUN/'wave_timing.jsonl')
times = {r['phase']: r for r in marks}
offset = marks[0]['unix_seconds'] - marks[0]['monotonic_seconds']
first_cuda = next(row['monotonic_ns']/1e9 + offset for row in ledger
                  if row['phase'] == 'entered' and row['operation'] == 'cuda_driver_initializations')
yield_times, restart_times = {}, {}
for line in (W/'GUARD_LOG_WINDOW.log').read_text().splitlines():
    match = re.match(r'(\S+) GPU (\d): (.*)', line)
    if not match:
        continue
    when = datetime.datetime.fromisoformat(match[1].replace('Z', '+00:00')).timestamp()
    if 'yielded' in match[3]:
        yield_times[match[2]] = when
    if 'started holder manager' in match[3]:
        restart_times[match[2]] = when
assert set(yield_times) == set(restart_times) == set(map(str, range(8)))
assert max(yield_times.values()) + 1 <= first_cuda
assert min(restart_times.values()) >= times['timed_process_exited']['unix_seconds']
assert len(rows(W/'CPU_PROCESS_AND_GUARD_OBSERVATIONS.jsonl')) == command_exit['CPU_observation_samples']

observations = {key: resource[key] for key in ('diagnostic_native_resets_returned',
    'diagnostic_observations_returned', 'post_control_observations_returned',
    'complete_observations_returned', 'usable_observation_artifacts')}
for key, cap in R['observation_caps'].items():
    assert 0 <= observations[key] <= cap
counts = dict(public=public, initialization=initialization, graphics=graphics, observations=observations,
    single_release_claim=1, real_sh_invocations=1, diagnostic_attempts_entered=public['counts']['simulator_attempts'],
    retries=0, deletions=0, native_nvml_identity_queries=2,
    identity_query_basis='Both frozen verify_device paths reached; source-defined two NVML CLI calls, no extra observer or audit query',
    measured_outermost_device_seconds=sum(public['outermost_measured_device_seconds_by_clock'].values()),
    measured_device_scope=public['device_scope'], total_GPU_seconds=None, peak_total_GPU_memory_bytes=None,
    total_GPU_measurement_missing_reason='Only scoped CUDA-event timings and optional PyTorch allocator peaks; full device utilization and total physical GPU peak not measured')
write(W/'ACTUAL_COUNTS.json', counts)
policy_evidence = dict(policy_uuid_guard_passed=True,
    actual_runtime_type=dict(module=policy['raw_type_module'], qualname=policy['raw_type_qualname'],
        trusted_class_identity_match=policy['trusted_class_identity_match']),
    conversion_calls=1, conversion_error=None, format_valid=True, target_matches=True,
    torch_uuid_text=policy['torch_uuid_text'], target_uuid=R['gpu_uuid'], physical_target=selected[0]['mapping'],
    selected_EGL_index=selected[0]['egl_index'], selected_EGL_handle=selected[0]['egl_handle'],
    selected_CUDA_attribute_handle=selected[0]['attribute']['value'], policy_logical_index=policy['logical_index'],
    after_torch_loader_snapshot_present=True, old_V2_runtime_type=None, old_V2_type_status='unknown; not backfilled',
    independent_extra_UUID_probe=False, evidence=[ref(D/name) for name in ('policy_device_type.json',
        'policy_device.json', 'device_mapping.json', 'loader_identity.json')])
write(W/'POLICY_UUID_EVIDENCE.json', policy_evidence)
missing = read(D/'artifact_status.json')
write(W/'ARTIFACT_STATUS_AUDIT.json', dict(**missing,
    all_presence_flags_match=all(row['present'] == (D/name).is_file() for name, row in missing['artifacts'].items()),
    visual_audit_separate='Saved pixel CPU audit only if present; no new render'))
audit = dict(status='ledger_identity_cleanup_audit_passed', native_preflight_outcome=launch['status'],
    failure=failure, counts=counts, policy_UUID=policy_evidence,
    independent_ledger_reconciliation=True, EGL_error_query_count=len(errors),
    EGL_errors_all_success=all(row['raw'] == 0x3000 for row in errors), graphics_cleanup=cleanup,
    occupancy=dict(guard_pid=restoration['guard_status']['pid'],
        restored_holder_managers={key: value['manager_pid'] for key, value in gpus.items()},
        all_eight_restored=True, process_family_cleanup=family, no_matching_processes_after_command=True,
        yield_times_unix=yield_times, restart_times_unix=restart_times, first_explicit_cuInit_unix=first_cuda,
        all_yield_log_seconds_end_before_first_cuInit=True, all_holder_restarts_after_group_exit=True,
        guard_snapshot_scope='Existing guard state, not extra GPU samples; serial shutdown status may lag'),
    timing=launch['timing'], CPU_observation=command_exit, no_retry_or_extra_checker=True,
    current_release_sha256=sha(B/'releases/P10_A_NATIVE_PREFLIGHT_V3.json'),
    code_manifest_still_matches_release=sha(P/'code/CODE_MANIFEST.json') == R['code_manifest_sha256'],
    proposal_still_matches_release=sha(P/'proposal/PROPOSAL.json') == R['proposal_sha256'],
    GPU_queries_by_this_audit=0, large_weight_rehashes_by_this_audit=0,
    checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
write(W/'FINAL_LEDGER_AUDIT.json', audit)
print(json.dumps(dict(status=audit['status'], outcome=launch['status'], public=public['counts'],
    initialization=initialization['entered_budget_usage'], graphics_entered=sum(graphics['entered_budget_usage'].values()),
    observations=observations, holders_restored=8), indent=2))
