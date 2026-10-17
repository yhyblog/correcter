"""Saved scalar analysis only. No torch/model/hardware/environment imports.

The existing success bootstrap is reused. At most one new, cached fixed-seed
cost bootstrap is produced; subsequent formatting changes reuse that cache.
"""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[2]
WS = BASE.parents[2]
DEADLINE = BASE / 'deadline_20260924'
MAIN = BASE / 'results/A/A_D24_MAIN_ONCE_V1'
TASK = 'A_D24_OURS_E5_REPORT_V1'
UTC = datetime.now(timezone.utc).isoformat()
METRICS = ['policy_calls', 'sampling_calls', 'flow_calls', 'steps', 'interventions',
           'elapsed_seconds', 'elapsed_control_seconds', 'inference_seconds',
           'environment_seconds', 'reset_seconds']
TIMES = [k for k in METRICS if k.endswith('_seconds')]
COUNTERS = ['D_forward', 'G0_forward', 'Q_ensemble_forward', 'action_gradients',
            'contexts', 'flow', 'interventions', 'sampling']
ORDER = ['N_H10', 'R_H10', 'Post_H10', 'Velocity_H10'] + [
    m + '_H' + str(h) for h in [20, 30, 40, 50] for m in ['N', 'Post', 'Velocity']]


def read_json(p):
    return json.loads(p.read_text())


def save_json(name, data):
    p = ROOT / name
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def csv_rows(p):
    with p.open(newline='') as f:
        return list(csv.DictReader(f))


