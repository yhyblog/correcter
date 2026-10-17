# A：持久批次队列实现与一次部署

task_id=`A_QUEUE_BOOTSTRAP_V1`，revision1，owner=A。依据用户2026-09-21新指令与`persistent_queue/AUTHORIZATION_V1.json`；这是包含实施、控制面验收、空闲边界部署和冻结集合自动运行的总授权，不是只交CPU_READY后再等人工release。

先读`persistent_queue/QUEUE_CONTRACT_V1.md`与冻结plan。保持当前Batch3正式命令、原release和所有计算文件不变，继续同一波次，禁止重跑。可以隔离做轻量队列实现；安装/切换在旧wave所有后代退出、数据/成本发布与清理完成后。旧CONTROL50服务旧波次；新协议按节点管理后续任务，不把当前global A-only限制偷偷当作B权限。

交付共同程序到`persistent_queue/package/`，包括supervisor、queue-drain、批次元数据实例化、机器验收/发布、节点状态/stop/status入口及基于500源manifest的选取器。用新入口替代旧逐批预约/恢复层，不嵌套formal.lock，数值采集器与15cold逻辑沿用。保持一个预约连续执行可运行批次，全8holder只在真正空队列/停止且进程与发布屏障完成后恢复。

执行必要定向CPU/fake测试，冻结源码SHA及`package/READY.json`；在无GPU的合成任务中实际验证后台独立session、关闭启动会话仍完成两个任务、重入单例、崩溃不重复claim、跨节点共享存储预约与预算、连续批次不恢复holder、空队列恢复。不要新增模型/渲染/仿真试验；科学操作只来自已批准的计划父源。

测试通过即可在安全边界安装并启动A daemon，无需再次等待分析。优先使用现成可用服务管理器，无则detached supervisor并交准确restart/status/stop命令；如机器重启无法自动启动必须如实说明。实际写`nodes/A/DAEMON_READY.json`和heartbeat。READY后按A冻结顺序、每批≤8/并发≤2自动执行；合法partial或完备局部失败继续，合同规定的系统异常暂停。单批结束自动CPU验收并接续，不回到聊天等待。

同时发布B一次接入脚本及包manifest，B自行验证、配置本机固定设备/环境后接入。不得由A用本机UUID代替B，不直接访问B硬件、不代写B READY。B11视图任务的已有接口保留；公共队列可调度已准备的CPU消费程序，未实现的LLM工程任务不能假称已有shell命令。

原始17结案与当前8独占身份排除，剩余A225/B250受总上界约束；dev明确使用本次ASCII ordinal表。不按收益/失败率换源，不把缺配对记0，不重跑旧standalone，不新训练/评测/删除。当前已授权占卡控制和服务部署归控制面成本，实验计量分列。

回执：`receipts/A/A_QUEUE_BOOTSTRAP_V1_ACK.json`、`_REPORT.md`、`_RESULT.json`，报告package SHA、实际daemon模式/进程与断会话证据、B入口命令、当前队列阶段/阻塞；发出后daemon继续工作，不因交付而停止。若遇合同未覆盖的真实阻塞，仅暂停受影响范围并保留原因，不自主改科学方法。
