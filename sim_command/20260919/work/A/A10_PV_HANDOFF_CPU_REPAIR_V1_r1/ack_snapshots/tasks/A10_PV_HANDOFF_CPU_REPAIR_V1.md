# A：占卡交接等待修订与离线 P/V V3 准备（仅 CPU）

task_id=`A10_PV_HANDOFF_CPU_REPAIR_V1`；revision=1；owner=A。授权 `releases/P00_PV_HANDOFF_CPU_REPAIR_V1.json`。先写本任务 ACK；本任务不安装修补、不调用真实入口、不停止holder、不授予计算机会。

## 起点与诊断边界

`A10_PV_OFFLINE_PREFLIGHT_V2` 已验收失败并关闭，见 `manifests/A_PV_OFFLINE_PREFLIGHT_V2_FAILURE_ACCEPTANCE.json`。命令1/claim1、父NVML身份1，offline attempt及模型/梯度/环境计算0；八holder已恢复。旧机会/额度不复用。

保存源码和时序支持：active guard 的 run_formal 固定等待90秒，而daemon串行停止8个holder，每个TERM最多15秒、KILL后最多5秒；GPU6/7在失败返回后才yield。无deadline逐进程NVML行，不能把串行等待宣称为已排除所有其他原因。无需补探针、重演故障或重投旧回执。

静态审阅发现 `GPU_HOLDER_STOP_TIMEOUT_SECONDS` 只影响inactive-guard fallback，不能改变本次active-guard路径；外套更长timeout亦不能解决内部90秒拒绝。

## 最小修补方案

在本任务私有目录准备当前 `/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py` 的精确源SHA、最小patch、patched SHA及回退文件；**不安装到共享路径、不重启daemon**。优先仅令新run客户端的hand-off等待支持显式、有限、经校验的参数，现有默认90秒保持，daemon串行stop逻辑不变。建议本任务未来固定 `CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300`，由新提案/配置和实际入口绑定；未设置时兼容90秒，非法/非有限/越界值拒绝，不无限等候。说明环境参数如何进入实际active-guard run路径，不能只写无效export。

300秒来自8×(15+5)=160秒加poll/调度余量，是名义等待上限，不保证未知驱动查询/外部进程下成功，也不是整个任务端到端上界。若选择另一个有限值，明确推导和理由。

未来仍通过既有 `gpu_occupancy_lifecycle.sh run -- ...` 入口，沿用同一个formal.lock及原预约机制。禁止拿锁后递归调用该入口造成死锁，禁止先释放再重新预约造成holder恢复空窗；不绕过空GPU检查、不忽略某些GPU、不杀无关进程、不运行闲置子集holder。预约须覆盖所有8卡直到正式进程组完全退出，成功/失败均恢复占用。不得通过改daemon停止方式、换renderer、删除数据或改算法处理本问题。

如需记录handoff失败证据，只复用原轮询已取得的数据，保存最后一次观测/时间和超时原因，不增加硬件查询。区分holder/container PID与NVML host PID，不据未采集信息补造deadline快照；没有证据则null。

共享文件安装仅作为未来独立release的具体操作提案：列出唯一允许改动路径、原/新SHA、安装前比对、回退条件和命令。当前只准备，不安装。说明无需重启现有daemon的源码依据；如果发现必须重启或扩展共享修改，报告后由分析决定，不自行扩大。

## 独立 V3 包与保持项

以 `results/A/A10_PV_AUTH_METADATA_CPU_V1/` 为源，在 `results/A/A10_PV_HANDOFF_CPU_REPAIR_V1/` 冻结独立未来 task=`A10_PV_OFFLINE_PREFLIGHT_V3` / release=`P10_A_PV_OFFLINE_PREFLIGHT_V3` / revision1。新claim/run/wave/shard/output/cache唯一，旧七份release保持关闭。

只改身份/路径、明确的handoff参数/检查/必要证据与外部源manifest；逐文件列差异。数值算法、step0/raw50/seed/noise SHA、encoder/Q/PCA/norm、严格载入、独立自身半径、原66项数值和辅助caps、1800+30诊断子进程timeout、私有父子账本不变。输入权重SHA复用，不重新hash大模型，不读实现大树，不重跑全套算法/fake检查。

注意新包对共享guard的预期SHA与未来安装后实际字节一致；原SHA另列安装前置条件，不能将同一路径旧/新SHA同时当成运行时必须成立。实际入口必须拒绝缺失或不匹配修补，不能静默使用90秒或放宽哈希。给出准确新增安装/CPU操作和轮询计量语义；不把占卡交接时间混入诊断timeout或模型GPU秒。

TASK_BOARD仍从同源BOARD_TASK_TEMPLATE直接构建 `ready`，真实release `released`，模板当前 `UNAUTHORIZED_TEMPLATE`。复用并针对改动调整已验收纯JSON发布检查入口，确保handoff参数/身份/外部manifest/提案一致；不给当前CONTROL/任务板写真实计算状态。

## 定向检查与交付

只用fake时钟、fake应用列表、fake锁/子进程/信号和临时文件检查改动。至少覆盖：

- 模拟最后holder在90秒后、300秒前退出时，原90秒合同会拒绝而新等待完成后才启动一次；未清空不得启动。
- 超过有限等待/存在无关进程时失败，不杀无关进程；检查器/driver异常不会被当作空GPU。无自动重试。
- 锁/预约覆盖等待及整个命令进程组；成功/失败释放后恢复，不能提前在单卡完成后启动holder。
- 默认/合法300/非法值、缺失实际参数或未装预期patch按合同处理；新元数据board ready通过，旧身份/关闭记录拒绝。

fake不导入NVML/Torch、不调用真实guard命令或进程信号；测试临时文件锁不得占用真正formal.lock。仅做改动AST/shell检查。交短REPORT/RESULT、CPU_READY、差异/定向测试、精确安装与回退提案、新PROPOSAL/RELEASE_TEMPLATE/CONTROL_REQUIRED/BOARD_TASK_TEMPLATE、纯JSON发布检查用法及唯一未来命令。

当前Torch/dlopen/NVML/CUDA/EGL/模型/encoder/Q/梯度、环境/reset/render/物理/训练、真实launcher/claim/guard start/status/holder查询停止、共享安装/重启、删除均0。仅复用保存日志、静态源和小元数据，不新增GPU probe或handoff-only实测。收到CPU包后由分析决定下一步；不得自行执行V3。B不变，所有新证据保留。