def save_csv(name, rows):
    assert rows
    with (ROOT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def boolean(v):
    if v is True or v == 'True':
        return True
    if v is False or v == 'False':
        return False
    raise ValueError('Missing or invalid scientific outcome: ' + repr(v))


def number(v):
    if v is None or v == '':
        return None
    x = float(v)
    assert math.isfinite(x)
    return x


def field_stats(rows, name):
    all_values = [number(r.get(name)) for r in rows]
    success_values = [number(r.get(name)) for r in rows if r['success']]
    all_values = [v for v in all_values if v is not None]
    success_values = [v for v in success_values if v is not None]
    n = len(rows); s = sum(r['success'] for r in rows)
    # Full-denominator means/amortized values are not imputed if coverage is incomplete.
    total = math.fsum(all_values) if all_values else None
    conditional_total = math.fsum(success_values) if success_values else None
    return dict(recorded_all=len(all_values), recorded_success=len(success_values),
        denominator_all=n, denominator_success=s,
        sum_all=total, sum_success_only=conditional_total,
        mean_all=total / n if len(all_values) == n and n else None,
        mean_success_only=conditional_total / s if len(success_values) == s and s else None,
        amortized_per_success=total / s if len(all_values) == n and s else None,
        min_observed=min(all_values) if all_values else None,
        max_observed=max(all_values) if all_values else None,
        null_reason=None if len(all_values) == n else 'field not recorded for all episodes; no imputation')


# Count parameter tensors from the one-time CPU state_dict inspection, not models.
shapes = read_json(ROOT / 'SMALL_MODULE_SHAPES.json')
members = []
for entry in shapes['members']:
    weights = [t for t in entry['tensors'] if t['key'].split('.')[-1].startswith(('weight', 'bias'))]
    buffers = [t for t in entry['tensors'] if t not in weights]
    count = sum(t['elements'] for t in weights)
    assert count == entry['expected_parameters']
    if entry['component'] in ['D', 'G0']:
        assert {t['key'] for t in buffers} == {'mean', 'std', 'delta_scale'}
    else:
        assert {t['key'] for t in buffers} == {'norm_mean', 'norm_std', 'residual_scale',
            'visual_center', 'visual_basis', 'visual_scale', 'language_center',
            'language_basis', 'language_scale'}
    updated = sum(t['elements'] for t in weights if t['key'].startswith(('residual.', 'advantage.')))
    if entry['component'] == 'Q':
        assert updated == 2529
    members.append(dict(component=entry['component'], member=entry['member'], path=entry['path'],
        network_parameters=count, network_tensor_bytes=sum(t['bytes'] for t in weights),
        buffers_elements=sum(t['elements'] for t in buffers),
        buffers_bytes=sum(t['bytes'] for t in buffers), buffers=buffers,
        checkpoint_file_bytes=entry['bytes'], tensor_dtype=sorted({t['dtype'] for t in entry['tensors']}),
        historical_A4000_updated_parameters=updated if entry['component'] == 'Q' else 0,
        E5_updates=0, inference_trainable_parameters=0))
components = {}
for component in ['D', 'G0', 'Q']:
    subset = [m for m in members if m['component'] == component]
    components[component] = dict(members=len(subset), member_parameters=subset[0]['network_parameters'],
        ensemble_parameters=sum(m['network_parameters'] for m in subset),
        buffer_elements_loaded_copies=sum(m['buffers_elements'] for m in subset),
        buffer_bytes_loaded_copies=sum(m['buffers_bytes'] for m in subset),
        network_tensor_bytes=sum(m['network_tensor_bytes'] for m in subset),
        historical_A4000_updated_parameters=sum(m['historical_A4000_updated_parameters'] for m in subset))
parameter_counts = dict(schema='corrector_e5_parameters_v1', utc=UTC,
    counting_basis='Saved module parameter tensor shapes; independent members counted once, no VLA encoder duplication.',
    sources=[str(WS / 'Corrector/docs/PARAMETER_EFFICIENT_CORRECTOR_PLAN_20260919.md'),
             str(WS / 'Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md'), str(ROOT / 'SMALL_MODULE_SHAPES.json')],
    components=components, members=members,
    total_added_unique_network_parameters=sum(m['network_parameters'] for m in members),
    total_added_network_tensor_bytes=sum(m['network_tensor_bytes'] for m in members),
    buffer_elements_loaded_copies=sum(m['buffers_elements'] for m in members),
    buffer_bytes_loaded_copies=sum(m['buffers_bytes'] for m in members),
    buffer_count_note='Non-trainable preprocessing buffers; actual per-member serialized copies counted, not claimed unique constants or peak RAM.',
    shared_existing_encoder=dict(added_network_parameters=0, definition='Reuse the same frozen pi05 image/language backbone; its computation is not free.'),
    shared_existing_projection=shapes['shared_projection'], base=shapes['base'],
    historical_A4000_updated_parameters=10116,
    historical_training_note='Only inherited Q residual/advantage updated in A4000 (2529/member); D/G0 are previously trained frozen modules. This is not all historical training parameters or training FLOPs.',
    E5_new_updated_parameters=0, D24_main_updated_parameters=0,
    Smol_X=dict(unique_runtime_base_parameters=None, adapted_total_added_parameters=None,
        reason='Out of this pi0516-cell delivery; no multi-GB base load or extrapolation to different bridges.'),
    limitations=['Serialized VLA weight elements are not a verified unique runtime parameter count.',
                'Network tensor/buffer byte totals are not peak device memory or optimizer memory.',
                '28,232 Q parameters are not the full D/G0/Q deployment overhead.'])
assert parameter_counts['total_added_unique_network_parameters'] == 11912530
save_json('PARAMETER_COUNTS.json', parameter_counts)

accepted = read_json(DEADLINE / 'MAIN_FINAL_STATISTICS.json')
accepted_csv = {r['cell']: r for r in csv_rows(DEADLINE / 'MAIN_FINAL_CELLS_WITH_COSTS.csv')}
paired = csv_rows(DEADLINE / 'MAIN_FINAL_PAIRED_COMPARISONS.csv')
resources = read_json(MAIN / 'FINAL_RESOURCE_SUMMARY.json')
grouped = defaultdict(list)
main_scalar_rows = csv_rows(MAIN / 'FINAL_EPISODES.csv')
for r in main_scalar_rows:
    r['success'] = boolean(r['success'])
    assert boolean(r['terminal']) and not r['technical_failure']
    grouped[r['cell']].append(r)
n_paths = sorted((DEADLINE / 'A/runs').glob('N_H*_*/RESULT.json'))
assert len(n_paths) == 250
for p in n_paths:
    result = read_json(p)
    assert result['technical_failures'] == 0
    for raw in result['episodes']:
        r = dict(raw, cell='N_H' + str(raw['H']), result_path=str(p))
        r['success'] = boolean(r['success'])
        assert r['terminal'] and not r['technical_failure']
        grouped[r['cell']].append(r)
assert set(grouped) == set(ORDER)
assert sum(map(len, grouped.values())) == 8000
common_keys = sorted((r['task'], r['source_id']) for r in grouped['N_H10'])
assert len(set(common_keys)) == 500
assert set(Counter(t for t, s in common_keys).values()) == {10}
assert len({t for t, s in common_keys}) == 50
checks = []
stats = {}
ordered_rows = {}
for cell in ORDER:
    rows = sorted(grouped[cell], key=lambda r: (r['task'], r['source_id']))
    assert [(r['task'], r['source_id']) for r in rows] == common_keys
    assert len(rows) == accepted['cells'][cell]['episodes'] == 500
    assert sum(r['success'] for r in rows) == accepted['cells'][cell]['successes']
    ordered_rows[cell] = rows
    metrics = {name: field_stats(rows, name) for name in METRICS}
    for name, values in metrics.items():
        old = accepted['cells'][cell]['saved_field_stats'][name]
        assert values['recorded_all'] == old['all_episodes']['recorded_episodes']
        assert values['recorded_success'] == old['success_episodes_only']['recorded_episodes']
        for side, part in [('all', 'all_episodes'), ('success_only', 'success_episodes_only')]:
            for key in ['sum', 'mean']:
                actual = values[key + '_' + side]; previous = old[part][key]
                assert (actual is None and previous is None) or (
                    actual is not None and previous is not None and abs(actual - previous) < 1e-5)
    assert all(number(r['flow_calls']) == 10 * number(r['policy_calls']) for r in rows)
    if not cell.startswith('N_'):
        assert all(number(r['sampling_calls']) == number(r['policy_calls']) for r in rows)
        assert all(number(r['interventions']) in [0, 1] for r in rows)
    else:
        assert metrics['sampling_calls']['recorded_all'] == 0
    stats[cell] = dict(method=accepted['cells'][cell]['method'], H=accepted['cells'][cell]['H'],
        tasks=50, valid_episodes=500, successes=sum(r['success'] for r in rows), technical_failures=0,
        success_rate_pct=accepted['cells'][cell]['success_rate_pct'],
        success_ci95_pct_reused=accepted['cells'][cell]['success_rate_ci95_pct'], metrics=metrics)
    checks.append(dict(cell=cell, matched_saved_outcomes=True, matched_saved_field_summaries=True,
                       explicit_sampling_missing_preserved=cell.startswith('N_'),
                       source_pairs=500, saved_complete_flows_equal_10x_policy=True))

# Exactly one optional cost-only bootstrap; never recompute saved success intervals.
calls = np.array([[number(r['policy_calls']) for r in ordered_rows[c]] for c in ORDER], dtype=np.float64)
success = np.array([[r['success'] for r in ordered_rows[c]] for c in ORDER], dtype=np.int64)
fingerprint = hashlib.sha256(json.dumps(dict(cells=ORDER, keys=common_keys,
    calls=calls.tolist(), success=success.tolist()), sort_keys=True).encode()).hexdigest()
boot_path = ROOT / 'COST_BOOTSTRAP.json'
if boot_path.exists():
    bootstrap = read_json(boot_path)
    assert bootstrap['scalar_input_sha256'] == fingerprint
    assert bootstrap['seed'] == 20260922 and bootstrap['replicates'] == 2000
else:
    rng = np.random.default_rng(20260922)
    draws = rng.integers(0, 10, size=(2000, 50, 10)) + np.arange(50)[None, :, None] * 10
    amortized = np.stack([calls[i][draws].sum(axis=(1, 2)) / success[i][draws].sum(axis=(1, 2))
                          for i in range(len(ORDER))])
    bootstrap = dict(utc=UTC, seed=20260922, replicates=2000, generator='numpy.default_rng',
        scalar_input_sha256=fingerprint, purpose='New policy-call amortization/ratio intervals only; existing success bootstrap not rerun.',
        method='Fixed50 equal-weight tasks; resample10 sources/task with replacement, same source draws in all16cells; ratio of total calls to total successes.',
        interval='Pointwise 2.5/97.5 percentile; unadjusted, conditional on fixed tasks/empirical sources, not training-seed uncertainty.',
        cells={c: dict(policy_calls_amortized_ci95=np.percentile(amortized[i], [2.5, 97.5]).tolist())
               for i, c in enumerate(ORDER)}, comparisons={})
    for pair in paired:
        a = ORDER.index(pair['A']); b = ORDER.index(pair['B'])
        bootstrap['comparisons'][pair['comparison']] = dict(
            amortized_policy_ratio_ci95=np.percentile(amortized[a] / amortized[b], [2.5, 97.5]).tolist())
    with boot_path.open('x') as f:
        json.dump(bootstrap, f, indent=2, allow_nan=False); f.write('\n')

# Existing plan timers were preserved in job JSON even though not flattened into
# FINAL_EPISODES.csv. Extract only their scalars, not observations/noise/trajectories.
entry_path = ROOT / 'ENTRY_TIMING_SUMMARY.json'
entry_scopes = {
    'natural_plan': 'propose() wall: preprocessing/raw50 generation/decoding; no D/G0 context',
    'intervention_entry': 'R: propose timer; Post/Velocity: intervene wall incl base/guided/Q/projection and local correction artifact write; excludes monitor/context before entry',
    'intervention_base': 'Nested base propose timer; overlaps intervention entry, do not add',
    'intervention_guided': 'Nested guided propose timer incl its action gradients; overlaps entry, do not add',
    'objective_forward': 'Sum of FrozenObjective.__call__ host timers inside one intervention: CPU transfer/validation/Q ensemble/value conversion; excludes backward and objective construction; overlaps entry',
}
if entry_path.exists():
    entry_summary = read_json(entry_path)
else:
    paths = sorted({r['result_path'] for r in main_scalar_rows})
    assert len(paths) == 550
    observed = defaultdict(list); expected = Counter(); plan_totals = defaultdict(float)
    for path in paths:
        job = read_json(Path(path)); cell = job['method'] + '_H' + str(job['H'])
        for episode in job['episodes']:
            for plan in episode['plans']:
                kind = plan['kind']; payload = plan['stats']
                metric = 'natural_plan' if kind == 'natural' else 'intervention_entry'
                expected[cell, metric] += 1
                if payload.get('seconds') is not None:
                    value = number(payload['seconds']); observed[cell, metric].append(value)
                    plan_totals[cell] += value
                if kind == 'intervention':
                    for key, stat_key in [('intervention_base', 'base'), ('intervention_guided', 'guided')]:
                        if (stat_key == 'base' and job['method'] in ['Post', 'Velocity']) or (stat_key == 'guided' and job['method'] == 'Velocity'):
                            expected[cell, key] += 1
                            value = (payload.get(stat_key) or {}).get('seconds')
                            if value is not None:
                                observed[cell, key].append(number(value))
                    if job['method'] in ['Post', 'Velocity']:
                        expected[cell, 'objective_forward'] += 1
                        value = (payload.get('objective') or {}).get('critic_forward_seconds')
                        if value is not None:
                            observed[cell, 'objective_forward'].append(number(value))
    rows = []
    for cell in ORDER:
        for metric, scope in entry_scopes.items():
            values = observed[cell, metric]; denominator = expected[cell, metric]
            total = math.fsum(values) if values else None
            rows.append(dict(cell=cell, metric=metric, scope=scope,
                expected_entries=denominator if not cell.startswith('N_') else None,
                recorded_entries=len(values), sum_seconds=total,
                mean_seconds=total/len(values) if values else None,
                median_seconds=float(np.median(values)) if values else None,
                p95_seconds=float(np.percentile(values, 95)) if values else None,
                min_seconds=min(values) if values else None, max_seconds=max(values) if values else None,
                null_reason=None if values else ('N has no saved per-plan timers' if cell.startswith('N_') else 'not applicable: no such nested timer/call in this method'),
                warmed_subset=False, interval_estimation=False))
    for cell, total in plan_totals.items():
        assert abs(total-stats[cell]['metrics']['inference_seconds']['sum_all']) < 1e-5
    entry_summary = dict(utc=UTC, status='SAVED_SCALARS_ONLY', job_files=len(paths),
        input_file_bytes=sum(Path(p).stat().st_size for p in paths), job_paths=paths, rows=rows,
        plan_time_sums_match_episode_inference=True, scope='No new timer/model/environment; no subtractive net-cost inference',
        limitations='Observed entries under concurrent jobs, unfiltered warm/cold and history-dependent trigger subsets; descriptive percentiles, not isolated GPU latency/CI.')
    save_json('ENTRY_TIMING_SUMMARY.json', entry_summary)
save_csv('ENTRY_TIMING_TABLE.csv', entry_summary['rows'])

paper = []; time_rows = []; call_rows = []
for cell in ORDER:
    s = stats[cell]; metrics = s['metrics']
    ci = bootstrap['cells'][cell]['policy_calls_amortized_ci95']
    s['policy_calls_amortized_ci95'] = ci
    row = dict(cell=cell, method=s['method'], H=s['H'], tasks=50, attempts=500, valid_episodes=500,
        successes=s['successes'], technical_failures=0, success_rate_pct=s['success_rate_pct'],
        success_CI_low_pct=s['success_ci95_pct_reused'][0], success_CI_high_pct=s['success_ci95_pct_reused'][1],
        policy_definition_id='N_sample_actions_entered_all_completed' if s['method'] == 'N' else 'main_complete_sampling_including_guided',
        complete_sampling_explicit_null_reason='not separately recorded; policy_calls retains its source-defined meaning' if s['method'] == 'N' else None)
    for field in ['policy_calls', 'sampling_calls', 'flow_calls', 'steps', 'interventions']:
        for k in ['sum_all', 'mean_all', 'sum_success_only', 'mean_success_only',
                  'amortized_per_success', 'recorded_all', 'recorded_success']:
            row[field + '_' + k] = metrics[field][k]
    row.update(policy_amortized_CI_low=ci[0], policy_amortized_CI_high=ci[1])
    paper.append(row)
    for field in TIMES:
        if field == 'inference_seconds':
            scope = 'N: preprocessing, raw50 generation and decoding; no correction' if s['method'] == 'N' else 'Main: summed plan generation/correction timers, includes Q/projection work there; excludes most context/D/G0'
        elif field == 'environment_seconds':
            scope = 'N: reset plus native steps/observation formatting' if s['method'] == 'N' else 'Main: native steps/observation formatting; reset separately recorded'
        elif field == 'elapsed_seconds':
            scope = 'Saved per-episode host wall time, excludes resident model load/job environment construction; sum is not makespan/GPU time'
        elif field == 'elapsed_control_seconds':
            scope = 'Main controller loop wall after reset; N unrecorded'
        else:
            scope = 'Main reset call timer; N has no separate field'
        time_rows.append(dict(cell=cell, metric=field, scope=scope, **metrics[field],
            entry_timing_reference='ENTRY_TIMING_TABLE.csv; separate entry denominators/scopes'))
    counter_row = dict(cell=cell, episodes=500, interventions_saved=metrics['interventions']['sum_all'])
    for name in COUNTERS:
        f = field_stats(ordered_rows[cell], 'counter_' + name)
        counter_row[name + '_sum'] = f['sum_all']
        counter_row[name + '_recorded_episodes'] = f['recorded_all']
        counter_row[name + '_mean_all'] = f['mean_all']
        if s['method'] != 'N':
            assert f['sum_all'] == resources['per_cell'][cell]['episode_counters'][name]
    counter_row['Q_member_forwards_derived_4x_ensemble'] = (
        4 * counter_row['Q_ensemble_forward_sum'] if counter_row['Q_ensemble_forward_sum'] is not None else None)
    counter_row['null_reason'] = 'No corresponding per-episode counters in N; no zero-fill' if s['method'] == 'N' else None
    call_rows.append(counter_row)

cost_pairs = []
for p in paired:
    a = stats[p['A']]['metrics']['policy_calls']; b = stats[p['B']]['metrics']['policy_calls']
    ci = bootstrap['comparisons'][p['comparison']]['amortized_policy_ratio_ci95']
    cost_pairs.append(dict(comparison=p['comparison'], comparison_class=p['comparison_class'], A=p['A'], B=p['B'],
        policy_mean_all_ratio_A_over_B=a['mean_all'] / b['mean_all'],
        amortized_policy_ratio_A_over_B=a['amortized_per_success'] / b['amortized_per_success'],
        amortized_ratio_CI_low=ci[0], amortized_ratio_CI_high=ci[1],
        success_delta_pp_reused=float(p['delta_pp']), success_delta_CI_low_reused=float(p['CI_low_pp']),
        success_delta_CI_high_reused=float(p['CI_high_pp']), rescued_reused=int(p['rescued']), harmed_reused=int(p['harmed']),
        interpretation='Descriptive realized cost on paired sources; not equal-work speed or noninferiority'))
save_csv('PAPER_COST_TABLE.csv', paper)
save_csv('TIMING_TABLE.csv', time_rows)
save_csv('CALL_ACCOUNTING.csv', call_rows)
save_csv('COST_COMPARISONS.csv', cost_pairs)
save_json('SCALAR_COST_SUMMARY.json', dict(utc=UTC, cells=stats,
    aggregation='Uniform task then uniform source; 50x10 balanced. Amortized = macro mean calls / macro SR = total calls/total successes, not mean of task-specific ratios.',
    success_conditioning='Conditional on success under the uniform-task design; different methods select different successful sources/tasks.',
    bootstrap=str(boot_path), saved_success_inference=str(DEADLINE / 'MAIN_FINAL_STATISTICS.json')))

definitions = dict(
    policy_calls=dict(N='Counter increment immediately before model.sample_actions; every sample completed in these zero-technical-failure episodes. Produces raw50 using10 flow steps, retains firstH.',
        main='Alias of complete sampling_calls: natural1, intervention R1/Post1/Velocity2 (base1+guided1); includes natural replanning.',
        explicit_N_sampling_calls=None, reason='N did not save that field; no borrowing or filling even though code defines policy_calls sampling semantics.'),
    flow_calls=dict(N='Increment10 following successful complete sample; no per-tau timer.',
        main='Episode field10*sampling_calls; separately saved hook counter_flow matches in all5500 episodes.',
        limit='Flow count is action-expert vector-field calls, not all encoders/Q/D/G0 or equal computation across methods.'),
    per_intervention=dict(R=dict(complete_sampling=1, flow=10, Q_ensemble=0, action_gradients=0),
        Post=dict(complete_sampling=1, flow=10, Q_ensemble=3, Q_members=12, action_gradients=1),
        Velocity=dict(complete_sampling=2, flow=20, Q_ensemble=8, Q_members=32, action_gradients=3)),
    Q_note='Q counts include objective evaluations logged by the executed entry, not just gradients; frozen weights, no optimizer/backward weight update.',
    monitor='Per mature context: two D members plus two G0 members; counter_D/G0 counts individual networks, Q counter counts a four-member ensemble.',
    amortization='All terminal attempts including scientifically unsuccessful outcomes contribute to numerator; successes alone in denominator.',
    timing_missing=['N per-entry mean/median/P95', 'isolated D/G0/context time', 'Q backward and net correction incremental time', 'GPU kernel seconds/energy'],
    saved_entry_timing='Main job JSON plans[].stats.seconds plus nested base/guided.seconds and objective.critic_forward_seconds; see ENTRY_TIMING_TABLE.csv',
    task_weighting='50 fixed tasks each10 fixed test sources, same sources across16cells; no training-model/threshold selection.',
    training_coverage=accepted['training_coverage_description']['training_tasks'])
save_json('FIELD_DEFINITIONS.json', definitions)
save_json('CPU_CHECKS.json', dict(utc=UTC, status='PASS', scope='New scalar aggregation and small parameter counts only',
    small_member_counts_match_docs=True, checked_members=8, expected_added_parameters=11912530,
    cells=checks, total_saved_episodes=8000, paired_sources_per_cell=500,
    saved_entry_plan_time_sums_match_episode_inference=entry_summary['plan_time_sums_match_episode_inference'],
    old_success_bootstrap_reexecuted=False, new_cost_bootstrap_seed=20260922,
    new_cost_bootstrap_replicates=2000, N_missing_sampling_imputed=False,
    model_instances=0, model_forwards=0, GPU_calls=0, holder_queries_or_changes=0))

# A small input index, not a new whole-tree/hash audit.
small_sources = [DEADLINE / 'MAIN_FINAL_CELLS_WITH_COSTS.csv', DEADLINE / 'MAIN_FINAL_STATISTICS.json',
    DEADLINE / 'MAIN_FINAL_PAIRED_COMPARISONS.csv', MAIN / 'FINAL_EPISODES.csv', MAIN / 'FINAL_RESOURCE_SUMMARY.json',
    WS / 'Corrector/docs/PARAMETER_EFFICIENT_CORRECTOR_PLAN_20260919.md',
    WS / 'Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md',
    DEADLINE / 'E1_COMPLETED_ANALYSIS_20260922.md', DEADLINE / 'E6_COMPLETED_ANALYSIS_20260922.md']
save_json('INPUT_INDEX.json', dict(utc=UTC, small_scalar_and_document_inputs=[dict(path=str(p),
    bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in small_sources],
    N_scalar_result_paths=[str(p) for p in n_paths], N_result_files=250,
    main_plan_timer_scalar_inputs='ENTRY_TIMING_SUMMARY.json contains550 job paths and127,142,692 logical input bytes; only saved timer scalars extracted.',
    weight_access='8 necessary small state_dicts once on CPU (50,574,744 file bytes); base/projection headers only; no new weight hash',
    prior_source_hashes='MODULE_INPUTS contains existing hashes as provenance, not newly rechecked hashes'))


def f(x, precision=3):
    return 'NR' if x is None else format(x, '.' + str(precision) + 'f')


def md_table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---']*len(headers)) + ' |'] +
        ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows])


