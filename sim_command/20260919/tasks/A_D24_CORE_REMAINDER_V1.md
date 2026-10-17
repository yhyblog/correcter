# A：E6和E3接续任务

任务 `A_D24_CORE_REMAINDER_V1`，revision 1，owner A。直接执行既有D24范围内的必要适配与训练评测；无需再交CPU_READY等待分析放行。授权见 `deadline_20260924/CONTINUATION_AUTHORIZATION_20260922_V1.json`。A原N2500、主链5500、pilot120全部结束，不重启这些入口。

## 自动队列顺序

1. E6：100个既有dev身份的因果trace → CPU冻结异常阈值 → 同50个test两触发器各50条。
2. E3：现有epoch30 VLA-Corrector → MT50 H10共500条。
3. E3：GAF-v1 adapted非空合法train/dev张量 → 三成员各10000步 → MT50 H10共500条。

这是默认优先级，不要求空等：某项尚需适配，先运行另一项已经可执行的任务。GAF输入未就绪不阻塞E6和VLA-Corrector。A不等B的E1、E8或新公共池。复用原8常驻模型worker和后台调度方式，按工作需要复用模型；不新造通用队列认证工程。单个失败给具体原因，已诊断错误允许既有授权规定的一次修正重试，成功样本不重跑。

### E6：只比较触发，不改下游

- 五任务 disassemble / pick-place-wall / shelf-place / stick-pull / stick-push（均-v3）；H10、C10、300控制步、最多干预一次，两臂下游均R。
- 继承A已完成R_H10的底座、D两成员、G0、特征及动作变换。收益阈值仍0.05，其他资格/时序条件不变。
- 异常定义继承 `results/B/B10/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z/configs/METHODS.json` 的 E6-D5-R：在s时刻用当时已知未来5动作保存D预测；s+5收齐真实特征，按各D成员固定训练delta_scale标准化，取两成员×5步×4096维平方误差均值。没有合法成熟预测则不触发，不用未来信息改历史预测。
- 源表直接用 `work/B/B_D24_E6_PREP_V1_r1/SOURCE_AND_IMPLEMENTATION_PREP.json` 的development.rows（100）与test_candidate.rows（50）。dev是历史初态重放，不新增100个身份；包括原来没有有效cut的5个父源。不要把95个cut行冒充完整dev。
- dev使用N轨迹，旁路计算两种报警，不实际改变轨迹。按全部100个episode匹配G0报警episode数，平局先更少报警、再更高阈值，不使用成功标签。复用 `results/B/B_INDEPENDENT_PIPELINE_PREP_V1/code/calibrate_e6.py`；已有合法同协议trace可复用，缺失则一次固定dev重放。阈值和test源表在test前写定。
- test明确是各任务ordinal10..19，与A主表ordinal0..9不同。因此本次两臂各跑50条，不能直接拿A已完成R50作这批的配对侧。两臂同env/policy seed、同renderer；无需严格状态一致性证明。test不强制配平报警数，不增加阈值sweep。
- 输出两臂SR、逐源救回/损害、实际报警episode数/干预数、策略调用及耗时、技术失败。小样本证据不外推MT50排名。

### E3：先完成现有VLA-Corrector

- 共同π0.5 SFT030000和A主表同500源：`deadline_20260924/A/config/TEST_SOURCES_V1.json`每任务ordinal0..9；H10/raw50、相同300步和终局口径。只复用源身份，不根据A测试结果选参数。
- 已选模型：`/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/outputs/metaworld_very_hard/corrector_pi05_mt50/h1_k10/best_cosine_model.pt`（epoch30）及同目录config.json。
- 固定本地仓库commit `9d23a0ba6fad562d3ed1a68fc52c8a12459abb41`，Python `/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python`。原模块 `lerobot.scripts.lerobot_eval_modified_detection`，原命令参考 `vla-corrector/reproduction/metaworld_very_hard/04_eval_very_hard.sh`。包装器旧Very Hard任务筛选需替换为完整MT50测试源，不重训。
- 保留该方法原生逐步safety检查、cooldown10、可重复干预；safety_k10、eta1、guidance_every1、attract_delta_z_correction沿原部署设置。具体阈值从原部署配置绑定，不能用新test结果猜选。不要套我们的G0 once触发。
- 旧训练数据与本方法未必相同，须如实披露；当前D24取消“统一最终公共训练池”前置，不声称同数据训练。

### GAF独立接续

- 使用同B10包 `b10_adapters.py` 中gaf_view / GAFVelocityAdapter / pi05_denoiser_hook和已冻结METHODS；标注GAF-v1 adapted。每次native采样、每个denoise step引导，不套G0 once，不称官方原版完全复现。
- 可用视图 `results/B/B11_COMMON_POOL_VIEWS_CPU_V1/indices/`；拟合入口 `work/B/B_INDEPENDENT_PIPELINE_PREP_V1_r1/code/fit_worker.py`，三份配置在其兄弟configs目录 `gaf_v1_member_{9201,9202,9203}.json`。
- 当前视图并非已物化张量，development=0不是可训练证明。允许用已有历史train600/独立development、真实成功时刻及合法窗口完成必要物化，记录实际父源与分割；缺RGB/特征不能补造，不能从test训练。可用非空开发集按既有development MSE选checkpoint；没有合法输入则明确报告缺项并暂停GAF，不恢复475采集。
- 三成员各10000步，batch256，lr/wd各1e-4，gamma=.99/真实控制步，其余沿冻结配置；训练后同A500源H10一次评测，不加方法超参扫描。

## 执行及交付

- 本接续阶段上限3000次物理rollout attempt（含dev/失败/纠正），小网更新30000；与既有A节点总上限18000/200000累计核算，不能以新ID重新获得总预算。
- 原已计划100个dev身份的重放最多200attempt，无新的dev身份。GAF使用已有数据，不额外采集。
- 开始前只做必要的模型/动作维度与单位、源分割、普通资源可用检查；在计划episode里检查真实观测有效性。禁止额外完整SHA/一致性/MJB/状态回放审计、百万事件账本或独立GPU探针。
- 正式整波全部holder停止，整组退出后恢复；同卡holder族退出后才模型Popen。8卡有用任务为目标，不启用尾部空卡holder；不终止无关进程。
- 100dev结束自动校准并接E6 test；其后自动接已准备好的E3，不等分析逐格验收。稳定后退出LLM等待，沿已有原会话完成事件通知。最迟截止期按总接续文档执行。
- 每阶段保存小型config/source manifest、逐episode success/technical_error、interventions、policy_calls、时间与汇总表即可。结果写 `results/A/A_D24_CORE_REMAINDER_V1/`，ACK及滚动/最终回执写 `receipts/A/A_D24_CORE_REMAINDER_V1_*`。队列投递不冒称运行。
- 若B在所有权转交前已真实admit某个相同E6/E3单元，保留该在途任务，A只跳过准确重复单元并先做其他工作；不用等待整个B。
