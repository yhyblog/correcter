# Batch3 独立范围与存储风险接受

本分析决定只适用于 `P11_A_COMMON_POOL_BATCH3_V1` 固定八个A/train0/cut5新父源，并发2、每parent最多15个顺序cold分支。具体冻结身份见release及任务书。它不延续旧批计算机会，也不代表全500源quota、B计算、训练或评测权限。

依据Batch1/2并发2已完成的运行证据，接受本批 `bounded_batch3` 已披露的有限监测缺口：项目quota与独占预留未知；shared HF/native范围外写入、unlinked文件、监测间超调、容器内存限、RSS/VRAM及实际IO未知。保留5秒私有已链接cache监测、受控writer/log上限、身份拒绝与容量准入；这些不是全系统原子quota。128GiB RAM仅规划，不能冒充实测或硬限制。

整批准入93,415,604,224B，另512MiB free floor，总即时可用至少93,952,475,136B及564096inode。8parent×11,609,841,664B与512MiB批辅助分别约束。真实入口在NVML/holder之前检查即时容量，无新增容量探针。容量或身份拒绝后停止，不删除、换源/seed、变更并发或重试；新产物保留至明确的后续清理决定。

116数值caps和独立scheduler aux仅限本批满120attempt：3624sample/36240flow/36000control/36120obs，6240reset/12480reset_model/3127800初始化物理子步/9600初始化forward。door-lock静态额外520/attempt×15=7800已计入；同hook在Batch2 box-close通过计量不证明door-lock实际资格。新八任务在计划parent中通过原闭包/MJB门；physical_equality_proven仍null。

保存的Batch1 16143.591s、Batch2 15691.137s、cold模型载入与host时序只用于规划；不承诺本批工期，不作GPU秒、实际IO或并发线性加速结论。满120预算不因前批提前终局比例而缩小。输出最终inode去重大小不代表全局峰值。

preparation900、handoff300、child1800+30、parent27900、reserved111900+30、publication300、恢复观察120秒分别计量；锁等待、最终清理、端到端及精确GPU秒上界未知。单次command/claim，失败费用保留，未入额度不复用。全部正式后代退出和数据/成本发布后才统一恢复8holder，不恢复idle子集，不终止无关进程。

本批风险接受仅由本次新release引用。旧Batch1/2风险合同、原CPU包、旧回执、历史release和有效数据索引不改。
