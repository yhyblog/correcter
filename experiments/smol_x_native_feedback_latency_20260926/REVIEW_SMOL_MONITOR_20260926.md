# SmolVLA 34.947 ms 监测延迟复核

复核日期：2026-09-26。仅检查现有代码、MODEL_READY、输入快照与原始时序；没有启动模型、追加推理或修改已有结果。

结论：原始记录可以复算出 34.947 ms；现有证据没有显示少算视觉帧、少执行 D/G0 成员或只记录异步 GPU 提交时间。这个数字表示预热后的、独立运行的原生视觉反馈路径，不是完整 VLA 动作采样，也不是与策略同时运行时的反馈耗时。

## 原始时序复算

读取 `workers/worker_0` 至 `worker_3` 的 `latency.jsonl`，排除 `warmup=true`。每个 case 为 100 次调用、20 个不同 context。

| case | 外层墙钟均值 ms | 反馈内部 service 均值 ms | 策略内部 service 均值 ms |
|---|---:|---:|---:|
| N | 151.583206 | — | 151.491620 |
| monitor | 34.947057 | 34.862565 | — |
| parallel_feedback_no_intervention | 171.167614 | 47.916112 | 170.864886 |

独立 monitor 的 100 条外层墙钟范围为 **33.348538–37.720188 ms**，外层墙钟减反馈 service 的均值为 **0.084492 ms**。并行 case 的反馈 service 范围为 **46.325879–54.434424 ms**；其 **47.916 ms** 均值不能用独立运行的 **34.947 ms** 替代。

例如 `worker_0/latency.jsonl` 的 `MECH1_test_disassemble-v3_000`、repetition=0、monitor 原始值为 `wall_seconds=0.03537983074784279`、`feedback_seconds=0.03528697229921818`。数字单位和汇总口径一致。

来源：[worker 0](workers/worker_0/latency.jsonl)、[worker 1](workers/worker_1/latency.jsonl)、[worker 2](workers/worker_2/latency.jsonl)、[worker 3](workers/worker_3/latency.jsonl)。

## 五帧与两对辅助网络确实位于计时路径

- [contexts.json](contexts.json) 的 20 个实际 NPZ 中，`frames` 形状均为 `(5,480,480,3)`，`props` 均为 `(5,4)`。`model.py:73–78` 读取这些原始 RGB/本体快照；没有读取其保存的视觉特征。
- `smol_native.py:93–101` 遍历五组 frame/prop，每次执行独立反馈预处理器、原生 `prepare_images` 和 `native.embed_image`，然后拼接。没有视觉特征缓存、跳过帧分支或仅取当前帧的分支。每帧图像按当前 checkpoint 配置调整为 512×512，原生视觉塔加 connector 产生 64×960 tokens，并保留原生前缀的平方根缩放。
- `model.py:98–111` 每次继续执行 4×4 池化、固定随机 960→256 通道投影、4096 维历史构造和旧计划五步动作输入。`model.py:113–115` 遍历两个 world/gate 对，每对先 D 再 G0。
- 四个 Smol worker 的 MODEL_READY 均记录 D 参数量 `[4474116,4474116]`、G0 参数量 `[1468033,1468033]`，与 `model.py:45–47` 创建的两个成员一致；原生视觉维度均记录为 64×960。

代码：[model.py](model.py)、[smol_native.py](smol_native.py)。运行元数据：[worker 0](workers/worker_0/MODEL_READY.json)、[worker 1](workers/worker_1/MODEL_READY.json)、[worker 2](workers/worker_2/MODEL_READY.json)、[worker 3](workers/worker_3/MODEL_READY.json)。

## GPU 完成时间没有被排除

`model.py:97` 将完整监测提交到反馈专用 CUDA stream；第 116 行把最终 G0 输出传回 CPU，第 117 行显式等待该 stream 完成，然后才返回。`worker.py:32–35` 在函数返回后记录 service 结束；第 41 行等待 future 返回，第 49 行记录外层墙钟结束。因此这里不是只测 GPU kernel 入队，也没有把五帧视觉提前移到计时外。

两个并行操作使用不同 CUDA stream；并行 case 在 `worker.py:43–48` 同时释放两个工作线程并等待两个结果。171.168 ms 来自外层真实墙钟，不是把两项均值相加或取最大值计算出来的。并发提交不保证所有 GPU kernel 完全重叠；47.916 ms 的反馈 service 已包含这次同卡竞争带来的实际变化。

## 为什么可明显短于原生策略 151.583 ms

`native.embed_image` 只执行原生视觉塔和 connector，见 [smolvlm_with_expert.py:179](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/projects/upstream/lerobot-smolvla-8fff0fd/src/lerobot/policies/smolvla/smolvlm_with_expert.py:179)。完整策略除了视觉编码，还执行图像/语言前缀 transformer，并进行 10 次动作去噪，见 [modeling_smolvla.py:818](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/projects/upstream/lerobot-smolvla-8fff0fd/src/lerobot/policies/smolvla/modeling_smolvla.py:818)。五次视觉编码不能等同五次完整 VLA 采样；两条路径的计算量不同。

本次原生视觉编码使用 BF16 autocast，视觉输出直接留在 GPU 上进入池化、投影及 D/G0。旧外部 π0.5 特征路径保留 FP32 视觉塔，并先把逐帧视觉输出传回 CPU，再送回 GPU 做特征处理，随后还有外部服务通信和上下文构造。证据为 [旧 feature_path.py:143](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code/feature_path.py:143)、[旧 adapter.py:394](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/adapter.py:394) 及 [π0.5 视觉精度设置](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code/vendor_vla/src/lerobot/policies/pi05/modeling_pi05.py:406)。这些是速度不同的合理结构原因；当前没有分项 profiler，不能定量判定各因素贡献，也不能把跨批次差异全部归因于编码器。

## 计量边界

任务语言 embedding 均值在 `prepare` 中缓存，见 `model.py:79–85`；每次监测仍执行五次原生预处理器，但不重复计算该任务 embedding 均值，不执行 VLA 语言主干或动作采样。输入磁盘读取、模型加载和预热也不属于本次查询墙钟。

D/G0 是按原有宽度和成员数新建的随机网络，归一化为零均值、单位尺度，未训练；固定通道投影也未训练。这是结构计算开销测试，不是已适配原生特征的有效收益预测器。34.947 ms 不含 Q、动作梯度或纠偏。输入为预录真实快照，测试没有环境步进或机械臂闭环。现有记录没有逐层 kernel profiler；本复核确认的是代码路径、实际输入形状、运行元数据与完成后墙钟的一致性，不提供尚未测得的视觉/D/G0 分项耗时。
