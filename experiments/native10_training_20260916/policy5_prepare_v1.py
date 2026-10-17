"""Bind existing 100 dev inputs and freeze one separately released policy wave.

Preparation performs file/CPU checks only. It cannot capture, load a policy,
generate a candidate or reserve simulator/optimizer attempts. Original protocols
and every existing output version remain read-only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import tarfile

from . import storage
from .main_collection import POLICY_METHODS
from .prepare_fit import checked, sealed_directory
from .protocol import canonical_hash, protocol_digest, require_stage_budget, validate_protocol


STAGE = 'round1_development_policy'
CODE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def release(ready_path):
    ready = read(ready_path)
    if (ready.get('task_id') != 'native10-training-20260916'
            or not str(ready.get('status', '')).startswith('protocol_approved_')
            or STAGE not in ready.get('released_scope', [])):
        raise ValueError('READY must explicitly release the policy5 stage')
    row = ready.get(STAGE, {})
    expected = dict(scope=STAGE, stage=STAGE, simulator_attempts_limit=2100,
        expected_simulator_attempts=1995, optimizer_updates_limit=0, capture_attempts_limit=0,
        initialization_replacements_allowed=False, development_primary_slots=100,
        evaluation_unique_initial_states_per_task=20, reached_cut_sources=95,
        common_no_alarm_sources=5, common_success_sources=4, common_failure_sources=1,
        paired_suffixes_per_state=4, per_arm_outcome_denominator=400, arms=list(POLICY_METHODS))
    if any(row.get(key) != value for key, value in expected.items()):
        raise ValueError('READY policy5 scope/counts/resources differ from the registered contract')
    selected = row.get('selected_critic', {})
    if (selected.get('path'), selected.get('step'), selected.get('members')) != ('B', 200, 4):
        raise ValueError('Only the previously selected B200 four-member ensemble is released')
    for name in ('training_model_seal', 'selected_seal', 'selected_reload_audit'):
        checked(selected[name]['path'], selected[name]['sha256'])
    ids = row.get('episode_ids', [])
    if len(ids) != 100 or len(set(ids)) != 100 or canonical_hash(ids) != row.get('episode_ids_canonical_sha256'):
        raise ValueError('READY must bind the complete original 100 ordered IDs')
    stats = row.get('statistics', {})
    if (stats.get('bootstrap_draws') != 10000 or stats.get('bootstrap_seed') != 2026091622
            or stats.get('ci') != 'percentile95' or stats.get('quantile_method') != 'linear'):
        raise ValueError('Released descriptive statistics differ from the prepared auditor')
    # Validate every top-level document/review hash when its paired key is a path.
    references = {}
    for key, value in ready.items():
        if not key.endswith('_sha256') or not isinstance(ready.get(key[:-7]), str):
            continue
        name = ready[key[:-7]]; path = Path(name)
        path = path if path.is_absolute() else storage.PACKAGE/path
        references[name] = str(checked(path, value))
    return ready, row, references


def _new(path):
    path = Path(path).resolve()
    if not path.is_relative_to(storage.ROOT.resolve()) or path.is_relative_to((storage.ROOT/'p0').resolve()):
        raise ValueError('Preparation output must be a new workflow artifact outside P0')
    path.mkdir(parents=True, exist_ok=False)
    return path


def cpu_checks(evidence_paths):
    """Require current before/after identity for the actual new entrypoints."""
    required = {str(path.resolve()) for path in (
        Path(__file__), CODE/'policy5_runner_v1.py', CODE/'run_policy5_gpu_v1.sh',
        CODE/'policy_deployment_v1.py', CODE/'policy5_audit_v1.py',
        CODE/'test_policy_deployment_v1.py', CODE/'test_policy5_runner_v1.py',
        storage.PACKAGE/'tests/test_native10_policy5_audit_v1.py',
        storage.PACKAGE/'tests/test_native10_policy5_prepare_v1.py')}
    covered = {}
    for evidence in evidence_paths:
        evidence = Path(evidence).resolve()
        sealed_directory(evidence, storage.sha256(evidence/'complete.json'))
        cpu = read(evidence/'result.json')
        after = cpu.get('code_sha256_after', {})
        if (cpu.get('returncode') != 0 or cpu.get('status') != 'passed' or not after
                or cpu.get('code_sha256_before') != after
                or any(cpu.get(key) != 0 for key in ('model_calls', 'simulator_calls', 'optimizer_updates'))):
            raise ValueError('Final integration CPU evidence must pass at fixed code with zero real work')
        logs = [path for path in evidence.glob('*.log') if 'pytest' in path.name or path.name == 'run.log']
        if not logs or not any('passed' in path.read_text() and 'failed' not in path.read_text().lower() for path in logs):
            raise ValueError('Final integration CPU evidence lacks a passed test log')
        for path, digest in after.items():
            checked(path, digest)
            if path in covered and covered[path] != digest:
                raise ValueError('CPU evidence versions conflict')
            covered[path] = digest
    if not required <= set(covered):
        raise ValueError('CPU evidence omits actual preparation/runner/guard/auditor or their tests')
    return covered


def historical_audit(dataset, old, ids):
    audit = read(checked(dataset['input_audit_path'], dataset['input_audit_sha256']))
    if (audit.get('status') != 'passed' or audit.get('purpose') != 'development'
            or audit.get('dataset_seal_sha256') != dataset['seal_sha256']
            or audit.get('manifest_sha256') != canonical_hash(old['episode_manifest'])
            or audit.get('episode_ids') != ids or audit.get('missing_artifacts') != []
            or audit.get('completed_collections_only') is not False
            or any(audit.get('checks', {}).get(key) is not True for key in
                   ('source_seals', 'bank_seals', 'scene_identity', 'replacement_chain', 'complete_labels'))):
        raise ValueError('Original complete development artifact audit identity differs')
    artifacts = {row['path']: row['sha256'] for row in audit['artifacts']}
    resolutions = {row['planned_slot_id']: row for row in audit['slot_resolutions']}
    if len(artifacts) != len(audit['artifacts']) or set(resolutions) != set(ids):
        raise ValueError('Original artifact/resolution audit has duplicate or missing identities')
    return artifacts, resolutions


def inputs(base_config, ready_path, output):
    ready, approved, _ = release(ready_path)
    base_config = Path(base_config).resolve()
    checked(base_config, approved['input_config_sha256'])
    checked(base_config.with_name('freeze.json'), approved['input_freeze_sha256'])
    old = read(base_config);validate_protocol(old, require_runnable=True)
    registration = old['main_collection']['banks']['round1_labels_v1']
    lookup = {row['episode_id']: row for row in old['episode_manifest']}
    ids = [key for key in registration['episode_ids'] if lookup[key]['split'] == 'development']
    if ids != approved['episode_ids']:
        raise ValueError('READY dev IDs differ from the frozen collection')
    counts = Counter(lookup[key]['task'] for key in ids)
    if dict(counts) != approved['per_task_source_counts'] or set(counts.values()) != {20}:
        raise ValueError('Each original task must have exactly 20 development scenes')
    selected = approved['selected_critic']; trained = Path(selected['training_model_seal']['path']).parent
    sealed_directory(trained, selected['training_model_seal']['sha256'])
    sealed_directory(selected['directory'], selected['selected_seal']['sha256'])
    result = read(trained/'result.json')
    if (result['selection']['path'], result['selection']['step'], result['optimizer_updates']) != ('B', 200, 19200):
        raise ValueError('Training result differs from the fixed selected model')
    dataset = approved['development_dataset']
    sealed_directory(dataset['path'], dataset['seal_sha256'])
    historical, historical_resolutions = historical_audit(dataset, old, ids)
    source_bindings, rows, scenes, common, reached = {}, [], set(), [], []
    for identity in ids:
        case = lookup[identity]; source = storage.ROOT/'sources'/case['case_id']
        resolution = storage.ROOT/'slot_resolution'/identity
        ss = historical[str(source/'complete.json')]
        checked(source/'complete.json', ss)
        rs = storage.sha256(resolution/'complete.json')
        sealed_directory(source, ss);sealed_directory(resolution, rs)
        summary, resolved = read(source/'summary.json'), read(resolution/'resolution.json')
        if (summary['case'] != case or summary['seed_namespace'] != old['seed_namespace']
                or resolved.get('resolved_episode_id') != identity or resolved.get('ordered_rejections') != []
                or resolved.get('source_seal_sha256') != ss or summary.get('outcome_filter_applied') is not False
                or historical_resolutions[identity] != dict(planned_slot_id=identity,
                    resolved_episode_id=identity, preceding_rejections=[])):
            raise ValueError('Original accepted source/resolution identity changed')
        scene = (case['task'], summary['scene_fingerprint'])
        if scene in scenes:
            raise ValueError('Duplicate original task-matched physical initial state')
        scenes.add(scene);bank_path = None;bank_sha = None
        if summary['cuts']:
            cut, = summary['cuts'];reached.append(identity)
            bank_path = storage.ROOT/'banks/round1_labels_v1'/case['case_id']/f'cut{cut:03d}'
            bank_sha = historical[str(bank_path/'complete.json')]
            checked(bank_path/'complete.json', bank_sha);sealed_directory(bank_path, bank_sha)
        else:
            if not summary['no_alarm'] or not summary['full_episode_outcome_available'] or type(summary['success']) is not bool:
                raise ValueError('No-cut source lacks a known full common outcome')
            common.append(summary['success'])
        source_bindings[identity] = dict(source_seal_sha256=ss, resolution_seal_sha256=rs,
                                       old_bank_seal_sha256=bank_sha)
        rows.append(dict(case=case, source_path=str(source), resolution_path=str(resolution),
            old_bank_path=str(bank_path) if bank_path else None, cuts=summary['cuts'],
            scene_fingerprint=summary['scene_fingerprint'], common_outcome=summary['success'] if not summary['cuts'] else None,
            **source_bindings[identity]))
    if len(reached) != 95 or len(common) != 5 or sum(common) != 4:
        raise ValueError('Original 95+5 coverage/common outcomes changed')
    if read(trained/'selected_reload_audit.json')['episode_ids'] != reached:
        raise ValueError('Actual selected reload evidence does not cover the original reached sources')
    binding = dict(schema='native10_policy_deployment_v1',
        old_collection=dict(config_path=str(base_config), config_sha256=storage.sha256(base_config),
            freeze_path=str(base_config.with_name('freeze.json')), freeze_sha256=storage.sha256(base_config.with_name('freeze.json')),
            bank_version='round1_labels_v1'), selected_training=dict(path=str(trained),
            seal_sha256=selected['training_model_seal']['sha256'], selected_seal_sha256=selected['selected_seal']['sha256']),
        source_bindings=source_bindings)
    dest = _new(output)
    storage.dump(dest/'binding.json', binding)
    storage.dump(dest/'sources.json', rows)
    storage.dump(dest/'result.json', dict(status='passed', planned_source_ids=ids,
        planned_source_ids_sha256=canonical_hash(ids), per_task=dict(counts), unique_task_scenes=len(scenes),
        reached_source_ids=reached, common_outcomes=common, input_ready_sha256=storage.sha256(ready_path),
        selected_member_hashes=result['model_hashes'], preparation_code_sha256=storage.sha256(__file__),
        historical_source_and_bank_seals_checked=195, resolution_identities_checked=100,
        development_input_audit_sha256=dataset['input_audit_sha256'],
        capture_allowed=False, replacement_allowed=False, old_guided_action_reuse_allowed=False,
        new_attempts_expected=1995, simulator_calls=0, optimizer_updates=0, real_model_calls=0))
    storage.seal(dest, role='policy5_existing_source_bindings', simulator_attempts=0, optimizer_updates=0)
    return dict(path=str(dest), seal_sha256=storage.sha256(dest/'complete.json'))


def freeze(base_config, ready_path, input_directory, cpu_evidence, *, version, bank_version):
    if not all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', name) for name in (version, bank_version)):
        raise ValueError('Use new safe explicit protocol and bank versions')
    ready, approved, references = release(ready_path)
    base_config = checked(base_config, approved['input_config_sha256'])
    old_frozen = read(checked(base_config.with_name('freeze.json'), approved['input_freeze_sha256']))
    input_directory = Path(input_directory).resolve()
    input_seal = sealed_directory(input_directory, storage.sha256(input_directory/'complete.json'))
    binding = read(input_directory/'binding.json');summary = read(input_directory/'result.json')
    selected = approved['selected_critic']
    expected_training = dict(path=str(Path(selected['training_model_seal']['path']).parent),
        seal_sha256=selected['training_model_seal']['sha256'], selected_seal_sha256=selected['selected_seal']['sha256'])
    if (input_seal.get('role') != 'policy5_existing_source_bindings' or summary.get('status') != 'passed'
            or summary['planned_source_ids'] != approved['episode_ids']
            or summary['planned_source_ids_sha256'] != approved['episode_ids_canonical_sha256']
            or summary['input_ready_sha256'] != storage.sha256(ready_path)
            or binding['old_collection']['config_sha256'] != approved['input_config_sha256']
            or binding['old_collection']['freeze_sha256'] != approved['input_freeze_sha256']
            or binding['selected_training'] != expected_training
            or [summary['selected_member_hashes'].get(str(i)) for i in range(4)] != selected['member_checkpoint_sha256']
            or set(binding['source_bindings']) != set(approved['episode_ids'])):
        raise ValueError('Input manifest was prepared under different release/source bindings')
    original = read(base_config)
    historical, _ = historical_audit(approved['development_dataset'], original, approved['episode_ids'])
    input_rows = read(input_directory/'sources.json')
    if [row['case']['episode_id'] for row in input_rows] != approved['episode_ids']:
        raise ValueError('Frozen input rows differ from the complete ordered source manifest')
    for row in input_rows:
        for name in ('source', 'old_bank'):
            if row[name+'_path'] is not None:
                path = str(Path(row[name+'_path'])/'complete.json')
                digest = binding['source_bindings'][row['case']['episode_id']][name+'_seal_sha256']
                if historical.get(path) != digest:
                    raise ValueError('Input source/bank seal differs from the approved historical audit')
                checked(path, digest)
    cpu_coverage = cpu_checks(cpu_evidence)
    cfg = deepcopy(read(base_config));dest = _new(storage.ROOT/'policy_protocols'/version)
    try:
        snapshots = dest/'coordination';snapshots.mkdir()
        ready_path = Path(ready_path).resolve()
        shutil.copyfile(ready_path, snapshots/ready_path.name)
        checked(snapshots/ready_path.name, storage.sha256(ready_path))
        # Preserve READY verbatim; copy all relative review paths with their layout.
        for name, original in references.items():
            relative = Path(name)
            if relative.is_absolute():
                continue
            target = dest/relative;target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target);checked(target, storage.sha256(original))
        oldreg = cfg['main_collection']['banks']['round1_labels_v1']
        members = summary['selected_member_hashes']
        cfg['critic_assets'] = approved['selected_critic']['directory']
        cfg['main_collection']['banks'] = {bank_version: dict(stage=STAGE, kind='policy5',
            episode_ids=approved['episode_ids'], generation_round=1, cut_selection_policy='analysis_lead_v1',
            random_seed_domain='main_local_labels_v1',
            allowed_source_protocol_sha256=[cfg['analysis_approval']['protocol_sha256']],
            model_hashes={**{key: oldreg['model_hashes'][key] for key in ('vla', 'd', 'g0', 'implementation')},
                          **{'critic_'+key: value for key, value in members.items()}}, critic_member_hashes=members)}
        cfg['policy_deployment'] = binding
        cfg['policy_statistics'] = deepcopy(approved['statistics'])
        cfg['policy_statistics'].update(task_order=sorted(approved['per_task_source_counts']),
            source_order=approved['episode_ids'], primary_inference='within_new_policy5_only')
        cfg['stage_release_scopes'] = {stage: 'not_released_'+stage for stage in cfg['budget']['stages']}
        cfg['stage_release_scopes']['p0'] = 'p0_anchor_and_native10_diagnostics'
        cfg['stage_release_scopes'][STAGE] = STAGE
        cfg['analysis_ready'] = dict(path=str(snapshots/ready_path.name), sha256=storage.sha256(snapshots/ready_path.name))
        cfg['analysis_documents'] = {str(dest/Path(name)): storage.sha256(original)
            for name, original in references.items() if not Path(name).is_absolute() and Path(name).suffix == '.md'}
        cfg['policy_preparation'] = dict(mode='policy5', stage=STAGE, version=version,
            inputs=dict(path=str(input_directory), seal_sha256=storage.sha256(input_directory/'complete.json')),
            cpu_evidence=[dict(path=str(Path(path).resolve()), seal_sha256=storage.sha256(Path(path)/'complete.json')) for path in cpu_evidence],
            simulator_attempts=0, optimizer_updates=0)
        task = dest/Path(ready['task_document'])
        cfg['analysis_approval'] = dict(status='approved', approved_by='analysis', document_path=str(task),
            document_sha256=storage.sha256(task), protocol_sha256=protocol_digest(cfg))
        require_stage_budget(cfg, STAGE)
        from .policy_deployment_v1 import validate_deployment_inputs
        validated = validate_deployment_inputs(cfg, bank_version)
        storage.dump(dest/'input_validation.json', validated)
        storage.dump(dest/'config.json', cfg)
        files = dict(old_frozen['files'])
        extras = [Path(__file__), CODE/'policy5_runner_v1.py', CODE/'run_policy5_gpu_v1.sh',
            CODE/'policy_deployment_v1.py', CODE/'policy5_audit_v1.py', CODE/'policy5_seed_review_v1.py',
            CODE/'prepare_fit.py', base_config, base_config.with_name('freeze.json')]
        extras += [Path(path) for path in cpu_coverage]
        extras += [p for p in dest.rglob('*') if p.is_file()]
        extras += [p for p in input_directory.rglob('*') if p.is_file()]
        for evidence in cpu_evidence:
            extras += [p for p in Path(evidence).rglob('*') if p.is_file()]
        trained = Path(binding['selected_training']['path'])
        extras += [trained/'complete.json', trained/'result.json', trained/'selected_reload_audit.json']
        extras += [p for p in (trained/'selected').rglob('*') if p.is_file()]
        for source in validated['sources'].values():
            extras += [Path(source['source_path'])/'complete.json', Path(source['resolution_path'])/'complete.json']
            if source['old_bank_path']:
                extras.append(Path(source['old_bank_path'])/'complete.json')
        files.update({str(path.resolve()): storage.sha256(path) for path in extras})
        code_files = {path: digest for path, digest in files.items() if Path(path).suffix in ('.py', '.sh')}
        archive = dest/'code_snapshot.tar.gz'
        with tarfile.open(archive, 'x:gz') as bundle:
            for name in sorted(code_files):
                path = Path(name)
                arcname = (path.relative_to(storage.PACKAGE.parent) if path.is_relative_to(storage.PACKAGE.parent)
                           else Path('external')/str(path).lstrip('/'))
                bundle.add(name, arcname=arcname, recursive=False)
        files[str(archive)] = storage.sha256(archive)
        storage.dump(dest/'freeze.json', dict(files=files, code_files=code_files,
            large_files_verified_once_then_stat=old_frozen.get('large_files_verified_once_then_stat', {}),
            stage=STAGE, bank_version=bank_version, config_sha256=storage.sha256(dest/'config.json'),
            policy5_only=True, simulator_attempts_limit=2100, training_updates_limit=0))
        from .policy5_runner_v1 import verify_frozen
        verify_frozen(dest/'config.json', dest/'freeze.json', STAGE, bank_version, 32)
        return dict(config=str(dest/'config.json'), config_sha256=storage.sha256(dest/'config.json'),
                    freeze=str(dest/'freeze.json'), freeze_sha256=storage.sha256(dest/'freeze.json'))
    except BaseException as error:
        storage.dump(dest/'preparation_failure.json', dict(error=repr(error), simulator_attempts=0, optimizer_updates=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inputs', 'freeze'))
    parser.add_argument('--base-config', type=Path, required=True)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--input-directory', type=Path)
    parser.add_argument('--cpu-evidence', type=Path, action='append', default=[])
    parser.add_argument('--version')
    parser.add_argument('--bank-version')
    args = parser.parse_args()
    result = inputs(args.base_config, args.ready, args.output) if args.action == 'inputs' else freeze(
        args.base_config, args.ready, args.input_directory, args.cpu_evidence, version=args.version, bank_version=args.bank_version)
    print(json.dumps(result))
