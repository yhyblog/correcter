"""Consolidate existing Post results only; standard library, no scientific runs."""
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
DOCS = ROOT / 'Corrector/docs'
P = ROOT / 'Corrector/sim_command/20260919'
D = P / 'deadline_20260924'
F = D / 'FINAL_DATA_CONSOLIDATION_20260923'
OUT = Path(__file__).resolve().parent

def read(p):
    return json.loads(Path(p).read_text())

def link(p, label):
    p = Path(p)
    return f'[{label}]({p})'

def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(str(x) for x in row) + ' |' for row in rows])

def save_json(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def save_csv(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

for name in ['POST_LATEST_SOURCE_AUDIT.json', 'POST_ABLATION_TRIGGER_TABLES.json', 'POST_ABLATION_TRIGGER_NOTES.md', 'extract_post_ablation_trigger.py']:
    src = Path('/tmp') / name
    if src.exists():
        shutil.copy2(src, OUT / name)

audit = read(OUT / 'POST_LATEST_SOURCE_AUDIT.json')
ab = read(OUT / 'POST_ABLATION_TRIGGER_TABLES.json')
roll = read(D / 'L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json')
cross = read(F / 'FINAL_CROSSBASE_H_SWEEP_DATA.json')
base = read(DOCS / 'data/DATA_VELOCITY_VALUES_20260923.json')['ablation_and_external_source_data']
elapsed = {(x['model'], x['H']): x for x in read(F / 'FINAL_CROSSBASE_POST_ELAPSED.json')['rows']}
recovery_file = P / 'results/A/A_D24_L11_RENDER_RECOVERY_V1/RESULT.json'
recovery = read(recovery_file)['summary']['cells']
order = {'pi05': 0, 'SmolVLA': 1, 'X-VLA': 2}
display = {'pi05': 'π0.5', 'SmolVLA': 'SmolVLA', 'X-VLA': 'X-VLA'}
formal = []
for x in roll['cells']:
    if x['method'] != 'Post':
        continue
    row = dict(model=x['model'], H=x['H'], mode=x['mode'], valid=x['valid'], successes=x['successes'], sr_pct=100*x['success_rate'], policy_calls_total=x['sampling_calls_observed_sum'], policy_calls_mean=x['sampling_calls_mean'], flow_total=x['flow_calls_observed_sum'], interventions_total=x['interventions_observed_sum'], interventions_mean=x['interventions_mean'], gradient_observed_total=x['action_gradients_observed_sum'], gradient_coverage=x['action_gradients_known_count'], gradient_scope='episode_fields', elapsed_mean_s=x['elapsed_seconds_mean'], source=str(D / 'L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json'))
    if x['model'] == 'pi05' and x['H'] == 10:
        orig = recovery[f"L11_Post_{x['mode']}_H10"]
        row.update(gradient_observed_total=orig['action_gradients'], gradient_coverage=None, gradient_scope='complete_cell_total; episode_export_field_absent', gradient_source=str(recovery_file))
    formal.append(row)
for x in cross['cells']:
    if x['method'] != 'Post':
        continue
    c = x['costs']
    g = c['action_gradient_calls']
    formal.append(dict(model=x['model'], H=x['H'], mode=x['mode'], valid=x['valid'], successes=x['successes'], sr_pct=x['success_percent'], policy_calls_total=c['sampling_calls']['known_total'], policy_calls_mean=x['sampling_mean'], flow_total=c['flow_calls']['known_total'], interventions_total=c['interventions']['known_total'], interventions_mean=x['interventions_mean'], gradient_observed_total=g['known_total'], gradient_coverage=g['explicit_rows']+g['structural_zero_rows'], gradient_scope='explicit_and_documented_structural_zero', elapsed_mean_s=elapsed[(x['model'], x['H'])]['elapsed_seconds_mean'], source=str(F / 'FINAL_CROSSBASE_H_SWEEP_DATA.json')))
formal.sort(key=lambda x: (order[x['model']], x['H'], x['mode']))
assert len(formal) == 14 and sum(x['valid'] for x in formal) == 7000
for x in formal:
    a = audit['formal_post_cells'][f"{x['model']}/Post/{x['mode']}/H{x['H']}"]
    assert (a['successes'], a['valid']) == (x['successes'], x['valid'])
    assert abs(a['mean_policy_calls']-x['policy_calls_mean']) < 1e-10
    assert x['flow_total'] == 10*x['policy_calls_total']

main = []
for b in base['ablation']:
    x = next(x for x in formal if (x['model'],x['H'],x['mode']) == (b['model'],b['H'],'G0-multi'))
    row = dict(model=b['model'], H=b['H'], N_valid=b['N_valid'], N_successes=b['N_successes'], N_sr_pct=100*b['N_successes']/b['N_valid'], N_calls=b['N_sampling_mean'], R_valid=b['R_valid'], R_successes=b['R_successes'], R_sr_pct=100*b['R_successes']/b['R_valid'], R_calls=b['R_sampling_mean'], Post_valid=x['valid'], Post_successes=x['successes'], Post_sr_pct=x['sr_pct'], Post_calls=x['policy_calls_mean'], Post_interventions=x['interventions_mean'])
    for m in ['N','R']:
        candidate = next((v for v in cross['cells'] if (v['model'],v['H'],v['method'])==(b['model'],b['H'],m)), None)
        if candidate:
            assert row[m+'_successes']==candidate['successes'] and row[m+'_valid']==candidate['valid']
            assert abs(row[m+'_calls']-candidate['sampling_mean'])<1e-10
    main.append(row)
main.sort(key=lambda x: (order[x['model']], x['H']))
assert len(main)==13

external=[]
for m in ['N','R','Post']:
    row = main[0]
    external.append(dict(method={'N':'Native π0.5','R':'Replan-only (G0-multi)','Post':'Post L11 (G0-multi)'}[m], valid=row[m+'_valid'], successes=row[m+'_successes'], sr_pct=row[m+'_sr_pct'], policy_calls_mean=row[m+'_calls'], calls_known=row[m+'_valid'], interventions_mean={'N':0.0,'R':2.034,'Post':2.05}[m]))
for x in base['external']:
    external.append(dict(method=x['method'], valid=x['valid'], successes=x['successes'], sr_pct=x['success_rate_pct'], policy_calls_mean=x['policy_calls']['known_mean'], calls_known=x['policy_calls']['known_count'], interventions_mean=x['interventions']['known_mean']))

trigger=ab['trigger_modes_main500']+ab['e6_trigger_rows']
trigger.sort(key=lambda x: (0 if x['scope'].startswith('MT50') else 1, 0 if x['method']=='Post' else 1, x['H'], {'G0-once':0,'Random-once':1,'G0-multi':2,'D5-once':3,'D5-multi':4}[x['mode']]))
pairs=[]
for name in ['FINAL_L11_POST_PAIRED_STATS.json','FINAL_CROSSBASE_POST_PAIRED_STATS.json']:
    for x in read(F / name)['comparisons']:
        pairs.append(dict(scope='MT50', comparison=x['comparison'], n=x['n'], rescued=x['rescued'], harmed=x['harmed'], delta_pp=x['difference_pp'], ci=x['paired_normal_95ci_pp'], ci_method='Paired normal', p=x['mcnemar_exact_two_sided_p'], holm_p=x.get('holm_five_H_p'), source=str(F/name)))
for x in sorted(ab['r_trigger_paired_as_published']['comparisons'],key=lambda x:(x['H'],x['comparison'])):
    pairs.append(dict(scope='MT50',comparison=f"π0.5 H{x['H']} R {x['comparison']}",n=x['paired_valid'],rescued=x['rescued'],harmed=x['harmed'],delta_pp=x['delta_pp'],ci=[x['bootstrap95_low_pp'],x['bootstrap95_high_pp']],ci_method='Paired bootstrap',p=None,holm_p=None,source=ab['sources']['r_trigger_pairs']))
x=ab['e6_once_pair_as_published']
pairs.append(dict(scope='E6',comparison='R D5-once − G0-once',n=x['n'],rescued=x['rescued'],harmed=x['harmed'],delta_pp=x['difference_pp'],ci=None,ci_method='NR',p=x['mcnemar_exact_two_sided_p'],holm_p=None,source=ab['sources']['e6_once']))
x=ab['e6_multi_pair_as_published'][0]
pairs.append(dict(scope='E6',comparison='R G0-multi − D5-multi',n=x['paired_valid'],rescued=x['rescued'],harmed=x['harmed'],delta_pp=x['difference_pp'],ci=[x['CI95_low_pp'],x['CI95_high_pp']],ci_method='Paired bootstrap',p=x['McNemar_exact_p'],holm_p=None,source=ab['sources']['e6_multi_pairs']))
for x in pairs:
    assert abs(x['delta_pp']-100*(x['rescued']-x['harmed'])/x['n'])<1e-9

values=dict(generated_utc=datetime.now(timezone.utc).isoformat(),scope='Final Post L11 and identified reusable controls; no new scientific execution',configuration=dict(loss='BCE + gain + 0.5pair',loss_id='L11',fit_seed=9101,Q_members=[1041,1042,1043,1044],primary_mode='G0-multi'),main=main,external=external,loss_ablation=ab['full_q_post_summary'],loss_ablation_per_fit=ab['full_q_post_cells'],trigger=trigger,formal_post_costs=formal,paired_comparisons=pairs,parameters=base['parameter_counts'],source_audit=str(OUT/'POST_LATEST_SOURCE_AUDIT.json'),baseline_extraction_source=str(DOCS/'data/DATA_VELOCITY_VALUES_20260923.json'),baseline_original_sources=base['source_files'])
values['external_cost_missing_sources'] = {x['method']: x['cost_missing_sources'] for x in base['external']}
save_json(DOCS/'data/EXPERIMENT_FOR_POST_VALUES_20260924.json',values)
save_csv('MAIN_H_SWEEP.csv',main)
save_csv('EXTERNAL_COMPARISON.csv',external)
save_csv('FORMAL_POST_COSTS.csv',[{k:x.get(k) for k in formal[0]} for x in formal])
save_csv('TRIGGER_MODES.csv',[{k:x.get(k) for k in ['scope','method','mode','H','valid','successes','sr_pct','policy_calls_mean','interventions_mean','source']} for x in trigger])
save_csv('PAIRED_COMPARISONS.csv',pairs)
save_csv('LOSS_ABLATION_PER_FIT.csv',ab['full_q_post_cells'])

main_table=table(['Backbone','H','Native SR (%)','Native Policy Calls','Replan SR (%)','Replan Policy Calls','Post SR (%)','Post Policy Calls','Post Interventions'],[[display[x['model']],x['H'],f"{x['N_sr_pct']:.1f}"+('†' if x['N_valid']!=500 else ''),f"{x['N_calls']:.3f}"+('†' if x['N_valid']!=500 else ''),f"{x['R_sr_pct']:.1f}",f"{x['R_calls']:.3f}",f"{x['Post_sr_pct']:.1f}",f"{x['Post_calls']:.3f}",f"{x['Post_interventions']:.3f}"] for x in main])
external_table=table(['Method','Success Rate (%)','Policy Calls','Interventions'],[[x['method'],f"{x['sr_pct']:.1f}",f"{x['policy_calls_mean']:.3f}"+('†' if x['calls_known']!=500 else ''),'N/A' if x['interventions_mean'] is None else f"{x['interventions_mean']:.3f}"+('†' if x['calls_known']!=500 else '')] for x in external])
loss_rows=[]
for x in ab['full_q_post_summary']:
    d,s=x['development'],x['revealed_selection50']
    loss_rows.append([x['loss']+(' (Selected)' if x['selected_final'] else ''),x['objective'],' / '.join(f'{v:.1f}' for v in d['sr_pct_per_fit']),f"{d['mean_sr_pct']:.2f} ± {d['sample_sd_sr_pct']:.2f}",f"{d['sampling_calls_mean_over_evaluations']:.3f}",' / '.join(f'{v:.1f}' for v in s['sr_pct_per_fit']),f"{s['mean_sr_pct']:.2f} ± {s['sample_sd_sr_pct']:.2f}",f"{s['sampling_calls_mean_over_evaluations']:.3f}"])
loss_table=table(['Loss ID','Objective','Dev SR by Fit (%)','Dev SR, Mean ± SD (%)','Dev Policy Calls','Selection SR by Fit (%)','Selection SR, Mean ± SD (%)','Selection Policy Calls'],loss_rows)
trigger_table=table(['Source Set','Method','Trigger / Count','H','Success Rate (%)','Policy Calls','Interventions'],[['MT50' if x['scope'].startswith('MT50') else 'E6', 'Post L11' if x['method']=='Post' else 'Replan-only',x['mode'],x['H'],f"{x['sr_pct']:.1f}",f"{x['policy_calls_mean']:.3f}",f"{x['interventions_mean']:.3f}"] for x in trigger])
cost_rows=[]
for x in formal:
    cov='Cell total' if x['gradient_coverage'] is None else f"{x['gradient_coverage']}/{x['valid']}"
    cost_rows.append([display[x['model']],x['H'],x['mode'].replace('G0-',''),f"{x['policy_calls_total']:,.0f}",f"{x['flow_total']:,.0f}",f"{x['interventions_total']:,.0f}",f"{x['gradient_observed_total']:,.0f}",cov,f"{x['elapsed_mean_s']:.3f}"])
cost_table=table(['Backbone','H','Count Mode','Total Policy Calls','Total Flow Steps','Total Interventions','Observed Action Gradients','Gradient Coverage','Mean Episode Time (s)'],cost_rows)
def pv(v):
    if v is None: return 'NR'
    return '<0.001' if v<.001 else f'{v:.3f}'
pair_table=table(['Source Set','Comparison (Left − Right)','Rescued','Harmed','ΔSR (pp)','95% CI (pp)','CI Method','McNemar p','Holm p'],[[x['scope'],x['comparison'].replace('pi05','π0.5'),x['rescued'],x['harmed'],f"{x['delta_pp']:+.1f}",'NR' if x['ci'] is None else f"[{x['ci'][0]:.2f}, {x['ci'][1]:.2f}]",x['ci_method'],pv(x['p']),'—' if x['holm_p'] is None else pv(x['holm_p'])] for x in pairs])

doc=f'''# Post 分支正式实验数据汇总

更新日期：2026-09-24。最终配置为 **Post-multi，L11＝BCE＋gain＋0.5pair，固定 fit9101，Q 四成员 1041–1044**。正式 Post 结果共 **14 格、7,000 条有效终局**：π0.5 五个 H 的 multi 与 H10 once，SmolVLA 五个 H 的 multi，X-VLA 三个 H 的 multi。最新补充为 SmolVLA H20/30/40/50 与 X-VLA H20/30，已全部纳入。

本文件集中管理当前 Post 配置及仍可复用的基线、完整 Q 消融、触发器对照；同类数据合表。历史版本和失败尝试继续保存在 [实验总表](EXPERIMENT_RESULTS_MASTER.md)，论文布局参考 [论文数据文档](EXPERIMENT_FOR_PAPER.md)，算法对应 [Post 算法说明](ALGORITHM_POST_ZH.md)。本文没有新增评测。

数值导出：{link(DOCS/'data/EXPERIMENT_FOR_POST_VALUES_20260924.json','完整 JSON')}；{link(OUT,'本次合并来源、CSV 与生成脚本')}。文中 **NR** 表示没有可用记录，**N/A** 表示指标不适用，均不等于零。

## 1. MT50 主结果、H 扫描与跨底座适配

表 1 同时覆盖原 E4/E9 主结果与 H 扫描、N→R→Post 组件比较，以及 SmolVLA/X-VLA 适配，避免拆成多张重复表。**Native（N）**为原策略按 H 正常执行；**Replan（R）**为 G0 触发后仅重规划；**Post**在相同触发机制下进一步纠偏。R 与 Post 在本表均为 multi，不限制全局触发总次数，其余合法时机、阈值与承诺规则保持固定。

每底座预定 MT50 全部 50 个任务、每任务 10 个固定源，共 500 条；同底座各 H 复用同一源集合。成功率为有效终局成功数/有效终局数。除 † 外均为 500 条；† SmolVLA H10 Native 只有 496 条有效、4 条未知，234 个成功，以 496 为分母；这 4 条没有补为失败。Policy Calls 与 Interventions 为**每个有效 episode 的平均值，包含任务成功和失败**，并非“只在成功任务中”的均值。

{main_table}

**比较范围。** H 是正常执行队列长度，预测 chunk 不随 H 改变；π0.5/SmolVLA raw50，X-VLA raw30，干预承诺 C10，结束后丢弃未执行尾部并恢复正常 H。π0.5 使用 NVIDIA EGL、30Hz、动作尺度 .015；SmolVLA/X-VLA 使用其冻结 Mesa、80Hz、.01 协议。因此比较应在同底座内部进行，表中跨底座的原始成功率不是统一协议下的模型排名。SmolVLA H10 的 N 与 Post 不能用完整 500 对 496 直接构造配对检验。

**读数边界。** π0.5 Post 相对同 H Native 提高 7.6–26.0pp，但相对 Replan 的点差只有 0.2–2.4pp；相应配对统计见表 6。SmolVLA 五 H 的 Post 均高于其 Native 点估计；X-VLA H30 Post 与 Native 同为 77.0%，低于 Replan 的 78.8%。不将结果写成所有底座、所有 H 都有额外纠偏增益。π0.5 H10 Post 的调用数低于 Native；H>10 时 Post 的调用数高于同 H Native，不能概括为普遍减少策略调用。

来源：{link(D/'L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json','原八格 L11 Post 终局')}、{link(F/'FINAL_CROSSBASE_H_SWEEP_DATA.json','新增六格 Post 与对应 N/R')}、{link(F/'SMOL_R_H10_CALLS.json','Smol H10 R 调用')}、{link(P/'work/B/B_D24_E8_POST_V1_r1/VALID_N_INDEX.json','跨底座 H10 N 有效源')}。统一表格导出：{link(OUT/'MAIN_H_SWEEP.csv','MAIN_H_SWEEP.csv')}。

## 2. 外部方法对比

表 2 使用相同 π0.5 SFT030000、H10、MT50 原 500 源；N/R/Post 三行复用表 1，**不是额外实验**。外部方法使用各自实际实现与训练资产，干预预算未完全一致，属于本地系统比较。GAF 标为 adapted，不能当成官方协议的原样复现。

{external_table}

† VLA-Corrector 成功率覆盖全部 500 源，其中 8 条由已保存终局日志恢复并独立标记；精确调用与干预费用只覆盖 492 条，8 条费用保持未知。GAF 为连续 flow 引导，离散干预次数不适用。GAF 使用 15 个训练父源、2 个内部 holdout、三个 critic 各 10,000 更新；这些训练数据与 Post 不完全相同。

当前 L11 Post 相对 VLA-Corrector/GAF 的点差为 +5.4/+6.2pp，对应救回/损害为 62/35 与 62/31，统计见表 6。没有统一记录条件下的端到端速度排名；也不由本表宣称同数据预算、公平训练成本或通用 SOTA。

来源：{link(P/'results/A/A_D24_E3_UNSTARTED_CONTINUATION_V1/COMBINED_EPISODES.json','VLA-Corrector 合并终局')}、{link(P/'results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/FINAL_SUMMARY.json','GAF 终局')}；费用与未知源保存于 {link(DOCS/'data/EXPERIMENT_FOR_POST_VALUES_20260924.json','本次数值导出')}。

## 3. 完整 Q 损失消融与最终选型

表 3 合并开发评估与补充选型结果，全部为 π0.5、Post-multi、H10。**四种损失均实际重新训练 Q 的全部参数**，每种损失 3 个 fit、每 fit 四成员、每成员 4,000 更新；没有把只改推理损失或历史局部参数微调当作完整消融。

开发集为五任务各 20 源，共 100；选型集为五任务各 10 源，共 50。三 fit 顺序均为 9101/9102/9103；每 fit 复用相同源，不能将三次评测合称 150 个独立选型初态。± 为三 fit 成功率的**样本标准差**，不是二项误差或均值置信区间。Policy Calls 按各集合全部有效 episode 汇总。

{loss_table}

当前选择依据是**已揭晓选型集上三 fit 均值优先、并列时观察到的 SD 较小**：L11 与 L00 都为 72.00%，L11 的 SD 为 2.00、L00 为 3.46，因此采用 L11；部署固定 fit9101，不再次按评测表现挑 fit。L10 的 SD 更小但均值更低，L01 在开发集上更高。数据不支持“L11 在所有集合最优”“L11 的总体方差最小”或“每个损失项单独加入都有效”。

**选型集已揭晓，且其 50 源包含在主表 π0.5 的 500 源中；H10 L11 multi 复用了这 50 条有效结果。** 因此主表不能表述为完全未触及的盲测。历史开发集选择 L01 的决定仍留在总表，当前表不混用旧 L01 的最终成绩。

π0.5 共训练 48 个 Q 成员、192,000 更新；固定 train600、train-only PCA/归一化、AdamW lr3e−4、weight decay0.01、batch32、clip1；同(fit,member)的不同 loss 使用配对初始化及采样流。底座、D/G0 与编码器冻结。本表没有进行数据效率实验。

来源：{link(Path(ab['sources']['full_q_result']),'完整 Q 训练终局')}、{link(Path(ab['sources']['full_q_episodes']),'既有逐 episode 数据')}。逐 fit 成功数、调用、flow、干预和梯度保存在 {link(OUT/'LOSS_ABLATION_PER_FIT.csv','LOSS_ABLATION_PER_FIT.csv')}。

## 4. 触发机制与单次／多次：统一对照表

表 4 汇总原本分散的次数、随机时机和异常触发对照，按 Source Set 区分。MT50 行使用主表 500 源；E6 使用五任务各 10 个 ordinal10–19 的独立源，共 50，与主表 ordinal0–9 不重叠。E6 的四行复用同一 50 源，不能与 MT50 行横向当成相同难度比较。

{trigger_table}

当前同权重 L11 Post 的 once/multi 直接对照只覆盖 H10：68.6%→69.2%，救回 10、损害 7；配对区间包含零，不能写成多次显著优于单次。其余 H 的正式 Post 主表均为 multi。旧 Post 随机单次结果使用旧 Q，本文件不将其重标为 L11；**随机时机证据来自不依赖 Q 的 Replan-only 对照**。

R 的 Random-once 在运行前固定随机时机；任务在该时机前终止或时机不合法时不会强制补干预，因此 G0-once 与 Random-once 实际干预率不同。这是两种时机机制的总体效果比较，不是严格等实际干预次数的纯时机效应。Random-multi 已取消，没有结果可填。

E6 的 D5 阈值 0.2521600950570383 在旧开发 100 源上按 95/100 报警率匹配，不按测试成功率选择；G0 阈值 0.05。E6 once/multi 中 G0 成功率都没有高于 D5。multi 的 G0 平均干预较少（4.8 vs 7.6），但策略调用更多（21.44 vs 20.02），不能据此宣称整体更省。报警匹配也不等于 multi 下实际干预预算相同。

来源与逐行计数：{link(OUT/'POST_ABLATION_TRIGGER_TABLES.json','消融和触发结果合并 JSON')}、{link(OUT/'TRIGGER_MODES.csv','TRIGGER_MODES.csv')}。

## 5. 正式 Post 运行成本与计量覆盖

表 5 集中保存 14 格 Post 的总量与时间；表 1、表 4 中正式 Post 行的平均调用值来自这些总量。每格 500 个有效 episode；计量包含合法任务失败，排除历史技术无效尝试。一次 Policy Call 是完整 VLA 计划采样，NFE=10，因此本组 Flow Steps=10×Policy Calls。Post 每次纠偏使用一次动作梯度，不更新策略或 critic 参数。

{cost_table}

**覆盖说明。** π0.5 H10 的梯度总数由原单元 RESULT 明确记录，但统一逐 episode 导出没有该字段，故写 Cell total，不伪造逐源覆盖。Smol/X H10 的梯度字段显式覆盖 389/500、398/500，表中为已知记录之和，缺项不补零；不由这些稀疏行计算完整总体梯度均值。新增 H 的完整覆盖包括有明确证据的结构性零，细分保存在原汇总中。

Mean Episode Time 为保存的 episode elapsed_seconds 描述性均值，受节点、并发、模拟器、记录开销影响；不是纯推理延迟、GPU 秒、能耗或跨方法速度结论。历史技术失败、恢复尝试和占卡费用另存总表，未隐藏为成功样本成本。表 1 的 Policy Calls 不包含 D/G0、编码器与 Q 前向，不能等同全部计算量。

来源：{link(D/'L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json','原 L11 计量')}、{link(recovery_file,'π0.5 H10 原单元梯度总数')}、{link(F/'FINAL_CROSSBASE_H_SWEEP_DATA.json','新增 H 原始计量及覆盖')}、{link(F/'FINAL_CROSSBASE_POST_ELAPSED.json','新增 H 保存计时')}。导出：{link(OUT/'FORMAL_POST_COSTS.csv','FORMAL_POST_COSTS.csv')}。

## 6. 逐源配对差异：集中统计表

表 6 合并既有 Post、时机及 E6 配对结果。**救回/损害始终按 Comparison 左侧相对右侧定义**。MT50 各行共同有效源为 500，E6 为 50。Paired normal 为固定任务、任务内配对差的方差及逐项 95% 正态近似；Paired bootstrap 为原已发布的任务内配对源 bootstrap（2,000 次、seed20260921）。这里只迁移已完成统计，没有新跑 bootstrap。

{pair_table}

所有区间是逐项区间；π0.5 五 H 的 Post−N、Post−R 分别作五次 Holm 校正，其他行无该校正，故 Holm p 为“—”。NR 表示原结果没有对应检验/区间，非 p=1 或无差异。上述统计不覆盖训练 seed、新任务及协议变化的不确定性，也不能消除选型初态重叠。当前统一统计包未生成最终 L11 的 Smol/X H10 配对区间，因此不拿旧 Q 区间代替；其成功率和调用结果已完整列于表 1。

来源：{link(F/'FINAL_L11_POST_PAIRED_STATS.json','π0.5／外部／次数配对')}、{link(F/'FINAL_CROSSBASE_POST_PAIRED_STATS.json','新增跨底座 H 配对')}、{link(Path(ab['sources']['r_trigger_pairs']),'R 时机及次数配对')}、{link(Path(ab['sources']['e6_multi_pairs']),'E6 multi 配对')}。全部精确 p 值与区间（未四舍五入）见 {link(OUT/'PAIRED_COMPARISONS.csv','PAIRED_COMPARISONS.csv')}。

## 7. 训练覆盖、参数与方法描述所需数据

| Backbone | Base Checkpoint | Predicted Chunk | Evaluated H | Auxiliary Data / Training |
| --- | --- | --- | --- | --- |
| π0.5 | MT50 SFT030000 | 50 | 10 / 20 / 30 / 40 / 50 | 历史五任务 train600；完整 Q 四 loss×三 fit×四成员，各 4,000 更新；最终 L11/fit9101 |
| SmolVLA | MT50 SFT050000 | 50 | 10 / 20 / 30 / 40 / 50 | 专属 200 train＋50 dev 计划父源，有效 cut 188/47；首轮 D/G0/Q 合计 32,000 更新；完整 Q 四 loss×四成员另 64,000 更新；使用本底座 L11 |
| X-VLA | MT50 SFT030000 | 30 | 10 / 20 / 30 | 专属 200 train＋50 dev 计划父源，有效 cut 191/49；首轮 D/G0/Q 合计 32,000 更新；完整 Q 四 loss×四成员另 64,000 更新；使用本底座 L11 |

Smol/X 首轮的 32,000 为 D 双成员、G0 双成员、Q 四成员各 4,000 的**合计**，不是每类网络各 32,000。它们重新采集本底座数据并训练辅助网络，未直接沿用 π0.5 Q 权重；但仍使用额外冻结 π0.5 特征提供者，其成本须另计。

| Component | Members | Parameters per Member | Total Parameters |
| --- | --- | --- | --- |
| D | 2 | 4,474,116 | 8,948,232 |
| G0 | 2 | 1,468,033 | 2,936,066 |
| Q | 4 | 7,058 | 28,232 |
| Total | 8 | — | 11,912,530 |

11.91M 是附加 D/G0/Q 网络规模，28K 只是 Q，均不包含底座。π0.5 复用冻结编码器，新增编码器参数为零不等于新增编码计算为零；PCA/归一化 buffer 不计入网络参数。Smol/X 的额外冻结特征模型更不能省略。可以描述小规模附加网络，不能据此推出比 VLA 微调更高效。

π0.5 主表评测 MT50 全 50 任务，但 D/G0/Q 的训练覆盖仍是五任务。历史 G0 的收益监督为 5 步承诺、native10 后缀；Q 的终局标签为候选执行 10 步后 native10 续跑。部署使用 C10、不同 H 和 multi，不能直接宣称这些分数是当前部署下已校准的最终成功概率。局部配对采集本身不作为创新或数据效率优势。

来源：{link(DOCS/'EXPERIMENT_RESULTS_MASTER.md','总表 F8 专属训练记录')}、{link(D/'analysis_20260923_claims/component_notes.md','完整 Q 训练设置（其中旧成绩不复用）')}、{link(D/'analysis_20260923_claims/costs_notes.md','参数与计量定义')}。

## 8. 细粒度数据入口与尚不能归入正式 Post 的项目

π0.5 各 H 的 50 任务 N/R/Post 成功数保存在 {link(F/'FINAL_L11_POST_PER_TASK.csv','逐任务 CSV')}；新跨底座 H 的有效 episode 及来源索引保存在 {link(F/'FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv','跨底座逐 episode CSV')}。这些细粒度数据通过链接集中管理，避免在本文复制超宽逐任务表。

| Item | Current Evidence | Treatment in This Document |
| --- | --- | --- |
| L11 Post Random-once | 当前没有同版本正式结果；已有 Post 随机对照绑定旧 Q | 不填成 L11；保留 R 随机对照作为明确标注的辅助证据 |
| L11 Post once at H20/30/40/50 | 当前没有同版本正式结果 | H 扫描只报告已完成 multi，不移用旧 once |
| Real-world results | 已有用户提供的三任务计数，每任务 60 次；Post 分支、Q 版本和触发配置尚未绑定 | 数值仍在总表，正式 Post 结果待身份确认后再加入 |
| LIBERO full method | 完整 D/G0/L11 系统缺结果；已有 operator-only 不等价 | 暂不列正式 Post 成功率 |
| QGF / QPILOTS | 文献资料可用，未找到本地同协议实际终局 | 不将论文数值冒充复现实验 |
| Historical L01 / old Q / demo videos | 历史数据及选择性展示保留 | 不混入当前正式主表；演示视频不计总体成功率 |

本次核对以终局结果、有效源索引和小型汇总为准；较晚回执中的演示录像与缺口审计未产生新的正式成绩。最新来源与纳入决定见 {link(OUT/'POST_LATEST_SOURCE_AUDIT.json','Post 来源审计')}。原始数据、现有总表与其他分支文档均保留。
'''
(DOCS/'EXPERIMENT_FOR_POST.md').write_text(doc)
save_json(OUT/'BUILD_SUMMARY.json',dict(generated_utc=values['generated_utc'],formal_post_cells=len(formal),formal_post_valid=sum(x['valid'] for x in formal),main_multi_rows=len(main),loss_rows=len(ab['full_q_post_summary']),loss_per_fit_rows=len(ab['full_q_post_cells']),trigger_rows=len(trigger),paired_rows=len(pairs),document=str(DOCS/'EXPERIMENT_FOR_POST.md'),scientific_runs=0))
print(json.dumps(read(OUT/'BUILD_SUMMARY.json'),ensure_ascii=False))
# Preserve the requested appendix when rebuilding the base document.
if (OUT/'appendix_data/POST_LIBERO_APPENDIX_DATA.json').exists():
    import runpy
    runpy.run_path(str(OUT/'append_post_fine_results.py'),run_name='__main__')
