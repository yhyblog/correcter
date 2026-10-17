# 最终 A4000：第二次开发五臂测评决定

2026-09-17 UTC。最终训练、固定选择及模型/资源独立复核通过。科学方案确定为一次既定的最终开发测评，选中 critic 固定 A4000。**本文件授权工程准备；真实模型装载/环境/仿真仍需后续 READY 显式释放并绑定已审的新阶段实现。** 当前 live READY v10 仅释放已经完成的训练，不是 policy 许可。

## 模型与数据

- 只使用 `outputs/native10_training_20260916/models/final/final_fit_v1/selected`，selected seal `f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a`。
- 选中路径/步数为 A4000；四模型身份以该 complete、ranking、config 及 `analysis/final_trained_model_review.json` 中的实际 SHA 为准。绑定真实 `selected_reload_audit.json`，不得仅检查缓存或旧 B200 权重。
- 使用原 dev100 注册槽 `2026111600..2026111699`，每任务 20 个不同物理初态。原采集、场景、cut、原 a0 与初始采样噪声身份保留；数据来源仍是原 round1 collection，当前生成 critic 改为最终 A4000，不能伪改来源字段以绕过旧 guard。
- 95 个已有有效 cut；5 个无 cut 源保留原共同结局（4 成功、1 失败）和全部 100 源分母。禁止新 capture、替补、按结果筛源或为某一模型改 cut。

## 臂、配对与方法

固定 normal/continue_native10、replan、velocity、direct、post 五臂，每源 4 个配对后缀。95 个 cut 源生成新的银行，并实际执行 95×5×4=1900 分支；不复用旧 guided 结果，不增加第六臂。

从 episode 起的 native10、有效报警 cut 语义、G0=.05、raw a0、critic C(raw)、修正 mask、velocity/direct alpha10 与 times=.3/.2/.1、XYZ/gripper 半径与上限、matched 规则及原接受语义全部保持。normal 完成原剩余队列；replan 与三种纠偏均按既定 prefix10/fixed10 后缀执行，总控制预算300。不给 A4000 新增 Q 门、拒绝门、任务条件、强度搜索或重新规划规则。

沿原 seed namespace 和原 source/repeat/suffix 配对键。新生成前真实核对原 a0/noise/raw mask；保持 raw 命令及 critic 映射检查。注入比较只要求本轮的既定 matched 规则，不要求跨 critic 半径或方向与旧模型相等。技术不一致须中止并保留证据，不用结果相似代替原始身份核验。

## 预算和统计

- 拟 stage/scope 均为 `round2_development_policy`。
- 预计 95 次独立 bank restore +1900 分支 =1995 次仿真，阶段硬上限2100；失败/重试均记账，未授权自动重跑。
- 优化更新为0；工作流优化预算51200已全部用完。仿真仍为50000硬上限，起始42874；不得挪用未来阶段或技术储备绕过本阶段上限。
- 主结果仅比较本轮新五臂内部的 I=R−N、三个 A=corrected−R、三个 T=corrected−N，共7个配对比较。按任务分层整源 bootstrap10000次、seed2026091622、percentile95%，保持线性分位数及未做多比较校正的说明；4后缀不是4个独立源。
- 报告全部100源总体、每任务20源、95cut条件结果与5共同结局、逐源/逐repeat、救回/损害、正负零源、Q预测与实际增益、raw/mask/alias/fallback、来源和预算。
- 跨轮结果可作明确标注的描述性对照；未经实际噪声/轨迹配对证据，不因源相同声称跨轮配对因果增益。不以中途结果选注入赢家或自动宣称达到+5pp。
- 时间拆分保持源恢复、候选 bank（不含恢复）、各采样/梯度子步骤及完整 wall；post 梯度子步骤不是完整部署时延。

## 工程准备与真实运行门槛

旧 policy5 prepare/guard/runner 硬编码 round1/B200，不能只改 READY 或绕过断言来运行新模型。执行端在新隔离模块中做最小阶段适配，复用已审原始执行与统计逻辑，旧模型、采集、预检、fit、policy1 封存及依赖保持只读。

提交新实际 prepare/collector/guard/runner 的连接说明、必要 CPU 通过证据、所用代码 SHA、原100槽/95银行输入绑定及精确 READY 契约。重点验证 A4000 实际模型身份、原 a0/noise/raw mask、禁止 capture/替补/旧 guided 复用、stage/scope/预算及失败关闭。只做所需检查，不重复大规模技术仿真或预检。

分析端绑定必要材料的 READY 后，执行端完成独立 config/code/READY/CPU evidence freeze，核验通过即可直接运行一次，无需重复请求许可。正式 GPU 工作使用 lifecycle；按既定8GPU×4worker运行，退出恢复holder。新工程、封存或模型身份若不一致，先报告具体技术差异，不静默换模型或参数。

完成后全量 raw 分支审计、独立统计重聚合、模型/代码/输入冻结核验及预算闭合，通过后交分析端判断。calibration 与 heldout 保持锁定；不得用开发结果冒充独立验证或自动启动下一阶段。
