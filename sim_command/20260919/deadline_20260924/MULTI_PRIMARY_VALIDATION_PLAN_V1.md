# 多次收益触发升为主线：验证接续清单 V1

用户2026-09-22明确将不限总次数的收益触发设为主方法，并要求重做受部署次数影响的验证。此次是查看once/multi结果后的明确方法版本修订，不将multi伪称为原最初预定设置。旧once、旧失败和全部权重/原始结果保留。

## 新主方法定义

主方法现在为G0-multi：保留每5步因果检查、原收益阈值、合法cut、历史成熟、C10承诺锁、丢尾和恢复native队列，仅取消episode总干预次数帽。不是任意每步重复采样，也不取消C10期间禁止重入。π0.5仍raw50/NFE10，H10/20/30/40/50；Smol/X保持native K10、各自raw50/30和原动作坐标。原source/env/policy/candidate随机流与模型不因次数变化重新选择，无Q接受门。

旧Q/G0监督是一次局部替换后的native continuation，π0.5旧G0另有execute5标签/C10部署差异。多次版重复应用局部收益启发式；不将这些头称为已校准的multi最终价值函数或全局最优控制器。Smol/X新头C10标签也仍以native suffix为后续。取消帽本身不要求重新采集/重训现有头。

## 完成与未完成清单

| 实验 | 已完成/可复用 | 此次还要做 | 执行端/新首次评测 |
|---|---|---|---|
| E4/E9 MT50主结果+H扫描 | N五H2500、G0-multi三分支五H7500均已完成 | 直接升为主表，旧once作为次数消融 | A做CPU表图；0 |
| E1损失消融 | 原48个小网/12ensemble已训练；once1200保留 | 相同loss/fit/source只改multi，24格各50 | A；1200 |
| E6收益与异常触发 | 原100dev/阈值/50test已完成 | G0→R、D5→R都改multi，各50 | A；100 |
| 随机触发机制对照 | 旧Random-once7500保留为once补充 | 新Random-multi五H×R/P/V×500，覆盖原H扫描 | A；7500 |
| E3外部方法对比 | VLA-Corrector/GAF原生机制各500已完成 | 对H10主线R343/P355/V346重新配对、作图 | A CPU；0 |
| E5成本/参数 | 新multi原日志及11.91M小网参数已有 | 主成本表换multi，分别列每episode与成功摊销调用 | A CPU；0 |
| E8 Smol专属适配 | 250父源采集已完成，8小网共32000更新完成；原once正在评测 | 原链完整收尾后，用同一选定头跑R/P/V multi各500 | B；1500 |
| E8 X专属适配 | 同上，原once正在评测 | 原链完整收尾后，用同一选定头跑R/P/V multi各500 | C；1500 |
| E8完整LIBERO | 算子版完成，Full监督有科学缺口 | Full仍未完成；不能把定时算子改名为Full-multi | 无新增盲目GPU运行 |
| 用户真实场景 | 用户自己实施 | 以新multi主方法记录触发、调用和结果 | 用户负责 |

新增首次评测共11800：A8800+B1500+C1500；**不是重跑已完成multi主表**。现有B/C单次链继续完成，不在同一格中混入multi，也不重采/重训头/N。完整LIBERO仍为待解决的科学缺口，不随其他表升格为已完成。

## A：8卡独立队列，总8800新评测

任务A_D24_MULTI_PRIMARY_VALIDATION_V1。顺序E6 100→E1 1200→Random-multi H10三分支1500→H30/50/20/40每H三分支；各阶段自动接续，不等待B/C。已完成阶段立即发布小表。A当前上一wave已完整退出，可直接私有准备后启动，不需新GPU预检。

### E6：100新评测

读取results/A/A_D24_CORE_REMAINDER_V1/config/E6_SOURCES.json，**只用其中原50 test**（五任务ordinal10..19），不是主500源。dev100、phases/THRESHOLD.json以及DEVELOPMENT_TRACES/MANIFEST全部复用，D5阈值0.2521600950570383不重新调；G0严格>.05。两臂都仅去总次数帽，保留D5误差定义/监测/cut/C10和R本体。原dev95/100是episode有无报警匹配，不能称multi实际次数已匹配。结果报告success/valid、成对救回损害、真实次数和调用，保留旧once52%/60%。

### E1：1200新评测，零重新拟合

完整ensemble索引results/B/B_D24_SPRINT_V1/r1/E1_ENSEMBLES.json；L00/L01/L10/L11×fitseed9101/9102/9103×Post/Velocity×50=1200。48个权重均为原固定终步检查点，不据已揭晓测试重新选loss/seed。源必须用work/B/B_D24_E1_EVAL_V1_r1/TEST_SOURCES.json的完整50，BASE.json同目录；**不能直接抄旧repair r3只含剩余40源的单元配置**。

私有复用work/B/B_D24_E1_REPAIR_V1_r1/已修复运行组件及renderer_cleanup。E1实际环境是Mesa/30Hz/400Hz/.015，不是Smol/X的80Hz/.01；保持旧E1协议以使次数成为此次改变。首个已计划episode确认合法图像/单位即可，不另开GPU探针或像素/MJB证明。不要无说明换成A主表NVIDIA后把全部差异归因于次数。

