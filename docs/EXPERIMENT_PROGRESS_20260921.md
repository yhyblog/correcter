# 实验进度快照

**统一实验结果入口：[实验结果总表（已完成数据＋待填空表）](EXPERIMENT_RESULTS_MASTER.md)。后续终局优先更新该文档；本文件历史进度快照不代替最新结果表。**

**9月22日15:52北京时间最新进展：A的E5完成，C的Smol/X Velocity各500完成；B的LIBERO Post400完成，Velocity保存快照395/400（最后分片运行中）。当前缩减后的仿真执行仅余该收尾，LIBERO仍是无D/G0的算子迁移，不冒称完整系统验证。** [完整进展与结果边界](../sim_command/20260919/deadline_20260924/PROGRESS_20260922_1552_ZH.md)。

**9月22日终局更新：A的E6、VLA-Corrector和GAF全部完成并验收。H10同500源，VLA-Corrector 319/500（63.8%），GAF-v1 adapted 315/500（63.0%）；GAF技术失败0、全组退出且占卡恢复。下方201/474快照与“继续GAF”仅为历史，不重启。B的Smol/X Post已完成，继续LIBERO；C独立负责Smol/X Velocity，发布不等于已运行。** [E3完整终局表](../sim_command/20260919/deadline_20260924/E3_H10_EXTERNAL_FINAL_20260922.md)。

**9月22日05:22 UTC更新：E3 VLA-Corrector已完整500源、319成功（63.8%），原8条日志恢复和成本缺项保留；不重跑。GAF-v1 adapted已真实15train/2holdout物化并完成3×10000更新，八卡评测进展201/500、技术失败0，仅快照。GAF继续当前后台链，无需再放行；尚非全实验完成。** [VLA-Corrector终局登记](../sim_command/20260919/deadline_20260924/E3_UNSTARTED_CONTINUATION_COMPLETE.json)。

**9月22日04:55 UTC实际运行快照：A的VLA-Corrector453源接续已8模型READY、新终局243；加旧47条共290/500有效终局，仍在运行，不是最终成功率。当前新波已记录技术失败0，旧失败保留。终局自动汇总后继续已授权GAF张量物化/拟合，GAF当前fit0。无需重复派单或LLM轮询。** [稳定交接登记](../sim_command/20260919/deadline_20260924/E3_UNSTARTED_STABLE_ACCEPTANCE_V1.json)。

**9月22日E6终局及接续：E6 G0→R26/50、D5→R30/50，配对p=0.219，不支持收益触发优于异常触发；不重跑。A的VLA-Corrector序列化失败后仅接续453个未启动源，保留已进入47源。GAF改用既有池的固定父源内部holdout，不补采。B的Smol/Post与X/Post已在八卡执行，LIBERO适配继续。** [E6分析](../sim_command/20260919/deadline_20260924/E6_COMPLETED_ANALYSIS_20260922.md)。

**9月22日新增回执：B已发布E1最终24格/1200条有效评测，旧无效渲染已剔除；不再等待E1汇总，不重跑。余下优先E6、E3、E8，分工仍A做E6/E3、B做E8。E1的L11没有一致优于其他损失，论文不能预写Full损失最优。** [E1最终表](../sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_E1_RENDER_REPAIR_r3/E1_COMPLETE_SUMMARY.md)。

**9月22日接续：主结果8000条和pilot120已完成；还没有完成全部论文实验。A改派E6触发对照、E3外部比较；B汇总已完成的E1修正1200条并继续Smol/X/LIBERO+Post。X已训练30k且N403/500，Smol N234/496，LIBERO N382/394；沿实际分母，不重训底座或重跑有效N。任务已发布，执行启动以ACK/真实运行回报为准。** [接续清单](../sim_command/20260919/deadline_20260924/CONTINUATION_20260922.md)。

**最新：A主矩阵16/16格、8000条全部完成，技术失败0，共用500个固定test源；旧20开发pilot120另计。原主链一次运行，8worker退出0，18:37:02 UTC原8holder恢复。末段32辅助占卡会话如实披露为全波停卡条款偏差，不把76.62分钟当纯推理/无占卡吞吐，不重跑。E4/E9主结果完成，E5现成过程数据在整理；E1/E6/E3/E8等B任务需独立状态，不能称全论文实验完成。[终局接收](../sim_command/20260919/deadline_20260924/MAIN_FINAL_ACCEPTANCE.json)；[完整格CSV](../sim_command/20260919/deadline_20260924/MAIN_RESULTS_COMPLETED_CELLS.csv)。**

