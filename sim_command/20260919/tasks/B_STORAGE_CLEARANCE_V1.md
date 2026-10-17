# B：已有11项候选的最后一次定向使用核查

这是已放行 `B10_PREFLIGHT_REVISION_R2` 中存储附项的具体输入，不增加GPU/仿真/训练/删除权限。A已完成本机核查，见 `receipts/A/STORAGE_DEPENDENCY_REVIEW_V1.json`；分析登记见 `manifests/STORAGE_PAYLOAD_REVIEW_V1.json`。

候选限于原11个路径下的27个大文件：9个旧Smol checkpoint的权重/optimizer共18件，X旧下载8个range part＋1个incomplete。所有小配置、processor、RNG、日志、沿革保留；Smol050000和X完整底座保留。无需扩大扫描范围或重新哈希全部历史数据。

请在B本机只读确认：

1. B当前或已计划任务是否需要这27文件作输入、选模或恢复；若需要，列精确文件及原因。E8已锁定Smol050000，不做历史checkpoint sweep，不续旧100k队列。
2. 是否有本机可见进程正在打开、映射或写入这些候选，是否有活跃下载/恢复任务；报告检查UTC、可见范围和权限缺口。仅本机时点证据，不声称跨节点全局锁。
3. 核对共享路径与A给定候选身份；设备号/inode属于主机视角，不能要求B与A数值相同。存在身份变化或不明用途则指出，不替换近似路径。
4. 写 `receipts/B/STORAGE_DEPENDENCY_REVIEW_V1.json`，明确需要保留的文件、确认不需要的文件与仍未知项，并声明B后续任务不会打开候选，若需求改变先通知分析端。A为唯一共享删除执行者，B不删除。

分析端收到此回执后决定具体 delete/keep/defer。实际删除前A仍须复核身份和使用者；当前没有删除release。此核查不要求等待GPU预检，也不阻塞A已发布的独立原生预检。
