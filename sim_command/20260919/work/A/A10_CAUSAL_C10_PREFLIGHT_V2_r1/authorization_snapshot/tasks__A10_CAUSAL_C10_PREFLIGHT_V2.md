# A：一次合法 cut 的因果 D/G0 与 C10→H20 集成预检

task_id=`A10_CAUSAL_C10_PREFLIGHT_V2`；revision=1；owner=A；host=`trial-303224955-trialrun-303224955-worker-0`。本任务书不单独授权，当前CONTROL/TASK_BOARD与独立 `releases/P10_A_CAUSAL_C10_PREFLIGHT_V2.json` 必须一致。旧九计算release及guard安装release均已关闭。

## V2 修订验收与实测边界

本次 CPU 修正见 `manifests/CAUSAL_EVENT_CPU_REPAIR_V1_ACCEPTANCE.json`：去掉重复branch、生产与fixture共用真实recorder、保留身份冲突在写入及ID提交前拒绝；异常实时保存primary/cleanup traceback、branch和已知阶段。六份数值实现、strict loader、UUID parser、输入/种子/111预算不变。CPU成功不代表整体GPU链成功。

旧V1已关闭：实际模型初始化9/语言前向1、环境0，无运行堆栈可回填。V2采用新的命令机会、claim、run/wave/shard/output/cache。真实事件的synthetic=false；CPU合成记录不得混入。发生新异常只保存当时真实栈，主失败与cleanup分开，不通过修补、换seed或重跑继续。已通过纯JSON发布检查，执行端无需另跑checker或原CPU测试。

## 分析决定与唯一命令

批准CPU提案中的**两个固定种子独立回放**替代方案，仅用于工程集成预检：没有完整隐藏状态恢复证明，不使用qpos/qvel伪装恢复，不进行配对性能估计。Post、Velocity顺序新建两个子进程，属于同一formal进程组和一次持续预约；中间不释放锁、不恢复任何holder。

