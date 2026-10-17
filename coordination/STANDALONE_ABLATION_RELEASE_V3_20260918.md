# Standalone READY v3：最终工程绑定，直接执行

2026-09-18 UTC，分析端。

采用preparation/handoff_v3/future_ready_fields.json的完整字段。原TASK、pending及全部科学契约保持不变；本次只绑定最终CPU与engine/test两文件的活动计数增强。前两版READY均未产生运行freeze或模型/仿真调用，保留历史。

CPU v5：145 passed、0失败/错误/跳过，22文件before=after=current；seal 0244e95c3c564678f407666f27f751ddb6c8b846d621745be475bfbdb286c18e。

独立窄审PASS：新增代理只记录native_action活动，正常采样、梯度、种子及P/D/V的1/2/2采样语义未变；覆盖采样前、采样中、采样后校验异常及中断，记录已经启动的采样，失败停止、不输出候选。此前异常日志建议已处理，不再重复修订或测试。

- engine SHA：73b2a0758cf5e281ff5ec5288ae747abf6bd6c3181aa011e00a22307bd18adaf。
- test_engine SHA：e4883fc6d765e674e1965e38ceddbaf5628b89b67f738184e6eea7d65568a8cb。

运行权限只有standalone_preflight与standalone_formal：固定50次技术预检；同一冻结配置的完整预检审计passed后，直接唯一正式波次，计划1274次；最后全量只读审计和统计。repair锁定，无自动失败重试，生成或配对技术异常须停止回报。

新预算上限1500sim/0opt，carry-in48183sim/51200opt，累计最多49683sim。原100源、98cut+2common、每任务20初态、4后缀、A4000、三solo-R主比较、源bootstrap及家族区间不变。所有30次预检旧消息作废。

旧matching文字仅描述封存参照及固定数值参数；新正式入口使用solo_rule和bank_mode=solo，不生成其他方向，不读取其容量作为生产输入。

执行端以当前READY实际版本、精确绑定及本决定为准；旧排队消息不构成继续工程修改或重复运行的指令。核验通过后立即独立freeze并通过lifecycle运行，不再等待用户或分析端重复许可。阶段技术通过即可继续下一已释放阶段，不需要另发READY。

已揭晓held队列的结构消融定位不变，正式全100完成前不读新汇总成功率。旧native10所有封存只读，整波退出恢复8卡holder。未新增论文赢家选择、重训或调参权限。
