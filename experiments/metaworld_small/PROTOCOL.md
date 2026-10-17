# 当前 MetaWorld 环境下的小批量比较

登记日期：2026-09-16。正式采集前固定；本文件不是结果。

## 目标与范围

比较冻结的 velocity 注入、QGF 式 direct 注入、采样后 post 修正，并测量不触发中断重规划的完整策略基线。只使用当前五个 MetaWorld 任务、已有 VLA/D/G0 和四成员 v3 critic，不训练、不扩大为 100 源验证、不根据结局改参数或追加源。

代码入口在 `experiments/metaworld_small/`，独立算法在 `src/corrector/`。VLA、MetaWorld、观测编码、首次 G0 捕获、物理回放通过只读 `ACT-RECAP` 运行时复用。所有新产物写入 `outputs/metaworld_small_20260916/`；原实验产物和权重只读。

## 五个执行臂

| 名称 | 报警后的行为 | 后续执行周期 |
| --- | --- | --- |
| `continue_old` | 继续源策略原 50 步队列中尚未执行的动作，到自然耗尽；忽略 G0，不在第 10 步主动清队列 | 正常生成并完整执行 50 步块，到成功/终止/总 300 步 |
| `replan` | 从同一报警状态生成 a0，执行其前 10 步 | 清队列，冻结 fixed10 |
| `velocity_matched` | 同一 a0/初始噪声，velocity 注入后的最终命令匹配 | 10 步前缀后 fixed10 |
| `direct_matched` | 同一 a0/初始噪声，QGF 式 direct 注入后的最终命令匹配 | 10 步前缀后 fixed10 |
| `post_matched` | a0 上 `S² grad_a R` 终点修正后的最终命令匹配 | 10 步前缀后 fixed10 |

原正常策略可能输出超出 [-1,1] 的 raw 命令；`continue_old` 保留这些原始输入，和原 source/native50 一致，不额外投影。轨迹与原始命令 SHA 精确核对；另存裁剪命令的代理 SHA，但它不替代原始命令记录。原生环境对 XYZ 做 clip，夹爪交给 actuator，并可能由 reward 读取 raw 值，因此不能为匹配审计擅自全维裁剪 old。old 不计入十步幅度匹配统计。

`continue_old` 与过去“执行旧队列前 10 步，再清队列接 fixed10”的 `old` 不同。其第一个后续采样时刻应为 `cut + 50 - plan_age`，若此前终止则没有后续采样。保存原队列剩余长度、期望/实际首次自然再采样时刻、horizon 和调用次数；审计实际命令与原队列一致，以及所有后续采样相隔 50 步。

`replan - continue_old` 是完整策略差异，包含中断和执行周期从 50 改为 10 的效果。它不能单独识别报警时重规划这个动作的因果效应。三种纠偏分别与 `replan` 比较，才保持同一 a0 和 fixed10 后缀，隔离本轮局部纠偏。

## 不变的纠偏定义

四成员平均 `sigmoid(C(s,a;a0)) - sigmoid(C(s,a0;a0))`，固定状态及槽 0 的指定 a0，只对槽 1 候选求导。CPU 两线程保持训练数值路径。Flow 时间 1→0，十次 Euler，步长 -.1，alpha=10，仅在 tau=.3/.2/.1 引导。velocity 用 `v-alpha*tau*g`，direct 用 `v-alpha*g`，共同采用真实反归一化/clamp 导数。direct 是 QGF 式适配，不能称为官方 QGF 的完整复现。

XYZ/夹爪的最终命令 RMS 上限为 .05/.10，Linf 为 .15/.4，共同 mask 为 `1-abs(a0)>=.05`，幅度误差容差 1e-6。所有五方向（velocity/direct/post/reverse/random）都必须生成并保留，共同可行最小半径规则原样沿用；reverse/random 和原生 velocity/direct 输出只保存，不增加模拟分支。匹配可能放大原生小方向，并改变 XYZ 与夹爪比例。

## 新源、随机性及预算

预检五源种子 2026105900–2026105904。正式十五源种子 2026106000–2026106014，按任务排序轮转，每任务三源。注册时扫描历史输出 JSON，拒绝重复源；保留的 2026105000–2026105099 验证种子不使用。首次冻结 G0 报警阈值 .05，每五控制步检查；无报警/提前成功源保留，共同结局广播到各臂，不根据难度换源。

