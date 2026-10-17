# B_QUEUE_JOIN_V1 revision2 回执

B 的 V2 接入等待器已独立后台部署；当前公共 `persistent_queue/package/READY.json` 不存在，故仍为 waiting_for_A_package，**不是 DAEMON_READY**。当前真实身份为 host=trial-303225685-trialrun-303225685-worker-0，PID/session=431242，boot=292a2299-7f93-4ef9-a6f8-6d6abfc804fd，start_ticks=91170445。关闭对话或终端不影响该进程；机器/container重启尚无OS自启机制，需按身份对账后重新start，不能重复不确定任务。

V1 waiter（PID417490/start90881347）在核对host/boot/PID/start_ticks及实际命令后通过自身stop退出；V2 waiter（PID421737/start91001752）随后因CONTROL revision3的SHA占卡覆盖迁移至当前入口。两次迁移均保存旧日志/状态和退出证据于 `nodes/B/migrations/`，没有触碰无关进程，也没有重启guard。r1 ACK及工作目录保留。原r1 CPU wave曾在V2切换后被授权门拒绝，未获得正式预约、未进入GPU工作；B11随后由r2纯CPU后台队列顺序运行tests→consume→publish，2026-09-21T12:44:00Z正常完成并排空自有后代。

本次实际CPU控制面测试：4项detached two-job/幂等/unknown防重跑/失败消费与身份/SHA固定入口拒绝门全部通过，最新版本增加当前occupancy override SHA及模型前同卡holder退出声明拒绝检查；A公共调度器的完整资源/交接测试仍须随包提供，不能借B bootstrap测试宣称公共daemon已验收。每次只有SHA绑定、Python固定入口可被执行一次，无shell发现/动态猜测入口；安装ENTERED/PROCESS/RESULT持久记录，未知执行不会重跑。

当前r3以AUTHORIZATION_V2为科学授权、OCCUPANCY_OVERRIDE_V1为调度补充：B不领取共同池475源；训练/正式评测仍需单独一次冻结。包接口在 `nodes/B/JOIN_GATE_V2.json` 和不可变版本 `JOIN_GATE_V2_OCCUPANCY_V1.json`，要求当前override SHA、同卡模型前退出、活跃正式卡禁holder、辅助holder回收后才交回guard、单节点预约不嵌套、资源内存门/补位和A/B故障隔离。旧“整个wave全8holder不停算/持续停算”均不能冒充当前实际行为；辅助占卡独立计量，未扩大科学预算。

最终13:12:12Z只读B本机检查：guard存活，8卡均holder，每卡1013MiB，实际利用率49/50/51/49/49/50/50/50%。这是瞬时辅助占用观测，不是8卡科学实验运行，也不保证平台聚合阈值。UUID见本机 `FINAL_LIVE_VERIFICATION.json`。此次仅join/CPU准备，没有新临时holder或模型命令；无需正式预约，原guard持续运行。

已完成并写共享回执：B11 17处理父源/16 paired的实际视图接口，以及 B_INDEPENDENT_PIPELINE_PREP_V1 的10阶段DAG和E1 48作业/3 GAF成员提案。E1历史train600输入已就绪，可立即一次阶段冻结；其余缺输入/缺工程逐项区分，不阻塞A或其他B阶段。B11原next_task泛称collection的文字已用独立V2 addendum更正为B collection0，原结果及计数不改。

服务管理命令和重启/unknown恢复限制在 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_QUEUE_JOIN_V1_r2_occupancy_v1/README_OPERATIONS.txt`。当前无需逐批保持对话。公共包到达且门通过后自动接入；持续自动实验调度须由届时真实公共daemon及一次阶段授权完成，本回执不把它写成已经发生。
