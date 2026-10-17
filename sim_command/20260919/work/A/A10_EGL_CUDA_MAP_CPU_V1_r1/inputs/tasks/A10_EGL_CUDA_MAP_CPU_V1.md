# A：EGL→CUDA handle→PCI 映射的有限 CPU 修订

task_id=`A10_EGL_CUDA_MAP_CPU_V1`；revision=1；owner=A。执行依据 `releases/P00_EGL_CUDA_MAP_CPU_V1.json`。上一graphics probe已消耗关闭；本任务是CPU静态/合成准备，任何CUDA初始化、EGL查询、display/context/渲染仍为0。

## 已接受事实与方法决定

前一探针一次枚举得到8个EGL设备，8个都声明 `EGL_NV_device_cuda` 与 `EGL_EXT_device_persistent_id`。DRM字符串没有可用路径，原记录未区分NULL/空串及错误码，不能事后补造。失败发生于物理身份守门检查，尚未调用display初始化，不证明context不可用。

**本次只准备一条确定路径：**`eglQueryDeviceAttribEXT(EGL_CUDA_DEVICE_NV)` 获取规范明确允许交给CUDA API的device handle，再用 `cuDeviceGetPCIBusId` 查询PCI，与已冻结目标 `0000:0f:00.0` 及 `/proc/driver/nvidia/gpus/.../information` 中的 `GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe` 核对。NVML UUID/PCI/driver一致性继续保留。不是把EGL、CUDA、NVML索引直接视作相同。[Khronos官方NV_device_cuda规范](https://registry.khronos.org/EGL/extensions/NV/EGL_NV_device_cuda.txt)。

不新增“去掉NVML GPU-前缀后直接与EGL二进制UUID比较”的路径：现有证据不足以证明该字符串编码与EGL值的字节关系，不尝试大小端变换直到匹配。persistent_id可作为后续有明确跨API证据时的备选，此次不实现、不增加查询。[Khronos persistent-id规范](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_persistent_id.txt)。当前也不要求平台补/dev/dri或重建容器。

## 最小修订

1. 复用冻结535.161.08 NVIDIA EGL/GLVND隔离栈，静态确认实际CUDA driver库来源、版本/SHA与加载顺序；不更换共享驱动或引入另一版本compat库优先项。冻结graphics子进程的CUDA可见性，解释API返回handle在该可见性下如何使用；不能将mask后的序号另行猜成EGL序号。
2. 检查FFI原型/ABI宽度、返回码和handle有效性；为每个EGL候选记录声明扩展、实际属性返回、CUDA PCI查询结果、规范化PCI和匹配结论。未匹配候选不创建context；只有唯一目标映射成立后才进入一次display/context。零匹配、多匹配或身份不一致即停止，不逐卡试context。
3. 原始NULL与空字符串分开记录；真实EGL/CUDA返回码按调用点保存，不推断未查询的错误状态。新增 `eglGetError` 等诊断调用也须在proposal显式封顶；旧回执只读。
4. CPU合成检查只覆盖此次映射/预算/拒绝路径：唯一匹配、零匹配、多匹配、CUDA返回失败、PCI/UUID冲突、可见性或ABI不符。仅用fake函数，不dlopen图形/CUDA库、不调用cuInit/任何EGL函数、不运行NVML以外的GPU探针、不重跑无关旧CPU全套。
5. 另发布新code/proposal/template/commands/bundle身份，原graphics v1和native v4/v5不改。给简短差异报告及独立新release所需精确CONTROL字段。

## 下一次单次graphics提案的预算要求（现在不执行）

保留1 attempt、1 EGL枚举、至多8次扩展字符串查询。新增 `cuInit≤1`、EGL CUDA属性查询≤8、`cuDeviceGetPCIBusId≤8`；函数地址查询、EGL错误查询和其他辅助调用按明确路径给有限上限。不要再并行尝试DRM/persistent_uuid等多个映射方案，不另做身份查询预探针。

唯一物理映射成立后才执行原有1 display初始化/1 EGLcontext/1个64×64静态场景/至多1显式mj_forward/1render/1RGB。新CUDA driver初始化不等于策略加载、CUDA context创建或CUDA kernel；如实现必须产生额外资源，明确列出，不隐入0项。VLA、MetaWorld/reset、物理时间推进、训练与自动重试仍0。

仍为120秒TERM＋10秒KILL子进程上限，前后准备/预约/恢复另计；整个A-only波次全A holder停算直到进程族退出，失败恢复。B不参加，旧release不复用。成功只证明单帧渲染，不放行native v5。

ACK/REPORT/RESULT 写 `receipts/A/A10_EGL_CUDA_MAP_CPU_V1_*`；产物写本角色独立work/results。当前删除0，所有新增证据保留。完成CPU修订直接交有限提案，不要求用户再次批准这项已授权工程准备。
