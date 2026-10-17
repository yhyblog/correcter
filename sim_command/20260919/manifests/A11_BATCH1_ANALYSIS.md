# Batch1 分析验收

验收时间：2026-09-20T20:07:45.425665+00:00。本轮关闭，原始外层 exit3/LAUNCH_RESULT=failed 保留。该值来自唯一 p04 normal 在 s48 成功、未到预定 cut55，随后14支按合同未启动；106已启动子进程全部退出0，无 primary/cleanup/发布技术失败。

累计计划500源已处理9：8个配对父源（train8/dev0）、1个cut前成功的normal-only源；剩余491个未执行槽。不因结果不足改cut、换seed或补源。

本批7合格源各15终局、14冻结状态比较、7双repeat组；28配对targets从原始分支复算一致。标签如下，数值单位为成功率差值；Q-C10与G0-C5监督分开。

| 源 | cut | gain+ | gain− | pair | G0 |
|---|---:|---:|---:|---:|---:|
| p00_disassemble_train0000_cut5 | 5 | 0 | 0.5 | -0.5 | 0.166667 |
| p01_pick_place_wall_train0000_cut5 | 5 | -0.5 | 0 | -0.5 | 0 |
| p02_stick_pull_train0000_cut5 | 5 | 0 | 0 | 0 | 0 |
| p03_stick_push_train0000_cut5 | 5 | 0 | 0 | 0 | 0 |
| p05_pick_place_wall_train0001_cut55 | 55 | 0 | 0 | 0 | 0 |
| p06_shelf_train0001_cut55 | 55 | 1 | 0 | 1 | 0 |
| p07_stick_pull_train0001_cut55 | 55 | 0 | 0 | 0 | 0 |

完整106终局为53绝对s300与53合法提前成功。这是采集覆盖记录，不能作为方法成功率样本或比较排名。8支Q在承诺内/边界成功时不再采H10；尾长42/41/40按实际执行8/9/10步记录，不强迫终局后恢复。

本批仅p00的G0 target非零且为正，其余6源为0；连同旧shelf0，目前8源的G0标签为2正6零，没有负标签。这不足以支持触发器泛化结论；按原固定源计划继续收集，不能据此挑种子补标签。Q局部探针并非Post/Velocity输出，标签不能证明哪一纠偏分支更优。

完整状态只认可冻结捕获字段/MJB闭合，physical_equality_proven=null。当前覆盖5个任务，其他45任务未实测；B方法视图仍待CPU消费确认，normal policy rollout不等于LVM demonstration positive。

本轮总4.4843小时，固定并发2；106次cold载入合计13228.62 host秒，占child host区间46.45%。不是GPU秒、实际IO或可消除墙钟耗时；不同任务和早终局比例使其不宜直接外推全500。下一批保持2，先以CPU补齐其余任务初始化报价。

最终输出按独立inode约15.9646GiB，不含全部系统峰值；quota、外部/unlinked cache、监测间超调、RSS/VRAM和实际IO仍未知。所有产物保留，无删除。本轮实际1973采样/19730flow/19469控制；116caps内，921713私有事件端配对无缺端。精确publication scan和成功handoff raw polls未序列化，继续null。

证据入口：`manifests/A11_COMMON_POOL_BATCH1_V1_ACCEPTANCE.json`；配对索引：`manifests/COMMON_POOL_ACCEPTED_PARENTS_V2.json`；覆盖处置：`manifests/COMMON_POOL_SOURCE_DISPOSITIONS_V1.json`。