先读当前合同、核对release/host/既有claim与命令记录，再写本任务ACK。状态必须是board ready（执行后可running）和release released，不能复制release状态到任务板。唯一真实命令执行一次：

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1/commands/run_proposed_causal_c10.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P10_A_CAUSAL_C10_PREFLIGHT_V2.json
```

cwd=`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1`。入口自带完整守门，不额外跑checker、GPU小探针、handoff-only测试或模型调用。命令1、claim1、分支attempt至多2；真实命令执行后即不得自行重跑，claim前失败也只交原始外层回执。剩余额度不复用。

## 固定来源、因果语义与停止条件

使用冻结 shelf-place-v3 开发源，环境seed2026091900、generation2026091901、suffix2026091902、恢复native采样seed2026091903；H20/cut5/C10、总步上限300，实际每分支最多16控制步。固定source/run/wave/shard以release为准，不按报警或结果更换来源。

- t0只有obs0，mask00001、历史动作0。新生成raw50/前20队列，D两成员对已知actions0..4的obs1..5预测必须在执行前保存。
- 到cut5先检查success/terminated/truncated，再排除自然刷新；history仅obs1..5，past动作仅actions1..4。实际prefix动作0..4与预测引用的计划必须吻合，才能成熟t0→obs5残差。
- 成熟残差仅作诊断。既有G0真实输入为cut context＋旧队列已知actions5..9＋D对obs6..10的预测；两成员原始回归均值严格>0.05，目标execute5_then_fixed10不改。不能擅自将残差加入G0、修改阈值或目标。
- 真实 `real_G0_trigger` 与 `forced_engineering_intervention` 分开保存。若不触发，允许该预定cut的强制工程分支以覆盖P/V执行接口，不能作为收益触发有效性样本。
- Velocity到cut5须先比较保存的RGB/proprio/context、prefix raw plan、实际动作/reward/flags/物理时间；不一致在V干预前停止，不换seed或再回放。即使匹配仍标hidden_state_equivalence_proven=false，各分支独立episode ID。
- 第一分支提前成功/terminated/truncated、技术失败或未达到完整C10_and_H20_checked状态时，结束剩余wave，第二分支不启动。任何分支提前终止均不补满、不追加重试，不将缺失阶段填为0结果或失败标签。

Post/Velocity每分支各自新a0；Post一次采样/一次动作梯度，Velocity锚点＋guided两次采样/末三步动作梯度，anchor-guided噪声身份匹配。独立自身半径、固定锚点、无Q接受门及raw位约束不变。只执行C10，随后丢弃余40及所有旧队列，清两类policy内部队列，再新native H20采样并最多执行第一步，余19。提前成功/终止先于任何后续模型调用。

## 预算与生命周期

完整上限为111项，以release及冻结RESOURCE_BUDGET为准；实际按entered计费，返回与未完成分列，早停低于上限正常，不要求凑满：

- 2 branch attempts；2wrapper/4native/2taskset；104native reset、208reset_model、10400初始化do_simulation、52000初始化物理子步。
- prefix5＋C10十步＋恢复H20首步，每分支16控制步；合计32控制、426控制子步、34RGB。426来自每支冻结13/13/14序列总213，不按32×13估计。native mj_forward452＝初始化420＋控制32；显式graphics事件完整上限306。
- VLA7/flow70＝Post3（prefix/anchor/恢复）＋Velocity4（prefix/anchor/guided/恢复）。encoder42＝视觉33＋语言9；D8、G0 4。Q ensemble11/成员44、动作梯度4（Post1＋V3）。18model初始化＝policy2＋Q8＋D4＋G0 4。
- 同一操作的alias不相加：model_gpu_inference7与VLA7，flow70与expert70，critic_backward4与动作梯度4，nativeforward总数与分项。身份NVML父1＋每子1＝3；guard/持久daemon原轮询另列范围，未知次数留null，不补探针。
- 环境状态恢复0、baseline rollout0、完整rollout0、参数反向/更新/训练/重试/删除0。step中额外隐式工作若超冻结caps即停，不临时放宽。

A-only固定GPU UUID/PCI/driver、535隔离EGL映射与strict loader按新manifest；实际全部输入/库源身份由入口核对。已安装guard SHA7910c567…85a4、显式handoff300；本任务不安装或重启。全8holder必须保持停算直到整组退出，成功/失败后恢复，不杀无关进程、不启用闲置子集holder。

每个顺序子进程1800+30秒含其完整校验/导入/加载/初始化和诊断，名义合计最多3660秒；父层准备、锁等待、handoff、整组退出清理及退出后恢复另计，端到端严格上界null。RAM估计32GiB/预留64、VRAM估计16GiB/预留24、输出估计256MiB，均非实测结论。

## 回执与证据范围

交本任务REPORT/RESULT、LAUNCH_RESULT、父/各子独立私有账本、初始化/graphics账本、policy UUID/strict loader、prefix逐步RGB/transition、D预存预测与成熟残差、G0分量/阈值/真实和强制标记、P/V噪声/动作/梯度/约束、尾部丢弃/H20余19、两分支及全组退出与holder恢复、manifest。硬杀或缺末事件保留已进入成本及未知项，不退款。

私有整数/UUID账本分别核算，不拼成public interface_v1事件流；公共接口文件不改。供分析查看图像时，只对已保存RGB作CPU无损编码并校验，不增加render。

自然早停时LAUNCH_RESULT可能仍为complete，不能据此声称两分支都完成。回执须分别列出计划/实际启动分支、合法cut到达、实际C10步数、尾部丢弃、H20恢复和completed_C10_branches；缺覆盖注明原因，不换seed补齐。

这是一个固定开发来源的有限集成诊断，不是触发有效性、真实任务成功率、方法排名、MT50适配或成本优势实验。部署Post1/Velocity2口径保留，prefix/恢复额外调用另列；没有共享prefix/a0节省。完成或失败均交分析关闭release，不进入公共池/训练/正式评测或任何下一阶段。B不参与，所有本轮证据保留。
