B 已消费依赖变化，CONTROL revision7 的 D24_SPRINT_V1 已允许立即科学执行，不再等待共享 READY。核对原 join waiter431242、事件观察器452085及现存claim，未重复启动旧任务；原 join waiter 等包不再阻塞本次执行，A 无依赖。

E1 的48个CPU任务全部完成，每任务4000步，合计192000步。四损失×三完整拟合seed×四成员均已保存final.pt与训练沿革，使用既有train600、不按test选模。整批用时142.29秒，CPU并行不计GPU利用率。

首批固定Smol050000的500个MT50 N episode，与官方pi05及其官方normalization的400个LIBERO N episode。原八路同时进入正式入口；当前4个Smol分片和LIBERO spatial模型常驻，五路均已有真实完整episode且无episode技术异常。另三套LIBERO在导入EGL、尚未开始任何episode时因Mesa默认临时目录并发mkdir/EEXIST退出。已保留错误回执，并按一次纠正重试授权预创建独立0700 XDG_RUNTIME_DIR，用新D24_LIBERO_REPAIR_r2排在现有单一formal预约之后。成功episode不重算；三个空闲GPU由当前队列自有辅助holder监督占用，其活动不算实验吞吐。

新测试源与策略随机种子在开始前冻结。LIBERO使用新seed驱动的任务reset及保存的初始sim state，是新的随机初态协议，不冒充旧官方50-init-state分数；后续方法复用这些已冻结来源。state8/action7/H10/K5、10步settle与各套件时域保留，Smol为action4/H50/K10/300步。技术异常与success=false分开。

正式GPU通过现有lifecycle进入，原holder退出后才加载模型；队列继承唯一formal.lock，活跃正式卡不补holder，空闲holder结束后回交原guard。三个已登记批次均有持久claim和原会话终局触发器，后台按配置自行推进，无需分析逐批ACK。当前原TUI回调路径已实证；headless断终端路径仍未实证，此限制按D24不阻塞计算。

本回执只完成事件审计与首批稳定交接，并非宣称D24全矩阵完成。X-VLA有限SFT、Post接线、E1/E6和外部比较仍属后续已授权工作；E1已完成事件及GPU整批终局事件会继续唤醒原会话。未重跑旧release、未启动475源采集、未改共享环境/CONTROL/A输出。

E1 完成事件续办（2026-09-21T15:56:21.630924+00:00）：确认48个作业/192000步、原claim及进程退出；未重启任何E1拟合。已发布E1_ENSEMBLES.json（12组、每组4成员）。X-VLA 的新D24_XVLA_r1后台等待器已登记终局触发，按顺序等待当前N与LIBERO修复退出，再复用现成8卡入口执行seed42/global64、最多30000步或6小时。窗口前冻结初始化与数据，最后完整checkpoint用于后续比较；当前X尚未开始训练。必要CPU检查通过，未额外运行GPU探针。训练数据元信息实际为2500 episode/204806帧/49个任务标签，按实际覆盖披露；X队列与其失败不阻塞A。

CONTROL 读取故障恢复（2026-09-21T16:16:49.572181+00:00，事件 B_422445bd68021930284fe3fd62016937）：原 X-VLA r1 在前序等待阶段读取 CONTROL.json 遇到 ENOENT，未进入模型加载或训练；原 claim 和事件保留，另写 RESULT_RECONCILED.json，未伪造直接退出码。原 N 批次及旧 LIBERO 修复也因此终止，当前回执替代上文旧运行状态。B 私有读取器增加最多30秒的瞬时读取等待，验证不可用时不沿用缓存授权；全局停止、B启停及授权SHA检查保持生效，七项有针对性的CPU检查通过。

原批次258个完整episode保留，5个已claim但无终局的来源仍为unknown且不重放。新D24_N_CONTROL_REPAIR_r2已在八卡运行（7路Smol各40episode、1路LIBERO spatial共73episode，合计353；其中仅1个有明确诊断的spatial技术失败作一次纠正重试），快照时已新增完成171个episode。D24_XVLA_r2等待它结束，随后D24_LIBERO_UNSTARTED_r3按八路处理279个未开始来源；后者排除了上一批全部claim，包括5个明确技术失败与1个unknown，无额外重试。三批持久claim、进程身份和终局触发器均已核实，观察器在运行，A无依赖；实际科学任务尚未全部完成。详情：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_422445bd68021930284fe3fd62016937_AUDIT.json；稳定交接：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_D24_RECOVERY_V1_r1/STABLE_HANDOFF.json。

