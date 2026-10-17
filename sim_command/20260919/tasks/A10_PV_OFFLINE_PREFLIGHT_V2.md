# A：一次缓存初态的 Post / Velocity 离线数值预检

task_id=`A10_PV_OFFLINE_PREFLIGHT_V2`；revision=1；owner=A；仅主机 `trial-303224955-trialrun-303224955-worker-0`。本任务书本身不放行计算；以当前 CONTROL、TASK_BOARD 和独立 `releases/P10_A_PV_OFFLINE_PREFLIGHT_V2.json` 一致为准。旧六份release保持关闭。

## 唯一命令

先核对当前release、host和claim状态，写本任务ACK，然后执行一次：

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_PV_AUTH_METADATA_CPU_V1/commands/run_proposed_pv_offline.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P10_A_PV_OFFLINE_PREFLIGHT_V2.json
```

cwd=`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_PV_AUTH_METADATA_CPU_V1`。真实入口自带完整SHA/设备核验，不额外跑checker或模型/UUID小探针，不作dry-run。已有claim或结案记录时只报告，不重复执行；一旦claim即消费本release，失败也不退款。

## 固定输入与范围

仅用已验收V3的step0 RGB/proprio和 `raw_plans.npy[0]`，指令、seed与身份按冻结INPUT_MANIFEST。单帧mask为00001，历史动作零填充；step1不参与任何条件或历史。使用同一SFT030000编码器、固定空间投影和历史五任务A4000四成员各自norm/PCA。t0不是报警cut，历史Q也不是已完成MT50适配。

缓存raw50提供有界锚点及原始位模式。按原torch.normal、float32[1,50,32]、seed2026091901仅重建一次噪声；SHA必须等于冻结V3值，失败立即停，不改seed、不再抽样、不补无引导基线。

载入1个π0.5及4个CPU Q。必须保留原有一次state文件读取、同一返回模型的一次strict state-dict载入证据；吞异常、缺权重/键或身份异常均在forward前拒绝。不得为完成预检绕过载入证明或切换随机模型。

## 精确工作额度

- 1 offline attempt；1次guided sampling/10flow，Post动作梯度1次、Velocity末三步动作梯度3次，共4次autograd。VLA参数反向、优化器更新均0。
- Q ensemble objective共10次：锚点评分1、Post梯度/终评各1、Velocity梯度3/局部后评3/终评1；4成员共40次前向，每次含锚点/候选两个slot。16成员反向路径是派生量，不再叠加为调用预算。
- 视觉4、语言embedding2、prefix1、expert10；成员特征变换4、空间投影1。自身投影2次加约束审计独立重放2次，共4；两次raw约束审计。完整辅助调用上限以release/proposal为准。
- `encoder_forward_calls=6`与视觉4/语言2、`model_initializations=5`与policy1/Q4、`critic_backward_calls=4`与动作梯度4均属重叠口径，不相加。父层NVML1＋子层NVML1，共2；Torch/驱动内部API及kernel并非逐项计量，不宣称零GPU开销。
- D/G0、环境实例/reset、EGL/graphics/render、物理推进、策略控制步、完整rollout、训练、重试、删除全部0。

Post为一次S²∇aJ；Velocity仅末τ=.3/.2/.1使用v−10τg与负Euler步长，速度/Jacobian detach。四成员先sigmoid后平均，固定锚点、参数冻结而动作梯度可用。各分支仅使用自身方向/容量/半径；XYZ/夹爪分组及原有可放大规则保留。只修复C10，tail40/mask外/零增量保留raw位模式。无Q改善接受门，不要求Q必升，不按分数换seed或重试。执行入口采用独立自身投影；复制函数的旧共同半径docstring不作为新算法定义，不为旧注释修改冻结包。

## 波次与回执

A-only固定UUID `GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe` / PCI `0000:0f:00.0` / driver `535.161.08`。使用入口内部lifecycle，全A8卡holder保持停算直到整个进程组退出，成功/失败后恢复；B不参与，不终止无关进程或开启闲置子集holder。

1800秒TERM＋30秒KILL只限诊断子进程，父层hash、预约、进程组清理、释放与最多120秒恢复观察另计。40GiB显存/64GiB RAM/2GiB磁盘仅估计；实测按作用范围报告，未知量留null。

交本任务ACK、心跳、REPORT.md/RESULT.json及LAUNCH_RESULT、输入/载入/设备/噪声证据、features和mask、固定锚点、P/V动作与中间梯度/τ局部量、组范数/容量/自身半径、raw约束审计、参数冻结、失败/cleanup/holder恢复和manifest。缺阶段写具体原因。非有限值、身份漂移、预算或约束失败即停；不作Q上涨或任务成功保证。

本包launcher与diagnostic的整数event_id属于**各自私有操作账本**，分别核算后按资源汇总；不能直接拼接或冒充interface_v1的全局UUID事件流。后续正式实验仍受原interface_v1身份合同约束。

成功也只证明这个缓存初态上的数值路径。诊断Post0采样/Velocity1采样不能报告为部署成本；独立部署仍Post1/Velocity2。不代表D/G0触发、C10实际执行/恢复、MT50适配、闭环收益或任务成功率通过。成功或失败均交分析端关闭release，不能自动进入下一阶段；所有新证据保留。

## V2授权元数据修订

旧离线V1为命令1、claim/计算0的已关闭元数据失败，不可复用。V2采用独立包/claim/run/wave/shard/output/cache；仅身份和路径改变，原数值算法/输入/66项caps不变。TASK_BOARD条目从BOARD_TASK_TEMPLATE原样构建，初始status=ready；release自身status=released。分析端发布前使用同包纯JSON入口核验完整候选CONTROL/board/release；执行端不额外重跑checker，直接按本任务唯一真实命令执行一次。任何真实命令机会一旦执行即不自动重用，即便失败早于claim；未进入的claim/计算如实保留0。
