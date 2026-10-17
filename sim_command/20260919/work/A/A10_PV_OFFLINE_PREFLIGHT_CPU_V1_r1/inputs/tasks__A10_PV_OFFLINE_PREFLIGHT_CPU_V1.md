# A：单保存初态的 Post/Velocity 离线数值预检准备

task_id=`A10_PV_OFFLINE_PREFLIGHT_CPU_V1`；revision=1；owner=A。仅CPU准备，授权见 `releases/P00_PV_OFFLINE_PREFLIGHT_CPU_V1.json`；不运行模型、GPU、环境或训练。

## 起点与目标

native V3已完成并由分析端验收，见 `manifests/A_NATIVE_PREFLIGHT_V3_FINAL_ACCEPTANCE.json`。其release已关闭，所有未用额度作废。原生加载、两帧观测、5H同噪声计划/队列和一条transition已验证；D/G0/Q、P/V数值、C10真实执行与完整任务效果尚未验证。

本任务准备**单个保存初态上的离线P/V数值内核诊断**，不新增论文实验矩阵，也不等待B。新CPU_READY和有限计算提案交分析端后，实际运行仍须独立release。

## 可复用输入与因果边界

- 已验收诊断目录：`results/A/P10_diagnostic_runs/ba0faa37ed325af8c2c61221310c8bb23f47fd10a109ff5a3d4847866d4f1f2a/`。定向冻结 `observation_step0.npz`、`raw_plans.npy[0]`、指令、源/seed、normalizer、noise SHA及相关模型身份；以V3完整清单为依据，不重新盘点。
- 五份raw50均在step0生成。**step1是未来观测，不得为step0锚点提供历史、特征或标签**；它只保留为既有transition证据。
- step0只有一帧真实观测、没有已执行动作。确认既有训练/推理合同是否支持单帧有效历史及合法mask/零填充；若不支持，报告具体缺口并另报价，不伪造历史、不拼接train600其他cut、不自动采到cut5。t0不是合法报警cut，本诊断不验证触发器。
- 定向绑定已保留的五任务A4000四成员Q、各自PCA/mean/std和所需encoder/normalizer，交确切路径/SHA/维度合同。4096视觉、2048语言等特征须从同一保存RGB/指令按冻结路径真实计算，缺失不能借用其他状态。只列Q条件所必需的特征链；如依赖D前向或其他模型，明确因果输入和额外报价，不自行省略或伪造。历史五任务权重不代表MT50适配完成。
- 核对保存raw动作是否足以按既有坐标变换还原诊断所需锚点及mask/raw语义；若不可逆或缺少内部字段，明确缺口。V3只保存噪声SHA，CPU阶段静态核查冻结RNG、shape/dtype/seed是否足以重建；未来实际使用前核对SHA，不一致立即停止，不自动补采基线。

## 未来有限计算的目标报价（本任务不执行）

优先复用保存a0：Post仅做一次动作梯度和自身投影；Velocity以同一保存a0作为诊断锚点，另做一次guided sampling/10flow，末三步各一次动作梯度。合计目标为4次动作梯度，VLA参数反向0。Q四成员前向、锚点评分、最终约束检查、encoder及必要条件模型调用、模型载入次数由A按实际入口逐项报价，不预先猜数。

环境实例/reset/graphics/物理步/完整rollout/训练/重试/删除全部0，无新渲染。若现有入口不能精确复用a0/噪声/条件，提交理由和最小替代报价，由分析端决定；不得为凑目标填假数据或暗增无引导采样。

这是**缓存输入的数值诊断**，不是完整独立部署运行或成本比较。正式部署口径仍为Post一次完整采样、Velocity两次完整采样；本诊断不能宣称Post零采样或Velocity一次采样的部署优势。

## 必须核对的算法语义

以 `Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md` 2026-09-19的独立算法为准，不回退旧共同半径版本。

- 四成员各自sigmoid后平均，锚点固定；J(b;b)=0，模型参数冻结而动作梯度可计算。固定基线相减不改变动作梯度。
- Post采用一次S²∇aJ，无flow重跑、无Q接受门。
- Velocity只在τ=.3/.2/.1使用v−10τg和负Euler步长，速度/Jacobian停止梯度；使用冻结的同初始噪声，不能换成direct更新或全VLA反向。
- 每分支只依赖自身方向/容量及独立半径，不调用另一分支、random或旧共同bank来决定尺度。XYZ/夹爪各自处理零组；RMS坐标数30/10、mask、边界与扰动上限按原合同。保留既有自身归一化可放大的规则，不新加“只能缩小”。
- 仅修复前C10；零扰动、mask外及尾40步保留raw位模式。记录梯度是否有限、方向、各τ局部量、组范数/容量/半径及raw一致性；不要求Q必升，不按Q结果重试或换seed。

针对实际改动只做CPU静态/fake检查；不要重新跑旧全套。若出现合同不明，交具体字段与缺口，不自行变更算法。

## 交付与运行约束

先写本任务ACK。最终交 `receipts/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1_REPORT.md` / `A10_PV_OFFLINE_PREFLIGHT_CPU_V1_RESULT.json`、独立不可变代码/config/input manifest、CPU_READY、PROPOSAL、RELEASE_TEMPLATE、CONTROL_REQUIRED及唯一真实命令。建议未来实际任务名 `A10_PV_OFFLINE_PREFLIGHT_V1`，模板为未授权。

明确全部操作上限、输入缓存沿革、GPU/CPU放置、显存/RAM/磁盘估算、子进程timeout及外围耗时、失败/部分进入账本。保留唯一claim、A-only全8卡holder直到进程组退出后恢复及无自动重试；原生EGL成功不意味着本次需要初始化EGL。

本CPU准备不导入Torch或GPU库、不调用dlopen/CUDA/EGL/NVML，不执行encoder/policy/Q/D任何前向反向，不加载模型或实例化环境，不查询/停止holder，不重复hash大底座，不删除。可以读取小checkpoint元数据或用不执行模型的方式定向检查维度，并复用既有权重SHA；新正式入口再完整核验输入。

完整公共训练池、MT50 D/G0/Q适配、D/G0真实因果触发链和C10闭环效果仍待后续任务；旧1300轨迹索引缺观测字段的问题未因V3两帧而解决。全部新产物保留。
