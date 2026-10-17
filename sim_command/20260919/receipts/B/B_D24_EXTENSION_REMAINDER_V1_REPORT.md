B 当前分配的 E1/E8 已完成。以下各设置分别统计，不合并不同环境的成功率。

| 设置 | 方法 | 成功/有效 | N成功/有效 | 配对候选/N成功（配对数） | 配对差值pp（95% CI） | 非零干预 |
|---|---|---:|---:|---:|---:|---:|
| smolvla_MW | Post | 240/500 | 234/496 | 239/234 (496) | 1.008 [-2.080, 4.096] | 420 |
| xvla_MW | Post | 407/500 | 403/500 | 407/403 (500) | 0.800 [-2.029, 3.629] | 411 |
| official_pi05_LIBERO | Post | 387/400 | 382/394 | 381/382 (394) | -0.254 [-1.906, 1.398] | 247 |
| official_pi05_LIBERO | Velocity | 387/400 | 382/394 | 381/382 (394) | -0.254 [-1.906, 1.398] | 43 |

三个 Post 设置共1400条有效测试；LIBERO Velocity另400条有效测试，均无技术失败或未知结果。Velocity与Post同为387/400，其中各自独有成功4条；总数相同不表示逐条结果相同，也不能据此声称改善。

E1最终为24格×50源=1200条有效结果：保留原80条并合入修正1120条，原1120条无效黑图结果排除；48次小网拟合、12个ensemble、3个完整fit seeds。调用成本与30个配对比较见下方E1补充。

资源：本接续1960次真实attempt、16000次小网更新；B累计5687次attempt。沿用预算更新计数238000，其中E1小网192000、LIBERO小网16000、既有X底座SFT30000；本接续基础SFT为0。

最新分工：A接手LIBERO完整方法；C拥有Smol/X Velocity及原N缺失项恢复和E8全表。B没有新的重复单元。原N缺失10项保留missing，本报告不宣称整个跨节点campaign已完成。

LIBERO Velocity：400次guided sampling、1200次动作梯度调用、43次最终非零干预。策略及corrector累计811.544秒，其中corrector83.070秒；episode墙钟累计15070.127秒，整批墙钟3247.671秒，二者口径不同。

科学边界：
- LIBERO Post/Velocity are operator transfers without D/G0, not the Full method. A owns the separately authorized native Full-system task.
- LIBERO uses the original random-reset sources and policy seeds with official weights/norm H10/K5/NFE10; this is not the official fixed-initial-state benchmark.
- Native head uses120 train candidates with5 negatives and40 descriptive-validation candidates, all successful. No test-based model, threshold or radius selection; four members are not four independent dataset fits.
- N retains10 missing entries (Smol4 unknown; LIBERO5 technical failures and1 unknown). Missing entries are never scored as failures. C owns recovery/eligible continuation under the latest assignment.
- MW uses frozen historical pi05 feature/D/G0/Q modules as an external transfer; Full-Post-transfer describes mechanism wiring, not a new all-MT50 head fit.
- Paired confidence intervals are descriptive normal intervals with no multiplicity correction. These completed comparisons do not establish improvement. Heterogeneous settings are reported separately.

交付文件：
- [E8 JSON](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/E8_B_COMPLETE_SUMMARY.json)
- [E8 CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/E8_B_COMPLETE_TABLE.csv)
- [E1最终表](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_E1_RENDER_REPAIR_r3/E1_COMPLETE_SUMMARY.json)
- [E1成本及配对补充](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/E1_final/E1_COST_AND_PAIR_SUMMARY.json)
- [Velocity套件/任务表](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/D24_E8_LIBERO_VELOCITY_r1/N_POST_VELOCITY_TASKS.csv)
- [事件审计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_ff0f2cb2920bcbc3def455857cd04a52_AUDIT.json)

后台：26个本批正式进程身份均已退出；八卡占卡守护恢复，原B会话observer及任务完成/依赖触发器保留。A不等待B。
