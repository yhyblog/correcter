"""Freeze only the CPU observation-contract and independent V4 identity delta."""
import copy
import difflib
import hashlib
import json
from pathlib import Path

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P = B / 'results/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1'
OLD = B / 'results/A/A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1'
O = B / 'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1'
W = B / 'work/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1_r1'

def read(p):
    return json.loads(Path(p).read_text())

def ref(p):
    p = Path(p)
    raw = p.read_bytes()
    return dict(path=str(p), realpath=str(p.resolve()), sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))

def write(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n')

prior = read(OLD / 'proposal/PROPOSAL.json')
old_config = read(OLD / 'config/CONFIG.json')
config = read(P / 'config/CONFIG.json')
other_config = copy.deepcopy(config)
other_config['native']['observation_phases'] = old_config['native']['observation_phases']
assert other_config == old_config
assert config['native']['observation_phases'] == [f'step_{i}' for i in range(301)]
assert read(P / 'CPU_PHASE_CHECKS.json')['status'] == 'PASS'
old_code_manifest = read(OLD / 'code/CODE_MANIFEST.json')
code_rows = [ref(p) for p in sorted((P / 'code').rglob('*.py'))]
diff, patch = [], []
for new in code_rows:
    dst = Path(new['path'])
    rel = dst.relative_to(P)
    src = OLD / rel
    old = ref(src) if src.exists() else None
    same = old is not None and old['sha256'] == new['sha256']
    diff.append(dict(relative_path=str(rel), old=old, new=new,
                     change='same_bytes_new_package' if same else ('new' if old is None else 'modified')))
    if not same:
        patch.extend(difflib.unified_diff(src.read_text().splitlines(True) if src.exists() else [],
            dst.read_text().splitlines(True), fromfile=str(src) if src.exists() else '/dev/null', tofile=str(dst)))
patch.extend(difflib.unified_diff((OLD / 'config/CONFIG.json').read_text().splitlines(True),
    (P / 'config/CONFIG.json').read_text().splitlines(True), fromfile=str(OLD / 'config/CONFIG.json'), tofile=str(P / 'config/CONFIG.json')))
patch.extend(difflib.unified_diff((OLD / 'commands/run_proposed_first_parent.sh').read_text().splitlines(True),
    (P / 'commands/run_proposed_first_parent.sh').read_text().splitlines(True),
    fromfile=str(OLD / 'commands/run_proposed_first_parent.sh'), tofile=str(P / 'commands/run_proposed_first_parent.sh')))
write(P / 'code/CODE_MANIFEST.json', dict(files=code_rows,
    inherited_manifests=old_code_manifest['inherited_manifests'],
    import_order='V4 complete small overlay > accepted contract-repair overlay > original collector; original native/vendor unchanged',
    no_large_weight_hashes_in_CPU_task=True))
write(P / 'CODE_DIFF.json', dict(files=diff, config_changed_fields=['native.observation_phases'],
    unchanged_runtime_methods_except_reset_step_phase_arguments=True,
    native_scope_hooks_and_journal_unchanged=True, separate_identity_changes=['authorization TASK/RELEASE', 'command package path']))
(P / 'MINIMAL.patch').write_text(''.join(patch))

delta = dict(status='UNAUTHORIZED_CPU_METADATA_QUOTE', observation_clock=[0, 300],
    operation_caps_delta=dict.fromkeys(prior['resource_caps'], 0), source_seed_storage_timeout_delta=0,
    future_scope_naming_calls_max=4515, scope_naming_formula='15 attempts * (1 reset observation + 300 next observations); replacement of old string formatting, no extra observation',
    per_config_validation=dict(canonical_name_calls=301, strict_target_checks=1,
        ordered_allowlist_equality_checks=1, string_element_checks=301, reads_only_small_CONFIG=True),
    future_load_authorization_calls_max=18,
    config_validation_count_formula='launcher metadata + launcher full + reserved metadata + 15 child full = 18; gates use check_documents and do not revalidate config',
    future_config_validation_canonical_calls_max=5418,
    publication_checker_config_validations_per_invocation=1,
    new_helper_SHA_checks_max=16,
    helper_SHA_formula='1 full launcher verification + 15 full child verifications; existing passes, no new large-weight pass',
    new_helper_bytes=ref(P / 'code/observation_phase.py')['size_bytes'],
    config_bytes_old=(OLD / 'config/CONFIG.json').stat().st_size,
    config_bytes_new=(P / 'config/CONFIG.json').stat().st_size,
    postrun_new_runtime_log_fields=0, extra_per_attempt_saved_files=0,
    resource_design_unchanged=True, hardware_calls_in_CPU_preparation=0,
    scope='Only necessary metadata/helper costs from this repair; no batch/storage redesign')
write(P / 'CPU_OBSERVATION_PHASE_DELTA.json', delta)
budget = read(OLD / 'proposal/RESOURCE_BUDGET.json')
budget['observation_phase_CPU_delta'] = delta
write(P / 'proposal/RESOURCE_BUDGET.json', budget)
assert (P / 'proposal/SOURCE_PROPOSAL.json').read_bytes() == (OLD / 'proposal/SOURCE_PROPOSAL.json').read_bytes()
for name in ['INPUT_MANIFEST.json', 'EXTERNAL_SOURCE_MANIFEST.json']:
    # Preserve the accepted input/driver closure without following large references.
    (P / name).write_bytes((OLD / name).read_bytes())
prep_files = [B / 'tasks/A11_OBSERVATION_PHASE_CPU_REPAIR_V1.md',
    B / 'releases/P00_A_OBSERVATION_PHASE_CPU_REPAIR_V1.json',
    B / 'manifests/A11_COMMON_POOL_FIRST_PARENT_V3_FAILURE_ACCEPTANCE.json',
    B / 'releases/P11_A_COMMON_POOL_FIRST_PARENT_V3_CLOSED.json',
    P / 'CPU_OBSERVATION_PHASE_DELTA.json']
old_preparation = read(OLD / 'PREPARATION_INPUT_MANIFEST.json')
write(P / 'PREPARATION_INPUT_MANIFEST.json', dict(files=[ref(f) for f in prep_files] + old_preparation['files'],
    inherited_manifests=old_preparation['inherited_manifests'],
    previous_consumed_V3_evidence_preserved=True))

proposal = copy.deepcopy(prior)
task, release = 'A11_COMMON_POOL_FIRST_PARENT_V4', 'P11_A_COMMON_POOL_FIRST_PARENT_V4'
proposal['task_id'] = task
proposal['authorization_identity'] = {k: v.replace('_V3', '_V4') if type(v) is str else v
                                      for k, v in prior['authorization_identity'].items()}
proposal['paths'] = {k: v.replace('_V3', '_V4') for k, v in prior['paths'].items()}
proposal.update(cwd=str(P), command=['bash', str(P / 'commands/run_proposed_first_parent.sh'), str(B / 'releases' / (release + '.json'))],
    observation_phase_CPU_delta_ref=ref(P / 'CPU_OBSERVATION_PHASE_DELTA.json'),
    preceding_consumed_attempt=dict(task_id='A11_COMMON_POOL_FIRST_PARENT_V3', command_invocations=1, claim_count=1,
        normal_attempts=1, model_initializations=1, language_embedding_forwards=1,
        initialization_native_resets=51, initialization_physics_substeps=25500,
        valid_training_samples=0, unused_caps_reusable=False,
        closure_ref=ref(B / 'releases/P11_A_COMMON_POOL_FIRST_PARENT_V3_CLOSED.json')),
    current_future_readiness='UNAUTHORIZED V4; same planned parent/source/seed after consumed V3 engineering failure. Only observation phase contract repaired. MJB/full-state qualification still unmeasured and must occur inside this parent.')
for key, rel in [('config', 'config/CONFIG.json'), ('budget', 'proposal/RESOURCE_BUDGET.json'),
    ('code_manifest', 'code/CODE_MANIFEST.json'), ('input_manifest', 'INPUT_MANIFEST.json'),
    ('external_manifest', 'EXTERNAL_SOURCE_MANIFEST.json'), ('preparation_manifest', 'PREPARATION_INPUT_MANIFEST.json'),
    ('command_ref', 'commands/run_proposed_first_parent.sh')]:
    proposal[key] = ref(P / rel)
proposal['command_sha256'] = proposal['command_ref']['sha256']
assert all(proposal[k] == prior[k] for k in ('resource_caps', 'source', 'device', 'storage', 'timeouts', 'branch_order'))
assert all(not Path(v).exists() and not Path(v).is_symlink() for v in proposal['paths'].values())
write(P / 'proposal/PROPOSAL.json', proposal)
rt = read(OLD / 'proposal/RELEASE_TEMPLATE.json')
rt.update(status='UNAUTHORIZED_TEMPLATE', identity=proposal['authorization_identity'], release_id=release,
    task_ids=[task], paths=proposal['paths'], proposal_sha256=ref(P / 'proposal/PROPOSAL.json')['sha256'])
rt['storage_admission']['run_id'] = proposal['authorization_identity']['run_id']
write(P / 'proposal/RELEASE_TEMPLATE.json', rt)
control = read(OLD / 'proposal/CONTROL_TEMPLATE.json')
control.update(active_compute_release='releases/' + release + '.json', active_compute_release_id=release,
    active_compute_task_ids=[task], allowed_task_ids=[task], per_task_compute_limits={task: proposal['resource_caps']})
write(P / 'proposal/CONTROL_TEMPLATE.json', control)
board = read(OLD / 'proposal/BOARD_TEMPLATE.json')
board['tasks'][0].update(id=task, release='releases/' + release + '.json',
    **{k: proposal['authorization_identity'][k] for k in ('run_id', 'wave_id', 'shard_id')})
write(P / 'proposal/BOARD_TEMPLATE.json', board)
write(P / 'CAPS_IDENTITY_DIFF.json', dict(status='PASS', unchanged_caps=116, cap_changes=0,
    source_exact_equal=True, source_file_bytes_equal=True, seed_changed=False, timeouts_equal=True,
    storage_equal=True, device_equal=True, branch_order_equal=True, old_paths=prior['paths'], new_paths=proposal['paths'],
    future_paths_absent=True, V3_already_executed_and_closed=True,
    V4_requires_new_independent_release=True, supplementary_protocol_ref_unchanged=proposal['supplementary_protocol_ref'] == prior['supplementary_protocol_ref'],
    sidecar_ref_unchanged=proposal['sidecar_ready'] == prior['sidecar_ready'],
    native_scope_and_render_hooks_original=ref(O / 'code/native/native_egl.py')))
print(json.dumps(dict(status='FROZEN_UNAUTHORIZED_V4', own_code_files=len(code_rows),
    changed_python_files=[x['relative_path'] for x in diff if x['change'] != 'same_bytes_new_package'],
    proposal=ref(P / 'proposal/PROPOSAL.json'), future_paths_created=0), ensure_ascii=False))
