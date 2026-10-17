# 首轮 B200 五臂实际开发测评：执行交接

本轮技术验收通过。三种纠偏相对仅重规划分别增加 **2.00、2.75、2.50 个百分点**，尚未达到约 +5pp 目标，三项源级 95% CI 均跨 0。本轮使用参与过选模的开发初态，不能称独立验证成功。

固定 B200 四成员、原100个开发 episode（五任务各20个不同物理初态）。95个原cut各生成新bank、五臂各4个配对后缀；5个无报警源沿用已知共同结局（4成功1失败），每臂总体分母400。无源筛选、capture、替补、技术失败或重试。

## 真实成功率与配对比较

| 方法 | 成功/400 | 成功率 |
|---|---:|---:|
| normal native10 | 221 | 55.25% |
| replan | 257 | 64.25% |
| velocity | 265 | 66.25% |
| direct | 268 | 67.00% |
| post | 267 | 66.75% |

| 比较 | 增益pp | 源级95% CI（pp） | 救回/损害 | 正/负/零源 |
|---|---:|---|---:|---:|
| replan − normal native10 | +9.00 | [2.75, 15.50] | 52/16 | 18/8/74 |
| velocity − replan | +2.00 | [-2.00, 6.25] | 19/11 | 7/5/88 |
| direct − replan | +2.75 | [-0.75, 6.50] | 20/9 | 9/4/87 |
| post − replan | +2.50 | [-1.25, 6.50] | 20/10 | 9/4/87 |
| velocity − normal native10 | +11.00 | [4.25, 17.75] | 57/13 | 19/6/75 |
| direct − normal native10 | +11.75 | [5.00, 18.75] | 59/12 | 20/6/74 |
| post − normal native10 | +11.50 | [5.00, 18.25] | 58/12 | 19/5/76 |

区间采用固定五任务内整源等权有放回 bootstrap（10,000次，seed=2026091622，NumPy default_rng.choice，percentile95）。源内4次后缀保持配对，不作为4个独立初态；七项区间未做多比较校正。救回/损害按400对逻辑结局计数，正负零按100个源的平均差计数。

| 任务（各20源/80逻辑结局） | normal | replan | velocity | direct | post |
|---|---:|---:|---:|---:|---:|
| disassemble-v3 | 85.00% | 76.25% | 83.75% | 83.75% | 82.50% |
| pick-place-wall-v3 | 55.00% | 86.25% | 88.75% | 87.50% | 87.50% |
| shelf-place-v3 | 26.25% | 28.75% | 28.75% | 28.75% | 31.25% |
| stick-pull-v3 | 22.50% | 30.00% | 30.00% | 35.00% | 32.50% |
| stick-push-v3 | 87.50% | 100.00% | 100.00% | 100.00% | 100.00% |

disassemble 的纠偏增益主要在弥补中断重规划造成的损害：normal85%，replan76.25%，三纠偏仍为82.5%–83.75%。pick-place-wall 的系统提升主要来自重规划；stick-push 的replan已为100%。这些任务差异用于解释结果，不据此改阈值或筛负例。

仅95个有cut源（每臂380）时，normal/replan/V/D/P成功数为205/241/249/252/251；纠偏额外增益为2.11/2.89/2.63pp。全100源分母仍是主要报告口径。逐任务全部七比较与alarm条件分层见补充result.json。

## 梯度、实际命令与评分诊断

95个bank中a0/V/D/P均为4个不同raw命令组：没有a0别名或仅clip后表示碰撞。V/D/P最终前10步命令的XYZ及gripper RMS同幅差均小于冻结1e-6容差；raw尾段、mask外恒等及C(raw)映射检查全部通过。XYZ无零组，gripper有2个零组；79个XYZ组、14个gripper组按既定可行匹配规则缩小。三臂平均XYZ RMS约0.041884、gripper RMS约0.093956；无guidance fallback、无提前结束导致的不足10步干预prefix。

