# A11：观测阶段名称与 s300 范围的定向 CPU 修复

task_id=`A11_OBSERVATION_PHASE_CPU_REPAIR_V1`；revision=1；owner=A。release=`releases/P00_A_OBSERVATION_PHASE_CPU_REPAIR_V1.json`。核对 CONTROL43 / TASK_BOARD50、host和新release SHA后写新ACK。V3已消费关闭，见 `releases/P11_A_COMMON_POOL_FIRST_PARENT_V3_CLOSED.json`；本任务没有真实计算权限。

## 已确认故障与范围

真实V3仅normal进入：模型1/语言1、环境2、初始化51 native reset/102 reset_model/25500物理子步已经发生；随后reset调用`observation_scope('step0')`被CONFIG的`step_0..step_16`拒绝。step调用也沿用无下划线命名，所以不能只改单个字符串；CONFIG仍须覆盖既定s300。诊断reset/观测/策略采样0，success=null、有效样本0。原堆栈/包/回执/claim保留，不重投旧任务，不回填数据。

## 最小修复与验证

1. 建立一个纯CPU规范函数，如`observation_phase(t)`，仅接受严格整数0≤t≤300（拒绝bool及非整数），返回`step_{t}`。真实reset取t=0，真实step取step+1，两个调用点共用同一规则。
2. 新CONFIG明确列出`step_0`到`step_300`共301项，并在真实入口进入模型/硬件前用纯元数据检查确认恰好匹配既定absolute_target=300。保留scope白名单、禁止嵌套、finally清理和render hook约束，不允许任意字符串或通配符。
3. 定向组合fixture必须使用新真实CONFIG、真实规范函数、实际`NativeEGL.observation_scope`方法（允许AST提取实际方法并提供标准库contextmanager和CPU替身journal），不初始化EGL/模型。遍历s0–s300验证进入/退出；边界重点0/16/17/299/300，以及负数、301、bool/非整数、旧拼写、非法字符串。选定阶段覆盖异常退出后清理、嵌套拒绝及后续可进入。通过窄AST/提取实际方法证明两个真实调用点使用同源函数；不能再次只测独立fake调用者。
4. 定向确认render/scene/readback记账接收同一个阶段名称，301个阶段只是既有每attempt301次观测的标签，不新增真实操作。保持116caps、453sample/4530flow/4500control/4515obs、15attempt、C5/C10、H10、s300、候选/噪声/状态资格/结局逻辑原样。若发现同一阶段链内其他硬编码限制，列确切证据并作最小一致修订，不扩成全项目审查。
5. 发布独立不可变代码/config小差异、定向CPU检查和新未授权未来`A11_COMMON_POOL_FIRST_PARENT_V4` / `P11_A_COMMON_POOL_FIRST_PARENT_V4`提案。V3已真实消耗一次工程attempt，后续仍是原计划父源：source/env_seed/master_seed不换；不要称V3从未执行。新V4 run/wave/shard/output/cache/claim/command_record隔离且不创建真实路径。保持原source身份/全部caps/storage/timeouts；metadata checker、BOARD ready和release模板同源，模板UNAUTHORIZED_TEMPLATE。只列本次必要新增CPU元数据成本。

沿用已接受的bounded_first_parent存储监测缺口及全8holder生命周期，不重做资源设计/容量探针。真实MJB/full-state资格仍留在同一计划parent，不追加短GPU验收。原public/sidecar_v1/supplement_v2、共享包/guard、旧失败包与回执保持不变；B现有CPU任务不变，不修改共享dispatch。

交新RESULT/REPORT/CPU_READY、窄DIFF、真实组合检查、新未授权V4提案及必要SHA manifest。只测试本轮变动；不重跑旧80/104/133套、不重新盘点/历史账本或大权重hash。

本轮Torch/MuJoCo导入、dlopen/GPU/CUDA/EGL/NVML/holder、模型/特征/环境/reset/采样/训练、真实launcher/claim、安装/删除均0。显式synthetic CPU操作另账。完成等分析验收，不自动采集；11份旧计算release（含本次V3）全部关闭，未用额度不复用。
