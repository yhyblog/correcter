# Native10 首轮运行审查

审查时间：2026-09-16 16:56–17:01 UTC。对象：`round1_labels / round1_labels_v1 / round1_v1_01`。本审查只读运行产物，未启动、恢复或终止任何仿真，也未修改冻结代码。

首批运行未发现协议偏差。以下是技术检查，不能作为算法有效性或成功率结论。

## 冻结与启动

- 配置：`outputs/native10_training_20260916/main_protocols/round1_v1/config.json`，SHA256 `f68b59f279ae4d03094ebe70f0185e29d7a65a8ce20903aed92ac4392f1e4fd2`。
- 冻结清单：同目录 `freeze.json`，SHA256 `f46dda706607bf8ed52281d33a203471c2854b6c09f83e6d26d3b216a509d893`，包含 747 个逐文件 SHA 项和 1 个已流式核验后核对 stat 的大权重项。独立重算了本轮 collector、runner、scene、shell、config、READY、任务书等 15 个匹配项，均一致；未为本次审查重复读取全部大权重。
- 冻结 READY 为 v4，只释放 `round1_native10_local_labels` 与初始化替补 scope；训练、第二轮、校准、heldout 均未放行。
- 400 个主槽明确为 300 个 round1 train + 100 个 development；没有初始化 calibration/heldout。
- `main_execution/round1_labels/round1_labels_v1/round1_v1_01/wave_spec.json` 为 8 GPU、32 worker、`hold_idle=false`。
- 16:56:48 从 `/proc` 读取到 32 个真实 worker。抽查祖先链为 worker → supervisor → `run_recap_gpu_wave.py` → `gpu_occupancy_guard.py run` → `gpu_occupancy_lifecycle.sh run`；生命周期祖先门已实际通过，之后才加载模型。此时账本仍为 P0 564 次，没有把模型加载计为仿真。

## 首批实物检查

17:00:27 UTC 的固定快照包含 34 个 scene registry 记录、34 个封存 source。对该快照逐一检查，以下各项均为 34/34 通过：

1. `initial_scene/complete.json` 和 source `complete.json` 的文件 SHA 完整性。
2. 从 `initial_scene/state.npz` 重算完整 exact state hash、按注册单位和精度重算物理 canonical scene hash，与 identity 和 registry 一致。
3. 初始化记录 `control_steps=0`、`before_first_policy_action=true`、`privileged_critic_input=false`；对应账本项为该 episode 的 `source_capture`，账本时间不晚于 scene 文件生成。
4. 每个 source 实际 `generated_steps` 与 `actual_sampling_steps` 均为 0、10、20…；`source_horizon=10`。
5. 所有保存的合法锚点队列均 `age=5`、`remaining_steps=5`；`requested_cut/actual_cut/selection_reason` 按已批准固定优先序重算一致。

34 个 `(task, scene_fingerprint)` 全部唯一且 accepted。该快照未使用替补 reserve。

切点构成为 12 个 `scheduled_target_reached`、17 个 `first_legal_alarm`、4 个 `scheduled_prior_anchor_fallback`、1 个 `no_alarm_training_anchor_fallback`。这些是采集协议状态计数，不是成功/失败分组。可复查实例：

| Source | 请求/实际切点 | 实测证据 |
|---|---:|---|
| `shelf-place-v3__2026111007` | 15 / 15 | 采样步 `[0,10]`；source attempt 565，bank restore 566 |
| `disassemble-v3__2026111015` | 45 / 45 | 采样步 `[0,10,20,30,40]` |
| `shelf-place-v3__2026111027` | 95 / 95 | 采样步从 0 到 90，每次间隔 10 |
| `pick-place-wall-v3__2026111026` | 95 / 45 | 原源运行到第 58 步；按 `95→45→15→5` 选已保存的 45 |
| `shelf-place-v3__2026111022` | first alarm / 15 | 完整原源 300 步无报警，训练按 `15→5` 取 15 |

实例路径前缀均为 `outputs/native10_training_20260916/sources/`。注册 case 中历史 `cut_rule.fallback=none_pending_analysis_review` 字段保留用于身份不变；有效策略由冻结 bank 的 `cut_selection_policy=analysis_lead_v1` 和 source 明示 selection audit 决定。本轮真实 fallback 与后者一致，不能把历史说明字段误读为运行规则。

另抽查第一个 bank `banks/round1_labels_v1/shelf-place-v3__2026111007/cut015`：slot0、same noise、raw bank audit 均通过，raw a0 最大绝对值约 5.437 的原始饱和坐标保留。其 normal 分支 `continue_native10/repeat_0` 从 cut15 执行剩余 5 步，首次后缀采样为 20，随后 30、40；suffix seed/noise SHA 已写入记录。这里只核查实际语义，没有统计各臂成绩。

## 预算顺序和限制

冻结 `main_collection.py:296` 在 `runtime.reset(...,10)`（301 行）之前 reserve 并写入 attempt；scene 捕获位于 305 行，早于语言编码、提案和环境动作。`storage.py:81` 的预算锁与 104–107 行追加/fsync 保留并发尝试记录。运行实物的 attempt/scene 关联与此顺序一致；文件时间只能辅助印证，不能代替冻结代码的先后关系。

17:00:27 快照账本为 1238 次 = P0 564 + round1_labels 674；round1 上限 23200、reserve 上限 1200、全局上限 50000。17:01 前检查 worker 日志未见 Traceback/Error。采集仍在进行，本文不代表全阶段通过；真实 dataset 审计、完整分母、配对标签及模型训练放行均仍需后续独立检查。
