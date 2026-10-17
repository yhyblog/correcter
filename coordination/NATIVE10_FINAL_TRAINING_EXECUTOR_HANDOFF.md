最终600源A/B训练交接（2026-09-17；工作流20260916）

最终训练及独立只读审计均已完成。A/B各四成员、每成员4000更新，合计32000新增优化、0新增仿真；14组固定ensemble检查点/56个成员检查点齐全。旧封存未修改。

**唯一选模：A4000。** 原dev100源×4后缀的候选银行选择从a0 257/400（64.25%）到275/400（68.75%），净+4.50pp，救回23/损害5；保留95cut及5共同结局、每任务20源的完整100分母。此数值是开发候选银行选模代理，不是实际flow纠偏部署，也不是独立成功验证。

排序理由：A3200、A4000、B200均+4.50pp；A两项损害5少于B200的6，优先A。A4000 gain MSE 0.056607967428307496小于A3200的0.05809580086090618，因此选A4000；更早检查点/最后优先B的平局规则未触发。未因结果临时改变规则。

| 路径/步数 | 代理净收益pp | 救回/损害 | gain MSE |
| --- | ---: | ---: | ---: |
| A/200 | +4.00 | 23/7 | 0.0519881770 |
| A/400 | +4.00 | 23/7 | 0.0519053472 |
| A/800 | +0.50 | 10/8 | 0.0534671843 |
| A/1600 | -2.00 | 4/12 | 0.0599953189 |
| A/2400 | +1.25 | 12/7 | 0.0600073969 |
| A/3200 | +4.50 | 23/5 | 0.0580958009 |
| A/4000 | +4.50 | 23/5 | 0.0566079674 |
| B/200 | +4.50 | 24/6 | 0.0534971644 |
| B/400 | +3.75 | 23/8 | 0.0529876116 |
| B/800 | +3.75 | 24/9 | 0.0528372748 |
| B/1600 | +2.75 | 22/11 | 0.0523174275 |
| B/2400 | +1.50 | 17/11 | 0.0515105587 |
| B/3200 | +1.00 | 21/17 | 0.0513686807 |
| B/4000 | +0.00 | 18/18 | 0.0519254613 |

A学习率1e-4、仅residual/advantage 2529参数可训练；B学习率3e-4、完整小critic MLP 7058参数可训练。AdamW wd=.01、clip=1、batch=32完整源，BCE/相对a0/正反差损失1/1/.5。训练均从同一真实预检的PCA、八初态、source bootstrap和minibatch计划恢复；没有重拟PCA或重新初始化，600训练源等权，两轮生成critic/真实protocol身份保留。

独立审计确认32000个update身份、8×4000计数、全部4000×32实际采样序列与封存计划一致，所有声明冻结的参数和预处理buffer逐字节不变，4个selected导出等于被选检查点。原dev100规则独立NumPy重聚合一致；浮点归约最大差1.3877787807814457e-17仅属原标量审计口径，未修改canonical数值容差或排序键。

所选A4000的真实重载审计覆盖95有效dev源、四成员13候选概率及槽0/11成员和ensemble梯度，canonical同shape严格逐位通过。完成后的独立审计只核封存重载证据及CPU state_dict，没有再次实例化模型、forward或重算梯度。

执行UTC 2026-09-17T00:12:56.556095+00:00 → 2026-09-17T00:37:34.484703+00:00。含入口核验墙钟1477.93秒（24.63分钟），训练管线墙钟1469.44秒、CPU1304.35秒，峰值RSS1.791GiB；独立审计4.90秒。runtime仍lerobot/torch2.7.1+cu126/NumPy2.2.6/CPU float32两线程，8卡holder保留。

资源累计42,874/50,000 simulator attempts、51,200/51,200 optimizer updates，technical reserve消耗0。没有失败、重试、新仿真或下一阶段自动启动。当前policy2/cal/held仍待分析端阶段决定。

- 训练配置：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_fit_protocols/final_fit_v1/config.json`，SHA `ba467bf5da9b0b3e1eab4b8dc1a2b7b5a85992440c4689b2720d8774a8d84779`；freeze `5798328ea34cef178bd6dde64ffc83a37613d1e6e4cced853b32277963a19db3`。
- READY v10 SHA `e44b37c380d50ce1bf88acc9f6c832fae1367b12fae0b0074076b269cce4938f`；specification `08891c3ee6feb71aa41a8cfa7cb0fbed61930e16eb8938cf5bfeff1dd24ad946`。
- 模型：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/models/final/final_fit_v1`；seal `864c00cfa1cfcbcc8736a898ab22e5afa821f15afbe2b8dc687f7731f2eea83e`；result SHA `ff4d7c11d81fb0c01617458f41c8e2d58645b3694ca0bc77ec56e56f3c35a1fd`。
- 唯一selected：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/models/final/final_fit_v1/selected`；seal `f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a`；四成员权重SHA详见同目录ranking.json与交接summary。
- 独立审计：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_training_audits/final_fit_v1`；seal `afa80b5e00286114be778607e1bf012654eaa8e3d1aa92e4c7dbcaac8b148809`；audit SHA `38265eee5669fcc586b6393d97d0dc5210afd30dad02be7e862937e6b76015ba`。
- 执行receipt：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_fit_execution/fit/final_fit_v1`；seal `9b57ad570eaa078384c247097f4d89511359f4f7bb62763ec5ab7a2bad2efa94`。
- 当前账本SHA `ef493c95d51a77eae82cdec142f63d0f63cb6805a9b676588274684e40213bee`；新update号码62075..94074，仿真增量0。
- 结构化交接与selected绑定：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_model_handoffs/final_fit_v1`。

结论仅为既定训练和技术审计完成；真实纠偏相对仅重规划能否再提升约5个百分点，仍须下一阶段真实配对策略测评判断。
