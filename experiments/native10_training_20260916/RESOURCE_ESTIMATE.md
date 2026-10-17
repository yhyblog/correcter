# Native10 训练准备：资源估算与测量方案

本文件只根据旧实验记录、文件大小元数据及当前 `df`/`/proc/meminfo` 作准备估算。**没有新增仿真、训练、GPU 工作或大 I/O benchmark；下列预计耗时不是 native10 新实测，也不是置信区间。**

## 当前主任务规模

已读取 `coordination/NATIVE10_TRAINING_TASK.md`（v1.0）及 `coordination/NATIVE10_TRAINING_ADDENDUM.md`。当前主方案为600训练、100开发、50校准、50保留，共800个预登记独立episode；P0另计。此前500–1000训练源、约3万分支的设想不能直接容纳当前候选和验证安排。

| 项目 | 计算 | 尝试上界 |
| --- | --- | ---: |
| P0技术诊断及复现 | 独立阶段上限 | 600 |
| 主episode捕获 | 800 | 800 |
| 训练标签 | 600 × 14臂 × 4后缀 | 33,600 |
| 开发局部标签 | 100 × 14 × 4 | 5,600 |
| 两轮开发策略 | 100 × 5 × 4 × 2 | 4,000 |
| 校准 | 50 × 5 × 4 | 1,000 |
| 最终保留 | 50 × 5 × 8 | 2,000 |
| 独立candidate bank恢复（新批准补充） | 1,000 | 1,000 |
| 计划 / 技术储备 / 硬上限 | 48,600 / 1,400 / 50,000 | 50,000 |

主rollout为46,200条，另外计捕获和P0。14臂是13个十步动作候选加正常continue_native10，四次后缀不构成四个独立episode；无报警、无合法cut、未到达或提前成功的预定episode仍保留分母，不能反复换seed凑满有cut源。共享完全相同候选或无报警结局可以减少实际物理次数，但必须明确复用映射。分支内前缀恢复与单独重启source replay的计费边界需按任务书记录。

三万分支仅作旧问题的算术说明：500×14×4=28,000，余2,000尚未含捕获或其他split；600×14×4=33,600本身已超限。1,000×8×4=32,000也超限；1,000×7×4=28,000虽装得下训练标签，却几乎没有完整开发/校准/保留余量。这些不是替代当前50,000硬限方案的授权。

## 旧真实测量依据

| 历史波次 | GPU / workers | 正式分支 | fixed10每分支均值 / P90（秒） | 正式活动窗口（秒） | 活动吞吐（分支/秒） |
| --- | ---: | ---: | --- | ---: | ---: |
| metaworld_small_20260916 | 8 / 8 | 600 | 6.355 / 11.071 | 598.370 | 1.003 |
| act_recap_ogg_flow_20260916 | 8 / 32 | 1920 | 6.603 / 14.686 | 888.902 | 2.160 |

这里没有归档的精确launcher起止时间。活动窗口用首条正式预算登记时间至末条分支seal文件mtime；属于旧实测记录重建，排除了之前模型加载，也可能受调度/文件时间影响。注册到末seal窗口分别为821.266秒、1116.222秒，包含注册后加载和协调，但遗漏最后进程退出；不能把这些窗口称为严格端到端性能基准。

旧Corrector混合600分支总wall为3,421.916 worker秒，其中480条fixed10为3,050.397秒（6.355秒/条），120条native50 continue_old仅3.096秒/条。**新所有分支都接native10，不能用混合均值5.703秒作为乐观基准。** 旧32-worker flow波次1,920条均接fixed10，总wall为12,678.473 worker秒。两波源和提前终止分布不同，不能把吞吐差直接归因为提高并发。

新capture也更贵：旧两批source大多首次采样后即报警停下；新训练要覆盖预定早/中/后cut、无报警及完整正常episode。300控制步的native10至多约30次VLA采样，按每5步监测约60次检查；旧native50完整episode仅约6次自然采样。本准备对完整带监测capture暂留10–30 worker秒/episode，**这是工程预算假设，不是测量**。800 captures另算；晚cut回放、渲染/特征和写盘成本需要P0修正。

