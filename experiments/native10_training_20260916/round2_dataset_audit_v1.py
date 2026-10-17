"""Post-wave round2 static audit. Never creates a model or simulator.

The full wave/slot gate precedes the outcome loader. Original collection files
remain immutable; all derived outputs use exclusive new version directories.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import fcntl
import hashlib
import json
from pathlib import Path
import re

from . import storage

STAGE, BANK = 'round2_labels', 'round2_labels_v1'
SCHEMA = 'native10_round2_dataset_completion_audit_v1'
CONTRACT_SHA = 'bceeccecbe2f5a41a27f05e8245ee8b9e68c525e8cb3d653a3460f275fab54a0'
READINESS_SHA = 'cd59280a23803bee7fbe25d969b20c5f0a4960ec0e3708e4a45cbf1b0b6ea587'
CONTRACT = storage.PACKAGE/'coordination/NATIVE10_FINAL_INPUT_CONTRACT.md'
BASE_CONFIG_SHA = 'f68b59f279ae4d03094ebe70f0185e29d7a65a8ce20903aed92ac4392f1e4fd2'
BASE_FREEZE_SHA = 'f46dda706607bf8ed52281d33a203471c2854b6c09f83e6d26d3b216a509d893'


def _read(path):
    return json.loads(Path(path).read_text())


def _component(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value):
        raise ValueError('Explicit safe new version/wave component required')
    return value


def _inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(storage.ROOT.resolve()):
        raise ValueError('Input escaped workflow ROOT')
    return path


def _record_file(path, evidence, *, expected=None):
    path = _inside(path)
    actual = storage.sha256(path)
    if expected is not None and actual != expected:
        raise ValueError('Evidence SHA mismatch: '+str(path))
    previous = evidence.setdefault(str(path), actual)
    if previous != actual:
        raise ValueError('Evidence changed during audit: '+str(path))
    return path


def _sealed(folder, protocol, evidence, *, role=None):
    folder = _inside(folder)
    complete = _record_file(folder/'complete.json', evidence)
    record = _read(complete)
    if (record.get('status') != 'complete' or record.get('protocol_sha256') != protocol
            or role is not None and record.get('role') != role):
        raise ValueError('Unexpected completed artifact identity: '+str(folder))
    files = record.get('files', {})
    actual = {str(p.relative_to(folder)) for p in folder.rglob('*')
              if p.is_file() and p != complete}
    if set(files) != actual:
        raise ValueError('Completed artifact file inventory changed: '+str(folder))
    for name, digest in files.items():
        path = (folder/name).resolve()
        if not path.is_relative_to(folder):
            raise ValueError('Unsafe sealed file')
        _record_file(path, evidence, expected=digest)
    return record


def _verify_frozen(config_path, freeze_path):
    # Pure byte/stat/registration checks; runner.verify_frozen does not load models.
    from .round2_runner_v1 import verify_frozen
    return verify_frozen(config_path, freeze_path, STAGE, BANK, 32)


def _loaded_identity(record, config):
    selected = Path(config['critic_assets']).resolve()
    hashes = config['main_collection']['banks'][BANK]['critic_member_hashes']
    paths = [str(selected/f'models/refit/member_{m}/selected.pt') for m in hashes]
    required = {'actual_selector_paths', 'checkpoint_file_sha',
                'frozen_parameter_buffer_versions', 'eval_cpu_no_parameter_grad'}
    if (set(hashes) != {'0', '1', '2', '3'} or record.get('status') != 'passed'
            or record.get('selected_path') != str(selected) or record.get('model_hashes') != hashes
            or record.get('model_paths') != paths
            or record.get('selected_seal_sha256') != config['round2_collection']['selected_training']['selected_seal_sha256']
            or not required <= set(record.get('checks', []))
            or record.get('optimizer_updates') != 0 or record.get('candidate_generation_only') is not True):
        raise ValueError('Worker did not attest the actual frozen B200 ensemble')


def _wave_gate(config, config_path, freeze_path, wave_id):
    """Technical metadata only; never parses collection/source success labels."""
    root = storage.ROOT.resolve()
    wave = root/'round2_execution'/STAGE/BANK/_component(wave_id)
    evidence = {}
    launch = _read(_record_file(wave/'launch_result.json', evidence))
    if (launch.get('status') != 'complete' or type(launch.get('returncode')) is not int
            or launch['returncode'] != 0 or launch.get('lifecycle_covers_entire_wave') is not True
            or launch.get('hold_idle') is not False or launch.get('next_stage_automatically_started') is not False):
        raise ValueError('Successful full-wave lifecycle exit is required before outcome access')
    spec_path = _record_file(wave/'wave_spec.json', evidence)
    spec = _read(spec_path)
    cfgsha, freezesha = storage.sha256(config_path), storage.sha256(freeze_path)
    if (spec.get('config_sha256') != cfgsha or spec.get('freeze_sha256') != freezesha
            or spec.get('stage') != STAGE or spec.get('bank_version') != BANK
            or spec.get('workers') != 32 or spec.get('hold_idle') is not False
            or spec.get('original_primary_slots') != 300):
        raise ValueError('Wave specification differs from the frozen round2 inputs')
    command = launch.get('command', [])
    if (not isinstance(command, list) or '--spec' not in command
            or command[command.index('--spec')+1:] != [str(spec_path)]):
        raise ValueError('Lifecycle result does not bind this wave specification')
    ids = config['main_collection']['banks'][BANK]['episode_ids']
    lookup = {row['episode_id']: row for row in config['episode_manifest']}
    if (len(ids) != 300 or len(set(ids)) != 300
            or any(lookup[x]['split'] != 'train' or lookup[x].get('round') != 2
                   or lookup[x].get('replacement_of') for x in ids)):
        raise ValueError('Round2 gate requires all original 300 primary train slots')
    workers = wave/'workers'
    if {p.name for p in workers.iterdir() if p.is_dir()} != {f'worker_{n:02d}' for n in range(32)}:
        raise ValueError('All 32 worker directories are required')
    protocol = config['analysis_approval']['protocol_sha256']
    dispositions, missing, rejects = {}, [], []
    for rank in range(32):
        folder = workers/f'worker_{rank:02d}'
        _sealed(folder, protocol, evidence, role='guarded_round2_worker')
        if (folder/'failure.json').exists():
            raise ValueError('Failed worker cannot claim complete audit readiness')
        status = _read(folder/'status.json')
        assigned = ids[rank::32]
        expected = dict(stage=STAGE, bank_version=BANK, wave_id=wave_id, rank=rank, workers=32,
                        config_sha256=cfgsha, freeze_sha256=freezesha, protocol_sha256=protocol,
                        assigned_slot_ids=assigned, completed_slot_records=len(assigned),
                        guard_factory='create_round2_collector', slot_entry='collect_round2_slot',
                        next_stage_automatically_started=False)
        if any(status.get(k) != v for k, v in expected.items()):
            raise ValueError('Worker final status differs from frozen assignment')
        _loaded_identity(_read(folder/'loaded_model_identity.json'), config)
        slot_files = {p.stem for p in (folder/'slots').glob('*.json')}
        if slot_files != set(assigned):
            raise ValueError('Not all assigned slots have final dispositions')
        worker_missing = []
        for identity in assigned:
            slot = _read(folder/'slots'/f'{identity}.json')
            actual = slot.get('resolved_episode_id')
            chain = [identity]+config['main_collection']['replacement_candidates'][identity]
            if slot.get('planned_slot_id') != identity or identity in dispositions:
                raise ValueError('Slot identity repeated or changed')
            if slot.get('status') == 'complete':
                if actual not in chain:
                    raise ValueError('Resolved source is outside the original replacement chain')
                rejected_ids = chain[:chain.index(actual)]
                resolution_path = root/'slot_resolution'/identity
                if Path(slot.get('resolution_path', '')).resolve() != resolution_path:
                    raise ValueError('Unexpected resolution path')
                _sealed(resolution_path, protocol, evidence)
                resolution = _read(resolution_path/'resolution.json')
                primary, case = lookup[identity], lookup[actual]
                expected_resolution = dict(status='resolved', planned_slot_id=identity, resolved_episode_id=actual,
                    task=primary['task'], split='train', round=2, original_env_seed=primary['env_seed'],
                    resolved_env_seed=case['env_seed'], source_protocol_sha256=protocol,
                    substitution_after_outcome_forbidden=True, ordered_rejections=slot.get('ordered_rejections'))
                if any(resolution.get(k) != v for k, v in expected_resolution.items()):
                    raise ValueError('Resolution identity/chain differs from worker disposition')
                _record_file(root/'sources'/case['case_id']/'complete.json', evidence,
                             expected=resolution['source_seal_sha256'])
                collection = root/'collections'/STAGE/BANK/case['case_id']
                if Path(slot.get('completion_path', '')).resolve() != collection:
                    raise ValueError('Unexpected completed collection path')
                _record_file(collection/'complete.json', evidence, expected=slot['completion_sha256'])
                _sealed(collection, protocol, evidence)  # summary bytes hashed, never parsed here.
            elif slot.get('status') == 'missing_unique_initial_scene':
                if actual is not None or slot.get('outcome_unknown') is not True:
                    raise ValueError('Missing source must retain unknown outcome')
                rejected_ids = chain
                missing.append(identity); worker_missing.append(identity)
            else:
                raise ValueError('Slot has no accepted terminal disposition')
            rejections = slot.get('ordered_rejections', [])
            if [row.get('episode_id') for row in rejections] != rejected_ids:
                raise ValueError('Replacement chain is out of order or skipped')
            for row in rejections:
                source = root/'sources'/lookup[row['episode_id']]['case_id']
                _sealed(source, protocol, evidence)
                rejection = _read(source/'rejection.json')
                if (rejection.get('episode_id') != row['episode_id'] or rejection.get('planned_slot_id') != identity
                        or rejection.get('reason') not in ('initialization_failed', 'duplicate_initial_scene')
                        or rejection.get('reason') != row.get('reason')
                        or rejection.get('budget_attempt') != row.get('budget_attempt')
                        or rejection.get('before_first_action') is not True
                        or rejection.get('outcome_not_observed') is not True
                        or rejection.get('control_steps_executed') != 0
                        or (source/'trajectory.npz').exists() or (source/'summary.json').exists()):
                    raise ValueError('Replacement was not a sealed pre-action rejection')
                rejects.append(dict(planned_slot_id=identity, **row))
            dispositions[identity] = slot
        if (status.get('missing_slot_ids') != worker_missing
                or status.get('status') != ('complete_with_missing_slots' if worker_missing else 'complete')):
            raise ValueError('Worker missing-slot status is inconsistent')
    return dict(wave_exited=True, all_300_disposed=True, loaded_workers=32,
                wave_path=str(wave), planned_slot_ids=ids,
                dispositions=[dispositions[x] for x in ids], missing_slot_ids=missing,
                pre_action_rejections=rejects, evidence=evidence)


def _ledger(config):
    path = storage.ROOT/'budget/attempts.jsonl'
    with storage.LOCK_PATH.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        raw = path.read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Ledger must end on a complete record')
    rows = [json.loads(line) for line in raw.splitlines()]
    if (any(type(row.get('number')) is not int for row in rows)
            or [row.get('number') for row in rows] != list(range(1, len(rows)+1))):
        raise ValueError('Ledger record numbers must be complete, unique and ordered')
    totals, stages, kinds, identities = Counter(), defaultdict(Counter), Counter(), Counter()
    protocol = config['analysis_approval']['protocol_sha256']
    round2_numbers, first = [], None
    for row in rows:
        amount, resource, stage = row.get('amount'), row.get('resource'), row.get('stage')
        if type(amount) is not int or amount < 1 or resource not in ('simulator_attempts', 'training_updates'):
            raise ValueError('Invalid charged ledger resource/amount')
        limits = config['budget']['stages']
        if stage not in limits:
            raise ValueError('Unregistered ledger stage')
        totals[resource] += amount; stages[stage][resource] += amount
        if row.get('protocol_sha256') == protocol or stage == STAGE:
            first = row['number'] if first is None else first
            if (row.get('protocol_sha256') != protocol or resource != 'simulator_attempts'
                    or amount != 1 or stage not in (STAGE, 'technical_reserve')
                    or row.get('kind') not in ('source_capture', 'candidate_restore', 'branch_including_restore')
                    or stage == 'technical_reserve' and row['kind'] != 'source_capture'):
                raise ValueError('Round2 ledger contains unapproved computation')
            round2_numbers.append(row['number']); kinds[stage+':'+row['kind']] += amount
            identities[(stage, row['kind'], row.get('identity'))] += 1
        elif first is not None:
            raise ValueError('Unexpected different-stage work after round2 began')
    for stage, counts in stages.items():
        if any(value > config['budget']['stages'][stage][key] for key, value in counts.items()):
            raise ValueError('Full ledger exceeds a stage budget')
    if (totals['simulator_attempts'] > 50000 or totals['training_updates'] != 19200
            or stages[STAGE]['simulator_attempts'] > 17400
            or stages['technical_reserve']['simulator_attempts'] > 1200
            or stages[STAGE]['training_updates'] != 0
            or kinds[STAGE+':source_capture'] > 300):
        raise ValueError('Global/stage budget or zero-new-optimizer contract failed')
    if not round2_numbers:
        raise ValueError('No completed round2 wave attempts in the ledger')
    return raw, rows, dict(all_attempts_charged=True, new_optimizer_updates=0,
        expected_existing_optimizer_updates=19200, records=len(rows),
        snapshot_sha256=hashlib.sha256(raw).hexdigest(), resource_totals=dict(totals),
        resources_by_stage={k:dict(v) for k,v in stages.items()}, round2_attempt_numbers=round2_numbers,
        round2_attempts_by_kind=dict(kinds),
        repeated_attempt_identities=[dict(stage=k[0],kind=k[1],identity=k[2],attempts=n)
                                    for k,n in identities.items() if n > 1],
        failures_rejections_retries_not_discounted=True)


def _analysis_sources(config, evidence):
    old = config['round2_collection']['original_collection']
    if old['config_sha256'] != BASE_CONFIG_SHA or old['freeze_sha256'] != BASE_FREEZE_SHA:
        raise ValueError('Original collection differs from the approved frozen source')
    old_path = _record_file(old['config_path'], evidence, expected=BASE_CONFIG_SHA)
    freeze_path = _record_file(old['freeze_path'], evidence, expected=BASE_FREEZE_SHA)
    previous, frozen = _read(old_path), _read(freeze_path)
    matches = [(p,h) for p,h in previous['analysis_documents'].items()
               if Path(p).name == 'NATIVE10_TRAINING_READINESS_REVIEW.md']
    if len(matches) != 1 or matches[0][1] != READINESS_SHA:
        raise ValueError('Required original sealed readiness reference is missing')
    path, digest = matches[0]
    if frozen['files'].get(str(Path(path).resolve())) != digest:
        raise ValueError('Readiness is absent from the original collection freeze')
    sources = dict(config['analysis_documents'])
    if any(Path(p).name == Path(path).name and (p != path or h != digest) for p,h in sources.items()):
        raise ValueError('Conflicting readiness source')
    sources[path] = digest
    for p,h in sources.items():
        _record_file(p, evidence, expected=h)
    return sources, dict(path=path,sha256=digest,origin_config=old,original_protocol_sha256=previous['analysis_approval']['protocol_sha256'],
                         purpose='document provenance only; not a final training release')


def _rejection_attempts(config, gate, rows, evidence):
    """Exhausted chains have no collection, so audit their attempts independently."""
    ledger = {row['number']:row for row in rows}
    cases = {row['episode_id']:row for row in config['episode_manifest']}
    numbers = []
    for rejection in gate['pre_action_rejections']:
        case = cases[rejection['episode_id']]
        saved = _read(_record_file(storage.ROOT/'sources'/case['case_id']/'attempt.json', evidence))
        number = saved.get('number')
        if (type(number) is not int or number in numbers or ledger.get(number) != saved
                or number != rejection['budget_attempt'] or saved.get('kind') != 'source_capture'
                or saved.get('stage') != ('technical_reserve' if case.get('replacement_of') else STAGE)
                or saved.get('identity') != case['case_id'] or saved.get('amount') != 1
                or saved.get('resource') != 'simulator_attempts'
                or saved.get('protocol_sha256') != config['analysis_approval']['protocol_sha256']):
            raise ValueError('Rejected initialization attempt differs from the full ledger')
        numbers.append(number)
    return numbers


def _load(config, sources):
    from .artifact_loader import load_artifact_dataset
    return load_artifact_dataset(config, BANK, purpose='train', rounds=[2],
                                 analysis_sources=sources, completed_collections_only=True)


def _save(version, audited):
    from .artifact_loader import save_audited_dataset
    return save_audited_dataset(version, audited)


def run_audit(config_path, freeze_path, wave_id, version, *, contract_path=CONTRACT):
    """Return a new sealed completion_audit and unchanged five-field dataset binding."""
    _component(version); _component(wave_id)
    contract_path = Path(contract_path).resolve()
    if storage.sha256(contract_path) != CONTRACT_SHA:
        raise ValueError('Final input audit contract differs from the authorized version')
    config_path, freeze_path = _inside(config_path), _inside(freeze_path)
    destination = storage.ROOT/'round2_dataset_reviews'/version
    if destination.exists() or (storage.ROOT/'datasets'/version).exists() or (storage.ROOT/'dataset_audits'/version).exists():
        raise FileExistsError('Audit and dataset versions must all be new')
    config = _verify_frozen(config_path, freeze_path)
    gate = _wave_gate(config, config_path, freeze_path, wave_id)
    # No source/branch outcome loader is reachable before the full 300-slot gate.
    evidence = gate.pop('evidence')
    for path in (config_path, freeze_path): _record_file(path, evidence)
    sources, readiness = _analysis_sources(config, evidence)
    raw_ledger, ledger_rows, ledger = _ledger(config)
    rejection_numbers = _rejection_attempts(config, gate, ledger_rows, evidence)
    audited = _load(config, sources)
    if audited['budget_snapshot'] != raw_ledger:
        raise ValueError('Ledger changed while auditing the completed wave')
    packed, audit = audited['packed'], audited['input_audit']
    ids = gate['planned_slot_ids']; records = packed['metadata']['records']
    if (audit['episode_ids'] != ids or [r.get('planned_slot_id',r['episode_id']) for r in records] != ids
            or packed['metadata']['planned_episode_count'] != 300
            or audit['protocol_sha256'] != config['analysis_approval']['protocol_sha256']):
        raise ValueError('Outcome loader did not preserve all original round2 slots/protocol')
    by_slot = {r['planned_slot_id']:r for r in audit['slot_resolutions']}
    for slot in gate['dispositions']:
        if by_slot[slot['planned_slot_id']]['resolved_episode_id'] != slot['resolved_episode_id']:
            raise ValueError('Loader replacement resolution disagrees with completed wave')
    referenced = set(audit['referenced_attempts'])
    stage_numbers = set(ledger['round2_attempt_numbers'])
    if not referenced <= stage_numbers:
        raise ValueError('Round2 labels reference attempts from another collection')
    ledger.update(referenced_attempt_count=len(referenced),
                  unreferenced_charged_attempt_numbers=sorted(stage_numbers-referenced),
                  sealed_pre_action_rejections=gate['pre_action_rejections'],
                  independently_verified_rejection_attempt_numbers=rejection_numbers)
    coverage = dict(planned_slot_count=300, complete_critic_groups=packed['metadata']['complete_critic_groups'],
                    status_counts=packed['metadata']['status_counts'],
                    complete_planned_selection_evidence=packed['metadata']['complete_planned_selection_evidence'],
                    unresolved_or_exhausted_slot_ids=gate['missing_slot_ids'])
    passed = audit.get('status') == 'passed' and coverage['complete_planned_selection_evidence'] and not gate['missing_slot_ids']
    # Recheck all technical bytes before producing the exclusive derived version.
    for path, digest in evidence.items(): _record_file(path, {}, expected=digest)
    destination.mkdir(parents=True, exist_ok=False)
    binding = _save(version, audited)
    contract_snapshot = destination/'NATIVE10_FINAL_INPUT_CONTRACT.md'
    with contract_snapshot.open('xb') as stream: stream.write(contract_path.read_bytes())
    if storage.sha256(contract_snapshot) != CONTRACT_SHA:
        raise ValueError('Authorized contract changed before publication')
    with (destination/'budget_snapshot.jsonl').open('xb') as stream: stream.write(raw_ledger)
    storage.dump(destination/'evidence.json', evidence)
    storage.dump(destination/'wave_gate.json', gate)
    storage.dump(destination/'analysis_sources.json', dict(sources=sources,readiness_supplement=readiness))
    collection = dict(config_path=str(config_path), config_sha256=storage.sha256(config_path),
        freeze_path=str(freeze_path), freeze_sha256=storage.sha256(freeze_path), bank_version=BANK,
        protocol_sha256=config['analysis_approval']['protocol_sha256'])
    result = dict(schema=SCHEMA,status='passed' if passed else 'incomplete', dataset_binding=binding,
        collection=collection, wave_gate=gate, ledger=ledger, coverage=coverage,
        generation_critic=dict(member_hashes=config['main_collection']['banks'][BANK]['critic_member_hashes'],
            assets=config['critic_assets'], **config['round2_collection']['selected_training']),
        analysis_sources=sources, readiness_supplement=readiness,
        scene_registry_before=config['round2_preparation']['scene_registry_before'],
        contract=dict(path=str(contract_snapshot.resolve()),sha256=CONTRACT_SHA,original_path=str(contract_path)),
        code_sha256={str(Path(__file__).resolve()):storage.sha256(__file__)},
        model_calls=0, simulator_calls=0, optimizer_updates=0, pca_fits=0,
        final_training_released=False, old_artifacts_modified=False)
    storage.dump(destination/'result.json', result)
    storage.seal(destination, role=SCHEMA, audit_status=result['status'], optimizer_updates=0)
    completion = dict(path=str(destination.resolve()),seal_sha256=storage.sha256(destination/'complete.json'),
                      result_sha256=storage.sha256(destination/'result.json'))
    return dict(status=result['status'],path=completion['path'],seal_sha256=completion['seal_sha256'],
                completion_audit=completion,dataset_binding=binding,**coverage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--wave-id', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--contract', type=Path, default=CONTRACT)
    args = parser.parse_args()
    print(json.dumps(run_audit(args.config,args.freeze,args.wave_id,args.version,contract_path=args.contract)))


if __name__ == '__main__':
    main()
