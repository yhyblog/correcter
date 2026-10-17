# Standalone 结构消融：完整结果与参数

封存时间：2026-09-18T17:12:22.952004+00:00。原已揭晓 held100、五任务各20个不同初态，98个cut＋2个共同结局；每源4个配对后缀。固定A4000，不训练、不改G0或种子，不作事后赢家选择。

本轮回答拆除其他生成分支后的效果与成本：三个入口各自产生a0及自身方向，半径只依赖自身容量。它是已揭晓队列的结构消融，不能称为新的独立held验证。

## 八臂成功率

| 方法 | 成功/400 | 成功率 | 数据来源 |
|---|---:|---:|---|
| 正常 native10 | 168/400 | 42.00% | 封存旧对照 |
| 仅报警重规划 R | 214/400 | 53.50% | 封存旧对照 |
| 原 matched-V | 237/400 | 59.25% | 封存旧对照 |
| 原 matched-D | 234/400 | 58.50% | 封存旧对照 |
| 原 matched-P | 250/400 | 62.50% | 封存旧对照 |
| standalone velocity | 240/400 | 60.00% | 新增独立入口实测 |
| standalone direct | 237/400 | 59.25% | 新增独立入口实测 |
| standalone post | 252/400 | 63.00% | 新增独立入口实测 |

## 三项共同主要比较：solo − R

区间单位为百分点；每次任务内整源抽样，4后缀不当作独立初态。同时报告普通95%与三比较Bonferroni 98.333%源bootstrap区间。

| 比较 | 差值pp | 95% CI | 98.333% CI | 救回/损害 | 正/负/零源 |
|---|---:|---|---|---:|---:|
| solo_post_minus_alarm_replan10 | 9.50 | [3.50, 15.75] | [2.50, 17.25] | 47/9 | 18/5/77 |
| solo_direct_minus_alarm_replan10 | 5.75 | [0.00, 11.75] | [-1.25, 13.00] | 37/14 | 16/5/79 |
| solo_velocity_minus_alarm_replan10 | 6.50 | [2.50, 11.25] | [1.50, 12.25] | 30/4 | 13/4/83 |

三项均保留。post和velocity的Bonferroni校正区间均高于0，direct的校正区间跨0。post相对R为+9.5pp，相对原matched-post仅+0.5pp（描述性95%区间含0）；本队列支持post拆掉其他方向生成后仍有正收益，但不证明它优于原完整matched-post。三项点估计超过5pp，不等于真实收益至少5pp。该队列已经揭晓，不能将此消融作为新的独立验证或据此重选模型/方法。

## 结构诊断与次要比较

| 比较 | 差值pp | 描述性95% CI | 救回/损害 | 正/负/零源 |
|---|---:|---|---:|---:|
| solo_post_minus_post | 0.50 | [0.00, 1.25] | 2/0 | 2/0/98 |
| solo_direct_minus_direct | 0.75 | [0.00, 1.75] | 3/0 | 3/0/97 |
| solo_velocity_minus_velocity | 0.75 | [-1.50, 3.00] | 6/3 | 3/1/96 |
| solo_post_minus_continue_native10 | 21.00 | [13.50, 29.00] | 96/12 | 35/6/59 |
| solo_direct_minus_continue_native10 | 17.25 | [9.75, 25.00] | 85/16 | 29/9/62 |
| solo_velocity_minus_continue_native10 | 18.00 | [10.75, 25.51] | 86/14 | 32/8/60 |
| alarm_replan10_minus_continue_native10 | 11.50 | [3.25, 20.00] | 79/33 | 28/13/59 |

## 逐任务

