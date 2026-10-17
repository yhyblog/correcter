# P10 有限预检审查决定

2026-09-19。A10 r1、B10 r1 的 CPU 准备均验收；回执产物 SHA 通过，正式计算计数为0。验收记录：`manifests/P10_PREPARATION_ACCEPTANCE_V1.json`。公共历史访问索引冻结于 `manifests/HISTORICAL_DATA_ACCESS_V1.json`，不等于完整新公共训练池。

## 当前决定

**原报价暂不发布 GPU release，先完成两个有限 CPU 修正。**已发布 `releases/P00_PREFLIGHT_CORRECTIONS_V1.json`，不扩大科学实验矩阵、不重跑已完成历史阶段。

| 节点 | 原预检 | 需修正 | 后续放行范围 |
|---|---|---|---|
| A | 原生 π0.5 加载、五H队列、单步 transition | MetaWorld 构造隐式50次reset，加包装/诊断至少52次reset、至少2个环境实例；原声明1/1不成立。绑定实际包源，明确初始化预算/观测与timeout作用域 | 1诊断初态、1诊断attempt、5完整采样/50flow、1策略控制步；初始化另计；0完整rollout/梯度/monitor/更新/重试 |
| B | 旧 LVM 2次 synthetic GPU forward | 补 GPU UUID/driver/可见设备及当前active release/status/全局预算检查 | 1模型初始化、2forward、0VLA/仿真/更新/重试；只验证加载/API/有限性 |

A 修正版独立达到要求即可先发布，不必等 B；B 先做 CPU 修正及共享资产依赖核查。当前控制采用单一 active_compute_release_id，两个 GPU 预检顺序发布为各自单机 wave。非参与节点保持其正常 occupancy；参与节点整个 wave 所有holder停算，失败退出也恢复。此处不发布联合波次，后续联合波次仍须冻结双方 compute-exited 屏障。

A 的1800+30秒、B 的180+20秒需写清受控进程范围；前置校验、预约建立与恢复记录实际时间，不能冒称已包含于进程timeout。输入/代码/配置/模型/SHA漂移、设备不符或预算耗尽即停，不换初态、不自动重试。

## 下一份可执行 release 的验收条件

- 修正任务只在各自新目录发布，原 A10/B10 回执与公共 interface_v1 不变。
- 报价、实际命令、授权守门及观测计数一致；纯 CPU 授权检查通过。只做修正涉及的必要检查，不重复无关整套准备。
- 精确输入、host、GPU UUID、driver、唯一 task/run/shard/wave、资源上限、timeout/重试、输出保留及失败回执均明确。
- 分析端发布 `status=released` 的新 GPU release 并更新 CONTROL/TASK_BOARD 后，执行端才运行。当前 CPU 修正 release 不能用于 GPU。

E1训练、GAF训练、VLA-Corrector新训练、共同池采集、真实 P/V 数值检查、MT50适配及正式评测均未随此次验收放行。

存储决定已逐路径保存于 `manifests/STORAGE_DECISIONS_V1.json`：4 keep，11 defer，0 delete。依赖核查由执行端完成；分析端不执行扫描或删除。
