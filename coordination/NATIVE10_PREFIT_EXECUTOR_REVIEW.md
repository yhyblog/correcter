# Native10 第一轮训练前预检：执行端接线与 CPU 证据

2026-09-16 17:25 UTC。独立预检接口已实现，归档回归为 **38 passed, 1 warning in 43.38s**，退出码 0。测试仅使用合成数组、CPU 算术采集桩和模拟 fit 回调；本次真实数据 PCA 拟合、真实模型 fit、优化器更新与仿真调用均为 **0**。

## 权限与执行边界

当前 live READY v5 已条件放行独立 `round1_fit_preflight`，正式 `training_round1` 仍未放行。本文记录代码与合成检查通过，不表示真实预检已经完成。执行真实预检仍须等待预登记 **300 train＋100 development 全部槽位终态**，并形成完整、静态、审计通过的数据 seal；三源 smoke 和增长中的 live bank 不可替代正式输入。合法无 cut、无报警及提前结束保留原计划分母；技术缺失不能填成失败标签。

预检配置单独冻结并绑定 READY v5；不得修改 `main_protocols/round1_v1` 的采集配置、freeze、代码或 READY v4 快照。本次未改冻结采集文件，也没有重复运行完整采集测试套件。

## 接口与防护

- `training_pipeline.preflight(config, phase, version)`：在读数据前核验冻结协议、对应独立 scope、同名 stage 映射，以及 simulator/optimizer **严格 0/0** 预算；核 READY 登记的原采集 config/freeze SHA。它不接受 ledger，不调用优化器或采集接口。
- 输入必须通过 source/bank/branch/ledger/raw/alias/后缀完整性审计，且 `scene_identity`、`replacement_chain` 为必填通过项。train/development 分开装载；阶段核查保持 300/100 主槽、替补实际 episode 身份及开发完整分母，禁止第二轮、校准和保留数据进入。
- A 保留原四成员权重与投影；B 仅在当前阶段唯一有效 train 源上拟合视觉 16／语言 8 维 PCA。预检先完成 **A/B 全部八个成员** 的 canonical 特征、13 候选概率、a0 精确零优势、固定槽位动作梯度及保存重载检查，再封存通过结果。位级一致为预登记判据；离线 float64 与在线 float32 集成汇总差异单独报告，不据结果放宽容差。
- 产物位于独占的 `outputs/native10_training_20260916/fit_preflight/<phase>/<version>/`，包含配置、输入/代码/设计绑定、PCA 诊断、两路初始化权重、八份任务分层 bootstrap 与 minibatch seed、可训练/冻结参数 mask、重载审计及完整 seal。role 为 `native10_fit_preflight_zero_updates`，`optimizer_updates=0`、`model_fit_complete=false`；PCA 拟合另行明确记录。失败保留 `failure.json`，不生成通过 seal，已有版本不可覆写。
- `training_pipeline.run(config, ledger, phase, version)`：要求独立正式训练授权及 `training_pipeline.preflight[phase]={path, seal_sha256}`。首次更新前核验预检完整文件集、阶段、manifest、输入数据、设计、代码、种子、步数、原采集绑定、两路初态、八份 bootstrap 和参数 mask。训练直接加载预检初态，**不重拟 PCA、不重读旧 warm start、不重新生成初始化**；fit 返回后再次核对实际 bootstrap 与 minibatch seed。
- `training_code_files()` 提供十二个关键实现文件的 SHA 清单。CLI 为 `python -m experiments.native10_training_20260916.training_pipeline preflight --config <独立冻结配置> --phase round1 --version <新版本>`；本次未执行此真实入口。

`config.training_pipeline` 的稳定字段为 `design`、`datasets[phase]`、`code_files`、`collection={config_path,config_sha256,freeze_path,freeze_sha256}`、`stop_after[phase]`，以及正式训练时的 `preflight[phase]`。预检与训练的协议 SHA 可以不同；上述输入和方法身份必须一致，避免产生自引用。

## 可复现 CPU 归档

归档目录：[prefit_cpu_20260916_v1](../outputs/native10_training_20260916/preparation/prefit_cpu_20260916_v1/)。2026-09-16 17:24:18–17:25:04 UTC，外层耗时 45.935 秒；相关十四个实现/测试文件在运行前后的 SHA 完全相同。

| 文件 | 内容 |
|---|---|
| [command.sh](../outputs/native10_training_20260916/preparation/prefit_cpu_20260916_v1/command.sh) | 准确工作目录、环境覆盖和 pytest 命令 |
| [pytest.log](../outputs/native10_training_20260916/preparation/prefit_cpu_20260916_v1/pytest.log) | 完整合并 stdout/stderr；38 个测试通过 |
| [result.json](../outputs/native10_training_20260916/preparation/prefit_cpu_20260916_v1/result.json) | 起止时间、退出码、运行环境、全部代码 SHA、范围与零真实计算记录 |
| [complete.json](../outputs/native10_training_20260916/preparation/prefit_cpu_20260916_v1/complete.json) | 归档文件清单与 SHA seal |

环境：Python 3.12.13、PyTorch 2.7.1、NumPy 2.2.6、pytest 9.0.3；`CUDA_VISIBLE_DEVICES=''`，OMP/MKL/OpenBLAS 各 2 线程，禁止写 pycache。日志保留一次 PyTorch autograd 的 CUDA 驱动探测 warning；CPU 测试全部通过，未执行 GPU 模型计算。

本次覆盖 pipeline 22 项与 artifact loader 16 项：独立 scope 与 0/0 gate、scene/replacement 必填、混合 train/dev 银行按用途读取、live 审计快照、完整开发分母、失败与篡改拒绝、A/B 共同先验审计、bootstrap/mask 绑定、同一初态训练及禁止重拟 PCA。没有把合成通过解释成真实数据数值审计通过。

| 关键文件 | SHA256 |
|---|---|
| `training_pipeline.py` | `8488dc82370a2dfb516d6da4f8da1e76200596194a64861a21b81a4d95788655` |
| `test_training_pipeline.py` | `b4164826cf7ff8b207dfe8bbb358fba87cc4399561ed0f1a251f92bb0f92dfd6` |
| `artifact_loader.py` | `923d5147e550beeb269e1ea168832f3b601797856de854fa6c35a4675608ecb4` |
| `test_artifact_loader.py` | `9be0cea6c5325ecb1cd6af86c46fdbb4310b7bc5cb24294e68fcbae60799d7ba` |
| CPU 归档 `complete.json` | `4a4996fa3e0cd58ef81cf6d3d6b6629b6e482121d95e33e845eaafbbdc2bbcc8` |

原采集 config SHA 为 `f68b59f279ae4d03094ebe70f0185e29d7a65a8ce20903aed92ac4392f1e4fd2`；freeze SHA 为 `f46dda706607bf8ed52281d33a203471c2854b6c09f83e6d26d3b216a509d893`。本报告读取时 live READY v5 SHA 为 `f060993392cb4e776b5d2694fc4ceb4a62ee0fbbc788f269565ef390d58cef49`；实际预检须绑定其独立冻结副本。

后续顺序仍为：完整 400 槽静态数据审计 → 独立预检配置与证据冻结 → 零优化器更新的真实预检 → 分析端复核预检 seal → 另行放行正式训练。本报告不宣称纠偏有效或独立验证成功。
