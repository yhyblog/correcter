# 仅供平台侧评估的容器启动配置

CPU 阶段已经在本任务隔离目录补齐匹配535.161.08的 EGL vendor/core/glsi/shader 库及 GLVND 配置。无需为了完成这项准备重启当前容器。尚未执行 EGL；不能声称隔离修复已在真实设备验证，也不能证明缺少 DRM 节点是当前唯一根因。

沙箱外只读文件检查确认 `/dev/nvidia0`、`/dev/nvidiactl`、`/dev/nvidia-uvm` 存在；`/dev/dri`、`/dev/nvidia-modeset` 不存在。sysfs 的 `card1` 与 `renderD128` 均映射 PCI `0000:0f:00.0`，内核记录对应 `GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe`。这些是静态映射依据；尚未得到 EGL 设备枚举结果。

如果新的一次 graphics-only 探针仍显示必要设备/驱动接口缺项，请平台在另建或经用户批准更新的容器规格中暴露 `compute,utility,graphics`，使用与宿主内核驱动匹配的 NVIDIA 容器运行时用户态组件。以下是标准 Docker 模板，IMAGE 必须填写与本项目现有依赖一致的镜像；不在当前容器执行，不与现有 A GPU 工作并发启动另一套作业：

```bash
docker run --rm --runtime=nvidia \
  --gpus '"device=GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe"' \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
  -v /mnt/bn/arnold-recommend/yaohaoyang:/mnt/bn/arnold-recommend/yaohaoyang \
  IMAGE bash
```

Kubernetes/内部平台应在容器创建参数设置上述能力、现有 NVIDIA RuntimeClass/device-plugin GPU 分配及同一工作区挂载。具体平台 YAML 未知，不编造 RuntimeClass 名称。若已分配的设备仍未注入，平台应检查该 GPU 对应的 DRM 节点/驱动组件，而不是无差别暴露全部宿主设备。

能力变量决定启动时组件挂载；在现有 shell 中单纯 `export NVIDIA_DRIVER_CAPABILITIES=graphics` 不补齐已经缺失的挂载。[NVIDIA 官方说明](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)

当前未执行容器命令、未安装/替换系统驱动、未切换 renderer。任何新容器中的实验仍须重新核对物理设备和代码身份并取得独立 release；此模板不授予计算额度。
