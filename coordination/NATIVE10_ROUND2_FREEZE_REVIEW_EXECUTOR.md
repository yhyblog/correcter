# Round2 正式冻结独立验收

2026-09-16。**技术结论：PASS，无实际启动阻塞。** 本次只读核验正式 `round2_v1`，未加载模型、未运行仿真/PCA/优化，未修改任何冻结依赖。此结论验证已批准阶段的技术条件，不增加 READY 权限，也不声称采集效果。

## 冻结身份与依赖

根目录为 `outputs/native10_training_20260916/main_protocols/round2_v1/`。

| 对象 | 独立计算 SHA256 |
|---|---|
| `config.json` | `13ff72cbec4aa8fe92354d55e3a5e0ce0babc934d8cfeb72124af8eb4abc1944` |
| `freeze.json` | `b1755f37303b914c2da362d59f390a91f8c1c46651023a7150810dff31a5ebcb` |
| 封存 READY v8 | `decbf30a364e1cc8e56bdc225bc99cce9fe1a5d810aaa1a869604bb3aeb89ec5` |

- `freeze.files` **804 个文件**全部逐文件重算 SHA 通过；其中原 round1 freeze 的 **747 个文件**身份完整保留，未被新配置覆盖。
- `code_snapshot.tar.gz` **670 个成员**名称、数量、文件类型及解压后内容 SHA 全部与 `code_files` 一一匹配，无缺项或额外成员。
- **1 个大 VLA 资产**的 size/mtime_ns/inode/device 与原 streaming SHA 验证后的封存记录一致；本次未重读整个大权重文件。
- 封存 READY 的 **27 个顶层文档/结果引用** SHA 全部匹配。正式配置引用冻结副本；活动 `coordination` 文件和活动 `scene_registry/entries.jsonl` 均没有进入静态 `freeze.files`。

## 阶段、数据与资产

独立 CPU stage gate 实际检查通过：`round2_labels`→`round2_native10_local_labels`，17,400 simulator/0 optimizer；`technical_reserve`→`preregistered_initialization_replacements`，全流程共用 1,200 simulator/0 optimizer。其余 **8 个阶段**（含 P0、已完成 round1、最终训练、第二次开发、校准、heldout）均拒绝运行。总硬限仍为 simulator50,000/optimizer51,200。

原注册 **300 个 train round2 主槽**完整行及顺序、全部 **600 个顺序候补**、原 manifest 和候补链映射一致。每任务60；首次报警目标30，scheduled15/45/95各10。IDs canonical SHA `9c1891d17b8c438162c4c2ab4ba245864e743b42cd4aa8b813baf298c922f78a`。半/全通道半径各150，map canonical SHA `27b7d171cb439dea68408203011eefebbf918161d6a3f4ce78d8eb6b7afb6362`。候补继承主槽 radius/cut，不增加计划分母。

有效切点策略为原 LEAD：scheduled15→5、45→15→5、95→45→15→5；训练无合法报警按15→5。原历史占位字段完整保留，有效策略单独冻结；无合法cut保留原因，不以 success/Q 重采。seed namespace、VLA/D/G0、guidance、matching、native10/raw、10步prefix和suffix、300步预算、split repeats与原 round1 完全一致。

**B200 四成员**注册哈希与 READY、ranking、四个实际 checkpoint 文件一致；`selected/complete.json` 及所列6个文件全部通过 SHA 核验。selected seal 为 `931c6f6043db92b5d9003eb2833dfc8edd0ab6c860a1979db3983cd7d893725f`。模型文件绑定已核实；实际模型加载由正式 worker 的 `actual_loaded_identity()` 在启动时检查并保存，本次没有调用模型加载。

## 场景表与实际入口

冻结 `scene_registry_before.jsonl` 为 **400 条、269,668 bytes**，SHA `ffb5abdf935645485604d0af9c43990ac7ebce87e9c921de70ef9d0cba39d497`，与 READY 指定启动证据一致，活动 registry 的原前缀逐字节一致。`round2_collection_v1.py:84–99` 在运行时仅验证不可变 snapshot 及活动表前缀，因此合法新增场景不会因活动表整文件 SHA 改变而被拒绝。

新 shell 指向 `round2_runner_v1`；worker 在模型加载前验证新 freeze/stage，并经 `create_round2_collector()` 与 `collect_round2_slot()` 进入原 labels13 采集逻辑。新入口允许300主槽 capture、原有条件候补、13候选×4及normal×4，未使用 policy5 existing-source-only 路径。运行模型身份检查结果写入每个 worker 的 `loaded_model_identity.json`。launcher 保留 8GPU×4worker、全波 lifecycle、`hold_idle=False` 和子进程清理；本审查未启动 launcher。

## CPU 证据

封存证据为 `preparation/round2_integration_cpu_20260916_v1/`，seal SHA `20e6cda6b4f359bc20c37c6b2c8914cede9690b76945d8e3e4e7c09ed1e307fe`。全部证据文件 SHA、pytest 完整日志和结果一致：**51 passed in 5.79s**，shell检查returncode0；**19 个当前代码/测试 SHA**在检查前后相同，均已进入正式freeze。证据记录 model/simulator/optimizer/PCA 全0。

本次另以标准库独立核对归档、manifest、模型文件和记录身份，仅调用冻结 protocol 的纯CPU gate 验证允许/拒绝结果。全部检查通过；未重复运行测试，也未修改封存产物。
