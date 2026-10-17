# Native10 校准结果：分析结论

2026-09-17 UTC。固定A4000与开发阶段选定的post；100个新校准初态，每任务20个、每源2个配对后缀。96个合法cut、4个无报警共同结局；主审计技术缺失0、替补0。结果用于此前预登记的全局启用/停用选择，不是最终保留验证。

## 主要结果

| 方法 | 成功/200 | 成功率 | 相对replan增益及源级95%CI（pp） | 救回/损害 |
|---|---:|---:|---|---:|
| normal native10 | 92 | 46.0% | — | — |
| replan | 119 | 59.5% | — | — |
| velocity | 122 | 61.0% | +1.5 [-3.0, 6.5] | 9/6 |
| direct | 116 | 58.0% | -1.5 [-7.0, 3.5] | 8/11 |
| post | 133 | 66.5% | +7.0 [3.0, 12.0] | 15/1 |

post−replan的总配对成功差为14，100源等权均值为14/200=0.07，严格大于0。因此预登记规则唯一对应的建议是：**在首次合法报警时统一启用post；无报警继续normal native10。** 不增加Q门，不改模型或幅度，不根据其他方法的校准结果重新选主方法。

post相对normal为+20.5pp，其中replan贡献+13.5pp、纠偏额外贡献+7pp。统计区间按原任务分层整源bootstrap10000次、seed2026091622、percentile95/linear计算，未校正多比较。启用决定只使用预登记的均值正负，不使用CI。

## 收益分布与仍需保留的限制

| 任务（各20源、40结局/臂） | normal | replan | post | post净新增成功 |
|---|---:|---:|---:|---:|
| disassemble-v3 | 30 | 25 | 29 | +4 |
| pick-place-wall-v3 | 11 | 32 | 32 | 0 |
| shelf-place-v3 | 5 | 9 | 11 | +2 |
| stick-pull-v3 | 13 | 17 | 21 | +4 |
| stick-push-v3 | 33 | 36 | 40 | +4 |

收益分布于四项任务，不再像开发集那样16/17净增量集中于两项。post的正/负/零源为9/0/91，但仍有1次配对损害；源内正负抵消可以形成零净差，不能把“0个负源”写成“没有损害”。每源只有两个后缀，也不能据此断言91个零源上效果严格为零。

校准初态未用于训练或开发选模，这提供了比重复开发评测更有价值的支持；但本批承担最终全局开关选择，不能与尚未打开的held合并成独立验证结论。开发post +4.25pp与校准+7pp是不同初态集合上的结果，不代表校准期间模型继续改善；本阶段没有模型更新。

disassemble的post仍比normal少1次成功，说明部分纠偏收益来自补回中断损害。direct本批相对replan为负，velocity增益较小：当前证据支持既定post方向，不支持“flow内部注入普遍更好”的结论，也不足以唯一定位评分或flow机制。

## Q与部署定义

96个cut中，post平均预测增益11.28pp，实际条件增益7.29pp，平均高估约3.99pp；Pearson约0.135、Spearman约0.140，仅作描述。没有证据据此追加可靠的逐源Q接受门。全局启用规则不等于修好了critic概率校准。

当前策略应准确称为**固定A4000的matched-post**。冻结config要求生成velocity/direct/post/reverse/random，共同决定各通道可行半径；reverse/random/native输出保存但不新增物理仿真臂。最终held必须保留全部生成依赖、随机流、mask、共同半径和零组规则，不得改成单独post的原生幅度。

本批XYZ/gripper平均RMS约0.04246/0.08890，XYZ收缩68源、gripper收缩34源且零组5。无raw别名、clip碰撞或最终同幅失败。完整候选生成约1.303秒、不含恢复；恢复约1.058秒。post梯度约0.003485秒只是子步骤，不能作为当前完整部署成本。

## 完成、资源与下一阶段

本阶段1156sim=100capture+96bank+960branch，global46025sim/51200opt，reserve0；32worker、100唯一主槽及每任务20不同物理初态通过有界复核，旧700条scene前缀保留，与此前同任务train/dev无碰撞。8卡holder恢复。

下一步先作0仿真/0训练的最终选择封存，然后准备既定held100×4；held每任务20不同初态、五个原物理臂、最多2200常规attempt，替补共用原剩余技术储备。held的唯一主比较固定为post−replan，其他比较为次要。不开新方法、训练或参数搜索。

主审计：`outputs/native10_training_20260916/calibration_audits/calibration_v1`，seal `6e1568c11fc52d3f1cb1ce43e41f51be5b218faa8ddcab0fbc3183e090a70d25`，result `454d323a64fe87516dcbf10c34435de6c58d1536d0cbb59dca1cfb1a2d55adc5`。

诊断：`calibration_diagnostics/calibration_v1`，seal `c5687a459aef2a9b6aef3028e208318052089fdd8f875fb3e963852fa4e546f3`。

分析端资源/初态复核：`analysis/calibration_completion_review.json`，SHA `c23f636eb2980b50b2ce00128adc71e66e72d07e6f9ca27f32aba104950944a1`。逐源统计独立复核另见`analysis/calibration_result_review.json`，实际选择封存授权由后续READY绑定其真实通过产物。
