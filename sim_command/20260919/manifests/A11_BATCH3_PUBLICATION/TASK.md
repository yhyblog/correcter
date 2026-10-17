# Batch3：下一固定八任务父源的有限正式采集

task_id=`A11_COMMON_POOL_BATCH3_V1`；revision=1；owner=A。唯一 release=`releases/P11_A_COMMON_POOL_BATCH3_V1.json`。按 CONTROL50/TASK_BOARD59 与 DISPATCH_A 核对 host/身份/SHA 后写新ACK；先读 `manifests/A11_BATCH3_PREP_CPU_V1_ACCEPTANCE.json` 和 `contracts/BATCH3_RISK_AND_SCOPE_V1.md`。

固定八源：coffee-button-v3、coffee-pull-v3、coffee-push-v3、dial-turn-v3、door-close-v3、door-lock-v3、door-open-v3、door-unlock-v3。全部 A/train ordinal0/cut5，source/seed/device/path 以冻结 release 为准，保留 PROPOSED 等身份文本。并发2；每parent固定GPU UUID，内部最多15个顺序cold分支；一个外层预约，同组同锁。已处理17槽全部排除，含此前normal-only；不补采、不替换源。

本批116数值caps及scheduler aux逐项冻结：最多120attempt、3624sample、36240flow、36000control、36120obs；6240native reset、12480reset_model、3127800初始化物理子步、9600初始化forward。door-lock每attempt额外520直接mj_step，共7800，已计入上限；嵌套do_simulation不双计。该任务实际资格仍未知，Batch2 box-close的同hook证据不替代本批实测。新任务初始化/full-state/MJB资格只在预定parent内检查，不额外短探针或放松拒绝门。

唯一真实命令：

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_BATCH3_PREP_CPU_V1/commands/run_proposed_batch3.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P11_A_COMMON_POOL_BATCH3_V1.json
```

分析端已完成纯JSON发布检查；不另跑checker、GPU/环境/并发探针。真实入口仍执行冻结SHA与即时容量/身份门。正式bash、command、claim各最多1次；即使claim前失败也不得重复。14份旧计算release及余额不复用。Q/D/G0前向、动作梯度、训练、安装、删除、重试均0；本批不授权B计算。

Q-C10/G0-C5、绝对s300与合法提前成功不变。112非normal比较分支由96候选替换和16 G0_old控制组成；old的intervened/plan_replaced=false，线上G0调用0，不称112次在线收益触发。normal在预定cut前成功时，停该parent后14支，保留normal终局和配对null/mask=false；不改seed/cut或补额度。承诺内或边界成功后不得补H10。技术失败/预算截尾不标负样本；保存原外层partial_or_failed，不改写为计算成功。

普通且计量完整的parent技术失败按冻结调度局部停止；身份/存储/清理/缺账本/未知组进程/CONTROL stop等问题停止owned wave。所有已启动源都交付，不按结果选择报告。full_state_verified只表示冻结闭包字段通过，physical_equality_proven仍null。

本批独立接受 `bounded_batch3` 已披露监测缺口，不能继承Batch1/2权限。真实入口容量准入在NVML/holder之前，要求即时可用至少93,952,475,136B、564096inode。quota、独占预留、容器内存限、RSS/VRAM、实际IO、unlinked和范围外temp/监测间超调仍未知；128GiB RAM仅规划。预算按满120分支，不按前批提前成功比例缩减；不新增探针或自动删除。

preparation900、handoff300、child1800+30、parent27900、reserved111900+30、publication300、恢复观察120秒分别作用于自己的阶段；锁等待/最终清理/完整端到端/精确GPU秒硬上界为null。

全8holder在整个formal wave停算，空闲或提前结束卡不恢复holder。分支及后代退出后才复用worker槽位，全部正式进程及后代退出且完成数据/成本发布后统一恢复8holder。仅处理即时核验的owned进程，不终止无关进程。

交短REPORT/RESULT/LAUNCH_RESULT、逐parent/branch覆盖、原始终局/双repeat/标签资格、116实际entered/returned/failed/incomplete、scheduler aux及未知项、严格载入/固定UUID、已存时序/存储/整组退出/发布/恢复证据。记录door-lock直接mj_step来源与非嵌套计量；不为补原始poll等缺项追加硬件查询。partial硬链接不重复计样本。当前接受索引仍16paired train/dev0、17processed、483未执行，新结果经分析验收后另增索引版本。完成或失败即停，不自动下一批、训练、评测或删除。
