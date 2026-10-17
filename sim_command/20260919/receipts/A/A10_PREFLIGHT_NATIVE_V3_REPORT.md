| 项目 | 实际结果 |
|---|---|
| 本次执行 | 冻结 sh 1 次，退出 0；有限原生工程预检完成，claim/release 已消费，重试 0 |
| 诊断 / 采样 / 控制 | 1 attempt；H=10/20/30/40/50 各 1 native、10 flow，共 5/50；1 真实控制步 /13 子步 |
| 初始化 | 1 模型、2 原生环境+1 wrapper；52 native reset、104 reset_model、5200 settling 调用、26000 初始化子步；全部 entered/returned 一致 |
| graphics | 108 entered /108 returned /0 failed /0 incomplete；35 次 EGL error 均 SUCCESS；EGL/MjrContext 各 1、render/readPixels 各 2 |
| 观测 | 诊断 native reset 返回 1；初态/步后完整观测各 1，可用 NPZ 共 2；与 reset 返回分开计数 |
| 设备与 UUID | 固定 PCI 0000:0f:00.0 / GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe；8 设备映射一致；本次实测原类型 torch._C._CUuuid，真实类 token 匹配，str 1 次，格式/目标均通过 |
| loader / renderer | Torch 绑定后仍为冻结隔离 libcuda.so.535.161.08；GL/EGL vendor 均 NVIDIA；旧 V2 具体对象类型仍未知 |
| 5H 队列 | raw_plans 形状 5×50×4 float32，五组计划逐位相等、noise SHA 相同，首出队后长度 9/19/29/39/49 |
| transition | 真实 step0→1，与当前/next NPZ、首动作及 raw50 引用 SHA 一致；reward=0、success=false、terminal_success=null，完整 rollout=0 |
| RGB 目视 | 红机械臂/木桌/立式木架/蓝方块/绿目标点，前后同视角且有细微变化；符合 shelf-place；待分析目视验收 |
| 清理与 occupancy | cleanup errors=[]；进程组 244701 全部退出后 8 holder 于 20:19:23 UTC 恢复，manager245508–245515，guard27508；无残留正式进程 |
| 未执行 | monitor/critic/反向/更新/训练/完整 rollout/重试/删除均 0；未额外 checker、UUID 探针或 render |

三套账本已独立重算并与 LAUNCH_RESULT 一致；公共事件 63 返回、0 失败/未终结。子进程 218.908 秒，launcher 端到端 306.243 秒（前置13.944、停holder预约63.355、恢复观察10.005秒）；1800+30 只约束子进程。

去除父子重叠的 CUDA event 计时仅覆盖采样测量区间，共 2.480890 秒；全 GPU 利用率积分/总 GPU 秒未知，保留 null。PyTorch allocator 峰值 allocated8.892 / reserved9.217 GiB，不代表设备总显存；CPU 单进程观测 RSS37.987 / HWM39.341 GiB，不是进程树总峰值。

[初态 PNG](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_PREFLIGHT_NATIVE_V3_r1/RGB_views/RGB_diagnostic.png) · [步后 PNG](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_PREFLIGHT_NATIVE_V3_r1/RGB_views/RGB_post_control.png)；两图仅从已保存像素 CPU 无损编码，NPZ=PPM=PNG 逐像素一致，无裁切/翻转/缩放或新 render。两帧23915像素发生变化；场景判定依据目视，未仅凭非空缓冲。

[LAUNCH_RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/P10_launcher_runs/A10_PREFLIGHT_NATIVE_V3_r1_A_wave05/LAUNCH_RESULT.json) · [最终审计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_PREFLIGHT_NATIVE_V3_r1/FINAL_AUDIT.json) · [实际计数](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_PREFLIGHT_NATIVE_V3_r1/ACTUAL_COUNTS.json) · [保存产物审计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_PREFLIGHT_NATIVE_V3_r1/SAVED_OUTPUTS_AUDIT.json) · [类型与设备证据](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_PREFLIGHT_NATIVE_V3_r1/POLICY_UUID_EVIDENCE.json)。原始三账本、两观测、5H计划、transition、loader、cleanup 与 guard 日志均随 RESULT/manifest 保留。

正式运行无失败。CPU 图像审计首版过严拦截 NumPy 的 Python 当前进程句柄初始化，未进入 GPU；保留失败证据后，仅放行该 CPU 句柄的 r2 审计通过，正式重试仍0。全部新缓存/临时证据保留；旧包、旧回执不改。

请分析端验收本次有限工程预检并关闭 P10_A_NATIVE_PREFLIGHT_V3。未用额度不复用；这不是完整 episode 成功率、P/V 数值或 MT50 性能证据。不自动进入其他阶段。
