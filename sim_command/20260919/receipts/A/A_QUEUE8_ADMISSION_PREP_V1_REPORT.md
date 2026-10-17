同一 revision1 的延迟派单已核对，P00 与固定NEXT8 SHA均匹配，原ACK/RESULT已于14:17/15:59 UTC保存。本次补齐缺少的短REPORT，原回执保留。

当前queue CONTROL14、TASK_BOARD74已转D24。remaining_common_pool_collection_enabled=false；本任务条目明确“Reusable implementation only; Full collector migration deferred”。Batch3已验收关闭，当前真实八卡为D24 test主评测，不是这8个train0/cut5采集parent。没有重启旧阶段或重复命令/claim。

已有RESOURCE_ADMISSION保留requested=8、无默认退回2：8×64GiB＋16GiB=528GiB仅工程预留；历史主机余量支持该预留，但实际parent峰值、cgroup硬限/current、VRAM峰值、FUSE后端吞吐、page cache与project quota仍unknown，supported_max=null。旧资源记录3组CPU/OS与1次GPU只读快照；本次新增0。容量按93,952,475,136B和564096 inode报价；120 cold权重逻辑读取约1.122TB，已知校验逻辑约1.148TB，均非共享物理IO上界或线性加速保证。

8源/UUID/116预算原计划字节保留，初始化物理子步3,120,000，不计door-lock额外。独立首8采集PROPOSAL/RUNTIME_MANIFEST/正式release仍未发布，通用包未部署；不将资源准备说成完整可执行采集包。已有占卡适配器CPU验证及D24实际入口复用分别有回执，但8个常驻评测worker不证明120 cold分支并发的资源峰值。

遵循后续D24决定，不重新采样OS/GPU、不重做runner或首8配置冻结、不创建正式command/claim；已授权D24链继续后台。若后续恢复共同池采集，仍需其独立计算授权与当时资源准入，不能用此旧P00或D24评测许可恢复采集。本次无需B或新审批链。
