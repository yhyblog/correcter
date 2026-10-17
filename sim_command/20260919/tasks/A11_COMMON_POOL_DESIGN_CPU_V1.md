# A11：共同训练池设计与资源报价（仅 CPU）

task_id=`A11_COMMON_POOL_DESIGN_CPU_V1`；revision=1；owner=A；授权 `releases/P00_COMMON_POOL_DESIGN_CPU_V1.json`。先核对当前CONTROL/TASK_BOARD与release再ACK。此为A11采集之前的独立设计任务，A11/B11实际采集仍planned且未获计算权限。

先读 `contracts/COMMON_POOL_CPU_DESIGN_SCOPE_V1.md`。当前P/V方向CPU分析已验收归档，十份旧计算release关闭；不再重投旧任务/重跑预检，不为补Velocity日志单独重放。只在既有资产表、输入manifest和B10已发布方法/字段合同基础上设计；不重复A00全盘点，不扫描历史大树或重hash大权重。

## 五项最小交付

1. `POOL_COVERAGE_AND_GAPS.json`：按50个实际环境逐项列正常示范、现有轨迹/标签/RGB/next/terminated/truncated可用性与来源证据。复用A00/A10已有小清单；49语言index不是50任务替代。未知填unknown，不实例化环境核查。封存train600与1300历史索引单列，缺字段不伪造，不补采旧600。
2. `COMMON_POOL_DRAFT.json`＋字段/视图矩阵：H10主原始池、parent级train/dev草案和数量待定项；D/G0/Q、VLA-Corrector与GAF-v1所需字段/标签窗口/特征与正常样本筛选、历史初始化差异。引用B的已冻结METHODS/视图要求，不等B新GPU回执即可写草案；未确认实现能力单列。公共interface_v1保持不变，容纳不了的字段用明确外部引用/扩展提案，不覆盖v1。
3. `COLLECTION_AND_REPLAY_PROTOCOL.md`：全MT50覆盖与无标签依赖的源/cut规则、候选族建议（说明各自必要性与计算成本）、normal/a0和重复/alias语义、真实后缀终局/截尾/技术失败、G0五步与Q十步目标区别。恢复方案可选完整snapshot或记录前缀独立回放，列必须核验的状态/RNG/队列字段、已有证据与缺口；回放reset/前缀/特征/采样都收费，不按免费restore算。CPU只制定验收条件，不执行恢复探针；也不先宣称隐藏状态相同。
4. `COLLECTION_SHARDS_DRAFT.json`：source/parent/branch/repeat ID规则、互斥A/B归属、唯一任务与输出路径规则、幂等发布/失败恢复边界和显式完成屏障草案。具体数量/seed未定则保留未定，不假扮已冻结实采manifest；已完成单元不得重跑，未完成不换seed凑成功。
5. `RESOURCE_AND_STORAGE_QUOTE.json`＋短REPORT/RESULT：给可审查的参数化成本表及一套推荐的数量草案，明确“报价非授权”。拆环境初始化/隐式reset、每源生成、每cut候选、每次恢复或前缀回放、物理步、完整VLA/flow/encoder/token/Q/D/G0、特征提取和异常退出费用；不能用标签数替物理attempt。区分直接复用已验收入口与尚待实现/验证；给最小必要collector验证范围报价，而非先跑。RGB/token/轨迹/缓存峰值分别估计，不假设压缩节省或共享池空闲量等于项目quota。可定向只读查必要文件系统配额/空间小元数据，不全树盘点、不删除。

H10采集基准、MT50任务等额计划、parent split和标签窗口已由分析确定；每任务train/dev数量、cut/candidate/repeat组成、组件训练方案/预算由分析看本报价后冻结，不能默认照搬历史13×4。建议先给最小充分方案与成本影响，避免扩出新的论文主张/实验矩阵。E8和真实环境不纳入本任务新池。

## 允许与禁止

允许CPU读取小manifest/报告/合同与必要窄接口、编写上述设计/表格和身份草案、轻量JSON字段/引用检查。此阶段不要求实现新collector、训练器或观测logger，不为CPU方案搭建大量测试；设计若暴露接口缺口，在报告中定向说明。

禁止Torch import/dlopen/CUDA/EGL/NVML、模型/特征/token提取/前反向、环境实例/reset/模拟/恢复/render、真实launcher/claim、holder查询停算/信号、安装重启、训练、删除、大权重重hash、历史held数据加载。不得创建真实采集/计算release或自动进入A11；A/B生产字段或共享环境不改。未来Velocity日志只列可选观测需求，不实现/不采集/不附加独立Q调用。

输入优先：MASTER_PLAN、contracts/DATA_LOG_CONTRACT_V1、INVENTORY_DECISIONS_V1、manifests/HISTORICAL_DATA_ACCESS_V1、PUBLIC_INTERFACE_V1、receipts/A/A00_ASSETS及B10冻结回执/方法。原始数据需要更广检查时先列精确需求，不无目的遍历。所有本轮产物保留。

receipt=`receipts/A/A11_COMMON_POOL_DESIGN_CPU_V1_RESULT.json`；package=`results/A/A11_COMMON_POOL_DESIGN_CPU_V1`。交付后由分析冻结协议与有限实施任务，不自动采集或训练。
