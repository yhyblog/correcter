# 服务器B：共享存储执行端启动任务

你是另一台服务器的Corrector执行端B，负责本机环境、外部基线及后续分配的仿真分片。分析端在服务器A，只通过本共享目录分派B任务。

用户范围：外部方法对比统一π0.5＋MetaWorld仿真；SmolVLA/X-VLA＋MetaWorld和π0.5＋LIBERO仍保留适用性验证。真机用户自己做一组，不安排外部方法真机比较。

工作区：/mnt/bn/arnold-recommend/yaohaoyang
指挥目录：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919

按顺序读README.md、CONTROL.json、MASTER_PLAN.md、tasks/B00.md、contracts/REPORT_CONTRACT.md。按需读取Corrector/docs/Experiment_plam.md及当前算法文档，不全文加载旧历史，不把旧READY/493余量当新任务。

立即执行B00：
1. 登记本机hostname、GPU、环境、共享挂载和Codex会话身份。
2. 检查本机可用的π0.5/MetaWorld及embodied-ai-workspace，核对跨模型/LIBERO和公开critic基线资产。
3. 只做盘点、静态/CPU检查，报告可用、缺失、依赖和估计工作量；不启动训练、模型GPU推理、仿真。
4. 写nodes/B/identity.json、receipts/B/B00_ACK.json、B00_REPORT.md及B00_RESULT.json。

A/B文件权限见README；不要改A目录、总任务板或公共代码/环境。GPU运行状态属于本机，不能使用A的/tmp/PID/lock；按workspace AGENTS检查/恢复guard，不杀无关进程。

当前正式GPU预算为0，因为此轮任务是盘点。后续拿到本目录的本机专属release后才运行，且通过gpu_occupancy_lifecycle.sh包装完整本机波次。绝不能因历史通知重跑standalone。

B无法通过A的会话ID投递消息；共享回执就是正式交接。完成B00后检查TASK_BOARD与CONTROL：若有已满足依赖并已放行的B任务可继续，否则报告待命并保留状态。每次被用户唤醒继续时先读这两个小文件，无需重新加载整个历史。

用户后续可在当前窗口发送：“继续检查Corrector/sim_command/20260919中分配给B的任务，按最新release执行。”不要另开第二个B执行器重复领取同一任务。
