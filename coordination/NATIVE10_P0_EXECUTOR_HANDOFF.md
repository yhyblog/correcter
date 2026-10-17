# Native10 P0 执行交接

更新：2026-09-16。本文补齐原500次报告后的并发结果；冻结P0审计和主协议中的历史副本保持原样。P0最终 **564/600**，剩余36不必用满；真实训练更新0。本次汇总只读，没有新增仿真。

## 技术、冻结与计数

基础P0审计61152项、并发审计2073项均通过，无未解决技术错误。基础500＝旧诊断6 generation＋24 branch＋队列探针10＋物理探针20＋source capture20＋独立bank20＋正式分支400；并发64＝32独立bank restore＋32 branch。P0账本564个编号唯一，新增编号501–564，失败记录未删除。P0波次结束时八卡holder已恢复；后续主采集重新通过lifecycle预留GPU。

冻结证据：`p0/freeze.json` SHA `1c06d15e6b95eff1e4d9667e5a2899682b8e6991cb1caaf10972b7ddeeb78d1d`；`p0/config.json` SHA `1fbe9d5fda7084169b24880772a1033bef046b05559c80c6c724c4fd472ee257`；绑定READY v2 SHA `748f17912c47aaf22aca344d6b9d240031fd9cfabc9bc3fc91a562d16129f188`。原audit SHA `5e9af04e9d6d84090421ee0bf2a01f6e837cae06838787535f3b0e7909bb9085`保留500次快照，并发另有完整审计，不覆写原统计。

旧shelf2026104012、stick-pull2026104028两个正例及disassemble2026104005中性例，仅按历史bounded/native50协议做迁移诊断：完整8候选、replan/post repeat0/1双实现一致，三个case共45项比较通过。不能将它们计入新native10有效性样本。

## 覆盖及五臂效果

20/20预登记episode全部保留，五任务各4；合法报警20，无报警0、无cut0、cut前提前终止0、晚报警0。cut5/15/25/35分别14/2/3/1。自然边界阈值越线21次是事件数，不是新增报警源。总体与报警条件统计在本批相同；每臂80配对槽来自20独立源，四重复不算四个独立episode。400分支没有十步前缀提前终止，227条成功分支在45–219步结束，173条失败分支均至300。

| 臂 | 成功槽/80 | 成功率 | 源级95%CI |
|---|---:|---:|---:|
| normal native10 | 46 | 57.50% | [40.00,75.00]% |
| alarm replan10 | 43 | 53.75% | [38.75,71.25]% |
| velocity | 47 | 58.75% | [42.50,73.75]% |
| direct | 44 | 55.00% | [38.75,71.25]% |
| post | 47 | 58.75% | [42.50,75.00]% |

| 比较 | 净增益pp [95%CI] | 救回/损害 | 正/负/零源 |
|---|---:|---:|---:|
| replan−normal | −3.75 [−15,+3.75] | 2/5 | 2/2/16 |
| velocity−replan | +5.00 [−2.5,+15] | 5/1 | 2/1/17 |
| direct−replan | +1.25 [0,+3.75] | 1/0 | 1/0/19 |
| post−replan | +5.00 [0,+12.5] | 4/0 | 2/0/18 |
| direct−velocity | −3.75 [−11.25,+2.5] | 1/4 | 1/2/17 |
| post−velocity | 0 [−5,+5] | 2/2 | 2/2/16 |
| post−direct | +3.75 [0,+8.75] | 3/0 | 2/0/18 |

CI按任务分层source bootstrap，10000次，seed2026091613，未做多重比较校正。相对normal的描述性系统增益：velocity +1.25pp [−10,+13.75]，救回/损害6/5；direct −2.5pp [−13.75,+6.25]，3/5；post +1.25pp [−12.5,+13.75]，6/5。中断增益＋纠偏增量＝系统增益。

五臂结果不同的仅以下6源（数值为每臂成功槽/4）；其余14源五臂相同。

