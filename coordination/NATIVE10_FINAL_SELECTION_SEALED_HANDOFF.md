# 最终固定选择已封存；held仅metadata准备

实际READY v13 SHA `bf2dd9e154d8639860867d9bbb0333e9f9cc3f5930756f32bf0d0331a37bc086`，scope/stage `calibration_selection_seal`。入口于2026-09-17T03:29:59.579230+00:00开始，2026-09-17T03:30:13.933635+00:00完成，耗时14.355秒。仅调用一次正式封存入口，写后已通过同入口只读验证；未重跑75+17 CPU或校准。

固定选择为A4000四成员 + 全局启用matched-post。仍完整生成velocity/direct/post/reverse/random并按原mask/全部方向可行半径匹配；cal的matching/guidance/command_semantics和其他已绑定科学参数逐对象相同，无新Q门/任务路由/单独post幅度。

| 实际产物 | 路径 | SHA256 |
|---|---|---|
| selection complete | `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_selections/final_selection_v1/complete.json` | `2afa80bc07c9cf3f87c5bb8a21bcc8b36baf2a129d25e86b37731de386c7144e` |
| selection result | `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_selections/final_selection_v1/result.json` | `87f1a411e8e82ecc4274875f93a264962824566271231338226d0a01e788f658` |
| held pending v2 complete | `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_preparations/heldout_pending_v2/complete.json` | `2b4f8706b587da23f6c0df0197222f0561d2cb189b68bc27b1647878acd1a3d4` |
| held pending v2 config | `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_preparations/heldout_pending_v2/config.json` | `3a60e99fe8fab7c7eff87801475c62d4354754ad73f375e3c538f84dfecfcf08` |
| 精确held future READY字段 | `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/final_selection_seal_v1/heldout_future_ready_fields.json` | `585287e6948d0246fa892f26f991ed2939868985333343c3c213b95d86546b96` |

实际选择封存含195个文件，188个READY递归授权引用完整归档。held pending v2已精确绑定实际selection path/complete/result；先前pending v1与模板保持只读，不能用于实际held放行。新future字段的25个实际引用已核对，其中selection/result.json显式列path+SHA，避免只冻结目录complete。

held工程及原方法复核继续复用：`analysis/heldout_preparation_method_review.json` SHA `8baa14d0beea590d918aa3103f4d1f8b432a19263ded13d7e17568168ca57829`。后续READY应绑定本实际selection和新v2 pending，并显式释放heldout及heldout_initialization_replacements。原100held（每任务20）+200顺序backup、五臂×4、2200sim/0opt、共享原1200储备、P−R唯一主比较及原统计排序不变。

本轮模型/仿真/优化/PCA调用均0；ledger前后SHA `4f289c308a418803fcf291553823378ddefebf1714de1da19d9f0ea43274a7f5`，仍46025sim/51200opt、reserve0。scene registry前后SHA `313bd9bd1a9cd8e35919abf42609677b9e45b1058fe33f17abd2e9eabfaa0250`，仍800条已接受旧scene；没有held初始化/物理状态/结局读取。8卡holder保持。v13未释放held，未生成held运行目录、未启动任何新波次。

控制结果：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/final_selection_seal_v1/result.json`，SHA `294b0520f3a6c02aaddfb21f11f69719869e9b14bd89a48eb7175f14af124ddb`；actual选择绑定：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/final_selection_seal_v1/selection_binding.json`。