18个源的53/950个原a0夹爪命令超过[-1,1]（最大绝对值1.025901），原raw值保留；评分使用同一C(raw)=clip(raw)映射。这里只报告本轮命令与表示检查，不将历史有限物理探针扩大为普遍物理等价。

| 方法（95个cut） | 平均预测ΔQ | 实测平均Δ成功率 | Q增益与实测Pearson | Q正且真实正/负/零源 |
|---|---:|---:|---:|---:|
| velocity | 0.04635 | +2.11pp | 0.116 | 7/5/83 |
| direct | 0.05332 | +2.89pp | 0.050 | 9/4/82 |
| post | 0.05421 | +2.63pp | 0.020 | 9/4/82 |

三种路径的Q均在95/95源上升，却仍有真实损害；生成候选上的评分幅度与实测收益关系较弱。direct/post点估计比velocity高0.75/0.50pp，尚不足以把问题单独归因于梯度进入flow的方式。这些描述更支持继续审查局部收益监督与评分判别能力，但本阶段没有正反/随机新臂，不能宣称已经因果定位为评分方向错误。不重新选B200，不新增接受阈值或自动挑本轮赢家；下一方法与阶段由分析端判断。

## 修复、随机流和部署边界

准备期v1留存了新guard缩进错误及30 passed/1 failed日志。后缀测试的合成case缺task/env_seed，在suffix_seed身份检查中报错，尚未执行索引断言。修复补齐合法身份，保留原采集器index=len(suffix)零基连续语义；审计拒绝跳号/重复，并核原seed及跨臂同repeat/index噪声。v1→v2另增加原slot lock，不能称仅改测试。v2为31项通过；最终48项（29guard+14runner+5audit）及另13项prepare通过。旧冻结依赖保持原SHA。

实际worker入口为create_policy_collector→collect_existing_slot；manifest绑定原100dev及95旧cut/5共同结局。新bank由B200重新生成，首分支前核对旧新raw50 a0、base seed、initial-noise hash、mask，并核新bank内部最终raw同幅。禁止capture、初始化替补和旧guided动作复用；本轮账本仅candidate_restore及branch_including_restore。

a0随机流键为designated_a0/episode/cut/index0；后缀为branch_suffix_decision/episode/cut/repeat/decision_index。方法、critic、bank和worker不进入采样seed。正常臂先完成cut时旧native10队列，干预臂执行新的10步prefix，之后均按native10；后缀按决策索引配对，不要求绝对采样时刻相同。旧bank seed只作身份参照，主要推断限本轮新五臂，不增oldcritic第六臂。

## 审计、资源与成本

主审计通过，独立重聚合通过115,658项检查，100×5×4逐次结局及全部主统计完全一致；24,857条实际后缀seed/noise核对通过。
新增仿真1995=95次独立bank恢复+1900分支（分支内恢复已计入），低于2100阶段上限；累计25474/50000次仿真。优化累计19200，本阶段及审计均0更新；资源字段由账本分别计数，44674条记录不是44674次仿真。8GPU holder已恢复。

正式波次8GPU×4worker，含lifecycle墙钟875.16s（约14.59分钟）。worker初始化（含输入校验、torch/CUDA初始化及模型加载）均值172.82s，中位172.39s，范围169.21–178.86s。
95个bank的均值：restore1.070s、candidate_bank1.387s、generation wall2.493s；generation wall包含restore。1900分支累计wall13393.184 worker-s，normal/replan/V/D/P每分支均8.281/6.959/6.692/6.648/6.665s。base采样均0.5174s，V0.4282s、D0.4108s；post记录的0.003262s仅为额外梯度步骤，不能当作完整策略推理成本。计时受共享base、执行顺序、并发和提前成功长度影响，组件有重叠，不能据此宣称相对串行或4倍加速。

本阶段新增banks/rollouts/collections/guard/wave产物共156,729,873逻辑字节（149.47MiB；不含复用的原source、模型及本报告）。逐项文件数与字节见runtime.json。

