# Smol/X MT50 H 扫描只读核对（2026-09-23）

根目录 P=`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919`。本核对无模型/硬件/实验/部署操作；不修改共享控制文件。

## 新单元与分工

- A: SmolVLA H20/30；B: SmolVLA H40/50；C: X-VLA H20/30。
- 每 H 运行 N、R-multi、L11 Post-multi、L11 Velocity-multi，各原500源，共每机4000/三机12000新终局。Post是当前论文，Velocity保留给其他工作。
- H10全部复用现有终局；Smol H10 N四unknown不补成失败、不自动补跑。无once/random/新采集/新训练/另开GPU预检。

## 固定资产与已成功实现

### SmolVLA

- 底座050000：`/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/050000/pretrained_model`。
- 已完成L11 P/V真实代码：`P/results/B/B_D24_L11_RETEST_V1/code/`；尤其 `native_client.py`, `smol_server.py`, `encoder_server.py`, `feature_server.py`。
- 专属D/G0根：`P/results/B/B_D24_SMOL_AUX_RETRAIN_V1`；D为`fits/D_1241/final.pt`,`D_1242`；G0为`fits/G0_1341/final.pt`,`G0_1342`；专属归一化`dataset/NORMALIZATION.json`；证据`FIT_SUMMARY.json`。
- 当前Q必须用 `P/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/models/L11`（ranking含4成员）；实际权重`fit_r1/fits/L11_fit9101_member{1041,1042,1043,1044}/final.pt`。不得回退旧`Q_19301...`或L01。
- `config/SMOL_BASE.json`记录 raw H=50、old K=10、NFE10；base_environment=`mw-smolvla-lr044`，保留原runtime launcher环境。
- Smol L11有效格见`P/results/B/B_D24_L11_RETEST_V1/FINAL_CELLS.csv`、`FINAL_EPISODES.csv`，Post250/500、Velocity247/500。
- 注意 `B_D24_L11_RENDER_RECOVERY_V1`实际主要是转入A的π05 H30恢复；不要误以为其 NVIDIA/30Hz参数就是Smol协议。`B_D24_L11_RETEST_V1/config/CONFIG.json`也混有π05阶段字段，不能盲目整份用作Smol科学配置。

### X-VLA

- 底座030000：`P/results/B/B_D24_SPRINT_V1/r1/jobs/xvla_mt50_s42_D24_r2/training/checkpoints/030000/pretrained_model`。raw chunk30，旧执行K10；不改底座chunk。
- 成功最终实现：`P/results/C/C_D24_L11_RENDER_RECOVERY_V1/xcode/`；尤其 `native_client.py`, `native_velocity.py`, `feature_server.py`, `gpu_job.py`，配套该包`code/`与`config/`。Post236原有效+264恢复，Velocity500原有效，均完整。
- 专属D/G0根：`P/results/C/C_D24_XVLA_AUX_RETRAIN_V1`；D为`fits/D_2241/final.pt`,`D_2242`；G0为`fits/G0_2341/final.pt`,`G0_2342`；归一化`dataset/NORMALIZATION.json`。`P/results/C/C_D24_XVLA_MULTI_EVAL_V1/FROZEN_HEADS.json`可作D/G0证据，但其中旧Q不是新L11。
- 当前Q：`P/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/ensembles/L11_s9101`，实际`training/L11_s9101_m{1041,1042,1043,1044}/final.pt`。
- `P/results/C/C_D24_L11_RENDER_RECOVERY_V1/config/X_NATIVE.json`记录raw30/K10，base_environment=`mw-xvla-lr044`。`config/X_ENGINE.json`继承部分旧π05/once文字，实际运行由外层覆盖；不要把旧`max_interventions=1`、`generated_horizon=50`或旧Q路径当作本轮有效协议。
- 最新有效汇总`P/results/C/C_D24_L11_RENDER_RECOVERY_V1/AUDITED_FIVE_CELLS.csv`、`AUDITED_SUMMARY.json`；Post411/500，Velocity407/500。

### 共同外部编码器

- 两底座均沿用冻结π05外部视觉/语言特征，不是Smol/X自身特征；额外参数/调用/时间独立计量。
- 编码器配置：`P/work/B/B_D24_E8_POST_V1_r1/BASE.json`（与C `config/ENCODER_BASE.json`相同关键资产）。π05 checkpoint：`/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/outputs/metaworld_very_hard/sft_pi05_mt50/checkpoints/030000/pretrained_model`；投影`/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/projection.npy`。
- 跨机部署需私有配置/代码，主机、GPU UUID、thread/socket路径全部当地绑定，不复制B/C实例身份。

## 源、环境、RNG与算法冻结

