# VLA-Corrector、QGF、QPILOTS、GAF：公开结果与可比性汇总

整理日期：2026-09-19。用途：查询可直接引用的论文成绩、确定需要本地验证的最小对照，避免重复复现不承担本文结论的完整系统。

论文和固定版本见[资料库索引](README.md)，下载来源与校验值见[manifest](manifest.json)。本项目实验范围见[总计划](../../docs/Experiment_plam.md)和[参数口径与必要验证](../../docs/PARAMETER_EFFICIENT_CORRECTOR_PLAN_20260919.md)。

## 1. 使用口径

- 下列数值均为原论文报告值；“增量”是本文件用表内数值相减得到的百分点（pp）。成功率用百分数，不把pp写成相对提升百分比。
- 可以将这些数值用于带有“论文报告结果”标识的文献表；只有任务、底座checkpoint、观测、训练数据、评测分布、horizon和预算一致，才可以组成直接排名。
- “NR”表示在本次核对的论文/官方材料中未找到明确数值，不代表数值为零，也不代表作者从未公布。
- QGF指Zhou等的2606.11087；GAF指Yang等的2607.02092。GAF正文也使用QGF简称，引用时以题名和arXiv编号消歧。
- GAF v3真机结果与v1仿真结果分开列，不能把两版组合成同一个模型的完整实验。

当前Corrector结果为π0.5、MetaWorld五任务、native10、100个物理源×4后缀、最多一次干预；standalone是在已揭晓held上的结构消融。Post 63%、Velocity 60%、R 53.5%不能与下表中跨任务/跨协议数值直接排名。

## 2. 快速定位：哪类数据可以拿来用

| 工作与固定版本 | 主要实验对象 | 可直接摘录的数值 | 最适合本项目的用途 |
|---|---|---|---|
| VLA-Corrector v1 | MetaWorld、LIBERO、PiPER真机；多个VLA底座 | 成功率、horizon、组件、容量、推理成本表 | 最近邻系统定位；提示截断与纠偏必须分开；引用其容量曲线 |
| QGF v1 | OGBench上的flow策略，非VLA | 配置表；主要成绩和计算量在图中 | 引用算子先例；作为本地同critic的引导/GradStep参照 |
| QPILOTS v1 | OGBench；π0.5在六个LIBERO-90任务上在线学习 | 逐任务成绩、单任务时延表 | 引用VLA上的Q引导与成本；保留在线数据预算区别 |
| GAF v3 | SmolVLA、单项真机放瓶任务 | 成功/失败次数、视觉干扰小样本成绩 | 引用真机可行性；不能代替广任务仿真验证 |
| GAF v1，历史 | SmolVLA、LIBERO子集 | 单任务、验证和held结果 | 查早期仿真证据及负结果，必须注明历史版本 |

来源分别为各节链接的原论文；本表不是统一基准榜单。

## 3. VLA-Corrector v1

