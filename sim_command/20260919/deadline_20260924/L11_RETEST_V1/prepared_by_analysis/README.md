# L11正式重测的科学单元清单

此目录仅为分析端从已有真实终局表生成的CPU清单，不启动计算，也不替代当前运行授权。执行端应消费自己的 `NEW_UNITS_A.jsonl`、`NEW_UNITS_B.jsonl` 或 `NEW_UNITS_C.jsonl`；文件按 Post 优先、Velocity 随后排列。GPU UUID、实际进程、分卡槽和容量必须由各节点本地绑定。

| 节点 | 新执行范围 | 新条数 |
|---|---|---:|
| A | π0.5 H10 multi剩余450×P/V；H30 multi 500×P/V；H10 once 500×P/V | 2900 |
| B | SmolVLA multi 500×P/V；π0.5 H20 multi 500×P/V；H50 Post multi 500 | 2500 |
| C | X-VLA multi 500×P/V；π0.5 H40 multi 500×P/V；H50 Velocity multi 500 | 2500 |

`REUSED_UNITS.jsonl` 包含 π0.5 H10 multi、L11、fit9101 的已有 Post 50条和 Velocity 50条，各37成功。这些单位与主表源的任务、环境种子、策略种子、ordinal及repeat一致，不重新执行。新7900加复用100，构成16格×500条；Post/Velocity各新增3950。

科学键按 `(model, source_id, method, mode, H, Q_loss, Q_fit_seed)` 唯一。新旧清单无交叉。同一 source_id 的 SmolVLA 与 X-VLA 是不同底座实验，不能相互去重。Smol/X源表没有repeat字段，故明确保存null及原因，原episode ordinal保留，不新增重复试验。

`H` 表示执行队列长度：原生Smol/X都执行K10，raw计划长度分别为50和30。π0.5保持原五H设置。各unit保留原CSV/数据行/RESULT引用；L01旧RESULT只用于确定原源和固定输入，不作为L11输出。新结果应写新的L11命名空间，原始失败、旧L01及消融数据都保留。

`ASSET_REFERENCES.json` 绑定三个底座已完成的 L11、fit9101、成员1041–1044，损失为 BCE + gain + 0.5pair。仅检查权重路径存在并引用既有SHA，没有重新读取或哈希权重。其余底座、D/G0、观测和动作单位、触发阈值、合法cut、C10、候选随机域及源种子均沿原本底座协议。LIBERO、N/R、外部方法、E6及完整消融不在新增清单内。

本轮是用户在观察先前结果后指定L11的配置修订，使用已揭晓的原测试源。记录该来源，不写成新未见测试集，也不覆盖原开发集选中L01的历史。

所有清单和引用由 `build_units.py` 生成，`SUMMARY.json` 提供分格计数。`MANIFEST.json` 只覆盖本次小型分析输出；不做历史海量文件审计。未创建实际claim或计算release。
