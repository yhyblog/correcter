# A11：首个计划 shelf-place 父源采集 V4

task_id=`A11_COMMON_POOL_FIRST_PARENT_V4`；revision=1；owner=A。唯一 release=`releases/P11_A_COMMON_POOL_FIRST_PARENT_V4.json`。
先核对 CONTROL44 / TASK_BOARD51、host、release/任务SHA并写新ACK。上一轮CPU修复已通过分析验收，见 `manifests/A11_OBSERVATION_PHASE_CPU_REPAIR_V1_ACCEPTANCE.json`。本任务开始真实采集，不重跑旧预检或增加独立探针。

## 范围与目的

V3已真实执行一次并消费关闭：模型初始化1、语言前向1、初始化native reset51／物理子步25500，随后在诊断reset前技术失败，无有效样本。V4是同一计划父源的新独立授权，保留source/env_seed/master_seed；不复用V3命令、claim或剩余额度。此次已用实际调用点和scope/hooks/Journal纯CPU组合验收step_0..step_300合同；它不代表真实s300/MJB/full-state已经通过。

这是原共同池覆盖计划的第一个 train 父源：shelf-place-v3，H10/cut5，绝对目标s300。沿用冻结source/env_seed/master_seed与全部身份；名称中的PROPOSED和source.status属于冻结内容，不自行改写。其运行权限来自本次顶层released release及当前CONTROL。

最多15个顺序物理attempt：normal 1；Q a0/local+/local−各2；G0 old/fresh0/fresh1/fresh2各2。Q承诺C10，G0承诺C5，之后native H10至原绝对s300或合法提前终局；不复用normal作为old的结局。a0/fresh0只共享计划生成。真实MJB/完整隐藏状态资格在这些计划轨迹内验证，不能以可观测prefix一致替代；资格不满足即遵守冻结拒绝门，不放宽容差、不改seed、不补采。

最多453策略采样/4530 flow、4500控制步、4515观测、780 native reset、390000初始化物理子步；完整116项上限以release为准。Q/D/G0前向、动作梯度、训练、重试和删除为0。所有额度是上限，未进入部分不允许重用。

## 唯一正式命令

工作目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1`。

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1/commands/run_proposed_first_parent.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P11_A_COMMON_POOL_FIRST_PARENT_V4.json
```

只执行一次冻结sh，不另跑CPU checker、UUID/render/环境探针或调试命令。分析端已用纯JSON入口核对发布元数据；真实入口自行执行完整SHA与容量检查。若授权/claim前失败，命令机会也不能自行重用。

## 存储与整组生命周期

接受已披露的单parent bounded_first_parent监测缺口：project quota未知、无独占预留、shared-HF/native越界写入/unlinked临时文件/扫描间超调及RSS硬上界未知。本次不是整批2.08TiB准入。规划11,609,841,664B，加512MiB floor，入口即时可用空间至少12,146,712,576B及70,000 inode；Store/log/private-temp有限监测沿用冻结合同。容量检查在NVML/holder前。无需额外容量/硬件探针或安装；运行写入/容量/监测异常按原流程结束owned wave，保留证据。

使用冻结全A8卡formal.lock/holder生命周期，handoff名义300秒。各child1800+30秒、准备900秒、reserved wave27900+30秒、恢复观察120秒作用域各自分计；锁等待/完整端到端/GPU秒硬上界未知，不用墙钟冒充。全组包括失败child完全退出后才恢复全部holder，不启动闲置子集holder，不终止无关进程。B不参与本wave。

## 回执和停止点

交独立RESULT/短REPORT/LAUNCH_RESULT、实际entered/returned/failed/incomplete、逐branch阶段及完整终局/配对资格、immutable source/plan/seed引用、存储和进程组退出/holder恢复证据。技术失败或预算截尾不写success=0；single outcome与双repeat/gain资格分列。保存观测只做CPU无损查看，不额外render。日志未记录的计数留null。全部新证据保留，不删除。

本轮只证明采集器与该计划parent的运行/数据资格，不是任务成功率、方法排名、收益触发有效性或MT50训练完成。完成或失败后停止，等待分析验收和关闭release；不自动下一parent、其他49任务、训练或评测。旧11份计算release（含V3）均已关闭，不复用。
