已证实：隔离 EGL 入口可枚举 8 个设备；所有设备的 DRM 路径映射为空，容器 /dev/dri 不存在。目标 PCI/内核 UUID/NVML 三者一致，sysfs 的 card1 和 renderD128 指向该物理卡。当前证据不足以断言 EGL context 本身不能运行，也不足以要求重建容器。

原实现未保存 DRM 查询原始 NULL/空串，也未查询 EGL error；报告只断言“无可用路径”。后续 CPU 修订宜保留 token、原始空值类别及失败阶段，新增查询必须明确计费。

供分析端决定的优先候选：CPU 审查 EGL_EXT_device_persistent_id 路线。8 个已枚举设备均宣告此扩展。规范提供 eglQueryDeviceBinaryEXT(EGL_DEVICE_UUID_EXT, 16-byte buffer)；固定长度无需再做长度探测。按目标 UUID 字节与已核对的内核/NVML PCI 身份做唯一匹配；结合 driver identity 消歧，拒绝任何零匹配、多匹配或不一致。不能把扩展声明当作实际 UUID 已验证，也不能假定 NVIDIA 字符串与二进制对应而跳过核对。此路线本轮未实现、未调用；如采纳，须另发 CPU 修订及带显式 binary-query/driver-query caps 的新 graphics release。
[Khronos persistent-id 规范](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_persistent_id.txt)

替代候选：如分析端坚持 DRM 路线，由平台先确认主机目标 /dev/dri/card1、/dev/dri/renderD128 的 PCI、字符设备 major/minor 与权限，再决定精确挂载与设备 cgroup 放行。容器缺节点是事实，但尚不能证明单独补节点必能恢复查询或 context；不自行 mknod、不改共享驱动、不重启容器。EGL DRM 扩展允许设备无关联节点时返回 NULL，不能仅凭宣告扩展推断一定可得路径。
[Khronos DRM render-node 规范](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_drm_render_node.txt)

以上仅为修复建议，未改变本次冻结 bundle/命令/设备/库；一次 release 已消耗，未执行第二次查询、枚举或渲染。
