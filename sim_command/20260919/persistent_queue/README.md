# A/B 持久任务队列

**当前最高优先级：[9月24日截稿冲刺](../deadline_20260924/PLAN.md)。必要算法适配和清单内计算已一次授权；取消严格一致性审计/全量475源采集/通用队列READY前置。CONTROL52 / BOARD67 / queue CONTROL7；23日20:00北京时间冻结数据、23:00交表图。下方旧采集与审批条款受此覆盖。**

长任务对话规则：确认后台稳定且完成触发器已登记后结束当前轮次；终局/失败事件自动唤醒各自原执行会话，检查结果并继续已授权任务。后台守护与正常自动续批照常，不以LLM长时间轮询代替。见[事件唤醒规则](LONG_TASK_EVENT_WAKEUP_V1.md)；实际部署待每节点handler ACK验证。

下一批正式并发更新（2026-09-21）：固定8个独立父源、一GPU一parent、正式并发8；不默认沿用2或另加2→4试验。资源/入口准备见 [任务书](../tasks/A_QUEUE8_ADMISSION_PREP_V1.md)，按当前QUEUE8_NEXT_WAVE_V1先核RAM/cgroup/IO/容量/输入压力，再发布独立首8路release；这是首次并发切换，不恢复逐批人工审批。Batch3已验收关闭，holder只保机、不算正式吞吐。

最新占卡覆盖（2026-09-21）：用户明确允许formal wave期间给空闲卡补holder，以维持8卡利用率；正式任务优先且同卡加载/运行前先让出。见[有效补充](OCCUPANCY_OVERRIDE_V1.md)。此补充覆盖下文及旧合同的全卡停holder表述；科学配置与A/B独立分工不变。

当前授权：[AUTHORIZATION_V2.json](AUTHORIZATION_V2.json)，生效指针为本目录[CONTROL.json](CONTROL.json)。V2覆盖旧合同中的A/B共同采集、并发2上限和联合阶段等待规则；旧文件保留供追溯。

| 节点 | 独立任务线 | 当前可执行范围 |
|---|---|---|
| A | 剩余共同池 → 自身D/G0/Q适配 → 全部16个MT50主结果单元 | 后台队列实施/部署、机器门后的475待采源、主线CPU准备 |
| B | 外部方法E3、五任务E1/E6、Smol/X-VLA/π0.5-LIBERO适用性E8 | 后台接入迁移、B11及独立流水线CPU准备；后续计算按阶段冻结 |

A不等待B上线、视图、模型或运行结束。B消费A已经发布的数据/测试输入快照；只有最后论文汇总收齐两端结果。8卡以真实任务利用率为目标，按实际资源准入；同卡正式任务开始前必须确认自己的holder已退出，其他空闲卡按最新用户覆盖保机；真实任务调度与占卡分别记账。

阅读：[基础合同](QUEUE_CONTRACT_V1.md) → [独立分工](INDEPENDENT_NODE_ASSIGNMENT_V2.md)＋[8卡要求](GPU_UTILIZATION_POLICY_V2.md) → 当前总授权 → 自己的任务书。

- A：`../tasks/A_QUEUE_BOOTSTRAP_V1_r2.md`、`../tasks/A_MAIN_PIPELINE_PREP_V1.md`。
- B：`../tasks/B_QUEUE_JOIN_V1_r2.md`、`../tasks/B_INDEPENDENT_PIPELINE_PREP_V1.md`。
- `plan/SOURCES_V2.json`保留500源原始计划身份；[Batch3终局覆盖](plan/LEGACY_BATCH3_TERMINAL_OVERLAY_V1.json)将原8个独占源标为已处理，现25终局/475待执行全部A；source/seed/split/cut不变。严格四目标索引23源，部分目标另1源，不能将其报作24个四目标完整源。
- `nodes/A/`、`nodes/B/`由节点独立发布进程身份、READY/heartbeat和状态；不把投递或join-waiter当作采集daemon就绪。
- `jobs/claims/events/indices`由实现端原子创建；已消费命令不重跑。正常批次机器核验通过自动接续，不等聊天回执。
- 共享package由A发布，A自身通过即可运行，不需要B确认；B可晚接入。共享容量仅短时记账锁，节点预约可并存，A主线空间优先。

当前Batch3继续原冻结并发2，退出/发布后安全切换，旧CONTROL和release不改。当前已观察到B的V1 join-waiter在等待尚未发布的公共包；V1常量不支持V2，需按新版B任务书一次CPU迁移。V2实际部署必须另有保存证据，本文不宣称服务已运行。B执行端迁移用语见[B_ONE_TIME_ACTIVATION.txt](B_ONE_TIME_ACTIVATION.txt)。

训练/正式评测仍需各自一次科学方案和总预算冻结；冻结后后台自动派批，无逐作业审批。终端关闭不影响正确部署的后台服务；机器/容器重启的恢复能力以实际服务配置为准。
