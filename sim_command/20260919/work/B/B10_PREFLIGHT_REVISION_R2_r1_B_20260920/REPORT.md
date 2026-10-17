# B10_PREFLIGHT_REVISION_R2：CPU 修订完成

| 项目 | 修订结果 |
|---|---|
| GPU身份 | 本机8×H100；选择UUID `GPU-4143840e-6c2e-d4c4-8c60-4005cfa1f917`；driver `535.161.08`、型号、PCI逐项核对 |
| 可见设备 | 导入torch前设完整UUID为CUDA_VISIBLE_DEVICES，逻辑cuda:0仅指该卡；主机序号变化不导致换卡 |
| 授权 | unique active release id/path/task、released状态、有效期/关闭历史、board owner/revision/ready或running、host、单机wave全部一致 |
| 预算/文件 | release caps=配置；CONTROL全局+单任务caps覆盖；code/config/input/lifecycle SHA核验；每次实际调用前重查元数据 |
| 有限预检 | 1初始化、2 GPU forward、仿真/VLA/更新0、180+20秒、重试0；synthetic token不代表真实特征或任务效果 |
| CPU验证 | 9项测试通过，36条登记拒绝子例；正确冻结提案的元数据/文件/保存GPU身份组合检查通过；无torch/numpy导入 |
| 存储附项 | 27文件/11父路径，18013109184逻辑bytes；元数据27/27吻合；本机50进程无fd/maps/下载恢复命中，权限缺口0 |

本轮仅CPU代码/配置修订、文件核验和明确授权的只读GPU身份查询。模型初始化/推理、仿真、训练、正式GPU秒、删除均0。沙箱首次nvidia-smi驱动查询失败；只读升级查询成功，未据沙箱失败推断主机驱动不可用。

代码/config/命令在 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_PREFLIGHT_REVISION_R2_r1_B_20260920`，不可变镜像在 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B10_PREFLIGHT_REVISION_R2/B10_PREFLIGHT_REVISION_R2_r1_B_20260920`。原B10 r1快照及回执不变。

- 无模型校验：`bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_PREFLIGHT_REVISION_R2_r1_B_20260920/commands/verify_release.sh <分析端绝对release路径>`。
- 后续正式命令：`bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_PREFLIGHT_REVISION_R2_r1_B_20260920/commands/run_preflight.sh <分析端绝对release路径>`；旧P00已确认拒绝，不写claim、不加载模型。
- config SHA：`4dd56601c7995946dc77c2891e4aff36b31eff51a05586ab77804bc1eabb9d58`；code manifest SHA：`14f209c2fd49d5d6dd30fbd9803f02fb64196a248bfbe95a03f9b89294d26145`。
- `release_template.json` SHA：`7ed51f603bf29e36cbcac62f14cf119b82fa9844222ba5ccf99b01509cde1448`，status=draft、时间null；`CONTROL_REQUIRED.json`明确未来B独立预检的task/board/active字段和caps。当前未发布计算release。
- Python使用既有`.miniforge3/envs/lerobot/bin/python`；授权/身份路径只有标准库。模型/source/输入沿用锁定旧LVM；未改共享环境。

完整命令仍经本机occupancy lifecycle暂停全部8卡holder并在退出含失败后恢复。当前先A后B的独立wave，不新增联合屏障。标明的200秒GPU作业上界含kill grace，交接/恢复耗时另记；完整命令两次nvidia-smi校验不当作CUDA模型调用。

存储回执 `receipts/B/STORAGE_DEPENDENCY_REVIEW_V1.json` 已发布：B当前/计划任务不依赖27个候选；若需求变化，先向分析端报告再读取。对照A冻结SHA来源，只复核精确路径/类型/大小/mtime，未重复哈希18GB，未把跨主机inode/device当一致性要求。仅本机时点证据；分析端决定，A删除前复核并执行，B未删除。Smol050000、X完整底座/初始化及全部小元数据/沿革继续保留。

建议分析端验收本包后按CONTROL_REQUIRED发布B单机两forward预检。当前CONTROL revision38，正式模型/仿真/训练上限仍0；准备完成不代表GPU预检通过。
