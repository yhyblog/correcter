# 最终 A/B 训练准备接口只读复核

2026-09-16。本次只读代码、设计与 `NATIVE10_FINAL_INPUT_CONTRACT.md`，未读取运行中结局，未加载真实数组或权重，未执行 PCA、初始化、模型前向、测试、仿真或 optimizer。本文供新 prepare/bundle/最终 pipeline 实现核对，不代表后续模型预检或训练已获放行。

现有训练数学核心可以复用。必须新增跨协议输入验证与最终准备入口，保留原模块与所有封存。**当前 bootstrap 没有硬编码抽 600：硬 600 检查的是 planned manifest，应该保留。**

| 工作 | 可复用接口及行号 | 接口约束 |
|---|---|---|
| A 原始权重导入 | `training_pipeline.load_old_members(package, import_spec)`，267–289 | 依 `training_design_v2.old_weight_import` 验 ranking 与四个原始 checkpoint SHA，按原成员数字顺序1041–1044读取；不能改成首轮 A 或 B200 warm start。当前 prepare 只绑定这些路径/SHA，不调用该函数。 |
| A 初始化及训练范围 | `training.initialize_model('A', seed=..., warm_start_state=states[member])`，244–263；`configure_trainable`，229–241 | A 不接受新 `preprocessing`，完整复制各原 state_dict，所以旧 PCA/归一化/所有 buffers 保留；仅 residual、advantage 可训练，lr=1e-4。 |
| B train-only PCA | `training.fit_train_preprocessing(arrays, rows, range(N_valid), norm_mean=..., norm_std=...)`，192–226 | 唯一有效 train 源各一次，bootstrap 前拟合；使用原共同视觉归一化，输出视觉16/语言8 PCA和固定 residual_scale。四个 B 共用这份投影。 |
| B 新初始化 | `training.initialize_model('B', seed=..., preprocessing=prep)`，244–263 | 不接受 warm_start_state；全小网络重新初始化、全部参数训练，lr=3e-4。不能携带 B200 参数进入新 PCA 坐标。 |
| 有效源 bootstrap | `training.stratified_episode_bootstrap(rows, seed=...)`，277–290 | 对 TASKS 固定顺序，每任务有效源组长度 N_t，`choice(group,size=N_t,replace=True)`；总长度 N_valid，而非600。保存 indices、actual episode_ids、multiplicities、各任务 available/drawn。 |
| 采样种子 | `training_pipeline._sampling(rows,config,'final',path,member)`，166–170 | 与 `fit_member` 371–376同一 seed_for 键：training_bootstrap / training_minibatches + final/path/member；保留原 namespace，不加 teacher/轮次权重或换种子择优。 |
| alias与源平均损失 | `training.dedup_weights`，75–108；`loss_parts`，121–167；`_validated_training_data`，293–317 | raw alias组内去重，gain排除a0别名，重复正反组对去重；各项先源内平均，然后整源 mean，权重1/1/0.5。bootstrap有意重复的源保留抽样 multiplicity，不按有效候选数/收益加权。 |
| canonical计算与重载 | `training.canonical_features`，266–274；`training_pipeline.predict_member`，300–320；`audit_reload`，393–455 | singleton source 特征路径必须保留；初态和导出均核全有效源的13候选概率及槽0/11梯度、成员和集成一致性。只在后续明确预检放行后调用。 |
| 优化/固定检查点 | `training.fit_member(...phase='final',stop_after=4000)`，342–422；常量31–34 | 8个成员（A/B各4）最多32000更新；每次更新先记账。final检查点200/400/800/1600/2400/3200/4000；batch32整源、AdamW decay=.01、clip norm1，沿原方案。 |
| 原开发集选择 | `training_pipeline.development_selection`，323–361；`training.choose_checkpoint`，465–486 | 原100计划dev、95cut+5共同结局。候选均值概率argmax，a0槽0赢平局；最大净增益、最小损害、最小gain MSE、更早step、最后偏好B。不能换新policy5结局或B200候选代替原开发13候选bank。 |

## PCA 与权重身份

canonical原输入是 history4096、language2048以及本体历史/过去动作/mask/剩余预算。`corrector.critic.observed_features` 21–28 把最后视觉帧与mask均值拼成8192维，再做视觉 PCA；语言先固定 layer_norm 再做语言 PCA；不能把历史两代 critic 的 PCA 坐标、Q或梯度作为共享 canonical 特征。

`training.fit_pca` 170–189 保留中心化 float32 SVD、`std(unbiased=False)`、scale floor 1e-3 和 clip诊断；`observed_features`/`project` 原有±8 clip、normalizer floor 1e-6不变。`fit_train_preprocessing`先验证唯一 train indices，再切出状态数组；PCA不得用候选/后缀重复、bootstrap重复、dev或缺cut填零。有效源数需大于16。A继续旧投影；B共享新投影。预检应像旧 pipeline 483–487 一样先验证四个原成员 norm_mean/norm_std一致。

原权重设计绑定为 `assets/critic/ranking.json` SHA `fa8e2b4b0ee166372a036e1656036812be8d34335a1f287240a80f34a3d3436c`，成员1041–1044。B200只作为第二轮采集 critic 来源；它不是最终 A 的初始化，也不是 B 的初始化。

## 必须在新入口解决的协议与 schema 风险

