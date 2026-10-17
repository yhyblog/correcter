# GAF-v1 adapted：有限数据拟合及500源评测完成

三个seed9201/9202/9203各10000更新，共30000；按两个内部holdout父源MSE选step9000/2000/10000，MSE分别0.04086844/0.06142881/0.06168959。固定训练15父源、11任务、27830窗口；holdout为assembly/basketball两父源、8494窗口。无测试选模型或新增采集。

同底座pi05-MT50 SFT030000、原A主表500源、H10：500/500终局，315成功，成功率63.0%，技术失败0、重试0。三个fit和八个eval进程均退出0，唯一命令仍05:15:56 UTC，未追加launch。

实际eval：7432采样、74320flow、222960 critic前向、74320动作反向、72982控制步；500条episode耗时合计2262.916秒（并发求和，不是墙钟或纯模型部署成本）。训练前向/反向各30000，开发前向1020另计。

全8holder在整个fit+eval正式波停算，无尾卡补位；整组及后代退出、数据成本发布完成，05:26:34 UTC保存到全8holder恢复。终局事件已按event_id处理，本处理只写回执，无新科学计算。

结论仅为有限既有数据池上的GAF-v1 adapted及内部parent holdout；非官方协议复现、非完整MT50训练或同最终公共池训练比较。窗口与分支非独立父源。

结果 /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/FINAL_SUMMARY.json
逐源 /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/EPISODES.json
逐任务 /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/PER_TASK.csv
资源 /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/FINAL_RESOURCE_SUMMARY.json
退出恢复 /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/chain/CHAIN_RESULT.json