- 原固定500源（50任务×每任务ordinal0..9）：`P/work/B/B_D24_E8_POST_V1_r1/POST_SOURCES.json`，其`sources`与`P/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/config/TEST_SOURCES.json`同源；先前记录文件SHA `ea5a9b7e1190a73f3019cd2f9cfa427404e159d80a902147bd514488c7f163a9`。
- 源字段保留`source_id,task,task_id,episode,reset_seed,policy_seed`。例D24_MW_t00_e00：reset24100000、policy34100000；每task步长1000，episode0..9。原表没有独立repeat字段，应null+原因而非造新重复。
- 真实环境：Mesa llvmpipe、corner2 480×480、MuJoCo dt=.0025、frame_skip5、80Hz控制/400Hz物理、action_scale=.01、真实agent_pos4、T300。不能切换π05的NVIDIA EGL/30Hz/.015后混用H10基线。
- NFE10；监测绝对t%5==0；至少5真实历史帧、至少4执行动作、native queue age>0、至少5旧队列动作、剩余预算>=10；G0双成员均值严格>.05；C10内不监测/不重入；取消episode总干预帽；不加Q改善门/回溯/重采样。
- 候选seed保留`seed_for('D24_designated_a0', source_id, policy_seed, absolute_cut, namespace='corrector_native10_training_20260916_v1')`，不增加方法/H/worker/临时计数因子。自然RNG独立于候选域，源间独立。
- 专属D/G0及Q全部冻结，不因H变更重新选型或训练。它们原标签含native10后缀，H>10是同模块执行H稳健性测试，不宣称每H校准收益。
- **坐标桥必须沿用各底座已验收实现**：Smol Post=`environment gradient × native_action_slopes²`；X Post既有合同明确沿用frozen π05 S²（feature_server返回`post_direction`），Velocity则本底座native inverse-normalization/clean head。不要在本H扫描中默默修改X Post度量。

## 必需的最小H适配（静态已定位）

Smol `code/native_client.py`和X `xcode/native_client.py`目前都硬编码：

- natural refill `if raw is None or age==10`；
- monitor eligibility `min(10-age,300-t)>=5`；
-结果/READY/协议 `native_K=10`、Smol`H=10`；
-干预事件`restore_native_K=10`。

**仅修改配置K不会生效。不能把所有10机械替成H，因为C10必须保持10。** 应私有参数化：自然queue_limit=H，触发后queue_limit=10且locked_until=t+10；十步后清空raw/tail并新采样自然H（而不是继续执行raw剩余H−10）。下一次自然合法cut以queue_age/remaining判断，不能固定5+Hk。所有H≤原raw长度，SFT预测长度不变。

N arm当前客户端未显式支持；必须关掉monitor/触发/纠偏，普通自然H路径保留；否则把method='N'塞进旧客户端仍会被G0触发成R。R arm保留相同G0/C10，Q/动作梯度零。所有ownership/claim/output key含model/H/method/mode/loss/fit/source，防止不同H互相误去重。

只做定向CPU队列检查，首批正式episode提供真实观察；不要恢复历史全量一致性或额外GPU预检。

## H10复用与缺项

| 模型 | N | R-multi | L11 Post-multi | L11 Velocity-multi |
|---|---:|---:|---:|---:|
|Smol050000|234/496，4unknown|245/500|250/500|247/500|
|X030000|403/500|412/500|411/500|407/500|

- P/V统一最终入口：`P/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_CELLS.csv`、`FINAL_EPISODES.csv`；不得复用旧L01行。
- N：`P/work/B/B_D24_E8_POST_V1_r1/VALID_N_INDEX.json`的smolvla/xvla数组；C另有相同用途`P/work/C/C_D24_MW_VELOCITY_V1_r2/VALID_N_INDEX.json`。旧N字段H表示raw length（Smol50/X30），K=10才是此处执行H10。
- Smol N缺4：`D24_MW_t18_e01`, `D24_MW_t21_e06`, `D24_MW_t23_e01`, `D24_MW_t24_e08`；H10保持unknown，不补失败或虚构500分母。新H20...仍按原完整500计划，不删去这4源；跨H配对按共同有效源。
- Smol R最新500：`P/results/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1/AGGREGATE.json`筛`stage='R',method='R'`，逐源result有准确路径；验收回执`P/receipts/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1_RESULT_r2.json`。不要使用`B_D24_SMOL_MULTI_EVAL_V1/FINAL_CELLS.csv`的早期4/4中间表。
- X R最新500：`P/results/C/C_D24_XVLA_MULTI_EVAL_V1/FINAL_CELLS.csv`及`FINAL_EPISODES.csv`/`FINAL_SUMMARY.json`；筛R，旧Post/Velocity不是L11。

本轮只需新H 24格×500=12000，H10八格继承：H10两个模型×四方法共4000计划，其中3996有效+4unknown。全H八档×四方法共32格16000计划，终局期望15996有效+旧4unknown（若新H没有新技术缺项）。
