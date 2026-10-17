# Batch2 独立范围与存储风险接受

分析决定时间：2026-09-20T20:56:00.593331+00:00。只适用于 `P11_A_COMMON_POOL_BATCH2_V1` 的固定8个A/train0/cut5新父源，并发2、每parent最多15顺序cold分支。不是Batch1权限延续，不代表全500源quota，也不授权B、训练或评测。

单独接受 `bounded_batch2` 已披露监测缺口：项目quota和独占预留未知；shared HF/native路径外写入、unlinked文件、监测间超调、容器内存限、RSS/VRAM峰值及实际IO未知。并发2沿用已完成Batch1的运行范围；128GiB RAM只作规划，不是实测或硬限制。保留5秒私有已链接cache监测、受控writer/log上限与新入口容量检查，不将其称作全系统原子quota。

本批准入93,415,604,224B，加512MiB floor后即时可用至少93,952,475,136B及564096 inode。真实入口在NVML/holder之前重新核验，不另加容量探针。容量或身份门失败即停；不删数据、换seed、替换源、扩缩并发或自动重试。8parent×11,609,841,664B与512MiB批辅助独立约束。新产物留待后续明确清理决定。

116数值caps+调度aux仅限本批：120attempt/3624sample/36240flow/36000control/36120obs，6240reset/12480reset_model/3127800初始化物理子步/12720初始化forward。box-close每attempt额外520直接mj_step子步合计7800已计入；嵌套do_simulation不双计。50任务静态报价通过不代表全50实测或普遍物理等价，新8的实际资格在预定parent中通过原门。

旧批16143.591s、106cold载入、124.80s平均load及46.45%child host比例只作为报价观察，不作本批工期、GPU秒、实际IO或并发线性收益。满120分支的已知尺寸逻辑校验读取小计1,148,665,724,481B仍有每遍116个未知尺寸引用，总严格上界null；不等于实际文件系统读取流量。

preparation900、handoff300、child1800+30、parent27900、reserved111900+30、publication300、恢复观察120秒分别约束自己的阶段；锁等待、最终清理、完整端到端与精确GPU秒上界未知。单次command/claim，所有已进入费用与失败保留、余量不复用。整波所有正式后代退出并完成数据/成本发布后才统一恢复8holder；不得杀无关进程。
