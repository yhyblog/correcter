# π0.5 / MetaWorld 文献基线核查（2026-09-22）

**关键纠正：目前直接相关的 VLA-Corrector 原文并不支持“H=10只有40%多”。其 Table 4 的 H=10 原始π0.5成功率是64.50%。**

| 执行H | VLA-Corrector论文 Baseline SR% | 当前本项目 N SR% |
|---:|---:|---:|
| 10 | 64.50 | 61.60 |
| 20 | 61.40 | 48.00 |
| 30 | 56.10 | 41.00 |
| 40 | 54.45 | 41.00 |
| 50 | 48.72 | 39.20 |

左列来源：[原文Table 4，PDF第8页](https://arxiv.org/pdf/2607.01804v1#page=8)；右列是本地 `deadline_20260924/MAIN_FINAL_CELLS_WITH_COSTS.csv`。这些只是定位参照，不能作为同协议排名。H10我们的61.6%较文献64.5%低2.9pp，而不是异常超过文献约40%的基准。

**40%多的容易混淆出处：**Table 1的平均48.70%；Table 3明确写H50、48.72%；Table 1的Very Hard单组是41.0%。不能把这些字段改称H10全MetaWorld。[Table 1/3，PDF第6–7页](https://arxiv.org/pdf/2607.01804v1#page=6)。Table 1的48.70恰为四难度列(70.5+45.0+38.3+41.0)/4；不能默认等于50任务等权的分母口径。

## 协议已知与未知

- 原文H定义为每次生成后实际执行动作数；与生成chunk长度C区分。[§2，PDF第3页](https://arxiv.org/pdf/2607.01804v1#page=3)
- 原文按四难度组报告、每任务20 episodes；Table 13明确50任务。因此不是本项目旧五任务开发集。[§C.1，第17页；Table 13，第19页](https://arxiv.org/pdf/2607.01804v1#page=17)
- 作者官方README示例为n_action_steps10、chunk_size50、episode_length300、每任务20、seed1000；这里是公开示例，不能据此断言论文每一表均用了该命令。README明确不提供数据、微调VLA权重、corrector checkpoint或原始日志。[官方Evaluation/Data and Checkpoints](https://github.com/ZJU-OmniAI/vla-corrector#evaluation)
- 已核论文/README没有明确给出该π0.5 MetaWorld底座的SFT更新步数、精确checkpoint身份、逐源seed表、renderer和控制频率/动作scale。当前本地030000是我们保存的复现底座，**不能写成已证明与作者底座相同**。官方示例中的seed1000也不等于我们主表500个哈希新test seeds。
- 本项目当前固定30Hz控制/400Hz物理、动作scale.015、NVIDIA EGL、每任务10新源；上述原文缺项不能擅自补齐。即使H相同，绝对成功率仍不可要求逐点相等。

## 另外三篇不能佐证“π0.5＋MetaWorld H10都是40多”

| 工作 | 原文实际对应实验 |
|---|---|
| [QGF，§6/附录A](https://arxiv.org/html/2606.11087v1) | OGBench flow策略离线RL，不是π0.5-MetaWorld主表。 |
| [QPILOTS，§5.2](https://arxiv.org/html/2606.14801v1) | π0.5在6个LIBERO-90任务上的在线critic学习；不同环境与数据范围。 |
| [GAF v3，Table II](https://arxiv.org/html/2607.02092v3) | 47.5%=19/40，底座SmolVLA、真实机器人放瓶，不是π0.5-MetaWorld。 |

目前这四篇中没有查到另一条“π0.5＋MetaWorld、执行H10、统一协议约40%”的原文证据；若用户指具体其他工作/第三方复现，需按其具体表号核查，不能先假设与我们的61.6%可比。

本地文献已存在：`Corrector/references/vla_guidance/REPORTED_RESULTS_20260919.md` §3.2早已摘录Table 4；此次再次核对arXiv原文HTML/PDF页码和官方仓库。未启动任何模型、仿真或新实验；未改共享文档/controls。
