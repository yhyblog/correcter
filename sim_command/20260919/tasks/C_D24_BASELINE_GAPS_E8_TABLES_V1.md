# C：缺失基线终局恢复与E8配对表

任务 C_D24_BASELINE_GAPS_E8_TABLES_V1，revision1。用户要求空闲节点接续本方法未完成项。你已完成Smol/X Velocity1000，不重跑。按 IDLE_NODE_CONTINUATION_AUTHORIZATION_V1.json 直接执行本有限任务，无CPU_READY/逐批批准。

## 有限基线缺项

当前Smol N有效496/500，缺4；LIBERO N有效394/400，5技术失败+1未知。X N500完整不动。本任务只涉及这10个原源槽；先从原冻结source清单与有效N记录生成缺项清单，检查既有终局日志能否唯一恢复。任务不得挑失败样本重试至成功，也不能把unknown默认当未跑。

输入：work/B/B_D24_E8_POST_V1_r1/POST_SOURCES.json（Smol原500）及C已用N/Post基线索引；work/B/B_D24_LIBERO_POST_V1_r1/N_VALID_BASELINE.json（394有效N），同目录LIBERO_POST_BATCH.json/原sources绑定400测试reset/policy seeds。原N入口与结果路径可由 receipts/B/B_D24_SPRINT_V1_RESULT.json 的 N_incremental_summary/N_incremental_csv 及 work/B/B_D24_SPRINT_V1_r1/GPU_N_BATCH.json、B_D24_RECOVERY_V1_r1 原配置定位。只窄查这10源，别全目录盘点或重跑1400。

终局可唯一恢复则写新的RECOVERED_N记录，成本缺项null，保留原始失败/缺失不覆写B结果。只有保存证据表明确实没有完成、原任务已退出且尚有既有一次纠错机会的槽才可在C接续。仍未知是否完成的槽保持unknown；已经用尽允许纠错的槽保持缺失并给理由，不为凑500/400新增机会。本任务最多10次真实补跑attempt，每槽最多一次，无自动第二轮；旧错误/实际attempt计入原历史与C新计数，预算不重置。

补跑按原Smol050000或官方pi05-LIBERO权重/norm、原source/env/policy seed、renderer和原生频率/动作units；Smol沿已经在C跑通的B Mesa原协议，不能从旧文案误取30Hz/.015。LIBERO只对缺失N执行禁用纠偏的基线，不能把B现有Post/V结果当N。必要C私有环境修复允许，不写共享库/guard。若无法保持原基线协议则如实保留缺失，不启动整组N。普通输入/观测检查即可，无SHA/状态/像素一致性工程或额外GPU预检。

## 并行完成E8论文交付

立即复用已完成Smol/X N/Post/Velocity和LIBERO N/Post，输出跨底座/跨suite表、双方有效配对差/救回损害与已有不确定性，标明缺失分母。已有统计直接引用，不重做已完成实验或为了显著性换统计法。主设置π0.5 H10可列作背景行，但与Smol/X源协议不同，不做跨底座逐源配对。

B的算子Velocity若已经发布final，自动追加；否则先交独立可用表，后台最多注册一次等待final文件事件再追加，无LLM轮询，不以B收尾阻塞基线缺项。A新Full-LIBERO另命名另表，不覆盖现有算子版，未来有final再按事件追加。没有新终局时表格写pending，不伪造全表完成。

生成 results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/ 中 N_GAP_DISPOSITION.json、COMBINED_N_INDEX.json、E8_TABLE.csv/.tex、E8_PAIRED.csv、E8_REPORT.md；用标准绘图库输出PDF/SVG的成功率比较图，已有主图不重画。不需要生成AI图片。恢复/补跑新增来源与旧baseline可单独追踪，不修改B/C原终局。图表应明确LIBERO是无D/G0的算子迁移，未按官方固定初态协议；不能称普遍增益。

C独立追加attempt<=10，继承原C累计上限2400且已用1008，底座和小头optimizer均0。能同时运行的独立缺项尽量用8GPU，不为填卡复制任务。CPU整理阶段占卡保持；GPU正式整波全holder停、全部后代退出后恢复，别启动尾部holder。原thread后台事件机制继续用；稳定后结束LLM等待。完成/具体缺项交 receipts/C/C_D24_BASELINE_GAPS_E8_TABLES_V1_RESULT_r*.json。若没有合法补跑槽，就完成恢复及表图，不编造GPU工作。
