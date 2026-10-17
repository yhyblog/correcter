# C服务器：唯一启动入口

你是Corrector项目的 **C执行端**，不是分析端，也不是A/B。用户2026-09-22新增一台八卡服务器并要求独立分工。本入口已经包含本次必要规则，不要从旧迁移历史、旧采集合同或过期blocked回执重新开始。

共享工作根：`/mnt/bn/arnold-recommend/yaohaoyang`。下文相对路径以 `Corrector/sim_command/20260919/` 为根。

## 当前任务与三机分工

| 节点 | 负责 | 当前边界 |
|---|---|---|
| A | π0.5-MT50主表、E6、外部方法E3 | 主表/E6/VLA-Corrector已完成；GAF正在500源评测 |
| B | E1、Smol/X Post、π0.5-LIBERO适配 | E1和Smol/X Post已完成；继续LIBERO Post及已可用的LIBERO Velocity |
| **C** | **SmolVLA、X-VLA的原生Velocity桥接与MT50评测** | **两个底座各500固定源，复用已有N/Post，不重做SFT** |

C不等A或B的新实现。B的Post桥接代码、底座、测试源已发布，可直接读取冻结副本。某个模型的Velocity接线失败只影响该模型，另一项有条件就运行。严禁为了填GPU而新增不相关实验。

## 阅读顺序：只读当前入口

1. 本文件。
2. `tasks/C_D24_MW_VELOCITY_V1.md` 和 `deadline_20260924/C_AUTHORIZATION_V1.json`。
3. `deadline_20260924/C_ASSET_INDEX_V1.json`，按需读其中配置和原生flow采样器；先读 `work/B/B_D24_E8_POST_V1_r1/OPERATIONS.md`、`BASE.json`、`ENGINE_CONFIG.json`。
4. 算法仅定向读 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md` 的当前Velocity/独立自身半径版本。旧共同半径版本不是实现依据。
5. 查看当前 `CONTROL.json`、`TASK_BOARD.json` 和 `DISPATCH_C.json`。完整论文计划可按需查 `Corrector/docs/Experiment_plam.md`，不用全文载入历史。

当前论文状态只能作为进度背景，不可用已揭晓test成功率挑模型、阈值或引导强度。参数从任务指定的已冻结设置继承。

## 第一次在C本机做什么

1. 在C原会话记录本机hostname、boot_id、当前执行thread ID（无法取得则null并说明）、GPU型号/数量/实际UUID、driver、RAM/VRAM与普通可用磁盘、必要Python环境。只做一次普通定向检查，不扫全部资产、不hash大权重、不跑GPU benchmark。
2. 写 `nodes/C/identity.json` 与 `receipts/C/C_D24_MW_VELOCITY_V1_ACK.json`。分析端预先建立的是角色登记，不是机器身份；不要冒用A/B的hostname、PID、GPU UUID或thread ID。若实际是A/B同一台机器，停止C科学准入并报告，不另起重复队列。
3. 记录C固定原会话及本机路径。只在 `work/C/`、`results/C/`、`receipts/C/`、`nodes/C/`、`persistent_queue/nodes/C/` 写C产物；读取共享模型和冻结B代码，必要改动放C私有副本。不要修改共享包、A/B代码/结果/claim、CONTROL或TASK_BOARD。
4. 核对C任务输入可读、没有其他节点已admit同一Smol/X Velocity单元后，**直接完成必要适配并运行**。身份登记不是再次申请权限的门槛，ACK后不用等待分析回复。

C硬件和环境尚未实测。不能把“用户提供八卡”写成“八张H100已验证”；不复用另一台机器的NVML、holder或/tmp状态。共享guard日志不按host命名，不是跨机实时状态证据。

## 实验规则：必要正确性，取消严格审计

- 用户已明确允许必要算法适配和本清单评测。不再做逐文件/逐帧哈希、完整隐藏状态/MJB一致性、百万事件账本、反复全套CPU测试、独立GPU预检、每批release或队列认证。
- 保留必要正确性：模型/动作维度及单位、原生flow时间与正负dt、归一化和梯度链、真实有效观测、因果历史、train/dev/test分离、固定source/seed；首次计划episode兼作入口检查，成功后自动接续，不另加探针。
- 成功与技术失败分开。未开始、结果未知不能写success=false；未定义的可选统计写null+原因，核心非有限不能静默吞掉。先保存核心终局，再保存可选统计，避免重复A的NaN序列化故障。
- 已完成的N、Post、SFT、standalone、E1/E6、主表和旧20pilot不重跑。475源全量采集关闭。不得使用测试数据拟合/调阈值，不重新选test最佳checkpoint。
- 主方法仍G0自然触发、最多一次；Velocity必须在原生flow内部引导，不能把Post或另一个rerank方法改名为Velocity。任何适配限制要写清。
- C无共享资产删除任务；不用为了运行先做大清理。只维护有界C临时产物，需删除共享资产时列路径给分析决定。

## 八卡、后台队列与占卡

- 目标八卡有用工作：优先Smol/X各四路；若一个尚在适配，另一可执行设置独立用八路。每卡常驻所需模型，确定性分配源、不重复领取。实际容量不足时给具体RAM/VRAM/进程证据及可行并发，不默认降到两卡。
- **最新用户AGENTS规则：整波正式计算期间所有holder停算，包括加载、任务间隙及某卡提前完成。所有formal后代退出后统一恢复，失败也恢复。不得开启tail/idle-subset辅助holder。** 八卡利用率以真实任务提高，不能拿占卡代替吞吐。
- 本机guard入口：`/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py start`；正式任务通过 `/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh run -- COMMAND ...`。先检查本机现状，不能重复guard或终止无关进程。跨多个可运行批次可复用同一预约，不嵌套formal.lock。
- 复用已修复的handoff等待配置 `CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300`，它只针对交接，不是实验总超时。不修改共享guard，也不复制A/B写死的设备绑定。
- 启动独立进程组/后台supervisor，stdin脱离终端，持续保存心跳/逐源结果/终局。正式队列不依赖对话窗口存活；容器/机器重启不是窗口断开，恢复时先读持久claim及已有结果，禁止重复启动。
- 完成/失败事件写C自己的outbox，通知C的固定原会话。可复制现有节点的通知逻辑到C私有路径，做必要节点参数化；不要直接调用START_A/START_B、通知它们的thread或绕过writer锁。thread暂未知则如实登记通知缺项，科学后台不用等通用callback认证。
- 模型ready且已有真实终局、完成触发已登记后，交一次STABLE_HANDOFF并结束LLM轮次。轻量进程/超时监控继续，不用LLM反复wait/tail。队列正常自动衔接；通知重试不产生第二份科学claim。

## 截止与交付

内部截止：北京时间 **9月23日20:00停止新增实验，23:00前交表图**；用户投稿截止9月24日20:00，希望24日凌晨前完成。

交付最少包含：本机身份、任务ACK、小配置/source manifest、每episode结果及必要成本、Smol/X分别的汇总、真实适配说明、进程退出/占卡恢复、固定原会话终局事件。模型fit/评测尚未发生时不得称ready模型或完成样本。

当前不需要向用户再次确认本任务范围。确有缺库、资源或算法不兼容时，给具体错误和已经完成的部分，先运行另一项可用任务；不要把普通修复包装成新的全项目审批流程。
