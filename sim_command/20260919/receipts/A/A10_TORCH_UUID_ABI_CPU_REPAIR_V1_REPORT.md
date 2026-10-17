| 项目 | 可用 / 缺口 |
|---|---|
| 状态 | CPU 修正完成；native V3 仅提案，未授权、未执行 |
| ABI 依据 | 本地 Torch 2.7.1+cu126 / e2d141…：stub uuid:str；官方绑定 `_CUuuid` 与 `__str__`，直接绑定 properties.uuid |
| 最小差异 | 新快照 419 文件中 417 不变；仅 UUID 处理/证据及 V3 release 身份两文件变化 |
| UUID 合同 | 原生 str 或实际类 token 身份；可信非字符串转换一次；完整 ASCII UUID + 可选字面 GPU-，严格目标比较 |
| 证据 | properties 仍一次；转换前持久化原类型，决策前持久化转换/异常/格式/目标结果；旧运行具体类型仍未知 |
| CPU 检查 | 50/50 fake 与授权拒绝检查通过；新增 419 文件 SHA / 16 新集成引用核对，11 旧隔离库引用原样继承 |
| 本轮实际计算 | Torch import / 显式 dlopen / CUDA / EGL / NVML / 模型 / 环境 / reset / 训练 / 删除均 0；holder 未查询、未停止 |
| 待分析放行 | 固定 shelf-place 同源同 seed：1 attempt，5 native/50 flow，1 step/13 子步，2 张 corner2 RGB；52 reset/26000 初始化子步、108 显式 graphics 均不变 |

静态依据：[冻结源码核对](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1/ABI_SOURCE_REVIEW.json)；[官方对应提交](https://raw.githubusercontent.com/pytorch/pytorch/e2d141dbde55c2a4370fac5165b0561b6af4798b/torch/csrc/cuda/Module.cpp)。静态绑定信息不替代旧运行未记录的对象类型。

[精确差异](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1/UUID_ONLY_DIFF.patch) · [定向测试](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1_r1/targeted_tests_01/TEST_RESULT.json) · [CPU_READY](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1/CPU_READY.json) · [V3 提案](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1/proposal/PROPOSAL.json)。PROPOSAL SHA256 `a8659f3d89f34a9cdc4741f3ef222220f3bf773273cf2e67104f4b71f5732c88`。

唯一真实入口：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1/commands/run_proposed_native_preflight.sh NEW_RELEASE_JSON`；纯 CPU 授权入口同目录 `check_authorization_cpu.sh NEW_RELEASE_JSON`。本轮两入口均未执行；真实入口自带完整 SHA，未来放行后无需额外 CPU checker。

独占 claim、A-only 全 8 holder 停至整个进程组退出（含失败）、1800+30 仅约束诊断子进程规则不变。完整 rollout/monitor/critic/反向/更新/重试/删除均 0，无独立 UUID 探针或球体渲染。旧包与回执不改，全部本轮证据保留。

公开源码首次数下载受沙箱 DNS 限制失败，取得网络权限后定向下载成功；这是 CPU 取证恢复，无计算重试。无工程阻塞；真实 native V3 结果仍须另行 release 后取得。
