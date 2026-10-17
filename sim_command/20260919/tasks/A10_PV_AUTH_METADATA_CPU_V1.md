# A：离线 P/V 授权元数据修订（仅 CPU）

task_id=`A10_PV_AUTH_METADATA_CPU_V1`；revision=1；owner=A；授权 `releases/P00_PV_AUTH_METADATA_CPU_V1.json`。先写本任务 ACK。本任务不授予真实命令或计算机会。

## 已结案事实

分析端发布 TASK_BOARD29 时误用 `status=released`，与旧包 `CONTROL_REQUIRED.board_task.status=ready` 及冻结入口 `ready/running` 合同冲突。旧命令执行1次，在claim之前失败；claim/计算0，holder未停。见 `manifests/A_PV_OFFLINE_PREFLIGHT_V1_FAILURE_ACCEPTANCE.json`。`P10_A_PV_OFFLINE_PREFLIGHT_V1` 已关闭，旧包及原回执均不改、旧机会不复用。无需重复旧失败审计或库存。

## 唯一修订范围

以 `results/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1/` 为来源，发布独立新包 `results/A/A10_PV_AUTH_METADATA_CPU_V1/`。未来计算身份为 task=`A10_PV_OFFLINE_PREFLIGHT_V2`，release=`P10_A_PV_OFFLINE_PREFLIGHT_V2`，task_revision=1；当前只是未授权模板。

只调整新包的授权常量、包根/命令/输出路径、模板/proposal/CONTROL_REQUIRED及相应manifest引用。新run/wave/shard/claim路径必须与旧V1独立，不覆盖旧结果。提供逐文件差异清单，区分身份/路径变更与数值文件字节未变证明。复用既有输入SHA，不重新hash大权重；不重新跑完整算法/fake检查或另造特征/噪声。

数值算法、step0/raw50/seed及noise SHA、同源encoder/投影/四成员PCA/norm、严格SFT单次载入证明、设备绑定、私有账本、操作caps、1800+30子进程timeout、A-only全8holder生命周期保持原样。不借本次重构launcher或增加模型/调用预算。旧loader在claim前失败不产生内部LAUNCH_RESULT的范围已准确记录，本次不要求顺带改变。

## 状态合同与定向 CPU 检查

以 `contracts/TASK_STATE_CONTRACT_V1.md` 为准。TASK_BOARD中唯一任务条目必须 `id=新task, owner=A, revision=1, status=ready, release=releases/新release.json`；未来真实release内部为 `status=released`。二者不是同一状态字段。

用纯JSON/临时fixture进行少量定向检查，调用或抽取实际元数据验证函数；不调用真实launcher，不运行完整输入hash或claim/lifecycle。覆盖：

- 同一拟发布合同的board ready、running分别通过；board released必须拒绝。
- CONTROL唯一任务/release/path、allowed、全局及单任务caps，board owner/revision/release，proposal/release五类manifest SHA、host/device/cuda环境一致；错revision、错caps或错active identity拒绝。
- 新V2身份通过；旧V1、已关闭release及重复claim相关既有拒绝语义保持。相关检查采用临时fixture，不制造真实claim，不修改当前CONTROL/旧关闭记录。
- 生成与 `RELEASE_TEMPLATE`、`CONTROL_REQUIRED` 同源的完整拟发布board条目，避免分析端再次手写出另一套状态。模板仍未授权，不把CPU fixture当真实放行。

针对实际身份/路径变更做必要AST/shell检查。提交一个可供分析端在发布前核对纯JSON元数据的明确入口/用法；该入口只允许读取元数据和小manifest，不得导入Torch、查询GPU、完整hash模型、写claim或运行真实命令。若使用现有纯函数即可，不为此增加新测试框架。

## 交付及边界

交本任务短REPORT/RESULT、CPU_READY、新PROPOSAL、RELEASE_TEMPLATE、CONTROL_REQUIRED、唯一真实命令、上述定向检查/差异证据及必要manifest。报告新包 task/release/版本/路径/SHA 和精确board状态，给出未来单次V2提案；由分析另发计算release后方可执行。

未来预算仍1 offline attempt、1guided/10flow、Post1+Velocity3动作梯度、10ensemble/40成员前向；完整辅助caps逐项与旧已验收提案相等。诊断缓存成本不作部署成本；无新算法验证结论。

当前Torch import/dlopen/NVML/CUDA/EGL、模型/encoder/Q/梯度、环境/reset/render/物理/训练/正式命令/重试/删除全部0。不查询或停止holder，不修改共享环境、旧代码/回执和分析端CONTROL/TASK_BOARD。所有本次证据保留。B任务不变。
