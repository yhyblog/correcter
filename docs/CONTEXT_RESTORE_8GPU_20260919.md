# 在另一台 8 卡机器上恢复 Corrector 项目上下文

日期：2026-09-19。此文是迁移交接入口；没有启动实验、改写旧封存或授予新仿真额度。

## 1. 最短恢复办法

如果新机器也挂载 `/mnt/bn/arnold-recommend/yaohaoyang`，先确认下面的文件可读，再在新机器的 Codex 对话中粘贴 [恢复提示词](../coordination/CONTEXT_RESTORE_PROMPT_20260919.txt)。不需要把数十轮历史消息逐条粘贴。

如果使用 CLI，可先运行：

```bash
codex -C /mnt/bn/arnold-recommend/yaohaoyang/Corrector
```

随后粘贴提示词。若是其他界面，打开新机器上的这个工作目录后发送相同提示词即可。

文件交接恢复的是任务目标、方法、已完成工作和证据入口，不保证恢复原聊天逐字记录。CLI 的 `codex resume --all` 可以选择已有的保存会话；新机器必须能访问相应会话历史。它本身不会迁移项目、模型、环境或运行进程。Codex 本地状态通常位于 `CODEX_HOME`（默认 `~/.codex`），其中还可能包含凭据；不要把整个目录当作普通项目交接包直接覆盖或分发。[官方 CLI 说明](https://learn.chatgpt.com/docs/codex/cli)、[本地状态说明](https://developers.openai.com/zh-Hans/docs/config-file/config-advanced)。

## 2. 必须恢复的当前状态

- 原始需求：固定 VLA、D/G0，验证动作纠偏在报警后仅重规划的基础上能否再提升约 5 个百分点。
- 原 ACT-RECAP 与各轮冻结代码、数据、参数和结果保留，只读。后续主要工作位于 `Corrector`。
- native10 主工作流已经完成：600 train；dev/cal/held 各 100 episode，五任务各 20 个不同物理初态。最终固定 critic 为 A4000，主策略为完整 matched-post。
- 原独立 held 测试中，matched-post 相对 replan 为 **+9 pp，95% CI [3.25, 15]**。支持正收益，但不能声称真实收益至少 5 pp。
- 随后的 standalone 结构消融也已完成，状态为 **`complete_analysis_accepted`**。它复用已经揭晓的 held100，不能称作新的独立 held 验证。
- standalone Post / Velocity / Direct 成功率分别为 **63% / 60% / 59.25%**，replan 为 53.5%。三个 solo−replan 同属主要比较族；校正后 Post、Velocity 支持正收益，Direct 尚不确定。详细区间与逐源证据以最终报告为准。
- standalone 保留 A4000、G0、native10、一次干预与原方向公式，只去掉其他方向对半径的限制。Post / Direct / Velocity 各自生成 a0，干预点独立入口分别使用 **1 / 2 / 2** 次 VLA 采样。训练数据仍为混合候选；没有增加 Q 门或任务专用规则。
- 累计 **49,507 / 50,000 次仿真，51,200 次优化**；standalone 新增 1,324 次仿真、0 次优化。余下 493 次是历史预算余额，不构成新任务许可。
- 两轮工作均已结项。不能因为旧 READY 存在就重启旧阶段、补样本或训练。新工作由用户提出后使用新任务目录与相应协议。
- 原机器结项时已核验 8 个 holder；这是历史证据，不能替代新机器的现场检查。

按此顺序读取：

1. 工作区 [AGENTS.md](../../AGENTS.md)。
2. [standalone 最终分析报告](STANDALONE_CORRECTOR_ABLATION_20260918.md)。
3. [standalone 最终执行状态](../coordination/STANDALONE_ABLATION_EXECUTOR_STATUS.json)；以顶层最终状态和结项回执为准，里面保留的早期准备字段不是当前待办。
4. [执行交接](../coordination/STANDALONE_ABLATION_FINAL_HANDOFF_20260918.md)、[完整参数](../outputs/standalone_ablation_20260918/handoff/standalone_v2/parameters.json)、[逐源结果](../outputs/standalone_ablation_20260918/handoff/standalone_v2/per_source.csv)。
5. [原 native10 独立 held 分析](../coordination/NATIVE10_HELDOUT_ANALYSIS.md)、[原工作流结项记录](../coordination/NATIVE10_FINAL_ANALYSIS_COMPLETE.json)。
6. 需要继续研究或实现时，再读 [standalone 方法任务书](../coordination/STANDALONE_ABLATION_TASK_20260918.md) 与报告所列代码、审查和冻结索引。

这些入口的迁移校验清单为 [CONTEXT_RESTORE_20260919.sha256](../coordination/CONTEXT_RESTORE_20260919.sha256)，可在工作区根目录执行：

```bash
cd /mnt/bn/arnold-recommend/yaohaoyang
sha256sum -c Corrector/coordination/CONTEXT_RESTORE_20260919.sha256
```

此清单只校验交接入口与选定身份文件，不代替全数据、模型或运行环境审计。

## 3. 文件与环境如何带到新机器

只恢复分析上下文时，以上文档、参数、状态、结果与证据索引即可。若要执行未来新授权的计算，还需恢复实际代码、数据、权重和环境。

| 项目 | 新机器需要做的事 |
|---|---|
| 共享挂载 | 确认两机看到同一个工作区、权限正常。尽量保留原绝对路径；历史配置有绝对路径引用。 |
| 没有共享挂载 | 复制项目与所引用的依赖、模型、数据，并保留软链接目标。只复制 Git 源码不足以恢复原始结果、环境和模型。 |
| 主要目录 | `Corrector/`、`ACT-RECAP/`、`embodied-ai-workspace/`，以及它们实际引用的 `vla-corrector/`、环境和模型路径。不要遗漏点目录 `.miniforge3/`。按冻结依赖清单核对，不因目录名相似而替换版本。 |
| Python 环境 | 正式 lerobot 路径是 `.miniforge3/envs/lerobot/bin/python`，既有正式环境为 Python 3.12.13、PyTorch 2.7.1+cu126、NumPy 2.2.6。critic CPU 使用 float32、2 线程。检查新机二进制、驱动及依赖兼容性；共享目录存在不等于环境可用。 |
| 渲染与加载 | 保留 `embodied-ai-workspace/config/vla-corrector-mesa.env`、其引用的环境和 `prepare_torch_runtime.sh`。正式入口具有 Mesa/EGL、cuDNN 库顺序与 PYTHONPATH 设置，不能只设置 `CUDA_VISIBLE_DEVICES` 就假定环境相同。 |
| GPU 管理 | 保留根目录 `gpu_occupancy_guard.py`、`gpu_occupancy_lifecycle.sh`、`gpu_hold.py`，在新机器独立建立运行状态。 |

**容易漏掉的机器本地资产：VLA checkpoint 在原机 `/tmp`。** 已完成 standalone 的冻结引用：

```text
/tmp/act_recap_future_aware_20260914/checkpoint_cache/030000/pretrained_model/
```

该目录需要包含模型、config、train_config、pre/postprocessor JSON 和对应 normalizer safetensors。仅挂载工作区不会恢复原机的 `/tmp`。模型身份来自原封存：

```text
model.safetensors
size = 9354050752 bytes
sha256 = dff338a91dbe534ca3c4525ba82df9324662e3c87131f42ed6e3d1b7bf0e94d4
```

需要未来运行时，可从旧机器完整传输该 checkpoint 目录到新机器相同路径，或使用持久路径并在新协议中显式登记映射；接收后按冻结 SHA 校验。本次编写交接没有重新读取约 9.35 GB 的权重计算哈希。

A4000 四成员及其配套文件位于：

```text
Corrector/outputs/native10_training_20260916/models/final/final_fit_v1/selected/
```

其 `complete.json` SHA 为 `f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a`。保留完整选中模型目录与引用的投影、初态及训练证据，不只复制单个权重文件。

旧 freeze 含绝对路径及部分文件的 inode/device/mtime。跨机器复制即使字节一致，这些属性也可能变化。保留旧 freeze 原样；未来新授权的运行应使用独立的新机器身份记录和协议，不能伪改旧属性、跳过 SHA 守卫或直接重用旧运行目录。相同版本和随机种子也不自动证明跨 GPU/驱动结果逐位一致。

## 4. 新机器的 8 卡 holder

以下命令应在**新机器**执行，先检查状态，再在未启动时启动 guard，最后复查：

```bash
/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh status
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py start
/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh status
```

空闲 GPU 由 holder 占用；已有正式任务的 GPU 由 guard 按政策处理，不终止无关计算进程。不要迁移旧机 `/tmp/gpu_occupancy_guard/` 内的 PID、锁或运行状态。GPU 状态检查的沙箱 NVML 失败不等于驱动不可用，应核对权限。

只有未来计算任务获授权并完成相应检查后，才通过 lifecycle 运行正式命令：

```text
/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh run -- <已授权的正式命令及参数>
```

不要把本段占位符当作实验启动指令。正式波次期间停 holder，整波退出后恢复；本轮迁移上下文无需加载模型或重跑仿真。

## 5. 新会话的首次回报

新会话读完交接后，只需先给出：当前已完成什么、支持哪些结论及其边界、关键代码/模型/结果在哪里、新机器有哪些路径或环境缺口、现场 GPU 状态。分析端负责方法与统计判断，执行端负责实现、运行与整理；旧线程 ID 不自动迁移会话或建立新机协作连接。下一步具体研究工作由用户另行给出。
