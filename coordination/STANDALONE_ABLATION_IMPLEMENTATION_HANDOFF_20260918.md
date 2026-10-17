# Standalone消融：隔离实现与CPU交接

2026-09-18T16:00:34.649344+00:00。已完成隔离工程准备；尚未调用真实VLA/critic/环境，未生成运行freeze或任何新增仿真账目。八卡holder=True。

## 绑定与边界

- 任务书SHA：`363c50bedcb04d93a5904bf7ecf9873d691974e7e67d82f3a419af4c0065ff5e`。
- 新代码：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/standalone_ablation_20260918`；新产物：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918`。旧native10/ACT-RECAP、READY v14、原config/freeze和旧账本均保留只读。
- 沿用原held100，五任务各20不同物理初态；98个cut，2个无报警共同结局。三新臂各392实测分支加8共同计分位置，完整400分母；不重新capture、替补或登记scene。
- 本次是已揭晓队列的结构消融，不是新独立held；三solo−R为同一主要比较族，不按结果挑最好方法。

## 实现

三个入口各自产生a0及本方向，post/direct/velocity分别1/2/2次采样。只共享已加载模型和已恢复状态，不共享a0缓存；生产入口不生成V/D/post以外的其他方向、reverse或random。每组半径仅由自身容量与固定target决定，自身零组才归零；保留可放大原生小位移的规则。

保留A4000四成员、原native10/300步/一次干预、alpha10和tau .3/.2/.1、原概率目标和clamp导数、原mask及raw命令恒等。每个实际入口完成后核旧a0/noise/context/mask，旧bank仅供审计，不作为生成输入。

原完整bank只在单独计费的技术预检路径重建，旧函数文件与目标Python3.12原生AST均严格校验，并捕获当次原生V/D。旧bank未保存原生V/D，不能由旧matched动作反推，也不能把CPU证明称为真实数值复现。

## CPU与预算

最终CPU：**125通过、0失败**，路径`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/cpu_v3`，seal `ebcc3904757af5406be29543fa5d221fac5c71a986e48aad3d25247dcf53aa8a`。新代码/测试/脚本22文件在测试前后SHA一致。失败v1和已通过v2均保留；v1两项为引用去重测试预期与Python3.11/3.12 AST序列化差异，已修正，没有改变旧源码或算法。

正式计费为98×(1 bank恢复+3×4 branch)=1274；每branch包含自己的恢复。新账本carry-in48183sim/51200opt；新增cap1500/0opt、跨账本最多49683sim，原50000上限不变。阶段cap60/1400/40，repair初始锁定。没有把旧剩余技术额度再叠加。

**预检文本待分析端统一：最新消息写30，而实际TASK第6/7节写50（5源×2bank+5旧rep0+3solo rep0）。本pending按磁盘TASK明确记录50，因此计划1324、累计49507；它不授权运行，也没有静默增加实际attempt。若确定30，须冻结明确的分支清单并生成新pending/契约，不能仅改总数。**

## 运行和交付接线

新READY必须使用精确`future_ready_fields.json`。授权递归引用36个实际文件已只读核SHA；真正freeze会同时枚举原件和独立副本，且保留原大权重身份。预检通过条件下沉至模型工厂和账本，不能绕过runner直接进入正式阶段；异常保留日志/计数，不自动重试或启动新wave。

真实预检5worker、正式8GPU×4worker，均整波lifecycle封装。正式全100闭合、逐轨迹/scene/raw/配对/账本审计通过后，输出8臂逐源4后缀及五任务统计。三主要比较同时报告95%与Bonferroni98.333%源bootstrap区间；seed2026091801、10000次、任务内整源、linear。solo−旧同臂及solo−N为诊断/次要。

Q、实际增益、XYZ/grip新旧幅度/零组/角度及独立成本另行只读汇总。完整entry计时包含各自a0；模型加载、恢复、后缀、原fullbank诊断分开，不把共享a0摊销成本称为独立部署性能。A4000训练仍使用混合方向数据。

## 精确材料

- pending config SHA `f1cf094b4ac0cd53c9e77ea9911e5a6abbd6746496b35bbe2eea6103f4239124`；pending seal `5b55146a6fb9999c28a57c9c618aa99b29b7eed9576b2b38b2c8fa4eca6679b9`。
- future READY字段：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/handoff_v1/future_ready_fields.json`。
- CPU、来源、预算、方法与路径机器可读交接：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/handoff_v1/handoff.json`。
- 新状态：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/coordination/STANDALONE_ABLATION_EXECUTOR_STATUS.json`。

本材料不声称真实preflight或跨实现配对已经通过；当前实际model/sim/opt均0。分析端闭合TASK/READY清单后再按冻结条件执行，无需用户重复确认。
