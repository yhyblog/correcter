"""Read-only paired implementation audits; outcomes require a full-wave gate.

Preflight audits technical identity without aggregating solo success. Formal
statistics may run once all 100 source dispositions and the whole wave complete.
Old and new artifacts keep separate protocol identities and ledgers.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.native10_training_20260916 import artifact_loader as old_loader
from experiments.native10_training_20260916 import storage as old_storage
from experiments.native10_training_20260916.policy5_audit_v1 import audit_suffix_identities
from experiments.native10_training_20260916.protocol import candidate_seed, canonical_hash, validate_manifest
from .statistics import METHODS, OLD_METHODS, SOLO_METHODS, REGISTERED_PRIMARY_IDS, NO_CUT_IDS, summarize
from .candidates import audit_solo, bit_equal, array_sha
from . import storage, protocol

ROOT = Path(__file__).resolve().parents[2]/'outputs/standalone_ablation_20260918'
OLD_ROOT = old_storage.ROOT
ROLE = 'standalone_ablation_full_static_audit_v1'
PREFLIGHT_ROLE = 'standalone_preflight_audit'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def file_ref(path, artifacts, *, expected=None, role='input'):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT.resolve()) or path.is_relative_to(OLD_ROOT.resolve()),
            'Audited artifacts must remain in their explicit old/new roots')
    digest = old_storage.sha256(path)
    require(expected is None or digest == expected, 'Bound artifact SHA changed: '+str(path))
    if str(path) in artifacts:
        require(artifacts[str(path)]['sha256'] == digest, 'Artifact changed during audit')
    artifacts[str(path)] = dict(path=str(path), sha256=digest, role=role)
    return path


def sealed(path, protocol, artifacts, *, expected=None, role='input'):
    path = Path(path).resolve()
    complete = read(file_ref(path/'complete.json', artifacts, expected=expected, role=role))
    require(complete.get('status') == 'complete' and complete.get('protocol_sha256') == protocol,
            'Old/new artifact protocol must match its actual original seal')
    actual = {str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p != path/'complete.json'}
    require(set(complete.get('files', {})) == actual, 'Sealed file inventory changed')
    for name, digest in complete['files'].items():
        target = (path/name).resolve()
        require(target.is_relative_to(path), 'Sealed artifact path escapes its directory')
        file_ref(target, artifacts, expected=digest, role=role)
    return complete


def arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name].copy() for name in archive.files}


def context_sha(observed):
    digest = hashlib.sha256()
    for name in sorted(observed):
        value = np.ascontiguousarray(observed[name])
        digest.update(name.encode()); digest.update(str(value.dtype).encode())
        digest.update(str(value.shape).encode()); digest.update(value.tobytes())
    return digest.hexdigest()


def compare_arrays(expected, actual, *, label):
    require(set(expected) == set(actual), label+' array key inventory differs')
    for key in expected:
        require(bit_equal(expected[key], actual[key]), label+' dtype/shape/bytes differ: '+key)
    return dict(status='passed', arrays=len(expected), byte_exact=True)


def compare_reference(old_plans, old_formal, reference_plans, reference_formal):
    """Already-seal-checked NPZ dictionaries, without outcome/statistic inputs."""
    plan_map = dict(alarm_replan10='replan', velocity='velocity_matched',
                    direct='direct_matched', post='post_matched')
    require(set(old_plans) == set(plan_map), 'Old policy bank must contain its four actual plans')
    for old_name, new_name in plan_map.items():
        key = old_name if old_name in reference_plans else new_name
        require(key in reference_plans and bit_equal(old_plans[old_name], reference_plans[key]),
                'Reference no longer reproduces old raw plan: '+old_name)
    require(set(old_formal) <= set(reference_formal), 'Reference omits old formal direction arrays')
    compare_arrays(old_formal, {k: reference_formal[k] for k in old_formal}, label='old fullbank formal')
    return dict(status='passed', old_four_plan_bytes_exact=True, old_fullbank_formal_bytes_exact=True,
        native_velocity_direct_historically_saved=False,
        native_velocity_direct_reference='newly captured from the independently reproduced full implementation')


def audit_method(method, saved, metadata, old_formal, old_generation, observed, case, cut,
                 config, *, reference_native=None):
    """Audit one independent entry; another direction is never a generator input."""
    require(method in SOLO_METHODS and metadata.get('schema') == 'standalone_generation_v1'
            and metadata.get('status') == 'complete' and metadata.get('method') == method,
            'Wrong standalone method identity')
    calls = 1 if method == 'solo_post' else 2
    mode = method.removeprefix('solo_')
    seed = candidate_seed(case, cut, namespace=config['seed_namespace'])
    common = dict(base_seed=seed, actual_policy_calls=calls, expected_policy_calls=calls,
        native_direction=mode, other_direction_calls=0, random_calls=0, joint_bank_calls=0,
        cached_a0_used=False, context_sha256=context_sha(observed),
        raw_a0_sha256=array_sha(saved['raw_a0']), same_noise=True, a0_slot=0,
        saved_before_any_branch=True, environment_unchanged=True, includes_own_a0_generation=True,
        restore_included=False, model_loading_included=False, new_acceptance_or_selection_rule=False)
    require(all(metadata.get(k) == v for k, v in common.items()),
            'Standalone entry uses wrong anchor/context/calls/independence semantics')
    require(bit_equal(saved['raw_a0'], old_formal['raw_a0'])
            and bit_equal(saved['critic_a0'], old_formal['critic_a0'])
            and bit_equal(saved['mask'], old_formal['mask']), 'Old source a0/critic proxy/mask bytes changed')
    old_noise = old_generation['base_generation']['noise_sha256']
    require(isinstance(old_noise, str) and len(old_noise) == 64
            and metadata.get('noise_sha256') == old_noise
            and metadata['base_generation'].get('noise_sha256') == old_noise
            and old_generation['base_seed'] == seed, 'Old designated-a0 seed/actual noise differs')
    proposals = metadata.get('proposal_records', [])
    require(len(proposals) == calls and [p.get('purpose') for p in proposals] ==
            (['base'] if calls == 1 else ['base', mode]), 'Independent proposal sequence differs')
    for index, proposal in enumerate(proposals):
        stats = proposal.get('stats', {})
        require(proposal.get('seed') == seed and proposal.get('mode') == (None if index == 0 else mode)
                and stats.get('policy_calls') == 1 and stats.get('fallback') is None
                and stats.get('noise_sha256') == old_noise,
                'Extra/fallback/other-method sampler call prevents paired acceptance')
    if method == 'solo_post':
        for key in ('post_command_gradient', 'post_internal_metric_direction'):
            require(bit_equal(saved[key], old_formal[key]), 'Original post gradient/metric direction differs')
        require(bit_equal(saved['raw_direction'], saved['post_internal_metric_direction'])
                and metadata['post_gradient']['value'] == 0, 'Post direction is not the fixed-a0 S squared gradient')
    else:
        clipped = np.clip(saved['own_native_raw'], -1, 1).astype(np.float32)
        require(bit_equal(saved['own_native_clipped'], clipped)
                and bit_equal(saved['raw_direction'], clipped[:10].astype(float)-saved['critic_a0'][:10].astype(float)),
                'V/D direction must come from its own clipped guided raw sample')
        updates = metadata['own_generation'].get('updates', [])
        require(len(updates) == len(config['guidance']['times'])
                and np.allclose([u['tau'] for u in updates], config['guidance']['times'], atol=1e-6, rtol=0)
                and all(u.get('mode') == mode and u.get('alpha') == 10
                        and u.get('objective_semantics') == 'maximize_mean_member_relative_success_probability'
                        and u.get('direct_gradient_outside_mask') == 0 for u in updates),
                'Original guided flow definition changed')
        if reference_native is not None:
            require(bit_equal(saved['own_native_raw'], reference_native[mode+'_native_raw'])
                    and bit_equal(saved['own_native_clipped'], reference_native[mode+'_native_clipped']),
                    'Solo native V/D differs from independently captured reference')
    proof = audit_solo(saved['raw_a0'], saved['raw_plan'], saved['raw_direction'], config['matching'])
    require(metadata['predictions']['replan']['mean_gain'] == 0, 'Critic slot-zero anchor moved')
    for group in ('xyz', 'gripper'):
        old_radius = old_generation['matching']['groups'][group]['achieved_target']
        require(proof['groups'][group]['achieved_target']+config['matching']['tolerance'] >= old_radius,
                'Own-direction radius fell below old common radius')
    return dict(status='passed', method=method, fixed_source_a0_noise_context=True,
        original_post_direction_checked=method == 'solo_post',
        captured_native_reference_checked=reference_native is not None and method != 'solo_post',
        own_projection=proof, actual_policy_calls=calls,
        no_other_direction_or_cache_calls=True, new_outcome_not_used=True)


def compare_replay(old_summary, new_summary, old_trajectory, new_trajectory):
    """Same old actions replayed: exact discrete data, original physics tolerances."""
    fields = ('method', 'repeat', 'cut_step', 'success', 'terminal_step', 'requested_prefix_steps',
        'actual_prefix_steps', 'first_expected_resample', 'first_actual_resample', 'suffix_seeds',
        'command_sha256', 'clipped_command_proxy_sha256', 'paired_suffix_id', 'original_queue_remaining',
        'endpoint_image_sha256')
    require(all(old_summary.get(k) == new_summary.get(k) for k in fields),
            'Reference replay outcome/seed/command/execution identity differs')
    require(set(old_trajectory) == set(new_trajectory), 'Reference replay trajectory schema differs')
    for name, value in old_trajectory.items():
        other = new_trajectory[name]
        require(value.shape == other.shape and value.dtype == other.dtype, 'Replay shape/dtype differs: '+name)
        if name in ('physics_states', 'rewards'):
            tolerance = 1e-10 if name == 'physics_states' else 1e-8
            require(np.allclose(value, other, atol=tolerance, rtol=0), 'Replay physics/rewards differs')
        else:
            require(bit_equal(value, other), 'Replay discrete/actions/plans bytes differ: '+name)
    return dict(status='passed', full_replay_checked=True, outcome_exact=True,
        actions_plans_seeds_flags_exact=True, physics_atol=1e-10, rewards_atol=1e-8)


def ledger_closure(config, ledger_rows, used_attempts, *, stage, expected_counts):
    """New ledger only; carry-in remains an immutable old-ledger binding."""
    numbers = [r['number'] for r in ledger_rows]
    require(numbers == list(range(1, len(numbers)+1)), 'New ledger IDs must be contiguous and unique')
    protocol_hash = config['analysis_approval']['protocol_sha256']
    charged, kinds, stages, identities = [], Counter(), Counter(), set()
    for row in ledger_rows:
        require(row.get('resource') == 'simulator_attempts' and type(row.get('amount')) is int and row['amount'] == 1
            and row.get('stage') in protocol.CAPS and row.get('kind') in ('candidate_restore', 'branch_including_restore')
            and row.get('optimizer_updates') == 0 and row.get('carry_in_ledger_sha256') == config['carry_in']['ledger']['sha256']
            and row.get('cumulative_simulator_attempts') == 48183+row['number'],
                'Standalone ledger forbids optimizer updates and batched reservations')
        require(row['identity'] not in identities, 'Unregistered repeated attempt identity')
        identities.add(row['identity']); stages[row['stage']] += 1
        if row['stage'] == stage:
            require(row.get('protocol_sha256') == protocol_hash and row.get('kind') in
                    ('candidate_restore', 'branch_including_restore'), 'Unexpected stage or forbidden capture kind')
            charged.append(row['number']); kinds[row['kind']] += 1
    require(len(used_attempts) == len(set(used_attempts)) and set(used_attempts) == set(charged)
            and kinds == Counter(expected_counts), 'Missing/duplicate/extra attempts block complete audit')
    require(len(ledger_rows) <= 1500 and 48183+len(ledger_rows) <= 50000,
            'New plus immutable carry-in exceeds the approved global budget')
    require(all(n <= protocol.CAPS[s] for s,n in stages.items()), 'Supplementary stage cap exceeded')
    return dict(status='passed', new_stage_attempts=len(charged), attempt_numbers=charged,
        counts_by_kind=dict(kinds), new_workflow_attempts=len(ledger_rows), carry_in_simulator_attempts=48183,
        cross_ledger_simulator_attempts=48183+len(ledger_rows), optimizer_updates=0,
        carry_in_optimizer_updates=51200, all_attempts_charged=True)


def _loaded(record, config, old_config, stage):
    selected = Path(config['critic_assets']).resolve()
    members = old_config['main_collection']['banks']['heldout_policy_v1']['critic_member_hashes']
    expected = dict(status='passed', stage=stage, selected_assets=str(selected),
        model_paths=[str(selected/f'models/refit/member_{i}/selected.pt') for i in range(4)],
        member_hashes=members, selection=dict(path='A', step=4000), optimizer_updates=0,
        actual_selector_paths=True, checkpoint_file_sha=True, frozen_parameter_buffer_versions=True,
        eval_cpu_no_parameter_grad=True, generation_only=True)
    require(all(record.get(k) == v for k, v in expected.items()), 'Worker did not load fixed actual A4000')
    return canonical_hash(record)


def audit_device_slots(config, cp, fp, wave, stage, spec):
    """Bind all device slots before any worker or source outcome is inspected."""
    require(stage in (protocol.PREFLIGHT, protocol.FORMAL), 'Unregistered wave stage')
    plan = config['execution_plans'][stage]
    count, real_gpus, copies = (5, 5, 1) if stage == protocol.PREFLIGHT else (32, 8, 4)
    require(plan['workers'] == count and spec.get('physical_gpu_slots') == 8
        and spec.get('real_gpu_slots') == real_gpus and spec.get('empty_gpu_slots') == 8-real_gpus
        and spec.get('whole_wave_reserves_all_eight_gpus') is True,
        'Real workers and empty GPU scheduling slots differ from the frozen stage')
    jobs = spec.get('jobs')
    require(isinstance(jobs, list) and len(jobs) == 8, 'Exactly eight GPU scheduling slots required')
    for gpu, job in enumerate(jobs):
        if gpu < real_gpus:
            ranks = [gpu+real_gpus*copy for copy in range(copies)]
            expected = dict(devices=[gpu], role='real_supervisor', worker_ranks=ranks,
                episode_ids=[identity for rank in ranks for identity in plan['episode_ids'][rank::count]],
                command=['bash', str(Path(__file__).with_name('run_gpu.sh').resolve()), 'supervisor',
                    '--config', str(Path(cp).resolve()), '--freeze', str(Path(fp).resolve()),
                    '--stage', stage, '--wave-id', Path(wave).name, '--gpu-rank', str(gpu), '--workers', str(count)])
        else:
            expected = dict(devices=[gpu], role='empty_gpu_slot', command=['/usr/bin/true'],
                worker_ranks=[], episode_ids=[], model_calls=0, simulator_calls=0,
                optimizer_updates=0, attempts=0)
        require(job == expected, 'GPU slot command, source assignment, or empty-slot contract changed')


def wave_gate(config, cp, fp, wave, stage, artifacts, old_config):
    """Completion/assignment metadata only. New outcome reads happen afterward."""
    wave = Path(wave).resolve(); plan = config['execution_plans'][stage]
    require(wave.parent == (ROOT/'execution'/stage).resolve(), 'Wave is outside its registered stage')
    launch = read(file_ref(wave/'launch_result.json', artifacts, role='wave'))
    require(launch.get('status') == 'complete' and type(launch.get('returncode')) is int and launch['returncode'] == 0
        and launch.get('lifecycle_covers_entire_wave') is True and launch.get('hold_idle') is False
        and launch.get('next_stage_automatically_started') is False, 'Wait for successful complete lifecycle exit')
    spec_path = file_ref(wave/'wave_spec.json', artifacts, role='wave'); spec = read(spec_path)
    expected = dict(config_sha256=storage.sha256(cp), freeze_sha256=storage.sha256(fp), stage=stage,
        workers=plan['workers'], episode_ids=plan['episode_ids'], original_primary_slots=len(plan['episode_ids']),
        methods=plan['methods'], repeats=plan['repeats'], bank_mode=plan['bank_mode'],
        reference_methods=plan.get('reference_methods', []), ref_repeats=plan.get('ref_repeats', []),
        expected_attempts=plan['expected_attempts'], source_capture_allowed=False, replacement_allowed=False,
        hold_idle=False, next_stage_automatically_started=False)
    require(all(spec.get(k) == v for k, v in expected.items()), 'Frozen execution plan/wave differs')
    audit_device_slots(config, cp, fp, wave, stage, spec)
    command = launch.get('command', [])
    require('--spec' in command and command[command.index('--spec')+1:] == [str(spec_path)], 'Launch referenced another wave')
    workers = wave/'workers'; count = plan['workers']; ids = plan['episode_ids']
    require(workers.is_dir() and {p.name for p in workers.iterdir() if p.is_dir()} ==
        {f'worker_{i:02d}' for i in range(count)} and all((workers/f'worker_{i:02d}/complete.json').is_file() for i in range(count)),
        'All registered workers must seal before source outcomes may be read')
    new_protocol = config['analysis_approval']['protocol_sha256']; slots, model_hashes = {}, set()
    for rank in range(count):
        folder = workers/f'worker_{rank:02d}'; seal = sealed(folder, new_protocol, artifacts, role='worker')
        require(seal.get('role') == 'standalone_worker' and not (folder/'failure.json').exists(), 'Failed worker blocks audit')
        status = read(folder/'status.json'); assigned = ids[rank::count]
        wanted = dict(status='complete', stage=stage, wave_id=wave.name, rank=rank, workers=count,
            config_sha256=expected['config_sha256'], freeze_sha256=expected['freeze_sha256'],
            protocol_sha256=new_protocol, assigned_slot_ids=assigned, completed_slot_records=len(assigned),
            missing_slot_ids=[], source_capture_allowed=False, replacement_allowed=False, next_stage_automatically_started=False)
        require(all(status.get(k) == v for k, v in wanted.items()), 'Incomplete or changed worker assignment')
        model_hashes.add(_loaded(read(folder/'loaded_model_identity.json'), config, old_config, stage))
        require({p.stem for p in (folder/'slots').glob('*.json')} == set(assigned), 'Slot metadata inventory differs')
        for identity in assigned:
            row = read(folder/'slots'/f'{identity}.json')
            folder_expected = ROOT/'collections'/stage/identity
            require(row.get('status') == 'complete' and row.get('episode_id') == identity and identity not in slots
                and Path(row.get('completion_path', '')).resolve() == folder_expected.resolve(), 'Missing/changed logical source')
            file_ref(folder_expected/'complete.json', artifacts, expected=row['completion_sha256'], role='collection')
            slots[identity] = row
    require(set(slots) == set(ids) and len(model_hashes) == 1, 'Incomplete source set or inconsistent loaded model identity')
    return dict(status='passed', stage=stage, wave_path=str(wave), loaded_workers=count, all_slots_complete=True,
        slots=[slots[k] for k in ids], model_identity_sha256=next(iter(model_hashes)), lifecycle_returncode=0)


def _attempt(folder, summary, ledger, config, stage, kind):
    row = read(Path(folder)/'attempt.json'); number = row.get('number')
    expected = dict(stage=stage, kind=kind, identity=str(Path(folder).relative_to(ROOT)),
        resource='simulator_attempts', amount=1, protocol_sha256=config['analysis_approval']['protocol_sha256'],
        carry_in_ledger_sha256=config['carry_in']['ledger']['sha256'], optimizer_updates=0)
    require(number in ledger and ledger[number] == row and summary.get('budget_attempt') == number
        and all(row.get(k) == v for k, v in expected.items()), 'New saved attempt/ledger/stage identity differs')
    return number


def _provenance(config, bound, stage, model_hash, bank_sha=None):
    case = bound['case']
    return dict(episode_id=case['episode_id'], case_id=case['case_id'], planned_slot_id=case['episode_id'],
        task=case['task'], env_seed=case['env_seed'], split=case['split'], round=case.get('round'), stage=stage,
        protocol_sha256=config['analysis_approval']['protocol_sha256'], source_path=bound['source_path'],
        source_protocol_sha256=bound['source_protocol_sha256'], source_seal_sha256=bound['source_seal_sha256'],
        old_collection_seal_sha256=bound['collection_seal_sha256'], actual_cut=bound['actual_cut'],
        scene_fingerprint=bound['scene_fingerprint'], model_identity_sha256=model_hash,
        candidate_bank_sha256=bank_sha, suffix_seed_namespace=config['seed_namespace'],
        suffix_protocol='native10_first_ten_raw_commands_v1')


def _old_source(bound, config, artifacts):
    from experiments.native10_training_20260916.semantics import QueueSnapshot
    source = Path(bound['source_path']); p = bound['source_protocol_sha256']
    require(source == OLD_ROOT/'sources'/bound['resolved_episode_id'], 'New experiment cannot replace the old source')
    sealed(source, p, artifacts, expected=bound['source_seal_sha256'], role='old_source')
    summary = read(source/'summary.json'); case = bound['case']; cut = bound['actual_cut']
    require(summary['case'] == case and summary['actual_cut'] == cut and summary['no_cut'] == bound['no_cut']
        and summary['scene_fingerprint'] == bound['scene_fingerprint'] and summary['source_horizon'] == 10
        and summary['control_budget'] == 300, 'Frozen source/context/cut identity differs')
    collection = Path(bound['collection_path'])
    sealed(collection, p, artifacts, expected=bound['collection_seal_sha256'], role='old_collection')
    old_collection = read(collection/'summary.json')
    require(old_collection['case'] == case and old_collection['methods'] == list(OLD_METHODS)
        and old_collection['replicates'] == 4 and old_collection['no_cut'] == bound['no_cut'],
        'Old five-arm source denominator/protocol changed')
    if cut is None:
        require(bound['planned_slot_id'] in NO_CUT_IDS and summary['full_episode_outcome_available'] is True
            and type(summary['success']) is bool and summary['success'] == bound['common_outcome']
            and old_collection['common_outcome'] == bound['common_outcome'] and old_collection['branch_records'] == [],
            'Known no-alarm common outcome changed')
        return summary, old_collection, None, None, None, None, None
    context = arrays(source/f'cut{cut:03d}/context.npz'); anchor = read(source/f'cut{cut:03d}/anchor.json')
    state_keys = ('history', 'history_mask', 'proprio', 'proprio_mask', 'past_actions', 'language', 'remaining')
    observed = {k: context[k] for k in state_keys}
    snapshot = QueueSnapshot.from_dict(anchor['queue'], raw_plan=context['full_plan'])
    require(snapshot.step == cut and anchor['live_nonterminal'] is True, 'Old live anchor/queue changed')
    bank = Path(bound['old_bank_path']); sealed(bank, p, artifacts, expected=bound['old_bank_seal_sha256'], role='old_bank')
    return summary, old_collection, arrays(source/'trajectory.npz'), snapshot, observed, arrays(bank/'formal_directions.npz'), read(bank/'generation.json')


def _old_branch_references(collection, bound, artifacts, noise, namespace):
    records = collection['branch_records']; expected = {(m, r) for m in OLD_METHODS for r in range(4)}
    saved = {(r['method'], r['repeat']): r for r in records}
    require(len(records) == len(saved) == 20 and set(saved) == expected, 'All 20 old paired branch labels are required')
    summaries = {}
    for key, ref in saved.items():
        path = Path(ref['summary_path']); folder = path.parent
        wanted = OLD_ROOT/'rollouts/heldout/heldout_policy_v1'/bound['resolved_episode_id']/f"cut{bound['actual_cut']:03d}"/key[0]/f'repeat_{key[1]}'
        require(folder == wanted, 'Old branch reference escaped its original source/method/repeat')
        seal = read(file_ref(folder/'complete.json', artifacts, expected=ref['seal_sha256'], role='old_branch'))
        require(seal.get('status') == 'complete' and seal.get('protocol_sha256') == bound['source_protocol_sha256'],
                'Old branch protocol differs')
        row = read(file_ref(path, artifacts, expected=seal['files']['summary.json'], role='old_branch'))
        require(row['method'] == key[0] and row['repeat'] == key[1] and type(row['success']) is bool
            and all(ref[k] == row[k] for k in ('success', 'budget_attempt', 'command_sha256'))
            and row['source_seal_sha256'] == bound['source_seal_sha256'], 'Old result reference identity differs')
        require(row.get('suffix_seed_namespace') == namespace, 'Old and new suffix random domains differ')
        audit_suffix_identities(row['suffix_seeds'], bound['case'], bound['actual_cut'], key[1],
            row['suffix_seed_namespace'], noise)
        summaries[key] = (row, folder, seal)
    return summaries


def _audit_bank(config, bound, stage, kind, model_hash, ledger, artifacts, observed, old_formal, old_generation,
                *, reference_native=None):
    cut = bound['actual_cut']; folder = ROOT/'banks'/stage/bound['resolved_episode_id']/f'cut{cut:03d}'/kind
    seal = sealed(folder, config['analysis_approval']['protocol_sha256'], artifacts, role=kind+'_bank')
    require(seal.get('role') == 'standalone_candidate_bundle', 'Wrong new bank role')
    generation = read(folder/'generation.json'); wanted = _provenance(config, bound, stage, model_hash)
    wanted.update(status='complete', bank_kind=kind, cut_step=cut, restore_count=1,
        saved_queue_unchanged=True, physical_state_unchanged=True, saved_before_any_branch=True,
        old_bank_used_as_generation_input=False, reference_diagnostic_only=kind == 'reference')
    require(all(generation.get(k) == v for k, v in wanted.items()), 'New bank source/model/independence identity differs')
    context_path = Path(bound['source_path'])/f'cut{cut:03d}/context.npz'
    require(generation['context_sha256'] == storage.sha256(context_path)
        and generation['source_context_array_sha256'] == {k: array_sha(v) for k, v in observed.items()},
        'New bank changed canonical old state context')
    attempt = _attempt(folder, generation, ledger, config, stage, 'candidate_restore')
    plans = arrays(folder/'plans.npz'); proofs = {}
    if kind == 'reference':
        native = arrays(folder/'directions.npz')
        proofs['old_joint_reference'] = compare_reference(arrays(Path(bound['old_bank_path'])/'plans.npz'),
            old_formal, plans, native)
        return folder, plans, native, attempt, proofs
    require(set(plans) == set(SOLO_METHODS) and set(generation['independent_entries']) == set(SOLO_METHODS)
        and set(generation['guards']) == set(SOLO_METHODS), 'Independent bank must contain exactly three entries')
    for method in SOLO_METHODS:
        saved = arrays(folder/'methods'/method/'arrays.npz')
        metadata = read(folder/'methods'/method/'generation.json')
        require(metadata == generation['independent_entries'][method] and bit_equal(plans[method], saved['raw_plan']),
            'Method arrays/metadata differ from executed bank')
        proofs[method] = audit_method(method, saved, metadata, old_formal, old_generation, observed,
            bound['case'], cut, config, reference_native=reference_native)
    return folder, plans, None, attempt, proofs


def _audit_records(config, stage, gate, ledger, artifacts):
    plan = config['execution_plans'][stage]; records, used, proofs = [], [], []
    new_protocol = config['analysis_approval']['protocol_sha256']
    for slot in gate['slots']:
        identity = slot['episode_id']; bound = config['inputs']['sources'][identity]
        source_summary, old_collection, source_data, queue, observed, old_formal, old_generation = _old_source(bound, config, artifacts)
        folder = ROOT/'collections'/stage/identity
        sealed(folder, new_protocol, artifacts, expected=slot['completion_sha256'], role='collection')
        row = read(folder/'summary.json'); wanted = _provenance(config, bound, stage, gate['model_identity_sha256'])
        wanted.update(status='complete', case=bound['case'], no_cut=bound['no_cut'],
            cuts=[] if bound['no_cut'] else [bound['actual_cut']], methods=plan['methods'],
            replicates=len(plan['repeats']), repeat_indices=plan['repeats'],
            reference_methods=plan.get('reference_methods', []), ref_repeats=plan.get('ref_repeats', []),
            planned_episode_retained=True, outcome_filter_applied=False, new_source_capture=False,
            initialization_replacement=False, old_common_outcome_reused=bound['no_cut'],
            logical_branch_count=3*len(plan['repeats']))
        require(all(row.get(k) == v for k, v in wanted.items()) and row['actual_branch_count'] == slot['actual_branch_count']
            and row['no_cut'] == slot['no_cut'], 'New collection changed source/denominator/plan')
        source_proofs = dict(planned_slot_id=identity, status='passed', reference_replays=[])
        if bound['no_cut']:
            require(stage == protocol.FORMAL and row['candidate_banks'] == {} and row['branch_records'] == []
                and row['actual_branch_count'] == 0 and row['common_outcome_available'] is True
                and row['common_outcome'] == bound['common_outcome'], 'No-cut source must preserve its original common outcome')
            outcomes = {m: [bound['common_outcome']]*4 for m in METHODS}
        else:
            noise = {}; old_branches = _old_branch_references(old_collection, bound, artifacts, noise, config['seed_namespace'])
            kinds = ['reference', 'solo'] if plan['bank_mode'] == 'paired_reference' else ['solo']
            require(set(row['candidate_banks']) == set(kinds), 'Unexpected/missing production or reference bank')
            banks = {}; reference_native = None
            for kind in kinds:
                bank, plans, native, attempt, proof = _audit_bank(config, bound, stage, kind, gate['model_identity_sha256'],
                    ledger, artifacts, observed, old_formal, old_generation, reference_native=reference_native)
                require(row['candidate_banks'][kind] == dict(path=str(bank), seal_sha256=storage.sha256(bank/'complete.json')),
                    'Collection bank binding differs')
                banks[kind] = (bank, plans); used.append(attempt); source_proofs[kind] = proof
                if kind == 'reference': reference_native = native
            expected_pairs = {(m, r) for m in plan['methods'] for r in plan['repeats']}
            expected_pairs |= {(m, r) for m in plan.get('reference_methods', []) for r in plan.get('ref_repeats', [])}
            saved = {(r['method'], r['repeat']): r for r in row['branch_records']}
            require(len(saved) == len(row['branch_records']) == row['actual_branch_count'] == len(expected_pairs)
                and set(saved) == expected_pairs, 'New branch set is incomplete or has duplicates')
            outcomes = {m: [old_branches[(m, r)][0]['success'] for r in range(4)] for m in OLD_METHODS}
            outcomes.update({m: [None]*4 for m in SOLO_METHODS})
            for (method, repeat), ref in saved.items():
                kind = 'reference' if method in OLD_METHODS else 'solo'; bank, plans = banks[kind]
                branch = ROOT/'rollouts'/stage/identity/f"cut{bound['actual_cut']:03d}"/method/f'repeat_{repeat}'
                sealed(branch, new_protocol, artifacts, expected=ref['seal_sha256'], role='branch')
                actual = read(branch/'summary.json')
                expected = _provenance(config, bound, stage, gate['model_identity_sha256'], storage.sha256(bank/'complete.json'))
                expected.update(status='complete', method=method, candidate_name=method, repeat=repeat,
                    cut_step=bound['actual_cut'], paired_suffix_id=f"{identity}:cut{bound['actual_cut']}:repeat{repeat}",
                    execution_role='continue_native10' if method == 'continue_native10' else 'alarm_replan10',
                    source_horizon=10, suffix_horizon=10, generated_horizon=50, restore_included_in_attempt=True,
                    physical_outcome_reused=False, normalized_queue_injection=False, reference_reproduction=kind == 'reference')
                require(all(actual.get(k) == v for k, v in expected.items()) and type(actual.get('success')) is bool
                    and ref['summary_path'] == str(branch/'summary.json')
                    and all(ref[k] == actual[k] for k in ('success', 'budget_attempt', 'command_sha256')),
                    'New branch command/model/source/paired identity differs')
                used.append(_attempt(branch, actual, ledger, config, stage, 'branch_including_restore'))
                old_loader._branch_trajectory(actual, branch, source_data, queue,
                    None if method == 'continue_native10' else plans[method])
                audit_suffix_identities(actual['suffix_seeds'], bound['case'], bound['actual_cut'], repeat,
                    config['seed_namespace'], noise)
                if kind == 'reference':
                    old_summary, old_path, old_seal = old_branches[(method, repeat)]
                    file_ref(old_path/'trajectory.npz', artifacts, expected=old_seal['files']['trajectory.npz'], role='old_replay')
                    source_proofs['reference_replays'].append(dict(method=method, repeat=repeat,
                        **compare_replay(old_summary, actual, arrays(old_path/'trajectory.npz'), arrays(branch/'trajectory.npz'))))
                else:
                    outcomes[method][repeat] = actual['success']
        if stage == protocol.FORMAL:
            require(all(type(x) is bool for values in outcomes.values() for x in values), 'Formal labels are technically incomplete')
            records.append(dict(planned_slot_id=identity, resolved_episode_id=bound['resolved_episode_id'], task=bound['task'],
                scene_fingerprint=bound['scene_fingerprint'], status='complete', artifact_audit_status='passed',
                pairing_audit_status='passed', no_cut=bound['no_cut'], actual_cut=bound['actual_cut'],
                common_outcome=bound['common_outcome'] if bound['no_cut'] else None, outcomes=outcomes))
        # Preflight saves only identity/projection/replay pass flags, never solo labels/ranking.
        proofs.append(source_proofs)
    return records, used, proofs


def _run(config_path, freeze_path, wave_path, *, version, stage):
    import re
    from .prepare import verify_frozen
    require(isinstance(version, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', version), 'Safe new audit version required')
    output = ROOT/('preflight_audits' if stage == protocol.PREFLIGHT else 'audits')/version
    require(not output.exists(), 'Audit output must be new')
    cp, fp = Path(config_path).resolve(), Path(freeze_path).resolve()
    config = verify_frozen(cp, fp, stage); artifacts = {}
    if stage == protocol.PREFLIGHT:
        require(version == config['protocol_version'], 'Preflight audit version must be the frozen formal-gate version')
    file_ref(cp, artifacts, role='config'); file_ref(fp, artifacts, role='freeze')
    old_cp = file_ref(OLD_ROOT/'heldout_protocols/heldout_v1/config.json', artifacts,
        expected='d86dc14afddf81a37587ff020cd36cc07e85869bf315502dc1778a97bda8f795', role='old_config')
    old_config = read(old_cp)
    gate = wave_gate(config, cp, fp, wave_path, stage, artifacts, old_config)
    carry = config['carry_in']['ledger']; file_ref(carry['path'], artifacts, expected=carry['sha256'], role='carry_in')
    ledger_path = ROOT/'budget/attempts.jsonl'; raw = ledger_path.read_bytes()
    require(not raw or raw.endswith(b'\n'), 'Supplementary ledger must end at a complete record')
    ledger_rows = [json.loads(line) for line in raw.splitlines()]; ledger = {r['number']: r for r in ledger_rows}
    records, attempts, proofs = _audit_records(config, stage, gate, ledger, artifacts)
    plan = config['execution_plans'][stage]; cuts = sum(not config['inputs']['sources'][i]['no_cut'] for i in plan['episode_ids'])
    count_banks = cuts*(2 if plan['bank_mode'] == 'paired_reference' else 1)
    count_branches = cuts*(3*len(plan['repeats'])+len(plan.get('reference_methods', []))*len(plan.get('ref_repeats', [])))
    budget = ledger_closure(config, ledger_rows, attempts, stage=stage,
        expected_counts={'candidate_restore': count_banks, 'branch_including_restore': count_branches})
    require(budget['new_stage_attempts'] == plan['expected_attempts'], 'Full stage budget differs from frozen plan')
    result = dict(status='passed', role=PREFLIGHT_ROLE if stage == protocol.PREFLIGHT else ROLE,
        stage=stage, config_sha256=storage.sha256(cp), freeze_sha256=storage.sha256(fp),
        protocol_sha256=config['analysis_approval']['protocol_sha256'], primary_ids=plan['episode_ids'],
        expected_attempts=plan['expected_attempts'],
        completed_sources=len(gate['slots']), reached_sources=cuts, no_cut_sources=len(gate['slots'])-cuts,
        loaded_workers=gate['loaded_workers'], wave_gate={k:v for k,v in gate.items() if k != 'slots'},
        budget=budget, technical_checks=proofs, artifacts=list(artifacts.values()),
        ledger_snapshot_sha256=hashlib.sha256(raw).hexdigest(), code_sha256={str(Path(__file__).resolve()):storage.sha256(__file__),
            str(Path(__file__).with_name('statistics.py')):storage.sha256(Path(__file__).with_name('statistics.py'))},
        model_calls=0, simulator_calls=0, optimizer_updates=0, new_source_captures=0,
        selection_seals_written=0, winner_selected=False, solo_success_aggregated=stage == protocol.FORMAL,
        preflight_results_included_in_formal_statistics=False, new_independent_heldout=False)
    if stage == protocol.FORMAL:
        result['statistics'] = summarize(records, task_sha256=config['task_document']['sha256'])
        result['per_source'] = records
        from .diagnostics import summarize as summarize_diagnostics
        result['diagnostics'] = summarize_diagnostics(config, result)
    result['task_document'] = deepcopy(config['task_document'])
    for item in artifacts.values(): storage.checked(item['path'], item['sha256'])
    output.mkdir(parents=True, exist_ok=False)
    (output/'budget_snapshot.jsonl').write_bytes(raw)
    storage.dump(output/'technical_checks.json', proofs)
    if stage == protocol.FORMAL: storage.dump(output/'source_records.json', records)
    storage.dump(output/'result.json', result)
    storage.seal(output, role=result['role'], protocol_sha256=result['protocol_sha256'],
        model_calls=0, simulator_calls=0, optimizer_updates=0, selection_seals_written=0)
    return dict(status='passed', path=str(output), seal_sha256=storage.sha256(output/'complete.json'),
        result_sha256=storage.sha256(output/'result.json'), solo_success_aggregated=result['solo_success_aggregated'])


def run_audit(config_path, freeze_path, wave_path, *, version):
    return _run(config_path, freeze_path, wave_path, version=version, stage=protocol.FORMAL)


def audit_preflight(config_path, freeze_path, wave_path, *, version):
    return _run(config_path, freeze_path, wave_path, version=version, stage=protocol.PREFLIGHT)
