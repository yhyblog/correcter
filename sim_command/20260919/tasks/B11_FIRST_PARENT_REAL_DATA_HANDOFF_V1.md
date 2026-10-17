# B11：首个真实父源的CPU兼容交接

这是原B11_COMMON_POOL_VIEWS_CPU_V1的定向集成补充；原task/release/hash不覆盖。允许只读以下新train父源的已有记录，建立CPU元数据窗口索引和资格报告；不运行特征提取、模型、Torch/GPU或训练，不物化新token/cache。全部真实计算额度仍0。

分析已验收索引：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/manifests/COMMON_POOL_ACCEPTED_PARENTS_V1.json`。
运行文件入口：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_COMMON_POOL_FIRST_PARENT_V4/RUNTIME_FILE_MANIFEST.json`，SHA256=6f68b72cfdc78d66719497c80bf07bb9c346f77c0e7e67fd382691977b64ed9f。
根目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/P11_COMMON_POOL_V4_runs/PROPOSED_A11_shelf_train0000_parent_V4`。冻结source/parent/seed/版本不改，不重复处理`.partial_*`硬链接别名。

1. 读取canonical `reserved/ATTEMPT_COVERAGE.json`、`PAIRED_LABELS.json`与四个`AGGREGATE_INDEX_*.json`，根据label_key逐成员验证双repeat/终局/冻结closure资格；不要把logical aggregate当物理轨迹。
2. 按原sidecar_v1+supplement_v2语义验证共享BANK计划引用、本branch观测与一致episode ID，公共cost refs缺失不补造，私有成本不伪拼UUID账本。
3. 从真实transition及已保存4096维feature/2048维language元数据形成D5/GAF窗口索引，绑定已有action/normalizer/state变换。原`views=false`表示窗口未装配，不能直接拒绝全部raw。报告真实可用/拒绝窗口数与明确理由，不把合成数量混入。
4. 本normal是policy rollout、无256×2048 endpoint token，应作为LVM正确拒绝真实案例；不得宣称LVM正样本已就绪。原任务synthetic正例继续保留，既有示范与未来token提取预算另列，不能为本次检查新增encoder调用。

输出原任务的实际consumer快照/兼容报告和RESULT；无需另起GPU预检。仅对新增consumer路径做CPU检查，不重做A全树SHA/已有审计，不改A文件、公共接口或共享dispatch。数据仅供本CPU任务消费，训练和B采集仍未授权。
