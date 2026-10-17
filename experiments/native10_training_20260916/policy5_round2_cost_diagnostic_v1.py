"""Completed round2 A4000 policy diagnostics; no models, simulators or optimization.

Pure calculations are imported unchanged from the first-wave supplement. The
isolated gate and artifact walker bind the real round2 stage; no old-stage
masquerading or in-progress outcome access is permitted.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
from . import policy5_cost_diagnostic_v1 as calculations
from .policy5_cost_diagnostic_v1 import (
    ROOT, METHODS, CORRECTIONS, COMPARISONS, _hash, _canonical, _read, _inside,
    _seal, describe, _numeric, _radii, command_diagnostics, paired_summary,
    association, _npz)
SCHEMA = 'native10_round2_policy5_cost_diagnostic_v1'
STAGE = 'round2_development_policy'

def validate_gate(config, result, bank_version):
    """No artifact access: reject partial results before loading any bank."""
    registration = config['main_collection']['banks'][bank_version]
    ids = registration['episode_ids']
    rows = result.get('per_source', [])
    if (registration.get('kind') != 'policy5'
            or registration.get('stage') != STAGE
            or len(ids) != 100 or len(set(ids)) != 100
            or result.get('status') != 'passed' or result.get('planned_slots') != 100
            or result.get('technical_missing') != 0
            or result.get('source_capture_attempts_added') != 0
            or result.get('new_attempts') != 1995
            or result.get('bank_version') != bank_version
            or result.get('stage') != registration['stage']
            or result.get('config_content_sha256') != _canonical(config)
            or result.get('selected_training') != config['policy_deployment']['selected_training']
            or len(rows) != 100 or [row.get('episode_id') for row in rows] != ids):
        raise ValueError('Require the matching complete 100-slot formal policy5 audit')
    values = []
    for row in rows:
        labels = row.get('paired_outcomes', {})
        if (type(row.get('no_cut')) is not bool or not row.get('task')
                or set(labels) != set(METHODS)
                or any(len(labels[name]) != 4 or any(type(v) is not bool for v in labels[name])
                       for name in METHODS)):
            raise ValueError('Audit requires five arms and four paired boolean outcomes per source')
        value = np.array([labels[name] for name in METHODS], dtype=bool)
        if row['no_cut'] and (row.get('actual_cut') is not None or not np.all(value == value.flat[0])):
            raise ValueError('No-cut common outcome must be broadcast to all five arms')
        if not row['no_cut'] and (type(row.get('actual_cut')) is not int or row['actual_cut'] < 0):
            raise ValueError('Cut source has no actual integer cut')
        if row.get('success_counts') != dict(zip(METHODS, value.sum(1).tolist())):
            raise ValueError('Audited success counts disagree with paired labels')
        values.append(value)
    if sum(row['no_cut'] for row in rows) != 5:
        raise ValueError('This frozen policy wave requires exactly 95 cut and 5 no-cut sources')
    attempts = result.get('attempt_numbers', [])
    if len(attempts) != 1995 or len(set(attempts)) != 1995 or any(type(n) is not int or n <= 0 for n in attempts):
        raise ValueError('Formal audit does not close the 1995 distinct stage attempts')
    return np.asarray(values, dtype=bool)

def run(config_path, audit_path, *, freeze_path=None, root=ROOT):
    """Return diagnostics only after the primary sealed all-100 audit gate."""
    root, config_path, audit_path = Path(root).resolve(), Path(config_path).resolve(), Path(audit_path).resolve()
    freeze_path = Path(freeze_path).resolve() if freeze_path else config_path.parent/'freeze.json'
    _seal(audit_path, role='native10_policy5_readonly_audit')
    config, result, freeze = _read(config_path), _read(audit_path/'result.json'), _read(freeze_path)
    digest = _hash(config_path)
    if freeze.get('config_sha256') != digest or freeze.get('files', {}).get(str(config_path)) != digest:
        raise ValueError('Frozen config SHA is not bound in its freeze inventory')
    bank_version = result['bank_version']
    values = validate_gate(config, result, bank_version)  # Must precede bank/branch/source reads.
    protocol, stage = config['analysis_approval']['protocol_sha256'], result['stage']
    registration = config['main_collection']['banks'][bank_version]
    manifest = {row['episode_id']: row for row in config['episode_manifest']}
    artifact_map = {}
    for row in result.get('artifacts', []):
        path = _inside(row['path'], root)
        if str(path) in artifact_map:
            raise ValueError('Primary audit repeats an artifact identity')
        artifact_map[str(path)] = row['sha256']
    used = {str(config_path): digest, str(freeze_path): _hash(freeze_path),
            str(audit_path/'result.json'): _hash(audit_path/'result.json'),
            str(audit_path/'complete.json'): _hash(audit_path/'complete.json'),
            str(Path(__file__).resolve()): _hash(__file__),
            str(Path(calculations.__file__).resolve()): _hash(calculations.__file__)}

    def bound(path, *, arrays=False):
        path = _inside(path, root)
        expected = artifact_map.get(str(path))
        if not expected or _hash(path) != expected:
            raise ValueError('Input absent from primary audit or changed since that audit: '+str(path))
        used[str(path)] = expected
        return _npz(path) if arrays else _read(path)

    sources, generations, branches, commands, gradients = [], [], [], [], []
    for i, audit_row in enumerate(result['per_source']):
        episode = audit_row['episode_id']; case = manifest[episode]
        if case['task'] != audit_row['task'] or case.get('split') != 'development':
            raise ValueError('Audited source is not the registered development identity')
        source = dict(episode_id=episode, task=case['task'], no_cut=audit_row['no_cut'],
            actual_cut=audit_row['actual_cut'], logical_outcomes_per_arm=4,
            success_counts=audit_row['success_counts'], common_outcome_broadcast=audit_row['no_cut'])
        if source['no_cut']:
            source.update(command_diagnostic=None, q=None, physical_branches=0)
            sources.append(source)
            continue
        cut = source['actual_cut']; base = root/'banks'/bank_version/case['case_id']/f'cut{cut:03d}'
        bank_seal = bound(base/'complete.json')
        generation, plans = bound(base/'generation.json'), bound(base/'plans.npz', arrays=True)
        identity = dict(episode_id=episode, cut_step=cut, bank_version=bank_version,
                        stage=stage, protocol_sha256=protocol, model_hashes=registration['model_hashes'])
        if (bank_seal.get('status') != 'complete' or bank_seal.get('protocol_sha256') != protocol
                or any(generation.get(k) != v for k, v in identity.items())):
            raise ValueError('Generation provenance disagrees with primary audit configuration')
        guard_folder = root/'policy_guard'/stage/bank_version/episode
        _seal(guard_folder, role='policy_deployment_bank_check', protocol=protocol)
        guard = _read(guard_folder/'bank_check.json')
        for name in ('complete.json', 'bank_check.json'):
            used[str(guard_folder/name)] = _hash(guard_folder/name)
        if (guard.get('status') != 'passed' or guard.get('episode_id') != episode
                or guard.get('bank_seal_sha256') != used[str(base/'complete.json')]
                or guard.get('source_seal_sha256') != generation.get('source_seal_sha256')
                or guard.get('checked_before_branch') is not True):
            raise ValueError('Before-branch guard does not bind the audited bank')
        diagnostic = command_diagnostics(plans, config['matching'])
        predictions = generation.get('bank_predictions', {})
        if set(predictions) != set(METHODS[1:]):
            raise ValueError('Final command bank predictions are missing')
        q = {}
        for name in METHODS[1:]:
            prediction = predictions[name]
            gain = float(prediction['mean_gain'])
            probability = float(prediction['candidate_mean_probability'])
            anchor_probability = float(prediction['a0_mean_probability'])
            if not np.isfinite([gain, probability, anchor_probability]).all() or not (0<=probability<=1 and 0<=anchor_probability<=1):
                raise ValueError('Nonfinite or invalid saved final-bank Q')
            if name == 'alarm_replan10' and gain != 0:
                raise ValueError('Fixed slot-zero anchor score must be exactly zero')
            actual_gain = float((values[i, METHODS.index(name)].astype(int)-values[i, 1].astype(int)).mean())
            q[name] = dict(predicted_gain=gain, candidate_probability=probability,
                           a0_probability=anchor_probability, actual_source_gain=actual_gain)
            commands.append(dict(episode_id=episode, task=case['task'], method=name,
                **diagnostic['methods'][name]['actual_delta'],
                raw_alias_of_a0=diagnostic['methods'][name]['raw_alias_of_a0'],
                predicted_gain=gain, actual_source_gain=actual_gain))
        generation_cost = dict(episode_id=episode, task=case['task'])
        for key in ('generation_wall_seconds', 'restore_seconds', 'candidate_bank_seconds'):
            generation_cost[key] = _numeric(generation, key)
        components = {'base': generation.get('base_generation', {}),
                      **generation.get('guidance', {}), 'post': generation.get('post_gradient', {}),
                      'objective': generation.get('objective_stats', {})}
        for name, record in components.items():
            for key in ('seconds', 'policy_calls', 'objective_forward_calls', 'backward_calls',
                        'critic_member_forward_calls', 'critic_member_backward_calls', 'critic_forward_seconds',
                        'peak_cuda_allocated_mib', 'peak_cuda_reserved_mib', 'incremental_peak_cuda_allocated_mib'):
                generation_cost[name+'_'+key] = _numeric(record, key)
        generation_cost['fallbacks'] = {name: record.get('fallback') for name, record in components.items() if name in ('base','velocity','direct')}
        generations.append(generation_cost)
        for name in ('velocity', 'direct'):
            gradients.append(dict(episode_id=episode, method=name,
                                  updates=generation.get('guidance', {}).get(name, {}).get('updates', [])))
        source.update(command_diagnostic=diagnostic, q=q, physical_branches=20,
            matching_groups=generation.get('matching', {}).get('groups'), generation_cost=generation_cost,
            post_gradient=generation.get('post_gradient'), guard_matched_rms=guard.get('matched_rms'))
        for method in METHODS:
            for repeat in range(4):
                folder = root/'rollouts'/stage/bank_version/case['case_id']/f'cut{cut:03d}'/method/f'repeat_{repeat}'
                row = bound(folder/'summary.json')
                bound(folder/'complete.json')
                if (any(row.get(k) != v for k, v in identity.items()) or row.get('method') != method
                        or row.get('repeat') != repeat or row.get('status') != 'complete'
                        or row.get('candidate_bank_sha256') != used[str(base/'complete.json')]
                        or row.get('success') is not bool(values[i, METHODS.index(method), repeat])):
                    raise ValueError('Branch metadata differs from the complete audit')
                cost = dict(episode_id=episode, task=case['task'], method=method, repeat=repeat)
                for key in ('restore_seconds','policy_calls','policy_seconds','environment_seconds','wall_seconds',
                            'requested_prefix_steps','actual_prefix_steps','terminal_step'):
                    cost[key] = _numeric(row, key)
                n = row.get('actual_prefix_steps')
                if type(n) is not int or not 0 <= n <= (5 if method == METHODS[0] else 10):
                    raise ValueError('Branch actual prefix count is invalid')
                cost['executed_prefix_delta'] = None
                if method != METHODS[0]:
                    if row.get('command_sha256') != diagnostic['methods'][method]['raw10_sha256']:
                        raise ValueError('Final raw10 command SHA differs from audited branch command')
                    cost['executed_prefix_delta'] = _radii(plans[method][:n].astype(float)-plans[METHODS[1]][:n].astype(float))
                branches.append(cost)
        sources.append(source)

    task_names = sorted({row['task'] for row in sources})
    cut_mask = np.array([not row['no_cut'] for row in sources])
    stats = dict(overall=paired_summary(values), alarm_conditioned=paired_summary(values[cut_mask]),
        no_cut_common_outcomes=paired_summary(values[~cut_mask]),
        per_task={task: dict(full_denominator=paired_summary(values[[r['task']==task for r in sources]]),
            alarm_conditioned=paired_summary(values[[r['task']==task and not r['no_cut'] for r in sources]])) for task in task_names})
    # Cross-check the means/counts with the primary result; do not create new CIs.
    primary = result['statistics']
    if stats['overall']['success_counts'] != primary['overall']['success_counts']:
        raise ValueError('Supplement count disagrees with the primary audit')
    for name, row in stats['overall']['comparisons'].items():
        original = primary['comparisons'][name]
        if abs(row['mean_gain']-original['gain']) > 1e-12 or any(row[k] != original[k] for k in ('rescues','harms','positive_sources','negative_sources','zero_sources')):
            raise ValueError('Supplement comparison disagrees with primary audit')
    cut_sources = [row for row in sources if not row['no_cut']]
    q_vs_actual = {}
    for name in CORRECTIONS:
        def group(rows):
            return association([row['q'][name]['predicted_gain'] for row in rows],
                               [row['q'][name]['actual_source_gain'] for row in rows])
        q_vs_actual[name] = dict(all_cut_sources=group(cut_sources),
            nonalias_to_a0=group([row for row in cut_sources if not row['command_diagnostic']['methods'][name]['raw_alias_of_a0']]),
            per_task={task: group([row for row in cut_sources if row['task']==task]) for task in task_names})
    generation_keys = sorted({key for row in generations for key in row if key not in ('episode_id','task','fallbacks')})
    branch_keys = ('restore_seconds','policy_calls','policy_seconds','environment_seconds','wall_seconds','actual_prefix_steps','terminal_step')
    cost_summary = dict(generation={key: describe(row.get(key) for row in generations) for key in generation_keys},
        branches_by_method={name: {key: describe(row.get(key) for row in branches if row['method']==name)
                                  for key in branch_keys} for name in METHODS},
        guidance_fallback_counts={name: dict(Counter(str(row['fallbacks'].get(name)) for row in generations))
                                  for name in ('base','velocity','direct')},
        partial_prefix_branches_by_method={name: sum(row['actual_prefix_steps'] < row['requested_prefix_steps']
                                                   for row in branches if row['method']==name) for name in METHODS},
        interpretation='Timing components overlap. Sums are cumulative worker seconds, not wave elapsed time; GPU peaks are descriptive, not additive. Original source capture is reused and excluded.')
    amplitude = {name: {key: describe(row[key] for row in commands if row['method']==name)
                        for key in ('xyz_rms','gripper_rms','xyz_linf','gripper_linf')} for name in METHODS[1:]}
    quality = dict(raw_invariant_failure_counts={name: {flag: sum(not row['command_diagnostic']['methods'][name][flag] for row in cut_sources)
        for flag in ('raw_tail_bit_exact', 'outside_mask_bit_exact', 'raw_delta_equals_critic_delta', 'caps_within_frozen_tolerance')}
        for name in METHODS[1:]},
        raw_unique_group_distribution=dict(Counter(row['command_diagnostic']['raw_unique_groups'] for row in cut_sources)),
        clipped_collision_sources=sum(row['command_diagnostic']['clipped_collision_of_distinct_raw'] for row in cut_sources),
        unmatched_final_rms_sources=sum(not row['command_diagnostic']['correction_rms_matched'] for row in cut_sources),
        zero_channel_counts={name: {channel: sum(row['command_diagnostic']['methods'][name]['zero_'+channel] for row in cut_sources)
                                   for channel in ('xyz','gripper')} for name in CORRECTIONS},
        aliases_of_a0={name: sum(row['command_diagnostic']['methods'][name]['raw_alias_of_a0'] for row in cut_sources) for name in CORRECTIONS},
        matching_group_flags={group: {flag: sum((row.get('matching_groups') or {}).get(group, {}).get(flag) is True for row in cut_sources)
                                     for flag in ('zero_group','shrunk')} for group in ('xyz','gripper')})
    return dict(schema=SCHEMA, status='complete', descriptive_only=True, new_scientific_acceptance_rules=False,
        simulator_attempts=0, optimizer_updates=0, model_calls=0, independent_validation_success=False,
        stage=stage, bank_version=bank_version, source_denominator=100, command_q_denominator=95,
        q_missing_no_cut_sources=5, cross_round_pairing_claim=False,
        logical_outcomes_per_arm=400, physical_branches=len(branches),
        config_sha256=digest, config_content_sha256=_canonical(config), protocol_sha256=protocol,
        selected_training=result['selected_training'], primary_statistics=primary, statistics=stats,
        per_repeat={str(repeat): dict(source_denominator=100,
            success_counts=dict(zip(METHODS, values[:, :, repeat].sum(0).tolist())),
            success_rates=dict(zip(METHODS, values[:, :, repeat].mean(0).tolist()))) for repeat in range(4)},
        cost=cost_summary, final_raw_amplitude=amplitude, quality=quality, q_vs_actual=q_vs_actual,
        per_source=sources, command_rows=commands, branch_cost_rows=branches, flow_updates=gradients,
        inputs=[dict(path=path, sha256=sha) for path, sha in sorted(used.items())],
        limitations=[
            'Only the new five arms are paired here. No historical sixth arm or old/new suffix equivalence is inferred.',
            'Four repeats remain dependent measurements within each source; no-cut sources retain their common outcome.',
            'Q is scored on C(raw)=clip(raw), while the raw plan is executed. Commands with equal proxy may differ physically.',
            'Final ten-command amplitude does not bound intermediate flow queries. Matching can expand native directions.',
            'Actual prefix amplitude uses each branch executed prefix length; it does not assert identical termination times.',
            'Q association is descriptive on generated candidates and development sources; it proves neither calibration nor causal score quality.',
            'No new bootstrap, winner, acceptance threshold, retraining rule, or independent-validation claim is introduced.',
            'Primary audit performed full trajectory/seed/physics verification; this supplement rehashes only consumed artifacts.',
        ])

def write_outputs(result, output, *, root=ROOT):
    output = _inside(output, Path(root)/'policy5_cost_diagnostics')
    output.mkdir(parents=True, exist_ok=False)
    def dump(name, value):
        with (output/name).open('x') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    dump('result.json', result)
    for name, rows in (('commands.csv', result['command_rows']), ('branch_costs.csv', result['branch_cost_rows'])):
        columns = sorted({key for row in rows for key in row})
        with (output/name).open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
            writer.writerows({key: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for key, v in row.items()} for row in rows)
    text = ['# 第二轮 A4000 Policy5 完整开发集补充诊断', '',
        f"固定 {result['source_denominator']} 源、每臂 {result['logical_outcomes_per_arm']} 个配对结局；",
        f"其中 {result['command_q_denominator']} 源有干预命令，{result['physical_branches']} 个真实分支。无 cut 共同结局保留在分母。", '',
        '这是完整主审计之后的描述性补充。原主审计的 CI 与比较规则原样保存在 result.json 的 primary_statistics；本模块不新增接受标准。', '',
        '| 比较 | 平均增益 pp | 救回 | 损害 | 正/负/零源 |', '|---|---:|---:|---:|---:|']
    for name, row in result['statistics']['overall']['comparisons'].items():
        text.append(f"| {name} | {row['gain_pp']:.2f} | {row['rescues']} | {row['harms']} | {row['positive_sources']}/{row['negative_sources']}/{row['zero_sources']} |")
    text += ['', '逐任务完整/报警条件比较见 statistics.per_task；成本见 cost；最终 raw 幅度见 final_raw_amplitude；别名/零组见 quality；Q 与真实源均值增益关系见 q_vs_actual。', '',
        '成本分量可能重叠，累加 worker 秒不等于波次 elapsed。显存峰值不能相加。未记录的字段保留缺失。', '',
        '最终局部 raw 幅度不限制 flow 中间查询；同幅投影可以放大原生方向，不能将 matched 当作原生 QGF。只比较当前五臂内部配对，不构造旧数据第六臂。', '',
        '开发集结果与 Q 相关性都不能称为独立验证成功。完整输入 SHA、逐源记录和限制见 result.json。', '']
    with (output/'report.md').open('x') as stream:
        stream.write('\n'.join(text))
    dump('complete.json', dict(status='complete', role=SCHEMA, simulator_attempts=0, optimizer_updates=0,
         files={path.name: _hash(path) for path in sorted(output.iterdir()) if path.is_file()}))

def self_test():
    """Bounded synthetic CPU checks, with no experiment input access."""
    class Checks(unittest.TestCase):
        def fixture(self):
            ids=[f'synthetic_{i}' for i in range(100)]
            config={'main_collection':{'banks':{'v':{'kind':'policy5','stage':STAGE,'episode_ids':ids}}},
                    'policy_deployment':{'selected_training':{'synthetic':True}}}
            result=dict(status='passed',planned_slots=100,technical_missing=0,source_capture_attempts_added=0,
                new_attempts=1995,bank_version='v',stage=STAGE,config_content_sha256=_canonical(config),
                selected_training=config['policy_deployment']['selected_training'],attempt_numbers=list(range(1,1996)),
                per_source=[dict(episode_id=k,task='synthetic',no_cut=i>=95,actual_cut=None if i>=95 else 5,
                    paired_outcomes={m:[False]*4 for m in METHODS},success_counts={m:0 for m in METHODS}) for i,k in enumerate(ids)])
            return config,result
        def test_full100_gate(self):
            c,r=self.fixture(); self.assertEqual(validate_gate(c,r,'v').shape,(100,5,4))
        def test_old_stage_rejected(self):
            c,r=self.fixture(); c['main_collection']['banks']['v']['stage']='round1_development_policy'
            r.update(stage='round1_development_policy',config_content_sha256=_canonical(c))
            with self.assertRaises(ValueError): validate_gate(c,r,'v')
        def test_partial_rejected(self):
            c,r=self.fixture(); r['per_source'].pop()
            with self.assertRaises(ValueError): validate_gate(c,r,'v')
        def test_no_cut_cannot_be_imputed_by_method(self):
            c,r=self.fixture(); r['per_source'][-1]['paired_outcomes']['post'][0]=True
            with self.assertRaises(ValueError): validate_gate(c,r,'v')
        def test_shared_scientific_functions_identical(self):
            for name in ('command_diagnostics','paired_summary','association','describe'):
                self.assertIs(globals()[name],getattr(calculations,name))
        def test_suffix_not_independent_sources(self):
            x=np.zeros((100,5,4),bool); x[0,2,:]=True
            d=paired_summary(x)['comparisons']['velocity_minus_alarm_replan10']
            self.assertEqual((d['positive_sources'],d['rescues'],d['gain_pp']),(1,4,1.0))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    if not result.wasSuccessful(): raise SystemExit(1)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--audit', type=Path, help='Existing sealed policy5 audit directory; all 100 sources required')
    parser.add_argument('--freeze', type=Path, help='Defaults to config directory/freeze.json')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, help='New directory under ROOT/policy5_cost_diagnostics')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        if any((args.config,args.audit,args.freeze,args.output)):
            parser.error('--self-test cannot open experiment inputs or outputs')
        self_test(); return
    if not all((args.config,args.audit,args.output)):
        parser.error('--config, --audit and --output are required')
    if args.output.exists():
        raise FileExistsError('Supplement output must be a new directory')
    result = run(args.config,args.audit,freeze_path=args.freeze,root=args.root)
    write_outputs(result,args.output,root=args.root)
    print(json.dumps(dict(status=result['status'],sources=result['source_denominator'],
        physical_branches=result['physical_branches'],output=str(args.output),descriptive_only=True)))

if __name__ == '__main__':
    main()