paper_table = md_table(['格', '有效/成功/技术失败', '成功率% [95%CI]', '调用/尝试', '调用/成功条件', '调用/成功摊销 [95%CI]', '显式采样总数', 'flow总数'], [
    [r['cell'], '500/' + str(r['successes']) + '/0',
     f(r['success_rate_pct'], 1) + ' [' + f(r['success_CI_low_pct'], 1) + ', ' + f(r['success_CI_high_pct'], 1) + ']',
     f(r['policy_calls_mean_all']), f(r['policy_calls_mean_success_only']),
     f(r['policy_calls_amortized_per_success']) + ' [' + f(r['policy_amortized_CI_low']) + ', ' + f(r['policy_amortized_CI_high']) + ']',
     'NR' if r['sampling_calls_sum_all'] is None else str(int(r['sampling_calls_sum_all'])), str(int(r['flow_calls_sum_all']))] for r in paper])
time_table = md_table(['格', 'episode墙钟/尝试(s)', '生成/纠偏计时/尝试(s)', '生成/纠偏计时/成功条件(s)',
                       '生成/纠偏计时/成功摊销(s)', '该计时已保存范围(min–max,s)'], [
    [c, f(stats[c]['metrics']['elapsed_seconds']['mean_all']), f(stats[c]['metrics']['inference_seconds']['mean_all']),
     f(stats[c]['metrics']['inference_seconds']['mean_success_only']), f(stats[c]['metrics']['inference_seconds']['amortized_per_success']),
     f(stats[c]['metrics']['inference_seconds']['min_observed']) + '–' + f(stats[c]['metrics']['inference_seconds']['max_observed'])] for c in ORDER])
