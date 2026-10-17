# 首parent：共享计划引用与实际干预标志的最小修订

2026-09-20。A上一轮工程合同修订已验收其已完成部分；本轮不再改变科学设计、状态准入、模型、源seed或数值预算。旧CPU包和未授权V1/V2提案封存，真实计算仍为0。

## 共享计划的合法引用

normal在cut处只生成一次BANK，分支复用既有raw计划是既定采集协议。不能要求generated_chunk_ref一定处于本branch目录，这会使Q_a0的首个承诺步必然被拒绝。

observation_ref和next_observation_ref仍限当前物理episode目录并核SHA；本branch自产prefix/suffix计划仍走原校验。唯一外部计划例外是本次源已经核验的BANK白名单：绑定normal BANK精确路径/SHA、source_signature、parent_source_id、source_id、cut，逐条绑定plan_key、逻辑别名映射、实际path/realpath/format及raw50内容SHA/shape/dtype（50×4 float32，raw数据800B）。引用必须匹配本branch请求计划；路径或内容一致本身不够。fresh0/a0可合法引用同一个生成计划，但不复用Q-C10与G0-C5结局。

不放开任意normal目录、跨parent文件、未经核验的外部路径；不放松观测归属。选择核验共享引用而非复制整个BANK，不增加writer大数据副本。补实际load_bank所产生引用与真实publisher组合的CPU fixture，不重新实现另一套简化fake路径。

## 干预标志

intervened不得仅由namespace非normal推出。未到cut结束必须false；cut/状态检查未通过也不能冒充已执行修复。基于已有控制器实际介入/计划替换或承诺开始证据定义并保存，区分计划分支与真实执行。G0_old继续旧队列不应被描述为收益模型触发；采集用强制分支也不代表在线G0触发有效性。不为这个字段另增真实实验。

## 不可变接口交接

公共interface_v1、原sidecar_v1及已发布supplement_v1全部保持SHA。原supplement_v1 README将chunk也一概限定本episode的句子不适用于共享BANK，发布独立supplement_v2或明确SHA绑定的后继补充，指出仅该引用规则更新、其余聚合/私有成本语义继承。B按共享dispatch指向的最新补充做CPU消费；不能暗改旧READY/schema。沿用现有sidecar字段，若确需新字段先说明理由，不默认升公共schema。

## 已审阅的资源结论

116项数值/物理caps、453sample、4530flow、4500control、4515obs及全部timeout保持。分析接受单个计划parent的bounded_first_parent监测缺口：规划11,609,841,664B、另留512MiB、70,000可用inode；2GiB私有temp阈值、5秒/6000次/4096项目录监测。project quota和独占预留仍未知，statvfs不代表项目配额；shared HF/native/unlinked写入、监测/清理超调和真实RSS峰值未完整计量。这是有边界的一次运行风险判断，不是宣布全磁盘硬上界，也不是本次计算放行。

无需再证明第三方写入为0、移回RLIMIT_AS、申请平台quota、预分配大文件或另跑硬件探针。保持拒绝/失败退出和整组holder恢复规则。新增白名单/小索引如改变CPU SHA检查次数，在资源delta如实列出，不能暗增模型或仿真配额。

真实MJB/完整状态资格仍在同一已计划首parent内验证，失败留证停下，不换seed、不放松字段容差、不添加短GPU实验。