N基线2500条全部完成，技术失败0。H10/20/30/40/50成功率为61.6/48.0/41.0/41.0/39.2%，每格500条；[基线结果](../sim_command/20260919/deadline_20260924/N_BASELINE_RESULTS.md)。

## 历史进度记录（下文旧状态不再作为执行门槛）

**最新运行回报：A的2500条N基线已获原会话用户明确批准并启动8常驻worker；16:10 UTC保存快照273正常终局/0技术异常，后台自动续跑，旧启动拒绝已对该范围解除。20旧初态多次干预测试尚未启动，A当前批准范围仅N。以下较早未启动/blocked描述保留历史，以本条及新回执为准。**

**9月21日截止期更新：已发布[9月24日冲刺授权](../sim_command/20260919/deadline_20260924/PLAN.md)，CONTROL52/BOARD67/queueCONTROL7。停止新475源全量采集；允许必要算法适配与清单内训练/评测，取消严格一致性审计及逐批审批。A已投递，B真实依赖事件已唤醒原线程；实际科学任务启动以新回报为准。内部23日20:00北京时间冻结数据、23:00交表图。**

核对时间：2026-09-21 14:29:35 UTC；CONTROL51 / TASK_BOARD66 / queue CONTROL6。只读保存证据；分析端未做GPU、模型或环境探针。

当前处于共同训练数据池采集阶段；本轮MT50适配训练和论文正式评测尚未开始。

| 项目 | 当前状态 |
|---|---|
| 历史 standalone 五任务实验 | 已完成，保留历史结论，不重跑；不等同MT50主结果 |
| 工程预检 | 原生VLA、EGL、P/V离线数值、真实C10执行/丢尾/H恢复、共同池终局与配对路径已通过有限检查 |
| 共同池 | 25/500源已处理：23个四目标完整train源、1个部分有效train源、1个旧normal-only；至少一目标有效覆盖21/50任务，dev0；剩475 |
| A：Batch3 | 已独立验收并关闭；8父源/120完整终局，新增7完整+1部分目标有效源；无重跑 |
| A：下一批与后台队列 | 八卡八父源正式并发准备已领取；RAM/cgroup/IO/存储及可执行入口回执未交，首次八路计算未放行；完成触发器待节点验证 |
| B：独立任务线 | V2接入等待器已迁移，等待A共享队列包；Batch3只读数据交接已发布。外部对比/消融/适用性CPU准备独立推进，不阻塞A；不把等待器当采集daemon |
| 新D/G0/Q训练与外部基线共同数据训练 | 未开始，依赖共同池及方法视图适配 |
| E4＋E9：MT50主结果与H扫描 | 未开始正式评测；H10/20/30/40/50各N/P/V，H10另R，共16单元 |
| E3：外部方法比较 | 未开始本轮共同数据训练和比较；π0.5＋MetaWorld，VLA-Corrector与GAF-v1 adapted |
| E1：损失消融 | 未开始本轮四损失训练与P/V消融；既有五任务H10 |
| E6：收益触发vs异常触发 | 未开始正式最小对照；两者都接R |
| E5：过程成本 | 日志合同已准备；正式性能/每成功调用与时间结论随主评测产生，不另加episode |
| E8：跨模型/环境 | 待适配和正式评测；Smol/X-VLA＋MT50与π0.5＋LIBERO保留，历史底座结果不算本轮完成 |
| 真机 | 用户负责一个设置，未纳入两机仿真排程 |

door-close 的三个差值标签因 raw alias 保持 null/mask=false；G0=0 有效，绝对成功监督在父源内去重后仅两个 repeat。部分有效源单列，不补采、不按结果换源。正式训练和论文评测尚未开始。

本批按用户临时覆盖启用了空闲卡holder，不能作为全卡停holder或可比吞吐基准。下一队列须确认同卡holder退出再进入正式GPU；后台任务稳定后结束对话轮次，由终局事件唤醒原执行会话。实际触发器就绪仍以节点handler ACK为准。

证据：[Batch3验收分析](../sim_command/20260919/manifests/A11_BATCH3_ANALYSIS.md)；[严格四目标索引V4](../sim_command/20260919/manifests/COMMON_POOL_ACCEPTED_PARENTS_V4.json)；[部分目标索引](../sim_command/20260919/manifests/COMMON_POOL_PARTIAL_TARGET_PARENTS_V1.json)；[总实验清单](../sim_command/20260919/MASTER_PLAN.md)。
