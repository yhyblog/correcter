# A：Torch UUID 表示合同的定向 CPU 修正

task_id=`A10_TORCH_UUID_ABI_CPU_REPAIR_V1`；revision=1；owner=A。CPU授权：`releases/P00_TORCH_UUID_ABI_CPU_REPAIR_V1.json`。实际CUDA/EGL/NVML/dlopen、Torch导入/设备探测、模型/环境/reset/物理推进/训练/删除均0，现有holder不查询、不停止。

## 已验收事实与修正依据

`A10_PREFLIGHT_NATIVE_V2`已技术失败结案，release消费关闭，未进入额度作废。八设备物理映射成功；policy set_device/properties均返回，之后非str类型守门拒绝。71项显式graphics调用均正常返回，不代表语义校验成功。模型初始化及diagnostic attempt均0，无RGB/transition/采样。

已保存 `str(properties.uuid)` 与目标UUID一致，但原对象具体类型未记录。旧回执继续保留类型未知，不把本次静态调查结果反填成旧运行实测证据。

分析端定向审查发现，本地Torch `2.7.1+cu126` 的 `torch/_C/__init__.pyi` 将uuid标注为str；本地 `version.py` 源码提交为 `e2d141dbde55c2a4370fac5165b0561b6af4798b`，其[官方 Module.cpp](https://raw.githubusercontent.com/pytorch/pytorch/e2d141dbde55c2a4370fac5165b0561b6af4798b/torch/csrc/cuda/Module.cpp)将CUuuid暴露为 `_CUuuid`、定义 `__str__` 并直接绑定device properties的uuid字段。请只定向核对并冻结这些依据及相关行，不扫描整个Torch仓库或重做环境盘点。

## 最小改动

1. 从已验收原生集成包派生新的不可变快照；只修正UUID表示处理及诊断证据、对应fake检查和新task/release身份。旧包、回执、共享Torch/conda/系统库不改。
2. 明確支持原生str和实际已加载 `torch._C._CUuuid` 类对象；按可信类对象身份判定，不仅按模块/类型名称，也不接受任意stringifiable对象。运行时类型对象从既有Torch导入取得，不增加设备查询；CPU检查不得为此导入Torch。
3. 原字符串直接使用；支持的非字符串对象仅调用一次str转换。对结果做完整ASCII UUID格式匹配，只允许明确的可选 `GPU-` 前缀与十六进制大小写归一，再与冻结目标严格相等。拒绝bytes、空白、截断、错误UUID、未知对象及转换异常；不解析或交换UUID字节序，不删除身份守门。
4. 在既有一次properties调用返回后，先保存原对象 `type.__module__` / `type.__qualname__`、支持类型分支、转换结果或异常、格式判定和目标比较结果，再决定是否继续。失败路径也保留类型证据，不重复调用properties或转换。`torch_uuid_text`等新字段应明确是表示文本，不能再将str转换值称为原对象。
5. 保留八设备映射、冻结可见性、固定物理UUID/PCI、Torch独立身份核对及绑定后loader快照。测试只用受控fake类，覆盖支持的两种输入、伪造同名类、任意stringifiable对象、错误UUID、格式异常及转换异常。复用现有流程，只运行相关新检查和新release拒绝检查，不重跑旧全套。
6. 新提案建议 `A10_PREFLIGHT_NATIVE_V3` / `P10_A_NATIVE_PREFLIGHT_V3`。诊断目标仍为同一源和seed、5native/50flow、1控制步/13子步、两张corner2 RGB；初始化52reset/26000子步、显式graphics预算108项保持，完整rollout/monitor/critic/反向/更新/重试/删除0。若修正要求改变调用预算，明确说明，不能暗增查询。
7. 发布新CPU_READY、PROPOSAL、RELEASE_TEMPLATE、CONTROL_REQUIRED、manifest及唯一真实命令，所有模板保持未授权。保留独占claim、A-only全8卡holder直到进程组退出、1800+30只限子进程的原规则；不额外做UUID小探针或重跑球体渲染。

## 交付

先写本任务ACK；交 `receipts/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1_REPORT.md` / `A10_TORCH_UUID_ABI_CPU_REPAIR_V1_RESULT.json`。短报告包含静态ABI依据、精确差异、fake结果、实际零计算声明及新有限提案引用。

不得新增硬件探测来补旧Python类型证据；未来类型证据只在另行放行的同一次原生诊断中取得。此CPU任务不授权V3运行，不调用真实入口作dry-run，不重复hash大模型或重新盘点存储。全部新证据保留。
