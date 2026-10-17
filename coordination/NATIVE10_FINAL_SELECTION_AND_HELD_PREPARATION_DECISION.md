# 最终选择封存与 held 工程准备决定

2026-09-17 UTC。校准主审计完整、100源post−replan=14/200=+0.07，预登记规则的确定性结论为启用post。本文件确定最终科学方案并授权隔离准备；**正式选择封存须新的READY显式释放0资源scope；held真实初始化、模型调用及仿真须再由后续READY绑定实际选择seal后释放。** 不以旧v12权限启动下一阶段。

## 1. 最终选择内容

- Critic固定A4000四成员，selected seal `f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a`；PCA、模型、G0全部不变。
- 主策略：首次合法G0报警时启用post，拒绝分支的定义仍为同a0重规划，但全局选择为启用；无报警保留normal native10共同结局。
- 依据仅为预登记全100源等权post−replan均值严格大于0。不得用Q、CI、任务或其他方法重新选择。
- 封存的是原 **matched-post**：完整生成velocity/direct/post/reverse/random，沿现有mask和全部方向可行半径取共同半径；保留可能放大原生方向、零组、raw/C(raw)、cap、prefix10、fixed10后缀及总控制预算300的既有语义。精确参数以本轮calibration冻结config中的matching/guidance/command_semantics为准。
- 五个物理臂仍为normal、replan、velocity、direct、post；reverse/random等输出只保存。不得静默删除半径依赖，也不增加物理第六臂、Q门、任务路由或独立post强度。

## 2. 0资源选择封存

执行端可准备一个最小、独立的选择封存入口，scope/stage建议统一为`calibration_selection_seal`。它只核验已封存输入并写确定性metadata/complete，不执行模型前向、PCA、优化、环境初始化或仿真；不得重算/重选其他候选。

提交精确字段契约或待封存payload供READY绑定，至少包含：

1. 最终A4000权重/selected/reload身份、原calibration config/freeze及全部matching/guidance/command语义绑定。
2. 主审计seal/result、原始100源/200结局与14次净差、固定规则、无报警处理、结果及资源独立复核。
3. `method=post`、全局启用、唯一主比较post−replan、其余预登记次要比较、held尚未打开。
4. scope、资源0/0、输出目录、原输入只读、实际READY SHA及写后完整SHA清单。所有path/SHA引用须可被严格inventory识别；没有现存实际路径的裸sha不混入授权引用。

选择封存不需要模型重载、仿真预检或重复79项CPU检查。仅对新metadata入口做必要结构/身份/资源拒绝检查。未经其实际seal返回并被held READY绑定，不自动开始held。

## 3. held隔离工程准备，可与选择入口准备并行

- 使用原main registration v2的100个held主槽，每任务20；原有序backup保持。当前只读注册元数据，不初始化held、不采轨迹、不提前查物理场景或看结局。
- 每源4个配对后缀、原五个物理臂，最多100capture+100bank+2000branch=2200常规sim，新增优化0。初始化技术失败/首次动作前重复才可按原规则使用共享technical_reserve，不能增加1200总储备或按结果换源。
- 当前global46025sim/51200opt、reserve0。held2200与全部剩余技术储备1200合计后为49425，仍低于50000；这不是本文件的真实运行授权。
- 实际运行时首次动作前验证每任务20个不同物理初态及与已接受train/dev/cal同任务场景无碰撞。无报警/提前正常结束保留共同结局与完整100源分母，技术缺失不能填0或凑有利源。
- 完整沿原native10/G0/cut、所有候选生成依赖、随机流与五臂执行规则；保留真实loaded A4000、raw/noise/mask/C/matched、scene及预算检查。新的来源是held，不能混用dev/cal的source、anchor或原始结局。
- 独立prepare/runner/guard与必要CPU检查；授权文件所有绝对/相对/嵌套引用同时入冻结清单，增长账本/scene只用不可变快照和授权前缀绑定。
- GPU实际波次将使用原lifecycle与8GPU×4worker，退出恢复holder；无自动重试或补看结果后追加样本。

## 4. 最终统计与判断边界

唯一主比较固定 **post−replan**。同时报告replan−normal、post−normal，以及V/D相对R/N四项次要比较，共原七项；不在held后另选最好方法作为主结论。

以100个独立初态为统计单位，源内4后缀先平均；任务内整源bootstrap10000次，seed2026091622、percentile95/linear，冻结实际任务及源顺序。报告每任务20源、整体/报警条件/共同结局、配对救回与损害、正负零源及Q/raw/成本。七项区间仍标未校正多比较；主比较的身份在held打开前固定。

约+5pp是既定实用目标，原样保留。报告主比较点估计与区间，分别说明是否达到该点估计目标、区间是否支持正增益；不能把点估计达到5pp说成真实收益至少5pp，也不能把不显著写成严格无效。不得因结果改变阈值、样本量、模型或任务组合。

校准与held结果分别报告；不合并成单一“独立验证”分母，不对held后验筛选任务或源。当前范围是固定五任务、native10、首次合法报警的一次干预，不能外推到新任务或多次报警策略。

提交简短工程交接、实际CPU/代码/注册输入/选择seal绑定与精确READY字段；完整清单单列。分析端主导科学判断，执行端实现和运行；用户无需重复确认本计划内的准备工作。
