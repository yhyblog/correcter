# 第二轮静态审计与最终600计划源输入约定

2026-09-16。分析端对 `NATIVE10_ROUND2_DATASET_COMPATIBILITY_REVIEW.md` 的处理决定。适用范围为独立的CPU审计、数据聚合和最终训练入口准备；当前round2采集继续使用原READY v8及round2_v1冻结。

## 1. 可立即并行准备的工作

执行端可实现独立round2静态审计wrapper、联合输入manifest与验证器、最终prepare接口，并进行必要的合成CPU检查。所有变更放新模块/版本。round2全300计划槽处置完、波次结束且静态证据可封存后，可直接运行只读数据审计并创建新的审计/数据版本，无需再等待单独许可。

当前不执行真实PCA拟合、模型初始化、optimizer更新或后续split仿真。最终零更新模型预检及正式训练将分别绑定完成的数据seal后放行。

## 2. 第二轮300源独立审计

在round2自己的封存config、bank `round2_labels_v1` 和真实protocol下审计train round=2。必须覆盖全部300原计划槽及actual episode/替补链，不从先完成的源构建正式输入。已完成no-cut源保留coverage与自然结局；技术缺失、未解析槽或备用链耗尽不能当作“完整可训练输入”。

保存所需readiness来源通过显式 `analysis_sources` 补齐：引用round1_v1冻结的 `coordination/NATIVE10_TRAINING_READINESS_REVIEW.md`，SHA `cd59280a23803bee7fbe25d969b20c5f0a4960ec0e3708e4a45cbf1b0b6ea587`；保留round2已冻结的LEAD、RAW_BUDGET、EVAL20及其实际SHA。补充来源用于文档溯源，不重标round2协议，不用旧readiness充当最终训练授权。验证封存文件字节并记录原冻结出处。

另核波次退出、32个实际B200装载身份、全部slot resolution和完整分资源账本；失败、拒绝、重试及未被有效样本引用的尝试也必须计数。阶段17400与共享technical_reserve1200的使用不能只依据样本内引用来推算。

## 3. 建立独立联合输入身份

创建新版本的aggregate input manifest，生成独立 `input_bundle_sha256`。至少绑定：

- round1 train pack/audit及round1 collection config/freeze/真实protocol；
- round2 train pack/audit及round2 collection config/freeze/真实protocol；
- 原development100 pack/audit及其真实round1来源；
- 两轮各自生成critic四成员身份及其原模型/预处理来源；
- 共同canonical特征定义、特征提取器、ActionTransform、动作单位/顺序/映射规则；
- 600个原planned_slot_id的注册顺序、actual episode/完整回合映射、split/scene/replacement证据；
- 聚合schema、实现SHA和新静态数据seal。

联合manifest明确区分train round1、train round2及development来源。每行保留真实bank、bank_protocol_sha256、generation round/critic、source/bank seal和原物理attempt身份。子包的 `input_protocol_sha256` 保持原值；新入口应验证明确允许的两协议及各子包，而非将旧audit字段改成同一伪造协议来通过单协议断言。

原round1/round2配置、数据包、audit及冻结文件均只读。联合输入是新的派生产物，不覆盖其中任一版本。当前仅登记好的calibration/heldout身份不进入任何训练、开发输入或初始化操作。

## 4. 特征和标签的可比性

训练合并原canonical视觉history4096、语言2048、本体历史、过去动作、mask和剩余预算等已定义特征；先核特征提取器、维度、顺序、单位和归一化定义一致。两代critic的PCA坐标、预测Q或梯度可用于来源诊断，不能充当相同坐标系的canonical训练特征。

保留raw动作、C(raw)、实际delta、a0及13候选顺序，核共同ActionTransform身份。normal仍是独立控制臂，不改作动作critic的a0。四后缀、别名与正反对始终归同一完整源；保留首轮既定的loss去重/项内平均，再按有效source均权。不能按轮次、teacher、Q、收益或候选数量新增采样权重。

两轮采集critic不同属于本次计划的数据来源差异，并不要求生成方向或PCA相同；共同输入与执行语义若不一致，应报告真实差异，不能改名消除。

## 5. 计划数、有效数与最终训练准备

600是计划槽数，不保证600个合法critic行。全部计划槽必须有完整处置；合法no-cut不伪造输入、补零标签或补采有利源。汇总各任务/轮次的计划、实际初态、有效cut和缺失原因。技术不完整项需在完整输入声明前解决或提交明确处置。

最终A按已批准方案从原旧四成员重新warm start，沿用旧投影；B在两轮全部唯一有效train源上重新拟合共享视觉16/语言8 PCA，然后初始化匹配的小网络。PCA在bootstrap之前按每个有效源一次拟合，dev和候选/后缀重复不参与加权。保留原近零主成分floor及初态、概率、动作梯度、singleton/导出重载检查。

四成员仍按任务对完整有效训练episode做source bootstrap。若存在合法no-cut，按各任务实际有效源数有放回抽取同等数量，总数为有效源数；保留计划覆盖表，不为凑600条bootstrap源伪造样本或过采某轮。最终预检须明确有效源数、各任务抽样数、种子和实际bootstrap清单。

损失权重1/1/0.5、A/B学习率/可训练范围、最终每成员最多4000更新及固定检查点/选择规则沿既定ADDENDUM。现阶段只准备接口，不调用真实初始化、PCA或优化。最终预检与训练必须通过新的跨协议输入验证入口；现有仅支持单一collection协议的入口不可直接使用。

## 6. 开发集与后续交接

原dev100独立保留，95个cut与5个共同结局仍按100计划分母执行固定选择；不混入train/PCA/bootstrap，不重标成round2数据。当前采集结束后，提交round2静态审计、联合manifest/新seal、完整预算和兼容性说明，供分析端放行最终零更新预检。后续训练和实际测评依各阶段READY推进。
