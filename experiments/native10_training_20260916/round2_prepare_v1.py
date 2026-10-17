"""Isolated round2 CPU preparation; never launches models, simulators or workers.

Pending output is deliberately not runnable. A later explicit READY release and
current entrypoint CPU evidence are required for a separate immutable freeze.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import re
import shutil
import tarfile

from . import storage
from .prepare_fit import checked, sealed_directory
from .protocol import canonical_hash, protocol_digest, require_stage_budget, validate_protocol

CODE = Path(__file__).resolve().parent
STAGE = 'round2_labels'
SCOPE = 'round2_native10_local_labels'
RESERVE_SCOPE = 'preregistered_initialization_replacements'
BANK = 'round2_labels_v1'
TRAINING_SEAL = 'ff460f12c598a34a15a28ed7619ed071a60be195a3dd2f0c1c963a202ee22287'
SELECTED_SEAL = '931c6f6043db92b5d9003eb2833dfc8edd0ab6c860a1979db3983cd7d893725f'
BASE_CONFIG_SHA = 'f68b59f279ae4d03094ebe70f0185e29d7a65a8ce20903aed92ac4392f1e4fd2'
BASE_FREEZE_SHA = 'f46dda706607bf8ed52281d33a203471c2854b6c09f83e6d26d3b216a509d893'
NEW_CODE = ('round2_prepare_v1.py', 'round2_collection_v1.py', 'round2_runner_v1.py', 'run_round2_gpu_v1.sh')
CUT_POLICY = dict(policy='analysis_lead_v1',
    scheduled_priority={'15': [15, 5], '45': [45, 15, 5], '95': [95, 45, 15, 5]},
    no_alarm_training_priority=[15, 5], eligible='reached_live_midpoint_with_at_least_10_steps_remaining',
    original_request_fields_preserved=True)


def read(path):
    return json.loads(Path(path).read_text())


def original_slots(config):
    rows = [row for row in config['episode_manifest']
            if not row.get('replacement_of') and row['split'] == 'train' and row.get('round') == 2]
    if len(rows) != 300 or [r['env_seed'] for r in rows] != list(range(2026111300, 2026111600)):
        raise ValueError('Require the original ordered 300 train round2 primary identities')
    counts = Counter(row['task'] for row in rows)
    if len(counts) != 5 or set(counts.values()) != {60}:
        raise ValueError('Round2 requires sixty registered sources per original task')
    for task in counts:
        groups = Counter('alarm' if r['cut_rule']['kind'] == 'first_alarm' else
                         str(r['cut_rule']['step']) for r in rows if r['task'] == task)
        if groups != dict(alarm=30, **{'15': 10, '45': 10, '95': 10}):
            raise ValueError('Original cut50/50 and scheduled balance changed')
    return rows


def radii(rows):
    counts, result = defaultdict(int), {}
    for row in rows:
        index = counts[row['task']]; counts[row['task']] += 1
        result[row['episode_id']] = .5 if (index // 2) % 2 == 0 else 1.
    return result


def build_pending(base_config, ready_path):
    base_config = Path(base_config).resolve(); ready_path = Path(ready_path).resolve()
    checked(base_config, BASE_CONFIG_SHA)
    checked(base_config.with_name('freeze.json'), BASE_FREEZE_SHA)
    old, frozen = read(base_config), read(base_config.with_name('freeze.json'))
    if frozen['files'].get(str(base_config)) != storage.sha256(base_config):
        raise ValueError('Original collection configuration differs from its frozen identity')
    validate_protocol(old, require_runnable=True)
    selected_training = storage.ROOT/'models/round1/round1_fit_v1'
    sealed_directory(selected_training, TRAINING_SEAL)
    selected = selected_training/'selected'; sealed_directory(selected, SELECTED_SEAL)
    result = read(selected_training/'result.json')
    if (result['selection']['path'], result['selection']['step'], result['optimizer_updates']) != ('B', 200, 19200):
        raise ValueError('Only the already selected B200 is eligible as round2 generation critic')
    members = read(selected/'ranking.json')['model_hashes']
    if set(members) != {'0', '1', '2', '3'} or result['model_hashes'] != members:
        raise ValueError('Selected four-member identity mismatch')
    rows = original_slots(old); ids = [x['episode_id'] for x in rows]
    cfg = deepcopy(old); oldreg = old['main_collection']['banks']['round1_labels_v1']
    cfg.update(status='pending', analysis_approval={'status': 'pending'},
        analysis_ready={'path': str(ready_path), 'sha256': storage.sha256(ready_path)}, critic_assets=str(selected))
    cfg['main_collection']['banks'] = {BANK: dict(stage=STAGE, kind='labels13', episode_ids=ids,
        generation_round=2, cut_selection_policy='analysis_lead_v1', random_seed_domain='main_local_labels_v1',
        channel_radius_by_episode=radii(rows),
        model_hashes={**{k: oldreg['model_hashes'][k] for k in ('vla', 'd', 'g0', 'implementation')},
                      **{'critic_'+k: v for k, v in members.items()}}, critic_member_hashes=members)}
    cfg['stage_release_scopes'] = {stage: 'not_released_'+stage for stage in cfg['budget']['stages']}
    cfg['stage_release_scopes'].update(p0='p0_anchor_and_native10_diagnostics',
                                      round2_labels=SCOPE, technical_reserve=RESERVE_SCOPE)
    cfg['round2_collection'] = dict(schema='native10_round2_collection_v1',
        original_collection=dict(config_path=str(base_config), config_sha256=storage.sha256(base_config),
            freeze_path=str(base_config.with_name('freeze.json')),
            freeze_sha256=storage.sha256(base_config.with_name('freeze.json')), bank_version='round1_labels_v1'),
        selected_training=dict(path=str(selected_training), seal_sha256=TRAINING_SEAL, selected_seal_sha256=SELECTED_SEAL),
        effective_cut_policy=deepcopy(CUT_POLICY),
        requested_cut_rules_sha256=canonical_hash({x['episode_id']: x['cut_rule'] for x in rows}))
    references = [storage.PACKAGE/'coordination/NATIVE10_ROUND2_COLLECTION_DECISION.md',
                  storage.PACKAGE/'coordination/NATIVE10_ANALYSIS_LEAD.md']
    cfg['round2_preparation'] = dict(status='pending_explicit_round2_ready_and_final_cpu_freeze',
        original_primary_ids_canonical_sha256=canonical_hash(ids),
        primary_capture_planned=300, independent_bank_restores_planned=300, branch_upper_bound=16800,
        simulator_attempts_upper_bound=17400, optimizer_updates=0,
        candidate_count=13, normal_control_count=1, paired_suffixes=4,
        no_simulation_or_model_call_during_preparation=True,
        source_capture_allowed_after_stage_release=True, initialization_replacements='original_pre_action_chain_only',
        original_registration_placeholder='preserved in request; effective analysis_lead_v1 governs actual selection',
        decision_references={str(p): storage.sha256(p) for p in references})
    validate_protocol(cfg)
    return cfg


def _new(path):
    path = Path(path).resolve()
    if not path.is_relative_to(storage.ROOT.resolve()) or path.is_relative_to((storage.ROOT/'p0').resolve()):
        raise ValueError('Use a new workflow output outside P0')
    path.mkdir(parents=True, exist_ok=False)
    return path


def prepare_pending(base_config, ready_path, output):
    cfg = build_pending(base_config, ready_path)
    from .round2_collection_v1 import validate_round2_inputs
    dest = _new(output)
    registry = storage.ROOT/'scene_registry/entries.jsonl'
    with Path('/tmp/corrector_native10_scene_registry.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH); raw = registry.read_bytes()
    snapshot = dest/'scene_registry_before.jsonl'; snapshot.write_bytes(raw)
    cfg['round2_preparation']['scene_registry_before'] = dict(live_path=str(registry),
        snapshot_path=str(snapshot), sha256=storage.sha256(snapshot), bytes=len(raw), records=len(raw.splitlines()))
    audit = validate_round2_inputs(cfg, BANK, require_release=False)
    storage.dump(dest/'config.json', cfg)
    storage.dump(dest/'input_validation.json', audit)
    storage.dump(dest/'primary_manifest.json', original_slots(cfg))
    storage.dump(dest/'effective_cut_policy.json', cfg['round2_collection']['effective_cut_policy'])
    storage.dump(dest/'result.json', dict(status='passed_pending_only', runnable=False, stage=STAGE,
        episode_ids_canonical_sha256=cfg['round2_preparation']['original_primary_ids_canonical_sha256'],
        simulator_attempts=0, optimizer_updates=0, model_calls=0, config_sha256=storage.sha256(dest/'config.json')))
    storage.seal(dest, role='round2_isolated_preparation', simulator_attempts=0, optimizer_updates=0)
    return dict(path=str(dest), config_sha256=storage.sha256(dest/'config.json'), seal_sha256=storage.sha256(dest/'complete.json'))


def release(ready_path, config):
    ready = read(ready_path)
    if (ready.get('task_id') != 'native10-training-20260916'
            or not str(ready.get('status', '')).startswith('protocol_approved_')
            or not {SCOPE, RESERVE_SCOPE} <= set(ready.get('released_scope', []))):
        raise ValueError('Round2 and ordered pre-action replacement scopes must be explicitly released')
    row = ready.get('round2_collection', {})
    for key, value in dict(scope=SCOPE, stage=STAGE, bank_version=BANK, train_primary_slots=300,
        simulator_attempts_limit=17400, initialization_replacement_stage='technical_reserve',
        initialization_replacement_workflow_limit=1200).items():
        if row.get(key) != value:
            raise ValueError('READY round2 collection contract differs: '+key)
    if row.get('training_updates') != 0 or row.get('optimizer_updates_limit') != 0:
        raise ValueError('Round2 labels never release optimizer updates')
    execution = row.get('execution_policy', {})
    if any(execution.get(k) != v for k, v in dict(validated_workers=32, gpu_count=8, workers_per_gpu=4).items()):
        raise ValueError('Round2 execution layout differs from approved eight-GPU concurrency')
    if row.get('episode_ids_canonical_sha256') != config['round2_preparation']['original_primary_ids_canonical_sha256']:
        raise ValueError('READY does not bind the original ordered 300 primary identities')
    release_assets(row, config)
    references = {}
    for key, digest in ready.items():
        if key.endswith('_sha256') and isinstance(ready.get(key[:-7]), str):
            name = ready[key[:-7]]; path = Path(name)
            references[name] = checked(path if path.is_absolute() else storage.PACKAGE/path, digest)
    return ready, references


def release_assets(row, config):
    """Bind the released model, physical registry and candidate/capture contract."""
    from .candidates13 import CANDIDATE_ORDER
    expected = dict(kind='labels13', generation_round=2, capture_allowed=True,
        planned_primary_capture_limit=300, development_primary_slots=0,
        paired_suffixes_per_candidate=4, candidate_count=13, candidate_order=list(CANDIDATE_ORDER),
        separate_control_arm='continue_native10', total_arms_per_source=14, planned_attempts_per_source=58)
    if any(row.get(key) != value for key, value in expected.items()):
        raise ValueError('READY labels13/new capture contract differs')
    if row.get('episode_ids') != config['main_collection']['banks'][BANK]['episode_ids']:
        raise ValueError('READY original ordered IDs differ from the actual bank')
    selected = row.get('selected_critic', {})
    if (selected.get('path'), selected.get('step'), selected.get('members')) != ('B', 200, 4):
        raise ValueError('READY must name the frozen B200 four-member ensemble')
    if (selected['training_model_seal']['sha256'] != TRAINING_SEAL or selected['selected_seal']['sha256'] != SELECTED_SEAL
            or Path(selected['directory']).resolve() != Path(config['critic_assets']).resolve()):
        raise ValueError('READY selected model differs from the actual prepared assets')
    ranking = read(Path(config['critic_assets'])/'ranking.json')['model_hashes']
    if selected.get('member_checkpoint_sha256') != [ranking[str(i)] for i in range(4)]:
        raise ValueError('READY ordered B200 member hashes differ')
    for name in ('training_model_seal', 'selected_seal', 'selected_reload_audit'):
        checked(selected[name]['path'], selected[name]['sha256'])
    for reference in row['primary_registration'].values():
        if isinstance(reference, dict) and set(reference) >= {'path', 'sha256'}:
            checked(reference['path'], reference['sha256'])
    for reference in row['selected_preprocessing'].values():
        if isinstance(reference, dict) and set(reference) >= {'path', 'sha256'}:
            checked(reference['path'], reference['sha256'])
    scene = row['scene_identity']
    if scene.get('heldout_initialization_allowed') is not False:
        raise ValueError('Round2 cannot initialize heldout')
    checked(scene['registry_before']['path'], scene['registry_before']['sha256'])
    for reference in scene['replacement_policy'].values():
        if isinstance(reference, dict) and set(reference) >= {'path', 'sha256'}:
            checked(reference['path'], reference['sha256'])


def cpu_checks(evidence_paths):
    required = {str((CODE/name).resolve()) for name in NEW_CODE}
    required |= {str((CODE/name).resolve()) for name in ('test_round2_collection_v1.py', 'test_round2_runner_v1.py')}
    required.add(str((storage.PACKAGE/'tests/test_native10_round2_prepare_v1.py').resolve()))
    covered = {}
    for path in evidence_paths:
        path = Path(path).resolve(); sealed_directory(path, storage.sha256(path/'complete.json'))
        result = read(path/'result.json')
        before, after = result.get('code_sha256_before', {}), result.get('code_sha256_after', {})
        if (result.get('status') != 'passed' or result.get('returncode') != 0
                or result.get('shell_returncode', 0) != 0 or not before or before != after
                or any(result.get(k) != 0 for k in ('model_calls', 'simulator_calls', 'optimizer_updates'))):
            raise ValueError('CPU evidence must pass with fixed code and zero formal work')
        for name, digest in after.items():
            checked(name, digest); covered[name] = digest
    if not required <= set(covered):
        raise ValueError('CPU evidence omits actual round2 prepare/guard/runner/tests')
    return covered


def merge_frozen_files(old_files, extra_files):
    if any(name in old_files and digest != old_files[name] for name, digest in extra_files.items()):
        raise ValueError('New freeze must not replace any old frozen dependency identity')
    return {**old_files, **extra_files}


def check_registry_snapshot(snapshot, ready):
    reference = ready['round2_collection']['scene_identity']['registry_before']
    return checked(snapshot, reference['sha256'])


def freeze(base_config, ready_path, cpu_evidence, *, version):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,60}', version):
        raise ValueError('Unsafe independent protocol version')
    cfg = build_pending(base_config, ready_path)
    ready, references = release(ready_path, cfg)  # No creation before explicit permission.
    coverage = cpu_checks(cpu_evidence)
    old = read(Path(base_config).with_name('freeze.json'))
    for name, digest in old['files'].items():
        checked(name, digest)
    ready_digest = cfg['analysis_ready']['sha256']
    checked(ready_path, ready_digest)
    reference_hashes = {ready[key[:-7]]: digest for key, digest in ready.items()
                       if key.endswith('_sha256') and isinstance(ready.get(key[:-7]), str)}
    dest = _new(storage.ROOT/'main_protocols'/version)
    try:
        for name, original in references.items():
            rel = Path(name)
            if not rel.is_absolute():
                target = dest/rel; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target); checked(target, reference_hashes[name])
        snapshots = dest/'coordination'; snapshots.mkdir(exist_ok=True)
        ready_path = Path(ready_path).resolve(); shutil.copyfile(ready_path, snapshots/ready_path.name)
        checked(snapshots/ready_path.name, ready_digest)
        cfg['analysis_ready'] = dict(path=str(snapshots/ready_path.name), sha256=storage.sha256(snapshots/ready_path.name))
        cfg['analysis_documents'] = {str(dest/Path(n)): storage.sha256(p) for n, p in references.items()
                                      if not Path(n).is_absolute() and Path(n).suffix == '.md'}
        effective_references = {}
        for name, digest in cfg['round2_preparation']['decision_references'].items():
            original = checked(name, digest); target = dest/original.relative_to(storage.PACKAGE)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(original, target)
            checked(target, digest); effective_references[str(target)] = digest
        cfg['round2_preparation']['decision_references'] = effective_references
        registry = storage.ROOT/'scene_registry/entries.jsonl'
        with Path('/tmp/corrector_native10_scene_registry.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_SH); raw = registry.read_bytes()
        snapshot = dest/'scene_registry_before.jsonl'; snapshot.write_bytes(raw)
        check_registry_snapshot(snapshot, ready)
        cfg['round2_preparation'].update(status='frozen_round2_collection_only', version=version,
            scene_registry_before=dict(live_path=str(registry), snapshot_path=str(snapshot),
                sha256=storage.sha256(snapshot), bytes=len(raw), records=len(raw.splitlines())),
            cpu_evidence=[dict(path=str(Path(p).resolve()), seal_sha256=storage.sha256(Path(p)/'complete.json')) for p in cpu_evidence])
        cfg['status'] = 'frozen'; task = dest/ready['task_document']
        cfg['analysis_approval'] = dict(status='approved', approved_by='analysis', document_path=str(task),
            document_sha256=storage.sha256(task), protocol_sha256=protocol_digest(cfg))
        require_stage_budget(cfg, STAGE); require_stage_budget(cfg, 'technical_reserve')
        from .round2_collection_v1 import validate_round2_inputs
        storage.dump(dest/'input_validation.json', validate_round2_inputs(cfg, BANK, require_release=True))
        storage.dump(dest/'config.json', cfg)
        files = dict(old['files'])
        extras = [CODE/name for name in NEW_CODE] + [CODE/'prepare_fit.py', Path(base_config), Path(base_config).with_name('freeze.json')]
        extras += [Path(name) for name in coverage]
        extras += [p for p in dest.rglob('*') if p.is_file()]
        for evidence in cpu_evidence:
            extras += [p for p in Path(evidence).rglob('*') if p.is_file()]
        trained = Path(cfg['round2_collection']['selected_training']['path'])
        extras += [trained/'complete.json', trained/'result.json', trained/'selected_reload_audit.json']
        extras += [p for p in (trained/'selected').rglob('*') if p.is_file()]
        files = merge_frozen_files(files, {str(p.resolve()): storage.sha256(p) for p in extras})
        code_files = {name: digest for name, digest in files.items() if Path(name).suffix in ('.py', '.sh')}
        archive = dest/'code_snapshot.tar.gz'
        with tarfile.open(archive, 'x:gz') as stream:
            for name in sorted(code_files):
                path = Path(name); rel = path.relative_to(storage.PACKAGE.parent) if path.is_relative_to(storage.PACKAGE.parent) else Path('external')/str(path).lstrip('/')
                stream.add(path, arcname=rel, recursive=False)
        files[str(archive)] = storage.sha256(archive)
        storage.dump(dest/'freeze.json', dict(files=files, code_files=code_files,
            large_files_verified_once_then_stat=old['large_files_verified_once_then_stat'],
            config_sha256=storage.sha256(dest/'config.json'), stage=STAGE, bank_version=BANK,
            round2_collection_only=True, simulator_attempts_limit=17400, training_updates_limit=0))
        from .round2_runner_v1 import verify_frozen
        verify_frozen(dest/'config.json', dest/'freeze.json', STAGE, BANK, 32)
        return dict(config=str(dest/'config.json'), config_sha256=storage.sha256(dest/'config.json'),
            freeze=str(dest/'freeze.json'), freeze_sha256=storage.sha256(dest/'freeze.json'))
    except BaseException as error:
        storage.dump(dest/'preparation_failure.json', dict(error=repr(error), simulator_attempts=0, optimizer_updates=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('pending', 'freeze'))
    parser.add_argument('--base-config', type=Path, required=True)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--version')
    parser.add_argument('--cpu-evidence', type=Path, action='append', default=[])
    args = parser.parse_args()
    result = prepare_pending(args.base_config, args.ready, args.output) if args.action == 'pending' else freeze(
        args.base_config, args.ready, args.cpu_evidence, version=args.version)
    print(json.dumps(result))
