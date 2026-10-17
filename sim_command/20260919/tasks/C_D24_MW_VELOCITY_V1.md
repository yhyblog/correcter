# C独立任务：Smol/X原生Velocity＋MetaWorld

任务ID `C_D24_MW_VELOCITY_V1`，revision1，owner C。用户新增C八卡资源用于既定实验；首次本机身份登记后直接按 `deadline_20260924/C_AUTHORIZATION_V1.json` 执行。A/B不等待C，C不等待它们的新代码或终局。

## 两个正式单元

| 底座 | 已冻结checkpoint | 正常队列 | 新增评测 |
|---|---|---|---|
| SmolVLA | 050000，现有50k底座 | H50 / K10 / NFE10 | Velocity，500个原B测试源 |
| X-VLA | D24 seed42训练030000 | H30 / K10 / NFE10 | Velocity，500个原B测试源 |

两组均用 `work/B/B_D24_E8_POST_V1_r1/POST_SOURCES.json` 的 `D24_MW_tXX_eYY`，**不是A的D24_NEW_TEST源表**。沿各底座原N/Post的env seed、policy seed、相机/renderer配置、30Hz/物理尺度与300步终局协议；N/Post已完成，不重算。Smol N有效496且4未知，比较用双方有效配对子集；未知不填失败。X N有效500。

## 适配范围

1. 复制B已运行Post桥接包到C私有目录，复用其原生底座加载、环境/源表、π0.5外置特征、D/G0/Q与动作变换；精确资产见 `C_ASSET_INDEX_V1.json`。B不需要为C另写输入包。
2. 只新增各自原生flow的Velocity梯度桥。方法数值继承当前Velocity及独立自身半径纯函数，接入实际采样时间/负dt、action padding、物理4维映射、归一化Jacobian及末3步引导。不能假设Smol、X和π0.5内部flow坐标相同。
3. 保持已冻结G0阈值0.05、因果时序、每episode最多一次、纠偏C10、结束后丢弃未执行尾部并恢复该底座正常H。实际native raw chunk长度沿底座，不强制改成π0.5的50；核心物理动作维度仍4。
4. baseline/guided的采样和噪声关系沿本方法定义；冻结参数、动作梯度、未修改尾部等只做必要定向检查。不增Q接受门、回滚/重试选优或新的触发方式。一次计划episode正常后自动续跑，不另开GPU预检。
5. 使用冻结π0.5外部特征/PCA/D/G0/Q时披露历史五任务训练覆盖；不把Smol/X的embedding直接输入原π0.5投影。不得重训底座、重拟合Q或看test结果选引导强度。
6. 如需开发验证，只用既有独立dev源，每底座最多40个dev父源、200次rollout；与本轮test隔离。优先冻结默认科学设置，不做强度扫描。只为实现正确性服务，不增加数据效率/扰动恢复实验。

优先复用B实际使用的renderer与环境配置。无需逐像素/完整状态相等证明，但不能悄悄换协议后把跨协议成功率差归因于Velocity。当前配置在C无法运行时，仅修复C私有环境的明确故障；不能借机重跑N/Post或换测试初态。环境差异若确实无法解决，报告该设置的具体缺项并继续另一设置。

## 资源、幂等与后台

- C独立总上限2400次物理attempt：计划1000条test、最多400条开发，其余仅供明确技术失败的单次修正；同一失败episode最多一次纠正重试，成功episode不重放。模型前失败和进入episode的次数分别记，不为了记录故障重复已终局来源。
- 基础模型SFT更新0、小头训练更新0；动作autograd属于推理，不是模型训练。已有权重只读，不复制整套数据/权重到新树，不恢复475源采集。
- 目标8路有用worker，先完成的可释放给同节点另一已准备模型任务；不跨节点预约，不设A/B/C退出屏障。原生适配问题只暂停受影响的模型。
- 只认C自己的host/boot/PID/GPU UUID；共享代码中的A/B固定身份和通知thread必须替换为C本机绑定，科学source/seed不变。若C实际上是A/B主机，拒绝重复节点准入。
- 每个 `base/source_id/Velocity/repeat0` 持久claim唯一。收到重复消息先查已有进程及claim；断线不重启活进程，通知重投也不启动第二份实验。
- 整波holder全停、整组退出恢复；用已存在guard/lifecycle，普通资源检查一次即可。不要写共享guard、重启A/B守护或终止无关进程。

## 结果

写 `results/C/C_D24_MW_VELOCITY_V1/`，滚动回执 `receipts/C/C_D24_MW_VELOCITY_V1_RESULT_r*.json` 和短报告。逐episode至少有source/env seed/policy seed、底座版本、H/C、真实success/终止/技术错误、interventions、policy_calls/flow/动作梯度、可测时间及缺值原因。无需逐帧存RGB或百万事件账本。

每底座独立完成后立即汇总，并与已完成N/Post按同source配对：有效分母、救回/损害、差值及不确定性。跨host时间不能直接当算法延迟优势；设备/renderer和并发条件单列。没有正确flow桥则如实写未完成，不能拿Post结果填Velocity。

后台自动接续与固定原会话终局事件按C启动入口。稳定交接后结束LLM等待，最终输出两组表即可；不等待分析逐格确认。内部截止沿9月23日20:00/23:00北京时间。
