# A10／存储交接补充

已核对 CONTROL v5、TASK_BOARD、P00_PREP_V1及存储规则；A00/A10完整RESULT已交付，合同/任务SHA一致。本轮只核对回执与已知VLA资产，不重复已完成实验或CPU测试。

- 公共接口：`results/A/A10/interface_v1/INTERFACE_READY.json`，B已消费；最终代码为`code_snapshot_v3`。两环境各42项CPU检查通过，A7/B23样例兼容。
- 有限预检文件：`results/A/A10/commands_v3/run_proposed_native_preflight.sh`与`preflight_v3/PROPOSAL.json`；需另行release。报价1次reset/attempt、5次native采样、50次flow、1真实控制步，0优化/重试；本轮未执行。
- 原存储清单：`receipts/A/STORAGE_CANDIDATES.json`，4 keep＋9 defer；9个Smol中间checkpoint为14,494,556,639逻辑bytes。不再使用未获证实，不能将其写成已批准删除。
- 本次补查：95份限定范围的合同/manifest/配置及B10回执；13项候选重新解析真实路径、大小/mtime/inode，结果见`STORAGE_REFERENCE_CHECK_r1.json`。Smol `last`指向保留的050000。
- B提交的2个X-VLA下载残片，A已核对其确切路径与大小，总计3,519,073,692逻辑bytes，完整替代权重存在。仍为defer；双方写入/历史恢复依赖尚未排除。
- 没有active_deletion_release，删除0；收到分析端逐项delete/keep/defer清单后，A仅执行匹配的delete项，届时重新检查身份、写入和引用，再追加清理回执。非VLA项目、目录外目标及旧封存不动。
- 模型GPU推理、训练更新、仿真全部0；8张H100的occupancy guard保持正常。TASK_BOARD仍由分析端维护，执行端未改为complete。

完整短报告与RESULT：`receipts/A/A10_REPORT.md`、`A10_RESULT.json`；此前已queue送达分析会话。此次只追加补充文件，未覆盖原结果或存储清单。
