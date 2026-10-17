# P20 / A20 / B20 / B21：正式评测合同（待冻结）

本文件列必填项，不是READY。当前不包含足以运行的源清单或预算。

分析端在release中填：
- campaign/task/revision、owner hostname、parent episode/source shard列表；
- 数据split与SHA、代码/环境/配置/checkpoint身份；
- E4五H三臂＋H10 R；E3两个外部方法H10；E1四损失×两算子×训练seed；E6两触发；
- 物理源数、每源后缀数、总attempt和重试上限，训练及推理调用分别计数；
- 预热/计时子集、硬件、并发；主统计比较与结局定义；
- 明确依赖、失败处理、恢复方式及后续暂停/停止边界。

执行端只运行自己shard的全部方法。每个正式GPU波次使用本机lifecycle；release列wave_id及参与主机，联合波次通过完成屏障维持预约，所有参与主机的holder停算到整波全部任务退出（含失败）。不因单GPU或单主机提前完成开启holder。

完成：逐源表、事件表、数据/模型/代码SHA、实际资源、技术失败清单、完整输出manifest、最终JSON与最多约150行报告。没有可审计产物的“已完成”不通过验收。
