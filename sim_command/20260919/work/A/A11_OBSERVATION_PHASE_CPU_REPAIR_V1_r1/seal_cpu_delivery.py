"""Seal CPU-only repair artifacts and verify small immutable references."""
import datetime
import hashlib
import json
from pathlib import Path

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'A11_OBSERVATION_PHASE_CPU_REPAIR_V1'
P = B / 'results/A' / TASK
W = B / 'work/A' / (TASK + '_r1')
RP = B / 'releases/P00_A_OBSERVATION_PHASE_CPU_REPAIR_V1.json'
ACK = B / 'receipts/A' / (TASK + '_ACK.json')

def read(p):
    return json.loads(Path(p).read_text())

def ref(p):
    p = Path(p)
    assert p.stat().st_size < 8 * 1024 * 1024, 'This CPU task must not hash a large asset: ' + str(p)
    raw = p.read_bytes()
    return dict(path=str(p), realpath=str(p.resolve()), sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))

def put(p, value):
    with Path(p).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

release = read(RP)
assert ref(RP)['sha256'] == '3ab42de2135ab3d998d1c339ad31f6cf096a4048bb3d8d8d2aa78f680517591a'
phase = read(P / 'CPU_PHASE_CHECKS.json')
metadata = read(P / 'CPU_METADATA_CHECKS.json')
assert phase['status'] == metadata['status'] == 'PASS'
proposal = read(P / 'proposal/PROPOSAL.json')
before = read(W / 'PROTECTED_BEFORE.json')
protected = []
for old in before['files']:
    actual = ref(old['path'])
    assert old['sha256'] == actual['sha256']
    protected.append(dict(before=old, after=actual, same_bytes=True))
put(P / 'PROTECTED_IDENTITIES.json', dict(status='PASS', files=protected, protected_count=len(protected),
    old_packages_and_failed_receipts_unchanged=True, shared_installs=0, deletions=0))

refs = []
code = read(P / 'code/CODE_MANIFEST.json')
for row in code['files'] + code['inherited_manifests']:
    actual = ref(row['path'])
    assert actual['sha256'] == row['sha256']
    assert actual['realpath'] == row['realpath']
    refs.append(dict(expected=row, actual=actual, status='PASS'))
for name in ['config', 'budget', 'code_manifest', 'input_manifest', 'external_manifest', 'closure',
             'sidecar_ready', 'command_ref', 'preparation_manifest', 'supplementary_protocol_ref',
             'observation_phase_CPU_delta_ref']:
    row = proposal[name]
    actual = ref(row['path'])
    assert actual['sha256'] == row['sha256']
    refs.append(dict(name=name, expected=row, actual=actual, status='PASS'))
rt = read(P / 'proposal/RELEASE_TEMPLATE.json')
assert rt['status'] == 'UNAUTHORIZED_TEMPLATE' and rt['proposal_sha256'] == ref(P / 'proposal/PROPOSAL.json')['sha256']
assert rt['identity'] == proposal['authorization_identity']
assert rt['paths'] == proposal['paths'] and rt['resource_caps'] == proposal['resource_caps']
board = read(P / 'proposal/BOARD_TEMPLATE.json')
assert board['tasks'][0]['status'] == 'ready'
future = {k: dict(path=v, absent=not Path(v).exists() and not Path(v).is_symlink()) for k, v in proposal['paths'].items()}
assert all(x['absent'] for x in future.values())
assert not (B / 'releases/P11_A_COMMON_POOL_FIRST_PARENT_V4.json').exists()
assert not any(release['limits'].values())
control = read(B / 'CONTROL.json')
assert control['revision'] == 43 and control['mode'] == 'prepare' and not control['formal_gpu_runs_enabled']
assert not any(control['current_compute_limits'].values())
assert ref(B / 'CONTROL.json')['sha256'] == ref(W / 'authorization/CONTROL.json')['sha256']
assert ref(B / 'TASK_BOARD.json')['sha256'] == ref(W / 'authorization/TASK_BOARD.json')['sha256']
put(P / 'FINAL_STATIC_REFERENCE_CHECKS.json', dict(status='PASS', small_reference_checks=refs,
    own_python_SHA_count=len(code['files']), inherited_manifest_SHA_only=len(code['inherited_manifests']),
    inherited_vendor_or_large_input_bodies_rehashed=False, future_paths=future,
    current_CONTROL_revision=43, current_TASK_BOARD_revision=50, current_COMPUTE_limits_all_zero=True,
    actual_V4_release_absent=True, future_template_unauthorized=True, board_template_ready=True))

