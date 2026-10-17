# MetaWorld 五臂小批量执行报告（2026-09-16）

本报告由冻结的 evaluation.json 自动汇总。15 个新源、每源 8 次配对续跑、5 臂；这是一轮当前五任务环境下的小批量比较。独立统计单位为源，不能把每臂 120 条续跑当成 120 个独立样本。

## 实际结果

| 执行臂 | 成功数 / 120 | 成功率 % | 相对 replan 增益 pp（95% 区间） | 救回 / 损害 | 正 / 负 / 零收益源 |
|---|---:|---:|---:|---:|---:|
| continue_old | 31 / 120 | 25.83 | — | — | — |
| replan | 66 / 120 | 55.00 | 0.00 [0.00, 0.00] | 0 / 0 | 0 / 0 / 15 |
| velocity_matched | 64 / 120 | 53.33 | -1.67 [-2.50, 0.00] | 0 / 2 | 0 / 2 / 13 |
| direct_matched | 67 / 120 | 55.83 | 0.83 [0.00, 2.50] | 3 / 2 | 1 / 0 / 14 |
| post_matched | 66 / 120 | 55.00 | 0.00 [-2.50, 2.50] | 2 / 2 | 1 / 1 / 13 |

| 预登记比较（前者减后者） | 增益 pp | 名义 95% 区间 pp | 救回 / 损害 |
|---|---:|---:|---:|
| velocity_matched − replan | -1.67 | [-2.50, 0.00] | 0 / 2 |
| direct_matched − replan | 0.83 | [0.00, 2.50] | 3 / 2 |
| post_matched − replan | 0.00 | [-2.50, 2.50] | 2 / 2 |
| direct_matched − velocity_matched | 2.50 | [0.00, 5.00] | 3 / 0 |
| post_matched − velocity_matched | 1.67 | [0.00, 5.00] | 2 / 0 |
| post_matched − direct_matched | -0.83 | [-2.50, 0.00] | 1 / 2 |
| replan − continue_old | 29.17 | [16.67, 45.00] | 38 / 3 |

本轮三种纠偏均未达到相对 replan 至少 +5 pp 的点估计目标。
所有区间均以完整源按任务分层 bootstrap 10,000 次（seed=29015），未做多比较校正。每任务只有 3 个源；应结合区间与救回/损害解释，不能据小批量最高点估计宣称已独立验证成功。

continue_old 保留报警时原 50 步队列直至自然耗尽，其后按正常 50 步周期生成；它保留原始策略命令。replan/纠偏执行 10 步有界前缀，随后 fixed10。因此 replan−continue_old 同时包含报警时中断、50→10 周期及可能的命令后处理差异，不能解释成单一报警重规划动作的净效应。

## 逐任务与逐源证据

| 任务（各 3 源 × 8 次） | old % | replan % | velocity % | direct % | post % |
|---|---:|---:|---:|---:|---:|
| disassemble-v3 | 0.00 | 100.00 | 100.00 | 100.00 | 100.00 |
| pick-place-wall-v3 | 12.50 | 33.33 | 33.33 | 33.33 | 33.33 |
| shelf-place-v3 | 16.67 | 33.33 | 33.33 | 33.33 | 33.33 |
| stick-pull-v3 | 0.00 | 8.33 | 0.00 | 12.50 | 8.33 |
| stick-push-v3 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 |

完整逐源、逐 replicate 二元结局见 [per_source.csv](../outputs/metaworld_small_20260916/report/per_source.csv) 和 [per_source.json](../outputs/metaworld_small_20260916/report/per_source.json)。未丢弃无报警源。
本轮报警源 15 / 15，无报警源 0 / 15。

## 这批结果对机制问题的回答

三种纠偏相对 a0 的所有配对结局变化都集中在 stick-pull 的两个源（2026106003、2026106013）；其余四个任务结局不变。direct 的净增益仅为最后一个源多成功 1 次；post 的救回与损害抵消。因此本批没有稳定支持哪种纠偏优胜。
critic 对三种纠偏的平均预测提升均约 +10 pp，而真实提升为 −1.67、+0.83、0 pp。a0 平均预测成功率为 56.81%，实际为 55.00%；整体均值接近并不能证明候选间的相对评分或梯度可靠。
本批不支持仅通过替换 flow 注入方式就能解决问题：direct 没有达到收益目标，绕开 flow 积分的 post 也没有额外净收益。更需要排查的是候选相对评分与真实结局的脱节，以及十步局部扰动何时足以改变结局。这是结果支持的排查方向，不能据此唯一认定评分梯度方向错误：本轮未执行反向/随机物理对照，且共同可行半径在部分源收缩。没有零 XYZ 源或引导 fallback，不能把负结果解释为纠偏根本没有执行。

## 技术检查与预算

26 项 CPU 检查通过，提取核心逐位重建 30 组历史候选。五源 25 分支预检检查了零 alpha 等价、真实采样器线性目标梯度符号、同初始噪声、指定 a0 固定、状态/图像还原、共同扰动幅度及 old/fixed10 实际采样时刻。8 个正式 worker 各复现一条预检 a0，完整轨迹、图像及采样 seed 逐位一致后才捕获正式源。
正式冻结时间：2026-09-16T14:23:54.788391+00:00；冻结时正式源不存在，参数未按预检或正式结局修改。

