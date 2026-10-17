"""Freeze a NEW CPU preflight/fit configuration; never run PCA or an optimizer.

Only round1 is implemented. A new analysis READY must explicitly release the
requested scope. Source/collection configurations and all existing versions are
read-only. Dataset provenance is fully checked by the execution entrypoint.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import tarfile

from . import storage
from .protocol import canonical_hash, protocol_digest, require_stage_budget, validate_protocol


SCOPES = {'preflight': 'round1_fit_preflight', 'fit': 'round1_critic_training'}
CODE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def checked(path, digest):
    path = Path(path).resolve()
    if not path.is_file() or storage.sha256(path) != digest:
        raise ValueError('Required binding SHA mismatch: '+str(path))
    return path


def sealed_directory(path, digest):
    """Validate a whole sealed directory without interpreting its model data."""
    path = Path(path).resolve()
    complete = read(checked(path/'complete.json', digest))
    if complete.get('status') != 'complete' or not isinstance(complete.get('files'), dict):
        raise ValueError('Expected a complete directory seal')
    actual = {str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p != path/'complete.json'}
    if set(complete['files']) != actual:
        raise ValueError('Sealed directory file list changed')
    for name, expected in complete['files'].items():
        target = (path/name).resolve()
        if not target.is_relative_to(path):
            raise ValueError('Sealed file escapes its artifact directory')
        checked(target, expected)
    return complete


def dataset_binding(path, *, purpose, manifest):
    """Check metadata bindings only; no feature/outcome arrays are deserialized."""
    binding = read(path)
    directory = Path(binding['path']).resolve()
    if not directory.is_relative_to((storage.ROOT/'datasets').resolve()):
        raise ValueError('Only datasets in the new workflow may be bound')
    sealed_directory(directory, binding['seal_sha256'])
    audit_path = checked(binding['input_audit_path'], binding['input_audit_sha256'])
    if not audit_path.is_relative_to((storage.ROOT/'dataset_audits').resolve()):
        raise ValueError('Input audit must be in the new workflow dataset_audits')
    audit = read(audit_path)
    from .artifact_loader import CHECK_NAMES
    if (audit.get('schema') != 'native10_input_artifact_audit_v1'
            or audit.get('status') != 'passed' or audit.get('purpose') != purpose
            or audit.get('manifest_sha256') != canonical_hash(manifest)
            or audit.get('dataset_seal_sha256') != binding['seal_sha256']
            or audit.get('protocol_sha256') != binding['input_protocol_sha256']
            or any(audit.get('checks', {}).get(key) is not True for key in CHECK_NAMES)):
        raise ValueError('Complete independently audited dataset metadata required')
    return binding


def freeze(*, base_config, ready_path, train_binding, development_binding,
           version, mode='preflight', preflight_binding=None):
    if mode not in SCOPES or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', version):
        raise ValueError('Use an explicit supported mode and safe NEW version')
    ready_path = Path(ready_path).resolve()
    ready = read(ready_path)
    if (ready.get('task_id') != 'native10-training-20260916'
            or not (ready.get('status') == 'approved' or str(ready.get('status', '')).startswith('protocol_approved_'))
            or SCOPES[mode] not in ready.get('released_scope', [])):
        raise ValueError('Analysis READY has not released '+SCOPES[mode])
    if ready_path.name != 'NATIVE10_ANALYSIS_READY.json':
        raise ValueError('Expected the workflow-specific READY filename')
    base_config = Path(base_config).resolve()
    if not base_config.is_relative_to((storage.ROOT/'main_protocols').resolve()):
        raise ValueError('Base config must be a separately frozen main protocol')
    cfg = read(base_config)
    validate_protocol(cfg, require_runnable=True)
    base_freeze = base_config.with_name('freeze.json')
    frozen = read(base_freeze)
    base_digest = storage.sha256(base_config)
    if frozen.get('config_sha256') != base_digest or frozen.get('files', {}).get(str(base_config)) != base_digest:
        raise ValueError('Original collection freeze does not bind the supplied config')
    collection = dict(config_path=str(base_config), config_sha256=base_digest,
                      freeze_path=str(base_freeze), freeze_sha256=storage.sha256(base_freeze))
    if mode == 'preflight':
        release = ready.get('round1_fit_preflight', {})
        if (release.get('stage') != 'round1_fit_preflight' or release.get('scope') != SCOPES[mode]
                or release.get('simulator_attempts_limit') != 0 or release.get('optimizer_updates_limit') != 0
                or release.get('training_updates') != 0
                or release.get('input_config_sha256') != collection['config_sha256']
                or release.get('input_freeze_sha256') != collection['freeze_sha256']):
            raise ValueError('READY preflight must bind this collection and exact zero resources')
    from .training_pipeline import training_code_files
    bindings = dict(train=dataset_binding(train_binding, purpose='train', manifest=cfg['episode_manifest']),
                    development=dataset_binding(development_binding, purpose='development', manifest=cfg['episode_manifest']))
    specification = dict(design=dict(path=str(CODE/'training_design_v2.json'), sha256=storage.sha256(CODE/'training_design_v2.json')),
                         datasets={'round1': bindings}, code_files=training_code_files(), collection=collection,
                         stop_after={'round1': {'A': 2400, 'B': 2400}})
    if mode == 'fit':
        if preflight_binding is None:
            raise ValueError('Fit preparation requires the separately sealed zero-update preflight binding')
        binding = read(preflight_binding)
        path = Path(binding['path']).resolve()
        if not path.is_relative_to((storage.ROOT/'fit_preflight/round1').resolve()):
            raise ValueError('Round1 preflight must be in this workflow')
        sealed_directory(path, binding['seal_sha256'])
        result = read(path/'result.json')
        if (result.get('role') != 'native10_fit_preflight_zero_updates' or result.get('status') != 'passed'
                or result.get('optimizer_updates') != 0 or result.get('phase') != 'round1'):
            raise ValueError('Fit preparation requires a passed zero-update round1 preflight')
        design_binding = result['design']
        checked(design_binding['path'], design_binding['sha256'])
        specification['design'] = deepcopy(design_binding)
        expected_identity = dict(manifest_sha256=canonical_hash(cfg['episode_manifest']),
            seed_namespace=cfg['seed_namespace'], design=specification['design'], dataset_bindings=bindings,
            code_files=specification['code_files'], stop_after=specification['stop_after']['round1'], collection=collection)
        if any(result.get(key) != value for key, value in expected_identity.items()):
            raise ValueError('Fit preparation must reuse the exact preflight input/code/design/seed identity')
        specification['preflight'] = {'round1': {'path': str(path), 'seal_sha256': binding['seal_sha256']}}
    elif preflight_binding is not None:
        raise ValueError('Preflight preparation does not consume another preflight')
    originals = {p.name: (p, storage.sha256(p)) for p in sorted(ready_path.parent.glob('NATIVE10_*.md'))}
    originals[ready_path.name] = (ready_path, storage.sha256(ready_path))
    # Validate referenced analysis documents BEFORE creating a new output version.
    for key in ('task_document', 'protocol_review'):
        path = Path(ready[key])
        if not path.is_absolute():
            path = ready_path.parent.parent/path
        path = checked(path, ready[key+'_sha256'])
        if path.parent != ready_path.parent or path.name not in originals:
            raise ValueError('READY documents must be in this workflow coordination directory')
    destination = storage.ROOT/'fit_protocols'/version
    destination.mkdir(parents=True, exist_ok=False)
    try:
        snapshots = destination/'coordination'; snapshots.mkdir()
        for name, (path, digest) in originals.items():
            shutil.copyfile(path, snapshots/name)
            checked(snapshots/name, digest); checked(path, digest)
        frozen_ready = read(snapshots/ready_path.name)
        # Preserve READY content verbatim. Its normal relative coordination paths
        # resolve inside destination; absolute references cannot be rewritten.
        if any(Path(frozen_ready[key]).is_absolute() for key in ('task_document','protocol_review')):
            raise ValueError('Use relative analysis document references for a self-contained freeze')
        if mode == 'preflight':
            original_design = read(CODE/'training_design_v2.json')
            design = deepcopy(original_design)
            design.update(status='round1_zero_update_prefit_configuration_frozen',
                training_implementation_complete=True, training_started=False, training_updates_executed=0,
                sources={str(snapshots/name): digest for name, (_, digest) in originals.items()},
                original_main_design=dict(path=str(CODE/'training_design_v2.json'), sha256=storage.sha256(CODE/'training_design_v2.json')),
                precedence='Original approved parameters unchanged; READY v5 and the round1 preflight decision govern only this zero-update phase.',
                implementation_status=dict(main_collection='continues under separate frozen READY v4',
                    cpu_pipeline='independent A/B preflight and sealed initialization import implemented',
                    real_data_fit='not_started', real_preprocessing_reload_audit='not_executed_by_preparation'),
                execution_gate=dict(current_ready_scope='round1_fit_preflight', this_record_releases_training=False,
                    simulator_calls_by_preparation=0, optimizer_updates_by_preparation=0,
                    execution_requires='complete input audit, frozen code bindings and exact zero-resource READY gate'),
                version_note='Independent metadata snapshot; original main v2 design and all approved scientific parameters remain unchanged.')
            for key in ('approved_parameters','candidate_schema','old_weight_import','budget'):
                if design[key] != original_design[key]:
                    raise ValueError('Preflight preparation changed an approved scientific parameter')
            storage.dump(destination/'training_design.json', design)
            specification['design'] = dict(path=str(destination/'training_design.json'),
                                          sha256=storage.sha256(destination/'training_design.json'))
        cfg = deepcopy(cfg)
        source_protocol = cfg['analysis_approval']['protocol_sha256']
        for bank in cfg['main_collection']['banks'].values():
            bank.setdefault('bank_protocol_sha256', source_protocol)
        cfg['analysis_documents'] = {str(snapshots/name): digest for name, (_, digest) in originals.items() if name.endswith('.md')}
        cfg['analysis_ready'] = dict(path=str(snapshots/ready_path.name), sha256=storage.sha256(snapshots/ready_path.name))
        cfg['training_pipeline'] = specification
        cfg['budget']['stages']['round1_fit_preflight'] = dict(simulator_attempts=0, training_updates=0)
        cfg['stage_release_scopes']['round1_fit_preflight'] = 'round1_fit_preflight'
        cfg['fit_preparation'] = dict(mode=mode, phase='round1', scope=SCOPES[mode],
                                     base_config=str(base_config), base_config_sha256=storage.sha256(base_config))
        if mode == 'fit':
            cfg['stage_release_scopes']['training_round1'] = SCOPES[mode]
        task = snapshots/Path(ready['task_document']).name
        cfg['analysis_approval'] = dict(status='approved', approved_by='analysis', document_path=str(task),
                                       document_sha256=storage.sha256(task), protocol_sha256=protocol_digest(cfg))
        validate_protocol(cfg, require_runnable=True)
        if mode == 'fit':
            require_stage_budget(cfg, 'training_round1', resource='training_updates')
        storage.dump(destination/'config.json', cfg)
        files = dict(specification['code_files'])
        for path in [Path(__file__), base_config, base_freeze, CODE/'training_design_v2.json',
                     Path(specification['design']['path']), destination/'config.json', *snapshots.iterdir()]:
            files[str(path.resolve())] = storage.sha256(path)
        archive = destination/'code_snapshot.tar.gz'
        with tarfile.open(archive, 'x:gz') as bundle:
            for name, digest in sorted(files.items()):
                checked(name, digest)
                bundle.add(name, arcname=name.lstrip('/'), recursive=False)
                checked(name, digest)
        storage.dump(destination/'freeze.json', dict(role='native10_cpu_fit_protocol', mode=mode, phase='round1', files=files,
                                                    config_sha256=storage.sha256(destination/'config.json'),
                                                    code_snapshot=dict(path=str(archive), sha256=storage.sha256(archive)),
                                                    simulator_calls=0, optimizer_updates=0, full_dataset_audit_required_at_execution=True))
        return destination/'config.json'
    except Exception as error:
        storage.dump(destination/'failure.json', dict(status='failed', error=repr(error), simulator_calls=0, optimizer_updates=0))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=SCOPES, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--base-config', type=Path, required=True)
    parser.add_argument('--ready-path', type=Path, default=storage.PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json')
    parser.add_argument('--train-binding', type=Path, required=True)
    parser.add_argument('--development-binding', type=Path, required=True)
    parser.add_argument('--preflight-binding', type=Path)
    args = vars(parser.parse_args())
    print(freeze(**args))


if __name__ == '__main__':
    main()
