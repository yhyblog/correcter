C 同任务24路接续

用户授权同卡2–3正式任务，本机选择3×8。科学源/随机数/阈值/权重/attempt上限不变。

原任务目录：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_XVLA_MULTI_EVAL_V1
调度目录：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_XVLA_MULTI_EVAL_V1/concurrency24_r1

原RESULT.json是8路物理wave的退出结果（730回合），不是逻辑任务失败；保持历史不可改。最终任务结果在新调度目录RESULT.json，FINAL_*、PAIRED、RESOURCE_SUMMARY、MASTER_UPDATE仍写原任务目录。以receipts/C/C_D24_XVLA_MULTI_EVAL_V1_RESULT_r1.json和CONCURRENCY_HANDOFF.json解析。

原eval_jobs中handoff_for只表示未启动组停车；新调度目录eval_jobs独占领取这些组。逐源attempt counter、claims/attempts、evaluation只有原目录一份。无删除claim，无自动重放。

两波前后各自完整停清holder，整个正式族退出后恢复；新轮48个模型进程/24worker同一正式进程族。Notification旧job显式合并到D24_C_XVLA_MULTI_c24_r1，只在整任务终局唤醒原线程。