## 推算耗时与GPU小时

公式：`rollout_hours = branches / historical_active_rate / 3600 × transfer_multiplier`。8-worker速率先用旧fixed10/混合分支wall比例校正；32-worker沿用旧全fixed10窗口。迁移系数预留1.25–2.0，涵盖不同状态、长失败后缀、后期cut和I/O变化，不是统计区间。

| rollout数 | workers / 8GPU | 按旧速率直接外推（小时） | 新分布预算区间（小时） |
| ---: | ---: | ---: | --- |
| 30,000 | 8 | 9.26 | 11.58–18.52 |
| 30,000 | 32 | 3.86 | 4.82–7.72 |
| 46,200 | 8 | 14.26 | 17.83–28.52 |
| 46,200 | 32 | 5.94 | 7.43–11.88 |

对当前48,600计划、最多50,000尝试，连同800 capture、P0、几次模型加载/审计及技术储备，建议先按 **8worker总计19–34小时**、或 **32worker总计8–15小时** 预留正式采集窗口。32worker只是旧配置可运行的参考，必须由新P0吞吐和一致性测量放行，不能承诺4倍加速。对应八卡预留为152–272或64–120 GPU·小时；这是8×波次wall，不是worker数乘wall，也不是CUDA核时总和。各阶段训练/选择有依赖，不能视为所有50,000尝试可一次并行完成。

CPU critic训练额外列预算：旧7,058参数四成员在80源、4,000更新下每成员约14.3–14.5秒；99源800更新约4.5–4.6秒。补充文件已固定两路径×四成员×两轮共16次成员拟合，第一轮每成员最多2,400更新、最终轮最多4,000更新，总计最多51,200次成员优化更新，batch为32个完整source，允许早停。A/B学习率分别1e-4/3e-4；B每轮重做train-only PCA并重新初始化。PCA、源bagging、辅助损失、固定检查点评分和缓存成本需要另测，不能沿用旧800步作为新预算依据。暂留0.5–2 CPU小时用于拟合、特征缓存、选择和审计，不将它计为仿真attempt；这不是保证。VLA/D冻结，小critic可优先CPU，无需为训练长期占GPU。每轮仅对离线选中的一个A/B critic做100×5×4实际开发，两轮总计4,000；不能给A/B分别执行实际开发而翻倍预算。

## 显存、主存与存储

旧单worker PyTorch峰值allocated为9,185.95MiB、reserved为9,462MiB；四worker简单合计约37,848MiB/GPU。旧32worker波次通过了整轨迹复现，但该算式未包含全部CUDA上下文和碎片，不能代替新进程NVML峰值测量。本准备没有重新查询GPU型号/容量，也没有测量新worker RSS/PSS。

当前/proc/meminfo可用主存约1.63TiB，总内存约1.97TiB；为共享主机瞬时读数，不能当本任务独享配额。按800个cut的float32观测历史/语言/动作历史直接缓存约68.9MiB，远小于逐分支图像。模型checkpoint和VLA权重共享只读；不为每worker复制完整模型，不一次载入全部轨迹。

| 历史产物 | 每分支均值 / 最大值（KiB） | 整棵输出目录大小 / 文件数 |
| --- | --- | --- |
| metaworld_small_20260916 | 86.6 / 155.0 | 61.5MiB / 2,860 |
| act_recap_ogg_flow_20260916 | 69.5 / 158.5 | 152.7MiB / 8,730 |

46,200分支按历史均值需约3.06–3.82GiB；按历史最大值逐条估算约6.98GiB。再加完整native10源、候选上下文、训练缓存/checkpoints、ledger与日志，建议轻量产物先预留20–50GiB；如保留有限审计视频/图像则50–100GiB。该储备不是磁盘写速率预测。

本机MetaWorld渲染480×480 RGB（backend源码对应证据已记录）。若每条完整300步分支都保存无压缩RGB，46,200分支约9.58TB；仅800完整source也约165.9GB。不能把压缩轨迹只有几GiB外推为全量视频也很小；视频压缩率尚未测量。按预登记小子集保留视觉，其余保留状态、命令、seed、label及hash以重建。

