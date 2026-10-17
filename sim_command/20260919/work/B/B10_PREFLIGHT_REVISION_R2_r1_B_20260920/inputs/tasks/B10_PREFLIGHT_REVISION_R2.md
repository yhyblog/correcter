# B10 后续：补齐预检 GPU 绑定（CPU）

task_id=`B10_PREFLIGHT_REVISION_R2`，task_revision=1，owner=B。B10 r1 CPU 准备已验收；旧回执和代码快照不变。新产物另发版本，不运行 GPU 模型、仿真或训练。

审核确认两次 synthetic LVM forward 的预算、claim、超时与生命周期基本完整，但当前入口直接使用 `cuda:0`，没有 GPU UUID/driver 校验，也未设置明确的 `CUDA_VISIBLE_DEVICES`。请仅补：

1. 在本机只读核对实际 GPU UUID、型号和 driver，加入新版 release 模板；启动前校验，绑定可见设备，身份不符即在模型调用前拒绝。整个 B-only wave 仍暂停本机所有 holder 至退出。
2. 明确与 `CONTROL.active_compute_release_id` 一致的授权校验，同时要求 release.status=released、CONTROL 全局计数上限覆盖本次工作、当前 task/revision/owner/release 相符，避免另一节点/另一任务的全局 GPU 开关使草稿或旧 release 可执行。当前调度采用先 A 后 B 的独立预检，不要求实现联合屏障。
3. CPU 模拟正确/错误 host、UUID/driver、过期 release、预算/输入 SHA 等相关拒绝路径；不实际初始化 CUDA。只测此次变更必要项。
4. 维持1初始化、2 GPU forward、仿真/VLA/更新全部0、180+20秒、0重试；synthetic token 只验证旧 LVM 加载/API/有限性，不代表真实特征或任务效果。
5. 发布新代码/config/命令/release模板及 SHA，提供 `--verify-release-only` 或等价无模型验证命令和短差异回执。正式 GPU 运行仍等下一份专属 release。

写 `receipts/B/B10_PREFLIGHT_REVISION_R2_{ACK,REPORT,RESULT}` 对应 JSON/MD；只写本角色目录。

同时按[存储依赖定向核查](STORAGE_DEPENDENCY_REVIEW_V1.md)交 B 的无使用/恢复依赖证明或具体仍用路径。不要删除共享资产。