| seed | task / cut | normal/replan/velocity/direct/post |
|---|---|---|
| 2026110000 | disassemble / 5 | 4/4/3/4/4 |
| 2026110004 | stick-push / 5 | 3/4/4/4/4 |
| 2026110006 | pick-place-wall / 5 | 0/0/4/1/3 |
| 2026110011 | pick-place-wall / 5 | 1/0/0/0/0 |
| 2026110012 | shelf-place / 25 | 2/3/3/3/4 |
| 2026110017 | shelf-place / 5 | 4/0/1/0/0 |

完整20源二值重复结果见audit的`source_rows`，逐任务表见原`p0/report.md`。纠偏收益集中，velocity/post相对replan虽有+5pp点估计，相对正常执行仅+1.25pp；不称独立验证成功，不从P0挑训练赢家，也不以小样本不显著阻止已批准采集。

## preview13与表示质量

20/20真实bank raw审查通过。preview13保留260槽，源内共256个唯一raw计划：19源各13唯一，shelf2026110017有9唯一（a0=grip+ =grip−，xyz+=post，xyz−=reverse_post）。a0外只有这两条grip候选为zero delta；formal组XYZ零组0/20、收缩15/20，grip零组1/20、收缩2/20。零通道未压零其他通道。

100个预览正反对全部对称通过，其中99对命令不同；最大对称及半/全半径误差均2.98e−8，C映射误差0，mask外与tail恒等。实际最大XYZ RMS/L∞为0.049999953/0.149999857，grip为0.099999910/0.299468756，在0.05/0.15/0.1/0.4上限内。`preview13.simulator_calls`合计0，**没有13臂rollout标签，不能据此判断13候选可改善性**。

native10实际150步的raw grip超界9次，最大超界0.007083；P0 a0前十步200命令超界11次，最大0.007659。loaded actuator限幅及10对物理探针实测通过，原data.ctrl差异保留，等价结论只限已测三步窗口，详见 `NATIVE10_RAW_RESTORE_EVIDENCE.md`。

## 成本与并发建议

| 指标 | 原P0 | 32-worker复现 |
|---|---:|---:|
| 模型加载 | 原审计未单列 | 均值174.366s，P95 176.602s |
| bank整体含restore | 均值1.729s | 均值4.374s，P95 4.650s |
| 相同engine bank函数（8源配对） | 均值0.730s | 均值2.342s |
| branch整体 | 均值5.789s，P90 10.098s | 均值11.058s，P95 18.061s |
| branch恢复段 | 均值0.963s | 均值1.135s，P95 1.283s |
| 后缀policy每调用 | 6185次、均值0.289s | 556次、均值0.548s |

20源capture均值2.389s，原400分支平均完整轨迹169.61步。原已审2096文件共40,942,676 bytes（39.046MiB），400分支平均86,230.69 bytes；此为已审轻量产物，不是全工作区容量。

32进程全部完成、无OOM，候选及完整轨迹一致性通过；加载后32个bank＋branch对跨度22.946s，即1.395对/s；含加载worker起止包络199.603s，即0.160对/s，并非完整外层命令墙钟。每进程末次propose reserved约9462MiB，四份约36.96GiB，这是逐次重置的PyTorch记录，不是整波NVML峰值。

建议8GPU×4worker、每worker CPU4线程/critic2线程、模型常驻。该探针仅前8源各复制4份、执行replan rep0，不能称为32独立源或13候选稳态基准；8-vs32的1.40–2.03倍为工作量模型估计，不是实测加速比。当前首轮已据后续READY v4放行，live v5确认继续；实际训练仍未放行。

## 证据与后续

以下路径相对 `outputs/native10_training_20260916/`：`p0/report.md`、`p0/audit_native20.json`（七比较/逐任务/逐源/preview13/hash）、`p0/concurrency32/{report.md,audit.json}`、`preparation/p0_resource_measurement.json`、`budget/attempts.jsonl`。新schema/config为 `experiments/native10_training_20260916/TRAINING_SCHEMA_MAIN_V2.md`、`training_design_v2.json`，原P0 design不覆盖。

当前下一步为完成首轮400主槽、静态train/dev数据审计与seal、独立READY v5零更新预检，再交分析端审查训练。阶段状态与原500次通知的版本对应关系见STATUS；不因迟到通知重复P0。
