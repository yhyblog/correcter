# Post MetaWorld 附录分层建议

采用已经存在的 VLA-Corrector 仓库 `DIFFICULTY_TO_TASKS` 四档划分：Easy 28、Medium 11、Hard 6、Very Hard 5。当前仓库 HEAD 为固定 `9d23a0ba6fad562d3ed1a68fc52c8a12459abb41`，该配置没有未提交 diff；复现 README 链接同一 commit 的定义。因此不需要按本次 Native 结果再划分，也避免用同批低 Native 成绩定义 Hard 后解释增益的回归均值问题。称为 VLA-Corrector repository difficulty groups，不称 MetaWorld 官方难度。映射精确覆盖当前 MT50 全 50 个 -v3 任务，无版本后缀转换。

固定同一任务映射应用于三底座与全部 H，绝不根据 Post 收益或某一 H 的结果重新分组。组内推荐 task-macro success 和 task-macro policy calls，完整每任务 10 条时等于 episode-micro。SmolVLA H10 Native 仅 496 有效，四缺项保持 missing；需保留每组 valid/planned 分母以及 macro/micro 两口径可审。总体保持 50 任务等权，不把四个大小不等的组直接四等分平均。

逐任务已有 pi05 全五 H 的 N/R/Post 成功数表：`deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_L11_POST_PER_TASK.csv`，每任务 10 条。新 Smol H20/30/40/50 与 X H20/30 的 N/R/Post 逐 episode 在同目录 `FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv`。旧 H10 Post 在 `L11_FINAL_ROLLUP_20260923/FINAL_EPISODES.csv`；H10 Native 与 R 需合并既有原始 source index/result 小JSON，不能拿统一500补缺。

机器可读映射与 provenance 已写 `/tmp/POST_MW_TASK_DIFFICULTY.json`。