entry_table = md_table(['格', '干预入口已记录/实际入口', '均值(s)', '中位数(s)', 'P95(s)', '最小–最大(s)'], [
    [r['cell'], str(r['recorded_entries']) + '/' + str(r['expected_entries']), f(r['mean_seconds']),
     f(r['median_seconds']), f(r['p95_seconds']), f(r['min_seconds']) + '–' + f(r['max_seconds'])]
    for r in entry_summary['rows'] if r['metric'] == 'intervention_entry' and not r['cell'].startswith('N_')])
param_table = md_table(['组件', '成员数', '每成员网络参数', 'ensemble网络参数', 'buffer元素(按加载副本)'], [
    [k, v['members'], format(v['member_parameters'], ','), format(v['ensemble_parameters'], ','),
     format(v['buffer_elements_loaded_copies'], ',')] for k, v in components.items()])
headline_pairs = [p for p in cost_pairs if p['comparison'] in ['R_H10-N_H10', 'Post_H10-N_H10', 'Velocity_H10-N_H10', 'Post_H10-R_H10', 'Velocity_H10-R_H10', 'Post_H30-N_H10']]
pair_table = md_table(['比较 A−B', '成功差pp [既有95%CI]', '救回/损害', '摊销调用A/B [新95%CI]'], [
    [p['comparison'], f(p['success_delta_pp_reused'], 1) + ' [' + f(p['success_delta_CI_low_reused'], 1) + ', ' + f(p['success_delta_CI_high_reused'], 1) + ']',
     str(p['rescued_reused']) + '/' + str(p['harmed_reused']),
     f(p['amortized_policy_ratio_A_over_B']) + ' [' + f(p['amortized_ratio_CI_low']) + ', ' + f(p['amortized_ratio_CI_high']) + ']'] for p in headline_pairs])

