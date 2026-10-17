# 2026-09-23 实验表终局整合

本目录仅汇总已有终局结果和CPU派生统计，不启动实验、不改变模型或阈值。三份阅读入口为 `Corrector/docs/DATA_VELOCITY.md`、`EXPERIMENT_RESULTS_MASTER.md`、`EXPERIMENT_FOR_PAPER.md`。旧文档已备份至 `Corrector/docs/archive/`。

| 文件 | 范围 |
|---|---|
| `FINAL_CROSSBASE_H_SWEEP_DATA.json` / `.csv` / `.md` | 新增24格：SmolVLA H20/30/40/50、X-VLA H20/30，各含N/R/Post/Velocity；每格500个有效终局 |
| `FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv` | 上述12,000个有效单元及执行端原始结果路径；H10复用格不重复计入 |
| `FINAL_L11_POST_PAIRED_STATS.json` | π0.5最终L11 Post与N/R、once、外部基线配对统计 |
| `FINAL_L11_POST_PER_TASK.csv` | π0.5最终L11 Post五H逐任务计数 |
| `FINAL_CROSSBASE_POST_PAIRED_STATS.json` | 新增H中Post–N/R的配对统计 |
| `FINAL_CROSSBASE_POST_ELAPSED.json` | 新增6格Post保存episode时长的描述性均值，每格500/500覆盖 |
| `SMOL_R_H10_CALLS.json` | 既有SmolVLA H10 R的平均调用数来源 |
| `aggregate_final_crossbase.py`、`derive_l11_post_pairs_paper.py`、`derive_new_h_post_pairs.py` | 本次CPU汇总/派生脚本的保存副本 |

调用均值只聚合有效终局，同时包含任务成功与任务失败。原技术失败尝试A381次、B384次及B另一次episode前启动失败单独保留，不能混入500分母或改成任务失败。部分辅助计数的显式记录、可由执行逻辑确定的结构零、未知字段在JSON中分开。

Post/Velocity均为各底座专属L11（BCE＋gain＋0.5pair）、fit9101；后续H扫描未重新选模。旧H10消融源与主源重叠、固定测试源已揭晓、不同底座环境协议不同等限制仍保留。新增配对区间是保存结果的描述性分析，方法写在各JSON中，不是额外独立验证或新的配置选择依据。

JSON中的正式来源路径指向保存的副本及原执行端结果；个别 `temporary_source_origins` 字段保留CPU整理时的临时来源。脚本副本保留原输出到 `/tmp` 的行为，不会触发模型、GPU或仿真实验。
