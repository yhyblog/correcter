"""Metadata-only heldout preparation and separately authorized immutable freeze.

No model, environment, PCA, optimizer or collector is constructed here. Pending
artifacts grant no execution scope. Authorization references are traversed through
the entire READY JSON tree; both absolute and relative references are inventoried
and copied, while the original READY bytes remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile

from . import storage
from .calibration_prepare_v1 import authorization_references, snapshot_authorization_references
from .prepare_fit import checked, sealed_directory
from .protocol import TASKS, canonical_hash, protocol_digest, require_stage_budget, validate_protocol

CODE = Path(__file__).resolve().parent
STAGE = SCOPE = 'heldout'
BANK = 'heldout_policy_v1'
SCHEMA = 'native10_heldout_collection_v1'
PRIMARY_IDS_SHA = 'f05bbfeb92da78d8fb9242bd28b116cf6f5a4cff252b5ad0487506e0bd108afc'
RESERVE_SCOPE = 'heldout_initialization_replacements'
BASE_CONFIG_SHA = 'c04125ae474316783e7dd6ca74c799d5441299801f22cd0910889f98511d7382'
BASE_FREEZE_SHA = 'd181899e5ccf70177db5fee6267ec9f102f4aae6e437e42f7a0eb86dc9800d1e'
DECISION = 'coordination/NATIVE10_FINAL_SELECTION_AND_HELD_PREPARATION_DECISION.md'
DECISION_SHA = '7b50be9baff4a7eca49607bda0a91f7b24e597fb95d65add765803daf70cbf24'
ARMS = ['continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post']
GLOBAL_ACCEPTANCE = dict(primary_method='post', fallback_method='alarm_replan10',
    rule='mean_paired_post_minus_replan_strictly_positive', source_denominator=100,
    replicates=2, no_cut_difference=0)
CUT_POLICY = dict(policy='first_legal_alarm_only', training_fallback_allowed=False,
                  no_alarm_common_outcome=True)
PRIMARY_COMPARISON = 'post_minus_alarm_replan10'
SECONDARY_COMPARISONS = ['alarm_replan10_minus_continue_native10',
    'velocity_minus_alarm_replan10', 'direct_minus_alarm_replan10',
    'velocity_minus_continue_native10', 'direct_minus_continue_native10',
    'post_minus_continue_native10']
NEW_CODE = ('heldout_prepare_v1.py', 'heldout_collection_v1.py',
            'heldout_runner_v1.py', 'run_heldout_gpu_v1.sh', 'heldout_statistics_v1.py',
            'final_selection_v1.py')
NEW_TESTS = ('test_heldout_prepare_v1.py', 'test_heldout_collection_v1.py',
             'test_heldout_runner_v1.py', 'test_heldout_statistics_v1.py',
             'test_final_selection_v1.py')


def read(path):
    return json.loads(Path(path).read_text())


def _new(path):
    path = Path(path).resolve()
    if not path.is_relative_to(storage.ROOT.resolve()) or path.is_relative_to((storage.ROOT/'p0').resolve()):
        raise ValueError('Use a new workflow directory outside P0')
    path.mkdir(parents=True, exist_ok=False)
    return path


def original_slots(config):
    rows = [x for x in config['episode_manifest'] if x['split'] == STAGE and not x.get('replacement_of')]
    seeds = list(range(2026111750, 2026111800))+list(range(2026111850, 2026111900))
    if (len(rows) != 100 or [x['env_seed'] for x in rows] != seeds
            or Counter(x['task'] for x in rows) != {task: 20 for task in TASKS}
            or len({x['episode_id'] for x in rows}) != 100
            or any(x.get('round') is not None or x['cut_rule'] != {'kind': 'first_alarm'} for x in rows)):
        raise ValueError('Heldout requires the original ordered 100 registered first-alarm slots')
    if canonical_hash([x['episode_id'] for x in rows]) != PRIMARY_IDS_SHA:
        raise ValueError('Heldout original ordered IDs changed')
    return rows


def assert_uninitialized(config):
    """Metadata-only pre-capture check; it does not establish physical uniqueness."""
    ids = [x['episode_id'] for x in original_slots(config)]
    backups = config['main_collection']['replacement_candidates']
    all_ids = ids+[name for identity in ids for name in backups[identity]]
    if len(all_ids) != 300 or len(set(all_ids)) != 300:
        raise ValueError('Require 100 primary and 200 distinct registered backup identities')
    for identity in all_ids:
        if (storage.ROOT/'sources'/identity).exists() or (storage.ROOT/'slot_resolution'/identity).exists():
            raise ValueError('Heldout preparation cannot reuse an initialized source: '+identity)
    return set(all_ids)


def validate_final_selection_reference(binding, *, require_actual=False):
    """Validate metadata only; a pending plan is never an execution permission."""
    from . import final_selection_v1 as selection
    if binding.get('status') == 'pending_selection_seal':
        if require_actual:
            raise ValueError('Actual final selection seal is required before heldout release')
        return selection.validate_pending_binding(binding)
    return selection.validate_selection_binding(binding)


def statistics_contract(config):
    ids = [row['episode_id'] for row in original_slots(config)]
    return dict(primary_comparison=PRIMARY_COMPARISON,
        secondary_comparisons=list(SECONDARY_COMPARISONS), draws=10000, seed=2026091622,
        task_order=list(TASKS), source_order=ids, unit='whole logical primary source within task',
        quantile_method='linear', interval='percentile95', multiplicity_adjusted=False,
        source_denominator=100, replicates=4, practical_point_estimate_target=.05,
        no_method_selection_after_heldout=True, no_combining_calibration_and_heldout=True)


def build_pending(base_config, ready_path, *, final_selection):
    base = checked(Path(base_config).resolve(), BASE_CONFIG_SHA)
    frozen_path = checked(base.with_name('freeze.json'), BASE_FREEZE_SHA)
    old, frozen = read(base), read(frozen_path)
    if frozen['files'].get(str(base)) != BASE_CONFIG_SHA:
        raise ValueError('Scientific base config is not bound by its original freeze')
    validate_protocol(old, require_runnable=True)
    checked(storage.PACKAGE/DECISION, DECISION_SHA)
    rows = original_slots(old); ids = [x['episode_id'] for x in rows]
    validate_final_selection_reference(final_selection)
    oldreg = old['main_collection']['banks']['calibration_policy_v1']
    cfg = deepcopy(old)
    for key in ('policy_deployment', 'policy_preparation', 'policy_statistics',
                'calibration_collection', 'calibration_preparation'):
        cfg.pop(key, None)
    cfg.update(status='pending', analysis_approval={'status': 'pending'},
        analysis_ready=dict(path=str(Path(ready_path).resolve()), sha256=storage.sha256(ready_path)))
    cfg['main_collection']['banks'] = {BANK: dict(stage=STAGE, kind='policy5', episode_ids=ids,
        generation_round=2, generation_phase=STAGE, cut_selection_policy='analysis_lead_v1',
        random_seed_domain=oldreg['random_seed_domain'], model_hashes=deepcopy(oldreg['model_hashes']),
        critic_member_hashes=deepcopy(oldreg['critic_member_hashes']))}
    cfg['stage_release_scopes'] = {name: 'not_released_'+name for name in cfg['budget']['stages']}
    cfg['stage_release_scopes'].update(p0='p0_anchor_and_native10_diagnostics',
                                      heldout=SCOPE, technical_reserve=RESERVE_SCOPE)
    cfg['heldout_collection'] = dict(schema=SCHEMA,
        original_collection=dict(config_path=str(base), config_sha256=BASE_CONFIG_SHA,
            freeze_path=str(frozen_path), freeze_sha256=BASE_FREEZE_SHA, bank_version='calibration_policy_v1'),
        selected_training=deepcopy(old['calibration_collection']['selected_training']),
        requested_cut_rules_sha256=canonical_hash({x['episode_id']: x['cut_rule'] for x in rows}),
        effective_cut_policy=deepcopy(CUT_POLICY), global_acceptance=deepcopy(GLOBAL_ACCEPTANCE),
        final_selection=deepcopy(final_selection), fixed_primary_comparison=PRIMARY_COMPARISON,
        selection_after_heldout_allowed=False)
    cfg['heldout_preparation'] = dict(status='pending_explicit_heldout_ready_and_cpu_freeze',
        base_policy=deepcopy(cfg['heldout_collection']['original_collection']),
        registration_origin=deepcopy(old['calibration_preparation']['registration_origin']),
        original_primary_ids_canonical_sha256=canonical_hash(ids), primary_capture_planned=100,
        independent_bank_restores_upper_bound=100, branch_upper_bound=2000,
        simulator_attempts_upper_bound=2200, optimizer_updates=0,
        capture_allowed_after_release=True, heldout_initialization_allowed=False,
        selection_seal_authorized=False, physical_initial_uniqueness_established=False,
        decision_references={str(storage.PACKAGE/DECISION): DECISION_SHA})
    cfg['heldout_statistics'] = statistics_contract(cfg)
    validate_protocol(cfg)
    return cfg


def ready_contract(config):
    """Exact mandatory future READY.heldout row; additional provenance is allowed."""
    collection = config['heldout_collection']; prep = config['heldout_preparation']
    reg = config['main_collection']['banks'][BANK]; rows = original_slots(config)
    model = collection['selected_training']; path = Path(model['path'])
    members = reg['critic_member_hashes']
    scene = prep.get('authorized_scene_registry_before', prep['scene_registry_before'])
    final_selection = collection['final_selection']
    selection_result = (dict(status='not_created_pending_selection_seal')
        if final_selection.get('status') == 'pending_selection_seal' else
        dict(path=str(Path(final_selection['path'])/'result.json'), sha256=final_selection['result_sha256']))
    return dict(scope=SCOPE, stage=STAGE, bank_version=BANK, schema=SCHEMA,
        simulator_attempts_limit=2200, simulator_attempts_upper_bound=2200,
        optimizer_updates_limit=0, training_updates=0, primary_capture_limit=100,
        heldout_primary_slots=100, per_task_source_counts=dict(Counter(x['task'] for x in rows)),
        paired_suffixes_per_state=4, arms=list(ARMS), per_arm_outcome_denominator=400,
        episode_ids=reg['episode_ids'], episode_ids_canonical_sha256=canonical_hash(reg['episode_ids']),
        input_config_sha256=collection['original_collection']['config_sha256'],
        input_freeze_sha256=collection['original_collection']['freeze_sha256'],
        original_collection=deepcopy(collection['original_collection']),
        full_manifest_sha256=canonical_hash(config['episode_manifest']),
        replacement_candidates_sha256=canonical_hash(config['main_collection']['replacement_candidates']),
        candidate_generation_round=2, generation_phase=STAGE, capture_allowed=True,
        heldout_initialization_allowed=True, old_development_anchor_reuse_allowed=False,
        old_calibration_anchor_reuse_allowed=False,
        initialization_replacement_stage='technical_reserve', initialization_replacement_scope=RESERVE_SCOPE,
        initialization_replacement_workflow_limit=1200,
        initialization_replacement_allowed_primary_ids_sha256=canonical_hash(reg['episode_ids']),
        initialization_replacement_reasons=['duplicate_initial_scene', 'initialization_failed'],
        global_simulator_hard_limit=50000, workflow_optimizer_hard_limit=51200,
        optimizer_updates_remaining=0, global_acceptance=deepcopy(GLOBAL_ACCEPTANCE),
        selection_seal_authorized=False, effective_cut_policy=deepcopy(CUT_POLICY),
        final_selection=deepcopy(collection['final_selection']), actual_selection_seal_required=True,
        final_selection_result=selection_result,
        fixed_method='post', post_enabled_on_alarm=True, selection_after_heldout_allowed=False,
        statistics=deepcopy(config['heldout_statistics']),
        scientific_semantics={k:deepcopy(config[k]) for k in ('guidance','matching','command_semantics')},
        scene_registry_before=dict(path=scene['snapshot_path'], sha256=scene['sha256'],
                                   bytes=scene['bytes'], records=scene['records']),
        selected_critic=dict(path='A', step=4000, members=4, directory=config['critic_assets'],
            training_model_seal=dict(path=str(path/'complete.json'), sha256=model['seal_sha256']),
            selected_seal=dict(path=str(path/'selected/complete.json'), sha256=model['selected_seal_sha256']),
            selected_reload_audit=dict(path=str(path/'selected_reload_audit.json'),
                                       sha256=model['selected_reload_audit_sha256']),
            model_review=deepcopy(model['model_review']), model_hashes=deepcopy(members),
            member_checkpoint_sha256=[members[str(i)] for i in range(4)]),
        execution_policy=dict(validated_workers=32, gpu_count=8, workers_per_gpu=4,
                              lifecycle_required=True, hold_idle=False),
        decision=dict(path=str(storage.PACKAGE/DECISION), sha256=DECISION_SHA))


def prepare_pending(base_config, ready_path, output, *, final_selection):
    cfg = build_pending(base_config, ready_path, final_selection=final_selection)
    uninitialized_ids = assert_uninitialized(cfg)
    dest = _new(output); registry = storage.ROOT/'scene_registry/entries.jsonl'
    with Path('/tmp/corrector_native10_scene_registry.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH); raw = registry.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Scene registry snapshot must end on a complete record')
    if any(json.loads(line).get('episode_id') in uninitialized_ids for line in raw.splitlines()):
        raise ValueError('Heldout initial scene was already registered')
    snapshot = dest/'scene_registry_before.jsonl'; snapshot.write_bytes(raw)
    cfg['heldout_preparation']['scene_registry_before'] = dict(live_path=str(registry),
        snapshot_path=str(snapshot), sha256=storage.sha256(snapshot), bytes=len(raw), records=len(raw.splitlines()))
    from .heldout_collection_v1 import validate_heldout_inputs
    audit = validate_heldout_inputs(cfg, BANK, require_release=False)
    storage.dump(dest/'config.json', cfg)
    storage.dump(dest/'primary_manifest.json', original_slots(cfg))
    storage.dump(dest/'ready_contract.json', ready_contract(cfg))
    storage.dump(dest/'input_validation.json', audit)
    storage.dump(dest/'result.json', dict(status='passed_pending_only', runnable=False, stage=STAGE,
        config_sha256=storage.sha256(dest/'config.json'), simulator_calls=0, model_calls=0, optimizer_updates=0))
    storage.seal(dest, role='heldout_isolated_preparation', simulator_attempts=0, optimizer_updates=0)
    return dict(path=str(dest), config_sha256=storage.sha256(dest/'config.json'),
                seal_sha256=storage.sha256(dest/'complete.json'))


def _scope(ready_path):
    ready = read(ready_path)
    if (ready.get('task_id') != 'native10-training-20260916'
            or not (ready.get('status') == 'approved' or str(ready.get('status', '')).startswith('protocol_approved_'))
            or not {SCOPE, RESERVE_SCOPE} <= set(ready.get('released_scope', []))):
        raise ValueError('READY must explicitly release heldout and its separate initialization reserve')
    return ready


def release(ready_path, config):
    ready = _scope(ready_path)  # Missing scope must fail before all bound input reads.
    validate_final_selection_reference(config['heldout_collection']['final_selection'], require_actual=True)
    expected = ready_contract(config); actual = ready.get(STAGE, {})
    if any(actual.get(k) != v for k, v in expected.items()):
        changed = [k for k, v in expected.items() if actual.get(k) != v]
        raise ValueError('READY heldout contract differs: '+','.join(changed))
    references = authorization_references(ready)
    for row in references:
        checked(row['original_path'], row['sha256'])
    return ready, references


def verify_authorization_inventory(config, frozen):
    """Pure read-only completeness/identity gate for the actual runner."""
    ready_ref = config['analysis_ready']; ready_path = checked(ready_ref['path'], ready_ref['sha256'])
    expected = authorization_references(read(ready_path))
    ref = config['heldout_preparation']['authorization_inventory']
    inventory_path = checked(ref['path'], ref['sha256']); inventory = read(inventory_path)
    if inventory.get('schema') != 'native10_authorization_reference_inventory_v1' or inventory.get('status') != 'passed':
        raise ValueError('Complete authorization inventory required')
    rows = inventory.get('references', [])
    if [{k:v for k,v in row.items() if k != 'snapshot_path'} for row in rows] != expected:
        raise ValueError('Authorization inventory does not exhaustively match nested frozen READY')
    required = {str(ready_path): ready_ref['sha256'], str(inventory_path): ref['sha256']}
    snapshot_root = inventory_path.parent/'authorization_references'
    for row in rows:
        snapshot = Path(row['snapshot_path']).resolve()
        if not snapshot.is_relative_to(snapshot_root.resolve()):
            raise ValueError('Authorization snapshot escapes its independent inventory')
        required[row['original_path']] = row['sha256']; required[str(snapshot)] = row['sha256']
    for path, digest in required.items():
        if frozen.get('files', {}).get(path) != digest:
            raise ValueError('Freeze omits authorization original/snapshot: '+path)
        checked(path, digest)
    return dict(status='passed', reference_count=len(rows), all_original_and_snapshot_files_frozen=True)


def cpu_checks(paths):
    required = {str((CODE/name).resolve()) for name in NEW_CODE+NEW_TESTS}; covered = {}
    for directory in paths:
        directory = Path(directory).resolve(); sealed_directory(directory, storage.sha256(directory/'complete.json'))
        result = read(directory/'result.json'); after = result.get('code_sha256_after', {})
        if (result.get('status') != 'passed' or result.get('returncode') != 0 or not after
                or result.get('code_sha256_before') != after
                or result.get('shell_returncode', 0) != 0
                or any(result.get(k) != 0 for k in ('model_calls', 'simulator_calls', 'optimizer_updates'))):
            raise ValueError('Current new-entry CPU evidence must pass with zero real work')
        for name, digest in after.items():
            checked(name, digest)
            if name in covered and covered[name] != digest: raise ValueError('Conflicting CPU evidence')
            covered[name] = digest
    if not required <= set(covered):
        raise ValueError('CPU evidence omits actual heldout entrypoints or tests')
    return covered


def _preparation_binding(pending, cpu_evidence, coverage):
    pending = Path(pending).resolve()
    return dict(pending_inputs=dict(path=str(pending), seal_sha256=storage.sha256(pending/'complete.json')),
        ready_contract=dict(path=str(pending/'ready_contract.json'), sha256=storage.sha256(pending/'ready_contract.json')),
        cpu_evidence=[dict(path=str(Path(p).resolve()), seal_sha256=storage.sha256(Path(p)/'complete.json'))
                      for p in cpu_evidence], code_sha256=deepcopy(coverage))


def expected_preparation_binding(pending, cpu_evidence):
    """Metadata-only exact future READY.heldout_preparation_binding payload."""
    pending = Path(pending).resolve()
    record = sealed_directory(pending, storage.sha256(pending/'complete.json'))
    if record.get('role') != 'heldout_isolated_preparation':
        raise ValueError('Wrong pending artifact role')
    if read(pending/'ready_contract.json') != ready_contract(read(pending/'config.json')):
        raise ValueError('Pending READY contract differs from its sealed configuration')
    return _preparation_binding(pending, cpu_evidence, cpu_checks(cpu_evidence))


def freeze(pending_directory, ready_path, cpu_evidence, *, version):
    ready_path = Path(ready_path).resolve()
    ready_bytes = ready_path.read_bytes()
    ready_sha = hashlib.sha256(ready_bytes).hexdigest()
    _scope(ready_path)  # In particular, live READY v11 cannot read pending inputs.
    checked(ready_path, ready_sha)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,60}', version):
        raise ValueError('Use a safe independent protocol version')
    pending = Path(pending_directory).resolve()
    ps = sealed_directory(pending, storage.sha256(pending/'complete.json'))
    if ps.get('role') != 'heldout_isolated_preparation': raise ValueError('Wrong pending artifact role')
    cfg = deepcopy(read(pending/'config.json'));ready, _ = release(ready_path, cfg)
    checked(ready_path, ready_sha)
    if ready != json.loads(ready_bytes): raise ValueError('Validated READY differs from captured bytes')
    assert_uninitialized(cfg)
    coverage = cpu_checks(cpu_evidence)
    if (read(pending/'ready_contract.json') != ready_contract(cfg)
            or ready.get('heldout_preparation_binding') != _preparation_binding(pending, cpu_evidence, coverage)):
        raise ValueError('READY must bind these exact pending inputs, contract, CPU evidence and current code')
    base = cfg['heldout_collection']['original_collection'];oldf = read(checked(base['freeze_path'], base['freeze_sha256']))
    checked(base['config_path'], base['config_sha256'])
    from .heldout_collection_v1 import validate_heldout_inputs
    validate_heldout_inputs(cfg, BANK, require_release=False)
    dest = _new(storage.ROOT/'heldout_protocols'/version)
    try:
        snapshot = dest/'coordination/NATIVE10_ANALYSIS_READY.json';snapshot.parent.mkdir()
        checked(ready_path, ready_sha)
        snapshot.write_bytes(ready_bytes);checked(snapshot, ready_sha)
        inventory = snapshot_authorization_references(ready, dest)
        cfg['analysis_ready'] = dict(path=str(snapshot), sha256=storage.sha256(snapshot))
        prep = cfg['heldout_preparation']
        # Copy the preregistered prefix; never lock/hash the growing live registry.
        scene = prep['scene_registry_before'];old_snapshot = checked(scene['snapshot_path'], scene['sha256'])
        prep['authorized_scene_registry_before'] = deepcopy(scene)
        target = dest/'scene_registry_before.jsonl';shutil.copyfile(old_snapshot, target);checked(target, scene['sha256'])
        scene['snapshot_path'] = str(target)
        prep.update(status='frozen_heldout_collection_only', version=version,
            pending_inputs=dict(path=str(pending), seal_sha256=storage.sha256(pending/'complete.json')),
            cpu_evidence=[dict(path=str(Path(p).resolve()), seal_sha256=storage.sha256(Path(p)/'complete.json')) for p in cpu_evidence],
            authorization_inventory=dict(path=str(dest/'authorization_inventory.json'), sha256=storage.sha256(dest/'authorization_inventory.json')))
        cfg['status'] = 'frozen'
        task = Path(ready['task_document']);task = task if task.is_absolute() else dest/task
        cfg['analysis_approval'] = dict(status='approved', approved_by='analysis', document_path=str(task),
            document_sha256=storage.sha256(task), protocol_sha256=protocol_digest(cfg))
        require_stage_budget(cfg, STAGE);require_stage_budget(cfg, 'technical_reserve')
        storage.dump(dest/'input_validation.json', validate_heldout_inputs(cfg, BANK, require_release=True))
        storage.dump(dest/'config.json', cfg)
        extras = [Path(base['config_path']),Path(base['freeze_path'])]+[Path(p) for p in coverage]
        extras += [p for folder in [pending,dest,*map(Path,cpu_evidence)] for p in folder.rglob('*') if p.is_file()]
        extras += [Path(row['original_path']) for row in inventory['references']]
        files = dict(oldf['files'])
        for p in extras:
            key = str(p.resolve());digest = storage.sha256(p)
            if key in files and files[key] != digest: raise ValueError('Old frozen dependency changed: '+key)
            files[key] = digest
        code_files = {p:h for p,h in files.items() if Path(p).suffix in ('.py','.sh')}
        archive = dest/'code_snapshot.tar.gz'
        with tarfile.open(archive, 'x:gz') as stream:
            for name in sorted(code_files):
                path = Path(name);arc = path.relative_to(storage.PACKAGE.parent) if path.is_relative_to(storage.PACKAGE.parent) else Path('external')/str(path).lstrip('/')
                stream.add(path, arcname=arc, recursive=False)
        files[str(archive)] = storage.sha256(archive)
        frozen = dict(files=files, code_files=code_files,
            large_files_verified_once_then_stat=oldf.get('large_files_verified_once_then_stat', {}),
            config_sha256=storage.sha256(dest/'config.json'),stage=STAGE,bank_version=BANK,
            heldout_only=True,simulator_attempts_limit=2200,training_updates_limit=0)
        checked(ready_path, ready_sha)
        storage.dump(dest/'freeze.json', frozen);verify_authorization_inventory(cfg, frozen)
        from .heldout_runner_v1 import verify_frozen
        verify_frozen(dest/'config.json',dest/'freeze.json',STAGE,BANK,32)
        return dict(config=str(dest/'config.json'),config_sha256=storage.sha256(dest/'config.json'),
                    freeze=str(dest/'freeze.json'),freeze_sha256=storage.sha256(dest/'freeze.json'))
    except BaseException as error:
        storage.dump(dest/'preparation_failure.json',dict(error=repr(error),model_calls=0,simulator_calls=0,optimizer_updates=0))
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['pending','freeze']);parser.add_argument('--base-config',type=Path)
    parser.add_argument('--ready',type=Path,required=True);parser.add_argument('--output',type=Path)
    parser.add_argument('--pending-directory',type=Path);parser.add_argument('--version')
    parser.add_argument('--final-selection-reference',type=Path)
    parser.add_argument('--cpu-evidence',type=Path,action='append',default=[]);args=parser.parse_args()
    result=prepare_pending(args.base_config,args.ready,args.output,
        final_selection=read(args.final_selection_reference)) if args.action=='pending' else freeze(
        args.pending_directory,args.ready,args.cpu_evidence,version=args.version)
    print(json.dumps(result))
