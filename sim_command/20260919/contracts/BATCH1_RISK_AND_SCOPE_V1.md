# Batch1：八父源有限运行范围与风险接受

分析决定时间：2026-09-20T15:10:47.252184+00:00。仅适用于 `P11_A_COMMON_POOL_BATCH1_V1`，不沿用单parent权限，也不代表500源整批quota。

固定8个预定A train父源，显式UUID/seed/path见proposal；并发固定2，每parent内部最多15个顺序cold子进程。不同parent可并行，同parent候选/repeat不跨GPU。其他45任务、B采集及任何训练评测不获授权。

接受本批 `bounded_batch1` 已披露限制：项目quota未知、没有独占磁盘预留；shared HF/native路径外写入、unlinked文件、监测间/清理超调未知；容器内存限、进程RSS/显存峰值、页缓存和实际共享IO未知。宿主MemAvailable约1.64TiB仅是CPU可见时点观察，不保证容器无限RAM。并发2按每worker64GiB规划共128GiB，是有限首次并行选择，不是实测峰值或不OOM保证。

本批准入93,415,604,224B，加512MiB floor后即时可用至少93,952,475,136B及564,096 inode。8份parent预算与512MiB批辅助独立封顶；Store/log硬限及5秒私有已链接cache监测沿用冻结实现。监测不是全系统原子quota。真实入口在NVML/holder之前重新核容量，写入/身份/清理/缺账本/全局停止等按冻结程序结束owned wave；所有正式进程退出前不能释放预约。不得删除原数据或临时降并发/换源来自动重试。

116数值caps与调度aux按proposal逐项冻结；最多120attempt/3624采样/36240flow/36000控制/36120观测。新task/cut55的MJB/full-state资格在各计划parent内判断，失败保留，无补源或额外探针。

口径修正：`IO_quote.input_hash_logical_bytes_upper`约1.148TB同时列116个尺寸unknown文件。分析只接受其为已知尺寸逻辑校验读取报价/小计，严格总上界为null；约1.122TBcheckpoint逻辑载入也不是实际磁盘/网络流量。4.82小时仅按已有72.29分钟父源和无争用作算术情景，不能当工期承诺或线性加速证据。无需重写旧CPU包；未来报告引用本解释。

handoff300、preparation900、branch1800+30、parent27900、reserved wave111900+30、publication300、restoration观察120秒分别约束其作用域。锁等待、强制清理/完整端到端上界、GPU计算秒上界均未知。固定一次command/claim，未进入额度作废，任何新波次另行授权。
