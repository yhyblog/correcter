# B10 预检修订 R2

只修订后续两次 synthetic LVM GPU forward 的启动授权与设备绑定。B10 r1 的结果、模型和训练提案不改；本包不执行训练、仿真或闭环评测。

本机8张 NVIDIA H100 80GB HBM3，driver535.161.08。选择 UUID `GPU-4143840e-6c2e-d4c4-8c60-4005cfa1f917`，PCI `00000000:0F:00.0`。运行时在导入 torch 前设置 `CUDA_VISIBLE_DEVICES` 为完整UUID、`CUDA_DEVICE_ORDER=PCI_BUS_ID`；`cuda:0`因此指向该UUID，而不是依赖主机枚举序号。UUID、型号、driver或PCI不符立即拒绝。身份查询仅使用 nvidia-smi/NVML，不初始化CUDA。

授权要求同时满足：CONTROL未stop且正式开关开启；唯一active release id/path和唯一active task对应本包；release.status=released且尚未过期、未进入closed历史；任务板恰有一个匹配id/owner=B/revision、状态ready或running、release路径一致；本机hostname与角色绑定一致；仅单机B参与；code/config/input/lifecycle文件SHA不变；release计数等于配置、全局和单任务caps覆盖；180秒+20秒kill grace，重试0。每次模型初始化/forward之前重读CONTROL/任务板并检查release未变。

`commands/verify_release.sh ABSOLUTE_ANALYSIS_RELEASE`：完整无模型验证，不写claim、不改变占卡；只在元数据与文件检查通过后查询GPU。当前P00拒绝预期已验证。

`commands/run_preflight.sh ABSOLUTE_ANALYSIS_RELEASE`：先验证，再经工作区gpu_occupancy_lifecycle.sh包装整个独立B wave；内部再次验证及UUID绑定后才导入模型。全部8卡holder暂停至命令退出（含失败），不启动idle子集holder。已有claim禁止自动重跑。无需联合A/B屏障，调度继续先A后B。

命令工作目录、配置和Python均写明绝对路径。本包code manifest不包含template以避免SHA自引用；发布产物manifest同时记录template自身SHA。`release_template.json`的status为draft、有效时间为null，不放行计算；CONTROL_REQUIRED.json给分析端明确的唯一task/release/caps/board字段。未来采用不同任务身份需要另发一致的新包，不能仅打开全局开关。

预算保持1次模型初始化、最多2次GPU模型forward，仿真/VLA/更新全部0；只检查已有LVM加载、API、输出形状和有限值。GPU墙钟上界200秒（包含kill grace），全8卡reservation相应最多1600卡秒的作业部分；lifecycle交接/恢复耗时独立，不伪装成模型GPU时间。模型输入与旧B10相同，预计VRAM2GiB、输出0.1GiB均为未实测估计。标准完整命令做两次只读nvidia-smi身份查询；内部NVML函数次数不作虚构计数。

9项CPU测试通过，覆盖36条已登记拒绝子例及文件篡改、枚举失败、当前P00拒绝；未导入torch/numpy，也未初始化CUDA。未重复B00盘点或原27项基线测试。

存储附项仅检查分析清单的27个payload（11个候选父路径），共18013109184逻辑bytes。B比较精确路径/类型/大小/mtime，不把主机inode/device当跨机身份，也不重复哈希18GB。50个本机可见进程的fd/maps和定向下载恢复信号检查未发现使用者，权限缺口0；当前/计划B配置无使用依赖。B承诺后续当前任务不打开候选，需求变化先通知分析端。证据是一时点、本机namespace内的观察，不能替代A删除前复核或跨机锁；分析决定、A执行，B未删除。