每正式源八个后缀重复，五臂按源/切点/重复号/决策序号使用同一随机命名空间；每重复内随机方法次序。对于 continue_old，决策时刻、状态、数量和执行周期不同，不能声称全程同初始噪声。纠偏三臂和 a0 的候选初始噪声必须逐位同 SHA。

预算：正式最多 15×8×5=600，预检 5×1×5=25，20 次源捕获，8 次正式并发 a0 复现，计划 **653 次**。每次开始模拟前登记；失败、重跑和源捕获都计数。硬上限 **700**，余量 47 只供技术失败修复。不得通过提高上限、换源、增加 repeats 寻找正结果。

## 必须先通过的检查

1. `common prepare` 冻结配置、种子去重和外部依赖身份。
2. `common cpu-check`：独立核心梯度/边界/锚点/导数测试、提取后参数和数值一致性；使用 Corrector 内旧 30 源归档逐位重建全部八个候选。
3. 预检五源检查同初始噪声、零 alpha 逐位恢复、真实采样器已知线性目标符号、物理回放和五臂实际采样时刻。预检审计不披露成功率，不按其结局改方法。
4. `common freeze`：正式源尚未捕获，固定代码/参数/CPU 与预检证据 SHA。
5. 正式八 worker 各先重复一条封存 a0，逐位核对完整轨迹/图像/采样 seed。全部 worker barrier 通过后才领取正式源；失败停止波次，不越过检查。

GPU 波次统一由工作区 `gpu_occupancy_lifecycle.sh run --` 包装，wave spec 为 `hold_idle:false`；整波期间全部 holder 停算，整波完成或失败后恢复，不终止无关进程。

## 统计、成本及解释

独立单位是十五个完整源，不是 120 个后缀。报告各臂成功率、相对 a0 的配对收益、救回/损害、正/负/零收益源数；三种纠偏之间三个相互比较，及 `replan-continue_old`。按任务分层重采样完整源 10000 次，seed=29015，给出名义 95% 区间。多比较没有校正；每任务仅三源，区间只能作为小批量探索证据，不以点估计强制选出优胜者。

成本分别记录 a0/velocity/direct 的原生 VLA 生成过程耗时、终点梯度耗时、包括所有方向和候选打分的完整 shared bank wall，以及各臂后缀 VLA 调用与模拟成本。单列 `restore_seconds` 与回放结束后开始的 `candidate_bank_seconds`；原 `wall_seconds` 含两者，不能误报为部署推理时延。bank 计时仍含上下文加载、诊断打分及候选文件保存。post 的终点梯度耗时不是现有 post_matched 策略的独立部署成本，因为其共同半径仍依赖其他 flow 方向。

## 执行命令

```bash
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector
bash scripts/run_metaworld_small.sh common prepare
CUDA_VISIBLE_DEVICES='' bash scripts/run_metaworld_small.sh common cpu-check
bash scripts/run_metaworld_small.sh common launch --stage preflight
```

最后一条只写并打印 SPEC 路径，不启动 GPU。执行端先检查/启动 guard，再将每个 SPEC 传入：

```bash
/usr/bin/python ../gpu_occupancy_guard.py start
../gpu_occupancy_lifecycle.sh run -- /usr/bin/python ../ACT-RECAP/scripts/run_recap_gpu_wave.py --spec /ABSOLUTE/PRINTED/SPEC.json
CUDA_VISIBLE_DEVICES='' bash scripts/run_metaworld_small.sh evaluation audit --stage preflight
CUDA_VISIBLE_DEVICES='' bash scripts/run_metaworld_small.sh common freeze
bash scripts/run_metaworld_small.sh common launch --stage development
# 将新的 development SPEC 交给相同 lifecycle/wave 命令。
CUDA_VISIBLE_DEVICES='' bash scripts/run_metaworld_small.sh evaluation evaluate
../gpu_occupancy_lifecycle.sh status
```

最终写出 `evaluation.json`、`audits/development.json`、`report/per_source.csv/json`。真实结果由分析端读取后解释。技术失败发生后保留失败预算记录与日志；只修实现问题，不参考正式收益修改算法。失败 worker 的 claim 不会自动抢占；确认其 owner 进程已经退出后，执行端才可将该 claim 目录移入本次输出的 `incomplete/` 并重试。保留失败轨迹、预算账本和旧 wave 记录，不重置 attempt 计数。