## 复现与精确身份

正式GPU命令已归档于preparation/policy5_execution_v1/command.sh；该命令是执行证据，已完成输出不可重复覆盖。只读重聚合命令见preparation/policy5_audit_execution_v1/command.json，输出须使用新的空目录。独立重聚合脚本policy5_independent_audit_v1.py，补充脚本policy5_cost_diagnostic_v1.py，报告脚本policy5_delivery_report_v2.py均位于experiments/native10_training_20260916。

| 产物（均在工作流outputs下） | SHA256 |
|---|---|
| [policy_protocols/round1_policy_v1/config.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_protocols/round1_policy_v1/config.json) | `56d0d31f1722f0cc1a974303219953e7340e7887f94c6d760c90739f3b64b06e` |
| [policy_protocols/round1_policy_v1/freeze.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_protocols/round1_policy_v1/freeze.json) | `54600fd9210fbb6cea17b4d67c6687d4da5c35476870331121ce6ab9819b6eb0` |
| [models/round1/round1_fit_v1/selected/complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/models/round1/round1_fit_v1/selected/complete.json) | `931c6f6043db92b5d9003eb2833dfc8edd0ab6c860a1979db3983cd7d893725f` |
| [models/round1/round1_fit_v1/selected_reload_audit.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/models/round1/round1_fit_v1/selected_reload_audit.json) | `ce43fc0888f807ef048612ad733795bc1ad5aef24103f0ed89e3c1d51c4beb7b` |
| [preparation/policy5_inputs_v1/complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/policy5_inputs_v1/complete.json) | `9bc90fb1b0dc6e9a55837b4dc898959e2435d1197778dbf0af8c73d206b58ac3` |
| [preparation/policy5_runner_cpu_20260916_v1/complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/policy5_runner_cpu_20260916_v1/complete.json) | `a7c1e190f76e863e94e37a2b7613a5075449d5b3c74dcd0355c5d6aeedec7da0` |
| [preparation/policy5_prepare_cpu_20260916_v1/complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/policy5_prepare_cpu_20260916_v1/complete.json) | `87d3b28547ddcbcc77eb6c634258fa9f0391f473001fadb4b321433fddb8a43e` |
| [policy_audits/round1_policy_v1/complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_audits/round1_policy_v1/complete.json) | `4bfadd48f1ee23b8a9e616d8517364ec69e3d96efe22c59d8ff3d2a0322cf701` |
| [policy5_independent_audits/round1_policy_v1_independent/complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy5_independent_audits/round1_policy_v1_independent/complete.json) | `7f11a12d453ba8071ef9ccf07bb9bbf0d150f2925f166cb8f90190087c5e4f1a` |
| [policy5_cost_diagnostics/round1_policy_v1/complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy5_cost_diagnostics/round1_policy_v1/complete.json) | `2794a827e559ee8782dd540462e583d0bf8c38eefe49ceed75259c45de8ad595` |
| [preparation/policy5_execution_v1/complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/policy5_execution_v1/complete.json) | `94c45b392fcdb572e0e17ae07c4a53b8109546faec8550a39c3b886c4911847f` |
| [preparation/policy5_audit_execution_v1/complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/policy5_audit_execution_v1/complete.json) | `b09ecec73e50efa44393551447939a872f6e49c7aa0f5b3feacfe7f09659937d` |

参数以冻结config.json为准：G0=0.05；native执行horizon10、生成50；总控制上限300；flow alpha10、时刻0.3/0.2/0.1；可行mask边界余量0.05；XYZ RMS目标0.05/L∞上限0.15，gripper RMS目标0.1/L∞上限0.4，matched容差1e-6。保持原真实clamp导数及接受语义，无新增Q阈值。

本报告记录已经完成的一次开发测评。round2、cal、held未自动启动，保留全量负结果与异常证据；下一阶段等待分析端按现有协作授权发布明确协议。
