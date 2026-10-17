"""Independent authorization; old native10 READY never releases this scope."""
from collections import Counter
from pathlib import Path
import json
from experiments.native10_training_20260916.protocol import (
    TASKS, canonical_hash, candidate_seed, suffix_seed, seed_for, validate_manifest)
from .storage import checked, read

TASK_ID = 'standalone-ablation-20260918'
PREFLIGHT = 'standalone_preflight'
FORMAL = 'standalone_formal'
REPAIR = 'standalone_technical_repair'
METHODS = ('solo_post', 'solo_direct', 'solo_velocity')
OLD_METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
PRIMARY_IDS = tuple(f'{TASKS[i % 5]}__{start+i}' for start in (2026111750, 2026111850) for i in range(50))
PRIMARY_IDS_SHA = canonical_hash(list(PRIMARY_IDS))
PRE_IDS = tuple(f'{task}__{2026111750+i}' for i, task in enumerate(TASKS))
COMMON_IDS = ('pick-place-wall-v3__2026111866', 'pick-place-wall-v3__2026111881')
CAPS = {PREFLIGHT:60, FORMAL:1400, REPAIR:40}
BASE_LEDGER_SHA = '3f293430a26d7c0405c33b797788fdfd099f3b8d0a42aec7c37a89338a4ef552'
SELECTED_SHA = 'f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a'
MATCHING = dict(xyz_rms=.05, gripper_rms=.10, xyz_linf=.15, gripper_linf=.40,
    boundary_clearance=.05, zero_threshold=1e-10, tolerance=1e-6)


def _require(value, message):
    if not value: raise ValueError(message)


def protocol_digest(config):
    return canonical_hash({k:v for k,v in config.items() if k != 'analysis_approval'})


def require_ready(config):
    ref = config.get('analysis_ready', {})
    path = Path(ref.get('path', ''))
    _require(path.is_absolute() and path.name == 'STANDALONE_ABLATION_ANALYSIS_READY.json', 'New standalone READY required')
    ready = read(checked(path, ref.get('sha256')))
    _require(ready.get('task_id') == TASK_ID and (ready.get('status') == 'approved'
        or str(ready.get('status','')).startswith('protocol_approved_')), 'Standalone approved READY required')
    task = config['task_document']; checked(task['path'], task['sha256'])
    _require(ready.get('task_document') == task['path'] and ready.get('task_document_sha256') == task['sha256'],
        'READY must bind the precise new scientific TASK')
    _require(isinstance(ready.get('released_scope'), list) and ready['released_scope'], 'Explicit released scopes required')
    _require(ready.get('standalone_ablation') == config.get('release_contract'), 'Exact standalone release contract differs')
    _require(ready.get('standalone_preparation_binding') == config.get('preparation_binding'),
        'Actual pending inputs/code/CPU preparation binding differs')
    return ready


