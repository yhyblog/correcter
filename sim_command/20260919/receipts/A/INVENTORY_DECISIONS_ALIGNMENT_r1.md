# 分析决定落实与保留清单

- CONTROL v6、P00合约及A10任务SHA已核对；A00/A10已完成，不因元数据更新重跑。公共 `results/A/A10/interface_v1/INTERFACE_READY.json` 已发布并由B消费。
- E3锁定GAF-v1 adapted。B冻结的MSE/discounted success-to-go及每次采样原生引导见 `configs/METHODS.json`；A接口允许完整多次事件，不强接G0一次门。
- E6准备同D241/242的因果5步误差vs既定G0，均接R/H10/一次上限；动作/分支/reset对齐，缺预测不报警，覆盖率单列。异常开发阈值仍null，不能套用G0的0.05或测试追平。
- Smol使用50000候选，不续100k旧队列。X完整MT50训练底座仍缺；B已独立列原30k更新方案，但未声称它是已证实最小训练量，耗时/显存报价待有限预检；当前不启动。
- A的既有索引为700 train/development父源＋600固定a0/repeat0后缀，共1300条真实轨迹；action/reward/success可用，RGB/next等缺失仍显式保留。B仅bank缺字段的观察不冲突；旧train600未重采。
- 新增 `receipts/A/STORAGE_CANDIDATES_r2.json`：33条精确输入/封存保留项，覆盖SFT及处理器、MT50示范、选定权重、D/G0/Q/PCA、train600/原始树、Smol50k及恢复状态、X初始化/底座、LIBERO最终推理及原数据。复用A00证据，不重扫大数据目录；重叠保留项不可相加算磁盘量。
- 其他候选保留此前9个Smol中间checkpoint（14,494,556,639 bytes）及B2个X下载残片（3,519,073,692 bytes）的待定证据；新增14个本轮测试/过渡发布目录清单，合计10033498逻辑bytes。它们含审计引用，执行端不自行判无用或删除。
- 原 `STORAGE_CANDIDATES.json` 与A10封存回执不覆盖。所有新候选的delete/keep/defer由分析端决定；当前active_deletion_release=null，删除0，训练/模型GPU推理/仿真0。

B的版本化方法/报价：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B10/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z/configs/METHODS.json`、`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B10/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z/configs/RESOURCE_QUOTE.json`。完整A10报告/有限预检命令与预算已交，尚未运行；后续只按具体新release推进。
