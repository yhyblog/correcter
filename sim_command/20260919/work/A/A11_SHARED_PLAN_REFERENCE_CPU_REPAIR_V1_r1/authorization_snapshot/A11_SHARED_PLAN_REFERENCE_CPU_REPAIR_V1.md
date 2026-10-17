# A11：共享BANK计划引用的定向CPU修复

task_id=`A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1`；revision=1；owner=A。
release=`releases/P00_A_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1.json`。核对当前CONTROL/TASK_BOARD/host及release SHA后新ACK。旧任务交付已审阅，不重投或重新执行未授权V2。

先读 `manifests/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1_REVIEW.json` 与 `contracts/A11_SHARED_PLAN_REFERENCE_DECISIONS_V1.md`。本次只修两处已知producer问题，保留其余已验收修订与immutable包，不增加纯设计轮次。

1. 实际load_bank + public_records.publish_transition组合：generated_chunk_ref接受本branch自产或已核验同parent/cut/source BANK白名单；obs/next仍严格本物理branch。白名单绑定BANK引用/内容身份及精确plan_key映射、format/raw50 SHA/shape/dtype，不能仅因路径在normal或hash相同就接受。用已有真实加载/发布函数配小型synthetic bank文件，先复现旧版合法共享被拒绝，再检验新路径。
2. 定向覆盖Q a0/plus/minus、G0 fresh0/1/2、G0_old和本branch native suffix。拒绝错parent/cut/source/BANK SHA/plan_key/内容、任意外路径、跨branch观测；不构造真实环境、不生成真实模型计划。别为复制BANK扩writer预算。
3. intervened改按实际介入证据，cut前结束必须false；在已有precut fixture补断言，并检查完成路径/normal/未到介入失败。不将强制采集或G0_old写成真实收益触发。允许修必要的控制器记录，但不得改执行顺序/计划/噪声/结局。
4. 原supplement_v1不可改。发布独立supplement_v2或绑定旧READY的后继解释，明确共享chunk例外，保留其他私有成本/aggregate语义。交新READY路径/SHA供B现有CPU任务消费；不向B会话直接发命令，也不修改B包/共享dispatch。
5. 新未授权未来提案 `A11_COMMON_POOL_FIRST_PARENT_V3` / `P11_A_COMMON_POOL_FIRST_PARENT_V3`，保持原未执行源/seed和116caps/timeout/bounded_first_parent合同，分离新run/output/cache/claim。BOARD/CONTROL/checker同源，模板UNAUTHORIZED_TEMPLATE，真实路径不创建。新增CPU引用核验如有成本差异另列，不新增模型/仿真额度。

交独立REPORT/CPU_READY/RESULT、最小DIFF、定向检查、新补充READY、新未授权提案及必要身份manifest。只测试本轮改动及真实函数组合；不重跑104或133旧套、不重新盘点、不复制重hash大权重、不重做已通过的资源准入审查。继承部分引用旧manifest，新增证据保留。

本轮真实模型/特征/训练/环境/采样/投影/GPU/CUDA/EGL/NVML/dlopen/holder/launcher/claim/安装/删除均0。允许标准库/NumPy小型显式synthetic CPU检查、隔离代码配置修改和必要窄读取。完成等分析验收，不自动采集；不借用旧十份计算release。
