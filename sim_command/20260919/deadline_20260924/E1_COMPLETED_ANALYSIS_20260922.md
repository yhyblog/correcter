# E1最终消融：结果已齐，但Full优势未得到一致支持

来源：`results/B/B_D24_SPRINT_V1/r1/D24_E1_RENDER_REPAIR_r3/E1_COMPLETE_SUMMARY.md`及同目录JSON/CSV。48次拟合、12个ensemble、24格×50个五任务test源；旧80条有效记录保留，1120条修正记录接入，原1120条无效渲染剔除且保留。无未解决技术失败。不重训、不重跑。

| 损失 | Post成功率，三fit seed均值±样本SD | Velocity成功率，三fit seed均值±样本SD |
|---|---:|---:|
| L00：BCE | 69.33±2.31% | 62.67±2.31% |
| L10：+gain | 71.33±1.15% | 66.00±2.00% |
| L01：+pair | 70.67±1.15% | 63.33±3.06% |
| L11：Full | 68.67±3.06% | 65.33±1.15% |

Full相对BCE：Post −0.67个百分点、Velocity +2.67个百分点。Full相对+gain：Post −2.67、Velocity −0.67。当前不支持“完整损失在两种算子上一致优于消融项”；不能为了得到该结论追加测试选参或换主表模型。+gain的点估计最高也不等于已证明显著更优。

三个拟合seed共用50个测试初态，SD不是置信区间，150条结局不是150个独立初态。本表只支持固定训练条件下的五任务损失消融，不替代MT50主结果，B renderer与A主表renderer不同。

逐源数据已在汇总JSON的input_refs中提供；后续可按相同source_id、complete_training_seed、method配对统计，无需新实验。尚未在本文件给出显著性结论。全篇需收敛损失贡献表述；触发创新和完整方法有效性仍分别由E6和已有MT50主表回答。
