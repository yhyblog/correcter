N2500 已完整完成（8张卡常驻 worker，未中断已有样本）。

| H | 完成 | 成功 | 成功率 | 技术失败 |
|---|---:|---:|---:|---:|
| 10 | 500 | 308 | 61.6% | 0 |
| 20 | 500 | 240 | 48.0% | 0 |
| 30 | 500 | 205 | 41.0% | 0 |
| 40 | 500 | 205 | 41.0% | 0 |
| 50 | 500 | 196 | 39.2% | 0 |

同一任务的10个固定新test初态在五个H间配对。成功率按真实终局计，技术失败未计作环境失败。原后台监督器 raw_lifecycle_exit=0，正式整组退出证据与8holder恢复已保存。旧20初态开发测试另用独立入口及数据，不混入这批test结果。

/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/A/SUMMARY.json
/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/A/chain/CHAIN_RESULT.json
