# Batch2 分析验收

验收时间：2026-09-21T01:38:15.100039+00:00。外层exit0，120已启动子进程全部退出0，原始记录保留。本轮已消费关闭，余量不可复用。

新增8个合格配对train父源；累计16个配对父源（dev0），另保留1个此前cut前成功的normal-only源。计划500源已处理17，剩余483未执行槽，当前覆盖13/50任务。不要把16个独立父源写成120/241个独立样本。

本批每源15完整终局、14精确状态比较、7双repeat组；32个targets从原始分支结果复算一致。

| 源 | gain+ | gain− | pair | G0 |
|---|---:|---:|---:|---:|
| assembly-v3 train0/cut5 | -0.5 | -0.5 | 0 | 0 |
| basketball-v3 train0/cut5 | 0 | 0 | 0 | 0 |
| bin-picking-v3 train0/cut5 | 0.5 | -0.5 | 1 | 0.166667 |
| box-close-v3 train0/cut5 | 0 | 0 | 0 | 0 |
| button-press-topdown-v3 train0/cut5 | 0 | 0 | 0 | 0 |
| button-press-topdown-wall-v3 train0/cut5 | 0 | 0 | 0 | 0 |
| button-press-v3 train0/cut5 | 0 | 0 | 0 | 0 |
| button-press-wall-v3 train0/cut5 | 0 | 0 | 0 | 0 |

120完整终局为37绝对s300和83合法提前成功；仅描述本次采集覆盖，不是方法成功率评测。112条非normal比较分支均完成C10/C5承诺、raw丢尾和H10恢复，其中96条候选替换、16条G0_old旧队列控制；后者plan_replaced/intervened/online_G0_triggered均false，不能将112称作在线干预次数。

Q局部±为采集探针，不代表Post或Velocity表现。当前16源的G0标签为3个正值、13个零、无负值；有效监督及验证覆盖仍有限，不能据此声称触发器泛化充分，也不能按结果挑源补标签。完整状态只在冻结捕获字段/MJB闭合范围内成立，physical_equality_proven=null。

361个私有scope共931766 entered/terminal对，116操作caps内，无failed/incomplete。实际box-close direct mj_step=7800（taskset7500/wrapper150/diagnostic150）；原日志确认不与do_simulation嵌套双计，总初始化物理3127800、forward12720。

外层15691.137秒（4.35865小时），120次cold加载平均124.531 host秒，合计约占child host时长48.406%；双host窗口占外层88.81%，不是GPU利用率。两批工作负载和终局分布不同，不构成加速比较。保留并发2，下一任务只参数化配置和报价，不新增工程GPU测试。

最终独立inode内容14,524,777,251B（13.5273GiB），不是全局峰值。quota、RSS/VRAM、物理IO、外部/unlinked temp与监测间超调未知；精确成功handoff poll/publication scan未序列化字段保持null。所有产物保留，没有删除。

证据：`manifests/A11_COMMON_POOL_BATCH2_V1_ACCEPTANCE.json`；配对索引：`manifests/COMMON_POOL_ACCEPTED_PARENTS_V3.json`；计划源处置：`manifests/COMMON_POOL_SOURCE_DISPOSITIONS_V2.json`。B视图CPU任务仍待自身ACK/RESULT，训练、主结果与消融均未由本次放行。