沿用每分支4–5个文件会产生约20–24万小文件，BF挂载的元数据延迟可能成为瓶颈。应保留可追溯分支seal，并在审计后生成训练分片/索引减少反复打开小文件；不删除旧封存产物。当前没有做大I/O benchmark。

当前`df -B1`只读快照：

```text
Filesystem                           1B-blocks          Used         Available Use% Mounted on
BF-bytefuse-arnold-recommend 11258999068426240 3777373900800 11255221694525440   1% /mnt/bn/arnold-recommend/yaohaoyang
/dev/nvme0n1p1                   3779301580800  548008931328     3039238144000  16% /tmp
```

BF-bytefuse的约10PiB是挂载呈现容量，不是已确认项目/账户配额；实际配额未核实。本机/tmp约2.76TiB可用，为共享盘，不能作为本任务独享，也不能清理无关任务文件。

## P0获阶段就绪后的测量安排

1. 所有GPU吞吐/复现probe计入P0的600和总50,000账本；本准备阶段不执行。先用新native10语义通过队列、命令、种子和物理一致性检查。
2. 保存launcher单调时钟及UTC起止，单列加载、barrier、capture、candidate bank、分支后缀、落盘/seal、审计和holder恢复；修补旧记录无法准确复原完整wave elapsed的缺口。
3. 在P0允许配额内预登记1/2/4 worker/GPU的比较；若配额不足只测最终候选配置，不追加未计费大benchmark。每个重复也算attempt，不能按更高成功率挑更快的数据。
4. 同时记录分支/秒、环境步/秒、长度分布、无报警率/cut分布、VLA调用、监测/特征耗时、GPU allocator及NVML、RSS/PSS、实际bytes/文件数和写seal耗时。
5. 根据P0的新实测速率更新主轮预计并再封存；不因无报警或早成功无限补episode。第一轮已有冻结特征后，用一次已授权小critic拟合测updates/s、缓存/checkpoint大小，再确定充分训练的wall预算。
6. 每个正式GPU波次统一通过`gpu_occupancy_lifecycle.sh run -- ...`，整波holder停算，完成/失败后恢复；不停止无关作业。

## 证据与可复核数字

- 主任务：`coordination/NATIVE10_TRAINING_TASK.md`；训练补充：`coordination/NATIVE10_TRAINING_ADDENDUM.md`；独立设计审查：`coordination/NATIVE10_PROTOCOL_REVIEW.md`。
- 旧小批量：`outputs/metaworld_small_20260916/evaluation.json`、`budget/attempts.jsonl`、`waves/development_1789568646706300246_execution.json`、`rollouts/development/*/cut*/*/replicate_*/summary.json`及邻接artifact stat。
- 旧32worker：`../ACT-RECAP/outputs/act_recap_ogg_flow_20260916/`下同名evaluation/budget/rollouts及`waves/development_1789564503483380044_execution.json`。
- 旧CPU训练：`../ACT-RECAP/outputs/act_recap_ogg_research_v3_20260916/learning/models/{inner,refit}/member_*/details.json`。
- 渲染大小：`../ACT-RECAP/src/ac_tmil/collection/metaworld_pi05.py:191`、`:512`；小critic数据维度见`../ACT-RECAP/src/ac_tmil/ogg_research_v3/learning.py:24`。
- 完整数字、计算假设、输入SHA、分支summary汇总manifest SHA与host快照：`outputs/native10_training_20260916/preparation/resource_estimate.json`。

资源层面的结论是：当前50,000上限的方案在已有八卡环境上具有实施可行性，轻量存储不是主要障碍；实际耗时取决于native10源覆盖、后缀长度和并发，需要P0实测后更新。此判断没有启动任何新阶段，也不替代阶段READY。

2026-09-16执行补记：已按分析端 `NATIVE10_RAW_BUDGET_AMENDMENT.md` 将1000次独立bank恢复从旧2400储备拨付，计划48600、剩余1400；总50000不变。上述耗时仍是覆盖总预算的宽工程外推，未转为新实测。
