# B R H20/H30 已完成

审计时间：2026-09-22T09:56:50.406286+00:00。事件 `B_4b6930e1938be25963539c5370ddd50e`。

| H | 成功 / 有效 | 成功率 | 技术失败 / unknown / 未启动 |
|---|---:|---:|---:|
| 20 | 312 / 500 | 62.4% | 0 / 0 / 0 |
| 30 | 307 / 500 | 61.4% | 0 / 0 / 0 |

1000 条唯一 H-source 结果，均匹配原 500 源的 task、env_seed、policy_seed；未使用 reserve 源。此次 1000 attempts，B 累计 6687；无新增训练。保存行与终局汇总一致。

R−N 配对差值：H20 +14.4 pp（95% CI 11.2–17.405），H30 +20.4 pp（17.4–23.8）。其余对比、rescued/harmed 见 FINAL_PAIRED.json；固定 50 task 内 10 源 bootstrap，共享 2000 次抽样、seed 20260921，未做多重校正，未涵盖重训练不确定性。跨主机耗时不作严格效率对比。

本机 supervisor、manager、8 个 worker 与既有 B 科学队列均已退出；8 张卡已恢复 target-util=0.90 占卡，guard 和原线程事件观察器存活。最新 CONTROL 对 B 仍仅有此已完成任务，没有新科学任务；保留依赖观察器等待真实新授权。全局任务板的 running 是滞后快照，未由 B 修改。A 无需等待 B。

终局：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_R_H20_H30_V1/FINAL_SUMMARY.json`。
审计：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_4b6930e1938be25963539c5370ddd50e_AUDIT.json`。
运行证据：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/events/B_4b6930e1938be25963539c5370ddd50e_RUNTIME.json`。
