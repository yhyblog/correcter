# B 长任务事件唤醒部署回执

已完成独立轻量观察器、持久outbox、固定原会话投递、busy单写门、注册接口与handler ACK核验，11项新CPU fake检查通过。已以独立session启动PID452085并登记2个短真实回调，当前尚无真实ACK；**未声称WAKEUP_READY**。本轮结束后后台继续自检，实时事实见 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/persistent_queue/nodes/B/wakeup/WAKEUP_STATUS.json` 和本任务RESULT；真实证明到达时由观察器更新RESULT。

B原会话为固定UUID `01a0b9c5-1e4b-7b73-9336-229e6df349a2`、gpt-6-astra，原model/工作区/权限策略元数据已保存并在dispatch前核对。当前运行在PID32661的本机TUI，持有该thread专属writer锁；默认app-server-control socket不存在。采用实际安装0.155.1 CLI的两个现成入口：已加载且turn结束时queue，writer正常释放后才exec resume同一UUID。当前turn忙时只保留pending，不并行起第二个writer；不更改model/审批/沙箱，不杀原TUI、不新建/fork替代对话。

公开接口依据为[OpenAI App Server文档](https://learn.chatgpt.com/docs/app-server)与[固定session非交互续接](https://learn.chatgpt.com/docs/non-interactive-mode#resume-a-non-interactive-session)，本机help/生成schema和数据库元数据才用于实现。默认socket缺失未通过重启服务绕过；官方接口存在及queue消息ID都不能替代真实原会话ACK。

第一个synthetic事件在本轮结束后投递；第二个只等待原writer正常退出后验证不依赖交互TUI的headless路径。两者预先登记、各最多一次传输；ACK或Codex回调完成不会再生成新事件。未实际发生窗口/原writer退出时，离线验证保持pending，不假称通过，也不让LLM反复wait/tail。后台15秒元数据检查、进程和占卡管理继续。主机停机期间不能触发；重启后需按身份start/对账，未装OS开机自启。

事件ID绑定node/thread/job/run/attempt/终局，先持久化后调用CLI；存enter、owned PID/boot/start、exit及ACK。进程消失无明确结果发execution_unknown；不重复实验。未知投递保留delivery_unknown且不自动重发，不用queue与resume并发碰运气。ACK入口验证该event_id确在原UUID的新active turn用户消息中，并原子写claim/ACK/handled。实际任务必须附B审计引用；自检只能写小ACK。已入queue的正常科学批次不等待对话ACK。

已有join-waiter保持运行，包仍未到也不妨碍本观察器安装。观察器仅在包、B已放行任务或阶段依赖实际变化时合并产生事件。B公共daemon后续通过本机注册接口登记其已admitted wave和terminal文件；没有科学任务时不制造fake实验。B不拥有A475源，A不等待B。

八卡并行要求已记录于同目录的B_PARALLEL8_SCHEDULING_ACK.json：真实已授权种子/方法/评测分片优先占满8卡，退出后及时补位，少于8必须记录具体已就绪作业数或资源限制；不自行增加seed/科学预算、不把冻结CPU E1移成GPU配方。当前只有CPU控制面授权，8卡为原guard占用。B当前224 CPU，MemAvailable约1.67TiB，8张H100每卡约78GiB空闲显存；本容器cgroup控制文件未可见、共享quota未知，不能把这些unknown当无限。正式准入仍要补齐cgroup/资源账本和A存储底线，记录实际利用率与载入/CPU仿真瓶颈。当前8卡holder观测和资源快照不等于8卡模型训练或吞吐证明。

运行/注册/恢复说明：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_LONG_TASK_WAKEUP_V1_r1/README_OPERATIONS.txt`。本任务没有模型推理、训练、仿真、特征抽取、新实验源、guard重启或A状态修改。GPU occupancy只作为独立控制面状态检查记录。
