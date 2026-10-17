"""Zero-resource final-selection metadata, with a separate explicit release gate.

Preparation creates no deployment authorization. No model/PCA/environment code is
imported or called. The actual seal requires a new READY binding the exact pending
payload, current CPU evidence and code; it never releases heldout execution.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from . import storage
from .prepare_fit import checked, sealed_directory
from .calibration_prepare_v1 import (authorization_references,
    snapshot_authorization_references, verify_authorization_inventory,
    original_slots, GLOBAL_ACCEPTANCE, ARMS)
from .protocol import canonical_hash

CODE = Path(__file__).resolve().parent
STAGE = SCOPE = 'calibration_selection_seal'
SCHEMA = 'native10_final_selection_v1'
ROLE = 'native10_final_selection_metadata_v1'
PENDING_ROLE = 'native10_final_selection_pending_v1'
DECISION = 'coordination/NATIVE10_FINAL_SELECTION_AND_HELD_PREPARATION_DECISION.md'
DECISION_SHA = '7b50be9baff4a7eca49607bda0a91f7b24e597fb95d65add765803daf70cbf24'
CONFIG_SHA = 'c04125ae474316783e7dd6ca74c799d5441299801f22cd0910889f98511d7382'
FREEZE_SHA = 'd181899e5ccf70177db5fee6267ec9f102f4aae6e437e42f7a0eb86dc9800d1e'
AUDIT_SEAL = '6e1568c11fc52d3f1cb1ce43e41f51be5b218faa8ddcab0fbc3183e090a70d25'
AUDIT_RESULT = '454d323a64fe87516dcbf10c34435de6c58d1536d0cbb59dca1cfb1a2d55adc5'
INDEPENDENT_SEAL = '1f5b59dabae1315019f0776ec0b9ecafa0f3e5ad21a90e6c979e96232e0acd98'
INDEPENDENT_RESULT = 'baeb54b0d152bef70d7b5afe051f6d534f1d2ec8dc7dd449be01967d475252b2'
SELECTED_SEAL = 'f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a'
SCIENCE_KEYS = ('source_horizon', 'prefix_horizon', 'suffix_horizon', 'control_budget',
    'gate_threshold', 'guidance', 'matching', 'command_semantics', 'seed_namespace')
COMPARISONS = ('alarm_replan10_minus_continue_native10',
    'velocity_minus_alarm_replan10', 'direct_minus_alarm_replan10',
    'post_minus_alarm_replan10', 'velocity_minus_continue_native10',
    'direct_minus_continue_native10', 'post_minus_continue_native10')
ZERO = dict(model_calls=0, simulator_calls=0, optimizer_updates=0, pca_fits=0)


def read(path):
    return json.loads(Path(path).read_text())


def reference(path, digest=None):
    path = Path(path).resolve()
    digest = digest or storage.sha256(path)
    checked(path, digest)
    return dict(path=str(path), sha256=digest)


def expected_directory():
    return storage.ROOT/'final_selections/final_selection_v1'


def _sealed_result(directory, seal_sha, result_sha):
    """Check the already-audited metadata, not repeat its trajectory audit."""
    directory = Path(directory)
    seal = read(checked(directory/'complete.json', seal_sha))
    if seal.get('status') != 'complete' or seal.get('files', {}).get('result.json') != result_sha:
        raise ValueError('Result is not bound by the expected completed audit')
    return read(checked(directory/'result.json', result_sha))


def _default_review(name):
    return reference(storage.PACKAGE/'analysis'/name)


def build_payload(*, result_review=None, completion_review=None):
    """Read/hash completed metadata only; never write a selection or recompute Q."""
    config_ref = reference(storage.ROOT/'calibration_protocols/calibration_v1/config.json', CONFIG_SHA)
    freeze_ref = reference(Path(config_ref['path']).with_name('freeze.json'), FREEZE_SHA)
    cfg, frozen = read(config_ref['path']), read(freeze_ref['path'])
    if frozen.get('files', {}).get(config_ref['path']) != CONFIG_SHA:
        raise ValueError('Calibration freeze must bind the exact scientific configuration')
    decision = reference(storage.PACKAGE/DECISION, DECISION_SHA)
    analysis = reference(storage.PACKAGE/'coordination/NATIVE10_CALIBRATION_ANALYSIS.md')
    result_review = deepcopy(result_review or _default_review('calibration_result_review.json'))
    completion_review = deepcopy(completion_review or _default_review('calibration_completion_review.json'))
    rr, cr = [read(checked(x['path'], x['sha256'])) for x in (result_review, completion_review)]
    audit_dir = storage.ROOT/'calibration_audits/calibration_v1'
    independent_dir = storage.ROOT/'calibration_independent_audits/calibration_v1'
    audit = _sealed_result(audit_dir, AUDIT_SEAL, AUDIT_RESULT)
    independent = _sealed_result(independent_dir, INDEPENDENT_SEAL, INDEPENDENT_RESULT)
    ids = [x['episode_id'] for x in original_slots(cfg)]
    proposal = audit['selection_proposal']
    if (audit.get('status') != 'passed' or audit.get('planned_slots') != 100
            or audit.get('technical_missing') != 0 or audit.get('logical_outcomes_per_arm') != 200
            or audit.get('config_sha256') != CONFIG_SHA or audit.get('freeze_sha256') != FREEZE_SHA
            or audit['statistics']['primary_ids'] != ids or proposal.get('method') != 'post'
            or proposal.get('post_enabled_on_alarm') is not True
            or proposal.get('paired_success_difference') != 14
            or proposal.get('mean_source_post_minus_replan') != .07
            or proposal.get('rule') != GLOBAL_ACCEPTANCE
            or proposal.get('ci_used') is not False or proposal.get('q_used') is not False):
        raise ValueError('Require completed original 100-source strict-positive post proposal')
    if (rr.get('status') != 'passed_independent_static_statistics_and_proposal_review'
            or rr.get('inputs', {}).get('audit_result') != reference(audit_dir/'result.json', AUDIT_RESULT)
            or rr.get('inputs', {}).get('audit_complete') != reference(audit_dir/'complete.json', AUDIT_SEAL)
            or rr.get('proposal_check', {}).get('recomputed_net_successes') != 14
            or rr['proposal_check'].get('recomputed_mean') != .07
            or rr['proposal_check'].get('proposed_post_enabled') is not True
            or rr['proposal_check'].get('use_of_ci_q_or_secondary_method_ranking') is not False
            or cr.get('status') != 'passed_bounded_completion_resource_scene_review'
            or cr.get('blockers') != []
            or cr.get('bindings', {}).get('config_sha256') != CONFIG_SHA
            or cr['bindings'].get('freeze_sha256') != FREEZE_SHA
            or independent.get('status') != 'passed'
            or independent.get('primary_audit_comparison', {}).get('exact') is not True
            or independent['primary_audit_comparison'].get('sha256') != AUDIT_RESULT):
        raise ValueError('Require actual passed independent result and completion reviews')
    model = cfg['calibration_collection']['selected_training']
    parent = Path(model['path']); selected = Path(cfg['critic_assets'])
    if (selected != parent/'selected' or model['selected_seal_sha256'] != SELECTED_SEAL
            or cfg['calibration_collection']['global_acceptance'] != GLOBAL_ACCEPTANCE):
        raise ValueError('Fixed A4000 model or acceptance definition changed')
    selected_seal = reference(selected/'complete.json', SELECTED_SEAL)
    ss = read(selected_seal['path'])
    member_hashes = cfg['main_collection']['banks']['calibration_policy_v1']['critic_member_hashes']
    members = []
    for i in range(4):
        name = f'models/refit/member_{i}/selected.pt'
        if ss.get('files', {}).get(name) != member_hashes[str(i)]:
            raise ValueError('Selected seal/member identity mismatch')
        members.append(reference(selected/name, member_hashes[str(i)]))
    critic = dict(path='A', step=4000, members=4, selected_directory=str(selected),
        selected_seal=selected_seal,
        training_model_seal=reference(parent/'complete.json', model['seal_sha256']),
        selected_reload_audit=reference(parent/'selected_reload_audit.json', model['selected_reload_audit_sha256']),
        member_checkpoints=members, model_review=deepcopy(model['model_review']))
    science = {k: deepcopy(cfg[k]) for k in SCIENCE_KEYS}
    evidence = dict(main_audit_seal=reference(audit_dir/'complete.json', AUDIT_SEAL),
        main_audit_result=reference(audit_dir/'result.json', AUDIT_RESULT),
        independent_seal=reference(independent_dir/'complete.json', INDEPENDENT_SEAL),
        independent_result=reference(independent_dir/'result.json', INDEPENDENT_RESULT),
        source_records=reference(audit_dir/'source_records.json'),
        budget_snapshot=reference(audit_dir/'budget_snapshot.jsonl'),
        scene_registry_snapshot=reference(audit_dir/'scene_registry_snapshot.jsonl'),
        result_review=result_review, completion_review=completion_review,
        decision=decision, analysis=analysis)
    payload = dict(schema=SCHEMA, status='pending_selection_seal', stage=STAGE, scope=SCOPE,
        method='post', post_enabled_on_alarm=True, primary_comparison='post_minus_alarm_replan10',
        secondary_comparisons=[x for x in COMPARISONS if x != 'post_minus_alarm_replan10'],
        physical_methods=list(ARMS), scientific_parameters=science,
        calibration_config=config_ref, calibration_freeze=freeze_ref,
        matching=deepcopy(science['matching']), guidance=deepcopy(science['guidance']),
        command_semantics=deepcopy(science['command_semantics']),
        fixed_critic=critic, selected_critic=deepcopy(critic), calibration_evidence=evidence,
        selection_basis=dict(rule=deepcopy(GLOBAL_ACCEPTANCE), primary_ids=ids,
            primary_ids_canonical_sha256=canonical_hash(ids), source_denominator=100,
            logical_outcomes_per_arm=200, net_success_difference=14, mean_source_difference=.07,
            no_alarm='retain common native10 outcome; paired difference zero',
            q_used=False, ci_used=False, task_routing=False, new_method_selection=False),
        complete_matching_dependencies=['velocity', 'direct', 'post', 'reverse', 'random'],
        expected_directory=str(expected_directory()), heldout_release=False,
        heldout_reads=0, heldout_mutations=0, **ZERO)
    _check_references(payload)
    return payload


def _check_references(value):
    rows = authorization_references(value)
    for row in rows:
        checked(row['original_path'], row['sha256'])
    return rows


def validate_payload(payload):
    refs = payload['calibration_evidence']
    expected = build_payload(result_review=refs['result_review'], completion_review=refs['completion_review'])
    if payload != expected:
        raise ValueError('Pending scientific payload differs from fixed completed evidence')
    return payload


def code_files():
    return {str(CODE/name): storage.sha256(CODE/name) for name in (
        'final_selection_v1.py', 'test_final_selection_v1.py', 'calibration_prepare_v1.py',
        'prepare_fit.py', 'protocol.py', 'storage.py')}


def prepare_pending(*, result_review=None, completion_review=None, version='final_selection_pending_v1'):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,70}', version):
        raise ValueError('Use a safe new pending version')
    payload = build_payload(result_review=result_review, completion_review=completion_review)
    dest = storage.ROOT/'final_selection_preparations'/version
    dest.mkdir(parents=True, exist_ok=False)
    storage.dump(dest/'payload.json', payload)
    storage.dump(dest/'result.json', dict(status='pending_only', runnable=False,
        selection_seal_created=False, heldout_release=False, code_files=code_files(), **ZERO))
    storage.seal(dest, role=PENDING_ROLE, **ZERO)
    return dict(status='pending_selection_seal', expected_directory=str(expected_directory()),
        preparation=dict(path=str(dest), seal_sha256=storage.sha256(dest/'complete.json')),
        payload=reference(dest/'payload.json'))


def validate_pending_binding(binding):
    if (binding.get('status') != 'pending_selection_seal'
            or binding.get('expected_directory') != str(expected_directory())):
        raise ValueError('Explicit pending-only selection binding required')
    prep = binding['preparation']; path = Path(prep['path']).resolve()
    if not path.is_relative_to((storage.ROOT/'final_selection_preparations').resolve()):
        raise ValueError('Pending selection is outside its isolated preparation directory')
    sealed = sealed_directory(path, prep['seal_sha256'])
    if sealed.get('role') != PENDING_ROLE or binding['payload']['path'] != str(path/'payload.json'):
        raise ValueError('Wrong pending artifact role or payload location')
    return validate_payload(read(checked(binding['payload']['path'], binding['payload']['sha256'])))


def cpu_checks(paths):
    required = {str(CODE/'final_selection_v1.py'), str(CODE/'test_final_selection_v1.py')}
    coverage = {}
    for directory in paths:
        directory = Path(directory).resolve()
        sealed_directory(directory, storage.sha256(directory/'complete.json'))
        row = read(directory/'result.json'); after = row.get('code_sha256_after', {})
        if (row.get('status') != 'passed' or row.get('returncode') != 0
                or row.get('shell_returncode', 0) != 0 or not after
                or row.get('code_sha256_before') != after
                or any(row.get(k) != 0 for k in ('model_calls', 'simulator_calls', 'optimizer_updates'))
                or row.get('pca_fits', 0) != 0):
            raise ValueError('Require current passing zero-resource CPU evidence')
        for name, digest in after.items():
            checked(name, digest)
            if name in coverage and coverage[name] != digest:
                raise ValueError('Conflicting CPU coverage')
            coverage[name] = digest
    if not required <= set(coverage):
        raise ValueError('CPU evidence omits this metadata entry or its tests')
    return coverage


def ready_contract(pending_binding, cpu_evidence):
    """Exact future READY[calibration_selection_seal]; does not grant permission."""
    validate_pending_binding(pending_binding)
    coverage = cpu_checks(cpu_evidence)
    return dict(scope=SCOPE, stage=STAGE, schema=SCHEMA,
        simulator_attempts_limit=0, optimizer_updates_limit=0, training_updates=0,
        model_calls_limit=0, pca_fits_limit=0, output_directory=str(expected_directory()),
        pending=deepcopy(pending_binding), cpu_evidence=[dict(path=str(Path(x).resolve()),
            seal_sha256=storage.sha256(Path(x)/'complete.json')) for x in cpu_evidence],
        code_files=code_files(), cpu_coverage=coverage, method='post',
        post_enabled_on_alarm=True, primary_comparison='post_minus_alarm_replan10', heldout_release=False)


def _scope(ready):
    if (ready.get('task_id') != 'native10-training-20260916'
            or not (ready.get('status') == 'approved' or str(ready.get('status', '')).startswith('protocol_approved_'))
            or SCOPE not in ready.get('released_scope', [])):
        raise ValueError('READY has not explicitly released zero-resource selection sealing')
    row = ready.get(STAGE, {})
    for key in ('simulator_attempts_limit', 'optimizer_updates_limit', 'training_updates',
                'model_calls_limit', 'pca_fits_limit'):
        if type(row.get(key)) is not int or row[key] != 0:
            raise ValueError('Selection sealing must bind exact zero resources: '+key)
    if row.get('stage') != STAGE or row.get('scope') != SCOPE or row.get('heldout_release') is not False:
        raise ValueError('Selection scope does not release any heldout execution')


def seal_selection(pending_binding, ready_path, cpu_evidence):
    """Write the actual selection ONLY under a separately issued explicit READY."""
    ready_path = Path(ready_path).resolve(); raw = ready_path.read_bytes()
    ready_sha = hashlib.sha256(raw).hexdigest(); ready = json.loads(raw)
    _scope(ready)  # Fail before reading pending/CPU/model metadata when unreleased.
    payload = validate_pending_binding(pending_binding)
    expected = ready_contract(pending_binding, cpu_evidence)
    if ready.get(STAGE) != expected:
        raise ValueError('READY must bind exact payload/preparation/CPU/code identity')
    refs = _check_references(ready); checked(ready_path, ready_sha)
    dest = expected_directory(); dest.mkdir(parents=True, exist_ok=False)
    snapshot = dest/'NATIVE10_ANALYSIS_READY.json'; snapshot.write_bytes(raw)
    checked(snapshot, ready_sha)
    inventory = snapshot_authorization_references(ready, dest)
    context = dict(analysis_ready=reference(snapshot, ready_sha),
        calibration_preparation=dict(authorization_inventory=reference(dest/'authorization_inventory.json')))
    files = {r['original_path']: r['sha256'] for r in refs}
    files.update({r['snapshot_path']: r['sha256'] for r in inventory['references']})
    files.update(code_files())
    files[str(snapshot)] = ready_sha
    files[str(dest/'authorization_inventory.json')] = storage.sha256(dest/'authorization_inventory.json')
    # The payload carries additional fixed scientific/evidence references. The
    # READY binds its bytes; list each dependency independently in the freeze.
    files.update({r['original_path']: r['sha256'] for r in _check_references(payload)})
    storage.dump(dest/'approved_payload.json', payload)
    files[str(dest/'approved_payload.json')] = storage.sha256(dest/'approved_payload.json')
    frozen = dict(schema='native10_final_selection_dependency_freeze_v1', files=files)
    verify_authorization_inventory(context, frozen)
    storage.dump(dest/'freeze.json', frozen)
    result = dict(deepcopy(payload), status='sealed', role=ROLE,
        approved_payload=reference(dest/'approved_payload.json'),
        pending=deepcopy(pending_binding), authorization_context=context,
        dependency_freeze=reference(dest/'freeze.json'), authorization_ready=reference(snapshot, ready_sha),
        authorization_reference_count=len(inventory['references']),
        cpu_evidence=expected['cpu_evidence'], selection_seal_created=True)
    storage.dump(dest/'result.json', result)
    checked(ready_path, ready_sha)
    for name, digest in files.items(): checked(name, digest)
    storage.seal(dest, role=ROLE, stage=STAGE, heldout_release=False, **ZERO)
    return dict(path=str(dest), seal_sha256=storage.sha256(dest/'complete.json'),
                result_sha256=storage.sha256(dest/'result.json'))


def validate_selection_binding(binding):
    """Verify sealed metadata and all dependencies; never authorize heldout."""
    directory = Path(binding['path']).resolve()
    if directory != expected_directory().resolve():
        raise ValueError('Unexpected actual selection directory')
    complete = sealed_directory(directory, binding['seal_sha256'])
    result = read(checked(directory/'result.json', binding['result_sha256']))
    if (complete.get('role') != ROLE or result.get('status') != 'sealed'
            or result.get('role') != ROLE or result.get('selection_seal_created') is not True):
        raise ValueError('A real completed selection seal is required')
    payload = validate_pending_binding(result['pending'])
    if read(checked(result['approved_payload']['path'], result['approved_payload']['sha256'])) != payload:
        raise ValueError('Actual selection differs from its authorized payload')
    if any(result.get(k) != v for k, v in payload.items() if k != 'status'):
        raise ValueError('Sealed selection changes pending scientific identity')
    context = result['authorization_context']; frozen_ref = result['dependency_freeze']
    frozen = read(checked(frozen_ref['path'], frozen_ref['sha256']))
    for path, digest in frozen['files'].items(): checked(path, digest)
    verify_authorization_inventory(context, frozen)
    if result['authorization_ready'] != context['analysis_ready']:
        raise ValueError('READY identity mismatch')
    ready = read(checked(result['authorization_ready']['path'], result['authorization_ready']['sha256']))
    _scope(ready)
    if ready[STAGE] != ready_contract(result['pending'], [x['path'] for x in result['cpu_evidence']]):
        raise ValueError('Sealed READY does not release these exact inputs')
    return result


load_selection = validate_selection_binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['pending', 'contract', 'seal', 'verify'])
    parser.add_argument('--binding', type=Path)
    parser.add_argument('--ready', type=Path)
    parser.add_argument('--cpu-evidence', type=Path, action='append', default=[])
    parser.add_argument('--version', default='final_selection_pending_v1')
    args = parser.parse_args()
    if args.mode == 'pending': result = prepare_pending(version=args.version)
    elif args.mode == 'contract': result = ready_contract(read(args.binding), args.cpu_evidence)
    elif args.mode == 'seal': result = seal_selection(read(args.binding), args.ready, args.cpu_evidence)
    else: result = validate_selection_binding(read(args.binding))
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
