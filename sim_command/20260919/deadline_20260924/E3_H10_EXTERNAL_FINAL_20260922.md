# MT50 H10：外部比较终局（2026-09-22）

π0.5 SFT030000，同500个A主表固定测试源，50任务各10条。下表均为完整终局，不使用中途快照。

| 方法 | 成功数 / 500 | 成功率 |
|---|---:|---:|
| 原策略 N | 308 | 61.6% |
| 重规划 R | 336 | 67.2% |
| Post | 345 | 69.0% |
| Velocity | 340 | 68.0% |
| VLA-Corrector（既有epoch30） | 319 | 63.8% |
| GAF-v1 adapted | 315 | 63.0% |

GAF三成员共30000更新，15训练父源/11任务/27830窗口，2固定内部holdout父源/8494窗口；checkpoint仅按holdout MSE选择。500条技术失败0、未完成0，全部训练和评测进程正常退出，05:26:34 UTC保存到全8holder恢复。旧474/500通知已被终局取代，不重新启动。

这是不同既有训练资产下的系统比较，训练数据并未统一。GAF为有限数据适配，不是官方协议复现；逐flow引导，不套本方法G0/once。VLA-Corrector也保留原生检测和重复干预。不能由表格单独推断同数据、同干预预算的净算法优势。

VLA-Corrector含8条已接受的终局日志恢复记录，其精确调用和时间缺失仍保留；此前进程失败不抹去。GAF 2262.916秒为500条episode计时相加，不能作为并行墙钟或纯推理成本。此处只报告点估计；已有VLA-Corrector配对统计见同目录 E3_VLA_CORRECTOR_COMPARISON_20260922.md，不能直接套到GAF比较。

证据：results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/FINAL_SUMMARY.json、PER_TASK.csv、chain/CHAIN_RESULT.json；receipts/A/A_D24_GAF_INTERNAL_HOLDOUT_V1_RESULT_r3.json；本目录 GAF_COMPLETE_ACCEPTANCE_20260922.json。

A本轮E6、VLA-Corrector、GAF任务已完成；B继续LIBERO适配，C负责SmolVLA/X-VLA Velocity。C登记及任务发布不等于C已启动。全论文实验尚未全部结束。
