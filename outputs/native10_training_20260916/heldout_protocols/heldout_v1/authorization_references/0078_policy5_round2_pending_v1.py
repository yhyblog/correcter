"""Metadata-only proposal for the separately released final A4000 policy wave.

This module cannot create a runnable protocol, release a stage, import a model,
reserve resources, or execute simulation.  Historical READY v7 is an immutable
source of original input/statistical identities, never a current authorization.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re

from . import storage
from .protocol import TASKS, canonical_hash, protocol_digest

STAGE = 'round2_development_policy'
SCHEMA = 'native10_policy_deployment_round2_v1'
ARMS = ['continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post']
REFERENCES = {
    'decision': ('coordination/NATIVE10_ROUND2_POLICY5_DECISION.md',
        'c9b0ccf1d9265626efbdc7c8dc556268766cfbd8a8f97548d3ae4844617c96e0'),
    'model_review': ('analysis/final_trained_model_review.json',
        '51dc687f285e92c0b81032bad5694ebca7f649fba597e121943362871305a928'),
    'historical_ready': ('outputs/native10_training_20260916/policy_protocols/round1_policy_v1/coordination/NATIVE10_ANALYSIS_READY.json',
        'f389390cfe8f05b83a00be66c7b823e2d4ba1c2f3247298b4e5ffa8487220f76'),
    'historical_policy_config': ('outputs/native10_training_20260916/policy_protocols/round1_policy_v1/config.json',
        '56d0d31f1722f0cc1a974303219953e7340e7887f94c6d760c90739f3b64b06e'),
    'historical_inputs': ('outputs/native10_training_20260916/preparation/policy5_inputs_v1/complete.json',
        '9bc90fb1b0dc6e9a55837b4dc898959e2435d1197778dbf0af8c73d206b58ac3'),
}
MODEL_SEAL = '864c00cfa1cfcbcc8736a898ab22e5afa821f15afbe2b8dc687f7731f2eea83e'
SELECTED_SEAL = 'f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a'
IDS_SHA = '7febdc814dee2c203378865a8371de6698bc727e783ee537312dce734a37db89'


def read(path):
    return json.loads(Path(path).read_text())


def checked(path, digest):
    path = Path(path).resolve()
    if not isinstance(digest, str) or len(digest) != 64 or storage.sha256(path) != digest:
        raise ValueError('Metadata binding SHA changed: '+str(path))
    return path


def _seal(path, digest, *, verify_files=False):
    """Check an immutable seal; full byte inventory only when explicitly requested."""
    path = Path(path).resolve()
    record = read(checked(path/'complete.json', digest))
    if record.get('status') != 'complete' or not isinstance(record.get('files'), dict):
        raise ValueError('Completed metadata seal required')
    if verify_files:
        for name, value in record['files'].items():
            target = (path/name).resolve()
            if not target.is_relative_to(path):
                raise ValueError('Sealed file escapes its directory')
            checked(target, value)
    return record


def _original_inputs(template, original_policy, input_path, input_sha):
    """Reuse the sealed identity-only manifest, never read source/bank outcomes."""
    _seal(input_path, input_sha, verify_files=True)
    binding, rows, summary = (read(input_path/name) for name in
                              ('binding.json', 'sources.json', 'result.json'))
    old = binding['old_collection']
    config = read(checked(old['config_path'], template['input_config_sha256']))
    freeze = read(checked(old['freeze_path'], template['input_freeze_sha256']))
    if (old['config_sha256'] != template['input_config_sha256']
            or old['freeze_sha256'] != template['input_freeze_sha256']
            or freeze.get('config_sha256') != old['config_sha256']
            or freeze.get('files', {}).get(old['config_path']) != old['config_sha256']
            or protocol_digest(config) != config['analysis_approval']['protocol_sha256']
            or old['bank_version'] != 'round1_labels_v1'
            or original_policy['policy_deployment']['old_collection'] != old
            or original_policy['policy_preparation']['inputs'] !=
                dict(path=str(input_path), seal_sha256=input_sha)):
        raise ValueError('Original collection/input provenance changed')
    lookup = {row['episode_id']: row for row in config['episode_manifest']}
    ids = [key for key in config['main_collection']['banks']['round1_labels_v1']['episode_ids']
           if lookup[key]['split'] == 'development']
    expected = [f'{TASKS[index % 5]}__{2026111600+index}' for index in range(100)]
    if (ids != expected or template['episode_ids'] != ids or canonical_hash(ids) != IDS_SHA
            or template['episode_ids_canonical_sha256'] != IDS_SHA
            or [row['case']['episode_id'] for row in rows] != ids
            or summary.get('status') != 'passed' or summary.get('planned_source_ids') != ids):
        raise ValueError('Original ordered development 100 identity changed')
    dataset = template['development_dataset']
    _seal(dataset['path'], dataset['seal_sha256'])
    audit = read(checked(dataset['input_audit_path'], dataset['input_audit_sha256']))
    if (audit.get('status') != 'passed' or audit.get('purpose') != 'development'
            or audit.get('dataset_seal_sha256') != dataset['seal_sha256']
            or audit.get('manifest_sha256') != canonical_hash(config['episode_manifest'])
            or audit.get('episode_ids') != ids or audit.get('missing_artifacts') != []
            or audit.get('completed_collections_only') is not False
            or dataset['input_protocol_sha256'] != config['analysis_approval']['protocol_sha256']
            or any(audit.get('checks', {}).get(key) is not True for key in
                   ('source_seals', 'bank_seals', 'scene_identity', 'replacement_chain', 'complete_labels'))):
        raise ValueError('Original development dataset audit identity changed')
    artifacts = {row['path']: row['sha256'] for row in audit['artifacts']}
    resolutions = {row['planned_slot_id']: row for row in audit['slot_resolutions']}
    if len(artifacts) != len(audit['artifacts']) or set(resolutions) != set(ids):
        raise ValueError('Historical audit has duplicate/missing identities')
    reached, common, scenes, source_bindings = [], [], set(), {}
    for row in rows:
        case = row['case']; identity = case['episode_id']; cut = row['cuts']
        if case != lookup[identity] or case.get('round') is not None:
            raise ValueError('Source case identity cannot be relabelled round2')
        scene = (case['task'], row['scene_fingerprint'])
        if scene in scenes:
            raise ValueError('Duplicate original scene identity')
        scenes.add(scene)
        source = storage.ROOT/'sources'/case['case_id']
        resolution = storage.ROOT/'slot_resolution'/identity
        if row['source_path'] != str(source) or row['resolution_path'] != str(resolution):
            raise ValueError('Original source paths changed')
        ss, rs = row['source_seal_sha256'], row['resolution_seal_sha256']
        if artifacts.get(str(source/'complete.json')) != ss:
            raise ValueError('Source seal differs from original input audit')
        _seal(source, ss)
        resolution_seal = _seal(resolution, rs)
        resolved = read(checked(resolution/'resolution.json', resolution_seal['files']['resolution.json']))
        if (resolved.get('resolved_episode_id') != identity or resolved.get('ordered_rejections') != []
                or resolved.get('source_seal_sha256') != ss
                or resolutions[identity] != dict(planned_slot_id=identity,
                    resolved_episode_id=identity, preceding_rejections=[])):
            raise ValueError('Original resolution or replacement identity changed')
        if cut:
            if len(cut) != 1 or row['common_outcome'] is not None:
                raise ValueError('Only one original cut, without outcome-dependent metadata, is allowed')
            bank = storage.ROOT/'banks/round1_labels_v1'/case['case_id']/f'cut{cut[0]:03d}'
            bs = row['old_bank_seal_sha256']
            if row['old_bank_path'] != str(bank) or artifacts.get(str(bank/'complete.json')) != bs:
                raise ValueError('Original candidate-bank seal identity changed')
            _seal(bank, bs); reached.append(identity)
        else:
            if (type(row['common_outcome']) is not bool or row['old_bank_path'] is not None
                    or row['old_bank_seal_sha256'] is not None):
                raise ValueError('No-cut slots require the known common outcome only')
            common.append(row['common_outcome'])
        source_bindings[identity] = {key: row[key] for key in
            ('source_seal_sha256', 'resolution_seal_sha256', 'old_bank_seal_sha256')}
    if (len(reached) != 95 or len(common) != 5 or sum(common) != 4
            or source_bindings != binding['source_bindings']
            or source_bindings != original_policy['policy_deployment']['source_bindings']
            or dict(Counter(row['case']['task'] for row in rows)) != {task: 20 for task in TASKS}):
        raise ValueError('Original 95 cuts / 5 common / source provenance changed')
    return binding, rows, reached


def _selected(review_ref, reached):
    review = read(checked(review_ref['path'], review_ref['sha256']))
    b = review['bindings']; root = storage.ROOT/'models/final/final_fit_v1'; selected = root/'selected'
    if (review.get('status') != 'passed' or review.get('blockers') != []
            or (review['selection'].get('path'), review['selection'].get('step')) != ('A', 4000)
            or b['model_directory'] != str(root) or b['selected_directory'] != str(selected)
            or b['model_complete_sha256'] != MODEL_SEAL or b['selected_complete_sha256'] != SELECTED_SEAL):
        raise ValueError('Approved final A4000 model review identity changed')
    complete = _seal(root, MODEL_SEAL)
    if complete.get('role') != 'native10_final_two_path_training' or complete.get('phase') != 'final':
        raise ValueError('Final model seal has wrong role')
    for name, digest in [('result.json', b['model_result_sha256']),
                         ('selected/complete.json', SELECTED_SEAL),
                         ('selected_reload_audit.json', b['selected_reload_audit_sha256'])]:
        if complete['files'].get(name) != digest:
            raise ValueError('Model metadata differs from final training seal')
        checked(root/name, digest)
    result = read(root/'result.json')
    if (result.get('status') != 'complete' or result.get('phase') != 'final'
            or result.get('optimizer_updates') != 32000 or result.get('simulator_calls') != 0
            or result['selection'].get('path') != 'A' or result['selection'].get('step') != 4000
            or result.get('selected_assets') != str(selected)):
        raise ValueError('Final selected model or 32000-update completion differs')
    export = _seal(selected, SELECTED_SEAL, verify_files=True)
    checked(selected/'ranking.json', b['selected_ranking_sha256'])
    checked(selected/'config.json', b['selected_config_sha256'])
    ranking = read(selected/'ranking.json'); hashes = ranking.get('model_hashes', {})
    if (export.get('role') != 'four_member_critic_export' or set(hashes) != {'0', '1', '2', '3'}
            or ranking.get('horizon') != 10 or ranking.get('a0_slot') != 0
            or any(hashes != row.get('model_hashes') for row in (export, complete, result, review))):
        raise ValueError('Four selected member identities disagree')
    models = review['selected_models']
    if [row.get('member') for row in models] != list(range(4)):
        raise ValueError('Review must identify exactly four ordered final members')
    for member, model in enumerate(models):
        relative = f'models/refit/member_{member}/selected.pt'
        if (model.get('path') != str(selected/relative) or model.get('sha256') != hashes[str(member)]
                or export['files'].get(relative) != hashes[str(member)]
                or model.get('exact_tensor_match_to_A4000_checkpoint') is not True):
            raise ValueError('Selected checkpoint bytes differ from reviewed A4000')
    reload = read(root/'selected_reload_audit.json')
    if (reload.get('status') != 'passed' or reload.get('source_count') != 95
            or reload.get('episode_ids') != reached or reload.get('members_checked') != 4
            or reload.get('gradient_slots') != [0, 11]
            or any(reload.get(key) is not True for key in ('feature_cache_bit_exact',
                'thirteen_candidate_member_probability_bit_exact', 'member_and_ensemble_gradient_bit_exact',
                'a0_anchor_exactly_zero', 'state_and_anchor_immutable'))):
        raise ValueError('Canonical trained-model reload audit is incomplete')
    critic = dict(path='A', step=4000, members=4, directory=str(selected),
        training_model_seal=dict(path=str(root/'complete.json'), sha256=MODEL_SEAL),
        selected_seal=dict(path=str(selected/'complete.json'), sha256=SELECTED_SEAL),
        selected_reload_audit=dict(path=str(root/'selected_reload_audit.json'),
                                   sha256=b['selected_reload_audit_sha256']),
        member_checkpoint_sha256=[hashes[str(index)] for index in range(4)], model_review=review_ref)
    binding = dict(path=str(root), seal_sha256=MODEL_SEAL, selected_seal_sha256=SELECTED_SEAL,
        selected_reload_audit_sha256=b['selected_reload_audit_sha256'], model_review=review_ref)
    return critic, binding


def pending(*, version='round2_policy_pending_v1'):
    """Write only a new sealed PENDING proposal; no READY/config/release is emitted."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', version):
        raise ValueError('Use an isolated, simple preparation version')
    output = storage.ROOT/'policy_preparations'/version
    if output.exists():
        raise FileExistsError(output)
    refs = {key: dict(path=str(checked(storage.PACKAGE/path, digest)), sha256=digest)
            for key, (path, digest) in REFERENCES.items()}
    historical = read(refs['historical_ready']['path'])
    if historical.get('version') != 7:
        raise ValueError('The immutable provenance template must be historical READY v7')
    template = historical['round1_development_policy']
    expected = dict(scope='round1_development_policy', stage='round1_development_policy',
        simulator_attempts_limit=2100, expected_simulator_attempts=1995, optimizer_updates_limit=0,
        capture_attempts_limit=0, initialization_replacements_allowed=False,
        development_primary_slots=100, evaluation_unique_initial_states_per_task=20,
        reached_cut_sources=95, common_no_alarm_sources=5, common_success_sources=4,
        common_failure_sources=1, paired_suffixes_per_state=4, per_arm_outcome_denominator=400, arms=ARMS)
    if any(template.get(key) != value for key, value in expected.items()):
        raise ValueError('Historical policy contract is not the original five-arm design')
    original = read(refs['historical_policy_config']['path'])
    old, rows, reached = _original_inputs(template, original,
        Path(refs['historical_inputs']['path']).parent, refs['historical_inputs']['sha256'])
    critic, trained = _selected(refs['model_review'], reached)
    contract = deepcopy(template)
    contract.update(scope=STAGE, stage=STAGE, status='pending_engineering_no_release', selected_critic=critic,
        guard_cpu_evidence=None, final_runner_integration_required=True,
        final_runner_already_frozen_at_release=False,
        future_stages_locked=['calibration', 'heldout', 'additional_training', 'additional_policy_waves'])
    binding = dict(schema=SCHEMA, old_collection=old['old_collection'], selected_training=trained,
                   source_bindings=old['source_bindings'])
    result = dict(schema='native10_policy5_round2_pending_v1', status='pending', runnable=False,
        released_scope=[], stage=STAGE, version=version, original_source_collection='round1_v1',
        candidate_generation_round=2, planned_source_ids=template['episode_ids'],
        planned_source_ids_sha256=IDS_SHA, source_count=100, reached_cut_sources=95,
        common_no_alarm_sources=5, common_success_sources=4, common_failure_sources=1,
        original_source_and_bank_seal_identifiers_verified=195, resolution_identities_verified=100,
        model_checkpoint_bytes_verified=4, model_deserialization_performed=False,
        full_historical_tensor_audit_repeated=False, source_or_branch_outcome_files_read=False,
        inherited_outcome_values='only the five already-known no-cut common outcomes',
        expected_simulator_attempts=1995, simulator_attempts_limit=2100,
        workflow_simulator_limit=50000, decision_starting_simulator_attempts=42874,
        workflow_optimizer_limit=51200, decision_starting_optimizer_updates=51200,
        automatic_retries_allowed=False, capture_allowed=False, replacement_allowed=False,
        old_guided_action_reuse_allowed=False, simulator_calls=0, optimizer_updates=0, model_calls=0,
        required_before_execution=['new guard/prepare/runner/auditor CPU evidence at unchanged code SHA',
            'new live READY explicitly releasing round2_development_policy and binding this proposal',
            'new independent config/code/READY/evidence freeze and runtime identity validation'],
        historical_ready_is_authorization=False, ready_contract_canonical_sha256=canonical_hash(contract),
        code_sha256={str(Path(__file__).resolve()): storage.sha256(__file__),
                     str(Path(__file__).with_name('test_policy5_round2_pending_v1.py').resolve()):
                         storage.sha256(Path(__file__).with_name('test_policy5_round2_pending_v1.py'))})
    # Check mutable review/decision paths again before creating any deliverable.
    for ref in refs.values():
        checked(ref['path'], ref['sha256'])
    output.mkdir(parents=True, exist_ok=False)
    for name, value in [('ready_contract.json', contract), ('binding.json', binding),
                        ('sources.json', rows), ('provenance.json', dict(references=refs,
                        historical_ready_usage='immutable metadata template only; not current authorization')),
                        ('result.json', result)]:
        storage.dump(output/name, value)
    storage.seal(output, role='policy5_round2_pending_metadata_only', runnable=False,
                 simulator_calls=0, optimizer_updates=0, model_calls=0)
    return dict(path=str(output), seal_sha256=storage.sha256(output/'complete.json'),
        ready_contract_path=str(output/'ready_contract.json'),
        ready_contract_sha256=storage.sha256(output/'ready_contract.json'),
        binding_path=str(output/'binding.json'), sources_path=str(output/'sources.json'),
        status='pending', runnable=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='round2_policy_pending_v1')
    args = parser.parse_args()
    print(json.dumps(pending(version=args.version), indent=2))


if __name__ == '__main__':
    main()
