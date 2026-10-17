"""Transcribe existing completed results into the master document; CPU only."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import json
import statistics

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
CAMPAIGN = ROOT / 'sim_command/20260919'
HERE = Path(__file__).parent
DOC = ROOT / 'docs/EXPERIMENT_RESULTS_MASTER.md'
STAMP = datetime.now(timezone.utc).isoformat()

def read_json(path):
    return json.loads(path.read_text())

def read_csv(path):
    return list(csv.DictReader(path.open()))

def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows])

s = DOC.read_text()
assert '### 新Q补录：Post五H同初态配对' not in s, 'This transcription has already been applied.'
(HERE / 'EXPERIMENT_RESULTS_MASTER_before_transcription.md').write_text(s)
pairs = read_json(HERE / 'main_pairs.json')['comparisons']
costs = read_json(HERE / 'costs.json')
extra = read_json(HERE / 'master_costs_e6_addendum.json')
cells = read_json(CAMPAIGN / 'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json')['compute_summary']['cells']
root_a = CAMPAIGN / 'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1'
external = read_csv(root_a / 'E3_PAIRED.csv')
once_pair = [r for r in read_csv(root_a / 'PAIRED.csv') if r['comparison'] == 'Post selected Q multi minus once H10'][0]

# Record both branches' development results and sample SD across the three fits.
dev_rows, loss_rows = [], []
for loss in ['L00', 'L10', 'L01', 'L11']:
    for method in ['Post', 'Velocity']:
        development = [cells[f'DEV_{loss}_s{seed}_{method}_H10'] for seed in [9101, 9102, 9103]]
        assert all(r['terminals'] == 100 for r in development)
        vals = [r['successes'] for r in development]
        dev_rows.append([loss, method, *[f'{v}/100' for v in vals], f'{sum(vals)}/300', f'{sum(vals)/3:.2f}%', '1；仅Post选型' if method == 'Post' else '0；仅另文保留'])
        rows = [cells[f'ABLATION_{loss}_s{seed}_{method}_H10'] for seed in [9101, 9102, 9103]]
        assert all(r['terminals'] == 50 for r in rows)
        percentages = [r['successes'] * 2 for r in rows]
        mean, sd = statistics.mean(percentages), statistics.stdev(percentages)
        old = '| ' + ' | '.join([loss, method, *[f"{r['successes']}/50" for r in rows], 'NR / 待CPU汇总']) + ' |'
        new = old.replace('NR / 待CPU汇总', f'{mean:.2f}±{sd:.2f}')
        assert old in s
        s = s.replace(old, new, 1)
        loss_rows.append(dict(loss=loss, method=method, successes=[r['successes'] for r in rows], mean_percent=mean, sample_sd_percent=sd))
dev_section = '\n### 新Q补录：完整DEV分fit结果（两分支原始记录）\n\n' + table(['loss', '分支', 'fit9101', 'fit9102', 'fit9103', '合计成功/评测', '三fit平均成功率', '选择权重'], dev_rows) + '\n\n每fit重复使用相同100个开发初态；300不是300个独立初态。Velocity不参与选型。来源为[A完整RESULT的compute_summary.cells](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)。下方test均值±SD按三个fit的成功率计算样本标准差（ddof=1），不是置信区间；三fit共用50个test初态。\n\n'
s = s.replace('下表仅填新完整Q的1200条补充test', dev_section + '下表仅填新完整Q的1200条补充test', 1)

# Main pairs and same-Q once/multi; retain every historical table separately.
pair_rows = []
for row in pairs:
    if row['comparison'] not in ['Post-minus-N', 'Post-minus-R']:
        continue
    label = 'Post−N' if row['comparison'].endswith('-N') else 'Post−R'
    pair_rows.append([row['H'], label, row['paired_n'], f"{row['left_success']}/{row['right_success']}", f"{row['delta_pp']:+.1f}", f"[{row['ci95_low_pp']:.1f}, {row['ci95_high_pp']:.1f}]", f"{row['rescued']}/{row['harmed']}", f"{row['exact_mcnemar_p']:.6g}", f"{row['holm_family_p']:.6g}"])
paired_section = '\n### 新Q补录：Post五H同初态配对\n\n' + table(['H', '对比', '共同有效', '左/右成功数', '差值pp', '逐项95%区间pp', '救回/损害', '精确McNemar p', '各五H Holm p'], pair_rows)
paired_section += '\n\n区间为固定50任务内、每任务10源的配对bootstrap5000次，seed20260923；Holm分别覆盖五个Post−N和五个Post−R，不是全论文校正。区间不包含训练seed或未见任务不确定性。五H共享500初态，不当作2500个独立源。Post−R五组区间均含0，不把Post−N大收益全部归因于Q纠偏。来源：[配对CSV](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/main_pairs.csv)、[统计方法与逐文件来源](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/main_pairs.json)。\n\n'
paired_section += '### 新Q补录：H10同版本multi−once\n\n' + table(['分支', 'multi / once成功', '有效对数', '差值pp', '95%区间pp', '救回/损害', '精确p'], [['Post', '350/500 / 341/500', 500, '+1.8', '[0.4, 3.4]', '13/4', '0.0490417'], ['Velocity（另文）', '340/500 / 336/500', 500, '+0.8（描述差值）', 'NR：本次未生成配对区间', 'NR', 'NR']])
paired_section += '\n\nPost配对直接转录[A已发布PAIRED.csv](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/PAIRED.csv)，固定任务内bootstrap2000次/seed20260921，单项未校正。Velocity两格终局完整，但不从边际成功数推断救回/损害。两分支once/multi调用均已补到第6节；不使用旧Q once作为新Q次数对照。\n\n'
s = s.replace(' 新Q配对、区间和成本为NR/待CPU汇总；此处未重算统计。Velocity列只作另文原始记录。', ' 当前Post新Q配对与两分支调用成本已补录到下表和第6节；Velocity列只作另文原始记录。', 1)
old_start = s.index('### 旧固定Q参考表：')
new_start = s.index('### 新所选Q L01正式结果')
once_start = s.index('### 历史次数预算消融：')
old_chunk, new_chunk = s[old_start:new_start], s[new_start:once_start]
s = s[:old_start] + new_chunk + paired_section + old_chunk + s[once_start:]

# External comparisons of the newly selected Q.
e3 = '\n### 当前L01新Q：H10与既有外部方法\n\n' + table(['方法', '成功/有效', '成功率', '范围'], [['N', '308/500', '61.6%', '原N复用'], ['R-multi', '343/500', '68.6%', '原R复用'], ['Post-multi L01/fit9101', '350/500', '70.0%', '本篇当前配置'], ['Velocity-multi L01/fit9101', '340/500', '68.0%', '另文记录'], ['VLA-Corrector', '319/500', '63.8%', '本地实现；8条log-derived'], ['GAF-v1 adapted', '315/500', '63.0%', '适配版；原结果复用']])
erows = []
for r in external:
    label = 'Post−VLA-Corrector' if 'VLA-Corrector' in r['comparison'] else 'Post−GAF-v1 adapted'
    erows.append([label, r['paired_valid'], f"+{float(r['difference_pp']):.1f}", f"[{float(r['CI95_low_pp']):.1f}, {float(r['CI95_high_pp']):.1f}]", f"{r['rescued']}/{r['harmed']}", f"{float(r['McNemar_exact_p']):.7f}"])
e3 += '\n\n' + table(['当前配对', '共同有效', '差值pp', '逐项95%区间pp', '救回/损害', '精确p（未校正）'], erows)
e3 += '\n\n来源：[E3当前表](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_COMPARISON.csv)、[新Q E3配对](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_PAIRED.csv)。固定任务内source bootstrap2000次/seed20260921，不含训练seed不确定性；未挪用旧Q的p值或校正值。各方法训练资产/干预预算未完全匹配，只作本地实现系统比较。VLA-Corrector精确费用覆盖492/500，8条缺项仍null。\n\n'
s = s.replace('## 4. 外部方法对比（E3）\n\n', '## 4. 外部方法对比（E3）\n' + e3, 1)
s = s.replace('### 历史旧Q：multi与既有外部方法（原数值保留，新Q配对待汇总）', '### 历史旧Q：multi与既有外部方法（原数值保留）', 1)
s = s.replace('统计空格等待原逐源结果的CPU配对汇总，不搬用下方once区间与p值。', '这些空格仅属于历史旧Q未转录的统计；不视作尚未执行的实验。当前新Q的Post配对已列在本节首表，不搬用下方once区间与p值。', 1)

# Fill the completed E6-multi empty fields from recorded episodes and pairing.
start = s.index('### F10：multi收益/异常触发')
end = s.index('### 历史once收益/异常触发', start)
e6_rows = []
for r in extra['e6_multi']:
    is_g0 = r['mode'] == 'G0-multi'
    tr = r['trigger_episode_counts']
    e6_rows.append(['G0→R-multi' if is_g0 else 'D5→R-multi', f"{r['successes']}/{r['n']}", f"{r['success_rate']*100:.1f}", f"{tr['zero']}/{tr['one']}/{tr['two_or_more']}", f"{r['total']['interventions']} / {r['mean']['interventions']:.2f}", f"{r['total']['policy_calls']} / {r['mean']['policy_calls']:.2f}", '−10 pp；[−22,0]；2/7' if is_g0 else '+10 pp；[0,22]；7/2'])
e6 = '### F10：multi收益/异常触发（100条及详细统计已补录）\n\n复用dev冻结的D5阈值0.2521600950570383与原五任务ordinal10–19测试源；两臂均取消总次数帽，保留阈值/合法性/C10。旧95/100的episode报警率不等于multi机会预算匹配。\n\n' + table(['触发器', '成功/有效', '成功率%', '触发0/1/≥2', '干预总数 / 均值', '完整policy调用总数 / 均值', '相对另一臂：差值/区间/救回损害'], e6_rows)
e6 += '\n\n技术缺项0。G0−D5精确McNemar p=0.1796875，固定任务内bootstrap2000次/seed20260921，区间为逐项95%；不支持G0优势。原once D5=30/50不代填本表multi的31/50。来源：[终局逐episode与成本补录](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json)、[既有E6配对](../sim_command/20260919/results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/PAIRED.json)。\n\n'
s = s[:start] + e6 + s[end:]

# Recorded native-backbone paired results: no new pairing, no unknown-as-failure.
start = s.index('| 底座 | 新对比 | 共同有效源 |')
end = s.index('原500测试源已经揭晓', start)
native_rows = [['SmolVLA', 'Post−N', 496, '244 / 234', '26 / 16', '+2.02', '[−0.40,4.44]'], ['SmolVLA', 'Velocity−N（另文）', 496, '239 / 234', '24 / 19', '+1.01', '[−1.41,3.43]'], ['X-VLA', 'Post−N', 500, '409 / 403', '24 / 18', '+1.2', '[−1.6,4.0]'], ['X-VLA', 'Post−R', 500, '409 / 412', '8 / 11', '−0.6', '[−2.0,0.8]'], ['X-VLA', 'Velocity−N（另文）', 500, '412 / 403', '21 / 12', '+1.8', '[−1.2,4.8]'], ['X-VLA', 'Velocity−R（另文）', 500, '412 / 412', '7 / 7', '0.0', '[−1.0,1.0]']]
native = '#### 当前新Q：跨底座已发布配对补录\n\n' + table(['底座', '对比', '共同有效源', '方法/参照成功数', '救回/损害', '差值pp', '逐项95%区间pp'], native_rows)
native += '\n\n来源：[Smol新Q配对](../sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/evaluation_r1/PAIRED.json)、[X新Q配对](../sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/PAIRED.json)。Smol为固定任务内共同源bootstrap2000次，X为任务cluster bootstrap2000次，均seed20260922；方法不同不混称同一区间程序。Smol配对的244/239是共同496源内成功数，不替换全500评测的245/240；N四个unknown保留。Smol对补齐后R500以及R−N本次未新增配对统计，成功数已完整录入，不视为未完成评测。上述区间均含0，不宣称稳定跨底座增益。\n\n'
s = s[:start] + native + s[end:]

# Current Q cost table for both branches, all five H plus H10 once.
pcache = {}
cost_rows = []
for r in costs['new_Post_cells']:
    chosen = []
    for path in r['source_paths']:
        if path not in pcache:
            pcache[path] = read_csv(Path(path))
        chosen.extend(x for x in pcache[path] if x.get('status') == 'complete' and x.get('method') == 'Post' and x.get('mode') == r['mode'] and x.get('stage') == ('MAIN' if r['mode'] == 'G0-multi' else 'ONCE') and int(x['H']) == r['H'])
    assert len(chosen) == len({x['source_id'] for x in chosen}) == 500
    counts = [int(x['interventions']) for x in chosen]
    distribution = [sum(v==0 for v in counts), sum(v==1 for v in counts), sum(v>=2 for v in counts)]
    cost_rows.append([r['H'], 'Post', r['mode'], f"{r['successes']}/500", r['policy_calls_total'], f"{r['policy_calls_mean']:.3f}", r['flow_calls_total'], f"{r['interventions_total']} / {r['interventions_total']/500:.3f}", '/'.join(map(str, distribution)), f"{r['all_valid_calls_per_success']:.3f}"])
for r in extra['velocity']:
    tr = r['trigger_episode_counts']
    cost_rows.append([r['H'], 'Velocity（另文）', r['mode'], f"{r['successes']}/500", r['total']['policy_calls'], f"{r['mean']['policy_calls']:.3f}", r['total']['flow_calls'], f"{r['total']['interventions']} / {r['mean']['interventions']:.3f}", f"{tr['zero']}/{tr['one']}/{tr['two_or_more']}", f"{r['total']['policy_calls']/r['successes']:.3f}"])
cost_rows.sort(key=lambda r:(r[2] != 'G0-multi', r[0], r[1]))
cost_section = '\n### 当前L01/fit9101：五H multi与H10 once真实调用\n\n' + table(['H', '分支', '模式', '成功/有效', '完整policy调用总数', '调用/episode', 'flow总数', '干预总数 / 均值', '次数0/1/≥2', '全调用/成功数'], cost_rows)
cost_section += '\n\n每格500个有效episode，包含任务失败；policy_calls=sampling_calls，flow_calls=10×sampling_calls。每次Post干预采样1份新计划，Velocity干预base+guided计2次；动作梯度、D/G0/Q与编码开销另计，不能把调用减少当端到端加速。B H20按各分支原有效12＋接续488合并，排除unstarted占位。\n\nPost H10 multi相对once：成功350对341、平均调用14.074对13.862；新增0.212次/episode，不写成multi更省调用。Post H30相对N H10：66.8%对61.6%、8.462对15.130次，调用点估少44.07%；这是跨H观测权衡，不是非劣性或低延迟保证。当前新Q计时/能耗未在此确认，不挪用下方旧Q计时。\n\n来源：[Post逐源汇总](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/costs.json)、[Velocity及E6成本补录](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json)。以下旧Q表及旧once成本继续留作历史。\n\n'
s = s.replace('## 6. 参数量、调用和计时（E5）\n\n', '## 6. 参数量、调用和计时（E5）\n' + cost_section, 1)

# Remove obsolete pending-summary language for fields filled above.
s = s.replace('新Q配对检验、区间和成本若无明确现成终局摘要，记NR/待CPU汇总，本次不新算统计或推断成本，也不为补表新增实验。', '当前新Q Post主配对/E3、P/V调用、完整Q分fit及均值SD、E6 multi详情和跨底座现成配对已录入本表。尚无可靠记录的计时/能耗继续NR；本次仅CPU转录与算术汇总，不新增实验。', 1)
s = s.replace('两种次数协议均完成；multi统计待转录', '两种次数协议均完成；multi次数/调用/配对已补齐', 1)
s = s.replace('multi调用完整；新增统计/计时范围待CPU汇总', '新Q P/V五H及H10 once调用已补录；未确认的新计时仍NR', 1)
s = s.replace('配对及成本无新明确摘要者NR/待CPU汇总，不能标为所有论文事项完成。', '当前已保存配对及调用详见第1/3/4/5/6节；缺失计时等仍NR，不能标为所有论文事项完成。', 1)
s = s.replace('更新：2026-09-23 00:50 UTC。', f'表格更新：{STAMP}；科学终局快照仍为2026-09-23 00:50 UTC。', 1)
update_line = f'- {STAMP}：补录新Q Post五H配对、H10同版本次数配对、当前E3；补齐P/V DEV分fit、test均值±样本SD、Smol/X现成配对、E6 multi次数/成本和P/V新Q十二格调用。科学终局数未变，未新增训练/评测；LIBERO本次不处理，所有原始记录与旧Q表保留。\n'
s = s.replace('## 11. 本次更新记录\n\n', '## 11. 本次更新记录\n\n' + update_line, 1)
DOC.write_text(s)

index_path = CAMPAIGN / 'deadline_20260924/EXPERIMENT_RESULTS_MASTER_INDEX.json'
idx = read_json(index_path)
idx['updated_at_utc'] = STAMP
idx['latest_analysis'] = '../../docs/POST_PAPER_CLAIMS_20260923.md'
idx['scientific_configuration_status'] = 'complete_selected_L01_Post_only_dev_fixed_fit9101_multi'
idx['per_base_auxiliary_stage'] = 'Smol_and_X_specialized_heads_complete_selected_full_Q_each_64000_updates_and_PV1000_valid'
idx['full_Q_selection'].update(status='complete_11600_valid', chosen_loss='L01', selection='Post-only development; Velocity selection weight0; fixed deployment fit9101', valid=11600, remaining=0)
idx['source_snapshots'].update(current_selected_Q_Post_pairs='deadline_20260924/analysis_20260923_claims/main_pairs.json', current_selected_Q_Post_costs='deadline_20260924/analysis_20260923_claims/costs.json', current_selected_Q_Velocity_and_E6_costs='deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json', current_selected_Q_E3_pairs='results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_PAIRED.csv', current_selected_Q_Smol_pairs='results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/evaluation_r1/PAIRED.json', current_selected_Q_X_pairs='results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/PAIRED.json')
idx['latest_transcription'] = dict(utc=STAMP, source='deadline_20260924/analysis_20260923_claims/MASTER_TRANSCRIPTION_20260923.json', scientific_matrix_valid_unchanged=11600, new_scientific_operations=0, LIBERO='not_processed_this_update', historical_Q_preserved=True)
index_path.write_text(json.dumps(idx,ensure_ascii=False,indent=2)+'\n')
receipt = dict(utc=STAMP, document=str(DOC), index=str(index_path), source_snapshot='2026-09-23T00:50:00Z', new_scientific_operations=0, main_Post_comparisons=10, same_Q_H10_Post_pairing=once_pair, current_E3_pairs=external, DEV_rows=dev_rows, loss_sample_statistics=loss_rows, cost_rows=cost_rows, native_pair_rows=native_rows, E6_rows=e6_rows, original_results_modified=False, historical_tables_retained=True, LIBERO_processed=False)
(HERE / 'MASTER_TRANSCRIPTION_20260923.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(updated=str(DOC), main_pairs=10, cost_cells=len(cost_rows), DEV_rows=len(dev_rows), loss_mean_sd_rows=len(loss_rows), E6_cells=len(e6_rows), native_pairs=len(native_rows), source_index_updated=True, new_experiments=0),ensure_ascii=False))
