# Batch2：8个新任务父源的有限正式采集

task_id=`A11_COMMON_POOL_BATCH2_V1`；revision=1；owner=A。唯一 release=`releases/P11_A_COMMON_POOL_BATCH2_V1.json`。按 CONTROL48/TASK_BOARD56 与 DISPATCH_A 核对 host/身份/SHA 后写新ACK，先读 `manifests/A11_MT50_CONTINUATION_CPU_V1_ACCEPTANCE.json` 和 `contracts/BATCH2_RISK_AND_SCOPE_V1.md`。

固定八源按冻结ASCII顺序：assembly-v3、basketball-v3、bin-picking-v3、box-close-v3、button-press-topdown-v3、button-press-topdown-wall-v3、button-press-v3、button-press-wall-v3。全部A/train ordinal0/cut5，逐source/seed/device/path以release为准，不改变PROPOSED等已冻结身份文本。并发2；每parent固定GPU UUID，内部最多15个顺序cold分支；一个外层预约，同组同锁。已处理9槽（含p04 normal-only和shelf0）不重采。仅这8槽获批，不扩到其余任务、B、训练或评测。

116数值caps和独立scheduler aux逐项冻结：120attempt、3624sample、36240flow、36000control、36120obs，6240native reset、12480reset_model、3127800初始化物理子步、12720初始化forward。box-close本批额外7800直接mj_step子步已纳入，不重复计do_simulation；door-lock不在本批。所有Q/D/G0前向、动作梯度、训练、重试、安装、删除0。50任务静态可报价不等于50任务实测；新任务的初始化/full-state/MJB资格仅在本计划parent中检查，不放松门限、不额外短探针。

工作目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_MT50_CONTINUATION_CPU_V1`。唯一真实命令：

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_MT50_CONTINUATION_CPU_V1/commands/run_proposed_batch2.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P11_A_COMMON_POOL_BATCH2_V1.json
```

分析端已完成纯JSON发布检查；不另跑checker、GPU/环境/并发探针。真实入口仍执行冻结SHA与即时容量/身份门。正式bash、command与claim各最多1次；即使命令在claim前失败，也不得重复本次机会。13旧计算release与余额不复用。

维持Q-C10/G0-C5、绝对s300及合法提前成功。若normal在预定cut前成功，按合同停止该parent后14支，保留normal和null/maskfalse，不换源/seed/cut、不补额度；原外层partial_or_failed字段如实保存。承诺内或边界成功时不得终局后补H10。技术失败/预算截尾不得写成负标签。普通完整计量的parent技术失败按冻结调度局部停止；身份/存储/清理/缺账本/未知组进程/CONTROL stop等系统问题停止owned wave。全部已启动源均交付，不能按结果选择报告。

本批 `bounded_batch2` 风险单独接受：即时可用空间至少93,952,475,136B、inode至少564096；128GiB RAM仅并发规划，quota/容器限/RSS/VRAM/实际IO及temp监测缺口仍未知。不可沿用Batch1风险合同，不能把statvfs当项目quota。预算满120分支，不因旧批提前成功缩减上限。所有timeout分别计preparation900、handoff300、child1800+30、parent27900、reserved111900+30、publication300、恢复观察120；锁等待/完整端到端/最终清理硬上界与GPU秒上界null。

全8holder在整个formal wave期间停算，空闲或提前结束卡不恢复holder；分支与后代退出后才能复用worker槽位，全部正式进程及后代退出并完成数据/成本发布后统一恢复8holder。只处理经即时所有权核验的owned进程，不终止无关进程。

交短REPORT/RESULT/LAUNCH_RESULT、逐parent/branch覆盖、完整终局与配对资格/原始标签、所有116实际entered/returned/failed/incomplete、scheduler aux及未知项、固定UUID/strict loader、存储与已存时序/整组退出/发布/8holder恢复证据。保留直接mj_step嵌套计量与各任务实际预算账本；只有已有日志，不为补计数加硬件查询或模型调用。partial硬链接不重复计样本。当前合格配对索引仍8、处理9；新样本经分析验收后另增版本。完成或失败后停止，不自动下一批、训练、评测或删除。
