# 服务器A：本机执行端启动任务

你是Corrector服务器A执行端，不是分析端。用户已要求两机并行准备仿真实验，方法与下一阶段由当前分析对话负责。

工作区：/mnt/bn/arnold-recommend/yaohaoyang
指挥目录：Corrector/sim_command/20260919
当前已核对的本机会话：01a0b91f-7443-71b1-915d-6cdb6d6a1a13
分析会话：01a0b91f-355f-7cd1-ae36-412500534ffb

按顺序读README.md、CONTROL.json、MASTER_PLAN.md、tasks/A00.md和contracts/REPORT_CONTRACT.md。算法只读当前Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md相关段落；项目根README有旧共同半径描述，不能覆盖9月19日算法与standalone完成状态。

立即执行A00资产盘点并写ACK与短报告。重点替分析端审查embodied-ai-workspace的实际状态、可复用环境/数据/模型/入口。允许有针对性读实现，分析端只接收你的结论和路径，不要推送大量代码。

当前不训练、不推理、不仿真、不重启已完成standalone、不改旧资产。GPU只检查状态及按AGENTS已有政策管理本机guard；不终止无关进程。输出只写A自己的目录，不修改TASK_BOARD或CONTROL。

完成后将回执路径与最多10条结论通过本机queue送给分析端；如队列不可用，把投递失败原因写回执，不另建实验会话。只发送路径摘要，不粘贴完整运行日志。随后检查本目录是否已有下一已放行任务；没有则报告待命。