1. `training_pipeline._specification` 93–101 强制所有输入 `input_protocol_sha256` 等于单个 collection协议；`_require_preflight` 149–155 也只接受一个 collection config/freeze绑定。`load_preflight` 535–537 会再次调用这两个函数。因此仅新增 prepare 字段仍无法直接复用旧 `preflight/run/load_preflight` 编排。新入口应绑定真实两轮 collection 与独立 input_bundle，不能伪造子包协议或临时 monkey-patch旧函数。
2. `load_audited_dataset` 172–211 能在各子包真实协议下复用，但只接受 `native10_input_artifact_audit_v1` 单包；不应拿聚合 audit 冒充这个 schema。先核 round1 train / round2 train / original dev 三个子包、各自 audit、config/freeze及模型来源，再通过新 bundle loader返回独立派生 train pack。聚合 metadata有自己的 bundle身份；子包 `input_protocol_sha256` 不改。
3. `validate_phase_datasets(...,'final')` 214–264 的600计划训练/100计划开发检查与合法no-cut兼容：有效train行可少于600，262单列train_reached，不能删除planned覆盖或伪造行。`stratified_episode_bootstrap`本身无需改动，不能改成每任务120次或每轮300次固定抽样。
4. `validate_phase_datasets` 244–255 对 `packed.rows` 与原manifest行（除planned_slot_id）逐字段一致。新增 bank/protocol/generation critic 等完整来源应放 metadata.records 或按行对齐的sidecar；若直接给 rows 新加这些键，复用该校验会失败。actual episode应仍为登记的主源/合法备用身份，planned_slot_id只用于覆盖映射；每主槽最多一个有效actual，不能重新编号或把两轮相同身份重名。
5. 若聚合层保留 `native10_dataset13_v1`兼容格式，数组仍须保持 `dataset.load_saved_dataset` 581–585 的精确字段集合；新增teacher/protocol数组会被拒绝，应使用显式聚合schema/sidecar。两轮 raw_actions、actions=C(raw)、outcomes、alias/pair权重及normal控制保持原定义，不能把normal加入13槽。
6. `prepare_fit.py` 的SCOPES、datasets/stop_after、preflight目录和phase全为round1（21、110–133、186–188）。新final prepare不可只替换目录名；需要新scope/阶段映射及跨协议身份验证。`training_result_audit_v1.py`同样硬编码round1、2400和40个检查点，最终审计应另写版本，不能原样声称已覆盖final。

## 建议的 final prepare 绑定

新配置宜保留原 `training_pipeline` 的 design/code_files/stop_after/preflight概念，但把单一collection身份替换为显式联合身份，并由新pipeline验证；不向旧pipeline喂兼容伪字段。最小接口内容：

- `input_bundle={manifest_path,input_bundle_sha256,seal_path,seal_sha256}`；manifest内分别列round1 train、round2 train、原dev的pack/audit/config/freeze/protocol和生成critic来源。
- `collections={round1:{config_path,config_sha256,freeze_path,freeze_sha256,protocol_sha256},round2:{...}}`；所有子包bindings保留真实 `input_protocol_sha256`。
- `design={path,sha256}` 是新metadata快照，approved_parameters/candidate_schema/old_weight_import/budget仍与批准v2一致，另附最终契约及有效N解释；原v2只读。
- `stop_after.final={A:4000,B:4000}`，固定7个检查点；若后续批准更早固定停止，应在预检前明确冻结，不能看中途结果改值。
- 阶段 `final_fit_preflight` 必须显式sim0/update0及独立READY绑定上述bundle/collection/design/code身份；`training_final` 是独立后续训练stage，上限sim0/update32000，总update51200。当前prepare不调用PCA或initialize。
- 预检身份至少包含phase、原manifest SHA、bundle SHA及seal、子包bindings、两份collections、namespace、design、实现SHA、stop_after、计划覆盖与有效源列表。随后fit沿用passed预检的同一路径/SHA及初态export，不在fit时重新fit PCA、重新采bootstrap或重新创建另一个design路径。
- 保留 sampling.json、trainable_masks.json、pca_fit_audit.json、A/B全部初态model seal与reload audit。final fit前核两路径、四成员、全部有效源、numeric runtime与固定抽样清单；不能只存在一个complete文件就通过。

编排可以复用上述纯训练函数与导出函数，但新的bundle验证、预检scope/identity、数据装载与load_preflight适配需作为新模块独立冻结。无需修改冻结采集或训练核心，也不需要为了合法no-cut改bootstrap数学规则。

## 本次读取身份

| 文件 | SHA256 |
|---|---|
| coordination/NATIVE10_FINAL_INPUT_CONTRACT.md | `bceeccecbe2f5a41a27f05e8245ee8b9e68c525e8cb3d653a3460f275fab54a0` |
| experiments/native10_training_20260916/training_design_v2.json | `23fecfe3a86a0011f38b4249e21d44eefaf1573f108586d7295c9ee4e070d4db` |
| experiments/native10_training_20260916/training.py | `c111518c3ce2973fae00ce1b4653211792390fbcfff6ce965e4759ad6a00be25` |
| experiments/native10_training_20260916/training_pipeline.py | `8488dc82370a2dfb516d6da4f8da1e76200596194a64861a21b81a4d95788655` |
| experiments/native10_training_20260916/prepare_fit.py | `163cc1f01135ae25573142fe4c207b9ac11990a6528b5e05feababde3e615248` |
