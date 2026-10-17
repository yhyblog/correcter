# A10_PV_OFFLINE_PREFLIGHT_CPU_V1 — CPU_READY，真实计算未执行

| 项目 | 可用 / 缺口 |
|---|---|
| 因果输入 | V3 step0 RGB/proprio + raw_plans[0]；既有 n=1 合同采用 00001 mask、前四帧/历史动作零填充、remaining=1。step1 不参与。t0 不是报警 cut。 |
| 特征 / Q | 同 SFT030000 编码器；视觉 4096、语言 2048；固定空间投影及四成员各自 checkpoint 内 norm/PCA 已绑定 SHA/维度。Q 条件不需要 D/G0。A4000 为五任务兼容诊断，不代表 MT50 适配。 |
| 锚点 / 噪声 | raw50 足以提供 bounded b 和原始位模式；不需要逆推出缺失的内部 50×32。噪声只存 SHA，按冻结 seed2026091901、原 torch.normal、float32[1,50,32] 重建；真实 SHA 尚待验证，不符立即停止。 |
| CPU 检查 | 28 项通过；380 代码文件、33 外部源身份。未 import Torch/NumPy、未 dlopen/查询 CUDA/EGL/NVML、未跑模型/环境、未查停 holder、未 hash 大权重、未删除。 |

未来单次报价：加载 **1 个 PI0.5 + 4 个 CPU Q**；缓存锚点 Post **1 次动作梯度**；Velocity **1 次 guided sampling / 10 flow / 末三步 3 次动作梯度**。Q 共 **10 次 ensemble objective = 40 次成员前向**，每次成员前向包含锚点和候选两个 slot；4 次动作 autograd，16 个成员反向路径为派生计数。10 次 objective 已包含 1 锚点评分、Post 梯度/最终评分各1、Velocity 梯度/局部后评分各3、最终评分1。

编码调用另计：视觉 **4**（Q真实帧1 + guided真实/两填充相机3），语言 embedding **2**，prefix transformer **1**，action expert **10**；成员特征变换4、空间投影1。各分支投影一次，最终约束审计各重放一次，共4次自身投影/2次审计，不增加模型调用。无 Q 接受门、无共享半径；C10/尾40/零扰动 raw 位模式按原函数保留。部署口径仍 Post=1完整采样、Velocity=2；本报价仅缓存数值诊断。

加载器会吞加载异常；本入口记录原有一次权重读取和一次 strict state-dict 载入，缺失/异常即拒绝，不额外载入或推理。未来固定 A GPU UUID GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe / PCI 0000:0f:00.0，NVML身份查询2、Torch properties1；全部环境/reset/graphics/物理/rollout/D/G0/训练/重试/删除0。

估算显存40 GiB、RAM64 GiB、新增盘2 GiB，非实测。子进程 timeout1800s、TERM后30s KILL；父层完整SHA、reservation、进程组清理和最多120s恢复观察另计，端到端无严格有限上界。真实入口完整大权重SHA共2遍；本轮0遍。全A8 holder 保持停算至整个进程组退出，失败亦清理后恢复；B不参与。

唯一拟运行命令（未执行；必须新 release）：

```sh
/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1/commands/run_proposed_pv_offline.sh NEW_RELEASE_JSON
```

交付目录：`results/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1/`；入口 `CPU_READY.json`、`proposal/PROPOSAL.json`、`RELEASE_TEMPLATE.json`、`CONTROL_REQUIRED.json`，详细维度/沿革/调用合同见 `CONTRACT_REVIEW.json`、`MODEL_AND_SNAPSHOT_METADATA.json`、`INPUT_MANIFEST.json`。新 release 固定路径为 `releases/P10_A_PV_OFFLINE_PREFLIGHT_V1.json`，当前不存在且未 claim。CONTROL21/TASK_BOARD28及旧封存未改；全部本轮产物保留。等待分析验收与另行放行。
