"""Full-wave, read-only calibration artifact audit and unsealed choice proposal.

No model, simulator, optimizer or new episode is constructed. The complete wave
gate precedes all source/branch outcome reads. Technical missingness raises; it
never becomes a false label. The audit seal is not a deployment-selection seal.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from . import artifact_loader as loader, storage
from .calibration_statistics_v1 import (METHODS, REGISTERED_PRIMARY_IDS,
    REGISTERED_PRIMARY_IDS_SHA256, summarize_calibration)
from .policy5_audit_v1 import audit_suffix_identities
from .protocol import canonical_hash, validate_manifest

STAGE, BANK = 'calibration', 'calibration_policy_v1'
ROLE = 'native10_calibration_readonly_audit'


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def _file(path, artifacts, role, expected=None):
    path = loader._safe(path); digest = storage.sha256(path)
    require(expected is None or digest == expected, 'Artifact SHA differs: '+str(path))
    if str(path) in artifacts:
        require(artifacts[str(path)]['sha256'] == digest, 'Artifact changed during audit')
    artifacts[str(path)] = dict(path=str(path), sha256=digest, role=role)
    return path


def _loaded(record, config):
    selected = Path(config['critic_assets']).resolve()
    hashes = config['main_collection']['banks'][BANK]['critic_member_hashes']
    trained = config['calibration_collection']['selected_training']
    expected = dict(status='passed', stage=STAGE, selected_assets=str(selected), selected_path=str(selected),
        selected_seal_sha256=trained['selected_seal_sha256'],
        selected_reload_audit_sha256=trained['selected_reload_audit_sha256'],
        model_paths=[str(selected/f'models/refit/member_{i}/selected.pt') for i in range(4)],
        member_hashes=hashes, model_hashes=hashes, selection=dict(path='A', step=4000),
        optimizer_updates=0, actual_selector_paths=True, checkpoint_file_sha=True,
        frozen_parameter_buffer_versions=True, eval_cpu_no_parameter_grad=True)
    require(set(hashes) == {'0', '1', '2', '3'} and all(record.get(k) == v for k, v in expected.items()),
            'Worker lacks actual loaded final A4000 identity evidence')


def _wave_gate(config, config_path, freeze_path, wave_path, artifacts):
    """Read completion/disposition metadata only, never source/branch outcomes."""
    wave = loader._safe(wave_path)
    require(wave.parent == (storage.ROOT/'calibration_execution'/STAGE/BANK).resolve(),
            'Wave must belong to the isolated calibration runner')
    launch_path = wave/'launch_result.json'
    require(launch_path.is_file(), 'Wait for the full lifecycle launch result before outcomes')
    launch = read(_file(launch_path, artifacts, 'wave'))
    require(launch.get('status') == 'complete' and type(launch.get('returncode')) is int
            and launch['returncode'] == 0 and launch.get('lifecycle_covers_entire_wave') is True
            and launch.get('hold_idle') is False and launch.get('next_stage_automatically_started') is False,
            'Successful full-wave lifecycle exit is required before outcomes')
    spec_path = _file(wave/'wave_spec.json', artifacts, 'wave'); spec = read(spec_path)
    expected = dict(config_sha256=storage.sha256(config_path), freeze_sha256=storage.sha256(freeze_path),
        stage=STAGE, bank_version=BANK, workers=32, hold_idle=False, original_primary_slots=100,
        paired_suffixes_per_state=2, primary_capture_limit=100, hard_attempt_limit=1200,
        global_choice_applied_during_collection=False, selection_automatically_started=False,
        physical_arms=list(METHODS), guard_factory='create_calibration_collector')
    require(all(spec.get(k) == v for k, v in expected.items()), 'Wave specification identity differs')
    command = launch.get('command', [])
    require(isinstance(command, list) and '--spec' in command
            and command[command.index('--spec')+1:] == [str(spec_path)], 'Launch result points to another wave')
    ids = config['main_collection']['banks'][BANK]['episode_ids']
    require(ids == list(REGISTERED_PRIMARY_IDS), 'Wave requires the original 100 calibration primaries')
    workers = wave/'workers'
    require(workers.is_dir() and {p.name for p in workers.iterdir() if p.is_dir()} ==
            {f'worker_{rank:02d}' for rank in range(32)}, 'All 32 workers must have final artifacts')
    # Require all seals before parsing any worker/slot detail.
    require(all((workers/f'worker_{rank:02d}/complete.json').is_file() for rank in range(32)),
            'Wait for every worker complete seal before outcomes')
    protocol = config['analysis_approval']['protocol_sha256']; slots = {}
    for rank in range(32):
        folder = workers/f'worker_{rank:02d}'
        sealed = loader._sealed(folder, [protocol], 'worker', artifacts)
        require(sealed.get('role') == 'guarded_calibration_worker' and not (folder/'failure.json').exists(),
                'Failed or wrong-role worker cannot complete calibration audit')
        status = read(folder/'status.json'); assigned = ids[rank::32]
        wanted = dict(status='complete', stage=STAGE, bank_version=BANK, wave_id=wave.name, rank=rank,
            workers=32, config_sha256=expected['config_sha256'], freeze_sha256=expected['freeze_sha256'],
            protocol_sha256=protocol, assigned_slot_ids=assigned, completed_slot_records=len(assigned),
            missing_slot_ids=[], primary_capture_allowed=True, global_choice_applied_during_collection=False,
            next_stage_automatically_started=False, guard_factory='create_calibration_collector',
            slot_entry='collect_calibration_slot')
        require(all(status.get(k) == v for k, v in wanted.items()),
                'Worker incomplete, missing technical slots, or frozen assignment differs')
        _loaded(read(folder/'loaded_model_identity.json'), config)
        require({p.stem for p in (folder/'slots').glob('*.json')} == set(assigned), 'Worker slot inventory differs')
        for identity in assigned:
            slot = read(folder/'slots'/f'{identity}.json'); actual = slot.get('resolved_episode_id')
            chain = [identity]+config['main_collection']['replacement_candidates'][identity]
            require(slot.get('status') == 'complete' and slot.get('planned_slot_id') == identity
                    and actual in chain and identity not in slots,
                    'All 100 logical slots require completed approved resolutions')
            require([r.get('episode_id') for r in slot.get('ordered_rejections', [])] == chain[:chain.index(actual)],
                    'Worker skipped or reordered a replacement predecessor')
            collection = storage.ROOT/'collections'/STAGE/BANK/actual
            resolution = storage.ROOT/'slot_resolution'/identity
            require(Path(slot.get('completion_path', '')).resolve() == collection.resolve()
                    and Path(slot.get('resolution_path', '')).resolve() == resolution.resolve()
                    and (collection/'complete.json').is_file() and (resolution/'complete.json').is_file(),
                    'Every source needs its original resolved collection and resolution seal')
            _file(collection/'complete.json', artifacts, 'collection', slot['completion_sha256'])
            slots[identity] = slot
    require(set(slots) == set(ids) and len({x['resolved_episode_id'] for x in slots.values()}) == 100,
            'Incomplete or repeated physical source resolutions')
    return dict(status='passed', wave_path=str(wave), loaded_workers=32, all_100_slots_complete=True,
                lifecycle_returncode=0, slots=[slots[identity] for identity in ids])


def _ledger_closure(config, ledger, used_attempts, *, cut_sources, replacement_captures):
    """Close accepted/rejected captures plus every bank/branch to actual charges."""
    protocol = config['analysis_approval']['protocol_sha256']
    require(type(cut_sources) is int and 0 <= cut_sources <= 100
            and type(replacement_captures) is int and 0 <= replacement_captures <= 200,
            'Calibration capture/cut counts exceed the registered slots and backup chains')
    require(list(ledger) == list(range(1, len(ledger)+1)), 'Global ledger numbers must be contiguous and unique')
    totals, stages, stage_kinds = Counter(), defaultdict(Counter), Counter()
    charged, seen = [], set()
    for row in ledger.values():
        resource, amount, stage = row.get('resource'), row.get('amount'), row.get('stage')
        require(resource in ('simulator_attempts', 'training_updates') and type(amount) is int and amount > 0
                and stage in config['budget']['stages'], 'Invalid global ledger resource/stage')
        totals[resource] += amount; stages[stage][resource] += amount
        if row.get('protocol_sha256') == protocol or stage == STAGE:
            require(row.get('protocol_sha256') == protocol and resource == 'simulator_attempts' and amount == 1
                    and stage in (STAGE, 'technical_reserve')
                    and row.get('kind') in ('source_capture', 'candidate_restore', 'branch_including_restore')
                    and (stage != 'technical_reserve' or row['kind'] == 'source_capture'),
                    'Calibration contains an unapproved stage, optimizer update, or reservation')
            key = (stage, row['kind'], row['identity'])
            require(key not in seen, 'Unapproved duplicate/retry calibration identity')
            seen.add(key); charged.append(row['number']); stage_kinds[stage+':'+row['kind']] += 1
    require(len(used_attempts) == len(set(used_attempts)) and set(used_attempts) == set(charged),
            'Unaccounted, duplicate, failed or extra calibration attempts prevent complete audit')
    expected = Counter({STAGE+':source_capture': 100})
    if cut_sources:
        expected[STAGE+':candidate_restore'] = cut_sources
        expected[STAGE+':branch_including_restore'] = cut_sources*10
    if replacement_captures:
        expected['technical_reserve:source_capture'] = replacement_captures
    require(stage_kinds == expected, 'Calibration 100 primary / backup / cut-bank / 5x2 branch accounting differs')
    require(totals['simulator_attempts'] <= 50000 and totals['training_updates'] == 51200,
            'Global simulator limit or exhausted optimization budget differs')
    for stage, counts in stages.items():
        require(all(value <= config['budget']['stages'][stage][resource] for resource, value in counts.items()),
                'Global ledger exceeds the frozen stage budget')
    return dict(status='passed', new_attempts=len(charged), attempt_numbers=charged,
        resource_totals=dict(totals), attempts_by_stage_kind=dict(stage_kinds),
        primary_capture_attempts=100, backup_capture_attempts=replacement_captures,
        bank_restore_attempts=cut_sources, physical_branch_attempts=cut_sources*10,
        calibration_stage_attempts=100+cut_sources*11, new_optimizer_updates=0,
        all_attempts_charged=True, failed_or_unresolved_attempts=0)


def _resolution(primary, case, slot, rejected, source_sha, protocol, artifacts):
    folder = storage.ROOT/'slot_resolution'/primary['episode_id']
    loader._sealed(folder, [protocol], 'resolution', artifacts); row = read(folder/'resolution.json')
    required = dict(status='resolved', planned_slot_id=primary['episode_id'], resolved_episode_id=case['episode_id'],
        task=primary['task'], split='calibration', round=None, original_env_seed=primary['env_seed'],
        resolved_env_seed=case['env_seed'], source_protocol_sha256=protocol, source_seal_sha256=source_sha,
        substitution_after_outcome_forbidden=True, ordered_rejections=slot['ordered_rejections'])
    require(all(row.get(k) == v for k, v in required.items()), 'Resolution differs from audited actual source')
    slim = lambda rows: [{k: r[k] for k in ('episode_id', 'reason', 'budget_attempt')} for r in rows]
    require(slim(rejected) == slim(row['ordered_rejections'])
            and all(r.get('before_first_action') is True for r in row['ordered_rejections']),
            'Sealed pre-action predecessor evidence differs from resolution')
    return row


def _labels(config, gate, ledger, scenes, artifacts):
    from .calibration_collection_v1 import verify_calibration_bank
    registration = config['main_collection']['banks'][BANK]
    registry = validate_manifest(config['episode_manifest']); protocol = config['analysis_approval']['protocol_sha256']
    records, used, sources, suffix_count, cut_count = [], [], set(), 0, 0
    for slot in gate['slots']:
        identity = slot['planned_slot_id']; primary = registry[identity]
        case, source, rejected, rejected_attempts = loader._resolve(
            primary, registration, config, registry, ledger, artifacts, scenes)
        require(case is not None and case['episode_id'] == slot['resolved_episode_id'],
                'Resolution is exhausted, missing, or differs from the completed worker')
        used.extend(rejected_attempts)
        summary, data, contexts, queues, attempt = loader._source(
            case, source, registration, config, ledger, artifacts, scenes)
        used.append(attempt); source_sha = storage.sha256(source/'complete.json')
        resolution = _resolution(primary, case, slot, rejected, source_sha, protocol, artifacts)
        require(summary.get('source_capture_stage') == ('technical_reserve' if case.get('replacement_of') else STAGE)
                and summary.get('planned_slot_id') == identity and summary.get('source_horizon') == 10
                and summary.get('control_budget') == 300 and summary.get('protocol_sha256') == protocol,
                'New calibration source capture provenance differs')
        scene = (case['task'], summary['scene_fingerprint'])
        require(scene not in sources and resolution.get('scene_fingerprint') == scene[1]
                and resolution.get('exact_state_sha256') == summary['exact_state_sha256'],
                'Repeated or inconsistent physical source scene')
        sources.add(scene)
        collection = storage.ROOT/'collections'/STAGE/BANK/case['case_id']
        loader._sealed(collection, [protocol], 'collection', artifacts); complete = read(collection/'summary.json')
        provenance = dict(episode_id=case['episode_id'], case_id=case['case_id'], task=case['task'],
            env_seed=case['env_seed'], split='calibration', round=None, generation_round=2,
            generation_phase='calibration', planned_slot_id=identity, bank_version=BANK, bank_kind='policy5',
            stage=STAGE, source_protocol_sha256=protocol, source_seal_sha256=source_sha,
            model_hashes=registration['model_hashes'], protocol_sha256=protocol,
            critic_member_hashes=registration['critic_member_hashes'],
            generation_critic_sha256=canonical_hash(registration['critic_member_hashes']),
            suffix_seed_namespace=config['seed_namespace'], suffix_protocol='native10_first_ten_raw_commands_v1')
        require(all(complete.get(k) == v for k, v in provenance.items()) and complete.get('status') == 'complete'
                and complete.get('case') == case and complete.get('methods') == list(METHODS)
                and complete.get('replicates') == 2 and complete.get('logical_branch_count') == 10
                and complete.get('cuts') == summary['cuts'] and complete.get('no_cut') == (not summary['cuts'])
                and complete.get('planned_episode_retained') is True and complete.get('outcome_filter_applied') is False
                and complete.get('actual_branch_count') == slot.get('actual_branch_count')
                and complete.get('no_cut') == slot.get('no_cut'), 'Calibration collection identity/count differs')
        outcomes = np.empty((5, 2), bool); cut = None
        if summary['cuts']:
            cut_count += 1; cut, = summary['cuts']
            require(cut == summary.get('first_legal_alarm_step') and summary.get('selection_reason') == 'first_legal_alarm'
                    and summary['selection_audit']['training_fallback_allowed'] is False,
                    'Calibration cut is not the original first eligible alarm')
            bank = storage.ROOT/'banks'/BANK/case['case_id']/f'cut{cut:03d}'
            loader._sealed(bank, [protocol], 'bank', artifacts)
            bank_check = verify_calibration_bank(bank, case, source, config)
            guard = storage.ROOT/'calibration_guard'/STAGE/BANK/case['case_id']
            seal = loader._sealed(guard, [protocol], 'same_bank_guard', artifacts)
            require(seal.get('role') == 'calibration_same_bank_check'
                    and read(guard/'bank_check.json') == bank_check, 'Recorded pre-branch bank guard differs')
            generation = read(bank/'generation.json'); plans = loader._npz(bank/'plans.npz')
            bank_sha = storage.sha256(bank/'complete.json')
            require(complete.get('candidate_bank_sha256') == bank_sha
                    and all(generation.get(k) == v for k, v in provenance.items()), 'Bank provenance differs')
            used.append(loader._attempt(bank, generation, ledger, kind='candidate_restore', stage=STAGE,
                protocol=protocol, identity=str(bank.relative_to(storage.ROOT))))
            branch_rows = complete.get('branch_records', [])
            saved = {(row['method'], row['repeat']): row for row in branch_rows}
            require(len(branch_rows) == len(saved) == complete['actual_branch_count'] == 10
                    and set(saved) == {(method, repeat) for method in METHODS for repeat in range(2)},
                    'Cut lacks all five arms and two distinct paired repeats')
            noise = {}
            for arm, method in enumerate(METHODS):
                for repeat in range(2):
                    branch = storage.ROOT/'rollouts'/STAGE/BANK/case['case_id']/f'cut{cut:03d}'/method/f'repeat_{repeat}'
                    loader._sealed(branch, [protocol], 'branch', artifacts); row = read(branch/'summary.json')
                    ref = saved[(method, repeat)]
                    expected = dict(provenance, candidate_bank_sha256=bank_sha, status='complete', cut_step=cut,
                        method=method, candidate_name=method, repeat=repeat,
                        paired_suffix_id=f"{case['episode_id']}:cut{cut}:repeat{repeat}", source_horizon=10,
                        suffix_horizon=10, generated_horizon=50, normalized_queue_injection=False,
                        restore_included_in_attempt=True, physical_outcome_reused=False,
                        execution_role='continue_native10' if arm == 0 else 'alarm_replan10')
                    require(all(row.get(k) == v for k, v in expected.items()) and type(row.get('success')) is bool
                            and ref.get('seal_sha256') == storage.sha256(branch/'complete.json')
                            and Path(ref.get('summary_path', '')).resolve() == (branch/'summary.json').resolve()
                            and all(ref.get(k) == row.get(k) for k in ('success', 'budget_attempt', 'command_sha256')),
                            'Branch model/source/raw-command/paired identity differs')
                    used.append(loader._attempt(branch, row, ledger, kind='branch_including_restore', stage=STAGE,
                        protocol=protocol, identity=str(branch.relative_to(storage.ROOT))))
                    loader._branch_trajectory(row, branch, data, queues[cut], None if arm == 0 else plans[method])
                    audit_suffix_identities(row['suffix_seeds'], case, cut, repeat, config['seed_namespace'], noise)
                    suffix_count += len(row['suffix_seeds']); outcomes[arm, repeat] = row['success']
        else:
            require(summary.get('no_alarm') is True and summary.get('full_episode_outcome_available') is True
                    and type(summary.get('success')) is bool and summary.get('first_legal_alarm_step') is None
                    and summary.get('actual_cut') is None and complete.get('actual_branch_count') == 0
                    and complete.get('branch_records') == [] and complete.get('candidate_bank_sha256') is None
                    and complete.get('common_outcome_available') is True
                    and complete.get('common_outcome') == summary['success'], 'No-alarm common outcome is incomplete')
            outcomes[:] = summary['success']
        # These passed declarations are emitted only after all artifacts above pass.
        records.append(dict(planned_slot_id=identity, resolved_episode_id=case['episode_id'], task=case['task'],
            scene_fingerprint=scene[1], status='complete', artifact_audit_status='passed', scene_isolation_status='passed',
            no_cut=cut is None, actual_cut=cut, common_outcome=summary['success'] if cut is None else None,
            outcomes={method: outcomes[index].tolist() for index, method in enumerate(METHODS)}, resolution=resolution,
            source_path=str(source), source_seal_sha256=source_sha, collection_path=str(collection),
            collection_seal_sha256=storage.sha256(collection/'complete.json')))
    replacement_captures = sum(ledger[number]['stage'] == 'technical_reserve' for number in used)
    return records, used, cut_count, replacement_captures, suffix_count


def run_audit(config_path, freeze_path, wave_path, *, version, bank_version=BANK):
    require(bank_version == BANK and isinstance(version, str)
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', version), 'Explicit safe calibration audit version required')
    output = storage.ROOT/'calibration_audits'/version
    require(not output.exists(), 'Audit output must be new')
    from .calibration_runner_v1 import verify_frozen
    config_path, freeze_path = Path(config_path).resolve(), Path(freeze_path).resolve()
    config = verify_frozen(config_path, freeze_path, STAGE, BANK, 32)
    artifacts = {}
    _file(config_path, artifacts, 'config'); _file(freeze_path, artifacts, 'freeze')
    gate = _wave_gate(config, config_path, freeze_path, wave_path, artifacts)
    raw_ledger, ledger = loader._ledger_snapshot(); raw_scenes, scenes = loader._scene_registry_snapshot()
    records, attempts, cuts, replacements, suffixes = _labels(config, gate, ledger, scenes, artifacts)
    budget = _ledger_closure(config, ledger, attempts, cut_sources=cuts, replacement_captures=replacements)
    statistics = summarize_calibration(config['episode_manifest'], list(REGISTERED_PRIMARY_IDS), records,
        expected_primary_ids_sha256=REGISTERED_PRIMARY_IDS_SHA256,
        replacement_candidates=config['main_collection']['replacement_candidates'])
    result = dict(status='passed', role=ROLE, schema='native10_calibration_full_static_audit_v1', stage=STAGE,
        bank_version=BANK, config_sha256=storage.sha256(config_path), freeze_sha256=storage.sha256(freeze_path),
        config_content_sha256=canonical_hash(config), protocol_sha256=config['analysis_approval']['protocol_sha256'],
        selected_training=config['calibration_collection']['selected_training'], planned_slots=100,
        technical_missing=0, reached_sources=cuts, no_cut_sources=100-cuts, physical_branches=cuts*10,
        logical_outcomes_per_arm=200, original_primary_ids_sha256=REGISTERED_PRIMARY_IDS_SHA256,
        statistics=statistics, selection_proposal=statistics['selection_proposal'], per_source=records,
        **{key: value for key, value in budget.items() if key != 'status'}, suffix_seed_records_checked=suffixes,
        artifacts=list(artifacts.values()), wave_gate={k: v for k, v in gate.items() if k != 'slots'},
        ledger_snapshot_sha256=hashlib.sha256(raw_ledger).hexdigest(),
        scene_registry_snapshot_sha256=hashlib.sha256(raw_scenes).hexdigest(),
        code_sha256={str(Path(__file__).resolve()): storage.sha256(__file__)},
        model_calls=0, simulator_calls=0, optimizer_updates=0, heldout_reads=0, heldout_mutations=0,
        selection_seal_created=False, selection_release_authorized=False,
        limitations=['Statistics follow verified completion; only an unsealed global choice proposal is returned.',
            'Artifact/trajectory/scene/suffix checks reuse the previously audited read-only helpers.',
            'Two repeats per source do not support per-source uncertainty; calibration is not heldout validation.'])
    output.mkdir(parents=True, exist_ok=False)
    (output/'budget_snapshot.jsonl').write_bytes(raw_ledger)
    (output/'scene_registry_snapshot.jsonl').write_bytes(raw_scenes)
    storage.dump(output/'source_records.json', records)
    storage.dump(output/'wave_completion.json', gate)
    storage.dump(output/'result.json', result)
    storage.seal(output, role=ROLE, model_calls=0, simulator_calls=0, optimizer_updates=0,
                 selection_seal_created=False, heldout_release=False)
    return dict(status='passed', path=str(output), seal_sha256=storage.sha256(output/'complete.json'),
                result_sha256=storage.sha256(output/'result.json'), selection_proposal=result['selection_proposal'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--wave', type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    print(json.dumps(run_audit(args.config, args.freeze, args.wave, version=args.version), indent=2))
