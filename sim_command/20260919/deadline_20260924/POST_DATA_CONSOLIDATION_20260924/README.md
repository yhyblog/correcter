# Post 数据合并记录（2026-09-24）

主文档：[EXPERIMENT_FOR_POST.md](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/EXPERIMENT_FOR_POST.md)。

数值主文件：[EXPERIMENT_FOR_POST_VALUES_20260924.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/data/EXPERIMENT_FOR_POST_VALUES_20260924.json)。仅汇总既有有效结果，没有新增实验、模型执行、GPU查询或统计重采样。

| File | Contents |
| --- | --- |
| MAIN_H_SWEEP.csv | 三底座13个H配置，Native/Replan/Post成功数、分母、成功率与平均调用 |
| EXTERNAL_COMPARISON.csv | π0.5 H10本地外部方法对比及调用覆盖 |
| LOSS_ABLATION_PER_FIT.csv | 完整Q四损失、三fit、DEV/选型两集合，共24格Post结果和费用 |
| TRIGGER_MODES.csv | L11 Post次数对照、Q无关R随机/次数对照、独立E6触发器比较 |
| FORMAL_POST_COSTS.csv | 14个正式Post格，计量总数、梯度覆盖与保存计时 |
| PAIRED_COMPARISONS.csv | 37项原已发布配对统计，保留未四舍五入区间和p值 |
| POST_ABLATION_TRIGGER_TABLES.json | 消融/触发原始抽取，含来源与计数分布 |
| POST_LATEST_SOURCE_AUDIT.json | 最新回执检查与正式Post纳入边界 |
| BUILD_SUMMARY.json | 本次构建规模 |
| DOCUMENT_VALIDATION.json | 表格、来源链接与基本算术验证 |
| POST_APPENDIX.md | LIBERO、固定难度分组和逐任务附录的生成内容 |
| appendix_data/POST_APPENDIX_VALUES.json | 附录完整来源、数值及已知缺项 |
| appendix_data/METAWORLD_DIFFICULTY_METRICS.csv | 三底座全H共52格固定难度统计，macro/micro同时保留 |
| appendix_data/METAWORLD_TASK_METRICS.csv | 650个model×H×task格；N/R/Post逐任务成功、分母、调用、干预 |
| appendix_data/METAWORLD_VALID_EPISODES.csv | 19,496条既有有效记录轻量索引，不是独立初态数 |
| appendix_data/LIBERO_SUITE_METRICS.csv | 四suite及整体Native/固定once BCE算子结果和配对；非L11 Full |
| appendix_data/LIBERO_TASK_METRICS.csv | LIBERO40任务成功数、有效分母、调用和配对 |
| appendix_data/POST_EXTERNAL_FINE_DATA.json | VLA-Corrector/GAF逐任务和难度统计，费用未知不填零 |
| appendix_data/POST_MW_TASK_DIFFICULTY.json | VLA-Corrector仓库冻结四档任务映射28/11/6/5及来源 |
| appendix_data/POST_VERY_HARD_SELECTION_OVERLAP.json | π0.5 Very Hard H10与已揭晓选型50源完全重叠证据 |
| EXPERIMENT_FOR_POST_before_APPENDIX.md | 添加本轮附录前的文档备份 |

附录生成使用 append_post_fine_results.py，只汇总已有小型JSON/CSV；基础文档生成器已接续该步骤，重建时保留附录。组内统计采用任务等权平均，固定难度来自冻结仓库而非本次Post表现。SmolVLA H10 Native有效分母不等、VLA-Corrector缺8条费用，附录中的macro均值与主表pooled均值有定义差异，二者均保留。LIBERO Full仍未评测，不能把BCE算子结果填为完整L11方法。

`build_post_document.py` 只读取现有小型汇总并生成 Markdown/JSON/CSV；其中基线抽取文件虽名为 DATA_VELOCITY_VALUES，仅选取不依赖分支的 N/R 和外部方法字段，不使用其他分支结果。Post 数值以 L11 最终汇总及新增 H 终局为准。

`extract_post_ablation_trigger.py` 为消融与触发表的只读抽取脚本副本，其临时输出位置仍为 `/tmp`；正式交付已复制保存于本目录。不要把重跑文档生成脚本当成实验执行，也不要覆盖原始终局证据。
