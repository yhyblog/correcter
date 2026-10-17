"""Isolated solo collection on sealed old sources; no capture or replacement.

Only the original physical restore and plan-recording primitives and native10
queue semantics are reused.  Production candidate generation never receives an
old bank or another method's arrays.  Every simulator restore is precharged.
"""
from copy import deepcopy
import json
from pathlib import Path
import time

import numpy as np

from experiments.native10_training_20260916.adapter import Native10Collector, digest
from experiments.native10_training_20260916.semantics import Native10Queue, make_branch_prefix, execute_prefix
from experiments.native10_training_20260916.protocol import suffix_seed
from . import storage, protocol

SOLO_METHODS = ('solo_post', 'solo_direct', 'solo_velocity')
REFERENCE_METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
STATE_KEYS = ('history', 'history_mask', 'proprio', 'proprio_mask', 'past_actions', 'language', 'remaining')


def read(path):
    return json.loads(Path(path).read_text())


def load_arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return {k: archive[k].copy() for k in archive.files}


def bit_equal(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def checked_seal(folder, expected=None, *, expected_protocol=None):
    """Metadata-only sealing check, used before loading any executable context."""
    folder = Path(folder).resolve(); record = read(folder/'complete.json')
    if expected is not None and storage.sha256(folder/'complete.json') != expected:
        raise ValueError('Source/bank seal identity changed')
    if record.get('status') != 'complete' or expected_protocol is not None and record.get('protocol_sha256') != expected_protocol:
        raise ValueError('Complete expected-protocol artifact required')
    files = record.get('files', {})
    actual = {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p != folder/'complete.json'}
    if not isinstance(files, dict) or set(files) != actual:
        raise ValueError('Sealed artifact inventory changed')
    for name, expected_sha in files.items():
        path = (folder/name).resolve()
        if not path.is_relative_to(folder) or storage.sha256(path) != expected_sha:
            raise ValueError('Sealed artifact member changed: '+str(path))
    return record


def stage_plan(config, stage):
    plan = config['execution_plans'][stage]
    ids, methods, repeats = plan['episode_ids'], plan['methods'], plan['repeats']
    if (not ids or len(ids) != len(set(ids)) or set(methods) != set(SOLO_METHODS) or len(methods) != 3
            or len(repeats) != len(set(repeats))
            or any(type(x) is not int or not 0 <= x < 4 for x in repeats)
            or plan['bank_mode'] not in ('solo', 'paired_reference')):
        raise ValueError('Explicit source, independent method and paired-repeat plan required')
    reference_methods = plan.get('reference_methods', [])
    reference_repeats = plan.get('ref_repeats', [])
    if plan['bank_mode'] == 'solo':
        if not repeats or reference_methods or reference_repeats:
            raise ValueError('Formal solo collection cannot execute reference generation or replay')
    elif (not reference_methods or len(set(reference_methods)) != len(reference_methods)
            or not set(reference_methods) <= set(REFERENCE_METHODS) or not reference_repeats
            or len(reference_repeats) != len(set(reference_repeats))
            or any(type(x) is not int or not 0 <= x < 4 for x in reference_repeats)):
        raise ValueError('Reference diagnostics require an explicit method/repeat list')
    sources = config['inputs']['sources']
    if any(key not in sources for key in ids):
        raise ValueError('Unregistered original source')
    cut_count = sum(not sources[key]['no_cut'] for key in ids)
    per_cut = 1+len(methods)*len(repeats)
    if plan['bank_mode'] == 'paired_reference':
        per_cut += 1+len(reference_methods)*len(reference_repeats)
    if plan.get('expected_attempts') != cut_count*per_cut:
        raise ValueError('Execution plan does not close independent restore/branch accounting')
    return plan


class Collector:
    restore = Native10Collector.restore
    _record_plan = Native10Collector._record_plan

    def __init__(self, engine, config, ledger, stage):
        protocol.validate_config(config, require_runnable=True)
        protocol.require_stage_budget(config, stage)
        self.plan = stage_plan(config, stage)
        self.engine, self.config, self.ledger, self.stage = engine, config, ledger, stage
        self.runtime = engine.runtime
        self.namespace, self.budget = config['seed_namespace'], config['control_budget']
        if self.budget != 300 or config['source_horizon'] != 10:
            raise ValueError('Original native10/300 semantics are fixed')
        self.protocol_sha256 = config['analysis_approval']['protocol_sha256']
        self.config_sha256 = protocol.canonical_hash(config)
        self.cases = {r['episode_id']: r for r in config['episode_manifest']}
        self.engine.verify()
        self.loaded_identity = deepcopy(engine.loaded_identity)
        self.model_identity_sha256 = protocol.canonical_hash(self.loaded_identity)

    def capture(self, *args, **kwargs):
        raise ValueError('Standalone ablation forbids new capture or replacement')

    def _case(self, case):
        identity = case.get('episode_id')
        if (identity not in self.plan['episode_ids'] or self.cases.get(identity) != case
                or case.get('case_id') != identity or case.get('replacement_of')
                or protocol.canonical_hash(self.config) != self.config_sha256):
            raise ValueError('Only the exact registered original source can be restored')
        return identity

    def _source(self, case):
        identity = self._case(case); row = self.config['inputs']['sources'][identity]
        if row['case'] != case or row['planned_slot_id'] != identity or row['resolved_episode_id'] != identity:
            raise ValueError('Source replacement or manifest drift is forbidden')
        source = Path(row['source_path']).resolve()
        if source.is_relative_to(storage.ROOT.resolve()):
            raise ValueError('Source must be the separate immutable old artifact')
        checked_seal(source, row['source_seal_sha256'], expected_protocol=row['source_protocol_sha256'])
        summary = read(source/'summary.json')
        if (summary['case'] != case or summary['actual_cut'] != row['actual_cut']
                or summary['no_cut'] != row['no_cut'] or summary['scene_fingerprint'] != row['scene_fingerprint']
                or summary['source_horizon'] != 10 or summary['control_budget'] != 300):
            raise ValueError('Old source/cut/physical identity changed')
        if row['no_cut'] and (summary['full_episode_outcome_available'] is not True
                or type(row['common_outcome']) is not bool or summary['success'] != row['common_outcome']):
            raise ValueError('Unknown common outcome cannot fill a missing source')
        return row, source, summary

    def _provenance(self, case, row, *, bank=None):
        return dict(episode_id=case['episode_id'], case_id=case['case_id'], planned_slot_id=case['episode_id'],
            task=case['task'], env_seed=case['env_seed'], split=case['split'], round=case.get('round'),
            stage=self.stage, protocol_sha256=self.protocol_sha256,
            source_path=row['source_path'], source_protocol_sha256=row['source_protocol_sha256'],
            source_seal_sha256=row['source_seal_sha256'], old_collection_seal_sha256=row['collection_seal_sha256'],
            actual_cut=row['actual_cut'], scene_fingerprint=row['scene_fingerprint'],
            model_identity_sha256=self.model_identity_sha256,
            candidate_bank_sha256=storage.sha256(Path(bank)/'complete.json') if bank else None,
            suffix_seed_namespace=self.namespace, suffix_protocol='native10_first_ten_raw_commands_v1')

    def bank_path(self, case, kind):
        cut = self.config['inputs']['sources'][case['episode_id']]['actual_cut']
        return storage.ROOT/'banks'/self.stage/case['case_id']/f'cut{cut:03d}'/kind

    def _reserve(self, kind, path):
        if kind not in ('candidate_restore', 'branch_including_restore'):
            raise ValueError('Only counted restore/continuation attempts are permitted')
        protocol.require_stage_budget(self.config, self.stage)
        path = Path(path).resolve()
        if not path.is_relative_to(storage.ROOT.resolve()):
            raise ValueError('New artifacts cannot write into the old workflow')
        if path.exists():
            raise FileExistsError('No automatic resume/retry or overwrite of an attempted artifact')
        attempt = self.ledger.reserve(self.stage, kind, str(path.relative_to(storage.ROOT)))
        path.mkdir(parents=True, exist_ok=False); storage.dump(path/'attempt.json', attempt)
        return attempt

    def prepare_bank(self, case, *, kind='solo'):
        row, source, _ = self._source(case)
        if row['no_cut'] or kind not in ('solo', 'reference'):
            raise ValueError('No candidate restore for no-cut sources or unknown bank kinds')
        if kind == 'reference' and self.plan['bank_mode'] != 'paired_reference':
            raise ValueError('Reference generator is restricted to explicit technical preflight')
        cut = row['actual_cut']; dest = self.bank_path(case, kind)
        attempt = self._reserve('candidate_restore', dest)
        begin = time.perf_counter(); _, snapshot, _ = self.restore(case, source, cut)
        restored = time.perf_counter(); context_path = source/f'cut{cut:03d}'/'context.npz'
        context = load_arrays(context_path); observed = {name: context[name] for name in STATE_KEYS}
        context_hash = {k: digest(v) for k, v in observed.items()}
        queue_hash, world = digest(snapshot.raw_plan), deepcopy(self.runtime.fingerprint())
        plans, methods, guards = {}, {}, {}
        if kind == 'solo':
            from .candidates import audit_solo
            from .reference_generation import compare_archived_identity as audit_archived_identity
            # Every call gets only observed state, case and cut, never old-bank data.
            for method in self.plan['methods']:
                plan, metadata, directions = self.engine.generate_solo(observed, case, cut, method)
                if (metadata['method'] != method or plan.dtype != np.float32 or plan.shape != (50, 4)
                        or not np.isfinite(plan).all() or not bit_equal(plan, directions['raw_plan'])):
                    raise ValueError('Independent entry returned the wrong raw command identity')
                audit = audit_solo(directions['raw_a0'], plan, directions['raw_direction'], self.config['matching'])
                guards[method] = dict(raw=audit, archived=audit_archived_identity(
                    directions, metadata, row['old_bank_path'], expected_seal=row['old_bank_seal_sha256']))
                if any(digest(observed[k]) != v for k, v in context_hash.items()):
                    raise ValueError('Candidate generation mutated the fixed source context')
                metadata = dict(metadata, **self._provenance(case, row), cut_step=cut,
                    source_context_file_sha256=storage.sha256(context_path), source_context_array_sha256=context_hash)
                storage.arrays(dest/'methods'/method/'arrays.npz', **directions)
                storage.dump(dest/'methods'/method/'generation.json', metadata)
                plans[method], methods[method] = plan, metadata
        else:
            from .reference_generation import generate_reference
            plans, metadata, directions = generate_reference(self.engine, observed, case, cut)
            aliases = dict(replan='alarm_replan10', velocity_matched='velocity', direct_matched='direct', post_matched='post')
            plans = {aliases.get(name, name): value for name, value in plans.items()}
            storage.arrays(dest/'directions.npz', **directions)
            methods['reference'] = metadata
        if digest(snapshot.raw_plan) != queue_hash or self.runtime.fingerprint() != world:
            raise ValueError('Generation altered the original queue or restored physical state')
        if any(digest(observed[k]) != v for k, v in context_hash.items()):
            raise ValueError('Generation mutated source context')
        self.engine.verify()
        storage.arrays(dest/'plans.npz', **plans)
        storage.dump(dest/'generation.json', dict(self._provenance(case, row), status='complete', bank_kind=kind,
            cut_step=cut, budget_attempt=attempt['number'], context_sha256=storage.sha256(context_path),
            source_context_array_sha256=context_hash, restore_seconds=restored-begin,
            candidate_generation_seconds=time.perf_counter()-restored, wall_seconds=time.perf_counter()-begin,
            independent_entries=methods, guards=guards, candidate_names=list(plans),
            restore_count=1, saved_queue_unchanged=True, physical_state_unchanged=True,
            saved_before_any_branch=True, old_bank_used_as_generation_input=False,
            reference_diagnostic_only=kind == 'reference'))
        storage.seal(dest, protocol_sha256=self.protocol_sha256, role='standalone_candidate_bundle')
        return dest

    def branch(self, case, method, repeat, bank):
        row, source, _ = self._source(case); bank = Path(bank)
        is_reference = method in REFERENCE_METHODS
        allowed_methods = self.plan.get('reference_methods', []) if is_reference else self.plan['methods']
        allowed_repeats = self.plan.get('ref_repeats', []) if is_reference else self.plan['repeats']
        if method not in allowed_methods or type(repeat) is not int or repeat not in allowed_repeats or row['no_cut']:
            raise ValueError('Unregistered method, repeat, reference branch or no-cut continuation')
        expected_bank = self.bank_path(case, 'reference' if is_reference else 'solo')
        if bank.resolve() != expected_bank.resolve():
            raise ValueError('Candidate bank belongs to another source/stage/generation role')
        checked_seal(bank, expected_protocol=self.protocol_sha256)
        generation = read(bank/'generation.json')
        if generation['source_seal_sha256'] != row['source_seal_sha256'] or generation['model_identity_sha256'] != self.model_identity_sha256:
            raise ValueError('Branch source or loaded model differs from its candidate generation')
        plans = load_arrays(bank/'plans.npz'); normal = method == 'continue_native10'
        plan = None if normal else plans[method]
        cut = row['actual_cut']; dest = storage.ROOT/'rollouts'/self.stage/case['case_id']/f'cut{cut:03d}'/method/f'repeat_{repeat}'
        attempt = self._reserve('branch_including_restore', dest)
        begin = time.perf_counter(); trace, snapshot, _ = self.restore(case, source, cut)
        restore_seconds = time.perf_counter()-begin
        role = 'continue_native10' if normal else 'alarm_replan10'
        prefix = make_branch_prefix(snapshot, role, plan)
        executed = execute_prefix(prefix, lambda command: trace.execute(self.runtime, command),
                                  lambda: trace.terminal, lambda: trace.step)
        endpoint = digest(self.runtime.frame()); suffix = []
        queue = Native10Queue(start_step=trace.step, budget=self.budget)
        while not trace.terminal and trace.step < self.budget:
            step = trace.step
            if queue.needs_plan(step):
                index = len(suffix); seed = suffix_seed(case, cut, repeat, index, namespace=self.namespace)
                raw, stats = self.engine.propose(seed)
                queue.replace(raw, step); self._record_plan(trace, raw, seed, stats)
                suffix.append(dict(step=step, decision_index=index, seed=seed, noise_sha256=stats.get('noise_sha256')))
            trace.execute(self.runtime, queue.pop(step))
        self.engine.verify(); storage.arrays(dest/'trajectory.npz', **trace.arrays())
        storage.dump(dest/'summary.json', dict(self._provenance(case, row, bank=bank), status='complete',
            method=method, candidate_name=method, execution_role=role, repeat=repeat, cut_step=cut,
            paired_suffix_id=f"{case['episode_id']}:cut{cut}:repeat{repeat}",
            pairing='original episode/cut/repeat/suffix decision index; source states and arm phases can differ',
            budget_attempt=attempt['number'], source_horizon=10, suffix_horizon=10, generated_horizon=50,
            success=bool(any(trace.successes)), terminal_step=trace.step,
            requested_prefix_steps=prefix.requested_steps, actual_prefix_steps=executed.actual_steps,
            first_expected_resample=prefix.next_sample_step, first_actual_resample=suffix[0]['step'] if suffix else None,
            suffix_seeds=suffix, endpoint_image_sha256=endpoint, command_sha256=digest(prefix.commands),
            clipped_command_proxy_sha256=digest(np.clip(prefix.commands, -1, 1)),
            restore_seconds=restore_seconds, policy_calls=trace.policy_calls, policy_seconds=trace.policy_seconds,
            environment_seconds=trace.environment_seconds, wall_seconds=time.perf_counter()-begin,
            original_queue_remaining=snapshot.remaining_steps, restore_included_in_attempt=True,
            physical_outcome_reused=False, normalized_queue_injection=False, reference_reproduction=is_reference))
        storage.seal(dest, protocol_sha256=self.protocol_sha256, role='standalone_branch')
        return dest

    def collect_episode(self, case):
        row, source, _ = self._source(case)
        dest = storage.ROOT/'collections'/self.stage/case['case_id']
        if dest.exists():
            raise FileExistsError('No automatic repeated collection or outcome-dependent replacement')
        branches, banks = [], {}
        if not row['no_cut']:
            if self.plan['bank_mode'] == 'paired_reference':
                banks['reference'] = self.prepare_bank(case, kind='reference')
            banks['solo'] = self.prepare_bank(case, kind='solo')
            modes = [('reference', self.plan.get('reference_methods', []), self.plan.get('ref_repeats', [])),
                     ('solo', self.plan['methods'], self.plan['repeats'])]
            for kind, methods, repeats in modes:
                for method in methods:
                    for repeat in repeats:
                        path = self.branch(case, method, repeat, banks[kind]); meta = read(path/'summary.json')
                        branches.append(dict(method=method, repeat=repeat, summary_path=str(path/'summary.json'),
                            seal_sha256=storage.sha256(path/'complete.json'), success=meta['success'],
                            budget_attempt=meta['budget_attempt'], command_sha256=meta['command_sha256']))
        dest.mkdir(parents=True, exist_ok=False)
        storage.dump(dest/'summary.json', dict(self._provenance(case, row), status='complete', case=case,
            no_cut=row['no_cut'], cuts=[] if row['no_cut'] else [row['actual_cut']],
            common_outcome_available=row['no_cut'], common_outcome=row['common_outcome'] if row['no_cut'] else None,
            methods=self.plan['methods'], replicates=len(self.plan['repeats']), repeat_indices=self.plan['repeats'],
            reference_methods=self.plan.get('reference_methods', []), ref_repeats=self.plan.get('ref_repeats', []),
            candidate_banks={kind:dict(path=str(path), seal_sha256=storage.sha256(path/'complete.json')) for kind,path in banks.items()},
            branch_records=branches, actual_branch_count=len(branches),
            logical_branch_count=len(self.plan['methods'])*len(self.plan['repeats']),
            planned_episode_retained=True, outcome_filter_applied=False, new_source_capture=False,
            initialization_replacement=False, old_common_outcome_reused=row['no_cut']))
        storage.seal(dest, protocol_sha256=self.protocol_sha256, role='standalone_collection')
        return dict(status='complete', episode_id=case['episode_id'], planned_slot_id=case['episode_id'],
            resolved_episode_id=case['episode_id'], no_cut=row['no_cut'],
            actual_branch_count=len(branches), completion_path=str(dest), completion_sha256=storage.sha256(dest/'complete.json'))


def create_collector(config, stage):
    protocol.validate_config(config, require_runnable=True)
    protocol.require_stage_budget(config, stage)
    stage_plan(config, stage)
    from .engine import create_engine
    return Collector(create_engine(config, stage), config, storage.AttemptLedger(config), stage)
