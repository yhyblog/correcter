主评测后台链已实际启动，独立daemon PID 1340697（父进程1）、正式manager PID 1341158。当前保存时点有 8 个存活worker，MODEL_READY=8，claims=12，已进入episode=71，已返回=64。八模型已实际就绪并进入正式episode；该时点计数不代表5500已运行或完成。

新ACK后一次START_MAIN.sh；原生命周期交接于17:21:17 UTC确认原8holder管理进程与私有session后代均已退出，再逐卡记录ACK、创建正式worker。同一预约/锁保持，加载中不填holder；退出且完整家族归属确认的卡才可辅助填充，末尾辅助清理/发布后一次交回原guard。95% duty与控制面利用率独立，不保证持续阈值。

计划固定11格×500=5500 episode，H10 R/Post/Velocity先行，H30/50 P/V后续，再H20/40；组间由后台自动接续。固定N原test表前10 ordinal/各任务，同一SFT030000和历史五任务D/G0/Q，数值Post/Velocity及独立半径不变，once=1，C10后恢复H。自然policy_seed噪声流复用N，候选固定域派生并跨方法一致；不使用旧20已揭晓源替换主test。无新MT50训练结论，先前N2500/pilot120复用，未恢复475采集。

定向9项CPU检查与shell语法通过，无独立GPU预检。初始进程身份只读核对发现沙箱PID/proc映射差异，宿主边界已确认8个原holder各3进程身份；科学入口未因此改动。启动后台CPU观察器，在8模型就绪及首正式返回或失败时投递固定原会话；已存后续cell/终局通知。当前不再用LLM轮询等待，任务继续后台执行。
