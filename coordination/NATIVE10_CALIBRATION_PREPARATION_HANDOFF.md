# Native10 校准隔离准备交接

2026-09-17T02:23:23.619600+00:00。准备完成，真实运行未放行。live READY仍v11，实际入口拒绝该版本的calibration授权。没有模型推理、reset、capture、仿真或优化更新；8个GPU holder保留。旧封存未改。

按分析端决定，固定A4000与post。前一轮开发Post相对replan为+4.25pp，未达约5pp、不是独立成功；本次不重跑wave/fit。校准只采原五个未加门物理臂，每源2个配对后缀。完整100源审计通过后，全局mean(post−replan)严格>0才提议统一post，否则统一同a0重规划；Q/CI/任务均不参与选择，无第六臂。统计模块只返回proposal，真实选择封存和held仍分别待分析端释放。

## 注册与资源

原cal100主槽：2026111700–1749及2026111800–1849，每任务20；保持原200个有序备用槽。首次合法G0报警、native10正常队列、raw/mask/matched与既有随机流不变，无训练fallback。新cal需要新capture，绝不复用dev的source或a0绑定。无报警共同结局保留全部分母，技术缺失阻止选择，不填失败或零。

100ID canonical SHA：`d2b7ca3b17c322e28610735d871dc319e5e7f24439d2cb4c48c5d00ec705f44e`。完整注册和替补映射来自旧冻结，SHA在ready_contract中。已核所有300个cal/backup身份尚未初始化，但这不能证明实际物理初态已不同。后续在首次动作前以原physical scene fingerprint按task跨split查重；替补仅原允许的初始化失败或重复。初态登记不可变前缀700行、471628字节，SHA `881f3f0b4e191175801c9ef76b22903af6e258e8a73ddf008bd82c44301d60f8`，允许live registry继续合法append。

预算上界1200=100capture+100独立bank restore+100×5×2branch，优化0。初始化替补共用原technical_reserve≤1200，不新增额度；新精确scope为`calibration_initialization_replacements`，不能借v11旧replacement scope运行。当前全局44869/50000 sim、51200/51200 opt、reserve0。cal1200+held2200+技术储备1200在剩余5131内，但这些额度本身不是运行许可。

## 实现与检查

新增隔离文件：calibration_prepare_v1.py、calibration_collection_v1.py、calibration_runner_v1.py、run_calibration_gpu_v1.sh、calibration_statistics_v1.py及4份专属测试。核心科学代码复用只读。运行器必须经过精确输入/模型/授权清单校验，再调用新capture factory；实际loaded A4000身份、每bank raw a0/noise/mask/C(raw)/同幅/尾段与梯度元数据在分支前检查。单个波次由lifecycle包住8GPU×4worker，失败保留attempt，无自动重试、选择或下一阶段。

最终79项合成CPU检查通过（pytest4.53秒，外层6.67秒），shell语法通过；9份新文件before/after SHA一致，96份旧代码未变，真实账本逐字不变。涵盖global正/负/零、共同结局/技术缺失、有序替补、入口/预算/阶段拒绝、raw与native10、嵌套abs/rel/*_path引用、READY竞争更新拒绝和完整prepare→validator→runner接线。v1的75项通过记录以及开发期fixture修复历史原样保留，无真仿真错误。

冻结的新处理：完整遍历READY实际path/SHA引用（绝对、相对、嵌套及文件映射），同时记录原件和快照并要求全部在freeze.files中；固定同一份已校验READY字节，拒绝校验与复制期间变更。新READY还必须精确绑定pending seal、合同SHA、CPU seal和被测代码集合。scene快照搬入新freeze后仍保留原授权前缀引用，避免合同身份漂移。

## 提交给下一READY的精确字段

[future_ready_fields.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_preparation_handoffs/calibration_v1/future_ready_fields.json)提供`calibration`完整行、`calibration_preparation_binding`及必须新增的两个scope；这是提案，不是READY。新READY须同时绑定pending与**v2 CPU**，不能沿用v1代码证据。

若继承v11的`current_resources.ledger/ledger_sha256`，请将live ledger引用替换为已封存[budget_snapshot.jsonl](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy5_independent_audits/round2_policy_v1_independent/budget_snapshot.jsonl)，SHA `8af52eeec7a34958d64205790010160cf04393f8db995c6b4707916c0f3dee2d`。新冻结入口拒绝hash持续追加的live ledger或scene registry；实际计账仍使用原live ledger，未更改预算系统。

| 材料 | SHA256 |
|---|---|
| [pending_seal](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_preparations/calibration_pending_v1/complete.json) | `fa6cc1a31d91e7229d00fc4dcbddc110aae83a725aae5a39a8c625fa5f4a8e77` |
| [pending_config](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_preparations/calibration_pending_v1/config.json) | `a4149b8d75b4ff58290bf230d2adb6eb4a2b17cdf68801985751deb482a965e1` |
| [ready_contract](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_preparations/calibration_pending_v1/ready_contract.json) | `9fd6256ba1cf9e0b043f26fef9621586530c047d4c76c3502442b0b2c98a812e` |
| [cpu_seal](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/calibration_cpu_20260917_v2/complete.json) | `7a907837ff2b46f11caf9b23d1bafcc1120733d54608eb46f40228e05bfbf04d` |
| [cpu_result](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/calibration_cpu_20260917_v2/result.json) | `a270757ac4a9d1120b4bd204fabe186bbbb7f280e5c432488e2bae6503689bd3` |
| [method_decision](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/coordination/NATIVE10_CALIBRATION_PREPARATION_DECISION.md) | `bb8e6c7f7eb145337b25ba6c859bf456754eead33062989aefff0d06c3314fd8` |
| [development_analysis](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/coordination/NATIVE10_ROUND2_POLICY5_ANALYSIS.md) | `3a733cb9d87040b2f86fe55b3c1210ff5534bc8e6ec66128818fa48995cab983` |
| [selected_seal](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/models/final/final_fit_v1/selected/complete.json) | `f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a` |
| [future_ready_fields](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_preparation_handoffs/calibration_v1/future_ready_fields.json) | `c4cb7324710212133750c2121ffb959be92bd29b83bd06d81e2cdc21e486e200` |
| [code_inventory](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_preparation_handoffs/calibration_v1/code_sha256.json) | `443cb6abae4e18e04dfc6eb440caa091aff1928efab5e04bcf4e2ebb06e2d1b8` |

全部注册ID、代码SHA及逐字段清单保留独立JSON，未内嵌逐分支长清单。真实cal未启动；收到后续精确READY并通过新freeze后才可运行，当前无需要用户重复确认的工程阻断。
