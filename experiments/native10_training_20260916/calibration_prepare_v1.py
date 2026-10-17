"""Metadata-only calibration preparation and separately authorized immutable freeze.

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
from .prepare_fit import checked, sealed_directory
from .protocol import TASKS, canonical_hash, protocol_digest, require_stage_budget, validate_protocol

CODE = Path(__file__).resolve().parent
STAGE = SCOPE = 'calibration'
BANK = 'calibration_policy_v1'
SCHEMA = 'native10_calibration_collection_v1'
PRIMARY_IDS_SHA = 'd2b7ca3b17c322e28610735d871dc319e5e7f24439d2cb4c48c5d00ec705f44e'
RESERVE_SCOPE = 'calibration_initialization_replacements'
BASE_CONFIG_SHA = 'd2a60785fc84063e02fee965fa8ba009b3880783ac58adf5dc9ce4011c819dc0'
BASE_FREEZE_SHA = 'cdbb364de29b44fea522f3740c185ccc97337f9123662e720e2f7903def5f292'
DECISION = 'coordination/NATIVE10_CALIBRATION_PREPARATION_DECISION.md'
DECISION_SHA = 'bb8e6c7f7eb145337b25ba6c859bf456754eead33062989aefff0d06c3314fd8'
ARMS = ['continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post']
GLOBAL_ACCEPTANCE = dict(primary_method='post', fallback_method='alarm_replan10',
    rule='mean_paired_post_minus_replan_strictly_positive', source_denominator=100,
    replicates=2, no_cut_difference=0)
CUT_POLICY = dict(policy='first_legal_alarm_only', training_fallback_allowed=False,
                  no_alarm_common_outcome=True)
NEW_CODE = ('calibration_prepare_v1.py', 'calibration_collection_v1.py',
            'calibration_runner_v1.py', 'run_calibration_gpu_v1.sh', 'calibration_statistics_v1.py')
NEW_TESTS = ('test_calibration_prepare_v1.py', 'test_calibration_collection_v1.py',
             'test_calibration_runner_v1.py', 'test_calibration_statistics_v1.py')


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
    seeds = list(range(2026111700, 2026111750))+list(range(2026111800, 2026111850))
    if (len(rows) != 100 or [x['env_seed'] for x in rows] != seeds
            or Counter(x['task'] for x in rows) != {task: 20 for task in TASKS}
            or len({x['episode_id'] for x in rows}) != 100
            or any(x.get('round') is not None or x['cut_rule'] != {'kind': 'first_alarm'} for x in rows)):
        raise ValueError('Calibration requires the original ordered 100 registered first-alarm slots')
    if canonical_hash([x['episode_id'] for x in rows]) != PRIMARY_IDS_SHA:
        raise ValueError('Calibration original ordered IDs changed')
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
            raise ValueError('Calibration preparation cannot reuse an initialized source: '+identity)
    return set(all_ids)


def build_pending(base_config, ready_path):
    base = checked(Path(base_config).resolve(), BASE_CONFIG_SHA)
    frozen_path = checked(base.with_name('freeze.json'), BASE_FREEZE_SHA)
    old, frozen = read(base), read(frozen_path)
    if frozen['files'].get(str(base)) != BASE_CONFIG_SHA:
        raise ValueError('Scientific base config is not bound by its original freeze')
    validate_protocol(old, require_runnable=True)
    checked(storage.PACKAGE/DECISION, DECISION_SHA)
    rows = original_slots(old); ids = [x['episode_id'] for x in rows]
    oldreg = old['main_collection']['banks']['round2_policy_v1']
    cfg = deepcopy(old)
    for key in ('policy_deployment', 'policy_preparation', 'policy_statistics'):
        cfg.pop(key, None)
    cfg.update(status='pending', analysis_approval={'status': 'pending'},
        analysis_ready=dict(path=str(Path(ready_path).resolve()), sha256=storage.sha256(ready_path)))
    cfg['main_collection']['banks'] = {BANK: dict(stage=STAGE, kind='policy5', episode_ids=ids,
        generation_round=2, generation_phase=STAGE, cut_selection_policy='analysis_lead_v1',
        random_seed_domain=oldreg['random_seed_domain'], model_hashes=deepcopy(oldreg['model_hashes']),
        critic_member_hashes=deepcopy(oldreg['critic_member_hashes']))}
    cfg['stage_release_scopes'] = {name: 'not_released_'+name for name in cfg['budget']['stages']}
    cfg['stage_release_scopes'].update(p0='p0_anchor_and_native10_diagnostics',
                                      calibration=SCOPE, technical_reserve=RESERVE_SCOPE)
    cfg['calibration_collection'] = dict(schema=SCHEMA,
        original_collection=dict(config_path=str(base), config_sha256=BASE_CONFIG_SHA,
            freeze_path=str(frozen_path), freeze_sha256=BASE_FREEZE_SHA, bank_version='round2_policy_v1'),
        selected_training=deepcopy(old['policy_deployment']['selected_training']),
        requested_cut_rules_sha256=canonical_hash({x['episode_id']: x['cut_rule'] for x in rows}),
        effective_cut_policy=deepcopy(CUT_POLICY), global_acceptance=deepcopy(GLOBAL_ACCEPTANCE))
    cfg['calibration_preparation'] = dict(status='pending_explicit_calibration_ready_and_cpu_freeze',
        base_policy=deepcopy(cfg['calibration_collection']['original_collection']),
        registration_origin=deepcopy(old['policy_deployment']['old_collection']),
        original_primary_ids_canonical_sha256=canonical_hash(ids), primary_capture_planned=100,
        independent_bank_restores_upper_bound=100, branch_upper_bound=1000,
        simulator_attempts_upper_bound=1200, optimizer_updates=0,
        capture_allowed_after_release=True, heldout_initialization_allowed=False,
        selection_seal_authorized=False, physical_initial_uniqueness_established=False,
        decision_references={str(storage.PACKAGE/DECISION): DECISION_SHA})
    validate_protocol(cfg)
    return cfg


def ready_contract(config):
    """Exact mandatory future READY.calibration row; additional provenance is allowed."""
    collection = config['calibration_collection']; prep = config['calibration_preparation']
    reg = config['main_collection']['banks'][BANK]; rows = original_slots(config)
    model = collection['selected_training']; path = Path(model['path'])
    members = reg['critic_member_hashes']
    scene = prep.get('authorized_scene_registry_before', prep['scene_registry_before'])
    return dict(scope=SCOPE, stage=STAGE, bank_version=BANK, schema=SCHEMA,
        simulator_attempts_limit=1200, simulator_attempts_upper_bound=1200,
        optimizer_updates_limit=0, training_updates=0, primary_capture_limit=100,
        calibration_primary_slots=100, per_task_source_counts=dict(Counter(x['task'] for x in rows)),
        paired_suffixes_per_state=2, arms=list(ARMS), per_arm_outcome_denominator=200,
        episode_ids=reg['episode_ids'], episode_ids_canonical_sha256=canonical_hash(reg['episode_ids']),
        input_config_sha256=collection['original_collection']['config_sha256'],
        input_freeze_sha256=collection['original_collection']['freeze_sha256'],
        original_collection=deepcopy(collection['original_collection']),
        full_manifest_sha256=canonical_hash(config['episode_manifest']),
        replacement_candidates_sha256=canonical_hash(config['main_collection']['replacement_candidates']),
        candidate_generation_round=2, generation_phase=STAGE, capture_allowed=True,
        heldout_initialization_allowed=False, old_development_anchor_reuse_allowed=False,
        initialization_replacement_stage='technical_reserve', initialization_replacement_scope=RESERVE_SCOPE,
        initialization_replacement_workflow_limit=1200,
        initialization_replacement_allowed_primary_ids_sha256=canonical_hash(reg['episode_ids']),
        initialization_replacement_reasons=['duplicate_initial_scene', 'initialization_failed'],
        global_simulator_hard_limit=50000, workflow_optimizer_hard_limit=51200,
        optimizer_updates_remaining=0, global_acceptance=deepcopy(GLOBAL_ACCEPTANCE),
        selection_seal_authorized=False, effective_cut_policy=deepcopy(CUT_POLICY),
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


def prepare_pending(base_config, ready_path, output):
    cfg = build_pending(base_config, ready_path)
    uninitialized_ids = assert_uninitialized(cfg)
    dest = _new(output); registry = storage.ROOT/'scene_registry/entries.jsonl'
    with Path('/tmp/corrector_native10_scene_registry.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH); raw = registry.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Scene registry snapshot must end on a complete record')
    if any(json.loads(line).get('episode_id') in uninitialized_ids for line in raw.splitlines()):
        raise ValueError('Calibration initial scene was already registered')
    snapshot = dest/'scene_registry_before.jsonl'; snapshot.write_bytes(raw)
    cfg['calibration_preparation']['scene_registry_before'] = dict(live_path=str(registry),
        snapshot_path=str(snapshot), sha256=storage.sha256(snapshot), bytes=len(raw), records=len(raw.splitlines()))
    from .calibration_collection_v1 import validate_calibration_inputs
    audit = validate_calibration_inputs(cfg, BANK, require_release=False)
    storage.dump(dest/'config.json', cfg)
    storage.dump(dest/'primary_manifest.json', original_slots(cfg))
    storage.dump(dest/'ready_contract.json', ready_contract(cfg))
    storage.dump(dest/'input_validation.json', audit)
    storage.dump(dest/'result.json', dict(status='passed_pending_only', runnable=False, stage=STAGE,
        config_sha256=storage.sha256(dest/'config.json'), simulator_calls=0, model_calls=0, optimizer_updates=0))
    storage.seal(dest, role='calibration_isolated_preparation', simulator_attempts=0, optimizer_updates=0)
    return dict(path=str(dest), config_sha256=storage.sha256(dest/'config.json'),
                seal_sha256=storage.sha256(dest/'complete.json'))


def _scope(ready_path):
    ready = read(ready_path)
    if (ready.get('task_id') != 'native10-training-20260916'
            or not (ready.get('status') == 'approved' or str(ready.get('status', '')).startswith('protocol_approved_'))
            or not {SCOPE, RESERVE_SCOPE} <= set(ready.get('released_scope', []))):
        raise ValueError('READY must explicitly release calibration and its separate initialization reserve')
    return ready


def authorization_references(ready, *, base_dir=None):
    """Enumerate nested JSON path/SHA pairs, including file-to-SHA mappings.

    Relative paths use the Corrector package root, matching READY's established
    convention. A directory+seal_sha256 reference means its complete.json. This
    traverses nested READY values, not the contents of arbitrary referenced JSON.
    Mutable global logs must instead be represented by immutable prefix snapshots.
    """
    base = Path(base_dir or storage.PACKAGE).resolve(); found = {}
    mutable = {(storage.ROOT/'scene_registry/entries.jsonl').resolve(),
               (storage.ROOT/'budget/attempts.jsonl').resolve()}
    def add(name, digest, location, *, seal=False):
        if not isinstance(name, str) or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Authorization path/SHA pair is malformed: '+location)
        p = Path(name); p = (p if p.is_absolute() else base/p).resolve()
        if seal and p.name != 'complete.json':
            p = p/'complete.json'
        if p in mutable:
            raise ValueError('Authorization must bind an immutable snapshot, not live ledger/scene registry: '+str(p))
        key = str(p)
        if key in found and found[key]['sha256'] != digest:
            raise ValueError('Conflicting authorization SHA for '+key)
        row = found.setdefault(key, dict(original_path=key, sha256=digest, references=[]))
        row['references'].append(location)
    def walk(value, location):
        if isinstance(value, dict):
            for k, digest in value.items():
                if k.endswith('_sha256'):
                    stem = k[:-7]
                    for field in (stem, stem+'_path'):
                        if isinstance(value.get(field), str):
                            add(value[field], digest, location+'/'+k+':'+field)
            if 'sha256' in value:
                candidates = [k for k in ('path', 'snapshot_path', 'file', 'directory') if isinstance(value.get(k), str)]
                if not candidates:
                    raise ValueError('Unpaired authorization sha256 at '+location)
                for k in candidates:
                    add(value[k], value['sha256'], location+'/sha256:'+k)
            if 'seal_sha256' in value and isinstance(value.get('path'), str):
                add(value['path'], value['seal_sha256'], location+'/seal_sha256:path', seal=True)
            if 'seal_sha256' in value and isinstance(value.get('directory'), str):
                add(value['directory'], value['seal_sha256'], location+'/seal_sha256:directory', seal=True)
            for k, v in value.items():
                if isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) and ('/' in k or Path(k).suffix):
                    add(k, v, location+'/'+k)
                walk(v, location+'/'+k)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, location+'/'+str(i))
    walk(ready, '$')
    return [dict(row, references=sorted(set(row['references']))) for _, row in sorted(found.items())]


def release(ready_path, config):
    ready = _scope(ready_path)  # Missing scope must fail before all bound input reads.
    expected = ready_contract(config); actual = ready.get(STAGE, {})
    if any(actual.get(k) != v for k, v in expected.items()):
        changed = [k for k, v in expected.items() if actual.get(k) != v]
        raise ValueError('READY calibration contract differs: '+','.join(changed))
    references = authorization_references(ready)
    for row in references:
        checked(row['original_path'], row['sha256'])
    return ready, references


def snapshot_authorization_references(ready, dest):
    dest = Path(dest).resolve(); rows = authorization_references(ready)
    for index, row in enumerate(rows):
        original = checked(row['original_path'], row['sha256'])
        target = dest/'authorization_references'/f'{index:04d}_{original.name}'
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(original.read_bytes())
        checked(target, row['sha256']); row['snapshot_path'] = str(target)
        # protocol._validate_ready resolves relative task/review under freeze root.
        for key in ('task_document', 'protocol_review'):
            if isinstance(ready.get(key), str) and not Path(ready[key]).is_absolute():
                rel = (dest/ready[key]).resolve()
                if not rel.is_relative_to(dest):
                    raise ValueError('Relative authorization document escapes new freeze')
                if original == (storage.PACKAGE/ready[key]).resolve():
                    rel.parent.mkdir(parents=True, exist_ok=True)
                    if not rel.exists(): shutil.copyfile(original, rel)
                    checked(rel, row['sha256'])
    record = dict(schema='native10_authorization_reference_inventory_v1', status='passed',
        traversal='all nested READY mappings/lists and paired path/SHA fields', references=rows)
    storage.dump(dest/'authorization_inventory.json', record)
    return record


def verify_authorization_inventory(config, frozen):
    """Pure read-only completeness/identity gate for the actual runner."""
    ready_ref = config['analysis_ready']; ready_path = checked(ready_ref['path'], ready_ref['sha256'])
    expected = authorization_references(read(ready_path))
    ref = config['calibration_preparation']['authorization_inventory']
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
        raise ValueError('CPU evidence omits actual calibration entrypoints or tests')
    return covered


def _preparation_binding(pending, cpu_evidence, coverage):
    pending = Path(pending).resolve()
    return dict(pending_inputs=dict(path=str(pending), seal_sha256=storage.sha256(pending/'complete.json')),
        ready_contract=dict(path=str(pending/'ready_contract.json'), sha256=storage.sha256(pending/'ready_contract.json')),
        cpu_evidence=[dict(path=str(Path(p).resolve()), seal_sha256=storage.sha256(Path(p)/'complete.json'))
                      for p in cpu_evidence], code_sha256=deepcopy(coverage))


def expected_preparation_binding(pending, cpu_evidence):
    """Metadata-only exact future READY.calibration_preparation_binding payload."""
    pending = Path(pending).resolve()
    record = sealed_directory(pending, storage.sha256(pending/'complete.json'))
    if record.get('role') != 'calibration_isolated_preparation':
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
    if ps.get('role') != 'calibration_isolated_preparation': raise ValueError('Wrong pending artifact role')
    cfg = deepcopy(read(pending/'config.json'));ready, _ = release(ready_path, cfg)
    checked(ready_path, ready_sha)
    if ready != json.loads(ready_bytes): raise ValueError('Validated READY differs from captured bytes')
    assert_uninitialized(cfg)
    coverage = cpu_checks(cpu_evidence)
    if (read(pending/'ready_contract.json') != ready_contract(cfg)
            or ready.get('calibration_preparation_binding') != _preparation_binding(pending, cpu_evidence, coverage)):
        raise ValueError('READY must bind these exact pending inputs, contract, CPU evidence and current code')
    base = cfg['calibration_collection']['original_collection'];oldf = read(checked(base['freeze_path'], base['freeze_sha256']))
    checked(base['config_path'], base['config_sha256'])
    from .calibration_collection_v1 import validate_calibration_inputs
    validate_calibration_inputs(cfg, BANK, require_release=False)
    dest = _new(storage.ROOT/'calibration_protocols'/version)
    try:
        snapshot = dest/'coordination/NATIVE10_ANALYSIS_READY.json';snapshot.parent.mkdir()
        checked(ready_path, ready_sha)
        snapshot.write_bytes(ready_bytes);checked(snapshot, ready_sha)
        inventory = snapshot_authorization_references(ready, dest)
        cfg['analysis_ready'] = dict(path=str(snapshot), sha256=storage.sha256(snapshot))
        prep = cfg['calibration_preparation']
        # Copy the preregistered prefix; never lock/hash the growing live registry.
        scene = prep['scene_registry_before'];old_snapshot = checked(scene['snapshot_path'], scene['sha256'])
        prep['authorized_scene_registry_before'] = deepcopy(scene)
        target = dest/'scene_registry_before.jsonl';shutil.copyfile(old_snapshot, target);checked(target, scene['sha256'])
        scene['snapshot_path'] = str(target)
        prep.update(status='frozen_calibration_collection_only', version=version,
            pending_inputs=dict(path=str(pending), seal_sha256=storage.sha256(pending/'complete.json')),
            cpu_evidence=[dict(path=str(Path(p).resolve()), seal_sha256=storage.sha256(Path(p)/'complete.json')) for p in cpu_evidence],
            authorization_inventory=dict(path=str(dest/'authorization_inventory.json'), sha256=storage.sha256(dest/'authorization_inventory.json')))
        cfg['status'] = 'frozen'
        task = Path(ready['task_document']);task = task if task.is_absolute() else dest/task
        cfg['analysis_approval'] = dict(status='approved', approved_by='analysis', document_path=str(task),
            document_sha256=storage.sha256(task), protocol_sha256=protocol_digest(cfg))
        require_stage_budget(cfg, STAGE);require_stage_budget(cfg, 'technical_reserve')
        storage.dump(dest/'input_validation.json', validate_calibration_inputs(cfg, BANK, require_release=True))
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
            calibration_only=True,simulator_attempts_limit=1200,training_updates_limit=0)
        checked(ready_path, ready_sha)
        storage.dump(dest/'freeze.json', frozen);verify_authorization_inventory(cfg, frozen)
        from .calibration_runner_v1 import verify_frozen
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
    parser.add_argument('--cpu-evidence',type=Path,action='append',default=[]);args=parser.parse_args()
    result=prepare_pending(args.base_config,args.ready,args.output) if args.action=='pending' else freeze(
        args.pending_directory,args.ready,args.cpu_evidence,version=args.version)
    print(json.dumps(result))