LIBERO 失败事件审计（2026-09-21T16:20:15.168696+00:00，B_720b05f54224e945fc8df00ea6e171c3）：核对原claim SHA、exit1终局、DRAIN及旧server/client进程身份，确认已退出；原失败结果保留。直接复核15个完整episode、5个技术失败、1个unknown及21个既有claim。既有D24_LIBERO_UNSTARTED_r3中的279个来源与上述全部claim无交集，排在当前恢复和X-VLA之后，本回合未新启动任何科学任务或重试。三个队列和观察器均存活，终局触发器已登记；当前恢复批次累计完成232个episode。审计：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_720b05f54224e945fc8df00ea6e171c3_AUDIT.json；A不等待B。

原 N 部分结果审计（2026-09-21T16:22:40.100464+00:00，B_b19457ac2e48eb664d4cc3c842a4f42b）：原claim SHA、exit1、DRAIN及各旧作业进程身份核对完成，原partial结果及历史occupancy_handoff=null保留。以episode记录确认243个完整、1个明确技术失败、4个已claim且无终局的unknown；未把unknown计为任务失败。既有353个恢复来源与已完成及unknown无交集，仅包含一次已诊断spatial失败的纠正重试；另三套LIBERO的已登记续跑沿用上一事件审计，本回合未新启动任务。三个后台队列及观察器存活、完成触发器核验通过；当前恢复批次完成277个episode，正式活跃作业6个。审计：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_b19457ac2e48eb664d4cc3c842a4f42b_AUDIT.json；A不等待B。

恢复 N 批次完成审计（2026-09-21T16:58:15.495071+00:00，B_164ca463b69bf91fb1b4477f5d672621）：8个作业全部exit0，353个固定episode均有唯一完整记录，无新增技术失败，旧进程已退出且正式预约交接完成。累计原有结果后，Smol MT50有496/500个完整来源（4 unknown），LIBERO spatial有100/100个完整来源；其他三套LIBERO保留15个完整来源，279个未开始来源仍排队，另5个技术失败及1个unknown保留。累计611/900完整，失败和unknown不计success=false。增量表：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_N_CONTROL_REPAIR_r2/N_INCREMENTAL_SUMMARY.json；CSV：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_N_CONTROL_REPAIR_r2/N_INCREMENTAL_SUMMARY.csv。

现有X-VLA八卡队列已自动接棒，当前phase=training，可观察optimizer_updates=150；只据实际状态记录，不将资产加载当作训练更新。LIBERO队列等待X结束，两批完成触发器及观察器已核验。本回合未新增科学启动，A不等待B。审计：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_164ca463b69bf91fb1b4477f5d672621_AUDIT.json。

依赖变化审计（2026-09-21T18:59:07.698082+00:00，B_2c9d49ecea9b35eced7bce65e6b718f0）：任务板将B_D24_SPRINT_V1从ready改为running，依赖快照中的未交付ready任务因而归零；授权SHA及共享包状态未变化。其他ready任务均已有B回执，未重复启动。旧join waiter仍存活等待包，但D24科学执行不以READY为前置条件。当前X-VLA八卡训练观察到15400次更新，最后完整保存为第15000步，COMPLETE和training_step小元数据一致；此处明确区分已执行步数与已保存步数。LIBERO的279个未开始来源队列等待X结束，两个终局触发器及观察器有效。已更新共享实时快照；本回合没有新增科学启动，A不等待B。审计：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_2c9d49ecea9b35eced7bce65e6b718f0_AUDIT.json。

X-VLA SFT完成审计（2026-09-21T21:03:06.738423+00:00，B_87dc0316e5ff8d608ee9b9ea6bd335ad）：八卡seed42/global64完成30000次更新，训练窗口14369.57秒，未触及6小时上限；终局exit0，所有自有后代已退出，预约交接完成。最后完整030000检查点已在任何X测试结果出现前冻结，权重、优化器、RNG、scheduler及预后处理元数据齐备；只核对小元数据与文件非空，不执行独立GPU预检或逐权重哈希。训练覆盖仍如实记录2500 episode/204806帧/49个任务标签。完成摘要：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/XVLA_TRAINING_COMPLETE_SUMMARY.json。

