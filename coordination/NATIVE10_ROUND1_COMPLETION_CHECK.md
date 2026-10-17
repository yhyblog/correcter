# Round 1 收尾独立核查

核查时间：2026-09-16 19:43:11 UTC。结论：本次运行收尾元数据核查通过，未发现技术阻塞。

本核查只读取运行、封存、账本、场景登记和 GPU guard 元数据；未汇总方法胜率、选赢家、运行仿真或训练。以下结果不替代另行进行的完整 dataset/trajectory 静态审计，也不构成算法有效性结论。

路径基址 `R = /mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916`；波次路径 `W = R/main_execution/round1_labels/round1_labels_v1/round1_v1_01`。

## 波次与完整分母

- `W/launch_result.json`：`status=complete`、`returncode=0`，整波包含生命周期管理，`hold_idle=false`，`next_stage_automatically_started=false`。包括生命周期的 wall 为 7834.784906 秒。
- `W/workers/worker_*/status.json`：32/32 complete，rank 恰为 0–31，16 个 worker 各分配 13 槽、16 个各分配 12 槽。400 个唯一主槽与冻结 bank 注册清单完全相同，没有漏槽、重复分配或替补记录。各 worker 的 config/freeze SHA 与实际冻结文件相同。
- 400 个 slot 记录及 collection 终态完整：300 train、100 development。对每槽核对 collection `complete.json` SHA、其中 `summary.json` SHA 和引用的 source seal SHA；均一致。全部 `planned_episode_retained=true`、`outcome_filter_applied=false`、`source_replaced=false`。
- 395 源有 cut，每源 56 个真实分支，共 22120 个分支记录；5 源为合法 development 无报警/no-cut，0 个伪造 critic 输入、0 个分支，均保留完整正常结局供共同结局广播。因此后续政策效果统计仍须保留全部 400 个计划主槽对应的分母，训练与开发各按其原始分组统计。

5 个合法 no-cut 的 source ID：

| Source ID | 终态选择原因 |
|---|---|
| pick-place-wall-v3__2026111616 | no_alarm_policy_common_outcome |
| pick-place-wall-v3__2026111631 | no_alarm_policy_common_outcome |
| stick-pull-v3__2026111653 | no_alarm_policy_common_outcome |
| shelf-place-v3__2026111657 | no_alarm_policy_common_outcome |
| pick-place-wall-v3__2026111671 | no_alarm_policy_common_outcome |

这些源的 `actual_cut=null`、`full_episode_outcome_available=true`、无合法首报警，且 development 不允许 training fallback。核查没有据结局替换任何源。

## 预算与场景

`R/budget/attempts.jsonl` 共 23479 行；`number` 连续覆盖 1–23479 且唯一，`(stage, kind, identity, resource)` 组合也全部唯一。

| 阶段/类别 | 实际计费 attempts |
|---|---:|
| P0 | 564 |
| Round 1 source_capture | 400 |
| Round 1 candidate_restore | 395 |
| Round 1 branch_including_restore | 22120 |
| Round 1 合计 | 22915 / 23200 |
| 全部合计 | 23479 / 50000 |

训练更新为 0，technical_reserve 为 0。账本中仅有 `p0` 和 `round1_labels` 两个仿真阶段，当前账本计数与已完成 source、bank、branch 数量一致。

`R/scene_registry/entries.jsonl` 恰有 400 个 accepted，episode 集合与本轮 400 主槽相同，400 个 `(task, scene_fingerprint)` 均唯一，`replacement_of` 全为 null。逐条核对 initial_scene seal SHA 与对应 source_capture 账本编号，均通过。没有重复场景、替补或缺口。

按冻结联合 manifest 检查后续注册身份（含每主槽的两条 backup）：calibration 300、heldout 300、round2 train 900；这些身份的 `R/sources/<episode_id>` 目录均不存在，scene registry 与账本也没有后续阶段初始化记录。没有自动启动下阶段。

## GPU 生命周期

读取 `/tmp/gpu_occupancy_guard/status.json`：guard PID 26616 存活，记录距核查时间约 2.00 秒；GPU 0–7 均为 `holder`，8 个 holder manager 进程均存在。仅检查现有状态与进程，不启动、停止或发送信号给任何 GPU 作业。

## 输入身份与审计边界

| 输入 | SHA256 |
|---|---|
| W/launch_result.json | 371d52fe1366a115a489863916960342e9ceb0ab2f282b8c4b35dc27055fe0eb |
| W/wave_spec.json | ae00774876ad54e6b3f1d901a74f05f57aca07b4f90fda1f58bde82a90c873a0 |
| R/budget/attempts.jsonl | 59366c2e08f34f1914b721e16111d1324b07cad187eab343efc21a460576d44f |
| R/scene_registry/entries.jsonl | ffb5abdf935645485604d0af9c43990ac7ebce87e9c921de70ef9d0cba39d497 |
| R/main_protocols/round1_v1/config.json | f68b59f279ae4d03094ebe70f0185e29d7a65a8ce20903aed92ac4392f1e4fd2 |
| R/main_protocols/round1_v1/freeze.json | f46dda706607bf8ed52281d33a203471c2854b6c09f83e6d26d3b216a509d893 |

这里只核查终态覆盖、相关 seal 引用、预算与物理场景登记；没有重跑测试，也没有重复读取全部 rollout trajectory。完整 dataset 审计与后续训练放行由执行端另行处理。本文件是新增独立记录，既有封存产物未修改。
