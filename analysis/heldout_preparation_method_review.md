# Held准备：方法与统计契约窄审

结论：准备层面通过，无需修改科学规则。当前被审产物仍为pending selection，不能视为实际selection或held freeze通过，也不授权held运行。

## 已核实

- held配置与原main registration v2的完整manifest、替补映射逐项一致：100主槽、每任务20，200个有序替补；每主槽固定两名，仅允许首次动作前初始化失败或重复初态替补。
- 原native10、首次合法报警、无训练fallback、总控制预算300保持。4个配对后缀、五个物理臂，完整分母为100源/每臂400个逻辑结局；无报警保留真实共同结局，技术缺失拒绝统计，不能填0。
- Post−replan为唯一主比较，另六项次要。先源内平均4后缀，再任务内整源bootstrap 10000次，seed2026091622，预定源/任务顺序、linear percentile95。不能把400后缀当独立初态，也不混入校准数据。
- A4000四成员、raw命令、G0、随机流、alpha/times、mask和半径与cal配置一致。完整velocity/direct/post/reverse/random五方向都参与共同幅度约束；reverse/random只保存依赖输出，不增加物理实验臂。held后禁止选赢家或增加Q/任务门。
- 2200sim/0opt包含最多100capture+100bank+2000branch；替补使用已有共享1200技术储备，全局50000硬上限不变，失败和重试计账。
- 800条历史scene前缀SHA闭合；它提供未来查重依据，尚不证明held物理初态唯一。实际首次动作前仍须对历史前缀和本批已接纳初态查重。
- 已封存75项整合与17项统计CPU证据及11文件SHA闭合；本审查未重跑测试。静态统计逻辑与上述完整分母、缺失处理、源级抽样、主次比较一致。

## 实际运行前仍需完成

当前pending明确不能执行，guard要求真实selection的path、complete SHA、result SHA。须以已独立验证的实际selection生成新的held pending，再单独绑定READY并freeze。本审查不证明后续生成物已通过，也未初始化held或读取真实held结局。

完整波次后仍需审计真实分支、配对随机流、加载模型、物理初态隔离及预算，之后才能形成held结论。点估计达到+5pp和CI支持正收益分开报告，均不能写成已证明真实增益至少5pp。

机器可读证据：`analysis/heldout_preparation_method_review.json`，SHA `8baa14d0beea590d918aa3103f4d1f8b432a19263ded13d7e17568168ca57829`。

本次模型、环境初始化、仿真、优化、测试重跑均为0。