LIBERO八路已自动接棒，当前新增完整65/279个episode。按既有D24授权复用现成X推理入口，冻结H30/K10/NFE10、物理state4/action4及同一组500个MW test来源，新增D24_XVLA_N_r1后台队列，8个GPU worker排在LIBERO之后；没有再次训练或重复已完成X评测。两个后续批次的claim、进程和终局触发器均已核验，A不等待B；Post/E1/E6及外部比较仍不虚称完成。审计：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_87dc0316e5ff8d608ee9b9ea6bd335ad_AUDIT.json。

LIBERO未开始部分续跑完成（2026-09-21T21:44:47.427445+00:00，B_d3a885089121ee27e52528b17599935c）：8个作业exit0，279个来源均有唯一完整episode记录，无新增技术失败；旧server/client进程身份及DRAIN确认退出，预约交接完成。原Smol与LIBERO N累计890/900个来源完整，保留5个明确技术失败和5个unknown，已无尚未开始来源；完整数据中Smol234/496成功，LIBERO spatial98/100、object99/99、goal96/97、libero10为89/98。分母仅含完整episode；LIBERO仍是新固定任务reset协议，不冒充官方固定初态测试。结果与缺项清单：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_LIBERO_UNSTARTED_r3/N_INCREMENTAL_SUMMARY.json；CSV：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_LIBERO_UNSTARTED_r3/N_INCREMENTAL_SUMMARY.csv。

已登记的X-VLA N队列自动接棒，八个worker进程均活跃，当前119/500个episode完整、技术失败0；终局触发器及观察器有效。本回合未新增科学启动或重试，未重放已完成来源，A不等待B。审计：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_d3a885089121ee27e52528b17599935c_AUDIT.json。


## 2026-09-21T22:18:42.284064+00:00 X-VLA N callback audit and E1 continuation

X-VLA N completed500/500:403 successes (80.6%),zero technical failures. Frozen final30000-step checkpoint;49 training task labels/50 evaluation tasks disclosed. All N totals1390/1400;5 technical failures and5 unknown retained as missing.

E1 evaluation:24 settings (4 losses ×3 complete fit seeds ×Post/Velocity),same50 fixed five-task test sources,1200 planned episodes,eight resident workers. No new fit or completed-episode replay. All-card formal reservation suppresses all holders until the wave drains. Mesa renderer is shared across B E1 cells and differs from A NVIDIA EGL.

Audit: /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_1e58b6736df1bff18f088f0623e00d90_AUDIT.json
Handoff: /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_D24_E1_EVAL_V1_r1/STABLE_HANDOFF.json


## 2026-09-21T23:05:31.271375+00:00 E1 renderer invalidity audit and corrected retry

E1 r1 process outcome complete is NOT full scientific acceptance. CPU reproduction found all-zero images after the first environment close. Preserve80 valid episodes (79 successes and1 scientific failure); invalidate1120 post-close rows as technical failures with outcomes excluded. All original records remain untouched. A private GL lifetime fix passed exact scene-recreation checks, using only old development identities.

D24_E1_RENDER_REPAIR_r2:1120 corrected attempts,8 resident GPU workers,all holders off throughout the formal wave. Frozen model/loss/operator/seed/source settings unchanged; no valid episode replay. Completion trigger is registered. E6/other extensions remain pending.

Disposition: /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_D24_E1_REPAIR_V1_r1/DISPOSITIONS.json
Report: /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_D24_E1_REPAIR_V1_r1/REPAIR_REPORT.md

Handoff follow-up: r2 exited before runner entry (90-second holder handoff limit),zero worker claims/zero scientific operations. Its consumed supervisor claim and terminal record remain. r3 is the same first scientific correction attempt, using the existing supported300-second handoff setting; all8 workers were subsequently admitted.


## 2026-09-22T03:50:46.274423+00:00 E1 completion audited

The1120 corrected episodes completed with zero new technical failures. Together with80 valid retained originals, all24 cells have50 valid episodes each. The1120 black-RGB originals remain excluded and immutable. Corrected matched examples recover exactly the pre-intervention G0 prefix. Final table: /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_E1_RENDER_REPAIR_r3/E1_COMPLETE_SUMMARY.md

Eight idle holders and the completion observer are alive. E6 is the next independent B stage; A does not wait.
