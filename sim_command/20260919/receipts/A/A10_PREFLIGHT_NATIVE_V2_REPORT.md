| 项目 | 实际结果 |
|---|---|
| 本次执行 | 冻结sh执行1次，退出1；技术失败，release已消费，重试0 |
| 失败阶段 | heavy_imports_and_policy_device_binding；`Torch UUID property is not the frozen string ABI` |
| 八设备映射 | 完成；固定PCI 0000:0f:00.0 / GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe唯一匹配 |
| policy UUID | properties调用返回，保存的字符串表示与目标一致；原对象未通过str类型守门，不能记为绑定校验通过；确切Python类型未记录 |
| 模型/诊断/native/flow/控制 | 全0；模型未初始化、诊断attempt未进入，非任务成功率样本 |
| 初始化 | 环境/wrapper/reset/reset_model/初始化及策略物理子步均0 |
| graphics显式操作 | 71 entered /71 returned /0 failed /0 incomplete；语义守门失败独立报告 |
| context/RGB/产物 | EGL/MjrContext、render/readPixels、完整观测/可用NPZ均0；5H/raw50/transition/前后RGB未到达 |
| 清理与恢复 | releaseThread1，cleanup errors=[]；整个进程组退出，8holder恢复；不换卡/库/renderer/seed、不删除 |

实际主要graphics计数：显式cuInit1、枚举1、设备扩展/属性/PCI各8，driver load2、CUDA符号2、EGL核心符号11、getProc4、EGL error23（全EGL_SUCCESS），策略set_device/properties各1、releaseThread1。剩余预算全部作废。全部精确计数见 `ACTUAL_COUNTS.json` / `GRAPHICS_COUNTS.csv`；三套账本已独立重算与LAUNCH_RESULT一致。

`policy_device.json` 的 `torch_uuid_raw` 是冻结入口保存的 `str(properties.uuid)`，不是原对象的类型证据。失败证明原值不是str；不能据其显示值猜测确切类型。映射后535库身份有证据，Torch绑定后的loader快照因守门失败未到达；没有补做GPU/UUID探测。

子进程21.551秒；前置14.145秒、预约/holder释放48.646秒、恢复观察10.006秒；launcher端到端94.378秒，observer全程96.119秒。CPU观测单进程RSS/HWM最大441.492MiB；实际GPU秒和GPU峰值显存未知，保留null。两个正式入口内权重SHA流程已通过，未额外跑CPU checker或第三遍hash。

`process_family_cleanup.json` 确认独立进程组234766无存活成员，无需补发信号；命令退出后的进程检查为空。guard记录八次yield，首显式cuInit为19:39:11.059 UTC；八holder均在进程组退出后于19:39:20恢复（manager234886–234893，guard27508）。guard状态在串行停holder期间可能滞后，不当作逐采样NVML实测。

回执证据：本任务 `RESULT.json`、`LAUNCH_RESULT.json`、`FINAL_AUDIT.json`、资源/初始化/graphics账本、mapping/loader/policy UUID及缺产物表均保留。无RGB可做PNG转换，本轮转换0。旧封存、已验收代码与共享库不改。

建议分析端验收本次技术失败并关闭P10_A_NATIVE_PREFLIGHT_V2；下一步如需修正，应另发CPU任务，核实Torch UUID返回ABI、完善原类型记录和文本身份合同，随后另审新有限release。本次不实施修正，不进入P/V、采集、训练或完整评测。