[原文](https://arxiv.org/html/2607.01804v1) · [本地PDF](VLA-Corrector_2607.01804v1.pdf) · [官方代码](https://github.com/ZJU-OmniAI/vla-corrector)

### 3.1 主表和组件结果

| 原文位置 / 设置 | 底座或比较项 | Baseline SR | Corrector SR | 增量 |
|---|---|---:|---:|---:|
| Table 1，MetaWorld | π0.5 | 48.70 | 64.35 | +15.65pp |
| Table 1，MetaWorld | SmolVLA | 61.90 | 66.65 | +4.75pp |
| Table 1，MetaWorld | X-VLA | 55.55 | 59.60 | +4.05pp |
| Table 2，LIBERO，few-shot底座 | π0.5，四suite平均 | 94.00 | 97.80 | +3.80pp |
| Table 5，PiPER真机 | π0.5，九任务平均 | 55.6 | 73.3 | +17.7pp |

Table 6的π0.5组件链：baseline **48.70** → 仅截断 **60.35** → 截断+OGG **64.35**。因此该表的OGG增量是相对仅截断的 **+4.00pp**，不能将完整系统+15.65pp全部归因于纠偏。[来源：Tables 1、2、5、6](https://arxiv.org/html/2607.01804v1)

MetaWorld评测为每任务20 episodes；附录时延统计按每底座1,000 episodes报告。Table 1/6的Avg是四个difficulty列的等权均值，不宜当成全部episodes直接合并的成功率。PiPER为九任务、每方法每任务20次。不同表的均值、配置和统计口径按原文保留。

### 3.2 π0.5固定horizon扫描

| H | Baseline SR | Corrector SR | Baseline calls/episode | Corrector calls/episode |
|---:|---:|---:|---:|---:|
| 10 | 64.50 | 72.40 | 20.41 | 17.64 |
| 20 | 61.40 | 69.10 | 10.77 | 9.95 |
| 30 | 56.10 | 63.50 | 7.97 | 7.92 |
| 40 | 54.45 | 60.80 | 5.96 | 6.04 |
| 50 | 48.72 | 58.70 | 5.15 | 4.98 |

来源：[Table 4](https://arxiv.org/html/2607.01804v1)。calls是episode平均调用数，不是每次调用耗时。该H=50结果与Table 1/6完整系统64.35不同，不能互换作为同一配置的成绩。

### 3.3 容量与运行成本

| 原文位置 | 配置 | 报告结果 |
|---|---|---|
| Table 9 | Corrector 10M / 40M / 160M | SR 56.58 / 64.35 / 64.28 |
| Table 11，π0.5 | 无OGG → 有OGG | 推理时间2.49 → 4.03秒/episode，1.62× |
| Table 11，SmolVLA | 无OGG → 有OGG | 2.13 → 3.51秒/episode，1.65× |
| Table 11，X-VLA | 无OGG → 有OGG | 1.54 → 2.59秒/episode，1.68× |
| §D.3，汇总调用 | 标准调用 → OGG调用 | 278.01 → 588.52ms/call，约2.12× |

来源：[Table 9、Table 11、§D.3](https://arxiv.org/html/2607.01804v1)。外接MLP实际规模随输入维度约38–42M；资源说明为8张A100 SXM4 40GB。episode推理时间不是包含机器人/仿真等待的总墙钟时间；汇总调用时间也不能当作π0.5专属测量。

对本项目的含义：可以引用“该工作报告40M与160M表现接近”，但不能据此证明本项目28.2K比其40M性能更好。其LVM同时承担动力学监测与引导，与本项目Q单模块功能不同；本项目外接D/G0/Q总计约11.9M。

### 3.4 引用时保留的边界

- 其方法允许多次截断，含cooldown；本项目当前为每episode最多一次干预。
- Figure 7的恢复指标是十步内监测量回到阈值以下，不是最终任务成功率；不要转写为“最终成功率提高23pp”。
- Table 3满训练比例结果54.32、Table 4的H=50结果58.70、Table 1结果64.35分别保留表号。数据划分文字也有“20%验证”与附录“10%验证+10%测试”的差异，复现前需明确选择。
- 官方仓库README明确不提供数据集、微调底座权重、训练后corrector checkpoint和实验日志；可引用论文成绩，不能假定下载代码即可无成本获得同一系统。[论文](https://arxiv.org/html/2607.01804v1)、[仓库](https://github.com/ZJU-OmniAI/vla-corrector)

## 4. QGF v1

[原文](https://arxiv.org/html/2606.11087v1) · [本地PDF](QGF_2606.11087v1.pdf) · [项目页](https://q-guided-flow.github.io/) · [官方代码](https://github.com/zhouzypaul/qgf)

### 4.1 已核对的可复用配置

| 项目 | 原文信息 |
|---|---|
| 策略/环境 | OGBench上的flow行为克隆策略；不是VLA |
| 主实验 | 20任务、10 seeds、500K离线更新 |
| 较难goal-conditioned实验 | 25任务、1M离线更新 |
| Actor / critic | MLP隐藏层[1024,1024,1024,1024]；critic ensemble=2 |
| 采样 | 通常action horizon=5，flow steps=10；puzzle-4x6有horizon例外 |
| 附录I GradStep | 完整动作采样之后做梯度上升，比较多步改进 |
| 精确critic总参数 | NR；不能用整套actor/critic缩放图的规模标签替代 |

来源：[实验部分、Tables 1–2、Appendix I](https://arxiv.org/html/2606.11087v1)。

### 4.2 成绩与计算量的可引用程度

主要成功率、计算量、容量结果位于Figures 5–9、11–12。此次没有定位到可直接下载的完整逐点数表或原始评测CSV；**未将曲线/柱高估读成精确成绩**。如果论文需要其精确逐任务数值，优先索取作者结果；只有必要时才做明确标注为digitized的图像读数，并记录误差，不能写成作者精确报告值。[原文图表](https://arxiv.org/html/2606.11087v1)、[仓库](https://github.com/zhouzypaul/qgf)

本项目可以直接引用其方法和公开图示结论；没有OGBench主张时，无须为凑比较表重跑其全部任务。需要证明本项目局部学习优于普通引导时，在本项目同数据、同critic、同幅度/预算下实现对应算子，并命名为“QGF-style / GradStep，同协议适配”。这不能冒充原论文完整QGF系统。

## 5. QPILOTS v1

[原文](https://arxiv.org/html/2606.14801v1) · [本地PDF](QPILOTS_2606.14801v1.pdf) · [实验室论文页](https://leaf.utias.utoronto.ca/publication/ruan-2026-qpilots/)

### 5.1 六个LIBERO-90任务的论文成绩

底座为在LIBERO-40微调的冻结π0.5，约3B；另进行500K在线环境步学习、5 seeds。下表沿用原文Task ID，全部为SR（%）。

| 方法 | 26 | 31 | 38 | 59 | 60 | 64 | 原文Mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| π0.5 | 6 | 14 | 32 | 19 | 50 | 36 | 26 |
| DSRL | 36 | 22 | 70 | 93 | 95 | 34 | 58 |
| Best-of-N，N=5 | 10 | 19 | 53 | 35 | 66 | 57 | 40 |
| EXPO | 7 | 29 | 55 | 28 | 62 | 52 | 39 |
| CGQL-LinEx | 11 | 12 | 25 | 27 | 64 | 49 | 31 |
| QPILOTS-U | 43 | 55 | 91 | 82 | 99 | 89 | 76 |
| QPILOTS-M | 41 | 42 | 78 | 87 | 98 | 86 | 72 |

来源：[Table 3](https://arxiv.org/html/2606.14801v1)。该表沿训练进度做时间加权EMA（α=0.99），再跨seed平均，报告训练末端结果；不是预先冻结checkpoint后单次独立held成绩。原文另有跨seed bootstrap 95% CI，本摘录仅列点估计。Mean保留原文，不能用已取整的六个任务数重新平均后“修正”。

### 5.2 Task 59单任务时延表

| 方法 | SR（%） | 原报推理耗时（ms） | 原文相对时延 |
|---|---:|---:|---:|
| π0.5 | 19.2 | 112.7 | 1.00× |
| Best-of-N，N=5 | 36.4 | 127.2 | 1.14× |
| Best-of-N，N=10 | 41.4 | 137.0 | 1.22× |
| Best-of-N，N=20 | 45.5 | 158.0 | 1.44× |
| QPILOTS-U | 83.3 | 114.1 | 1.04× |
| QPILOTS-M | 88.5 | 240.1 | 2.14× |

来源：[Table 5，RTX PRO 6000](https://arxiv.org/html/2606.14801v1)。原文字段为Inference-time，正文称single-step inference/per time step；完整调用所含环节未充分列明，不直接等同于本项目定义的完整chunk采样入口时延。

原文倍数与表内毫秒除法并非完全一致：例如U的114.1/112.7≈1.012，BoN20的158.0/112.7≈1.402。本表保留原文两列，不能把原文1.04×当作由这组毫秒数精确计算所得。Table 3和Table 5的Task 59成绩也不同，不能拼成同一评测批次。

### 5.3 参数与训练成本口径

| 项目 | 原文信息 |
|---|---|
| Critic | 10成员；CNN视觉编码+三层128宽MLP；精确总参数NR |
| QPILOTS-U | 无额外MFM；通过速度网络求导 |
| QPILOTS-M | 另有MFM，宽512、8 blocks、8 heads；精确参数NR |
| MFM预训练 | LIBERO-90公开示范，40K updates，batch 256，约2天/单H100 |
| LIBERO训练时间 | U约6h，M约8h；不能擅自补成同一GPU上的严格成本对照 |
| 生成/执行设置 | flow steps=10，action horizon=10 |

来源：[实现细节与附录](https://arxiv.org/html/2606.14801v1)。不能只引用M的在线8h而漏掉MFM预训练，也不能据此声称本项目比VLA微调高效。

本次未在论文、作者页及实验室页定位到可直接使用的官方复现仓库、训练后checkpoint或原始评测结果下载。这是检索状态，后续可更新。[作者页](https://sunlighted.github.io/)、[实验室页](https://leaf.utias.utoronto.ca/publication/ruan-2026-qpilots/)

## 6. GAF v3：当前真机版本

[原文](https://arxiv.org/html/2607.02092v3) · [本地PDF](GAF_2607.02092v3.pdf) · [公开项目仓库，版本覆盖见第10节](https://github.com/ylhaichen/guided-action-flow)

### 6.1 结果

| 原文位置 / 设置 | Frozen SmolVLA | Guided | 增量 |
|---|---:|---:|---:|
| Table II，放瓶入盒 | 19/40 = 47.5% | 34/40 = 85.0% | +37.5pp |
| 同一无扰动实验，timeout数 | 13/40 | 3/40 | — |
| Table III，场景加入黄色卷尺作为视觉干扰物 | 0/11 = 0% | 6/12 = 50% | +50pp |

来源：[Tables II–III](https://arxiv.org/html/2607.02092v3)。timeout是失败的一部分，不是额外一类总样本；视觉干扰实验仍为放瓶入盒，两组样本量不同。

### 6.2 训练与评测条件

| 项目 | 报告信息 |
|---|---|
| Critic数据 | 100 episodes，47成功/53失败，8,917 chunks |
| 划分 | episode级90/10；训练/验证chunks为7,970/947 |
| 模型 | 单Transformer critic，3层、宽256、4 heads；另有训练用value网络 |
| 参数/部署成本 | 精确参数、毫秒时延、FLOPs、GPU小时均NR |
| 动作 | chunk为50×8，控制15Hz |
| 引导 | β=2，梯度范数clip=1 |
| 超时 | 180秒，自首个实际动作开始计时；不含首次动作生成等待 |

来源：[方法与实验协议](https://arxiv.org/html/2607.02092v3)。

**数据独立性限制：** critic开发数据为episodes 17–116，baseline组77–116位于该范围内；guided组118–157为后续批次。因此85%对47.5%是其报告的顺序批次对比，不能转述成“同状态配对、完全独立held”的结果，也不能把guided组说成训练数据。

## 7. GAF v1：历史LIBERO结果

[历史原文](https://arxiv.org/html/2607.02092v1) · [历史PDF](historical/GAF_2607.02092v1.pdf)

| 设置 | Baseline | GAF | 增量 |
|---|---:|---:|---:|
| 单任务，seed 3000 | 34/50 = 68% | 41/50 = 82% | +14pp |
| 单任务，seed 4000 | 41/50 = 82% | 43/50 = 86% | +4pp |
| Spatial验证 | 32/60 = 53.3% | 最好不超过31/60 ≈51.7% | 未提高 |
| 多任务家族，validation | 23/50 = 46% | 28/50 = 56% | +10pp |
| 多任务家族，held-out | 26/40 = 65% | 27/40 = 67.5% | +2.5pp |

来源：[GAF v1实验](https://arxiv.org/html/2607.02092v1)。多任务配置用500个采集episodes训练，含332成功；三个MLP critic，宽768、深4。它与v3的单Transformer真机critic不同，不能套用v3模型结构解释v1成绩。held-out只有40次，+1次成功应连同分母报告。

## 8. 哪些公开资产能减少复现工作

截至整理日的核对结果：

| 工作 | 可用入口 | 不能据此默认已获得 |
|---|---|---|
| VLA-Corrector | [官方代码](https://github.com/ZJU-OmniAI/vla-corrector)、论文完整数表 | README明确排除的数据、底座微调权重、corrector checkpoint、日志 |
| QGF | [官方代码](https://github.com/zhouzypaul/qgf)、[项目页](https://q-guided-flow.github.io/)、论文图表 | 本次未找到公开原始逐点结果和可下载训练后checkpoint；README的本地输出路径不等于下载链接 |
| QPILOTS | [论文页](https://leaf.utias.utoronto.ca/publication/ruan-2026-qpilots/)、论文数表 | 本次未定位官方代码/权重/原始结果入口 |
| GAF | [代码](https://github.com/ylhaichen/guided-action-flow)、论文数表；可用SmolVLA公开底座 | 仓库旧LIBERO配置不等于v3真机数据/训练后critic；本地critic.pt说明不等于公开下载 |

由此安排本项目的最低必要工作：

1. **文献表直接用上面的原文结果。** 逐行标任务、底座、版本、来源表号和“reported”，不为重画已有成绩而重跑四套系统。
2. **核心方法对照在本项目内部统一。** 当前优先普通重规划、同数据的BCE/局部差监督，以及收益/异常两种触发器。方向、约束和搜索大矩阵已退出当前总计划；只有新增对应主张时才补必要对照。
3. **优先已有公开工程，在共同原始数据上训练各自网络。** 用户已本地复现VLA-Corrector；当前E3据此安排它及一个公开critic引导近邻。训练需求与字段清单见[总计划E3](../../docs/Experiment_plam.md)。保留各方法动态/TD/回归目标；仅改成共同critic或BCE时明确标“style/adapted”，不能称完整原法复现。
4. **小参数卖点对应准确的参数口径与真实效果。** 当前只主张小型critic能够有效纠偏，报告Q参数、D/G0/Q全外接参数和实际时延；不默认增加大小模型非劣实验。只有明确新增“小模型保持大模型性能”的主张才安排公平容量对照。外部论文NR项留空，不根据层宽猜一个总参数量放进主表。
5. **不设置VLA微调效率主张。** 已报告的外部成本只帮助理解方法代价，不承担本项目未进行的微调对照结论。

## 9. 建议论文呈现方式

正文使用本项目同协议实验表，明确区分Post和Velocity。另附一张“相关工作的已报告设置与结果”表，选取本文最相关的行，保留任务范围与数据预算，不进行跨协议加粗排名。

当前用参数及效果表说明小型critic，不将容量曲线列为必做。VLA-Corrector的10M/40M/160M曲线可作为独立文献材料；不要把本项目28.2K/Q成功率点与其40M/LVM成功率点连成一条Pareto曲线。

资料库仅归档论文与证据。本轮没有启动训练、仿真、推理计时或standalone重跑；后续执行需另行冻结任务书与资源预算。

## 10. 代码与同数据训练核查补充（2026-09-19）

VLA-Corrector和QGF代码已公开；GAF公开项目仓库当前可确认早期LIBERO管线，v3真机Transformer完整实现尚未确认；QPILOTS在论文、实验室页及作者页仍未定位官方代码。仓库链接见上表。

GAF v1使用首次成功时间折扣得到的success-to-go及MSE，v3改为Transformer与IQL，不能混称同一种训练目标。QGF原实现使用chunk-level IQL；QPILOTS的原LIBERO协议包含在线数据，M另有教师蒸馏。因此共同终局成功率摘要不能自动满足全部方法；共同原始轨迹需要保留实际转移、动作、奖励、成功时刻、next观测及终止/截断。[GAF v1](https://arxiv.org/html/2607.02092v1)、[GAF v3](https://arxiv.org/html/2607.02092v3)、[QGF](https://arxiv.org/html/2606.11087v1)、[QPILOTS](https://arxiv.org/html/2606.14801v1)

本地VLA-Corrector的训练资产与共同数据适配安排已写入总计划，不因官方仓库不发权重而误判本地没有已完成复现。新的对照结果与论文原报成绩、既有复现成绩分开标识。