| 任务（各20初态） | N | R | 原V | 原D | 原P | solo-V | solo-D | solo-P |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| disassemble-v3 | 52/80 | 49/80 | 59/80 | 64/80 | 60/80 | 61/80 | 65/80 | 60/80 |
| pick-place-wall-v3 | 30/80 | 58/80 | 58/80 | 60/80 | 66/80 | 59/80 | 62/80 | 66/80 |
| shelf-place-v3 | 16/80 | 14/80 | 18/80 | 17/80 | 22/80 | 18/80 | 17/80 | 23/80 |
| stick-pull-v3 | 7/80 | 17/80 | 22/80 | 21/80 | 22/80 | 22/80 | 21/80 | 23/80 |
| stick-push-v3 | 63/80 | 76/80 | 80/80 | 72/80 | 80/80 | 80/80 | 72/80 | 80/80 |

完整逐源4位结局串与十项源均差见 `per_source.csv`；无报警2源保留共同终局，完整分母不变。

## 实际幅度与完整入口成本

完整入口计时包含各自a0、方向生成、诊断评分和检查；不把共享a0摊销时间冒充独立成本。载模、恢复与后缀时间单列，重叠计时不得相加。旧fullbank与本轮并发条件不同，不能据此宣称严格硬件加速比。

| 方法 | VLA采样/入口 | 入口均值s | 中位s | p95s | XYZ实际RMS均值 | grip实际RMS均值 | XYZ/grip旧零组恢复源数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| standalone post | 1 | 0.6374 | 0.4837 | 1.2287 | 0.045115 | 0.090003 | 0/0 |
| standalone direct | 2 | 0.9204 | 0.9193 | 1.1988 | 0.048782 | 0.090511 | 0/0 |
| standalone velocity | 2 | 0.9039 | 0.8866 | 1.1515 | 0.045949 | 0.089554 | 0/0 |

正式整波含lifecycle耗时 640.90s；worker载模均值 170.11s；每源solo bank恢复均值 1.1185s。分支恢复/后缀、旧reference预检成本及Q关联详见summary.json。Q仅作描述，不是接受门或梯度有效性的充分证据。

## 技术、来源与预算

- 同freeze预检50次通过；5源旧五臂rep0完整复现、原生方向与raw身份检查通过。旧bank未保存原生V/D，不能扩大成98源历史原生V/D全部逐位复现；post历史梯度按实际存档检查。
- 正式100槽完整，32worker、98bank＋1176分支，全轨迹/raw/配对/scene/账本审计通过。独立从1960旧＋1176新summary重建标签并精确复算统计；2无报警共同结局保留。
- 新增1324sim＝50＋1274，新增optimizer0；全局49507/50000sim、51200opt，技术repair0；剩余全局493，当前supplement cap余额176，不自动使用。
- 结束后现场确认8holder恢复；旧封存及失败standalone_v1保留。运行使用standalone_v2，运维修复只重绑当前lifecycle/guard及补全holder/wave/no-op身份。
- 输出文件总字节快照 258232507（采样、快照与审计等合计；不是新增模型权重）。

## Q与实测的边界

98个cut源的Q预测与配对实测源增益Pearson仅约0.145（V）、0.178（D）、0.198（P）。solo-direct平均预测相对a0为−0.0324，而完整分母实际点估计为+5.75pp；扩大自身半径并不保证Q上升，也不能由Q变化推断真实纠偏收益。未增加任何Q接受门。这些相关系数仅为描述，不能作机制因果归因。

## 参数与可复现产物

- 实际配置：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/protocols/standalone_v2/config.json`，SHA `db0a276204a35e13ad088a84e6955a005c72b7705b1663f26e67447d70b9d2b0`。
- freeze：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/protocols/standalone_v2/freeze.json`，SHA `c56083482b2b664e629cf1007ce824b26a41fead668f3fe4b1c2c0d62669f1e3`。
- `parameters.json` 保存A4000四权重身份、native10/300/50、G0 .05、alpha10/tau .3/.2/.1、XYZ/grip target .05/.10与cap .15/.40、mask余量.05、自身半径及全部种子/统计规则。
- 完整审计：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/audits/standalone_v2`；独立重算：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/independent_audits/standalone_v2`。
- 新隔离代码：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/standalone_ablation_20260918`；原freeze含代码快照。

本轮不新增训练、capture、替补、selection seal或后续wave。
