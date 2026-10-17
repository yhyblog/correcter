# 校准入口独立审查

结论：准备审查通过，无阻断；可在精确READY与新独立freeze闭合后条件放行。

- 固定A4000/post；原100主槽、每任务20、每源2后缀及200个有序备用槽保持。采集五个未加门物理臂，不复用dev状态或a0。
- calibration上限1200仿真、0优化。备用capture仅使用既有technical_reserve，共享1200上限；需独立calibration_initialization_replacements scope。替补限首次动作前初始化失败或重复物理初态。
- 实际prepare→validator→runner→collector接线及首分支前bank检查存在。禁held、训练、事后换源和自动重试/推进。
- 完整100源通过实际审计后，仅按mean(post−replan)>0提出全局post，否则同a0重规划。Q、CI、任务不参与；缺失阻止proposal；统计函数不写最终选择seal。
- 79项合成CPU及shell检查通过；9份受测文件before/after/current身份一致。新freeze覆盖绝对、相对、嵌套授权引用；拒绝冻结live增长账本/scene。场景只绑定原700行前缀，实际去重需运行时完成。

下一READY须精确绑定future_ready_fields两块、两个scope、本审查及v2 CPU，并使用封存budget snapshot。cal结果与held均未读取；本审查没有模型调用、测试重跑或仿真。

完整证据：[calibration_entry_review.json](calibration_entry_review.json)。
