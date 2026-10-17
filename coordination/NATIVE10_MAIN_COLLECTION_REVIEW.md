# Native10 第一轮主采集独立审查

2026-09-16，增量复核执行端16:41之后更新。只读检查当前主采集、dataset/training接口、v2设计/schema及EVAL20修订；未仿真、未训练、未修改执行代码。此版取代早先尚缺EVAL20接线的阻塞结论。

## 结论

**方法与数据审查通过，建议分析端放行第一轮300训练＋100开发采集。** EVAL20、scene初态记录/去重/替补、主900源及阶段预算现已接入，原collect-before实质阻塞已解决。执行端完成当前主文件CPU结果归档及配置/代码冻结，并由主线程确认32-worker独立复现审查后，即可按READY启动；无须等待真实模型拟合。此次不放行训练、第二轮、校准或保留。

## 已核对一致的部分

- `main_collection.py`在活状态、合法队列中点保存5/15/45/95以及首报警anchor；scheduled不到目标按15→5、45→15→5、95→45→15→5选择；首次报警组仅在整集无报警时按15→5训练fallback。开发不使用fallback。主cut只有一个，其他anchor仅为已观察状态缓存，不作为额外独立episode。
- 正常队列从初始native10，干预十步、正常臂finish-current-10、raw a0及实际可行delta、后缀decision-index配对均复用已审查P0语义。主bank/rollout按版本隔离，source复用须核验VLA/D/G0与封存身份。
- 13候选保留a0、两通道正反、随机半/全半径正反、三引导、reverse-post；normal另列。dataset审查raw→C、对称、mask、完整4个配对后缀、attempt引用及别名。缺失不伪造失败，无cut保留计划记录。
- A/B必做、两轮新600训练源、B train-only PCA16/8、四成员source bagging、1/1/.5源内去重损失和每轮一个已选模型的实际开发比较仍符合批准设计。真实PCA/模型重载审计属于有真实数据后的fit前事项。

## Collect-before：增量复核已闭合

1. **真实scene记录已接入。** 主capture在reset后、首次policy动作前调用`capture_scene_identity`。记录qpos/qvel、act、mocap、物体/目标及model body/site/geom位姿；scene hash排除seed/RNG/time/计数器/未作用随机向量，按位置、角、速度、四元数等分别规范化。原始完整数组与exact hash独立保留；字段不进入critic。scene registry按task检查所有已初始化主split，用锁防并发重复接纳。
2. **替补及held隔离已接入。** 每个primary slot两个有序备用；仅在首次动作前的物理重复或初始化失败时允许下一备用，前序拒绝记录必须完整封存。替补capture计入technical_reserve，普通失败/无报警/不可达cut不换源。首轮银行仅登记300训练＋100开发，runner只分配这些slot；held及其备用虽预注册但不初始化。后续阶段仍需独立READY。
3. **EVAL20已同步。** v2 JSON/schema与主collector均为600/100/100/100、train/dev/cal/held重复4/4/2/4、48800计划/50000硬限/1200储备；独立主bank恢复1100次。第一轮上限23200、400个primary slots准确，未借此次修订增加训练或开发分支数。
4. **Manifest已核对。** `preparation/main_registration_v2/primary_manifest.json`有主900＋原P0 20；主开发/校准/保留均每任务20。原820条记录逐对象保留，新加cal/held各50。combined另含1800备用，不能计作新增已完成样本。原P0清单与封存不改；主配置/冻结写入独立`main_protocols`目录。
5. **阶段权限正确。** pending配置仅申请`round1_native10_local_labels`与`preregistered_initialization_replacements`；训练、第二轮、校准、held均为未放行scope。冻结入口核验P0封存及并发审计，复制独立协调快照，再检查主代码/hash/lifecycle。更新READY与实际freeze是执行交接，不是要求新增科学验证。

当前CPU通过数量来自执行端状态与测试材料；本子任务未重跑CPU测试，也不把合成测试称为真实新数据训练审计。主线程/执行端应在当前版本冻结时归档对应CPU结果。真实dataset还不存在，首轮采集无需等待fit审计。

## Fit-before：可在第一轮采集期间完成，不应拖住有效采集

- 对真实封存source/bank/branch重建训练与开发数据，验证全部计划episode覆盖，四后缀及attempt/alias一致；先缺失审计再拟合，不凭内存数组自述完整。
- 第一轮B PCA仅用第一轮训练有效源；最终才用两轮合集。保持16/8、scale floor1e-3、CPU两线程及canonical singleton路径；在新真实数据记录近零PC、尺度和clip，验证原模型/保存重载/FrozenObjective的概率与动作梯度，不增容量或raw特征。
- 完成四成员A/B检查点编排、同一100开发银行选择、ranking导出及实际引导加载审计；实际开发rollout每轮只跑一个所选critic，不能省略，也不能把A/B各跑一遍而翻倍预算。
- 后续校准只用低自由度已登记规则，held须最终方法/权重/门限冻结后才访问；这些后续阶段不属于此次首轮采集放行。

## 首300源是否足以另审查中断目标

已有字段足够，无需增加仿真臂或现在重训G0：dataset的`outcomes[:,0,:]`是同cut replan四次标签，`control_outcomes/control_valid`是native四次，配对repeat/后缀/attempt均保留。cut的`context.npz`保存当时观察history/proprio/past_actions/language/remaining及旧raw `full_plan`；`anchor.json`的queue保存horizon10、age、remaining_steps等，合法旧队列是`full_plan[age:10]`，不能把其余未承诺的50步计划算进有效长度。anchor有当时旧G0 gate，source事件有该时刻成员分数。

当前dataset没有将旧queue/G0单独打成特征张量，但可以从已封存source经CPU补提取；这不是采集缺口。应保持这些证据引用。训练fallback的完整source summary可能含晚于cut的事件及最终成功，后续G0输入只能使用选中cut的anchor/context和同一时刻event，不把整份summary作为输入。正常短旧队列是独立门控信息，始终不填充成critic槽0的a0。

本审查不以P0是否有显著收益为训练门槛，也不要求执行端在授权范围内重新向用户请示。新增用户硬要求对应的初始化数据接口现已落地；剩余真实dataset/PCA/模型审计明确属于fit-before，不能成为无意义等待采集的理由。
