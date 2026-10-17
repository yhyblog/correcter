# 第二轮数据审计与600源合并：执行端接口审查

2026-09-16。仅检查代码及已冻结配置；未读取运行中源/分支结局，未调用真实数据加载器、模型、PCA、仿真或优化。本文不是已完成数据审计，也不放行后续训练。

## 结论

现有 `artifact_loader.py` / `dataset.py` 支持第二轮 labels13 格式，300新计划槽无需修改冻结采集代码。收尾需要独立静态审计 wrapper；600源联合封存和最终训练准备尚有跨协议接线缺口，不能直接拿当前 round2 配置启动。

## 300新源可复用入口

波次结束、300槽均有明确处置后，读取 `outputs/native10_training_20260916/main_protocols/round2_v1/config.json`，以显式参数调用：

```python
load_artifact_dataset(
    round2_config, 'round2_labels_v1',
    purpose='train', rounds=[2],
    analysis_sources=explicit_frozen_analysis_sources,
    completed_collections_only=True,
)
```

这是后续调用说明，本审查没有执行。`completed_collections_only=True` 额外绑定已封存 collection；未完成槽仍保留 incomplete。wrapper 必须另核全部300计划槽的最终处置，不能把缺失当作完成。`save_audited_dataset(new_version, audited)` 只写新的 dataset/audit 版本，保留账本及 scene registry 快照。

- `artifact_loader.py:357–413` 已支持 `rounds=[2]`、显式 bank、主槽覆盖和分割隔离；不会打开开发/校准/保留集结局。
- `artifact_loader.py:207–324` 审查 source、实际 scene、原顺序替补链、LEAD fallback 及分阶段 capture 账本；`327–354` 检查恢复前缀、原raw命令及 native10 suffix。
- `dataset.py:199–293` 检查13候选槽0为a0、raw/C映射、mask/tail、对称/上限、重复权重和从0连续的 suffix 决策索引；`296–420` 要求4个配对标签，normal独立。
- `dataset.py:424–513` 保留全部计划槽及实际替补身份。没有合法cut但完整自然结局的源保留为 no_cut，不伪造 critic 行；技术缺失/备用耗尽仍阻止完整输入声明。300是计划源数，不保证是300个可训练cut。

## 已确认的保存缺口及最小适配

`round2_v1/config.json` 的 `analysis_documents` 缺少 `NATIVE10_TRAINING_READINESS_REVIEW.md`。`dataset.py:516–533` 保存时硬要求 LEAD、readiness、RAW_BUDGET、EVAL20 四个文件名，因此原样加载后直接保存会被拒绝。

独立 wrapper 应从 round2 已冻结文档映射开始，补入 **round1_v1 冻结配置 `analysis_documents` 中既有 readiness 的路径与SHA**，验证文件当前字节后，通过 `analysis_sources` 参数显式传入。保留 round2 的当前LEAD；记录补齐文档的旧冻结来源。不要修改 round2 配置、其协议digest或任何旧封存；不要绑定会继续编辑的 live coordination 文件。

收尾 wrapper 还应引用波次退出、32 worker实际B200装载身份、全部300槽 resolution 以及分资源账本证据。loader 核每个引用的 attempt，但 `require_stage_budget` 在读入口没有传入实际累计usage，不能代替全账本统计；失败/拒绝/未被完整样本引用的尝试也要计入阶段17400和共享technical_reserve1200上限。

## 600计划源：数据格式兼容，协议接线尚未完成

两份原协议分别是：

| 采集 | bank | protocol SHA |
|---|---|---|
| round1_v1 | round1_labels_v1 | `2456b73fd0728be1fe42f50c3421dddcf30e298d918c746290d3edadb13152d4` |
| round2_v1 | round2_labels_v1 | `a25c2e599a9fe656c02f253ee32add30c197eed8458a0afd491234ca68cfaaa2` |

二者保留同一2720条完整注册manifest，但每份配置只登记自己的bank，并把另一轮stage映射为 `not_released_*`（`round2_prepare_v1.py:83–93`）。直接拼入旧bank会改变已批准协议digest；原样使用第二轮配置也不能覆盖600源。不可通过覆盖 provenance 或修改旧配置使两轮伪装成单一采集protocol。

loader 本身已有多bank及每bank `bank_protocol_sha256` 支持（`artifact_loader.py:357–363, 435–521`）。后续独立合并层可分别在各自封存配置下审计两轮，再创建显式绑定两份 config/freeze、两份审计及各自生成critic的联合静态输入；如何给聚合层独立身份应在新模块/协议中明确。现有 `build_dataset` / `load_saved_dataset` 可复用格式和校验，不需要改变13候选数组schema。

合并必须按原manifest顺序保留600个 planned_slot_id，actual episode与整回合分组不变；保留两代生成critic的原始 provenance；不重编号物理attempt、不把alias或4重复当新源，不丢弃no-cut/失败记录。原100开发源及共同结局继续独立保留，不与训练数组拼接。

## 后续训练入口边界

- `prepare_fit.py:3,21,75–133,179–191` 只实现 round1；不能用于最终600源配置。
- `training_pipeline.py:214–264` 已支持 `phase='final'` 的600训练计划源+100开发计划源及防泄漏检查；`training.py:31–33` 也有final阶段。
- 但 `training_pipeline.py:93–101` 要求 train/dev 两个 `input_protocol_sha256` 等于**单个** collection配置protocol。因此“新round2或联合train绑定 + 原dev绑定”不能直接通过。后续必须独立实现并审查跨采集协议的聚合身份/输入绑定，不可仅改audit字段来通过检查。
- 最终 train-only PCA、A/B初始化、bootstrap/masks、完整dev绑定和optimizer阶段仍需分析端方法及阶段授权。当前READY只放行round2采集；本审查未实现新的merge、PCA或训练逻辑。

建议实现边界：先新增一个纯CPU的 `round2_dataset_audit_v1.py` 及合成测试，负责完整波次/300槽门、上述analysis_sources补齐、新版本保存、分资源账本及实际模型身份引用；600联合输入和最终fit准备另行定义独立接口。所有已冻结文件继续只读。
