"""Seal the single completed run using saved evidence only."""
from pathlib import Path
import datetime
import hashlib
import json

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'A11_COMMON_POOL_FIRST_PARENT_V3'
W = B / 'work/A' / (TASK + '_r1')
OUT = B / 'results/A' / TASK
PREP = B / 'results/A/A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1'
RP = B / 'releases/P11_A_COMMON_POOL_FIRST_PARENT_V3.json'

def read(p):
    return json.loads(Path(p).read_text())

def ref(p):
    p = Path(p)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for x in iter(lambda: f.read(1024 * 1024), b''):
            h.update(x)
    return dict(path=str(p), realpath=str(p.resolve()), sha256=h.hexdigest(), size_bytes=p.stat().st_size)

def put(p, obj):
    with Path(p).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

r = read(RP)
run = Path(r['paths']['output'])
summary = read(OUT / 'AUDIT_SUMMARY.json')
audit = read(OUT / 'INDEPENDENT_LEDGER_AUDIT.json')
coverage = read(OUT / 'BRANCH_COVERAGE.json')
failure = read(OUT / 'FAILURE_ANALYSIS.json')
exit_evidence = read(OUT / 'EXIT_AND_RESTORATION.json')
identity = read(OUT / 'IDENTITY_AND_INPUTS.json')
ack = B / 'receipts/A' / (TASK + '_ACK.json')
claim = read(r['paths']['claim'])
command = read(r['paths']['command_record'])
assert claim['release_sha256'] == ref(RP)['sha256']
assert claim['run_id'] == r['identity']['run_id']
assert summary['within_116_caps'] and summary['holder_count_restored'] == 8

paths = set(p for root in [OUT, W, run] for p in root.rglob('*') if p.is_file())
paths.update([ack, RP, Path(r['paths']['claim']), Path(r['paths']['command_record']),
              B / 'tasks/A11_COMMON_POOL_FIRST_PARENT_V3.md',
              PREP / 'code/runtime_engine.py',
              B / 'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code/native/native_egl.py',
              PREP / 'commands/run_proposed_first_parent.sh'])
paths.update(Path(x['path']) for x in identity['input_metadata_refs'])
manifest_rows = [ref(p) for p in sorted(paths)]
manifest = {'schema_version': 1, 'task_id': TASK, 'status': 'sealed_after_exit_CPU_audit',
            'files': manifest_rows, 'file_count': len(manifest_rows),
            'includes_retained_partial_hardlink_alias_paths': True,
            'large_weight_rehash': False, 'manifest_excludes_itself_and_RESULT_to_avoid_cycles': True,
            'raw_runtime_files': summary['run_files'], 'scope': 'this run, saved authorization, selected frozen small input/source references, and postrun CPU audit'}
put(OUT / 'EVIDENCE_MANIFEST.json', manifest)

artifacts = set(OUT.iterdir())
artifacts.update([ack, Path(r['paths']['claim']), Path(r['paths']['command_record']),
    W / 'OUTER_COMMAND_RECORD.json', W / 'OUTER_EXECUTION_RESULT.json',
    W / 'command.stdout', W / 'command.stderr'])
for rel in ['launcher/LAUNCH_RESULT.json', 'launcher/PRIVATE_COST_INDEX.json', 'launcher/events.jsonl',
            'launcher/NVML_IDENTITY.json', 'launcher/STORAGE_ADMISSION.json', 'launcher/STORAGE_MONITOR.jsonl',
            'launcher/LIFECYCLE_REQUESTED.json', 'launcher/HANDOFF_ENVIRONMENT.json',
            'reserved/PRIVATE_COST_INDEX.json', 'reserved/WAVE_EXIT.json', 'reserved/normal_EXIT.json',
            'reserved/PROCESS_GROUP_EXIT.json', 'reserved/ATTEMPT_COVERAGE.json', 'reserved/PAIRED_LABELS.json',
            'reserved/normal.stdout', 'reserved/normal.stderr',
            'normal/FAILURE.json', 'normal/RESOURCE_LEDGER.json', 'normal/numeric_events.jsonl',
            'normal/initialization_events.jsonl', 'normal/graphics_events.jsonl', 'normal/graphics_cleanup.json',
            'normal/graphics_receipt.json', 'normal/policy_device_type.json', 'normal/policy_device.json',
            'normal/loader_identity.json', 'normal/policy_loader.json', 'normal/device_mapping.json']:
    artifacts.add(run / rel)