| 预算项目 | 实际登记次数 |
|---|---:|
| source_capture | 20 |
| preflight | 25 |
| concurrency_check | 8 |
| development | 600 |
| 合计 / 硬上限 | 653 / 700 |
| 重复身份次数 | 0 |

失败/重复尝试均由启动前账本计数；未运行 100 源验证。GPU 波次均使用生命周期包装器且 hold_idle=false，整波期间占卡停止，结束后恢复。恢复证据见输出目录 audits/executor_gpu_final.txt。

## 固定参数与实现

冻结 VLA、D/G0（阈值 .05、每 5 控制步检查）、四成员 v3 critic（1041–1044）；未训练。critic 输入固定状态，槽 0 始终为指定 a0，只对槽 1 候选求导。目标为四成员成功概率平均差。
Flow 时间 1→0，十次 Euler，dt=−.1；alpha=10，仅 tau=.3/.2/.1。velocity 注入 v−alpha*tau*g，direct 注入 v−alpha*g；post 在采样终点使用 S²∇aR，S=(q99−q01)/2。direct 是 QGF 式适配；post 不在 flow 积分内部注入。
最终实际命令采用共享 mask（1−|a0|≥.05）与共同可行半径；XYZ RMS=.05、Linf=.15，夹爪 RMS=.10、Linf=.40，容差1e−6。五个方向 velocity/direct/post/reverse/random 均参与共同半径计算；本轮仅执行前三种纠偏，不执行 reverse/random/native 对照。完整动作50步，仅前10步纠偏，之后清队列并用冻结 fixed10；总控制预算300步。
预检种子 2026105900–2026105904，正式种子 2026106000–2026106014，五任务轮转，每任务3源。相同源/切点/重复号/决策序号种子；old 的自然采样时刻不同，不能声称其所有决策状态均同初始噪声。
完整参数见 [config.json](../outputs/metaworld_small_20260916/config.json)，预登记协议见 [PROTOCOL.md](../experiments/metaworld_small/PROTOCOL.md)。

## 预测、幅度和耗时诊断

| 纠偏 | critic 平均预测增益 pp | 实际增益 pp | 预测正、实际负的源数 |
|---|---:|---:|---:|
| velocity_matched | 10.05 | -1.67 | 2 |
| direct_matched | 10.13 | 0.83 | 0 |
| post_matched | 10.87 | 0.00 | 1 |

Q 上升不等同于真实救回。old 使用不同后缀，未将 fixed10 critic 输出当作 old 成功率预测。

- xyz：零幅度源 0，共同半径收缩源 10。
- gripper：零幅度源 2，共同半径收缩源 4。
- velocity：fallback 源 0。
- direct：fallback 源 0。

| 计时项 | 每源平均秒 |
|---|---:|
| 原生 base 候选生成 | 0.2122 |
| 原生 velocity 候选生成 | 0.2450 |
| 原生 direct 候选生成 | 0.2338 |
| post_gradient_seconds | 0.0028 |
| source_restore_seconds | 0.9627 |
| candidate_bank_seconds | 0.7362 |
| generation_wall_seconds | 1.6989 |

candidate_bank_seconds 排除状态回放，包含上下文加载、全部候选生成、评分和写盘；generation_wall_seconds 还包含回放。post 的单次梯度耗时不能代表当前 matched 方法部署成本，因为共同半径依赖其他 flow 方向。这些是本批硬件/并发条件下的测量，不是独立线上延迟基准。

## 复现与交付

原始轨迹、生成候选和每次预算登记都在 [outputs/metaworld_small_20260916](../outputs/metaworld_small_20260916/)。技术审计在 audits/；所有训练依赖与原 ACT-RECAP 只读。
复现结果汇总（不新增仿真）：

```bash
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector
CUDA_VISIBLE_DEVICES='' bash scripts/run_metaworld_small.sh evaluation evaluate
python coordination/EXECUTOR_REPORT.py
```

仿真入口与各阶段顺序已记录在 PROTOCOL.md，实际 wave spec 存于 waves/；不要对完成的波次盲目重启，以免额外计入预算。冻结代码快照为 provenance/frozen_runtime_code.tar.gz。

- 参数 SHA256：`b9bad6420031267d45d2ed30862a49f0a06a049f6bf981ae302774e2987f8328`
- 正式冻结 SHA256：`bc151464e5f3250f83e42a77eb480b9577375ee0052ec89a2dbde80c6377631b`
- evaluation SHA256：`c1d9353113d4410d373bc586c7137f0e2303ab98d025bce15521b5af74e72ca0`

执行端独立复核已确认全部600条分支、75行逐源CSV、七组比较及置信区间一致；见 [EXECUTOR_INDEPENDENT_REVIEW.json](../coordination/EXECUTOR_INDEPENDENT_REVIEW.json)。原 ACT-RECAP 的272个源文件和正式冻结的290个代码文件哈希保持不变。

执行端已提交原始产物供分析端独立复核。本轮结论仅适用于这组冻结方法、15个新源和当前MetaWorld设置。
