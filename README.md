# Corrector

## GitHub 版本

本仓库保存代码、配置、文档、结果汇总及小型核心资产。完整实验记录见 [EXPERIMENT_RESULTS_MASTER.md](docs/EXPERIMENT_RESULTS_MASTER.md)，论文采用的数据见 [EXPERIMENT_FOR_PAPER.md](docs/EXPERIMENT_FOR_PAPER.md)。

原始实验输出、大型模型检查点、逐步轨迹、视频和本机运行缓存不随 Git 上传；所需文件仍保存在原实验工作区。下文描述的是完整工作区，部分历史结果路径及外部环境依赖需要另行准备，具体排除规则见 [.gitignore](.gitignore)。

从 ACT-RECAP 分离出的冻结 critic 纠偏核心、2026-09-16 的完整 flow 实验产物，以及当前 MetaWorld 小批量比较入口。原仓库保留，历史结果按字节复制并校验。

## 三种纠偏方式

令 `u = x_tau - tau * v`，`R` 为四个冻结 critic 的平均成功概率增益，`g = ∇u R(T(u))`。`T` 包含原动作反归一化和真实 clamp 导数，Euler 的时间步为负。

| 方式 | 原生更新 | 实现 |
|---|---|---|
| velocity | `v' = v - alpha * tau * g` | `src/corrector/guidance.py` |
| direct（QGF 式适配） | `v' = v - alpha * g` | `src/corrector/guidance.py` |
| post（采样后终点修正） | 在 a0 上求 `S² ∇a R(a0)`，作为命令空间方向 | `post_direction`，同一文件 |

post 是第三种纠偏方式，不在 flow 积分内部注入。评分始终以指定 a0 为固定参照，不在候选之间重设参照。

实验执行的是 **matched** 版本：`candidates.construct` 在 XYZ 和夹爪两组中分别匹配 RMS、施加 Linf 和边界限制。共同半径仍取 velocity、direct、post、reverse、random 五个方向共同可行范围；本轮只省去反向和随机方向的物理 rollout。这一依赖不能删去，否则已改变上一轮算法。完整 post matched 的生成成本也不等于单次 post 梯度耗时。

## 目录

- `src/corrector/`：独立数值核心，不导入 `ac_tmil`。
- `assets/critic/`：四个冻结 critic、原配置与模型哈希。
- `assets/action_transform/`：VLA 动作变换所需的归一化参数。
- `tests/`：梯度、动作匹配和与原实现的数值等价检查。
- `results/reference_flow_20260916/`：上一轮完整 flow 结果，包含逐分支轨迹、源观测和审计。
- `docs/reference/`：原结果报告、协议及分析；历史 100 源计划只留档，本轮不运行。
- `provenance/`：原关键代码快照、复制清单与 SHA256。
- `experiments/metaworld_small/`、`configs/`、`scripts/run_metaworld_small.sh`：新小批量实验适配器。
- `coordination/`：分析端和执行端的任务、就绪记录及运行状态。
- `outputs/metaworld_small_20260916/`：新实验输出；与历史结果分开。

## 使用现有环境检查核心

```bash
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector
PYTHONPATH=src /mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -m pytest tests -q
```

核心依赖 NumPy、PyTorch、safetensors，检查还需要 pytest。通过 `FrozenSelector(assets_dir=...)` 可指定资产目录；在本源码目录运行时默认使用这里的 `assets/critic`。安装到其他位置时需显式传入资产路径；权重和历史结果不包含在 Python wheel 中。动作变换可通过 `ActionTransform.from_checkpoint('assets/action_transform', device='cpu')` 加载。

**分离边界：** 纠偏核心、critic 和历史结果已复制到这里；MetaWorld 执行适配器仍复用本机 ACT-RECAP 的环境/观测/状态回放接口，以及既有 VLA、G0 模型、LeRobot/Mesa 环境。大型 VLA 与环境不重复打包。实验适配器不等同于可直接搬到另一台机器运行的完整环境镜像。

## 本轮小批量

五个原任务各 3 个新源，共 15 源；每源 8 次配对续跑，共 5 臂：

1. `continue_old`：不响应 G0 中断，执行原队列至自然耗尽，再按原 50 步周期正常采样。
2. `replan`：报警时仅重规划，10 步后接 fixed10。
3. `velocity_matched`。
4. `direct_matched`。
5. `post_matched`。

共 600 条正式续跑，连同预检/捕获/并发复现预计 653 次，硬上限 700。原模型和超参数冻结，不根据中间结果追加采样。

`continue_old` 给出“不因报警重新规划”的完整基线，仍允许原策略在队列耗尽时正常规划。它保留原始队列命令及环境原有处理；四个干预分支的前 10 步仍按上一轮协议裁剪到 [-1,1]。因此 old 与 replan 的差异包含控制周期由 50 变为 10 和前缀命令处理的影响；三种纠偏与 replan 的比较才隔离局部纠偏的新增效果。统计单位是 15 个源，不能把每臂 120 次续跑视为 120 个独立场景。

操作与协作约定见 [执行任务](coordination/EXECUTOR_TASK.md)。正式运行前以 `coordination/ANALYSIS_READY.json` 和冻结协议为准，最终是否已经开始/完成以执行端状态及实际输出为准。