def validate_config(config, *, require_runnable=False):
    _require(config.get('task_id') == TASK_ID and config.get('schema_version') == 1, 'Wrong standalone protocol')
    _require(config.get('status') in ('pending','frozen'), 'Pending/frozen status required')
    _require(config.get('tasks') == list(TASKS), 'Original task order required')
    registry = validate_manifest(config['episode_manifest'])
    _require(list(registry) == list(PRIMARY_IDS) and
        Counter(row['task'] for row in registry.values()) == {t:20 for t in TASKS}, 'Original 100 held IDs/order required')
    _require(all(x.get('split') == 'heldout' and not x.get('replacement_of') for x in registry.values()), 'No new split or replacements')
    sources = config['inputs']['sources']
    _require(config['inputs'].get('source_bindings_hash') == canonical_hash(sources) and
        config['inputs'].get('primary_ids_hash') == PRIMARY_IDS_SHA, 'Source/ID content hash differs')
    _require(list(sources) == list(PRIMARY_IDS), 'Source bindings/order differ')
    _require(tuple(k for k,v in sources.items() if v['no_cut']) == COMMON_IDS, 'Retain exactly two existing common outcomes')
    for identity, row in sources.items():
        _require(row['case'] == registry[identity] and row['planned_slot_id'] == row['resolved_episode_id'] == identity,
            'Source/case identity changed')
        if row['no_cut']:
            _require(row['actual_cut'] is None and type(row['common_outcome']) is bool, 'Unknown common outcome cannot be imputed')
        else:
            cut = row['actual_cut']
            _require(type(cut) is int and cut % 10 == 5 and 5 <= cut <= 285, 'Only original legal cut')
    _require(all(config.get(k) == 10 for k in ('source_horizon','prefix_horizon','suffix_horizon')) and
        config.get('control_budget') == 300 and config.get('generated_horizon') == 50, 'Native10/300/50 unchanged')
    _require(config.get('gate_threshold') == .05 and config.get('seed_namespace') == 'corrector_native10_training_20260916_v1', 'Original gate/random namespace required')
    _require(config['guidance'].get('alpha') == 10 and config['guidance'].get('times') == [.3,.2,.1], 'Original flow alpha/times required')
    _require(all(config['matching'].get(k) == v for k,v in MATCHING.items()), 'Matching constants changed')
    _require(config.get('solo_rule') == dict(radius='own_symmetric_capacity', shrink=1-1e-6,
        expand_native=True, other_direction_dependencies=False, each_method_regenerates_a0=True,
        random_fallback=False, q_acceptance_gate=False), 'Own-direction-only scientific rule differs')
    carry = config['carry_in']
    _require(carry.get('simulator_attempts') == 48183 and carry.get('optimizer_updates') == 51200 and
        carry['ledger'].get('sha256') == BASE_LEDGER_SHA and carry.get('global_simulator_limit') == 50000 and
        carry.get('global_optimizer_limit') == 51200, 'Immutable cross-ledger base differs')
    _require(config['selected_model']['seal_sha256'] == SELECTED_SHA and config['selected_model']['selection'] == {'path':'A','step':4000}, 'Only frozen A4000')
    budget = config['budget']
    _require(budget.get('hard_total') == 1500 and budget.get('training_update_total') == 0 and
        budget.get('count_failures') is True and budget.get('count_retries') is True and
        budget['stages'] == {s:dict(simulator_attempts=n,training_updates=0) for s,n in CAPS.items()}, 'Fixed 1500/0 supplementary budget required')
    _require(config['stage_release_scopes'] == {s:s for s in CAPS}, 'Explicit independent stage/scope map required')
    _require(config.get('capture_allowed') is False and config.get('replacement_allowed') is False and
        config.get('scene_append_allowed') is False and config.get('training_allowed') is False, 'No capture/replace/scene/train')
    plans = config['execution_plans']; formal = plans[FORMAL]; pre = plans[PREFLIGHT]
    _require(formal == dict(episode_ids=list(PRIMARY_IDS),methods=list(METHODS),repeats=[0,1,2,3],
        bank_mode='solo',expected_attempts=1274,workers=32), 'Exactly one formal 100-slot three-solo wave')
    _require(pre['episode_ids'] == list(PRE_IDS) and pre['bank_mode'] == 'paired_reference' and pre['workers'] == 5,
        'Preregistered five-source reference preflight required')
    _require(pre['methods'] == list(METHODS) and set(pre['reference_methods']) <= set(OLD_METHODS), 'Preflight methods invalid')
    for name in ('repeats','ref_repeats'):
        _require(isinstance(pre[name],list) and pre[name] == sorted(set(pre[name])) and
            all(type(x) is int and 0 <= x < 4 for x in pre[name]), 'Preflight repeat indices must be ordered unique 0..3')
    expected = 5*(2+len(pre['methods'])*len(pre['repeats'])+len(pre['reference_methods'])*len(pre['ref_repeats']))
    _require(pre['expected_attempts'] == expected and expected <= CAPS[PREFLIGHT], 'Preflight plan restore/branch arithmetic differs')
    _require(config['statistics'] == dict(seed=2026091801,draws=10000,task_order=list(TASKS),source_order=list(PRIMARY_IDS),
        quantile_method='linear',unit='whole_source_within_task',primary_methods=list(METHODS),
        confidence_quantiles=[.025,.975],primary_family_quantiles=[.05/6,1-.05/6],posthoc_selection=False), 'Statistics registration changed')
    if config['status'] == 'frozen':
        from .prepare import ready_contract
        _require(config.get('release_contract') == ready_contract(config),
            'Released contract must equal the actual input/scientific configuration')
        approval = config.get('analysis_approval', {})
        _require(approval.get('status') == 'approved' and approval.get('approved_by') == 'analysis' and
            approval.get('protocol_sha256') == protocol_digest(config), 'Exact new protocol approval required')
        require_ready(config)
    if require_runnable: _require(config['status'] == 'frozen', 'Pending config cannot execute')
    return dict(status=config['status'], planned_sources=100, protocol_sha256=protocol_digest(config))


def require_stage_budget(config, stage, *, used=0, requested=1, total_used=0, resource='simulator_attempts'):
    validate_config(config, require_runnable=True)
    ready = require_ready(config)
    _require(stage in CAPS and stage in ready['released_scope'], 'Stage not released by standalone READY')
    if stage == FORMAL: require_preflight_pass(config)
    _require(resource == 'simulator_attempts' and all(type(x) is int for x in (used,requested,total_used)) and
        0 <= used <= total_used and requested >= 1, 'Only positive explicit simulator requests')
    _require(used+requested <= CAPS[stage] and total_used+requested <= 1500 and
        48183+total_used+requested <= 50000, 'Stage or cross-ledger budget exceeded')
    return dict(stage=stage,resource=resource,limit=CAPS[stage],total_limit=1500,used=used,total_used=total_used,requested=requested)


def require_preflight_pass(config):
    """The condition guards model/ledger entry too, not only the CLI runner."""
    import re
    from . import storage
    version=config.get('protocol_version','')
    _require(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,60}',version) is not None,
        'Formal work needs a frozen protocol version and passed preflight')
    protocol_path=storage.ROOT/'protocols'/version
    frozen=read(protocol_path/'freeze.json')
    config_path=checked(protocol_path/'config.json',frozen['config_sha256'])
    _require(read(config_path)==config and frozen['files'].get(str(config_path))==frozen['config_sha256'],
        'Formal work must use the exact preflight configuration')
    folder=storage.ROOT/'preflight_audits'/version
    record=storage.sealed(folder);result=read(folder/'result.json')
    _require(record.get('role')=='standalone_preflight_audit' and result.get('status')=='passed'
        and result.get('config_sha256')==frozen['config_sha256']
        and result.get('freeze_sha256')==storage.sha256(protocol_path/'freeze.json')
        and result.get('expected_attempts')==config['execution_plans'][PREFLIGHT]['expected_attempts'],
        'Same-freeze complete passing preflight is mandatory before formal work')
    return result