p10 = stats['Post_H10']['metrics']['policy_calls']; n10 = stats['N_H10']['metrics']['policy_calls']
p30 = stats['Post_H30']['metrics']['policy_calls']
report = f'''本任务已完成 π0.5-MT50 的16格 E5 参数与成本整理，复用8,000条已验收 episode（50个固定任务、各10个固定 test 初态）。本轮新增 episode、模型前向、GPU/硬件查询、训练、占卡操作均为0；未重启任何队列，未改旧结果。E6、E3、GAF保持已结案状态，B/C无需等待本报告。

可用于论文的描述：在冻结 π0.5-MT50 SFT030000 上，四成员纠偏 Q 共28,232个网络参数；计入双成员D和双成员G0后，新增网络总量为11,912,530。H10下 Post 成功率为69.0%，N为61.6%；既有同源配对差为+7.4pp，95%区间[4.4,10.4]，救回64、损害27。Post每次尝试平均完整采样语义的 policy 调用为{f(p10['mean_all'])}，计入失败轨迹后的每成功摊销调用为{f(p10['amortized_per_success'])}；N对应为{f(n10['mean_all'])}和{f(n10['amortized_per_success'])}。这些数值描述固定测试源上的实际调用成本，不构成整个系统加速或参数最优证明。D/G0/Q沿用历史五任务训练覆盖，不能写成新完成MT50纠偏器训练。

**参数与存储范围**

{param_table}

网络参数按独立成员各计一次，不把四成员Q写成单成员。D/G0合计11,884,298；全部新增网络11,912,530。8个小state_dict共50,574,744文件字节，仅CPU读取一次，并与既有参数文档逐成员计数相符。所有网络tensor为float32，共{parameter_counts['total_added_network_tensor_bytes']:,}数据字节；各成员预处理buffer副本合计{parameter_counts['buffer_elements_loaded_copies']:,}元素/{parameter_counts['buffer_bytes_loaded_copies']:,}字节。buffer不是可训练参数，副本合计也不声称是唯一常量或峰值内存。

同一π0.5视觉/语言编码器复用，额外编码器网络参数为0，但编码计算仍有开销。既有共享固定投影为2048×256 float32，524,288元素/2,097,152数据字节，单列一次，未并入新增可训练权重。Q的PCA/归一化buffer已计在上表。VLA文件头记录813个weight/bias tensor、4,143,404,816存储元素；含词嵌入及两个lm_head，尚未核定运行时权重绑定/未使用头，故**基础VLA唯一运行参数量为NR**，不据此算“整体缩小倍数”。未加载几GB底座。Smol/X适配模型规模与完整桥接额外参数不从本π0.5表外推。

历史A4000仅更新Q的E_delta/F_adv，每成员2,529，合计10,116；它是继承模型的一次拟合更新范围，不是部署总参数，也不是全部历史训练成本。本次报告及所汇总主评测的参数更新均为0，冻结并不表示历史未训练。

**论文调用表**

{paper_table}

每格500个有效终局、50任务各10个源，技术失败均0。成功率与调用/尝试按均匀任务、任务内均匀初态统计，因此这里与500条整体均值相等。令c为调用、s为0/1成功：全体均值=Σc/500；成功条件均值=Σ(c·s)/Σs；摊销调用=Σc/Σs=任务等权调用均值/任务等权成功率。摊销分子保留失败轨迹消耗，不能改成仅成功子集或各任务“调用/成功”的简单平均。成功条件分布随方法变化，不是同一批成功源上的等工作量比较。

`policy_calls`的N定义是进入一次raw50 `sample_actions`时计1，10flow完成后记flow；这批0技术失败、全部完成。主链该字段等于完整`sampling_calls`，天然重规划一次计1，每次R/Post入口各1，Velocity入口为base1+guided1共2、20flow，不能统一记成一次纠偏调用。每次采样均生成raw50，执行原生H；进入C10后的尾部丢弃与恢复语义不变。N没有独立保存`sampling_calls`，因此显式列为NR（0/500有记录），不借另一字段填造。N的policy与flow各500/500保存；主链两类采样字段与flow各500/500保存。

flow是动作专家向量场调用，不覆盖全部视觉/语言编码、D/G0或Q。主链episode流数是10×采样数，已保存hook计数在这5,500条中一致。每个成熟监测context调用D两成员/G0两成员；一次Post入口为3次Q ensemble（12成员前向）+1动作梯度；Velocity为8次Q ensemble（32成员前向）+3动作梯度。Q权重冻结、无模型更新。逐格真实监测/Q/梯度合计见CALL_ACCOUNTING.csv，N缺该类episode计数保留NR。

**配对结果与摊销区间**

{pair_table}

成功率区间及全部26组救回/损害、成功差区间直接复用MAIN_FINAL_STATISTICS/MAIN_FINAL_PAIRED_COMPARISONS，未重跑其bootstrap。仅新增一次固定seed=20260922、2,000次CPU摊销成本bootstrap：固定50任务，各任务内对10源有放回抽样；全部16格使用同一源抽样，计算总调用/总成功及同源方法比率。新旧区间均为未校正的逐项百分位95%区间，条件于当前固定任务和经验初态，不包含训练seed/新任务总体不确定性。全成功或全失败任务层的成功经验方差退化；不从这些区间宣称非劣、等效或赢家。

例如Post H30调用/尝试为{f(p30['mean_all'])}，N H10为{f(n10['mean_all'])}，成功率63.2%与61.6%，既有差区间跨0。这是跨H观察，不是“保持性能并加速”的检验。H10 Post/Velocity相对R的成功差区间跨0；所有同H Post−Velocity成功差区间也跨0，不主张二者显著排名。

**已有时间，只报告实际保存范围**

{time_table}

表中两类时间每格均有500/500尝试记录，成功条件/摊销分母分别为该格成功数；范围是已保存episode字段最小至最大，**不是单次纠偏入口延迟**。完整五类时间的总和、全体/成功条件/摊销均值及观测分母见TIMING_TABLE.csv。N缺独立reset及controller-loop字段，均保留null。

N的inference_seconds计预处理、raw50生成、解码；主链同名字段累计计划的生成/纠偏计时，含其内Q/投影等工作，context/D/G0主要进入episode墙钟。主链episode墙钟还含reset及部分本地保存/验证；N与主链实现范围不完全相同。N environment_seconds含reset，主链环境字段仅step/观测格式化，reset另计。不能相减估计净D/G0、净纠偏或监测耗时；表中数字也不作为跨方法系统速度排名。

主链550个已有job JSON实际保留了计划级秒数。本次仅定向读取其计时标量（总逻辑文件字节127,142,692），不重建事件账本或加载轨迹。以下入口统计直接从已保存`plans[].stats.seconds`计算；不额外测时，不人为去掉冷入口。

{entry_table}

R入口计一次propose生成范围；Post/Velocity入口包括其生成、Q调用、动作梯度、投影及本地纠偏产物保存，Velocity还含两次采样；均不含入口前的monitor/context。分母是实际触发入口数，不能当作500次/格或全部部署请求P95。自然重规划及嵌套base/guided计时另存ENTRY_TIMING_TABLE.csv；嵌套时间与入口范围重叠，不相加。其均值/中位数/P95是并发运行下的经验分位数，不是独立GPU性能实验或置信区间。

Post/Velocity还保存`objective.critic_forward_seconds`：每次干预内FrozenObjective.__call__的host计时之和，包括CPU搬运/检查、Q四成员前向及值转换；不含其后的动作反向或objective构造，不是纯Q kernel时间。该字段同样按入口记录分母列于ENTRY_TIMING_TABLE.csv。N没有计划级timer；D/G0/context独立耗时、Q backward、净纠偏增量、GPU kernel时间/能耗仍NR。没有用episode减几个已记录时间字段补造这些缺项。

已存11格主链的Σepisode墙钟为32,742.894s，Σ生成/纠偏字段为11,411.400s；这两项范围重叠，不相加。其command至terminal实际墙钟为4,597.395s（只涵盖R/P/V的5,500条，不含N另波）；8名常驻worker的保存加载时间范围183.576–185.335s，加载与各job环境构建不在episode指标内。并行Σepisode时间不等于整波墙钟、更不是GPU秒，无法从均值承诺部署延迟。

历史该主链还使用过32段尾卡辅助holder，GO至自有后代退出区间合计263.297s（跨卡区间之和，不是GPU算时），当时“整波全holder停算”为false。并发、共享I/O、尾卡占卡影响保留为计时可比性限制；不改历史、不重跑。本CPU任务未查询、停止或恢复holder。现行整波全停规则仍适用于未来正式工作。

**既有消融/触发结论与边界**

E1直接引用E1_COMPLETED_ANALYSIS_20260922.md：在其五任务测试和三拟合seed上，Full相对BCE的Post均值差−0.67pp、Velocity+2.67pp，不支持Full在两路均占优；三seed共享50初态不是150独立初态，seed标准差不是置信区间，该B侧结果不与A计时混排。E6直接引用E6_COMPLETED_ANALYSIS_20260922.md：G0→R 26/50=52%，D5→R 30/50=60%，配对p=0.21875，不支持G0优势，也不能称等价。未据test调阈值或选模型。本任务只交本方法E5，未扩展外部复现或改动这些已结案原件。

不能声称：仅28.2K就代表整个纠偏系统；更少参数即最优/优于微调；一次Velocity等于一次Post采样；成功子集均值就是失败计费后的摊销成本；调用少就是整个系统更快；区间跨0就是非劣/相等；五任务训练已变成MT50纠偏器训练。参数形状、计量定义、CPU算术检查及小型输入来源分别保存于PARAMETER_COUNTS.json、FIELD_DEFINITIONS.json、CPU_CHECKS.json和INPUT_INDEX.json。
'''
(ROOT / 'REPORT.md').write_text(report)
print(json.dumps(dict(status='CPU_REPORT_GENERATED', cells=16, existing_episode_rows=8000,
    added_parameters=parameter_counts['total_added_unique_network_parameters'],
    buffer_elements=parameter_counts['buffer_elements_loaded_copies'],
    outputs=[p.name for p in ROOT.iterdir() if p.is_file()],
    selected_costs={c: stats[c]['metrics']['policy_calls'] for c in ['N_H10', 'Post_H10', 'Velocity_H10']}), indent=2))
