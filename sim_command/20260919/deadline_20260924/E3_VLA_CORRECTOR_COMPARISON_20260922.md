# MT50 H10：VLA-Corrector完整结果

同500个固定test初态，π0.5 SFT030000底座，H10。VLA-Corrector原生逐步检测和重复干预保留；本文R/Post/Velocity沿冻结G0、最多一次干预。各方法训练数据未匹配，因此这是冻结现有模型下的系统比较，不能声称统一训练数据下的算法净效应。

| 方法 | 成功数/有效episode | 成功率 | 相对VLA-Corrector差值 |
|---|---:|---:|---:|
| 原策略N | 308/500 | 61.6% | −2.2个百分点 |
| 重规划R | 336/500 | 67.2% | +3.4个百分点 |
| Post | 345/500 | 69.0% | +5.2个百分点 |
| Velocity | 340/500 | 68.0% | +4.2个百分点 |
| VLA-Corrector，既有epoch30 | 319/500 | 63.8% | 0 |

VLA-Corrector的500个成功结局由原39条RESULT、8条分析接受的日志恢复记录和本次453条首次执行结果合并；没有重放旧47源。新接续453条无技术失败，进程组退出且05:01:49 UTC恢复占卡。之前模型前失败及8次worker/结果序列化失败仍保留，不能称历次运行技术失败为零。

8条恢复记录的实际采样、flow及精确耗时缺失。成功率分母仍可用500；费用均值必须单列可观测分母，不能补0或把进度条时间当episode计时，不给完整精确成本优势结论。

配对统计按同source_id与固定seed连接，见 `E3_VLA_CORRECTOR_PAIRED_ANALYSIS.json` 和同名CSV；不把同500源当互相独立的两组样本。训练覆盖不同、有限初态数和拟合随机性限制论文结论；不能由本表宣称跨任意底座/任务普遍优越。

## 已完成配对统计

四组均500对，source、env seed、policy seed匹配。差值和救回/损害均以VLA-Corrector为参照；CI固定50任务、在各任务内部配对bootstrap 2000次，seed20260921。

| 方法 | 差值95% CI，百分点 | 救回/损害 | 双侧精确McNemar p |
|---|---:|---:|---:|
| N | −2.2〔−4.2, 0.0〕 | 11/22 | 0.0801 |
| R | +3.4〔0.0, 6.6〕 | 54/37 | 0.0929 |
| Post | +5.2〔1.8, 8.2〕 | 62/36 | 0.0112 |
| Velocity | +4.2〔0.6, 7.6〕 | 60/39 | 0.0439 |

这四项比较内Holm校正后，Post p=0.0447、Velocity p=0.1316。不能把未校正p当全论文统一检验，也不覆盖训练seed或未见任务不确定性。可报告Post在本H10设置高于该选定VLA-Corrector检查点；不能称相同数据/相同干预预算的净算法优势。

GAF-v1 adapted已完成500源评测，315成功（63.0%）、技术失败0；见 [E3完整终局表](E3_H10_EXTERNAL_FINAL_20260922.md)。本文件以上配对统计仍只针对VLA-Corrector。其三成员各训练10000步，构成一个ensemble；15训练父源/11任务/27830窗口，2内部holdout父源/2任务/8494窗口，按开发MSE选择9000/2000/10000步。真实bounded命令经冻结SFT分位数映射到规范内部坐标，不声称恢复饱和前幅度。最终GAF表须保留有限数据适配说明，不称官方原版复现。

原始来源：`results/A/A_D24_E3_UNSTARTED_CONTINUATION_V1/COMBINED_FINAL_SUMMARY.json`、`COMBINED_EPISODES.json`；主表`results/A/A_D24_MAIN_ONCE_V1/FINAL_CELLS.csv`及冻结N结果。结果接收见`E3_UNSTARTED_CONTINUATION_COMPLETE.json`。