原底座常驻，按unit切换轻量Q ensemble，D/G0沿原E1冻结头。每次合法干预用当前loss的Q，C10结束恢复nativeH10；多次上下文及完整cut序列正确更新，first_cut只写第一次。若需将candidate seed扩展到第二次之后，沿已验证multi键source/policy_seed/absolute_cut，不加入loss/branch或临时counter扰动共同随机流。按原50源逐fit配对，三fit统计不能混为150独立初态。

### Random-multi：五H各三臂500=7500

这是与新multi主线匹配的无信息触发策略。每个**真实当前合法监测点**独立Bernoulli(p=.5)，无episode总次数帽；p在运行前固定，不用test报警次数校准。coin只替换G0>.05判断，其余合法性、每5步频率、历史成熟、C10期间不重入、终局预算均不变；D/G0可复用原shadow调用保存诊断但不决定是否介入，不额外计算相同forward。

固定抽签：UTF-8字符串 `corrector_random_multi_v1|2026092203|{source_id}|H={H}|cut={absolute_control_step}` 的SHA256取前8字节按无符号big-endian整数u；u<2**63则触发。三分支在相同source/H/t共用抽签，不依赖branch、成功结局、未来观测、实际G0触发数，不消耗策略Torch RNG。每合法t最多一次coin；未成熟/不合法/C10锁内不干预。早终止不强制动作、不替换源。

原500主源用deadline_20260924/TRIGGER_MODE_SOURCES_V1.json（ordinal0..9；不是原1000含备用源的全集）。执行H10→H30/50→H20/40；每H先R再Post再Velocity。R、Post、Velocity的原科学函数和动作坐标保持，Velocity a0/guided同噪声且完整引导采样计调用。300步和C10锁自然限制可发生次数，不人为加新总帽。

Random-once旧方案是预抽一个绝对时刻，本次Random-multi是每合法机会固定coin，两者随机协议不同；**不要将Random-multi减Random-once解释成纯取消帽的因果效果**。主对照是同H/同分支Random-multi与已完成G0-multi，并报告真实次数及全部调用；也不称实际次数严格相等。本轮完整15个比较单独做精确McNemar+Holm，区间仍pointwise固定task内源bootstrap2000seed20260921。不会按结果再调p或追加另一个随机强度。

### A的CPU汇总

复用已有外部500源结果，更新与H10 G0-multi R/P/V的配对。外部方法保留其原生连续/多次机制，不为了我们改main而重训或重测外部方法。原训练数据差异/GAF-adapted/8条VLA-C日志恢复成本缺失继续披露。

E5主表按multi同500有效源统计：完整策略采样/flow、观测编码、D/G0/Q/动作梯度、干预次数、实际时间。每有效episode平均与全部有效调用/成功数分列；技术故障与纠正的物理开销另列，不能混入某方法又不计其他方法。Velocity第二次guided采样必须计入。Post H10 mean13.780、H50 7.384等已有值可直接复用，参数量不因次数变化而增大。

共享EXPERIMENT_RESULTS_MASTER.md仅分析端写；A发小型MASTER_UPDATE.md/CSV+事件后分析端自动并表，不能因等待表格验收暂停科学队列。

## B/C：原专属once结束后，各1500 multi

B_D24_SMOL_MULTI_EVAL_V1与C_D24_XVLA_MULTI_EVAL_V1。先读各自原专属AUX_RETRAIN任务终局；不从正在写的未完成权重选择。使用FIT_SUMMARY中8个固定final权重、同train-only norm/PCA、同500 test源与native环境，**只取消总次数帽**。D5/G0>.05/C10/nativeK10/内部动作Jacobian等不变，R/P/V各500。旧once继续保留，可作为同一专属模型的次数消融；原冻结π0.5头迁移表另列。不复制主π0.5特征之外的随意输入、重新调门限、增加新的训练步骤或重复N。

两端已真实采集、训练完成；保持旧评测整条链收尾后再开独立multi run/claim，确保同一cell协议不混合。CPU准备可并行于现有GPU链；A/B/C互不等待。

## 预算、后台与截止

A本次最多9500attempt（8800首次+700仅技术纠正），累计cap由18000升至25000；B/C各1650attempt（1500首次+150纠正），B累计20000不变，C由11900升至14000。旧所有消耗/claim不重置。新训练更新0、额外开发采集0、底座SFT0。失败源最多一次明确修正；成功/已有合法终局禁止重跑。原source失败能可靠日志恢复则优先CPU恢复，不造费用。

目标8卡有用worker，整波holder全停到正式族退出。启动器/元数据读取容忍有界瞬时共享文件I/O异常，不能绕过真实撤销/stop；原始episode先落盘，非科学报表错误保留publication_pending而不杀健康worker。CPU定向检查原实际controller/recorder/serializer，不再全套测试和大模型SHA重算。

各自有界后台自动运行；首次8模型ready+真实进展写STABLE_HANDOFF后结束LLM等待，事件唤醒原线程收尾。重启通知不等于重启科学。单任务最长12小时或总截止更早者；9月23日20:00北京时间停止新科学准入，23:00交最终表图。无法完成如实空表，不用once结果填multi，不盲目补LIBERO数据或更换目标。
