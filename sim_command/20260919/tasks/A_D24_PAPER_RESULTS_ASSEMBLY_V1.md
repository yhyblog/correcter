# A：现有结果统计与论文表图收尾

task_id=`A_D24_PAPER_RESULTS_ASSEMBLY_V1`，revision=1，owner=A。用户要求A完成后继续承担未完成任务。本任务是原计划E3/E1/E6/E5及最终论文汇总的剩余工作，**仅CPU读取现有结果、统计、出图**，不新增模型/环境调用、训练或评测。无需再次批准。

## 先关闭上一任务，准确保留缺口

`A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r13.json`为终局SCIENTIFIC_GAP：40次新增开发attempt中30有效全部成功、10技术失败；设置累计200/200。G0只有7train＋4validation有效配对，收益全0。D2窗口681/225和Q-L11标签可用，不等于G0已训练；小网更新0、Full-Post/Velocity测试0。

该批已退出，不再重启/续训常数G0，也不把剩余测试数量转成其他实验。新任务不扩大开发预算、不重跑失败或成功源，不启动L11-only新800测试。用清楚的“完整系统未验证：收益标签无变化”说明；不能将算子版换名Full，也不能把未测试写0%或把30/30开发成功写Full测试100%。

## 现在可独立交付，不等B/C

### 1. GAF与主方法同源配对统计（E3）

读取`results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/{FINAL_SUMMARY,EPISODES}.json`、主表/N已有逐episode标量。对N/R/Post/Velocity分别与GAF按固定source_id配对；使用全部共同有效源，报告n、两方成功数、差值pp、救回/损害、双成/双败。

沿已发布主表的“任务内重采样、2000次、seed20260921”bootstrap方案给95%区间；明确是给定50任务/冻结模型的源级不确定性，不是训练seed不确定性。给exact McNemar双侧p及这4个GAF比较范围内Holm调整，不能说整篇所有比较均已校正。检查源身份/分母即可，不做轨迹/像素一致性审计。若字段缺失，保留NR，不凭总数拼配对。

生成`E3_GAF_PAIRED.csv/.json`与短解释，更新新的综合E3 LaTeX/CSV；原VLA-Corrector500中8条log-derived成功保留，费用只有492/500，不伪填缺失成本。GAF为15train/2internalholdout适配，各方法训练数据不同，不能称严格同数据复现。

### 2. E1/E6论文用表与图注

- E1读取`results/B/B_D24_SPRINT_V1/r1/D24_E1_RENDER_REPAIR_r3/E1_COMPLETE_CELLS.csv`与`results/B/B_D24_EXTENSION_REMAINDER_V1/E1_final/E1_COST_AND_PAIR_SUMMARY.json`。输出4损失×Post/Velocity×3完整fit seed的表，主文可用均值±训练seed样本SD，附录给每seed成功/50。相同50源不能当成150独立初态；旧1120黑RGB结果排除。L11未一致最优，图注不预写正结论。不要为新图增加拟合或重新跑旧统计全套。
- E6读取`results/A/A_D24_CORE_REMAINDER_V1/{E6_EPISODES.json,E6_PER_TASK_CELLS.csv,E6_FINAL_SUMMARY.json}`。准确为G0→R26/50、D5→R30/50，D5救回5/损害1；只用正确task CSV，不用旧SUMMARY.tasks末分片摘要。100dev阈值校准另列，不能混入100test。优先复用已发布统计，写清没有支持“收益触发更优”的结果。
- 输出`E1_LOSS_ABLATION_TABLE.{csv,tex}`、`E6_TRIGGER_TABLE.{csv,tex}`、可直接用的中文/英文图注草稿。图示若有误差条，标清SD或CI。

### 3. E5效果与调用成本图

读取`results/A/A_D24_OURS_E5_REPORT_V1/{PAPER_COST_TABLE.csv,COST_COMPARISONS.csv,FIELD_DEFINITIONS.json,TIMING_TABLE.csv,ENTRY_TIMING_TABLE.csv,PARAMETER_COUNTS.json}`及主表。

输出H曲线、成功率—平均策略调用散点、全部调用/成功数的摊销表；“成功episode内平均调用”与“全部调用/成功数”分列。N缺失独立sampling/干预入口字段仍NR。生成/纠偏计时、episode墙钟的scope不同，不能相减称净模块耗时；历史尾卡辅助holder偏差照注。此任务不新增计时实验。

参数表明确π0.5主设置D/G0/Q新增网络11,912,530；Smol/X还调用外接π0.5特征网络，不能把这11.9M直接冒充其完整附加网络/推理成本。若已有元数据没有完整外接参数计数，写NR和实际依赖，不加载大权重补测。没有比VLA微调更高效的主张。

### 4. E8已完成结果与LIBERO缺口

复用C已发布`results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/{E8_TABLE.csv,E8_PAIRED.csv,E8_REPORT.md,COMBINED_N_INDEX.json}`，其终局已恢复5个LIBERO N成功，现N=387/399；Smol N仍234/496，X403/500。必须同步采用C对应新配对子集/区间，不只换分母。原5个未知（Smol4、LIBERO1）保持未知。

两组LIBERO算子测试387/400仍保留“BCE、预定时刻、无D/G0”的实际范围。Full数值空白，状态SCIENTIFIC_GAP。交一个`LIBERO_SCOPE_AND_GAP.md`说明表，写真实缺项，不追加数据或掩盖已发生10技术失败。

## R补齐后仅CPU自动增补

B独占`B_D24_R_H20_H30_V1`，C独占`C_D24_R_H40_H50_V1`，每节点1000。A不接管、不复制R任务。已有16格先生成可用表图；在后台登记**一个有限的文件终局观察器**，逐节点只消费一次完整终局，读取实际结果CSV后补四格R，输出20格主表和四线H曲线及Full−R配对表。单侧先完成可先更新，不等待双端运行/退出屏障。

只认真实终局和有效episode，不把STABLE_HANDOFF、摘要快照或queue算完成。截至9月23日15:00 UTC未到的格保留空白和原因，观察器退出。图表任务无需持有formal.lock，不启动/停止holder；科学任务仍按整波全holder停算执行。

## 交付与停止等待

输出`results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/`：上述CSV/JSON/LaTeX及PDF/SVG/PNG、`CAPTIONS.md`、`RESULTS_FOR_PAPER.md`、`MASTER_DOCUMENT_UPDATE.md`、小型`PUBLICATION.json`。每图/表标来源和快照时间；不复制episode大树/模型/图像数据集。建议先交当前数据版，R终局后自动出追加版。不能更改B/C原产物、分析端CONTROL/TASK_BOARD或原始结果。

源表/图注核查与普通图像目视即可，不新增全hash/万文件审计或实现回归测试。分析端在接到回执后将数值合入统一`Corrector/docs/EXPERIMENT_RESULTS_MASTER.md`；本任务交精确更新片段，避免多个节点同时覆盖主文档。

任务ACK后直接执行CPU工作。后台增补监听登记好后结束LLM等待，发布/失败触发A原线程`01a0b91f-7443-71b1-915d-6cdb6d6a1a13`一次处理，不能回调重启科学计算。终局交`receipts/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1_RESULT_r*.json`及短报告。
