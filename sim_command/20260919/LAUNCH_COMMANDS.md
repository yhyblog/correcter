# 启动另一台服务器的Codex

如果另一台服务器已经打开Codex窗口，直接在那个窗口发送：

    你是Corrector服务器B执行端。请读取
    /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/START_SERVER_B.md，
    按当前CONTROL和B00任务书立即完成盘点，写共享回执。不要重复启动第二个B执行器，
    不运行未放行的GPU训练/推理/仿真；完成后检查新的B任务，没有则待命。

如果需要从另一台服务器终端新开Codex：

    codex -C /mnt/bn/arnold-recommend/yaohaoyang '请读取 /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/START_SERVER_B.md。你是服务器B执行端，立即按B00执行资产与环境盘点，写共享回执，再按CONTROL和任务板处理后续已放行任务。'

二选一，不同时启动两个B。命令使用本机已核对的Codex CLI参数；如果B版本不同，先用codex --help确认-C和初始prompt支持，不添加跳过审批/沙箱选项。

后续在同一B窗口继续：

    继续检查 /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919
    的CONTROL.json与TASK_BOARD.json，执行已放行且依赖满足的B任务；先核对现有回执和进程，避免重复运行。

A端已由分析端通过本机codex queue投递A00。A投递记录见DISPATCH_A.json；queue成功不等于A00完成，完成状态看receipts/A/A00_RESULT.json。

不需要把分析对话完整历史粘到B，也不需要用B连接A会话。任务、协议、数据身份和回执均通过共享目录交接。
