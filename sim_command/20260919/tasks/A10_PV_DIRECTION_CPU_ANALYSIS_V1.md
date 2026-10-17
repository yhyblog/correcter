# A：P/V已有正负诊断的方向与尺度分析（仅 CPU）

task_id=`A10_PV_DIRECTION_CPU_ANALYSIS_V1`；revision=1；owner=A；授权 `releases/P00_PV_DIRECTION_CPU_ANALYSIS_V1.json`。核对后写ACK。仅分析保存数据和窄范围冻结公式，不运行新模型、仿真或算法实验。

## 已验收事实与目的

C10 V2已按有限工程完成验收关闭，见 `manifests/A_CAUSAL_C10_PREFLIGHT_V2_FINAL_ACCEPTANCE.json` 及 `../../docs/CAUSAL_C10_PREFLIGHT_ANALYSIS_20260920.md`。十份旧计算release不复用。本次真实G0=-0.057708，未触发；两支是预先固定的强制工程干预。Post ΔQ=+0.0135891；Velocity ΔQ=-0.1560669，四成员和三次局部J均下降。完整收益触发方法在该cut不会干预，不能将此记作完整方法失败率。

独立分析已确认工程约束，并发现相同锚点保存梯度g与实际delta点积约Post+0.17801071、Velocity-0.06851492。无需重复整套工程验收；本任务将方向/尺度分析固化为可复核CPU证据，区别事实、推断、缺项，为是否需要新开发诊断提供依据。不在此改算法或挑分支。

## 唯二数据来源

1. `results/A/P10_PV_V3_launcher_runs/A10_PV_OFFLINE_PREFLIGHT_V3_r1_A_wave08` 的既有step0离线正例；入口及文件身份见 `manifests/A_PV_OFFLINE_PREFLIGHT_V3_FINAL_ACCEPTANCE.json` 与其runtime manifest。
2. `results/A/P10_CAUSAL_C10_V2_launcher_runs/A10_CAUSAL_C10_PREFLIGHT_V2_r1_A_wave10/{Post,Velocity}` 的cut5正/负例；入口见 `results/A/A10_CAUSAL_C10_PREFLIGHT_V2/EVIDENCE_MANIFEST.json`。

不新增来源，不读取held测试轨迹，不扫描历史大树。两状态不同，不作为受控消融/错误率分母。每个状态只用自身相同context/critic/anchor的P、V作几何比较，先证明身份；不跨状态复用梯度。

## 必须回答的窄问题

- 从保存成员概率重算anchor/final/局部J变化，明确局部clean-after与最终guided/final proposal的评价对象，区分原生raw命令、clamp后命令、内部归一化clean/velocity坐标及单位。日志accepted=true只表示固定更新已执行，不是Q批准。
- 对保存的guided_raw50→clamped方向→mask→单位方向→自身半径→实际delta→最终proposal，用CPU数组运算核对变换关系；报告各阶段与同锚点保存g的点积/cosine、范数/裁剪/饱和比例，判定负方向是否已存在于guided输出或首次出现于后处理。只算已保存数据，不重新调用投影/模型/梯度/采样来补证据；无法识别阶段留null并给原因。
- 与step0比较同一口径；展示S/S²、τ、dt、α的位置及实际冻结源码对应。允许仅定向读flow_update/坐标变换/独立半径相关函数，记录行号/SHA及简短代数，不全仓库加载。不改变函数，不调用网络或自动微分，不做有限差分Q查询。
- 利用已有每τ导数/范数，复核一阶变化尺度、局部前后J、边界和clip统计。把“大有限步长/曲率/flow传播/投影”等列为待证假设；未发现表面符号错误不等于根因已排除，不能因三个局部下降就改符号或α。
- 列出实际缺失逐τ x_t/v/updated_v/clean_before/clean_after和独立中间Q证据，不能从标量反演，也不能将末τ局部after未经dtype/Euler证据确认当成独立最终guided评分。若需要未来日志，先给最小字段/估算存储和新增操作报价；优先复用既有计算中间量。任何额外forward/梯度/重算都单列为未授权，不能为了补日志现在执行。

## 交付与禁止范围

交CPU分析短REPORT/RESULT、逐状态/逐阶段JSON或CSV、数组字段与单位映射、只读分析脚本及输入SHA manifest、假设/缺失证据表和下一步建议。先报告可得结论，再列必要后续观测；没有必要不强行设计新实验或GPU提案。保存已有风险结论，不覆盖旧包、回执、图像或算法文档。

允许标准库/CPU数组读取与算术，不是模型推理预算；禁止Torch import/dlopen/CUDA/EGL/NVML、模型加载或任何网络forward/backward、执行投影实现/重新采样、环境/reset/render/物理、真实launcher/claim、holder查询停算/信号、安装/训练/删除/大权重重hash。禁止扫α/半径/阈值、加Q门/回溯、换seed、补基线、重新做库存/整套测试。本轮不创建真实计算release或claim，B不参与。所有产物保留，完成交分析决定后续，不自动下一阶段。

receipt=`receipts/A/A10_PV_DIRECTION_CPU_ANALYSIS_V1_RESULT.json`；产物=`results/A/A10_PV_DIRECTION_CPU_ANALYSIS_V1`。