result = {'campaign_id': r['campaign_id'], 'task_id': TASK, 'revision': 1, 'owner': 'A',
    'hostname': r['owner_host'], 'status': 'TECHNICAL_FAILURE',
    'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'ACK': ref(ack), 'release': ref(RP), 'claim': ref(r['paths']['claim']),
    'command_record': ref(r['paths']['command_record']),
    'command_invocations': 1, 'claim_count': 1, 'actual_branch_attempts': 1,
    'raw_exit_code': 3, 'elapsed_seconds': summary['elapsed_seconds'],
    'actually_started_branches': ['normal'], 'not_started_branches': coverage['not_started_branches'],
    'completed_rollouts': 0, 'legal_cut_count': 0, 'full_state_qualified_attempts': 0,
    'single_outcome_qualified_attempts': 0, 'complete_repeat_pairs': 0,
    'valid_Q_or_G0_targets': 0, 'success': None,
    'success_missing_reason': 'No task outcome; technical failure before diagnostic reset is not success=0.',
    'per_branch_coverage': coverage['per_branch'],
    'resource_entered': audit['wave_operation_totals_only']['entered'],
    'resource_returned': audit['wave_operation_totals_only']['returned'],
    'resource_failed': audit['wave_operation_totals_only']['failed'],
    'resource_incomplete': audit['wave_operation_totals_only']['incomplete'],
    'counts_complete': True, 'within_all_116_caps': True,
    'private_ledger_events': summary['ledger_event_pairs'], 'public_UUID_bridge': False,
    'primary_failure': failure['primary'], 'cleanup_failures': [],
    'failure_outside_metered_operation_recorded_separately': True,
    'source': r['source'], 'raw_plan_or_noise_saved': False, 'saved_RGB_count': 0,
    'policy_device_UUID_accepted': True, 'strict_policy_loader_accepted': True,
    'process_family_cleanup': exit_evidence['process_group_exit'],
    'holder_restoration': exit_evidence['saved_restoration'], 'holder_count_restored': 8,
    'successful_handoff_raw_poll_count': None,
    'successful_handoff_missing_reason': exit_evidence['handoff_missing_reason'],
    'timing': {k: v for k, v in exit_evidence.items() if k.startswith('observed_') or k == 'timeouts_by_scope'},
    'storage_monitor_polls': 54, 'storage_monitor_failure': None,
    'storage_monitoring_gaps_preserved': True,
    'runtime_reference_count_verified': summary['runtime_reference_count'],
    'evidence_manifest_files': len(manifest_rows), 'artifacts': [ref(p) for p in sorted(artifacts)],
    'release_consumed': True, 'release_closure_by_analysis_pending': True,
    'remaining_caps_reusable': False, 'automatic_retry': False, 'old_releases_reused': [],
    'postrun_audit': 'saved files and narrow frozen-source inspection only; no project/runtime imports or probes',
    'shared_installations': 0, 'daemon_restarts': 0, 'training_updates': 0,
    'deletions': 0, 'retries': 0, 'B_participated': False,
    'public_interface_modified': False, 'old_packages_and_receipts_modified': False,
    'scientific_interpretation': 'collector technical failure evidence, not method/task failure or performance ranking',
    'next_action': 'wait for analysis acceptance/closure; no automatic repair, next parent or training'}
receipt = B / 'receipts/A' / (TASK + '_RESULT.json')
put(receipt, result)
for x in manifest_rows:
    assert ref(x['path'])['sha256'] == x['sha256'], x['path']
for x in result['artifacts']:
    assert ref(x['path'])['sha256'] == x['sha256'], x['path']
verification = {'status': 'PASS', 'manifest_file_count': len(manifest_rows),
    'artifact_reference_count': len(result['artifacts']), 'receipt': ref(receipt),
    'manifest': ref(OUT / 'EVIDENCE_MANIFEST.json'), 'report': ref(OUT / 'REPORT.md'),
    'verification_scope': 'SHA of saved run/audit/selected small frozen metadata only'}
put(W / 'DELIVERY_VERIFICATION.json', verification)
print(json.dumps(verification, ensure_ascii=False))