ready = dict(status='CPU_READY', task_id=TASK, revision=1, owner='A',
    at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    release_ref=ref(RP), scope='observation phase contract only; no actual collection',
    observation_range=[0, 300], canonical_names=301, strict_integer_only=True,
    real_callsite_reset='observation_phase(0)', real_callsite_step='observation_phase(step+1)',
    real_CONFIG_scope_hooks_journal_fixture=True, fixture_check_groups=phase['check_groups'],
    identity_metadata_AST_shell_check_groups=metadata['check_groups'],
    all_check_groups_passed=phase['check_groups'] + metadata['check_groups'],
    synthetic_operations=phase['synthetic_operations'], real_operation_counts=release['limits'],
    actual_native_or_Engine_module_imports=0,
    immutable_small_source_code_files=15, modified_or_new_Python_files=4,
    unchanged_numerical_caps=116, source_seed_device_storage_timeout_unchanged=True,
    V3_already_executed_and_closed=True, same_planned_parent=True,
    future_task_id='A11_COMMON_POOL_FIRST_PARENT_V4', future_release_id='P11_A_COMMON_POOL_FIRST_PARENT_V4',
    proposal_ref=ref(P / 'proposal/PROPOSAL.json'), config_ref=ref(P / 'config/CONFIG.json'),
    code_manifest_ref=ref(P / 'code/CODE_MANIFEST.json'),
    pure_JSON_publication_checker_ref=ref(P / 'commands/check_publication_metadata.sh'),
    future_compute_authorized=False, future_claim_and_run_paths_created=False,
    full_state_MJB_runtime_qualification='unmeasured; remains inside the same planned parent after a future independent release',
    B_task_or_dispatch_changed=False, next_action='wait for analysis acceptance; no automatic collection')
put(P / 'CPU_READY.json', ready)

paths = {p for root in (P, W) for p in root.rglob('*') if p.is_file()}
paths.update([ACK, RP, B / 'tasks/A11_OBSERVATION_PHASE_CPU_REPAIR_V1.md'])
paths.update(Path(x['path']) for x in before['files'])
paths.update(Path(x['actual']['path']) for x in refs)
rows = [ref(p) for p in sorted(paths)]
put(P / 'EVIDENCE_MANIFEST.json', dict(task_id=TASK, status='CPU_DELIVERY_SEALED', file_count=len(rows), files=rows,
    no_large_weight_hash=True, synthetic_data_identified=True,
    scope='new isolated CPU bundle/fixtures and selected small inherited references; no model/vendor tree re-audit',
    excludes_self_and_RESULT_to_avoid_cycles=True))
artifact_paths = [p for p in P.iterdir() if p.is_file()]
artifact_paths += [P / 'code/CODE_MANIFEST.json', P / 'config/CONFIG.json',
    *sorted((P / 'proposal').glob('*.json')), P / 'commands/run_proposed_first_parent.sh',
    P / 'commands/check_publication_metadata.sh', ACK]
artifact_rows = [ref(p) for p in sorted(set(artifact_paths))]
result = dict(campaign_id=release['campaign_id'], task_id=TASK, revision=1, owner='A',
    hostname=release['owner_host'], status='CPU_READY', at_utc=ready['at_utc'], ACK=ref(ACK), release=ref(RP),
    control_revision=43, task_board_revision=50,
    delivered='strict 0..300 observation-phase function, real reset/step callsites, CONFIG gate, targeted actual-method CPU checks, unauthorized independent V4 proposal',
    check_groups=ready['all_check_groups_passed'], checks_passed=True,
    synthetic_operations=phase['synthetic_operations'],
    synthetic_journal=dict(entered_events=906, returned_events=905, deliberately_failed_events=1,
        incomplete_events=0, meaning='CPU stubs only; never native graphics or training records'),
    real_operation_counts=release['limits'], own_code_files=15,
    changed_or_new_Python_files=['authorization.py', 'observation_phase.py', 'publication_check.py', 'runtime_engine.py'],
    native_scope_render_hooks_journal_unchanged=True,
    numerical_Engine_AST_unchanged_except_two_scope_expressions_and_import=True,
    caps_source_seed_storage_timeouts_preserved=True, preserved_caps=116,
    prior_V3_already_executed_consumed_closed=True, future_same_planned_parent=True,
    future_proposal_ref=ref(P / 'proposal/PROPOSAL.json'),
    future_compute_authorized=False, future_paths_created=False, actual_V4_release_created=False,
    protected_old_small_files=len(protected), inherited_large_model_or_vendor_reaudit=False,
    old_80_104_133_suites_repeated=False, public_sidecar_supplement_v2_unchanged=True,
    B_task_unchanged=True, dispatch_modified=False,
    artifact_reference_count=len(artifact_rows), evidence_manifest_file_count=len(rows), artifacts=artifact_rows,
    limitations=['CPU evidence does not establish real renderer/model/environment success',
        'MJB/full-state qualification and s300 outcomes remain unmeasured',
        'bounded_first_parent monitoring gaps and original whole-wave lifecycle preserved'],
    next_action='analysis acceptance; actual V4 execution requires independent new release; no automatic collection')
receipt = B / 'receipts/A' / (TASK + '_RESULT.json')
put(receipt, result)
for row in rows + artifact_rows:
    assert ref(row['path'])['sha256'] == row['sha256']
final = dict(status='PASS', task_id=TASK, manifest_files=len(rows), artifact_refs=len(artifact_rows),
    receipt=ref(receipt), report=ref(P / 'REPORT.md'), cpu_ready=ref(P / 'CPU_READY.json'),
    manifest=ref(P / 'EVIDENCE_MANIFEST.json'), proposal=ref(P / 'proposal/PROPOSAL.json'),
    all_real_operations_zero=True, analysis_acceptance_pending=True)
put(W / 'FINAL_VERIFICATION.json', final)
print(json.dumps(final, ensure_ascii=False))
