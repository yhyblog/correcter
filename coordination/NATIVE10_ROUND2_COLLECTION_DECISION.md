# 第二轮300训练源采集：分析端决定

2026-09-16。首轮训练及一次100源五臂真实开发测评完成，结局/CI与资源封存已独立复核。按用户已授权的600训练源计划，**条件放行第二轮300训练episode的采集**。完成本阶段独立配置、必要CPU检查和冻结后，执行端直接启动，无需再次等待用户或分析端许可。尚未满足技术条件时保持不运行。

## 方法依据与不变项

首轮重规划相对normal为+9pp；V/D/post相对replan为+2/+2.75/+2.5pp，区间均跨0。数据不支持把direct的微小名次优势当作最终赢家，也不支持继续只增加同批训练步数。第一轮300训练源的有限局部标签覆盖，以及旧候选排序与新梯度生成的差距，支持继续采集独立状态和当前critic方向的真实标签。

本阶段执行原预登记的迭代数据采集，不增加新方法搜索：唯一固定B200四成员只用来生成候选；G0、VLA/D、native10/raw、十步prefix、后缀、总300步、flow公式/时间/强度与matching均沿用。13候选、独立normal控制、随机/正反/半全半径候选完整保留，不只采当前critic预测好的方向。所有300源采完前不更新生成critic。

具体结果解释见 `NATIVE10_ROUND1_POLICY5_ANALYSIS.md`。新旧阶段如尚未完成全随机流等价审计，不据共同source宣称跨阶段严格配对；本次放行不依赖这种声明。

## 唯一采集范围

- stage `round2_labels`，scope `round2_native10_local_labels`；bank version `round2_labels_v1`，独立协议建议 `round2_v1`。
- 只采原primary注册的300个train round=2：env_seed 2026111300–2026111599，五任务各60。不是包含备用项的combined清单；不重新注册或替换为更有利的seed。
- 本阶段**允许且需要新primary capture**，最多300个正常计划capture。不要继承刚结束policy5的禁止capture规则；policy5冻结本身不改。
- 每源capture1、独立bank restore1、13候选×4后缀加normal×4，最多58次；stage硬限17400，optimizer上限0。alias沿用首轮完整执行候选、训练损失去重的实现与审计规则，不因本次授权新增物理标签复用。无合法cut可节约实际次数，必须保留计划分母及原因。
- 当前simulator累计25474、optimizer19200。若新阶段用满17400且无技术储备消耗，sim累计42874；总sim硬限50000、optimizer硬限51200不变。
- 预登记的pre-action场景重复或初始化技术失败只走原有顺序备用链，单独记 `technical_reserve`（scope `preregistered_initialization_replacements`，整个工作流累计上限1200，目前已用0）。失败、尝试、恢复成本如实计数；不得依据成败/Q/有无有益候选替换episode或额外重跑。没有自动新增源/候选/优化授权。

## Cut与初态契约

300源每任务30个注册首次报警目标源、30个scheduled；scheduled15/45/95各10个/任务。首报目标不保证实际出现报警，不补换源来凑实际报警数。主目标未到达和无报警时，按已批准LEAD执行训练专用fallback：

- scheduled15→5；45→15→5；95→45→15→5。
- 首次报警组无合法报警时，仅训练使用15→5。
- 只能选择已到达、非终止、剩余控制预算足够的合法cut；没有合法cut时保留缺失及原因，不按标签重采。

原registration的scheduled字段 `fallback=none_pending_analysis_review` 是早期占位，已被LEAD及首轮冻结实际策略取代。**第二轮新配置须显式绑定上述已批准规则，不能将该占位重新解释为禁用fallback或等待审批。** 原registration和旧冻结文件只读；保存原请求字段与解析后的有效策略，留可核对的区别。

初态身份仍取首次动作前真实物理scene fingerprint，排除seed/RNG/time；核对已有scene registry和split身份，严格按预登记的pre-action拒绝链处理重复。开发/校准/保留仍不使用训练fallback；本阶段不采这些split，不提前初始化held。

## 模型与执行冻结

冻结同一B200四成员、预处理和selected seal：`models/round1/round1_fit_v1/selected/complete.json` SHA `931c6f6043db92b5d9003eb2833dfc8edd0ab6c860a1979db3983cd7d893725f`。实际加载身份须核对，不能回退旧critic或复用旧guided动作。本阶段允许新源产生新a0，不施加policy5那种对旧dev a0的跨bank恒等约束。

复用已验证的native10/labels13实现与随机流语义。必须在独立collection入口正确区分本阶段的新capture/13候选能力和上一阶段仅五臂的部署入口。代码改动只放新版本；原采集、P0、训练和policy5冻结只读。

保存新的READY v8、300ID清单、当前模型与场景注册依据、配置/代码依赖快照。归档必要的CPU检查：stage/scope与资源隔离、原注册解析/fallback、B200装载绑定、13候选raw/mask/对称/alias与配对seed接口。已有通过且未变的共同依赖可引用封存证据，不要求重复整套P0或额外真实模拟。

GPU正式工作通过lifecycle，沿已验证8GPU×4worker；每次结束或失败自动恢复holder。运行中只报告技术进度/预算/错误，不按中途收益换源、模型或停止。阶段完成自动通知两端，并提交全部300槽静态审计与分资源账本。

## 后续仍锁定

本次不启动新的PCA、优化、最终训练或其他split仿真。300新槽解析完后，分别保留两个采集critic的来源标记，组成全部600计划训练源的静态输入；缺失与alias处理保持原规则。重新训练前另行审查train-only PCA、初始化、bootstrap/masks和完整dev输入绑定。

最终A/B训练、第二次实际开发策略测评、校准和heldout各阶段另行READY；不能因前阶段节约预算就自动增加模型比较或扩展试验。
