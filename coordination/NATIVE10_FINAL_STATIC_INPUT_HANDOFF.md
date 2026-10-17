# 真实最终训练输入封存交接

静态audit→dataset→600源联合bundle→pending→metadata preview已全部完成。**这是实际输入审计通过，不是600源真实模型预检通过，也不释放训练。** 当前live READY仍v8。

第二轮300/300完整银行、五任务各60，无技术缺失、重试、替补或reserve；两轮合计train600/600有效，开发保留100计划初态/95有效cut/5共同结局（4成功1失败）。开发每任务20个实际初态，未将共同结局删除或补成未知失败。两个collection原protocol与child seals、不同生成critic及canonical原始特征身份均保留。

| 产物 | seal SHA256 |
|---|---|
| round2 dataset | 9dcce602261a6cc2c680f8bb85b770c2a08d576c024ea38efe64f3d9e090dcba |
| round2 completion audit | deb06a0c869650781e733c4a6e1af97f50a6d9ccd36185fc63d8d38d75e1e69a |
| 联合bundle | 9e7798d534459e1f57dc32572f8634980faf963b246222ceb10e7fb1a2db805f |
| pending | 59e7e7f0ffc9f384ea4405ddd4a694ec5604c62f99ffca26a3ce5e7acae1810d |
| metadata preview | 14c1d5b5e8efdcbeac910ddbc9137e3a861c996d6a84d6c3ff61364924037a3f |

独立 input_bundle SHA：`d0395587afc390d5f9a4da9df075ae4b3797cbc7933bfeae42ebad4359053b87`。

**稳定 specification SHA：`08891c3ee6feb71aa41a8cfa7cb0fbed61930e16eb8938cf5bfeff1dd24ad946`。**

全路径及其绑定见 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_input_handoffs/final_static_input_v1/summary.json`；本汇总seal `ca42849e10616b4a596545cc6322c191464dcfe97b56d6c6f2cce09eb8dbaae7`。真实preview文件 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_previews/final_input_preview_v1/metadata_preview.json`，文件SHA `87329ae02a5b7c74afce1c474f02e978aff7bab34bd197af7cd662734f17b33a`。后续READY字段可直接取 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_input_handoffs/final_static_input_v1/preflight_ready_binding_contract.json`，scope/stage均final_fit_preflight，sim0/opt0；正式执行仍需分析端另发READY并独立prepare/freeze。

目标运行时已绑定lerobot Python3.12.13、Torch2.7.1+cu126、NumPy2.2.6、CPU float32/2线程。数值决定3e556bad...88cb1a与目标runtime V2证据、71项联合CPU证据均已提供。canonical同shape严格重载保持，dense跨shape仅显式诊断；实际真实预检尚未执行，未用toy误差建立实数据阈值。

静态链耗时769.32秒：全轨迹dataset audit 237.17秒，bundle 274.02秒，pending/preview 258.03秒；峰值RSS 1.886GiB。资源账本逐字未变：全局42874/50000 sim、19200/51200 optimizer，新增仿真/优化0，真实PCA/初始化/推理0。八holder已恢复，原封存未修改。
