# A11：闭合共同池候选、配对资格与预算（CPU 修订 v2）

task_id=`A11_COMMON_POOL_REVISION_CPU_V2`；revision=1；owner=A；授权 `releases/P00_COMMON_POOL_REVISION_CPU_V2.json`。先核对当前CONTROL/TASK_BOARD及本release再ACK，不重投V1。

V1设计交付已验收为草案，不能直接采集。先读 `manifests/COMMON_POOL_DESIGN_CPU_V1_REVIEW.json` 与 `contracts/COMMON_POOL_PROTOCOL_DECISIONS_V2.md`，后者是本轮分析决定。保留旧V1包，另建本任务独立目录。

## 必须修改与交付

1. Q改为a0＋local_plus/local_minus，各2suffix；用已文档化3高斯时间节点平滑随机方向及现有自身对称可行约束，不依赖旧Q、不新加guided族/扫参。给出一条source的逻辑候选、正反pair、raw-C10别名、实际物理执行与标签掩码的可读例子，解释零方向/缺repeat时为何不会伪造Full的pair数据。只设计/检查表格，不运行真实候选生成器。
2. G0固定3独立fresh各2suffix与old2suffix，fresh0共享Q的a0生成但不共享C5/C10终局。完整源级标签公式与valid_pair_repeat_ids、缺失mask、normal有条件引用Gold repeat0规则写清。300目标为parent绝对s300含末步；不再留成未定义。源级损失不改，训练初始化/具体优化不在本任务冻结。
3. 恢复/配对准入选full_state_verified，observables-only不入gain/pair/G0。通过已冻结小manifest与必要窄source/API静态阅读，列物理/任务/model可变字段/RNG/wrapper时钟/队列history的具体版本字段、序列化及核验顺序、可证明/待证分类、逐位或容差草案。CPU不能证明真实roundtrip，禁止填“已通过”；若某字段无法定静态规则，明确阻塞和首个已计划采集parent中必要核验，不扩大成50组独立实验。
4. 修正LVM独立资格分流、任务×split×cut分层owner、联合compute-exited全局屏障和独立数据发布屏障。可用draft/synthetic ID作轻量CPU交叉表，确认500源8/2、train各主机各cut均衡、dev跨50任务均衡且parent不拆；不得产生真实seed/shard/claim或改B冻结包。
5. 重发五项主交付及最小DIFF/DECISIONS_ALIGNMENT、输入manifest和短REPORT/RESULT。资源报价按3视觉/sample＋1语言修正，逐项分计预处理/实际图像/显式特征。列7500无复用与7000有条件normal复用两种上界算式、候选生成仅3fresh/cut、控制与flow/编码/初始化/暂存/输出；不得把旧4500报价留作新预算。新增局部候选不需Q/梯度，但CPU动作生成和序列化成本需如实说明。

500父源仅固定为首个覆盖批次设计，不保证有500合法源或能训练充分；没有真实采集配额。各任务初始化cap仅有shelf参考，其余49逐项列已知静态依据/未知，不把shelf数字复制为已证上限。用最低必要的源码阅读，不重新全库盘点。

存储按新规模重算；可用现存34帧PNG等已保存数据的尺寸估计无损编码规划范围，硬上界不能用未经证明的压缩率扣减。不要为报价重复编码大批图像。可定向只读查现有项目quota/空间小元数据，若无法取得保持unknown并明确后续放行依赖；不扫大树、不删除。持续加载/记录动作回放/共享缓存仅作为独立可验证优化报价，不先实现或宣称已节省。

有限collector下一阶段验收建议随新候选结构更新，强调只检查必要字段/身份/恢复与早停，完整终局在首个已计划完整parent验收；先CPU规则检查、后另发有限实施/计算任务。不需要当前创建真实sh、GPU模板或训练脚本。

## 范围

允许保存文件/报告/合同与必要窄source/API静态阅读、CPU文档/JSON/表格/身份及参数算术检查、定向只读文件系统quota元数据。禁止Torch import/dlopen/CUDA/EGL/NVML、模型/特征/token提取/梯度、实际投影/候选器运行、环境/reset/物理/恢复/render、真实launcher/claim、holder查询停算、安装重启、训练/删除、大权重重hash、历史held加载或新GPU proposal/release。旧公开interface_v1、所有旧回执/包、CONTROL/BOARD、B资产不改。

本任务产物全部保留，交 `receipts/A/A11_COMMON_POOL_REVISION_CPU_V2_RESULT.json` 和 `results/A/A11_COMMON_POOL_REVISION_CPU_V2`。完成只交分析验收，不自动collector实现、采集、训练或诊断重放。
