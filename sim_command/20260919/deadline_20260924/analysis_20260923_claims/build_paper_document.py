"""Build current-paper data tables from completed results, without new experiments."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import json
import statistics

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
CAMPAIGN = ROOT / 'sim_command/20260919'
HERE = Path(__file__).parent
EXPORTS = HERE / 'paper_exports'
EXPORTS.mkdir(exist_ok=True)
STAMP = datetime.now(timezone.utc).isoformat()

def read_json(path):
    return json.loads(path.read_text())

def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])

def save_csv(name, rows):
    with (EXPORTS / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

costs = read_json(HERE / 'costs.json')
components = read_json(HERE / 'components.json')
pairs = read_json(HERE / 'main_pairs.json')['comparisons']
transcribed = read_json(HERE / 'MASTER_TRANSCRIPTION_20260923.json')
extra = read_json(HERE / 'master_costs_e6_addendum.json')
cells = read_json(CAMPAIGN / 'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json')['compute_summary']['cells']
selection = read_json(CAMPAIGN / 'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json')
assert selection['chosen_loss'] == 'L01' and selection['fixed_fit_seed'] == 9101 and selection['Post_only']

native = {r['H']:r for r in costs['N_reused_cells']}
replan = {r['H']:r for r in costs['R_multi_reused_cells']}
post = {r['H']:r for r in costs['new_Post_cells'] if r['mode'] == 'G0-multi'}
main_rows, export_main = [], []
for h in [10, 20, 30, 40, 50]:
    row=[h]
    for method, cell in [('N',native[h]), ('R-multi',replan[h]), ('Post-multi',post[h])]:
        sr=cell['successes']/cell['valid']*100
        row.extend([f'{sr:.1f}',f"{cell['policy_calls_mean']:.3f}"])
        export_main.append(dict(H=h,method=method,valid=cell['valid'],successes=cell['successes'],success_rate_percent=sr,full_policy_calls_total=cell['policy_calls_total'],full_policy_calls_per_episode=cell['policy_calls_mean']))
    main_rows.append(row)
save_csv('MAIN_SUCCESS_AND_CALLS.csv',export_main)

loss_rows, fit_rows, export_loss = [], [], []
names={'L00':'BCE','L10':'BCE＋gain','L01':'BCE＋0.5pair','L11':'BCE＋gain＋0.5pair'}
for loss in ['L00','L10','L01','L11']:
    dev=[cells[f'DEV_{loss}_s{seed}_Post_H10']['successes'] for seed in [9101,9102,9103]]
    test=[cells[f'ABLATION_{loss}_s{seed}_Post_H10']['successes'] for seed in [9101,9102,9103]]
    mean=statistics.mean([v*2 for v in test]);sd=statistics.stdev([v*2 for v in test])
    loss_rows.append([f'{loss}：{names[loss]}',f'{sum(dev)/3:.2f}（{sum(dev)}/300）',f'{mean:.2f}±{sd:.2f}', '开发集选定' if loss=='L01' else '消融候选'])
    fit_rows.append([loss,*[f'{v}/100' for v in dev],*[f'{v}/50' for v in test]])
    export_loss.append(dict(loss=loss,objective=names[loss],development_successes=sum(dev),development_evaluations=300,development_unique_sources=100,development_rate_percent=sum(dev)/3,test_successes=sum(test),test_evaluations=150,test_unique_sources=50,test_fit_mean_percent=mean,test_fit_sample_sd_percent=sd,selected=loss=='L01'))
save_csv('LOSS_SELECTION_AND_TEST.csv',export_loss)

# Produce a full task-level source table, without pooling repeated H cells.
task_pairs=list(csv.DictReader((HERE/'task_pairs.csv').open()))
by_key={}
for row in task_pairs:
    if row['comparison'] not in ['Post-minus-N','Post-minus-R']:
        continue
    key=(int(row['H']),row['task'])
    dst=by_key.setdefault(key,dict(H=key[0],task=key[1],valid_per_method=10,Post_successes=int(row['left_success'])))
    assert dst['Post_successes']==int(row['left_success'])
    dst['N_successes' if row['comparison']=='Post-minus-N' else 'R_successes']=int(row['right_success'])
task_export=[by_key[k] for k in sorted(by_key)]
assert len(task_export)==250
save_csv('MT50_PER_TASK_RESULTS.csv',task_export)
save_csv('POST_PAIRED_STATISTICS.csv',[r for r in pairs if r['comparison'] in ['Post-minus-N','Post-minus-R']])

pair_rows=[]
for r in pairs:
    if r['comparison'] not in ['Post-minus-N','Post-minus-R']:
        continue
    pair_rows.append([r['H'],r['comparison'].replace('Post-minus-','Post−'),r['paired_n'],f"{r['delta_pp']:+.1f}",f"[{r['ci95_low_pp']:.1f},{r['ci95_high_pp']:.1f}]",f"{r['rescued']}/{r['harmed']}",f"{r['holm_family_p']:.6g}"])
task_summary=[]
for r in pairs:
    if r['comparison'] in ['Post-minus-N','Post-minus-R']:
        task_summary.append([r['H'],r['comparison'].replace('Post-minus-','Post−'),r['task_better'],r['task_equal'],r['task_worse']])

ext_rows=[]
for r in components['external']['current_pairs']:
    label='Post−VLA-Corrector' if 'VLA-Corrector' in r['comparison'] else 'Post−GAF-v1 adapted'
    ext_rows.append([label,r['paired_valid'],f"+{float(r['difference_pp']):.1f}",f"[{float(r['CI95_low_pp']):.1f},{float(r['CI95_high_pp']):.1f}]",f"{r['rescued']}/{r['harmed']}",f"{float(r['McNemar_exact_p']):.7f}"])

trigger_rows=[]
for r in components['r_g0_once_vs_random_once']['rows']:
    lo,hi=r['pointwise95_CI_pp']
    trigger_rows.append([r['H'],f"{r['g0_once_successes']}/500",f"{r['random_once_successes']}/500",f"+{r['g0_minus_random_pp']:.1f}",f'[{lo:.1f},{hi:.1f}]',f"{r['random_actual_interventions']}/500"])

post_cost_rows=[r for r in transcribed['cost_rows'] if r[1]=='Post']
native_rows=[['SmolVLA050000','234/496（47.18%）','245/500（49.0%）','245/500（49.0%）','N另有4个unknown'],['X-VLA030000','403/500（80.6%）','412/500（82.4%）','409/500（81.8%）','每格500有效']]
native_pairs=[r for r in transcribed['native_pair_rows'] if r[1].startswith('Post')]

parts=[]
parts.append(f'''# EXPERIMENT_FOR_PAPER：Post论文实验表与正文／附录安排

整理时间：{STAMP}。只整理已完成结果；不新增训练或评测。本文件是当前论文取表入口，[实验总表](EXPERIMENT_RESULTS_MASTER.md)继续保存全部原始汇总与历史配置。

## 0. 当前已运行配置：L01

**实际用于当前主结果的是Post-multi＋L01＝BCE＋0.5pair，固定fit9101、四成员Q。gain项未加入最终损失。** 阈值、合法触发与C10规则保持，只取消总干预次数上限。Velocity继承相同配置，但属于另一篇工作，不进入本篇正文或附录；本次暂不纳入LIBERO。

“完整Q训练”表示Q全部参数从头训练，不表示采用包含全部辅助项的L11。“完整方法”表示D/G0/Post流程，也不等于L11。

**为什么不是L11：**预先冻结的规则仅按Post开发集选择。L01开发207/300＝69.00%，L11为203/300＝67.67%；但补充test中，L01为103/150＝68.67%，L11为108/150＝72.00%。因此只写“L01按开发集选定”，不写“L01测试最优”或“L11效果更差”。开发领先仅1.33个百分点，不构成强稳定性证据。所有当前主表已经使用L01，不能将其改名为L11。详见正文表3，选择锁见[SELECTION.json](../sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json)。

### 正文与附录的分工

| 位置 | 原实验编号 | 内容 | 合并与取舍 |
|---|---|---|---|
| 正文表1 | E4/E9＋核心E5 | MT50五H：N/R/Post成功率＋完整策略调用 | 性能、H扫描和调用放在同表，不另铺一张重复效率表 |
| 正文表1补充 | 次数消融 | 同新Q的H10 once/multi | 两行小表；可排在表1下方，不与五H曲线混合 |
| 正文表2 | E3 | H10本地外部方法比较 | 同时保留N、R；说明适配、训练与干预预算差异 |
| 正文表3 | E1/F9 | 四损失的开发选择与补充test | 开发分数和test三fit均值±SD同表，避免混淆选型依据 |
| 正文方法段 | E5 | 约11.9M附加参数，Q4为28,232 | 一句话；完整分项移附录A5 |
| 附录A1/A2 | E4/E9、E1 | 配对统计、逐任务及每fit结果 | 保留共同源、检验范围与重复初态说明 |
| 附录A3 | E6＋触发时机 | multi收益/异常触发；R的Random-once对照 | 正文必须同时交代E6不支持收益触发更优 |
| 附录A4 | E8/F8 | Smol/X专属适配 | 完整呈现效果有限、外部特征成本，不主张普遍增益 |
| 附录A5/A6 | E5、协议说明 | 干预/调用细项、参数、复现边界 | 缺失时间不填0；历史配置不代替当前结果 |

建议正文图1用表1同一份数据画“成功率—平均完整策略调用次数”曲线，同时画N、R和Post。无需新增实验；[绘图用CSV](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/paper_exports/MAIN_SUCCESS_AND_CALLS.csv)已经导出。H=10→50的成功率曲线可作同图第二面板。

## 1. 正文表1：MT50主结果、H扫描与调用成本

**设置：**π0.5固定SFT底座，完整MT50，50任务各10个初态，每格500。H为原生执行间隔；干预发生时允许提前中断，因此H50不是保证连续开环50步。N为原生策略；R为收益触发的多次重规划；Post为同触发器加当前L01纠偏。

成功率单位为%，越高越好；调用为全部有效episode的完整VLA采样均值，越少表示完整采样次数更少。科学失败也进入成本分母。
''')
parts.append(table(['H','N成功率↑','N调用/ep','R-multi成功率↑','R调用/ep','Post-multi成功率↑','Post调用/ep'],main_rows))
parts.append('''
**正文可直接描述：**Post相对N五H提高8.4–25.8个百分点；H从10到50，N由61.6%降至39.2%，Post由70.0%降至64.6%。H30的Post为66.8%／8.462次，N H10为61.6%／15.130次，完整策略调用点估减少44.1%。

**正文必须同时说明：**Post相对同H R仅提高0.4–2.0个百分点，五个配对区间均包含零；大增益属于完整干预系统，不能全部归因于Q纠偏。跨H调用比较不是端到端加速或已证明的非劣性；同H下Post在H20–50比N调用更多。H20/H30相对N H10的成功率差在三项探索性Holm校正后p约0.063，H50区间包含零，故跨H只报告观测权衡。

一次完整raw50采样记一次调用，当前为10次flow；D/G0/Q、编码、梯度和加载等开销不包含在该次数中。提前成功也会减少调用。各H共用500初态，不能累加为2500个独立初态。

来源：[当前主表与逐episode来源](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/main_pairs.json)、[调用统计](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/costs.json)。本表15格共7500次评测，独立初态身份仍为500。

### 正文表1补充：H10同一新Q的单次／多次干预

| Post配置 | 成功/有效 | 成功率% | 完整VLA调用/episode | 平均实际干预次数 |
|---|---:|---:|---:|---:|
| 同L01，最多一次 | 341/500 | 68.2 | 13.862 | 0.782 |
| 同L01，不限总次数（主配置） | 350/500 | 70.0 | 14.074 | 2.022 |

multi−once为+1.8个百分点，救回13、损害4；现成逐项95%区间[0.4,3.4]，精确McNemar p=0.0490（单项未校正）。增加0.212次完整调用/episode，不能称multi更省调用。这是H10的有限证据，不用旧Q其它H的once成绩验证当前新Q。来源：[同版本配对](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/PAIRED.csv)。

## 2. 正文表2：H10本地外部方法比较

同π0.5 SFT030000、MT50原500源。方法保留各自干预机制；该表是本地实现的系统比较，不是严格等训练数据或等干预预算的算法排名。

| 方法 | 成功/有效 | 成功率% | 干预／实现范围 |
|---|---:|---:|---|
| 原生N | 308/500 | 61.6 | 原生H10 |
| 仅重规划R | 343/500 | 68.6 | 收益触发，允许多次 |
| VLA-Corrector，本地实现 | 319/500 | 63.8 | 自身检测与重复干预；8条终局由日志恢复 |
| GAF-v1 adapted | 315/500 | 63.0 | 本地适配、每flow步骤引导 |
| Post（当前L01） | 350/500 | 70.0 | 收益触发＋Post，允许多次 |

Post相对两种外部实现分别提高6.2、7.0个百分点；配对统计放附录A1。GAF的15个训练父源／2个内部holdout、三成员critic等适配细节必须保留，不能简称为官方完整协议复现。VLA-Corrector精确费用只有492/500覆盖，缺8条仍null，故不向本表硬加统一速度排名。不能由此宣称通用SOTA。

来源：[当前E3汇总](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_COMPARISON.csv)、[比较范围与恢复说明](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/component_notes.md)。

## 3. 正文表3：完整Q损失消融与配置选择

四种loss都从未训练初始化实际训练Q全部参数；不是仅改验证公式，也不是历史残差微调。每loss为3个fit，每fit四成员、各4000更新。π0.5、D/G0、编码与训练数据固定。下面仅为Post；开发每fit100源，补充test每fit50源。
''')
parts.append(table(['损失','Post开发分数%（成功/评测）','multi补充test均值±SD（%）','用途'],loss_rows))
parts.append('''
**表注不可省略：**L01按开发集选中，但补充test的L00/L11均值更高。因此不宣称pair或gain是测试增益必需项，不写L01测试最优。test原50初态已经揭晓，仅作补充消融；三个fit重复使用相同初态，300开发评测不是300独立源，150测试评测也不是150独立源。SD为三个fit成功率的样本标准差，不是均值置信区间。部署fit9101预先固定，不从test挑seed。

来源：[完整Q终局](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)、[选择锁](../sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json)、[可用CSV](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/paper_exports/LOSS_SELECTION_AND_TEST.csv)。

### 正文机制讨论必须保留的两项限定

- E6 multi中，收益G0→R为26/50（52%），异常D5→R为31/50（62%）；当前不支持收益触发胜过异常触发。详细次数与配对在附录A3。仍可介绍收益触发机制，但不能称为最优时机或已校准的多次策略价值。
- Smol上Post与R同为245/500，X上Post409/500低于R412/500；适配已验证可运行，尚不支持稳定跨底座纠偏增益。完整结果在附录A4。

### 正文方法段可合并的参数描述

“在冻结π0.5共享编码器之外，D/G0/Q使用约11.9M附加网络参数，其中四成员Q集成仅含28,232个参数。Post在一次新计划采样后完成受约束修复。”完整分项见附录A5。这里描述新增网络规模，不把Q的28K说成整套系统，也不推出相对VLA微调的效率优势。

## A1. Appendix：主结果与外部比较的配对统计

### A1.1 五H同初态配对
''')
parts.append(table(['H','对比','共同有效源','差值pp','逐项95%区间pp','救回/损害','五H家族Holm p'],pair_rows))
parts.append('''
固定50任务内重采样各任务10个配对初态，bootstrap5000次、seed20260923；精确双侧McNemar，Post−N与Post−R各五H分别作Holm校正。区间是逐项区间，不是同时区间，不含重训seed或未见任务不确定性。五H不当作独立数据合并。完整未四舍五入值：[配对CSV](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/paper_exports/POST_PAIRED_STATISTICS.csv)。

### A1.2 当前Post对外部实现
''')
parts.append(table(['对比','共同有效源','差值pp','逐项95%区间pp','救回/损害','精确p（未校正）'],ext_rows))
parts.append('''
该现成E3区间用固定任务内bootstrap2000次、seed20260921，与上表5000次版本分开注明；不套用旧Q的p值或旧多重比较校正。来源：[当前E3配对](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_PAIRED.csv)。

### A1.3 逐任务差异
''')
parts.append(table(['H','对比','成功数更多的任务数','持平任务数','更少的任务数'],task_summary))
parts.append('''
每任务仅10个初态；这里是描述性成功数比较，不是50个任务分别通过显著性检验。完整50任务×5H×N/R/Post成功数已导出[MT50逐任务CSV](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/paper_exports/MT50_PER_TASK_RESULTS.csv)，可供论文附录大表或热力图，不在正文重复250行。

## A2. Appendix：完整Q逐fit结果与训练口径
''')
parts.append(table(['loss','dev fit9101','dev fit9102','dev fit9103','test fit9101','test fit9102','test fit9103'],fit_rows))
parts.append('''
fit seed为9101/9102/9103；每fit四成员ensemble是一个策略配置，不把四成员当成四次独立实验。Q每成员7058参数，48份π0.5候选各4000更新，共192000；AdamW lr3e−4、weight decay0.01、batch32、clip1。同(fit,member)的四loss使用配对初始化/bootstrap/minibatch流，train-only PCA/norm冻结；底座、D/G0、视觉/语言编码冻结。训练来源为固定train600，不能据该表宣称数据效率。

开发100源来自五任务各20，补充test50源来自五任务各10；训练/开发/测试身份隔离，但test已经用于此前探索，因此不称全新盲测。历史“仅更新residual/advantage”的微调消融不进入本表。来源：[实际训练与选择范围](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/component_notes.md)。

## A3. Appendix：触发依据与触发时机

### A3.1 当前multi：收益与异常触发，固定下游R

| 触发器 | 成功/有效 | 成功率% | episode干预0/1/≥2 | 平均干预次数 | 完整策略调用总数 | 调用/episode |
|---|---:|---:|---|---:|---:|---:|
| 收益G0→R | 26/50 | 52.0 | 4/11/35 | 4.80 | 1072 | 21.44 |
| 异常D5→R | 31/50 | 62.0 | 5/2/43 | 7.60 | 1001 | 20.02 |

这是五任务的50个独立于主表ordinal0–9的测试源（ordinal10–19），不是完整MT50。H10/C10；D5阈值0.2521600950570383沿原dev冻结，不按test调阈值。G0−D5为−10pp，救回2／损害7，逐项95%区间[−22,0]，精确p=0.1796875。G0干预更少，但完整策略调用更多，不能称系统更省。旧once的D5=30/50不能代替本表。

来源：[已有E6配对](../sim_command/20260919/results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/PAIRED.json)、[次数与调用补录](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json)。

### A3.2 Q无关的R：G0-once与Random-once
''')
parts.append(table(['H','G0-once成功','Random-once成功','G0−Random pp','逐项95%区间pp','Random实际干预episode'],trigger_rows))
parts.append('''
这组属于单次触发策略的历史机制对照，R不使用Q，因而可继续引用；不把它当作当前Post-multi的随机对照。随机时刻提前冻结，终止在抽中时刻之前不补干预，所以两策略实际干预发生率不同，不能完全归因于相同次数下的纯时机效应。Random-multi已取消，不列待补空表。区间为固定任务内bootstrap2000次/seed20260921，逐项、未多重校正。来源：[冻结R触发对照](../sim_command/20260919/results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_PAIRED.json)。

## A4. Appendix：SmolVLA与X-VLA的专属辅助网络适配（F8）

这里只展示当前L01/fit9101的Post-multi，N与R不依赖Q，复用各底座原终局。
''')
parts.append(table(['底座','N成功/有效','专属R-multi','所选新Q Post-multi','缺项说明'],native_rows))
parts.append('\n\n'+table(['底座','对比','共同有效源','方法/参照成功数','救回/损害','差值pp','逐项95%区间pp'],native_pairs))
parts.append('''
Smol对N配对只使用共同496源，Post为244/496，不用全500源245成功代填。其区间为固定任务内共同源bootstrap2000次；X为任务cluster bootstrap2000次，均seed20260922，统计口径各自保留。Smol对R相同总成功数不代表逐源结果相同或已证明等价。来源：[Smol当前配对](../sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/evaluation_r1/PAIRED.json)、[X当前配对](../sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/PAIRED.json)。

专属数据各计划200 train＋50 dev父源，Smol实际有效cut为188/47，X为191/49；D/G0/Q首轮各32000更新，随后各底座四loss四成员完整Q刷新64000更新；按A的Post开发选定L01。没有用π0.5的Q权重直接替代本底座新Q。具体来源见[总表F8](EXPERIMENT_RESULTS_MASTER.md#current-f8)。

Smol为raw50/nativeK10，X为raw30/nativeK10；两者原协议Mesa80Hz/.01，与π0.5主线NVIDIA EGL30Hz/.015不同。各自内部比较，不把跨底座原始成功率直接当作统一协议下的模型排名。当前还使用额外冻结π0.5特征提供者，11.9M不能当作这两条完整管线全部额外规模。效果只支持适配可运行，不支持普遍纠偏收益。

## A5. Appendix：调用、干预与附加网络参数

### A5.1 当前Post完整计量
''')
parts.append(table(['H','分支','模式','成功/有效','完整调用总数','调用/episode','flow总数','干预总数/均值','干预0/1/≥2','全调用/成功数'],post_cost_rows))
parts.append('''
“全调用/成功数”包含失败episode耗费，是摊销比率；不是只在成功episode中求调用均值。每格500条调用完整；主表只取调用/episode这一易解释指标。技术尝试、训练和holder开销保留在原账，不混入完成任务成本；不能当作项目总计算支出。B H20合并原12条有效Post和接续488条，未重复计入未启动占位。

### A5.2 附加网络参数

| 组件 | 成员数 | 每成员参数 | 合计参数 |
|---|---:|---:|---:|
| D | 2 | 4,474,116 | 8,948,232 |
| G0 | 2 | 1,468,033 | 2,936,066 |
| Q | 4 | 7,058 | 28,232 |
| 总计 | 8 | — | **11,912,530** |

π0.5共享已有编码器，新增编码器参数0，但新增编码计算不为0。PCA/归一化buffer与固定投影不是网络参数；实际底座唯一运行参数量未核定，不以序列化元素数计算“缩小多少倍”。新Q为全参数训练，旧A4000局部更新10116参数不代填。

现有完整策略调用数可用于主表；当前部署条件下统一端到端延迟、GPU能耗、总FLOPs及峰值显存没有在本文件建立可比结论。旧once或旧Q计时不复制为新Q多次纠偏开销，外部方法缺失成本不填0。来源：[参数和成本口径](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/costs_notes.md)。

## A6. Appendix：结果身份与复现边界

| 数据组 | 可用范围 | 不混入当前正文的部分 |
|---|---|---|
| 当前MT50 | π0.5、当前L01/fit9101、完整50任务原500初态 | 旧Q更高或更低的成绩不改名为当前配置 |
| 当前损失消融 | 全参数从头训练、相同数据、每loss三fit | 历史微调初始化已携带监督，不当作本轮消融 |
| E3外部方法 | 固定测试源下的本地系统比较 | 不冒充等训练数据、等干预预算或官方完整复现 |
| 旧20源pilot | 单个disassemble开发样本，已揭晓 | 80%不当作MT50总体成功率 |
| 历史standalone | 独立协议的研究记录 | 不与当前MT50主表合并平均或替代当前消融 |

论文正文至少保留如下限制：固定训练配置，五H共享500初态；Q纠偏对R额外收益小且不确定；L01只在开发选择中领先；E6未显示收益触发胜D5；Smol/X未显示稳定纠偏收益。缺失/技术失败不是任务失败，日志恢复结果须注明来源。

当前稿件不使用Velocity、LIBERO、尚未交付的真机结果、取消的Random-multi或未执行的475源采集。未完成内容不放进论文结果表充作0或预期成绩。历史完整记录继续保存在[实验总表](EXPERIMENT_RESULTS_MASTER.md)，不删除旧失败与旧权重结果。

## 数据文件与更新方式

- [正文主表与图1数据](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/paper_exports/MAIN_SUCCESS_AND_CALLS.csv)
- [开发选择与测试消融](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/paper_exports/LOSS_SELECTION_AND_TEST.csv)
- [主结果配对统计](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/paper_exports/POST_PAIRED_STATISTICS.csv)
- [全部MT50逐任务结果](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/paper_exports/MT50_PER_TASK_RESULTS.csv)
- [可宣称的优势与完整边界](POST_PAPER_CLAIMS_20260923.md)

后续若实际更换loss、fit、触发或协议，必须建立新版本结果，不能改写本文件当前数据的配置标签。当前文档按已锁定L01生成；不根据test结果自行切换为L11。
''')

document='\n\n'.join(parts)+'\n'
assert '| Velocity' not in document
(ROOT/'docs/EXPERIMENT_FOR_PAPER.md').write_text(document)
(EXPORTS/'BUILD.json').write_text(json.dumps(dict(utc=STAMP,configuration='Post L01 fit9101 G0-multi',selection_source=str(CAMPAIGN/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json'),main_rows=len(export_main),loss_rows=len(export_loss),per_task_rows=len(task_export),new_experiments=0),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(document=str(ROOT/'docs/EXPERIMENT_FOR_PAPER.md'),main_cells=15,loss_rows=4,per_task_rows=250,configuration='L01',new_experiments=0),ensure_ascii=False))
