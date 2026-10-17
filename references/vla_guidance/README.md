# VLA纠偏与critic引导论文资料库

整理日期：2026-09-19。用于Corrector分析端的文献定位、公开结果查询和实验规划。

- [公开结果与可比性汇总](REPORTED_RESULTS_20260919.md)
- [下载来源、文件大小及SHA-256](manifest.json)
- [当前参数口径与必要验证](../../docs/PARAMETER_EFFICIENT_CORRECTOR_PLAN_20260919.md)
- [总实验计划](../../docs/Experiment_plam.md)

| 简称 | 固定版本 | 论文 | 本地PDF | 原始来源 |
|---|---|---|---|---|
| VLA-Corrector | v1，2026-07-02 | VLA-Corrector: Lightweight Detect-and-Correct Inference for Adaptive Action Horizon | [PDF](VLA-Corrector_2607.01804v1.pdf) | [arXiv](https://arxiv.org/abs/2607.01804v1) |
| QGF | v1，2026-06-09 | Test-Time Gradient Guidance of Flow Policies in Reinforcement Learning | [PDF](QGF_2606.11087v1.pdf) | [arXiv](https://arxiv.org/abs/2606.11087v1) |
| QPILOTS | v1，2026-06-11 | QPILOTS: Efficient Test-Time Q-Steering for Flow Policies | [PDF](QPILOTS_2606.14801v1.pdf) | [arXiv](https://arxiv.org/abs/2606.14801v1) |
| GAF | v3，2026-08-23 | Guided Action Flow: Q-Guided Inference for Flow-Matching Vision-Language-Action Policies | [PDF](GAF_2607.02092v3.pdf) | [arXiv](https://arxiv.org/abs/2607.02092v3) |
| GAF历史版 | v1，2026-07-02 | 同题；早期LIBERO实验 | [历史PDF](historical/GAF_2607.02092v1.pdf) | [arXiv](https://arxiv.org/abs/2607.02092v1) |

GAF v3是真机设置，v1包含早期LIBERO结果，分开保存。其文中也使用QGF简称；资料库中的“QGF”专指Zhou等的2606.11087，“GAF”专指Yang等的2607.02092。

PDF保存的是原论文，不是本项目的工作。文件下载后检查PDF标头并计算SHA-256；未修改内容。更新版本时新增带版本号文件，不覆盖历史PDF。

公开论文数据可免复现地用于文献成绩表；它们不是本项目同协议运行结果。具体可比性、未报告项和原文口径差异见汇总文档。
