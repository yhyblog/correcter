# 最终选择入口窄范围复核

结论：通过，可单独发布 `calibration_selection_seal` 零资源权限；阻断项无。

- 实际入口先检查独立 scope，再精确绑定 pending、CPU、代码和已封存审计；仅写 metadata 与 seal，不调用模型、环境、PCA 或优化器。
- 固定 A4000 四成员，校准净 14/200 = +7pp 按预登记严格正增益规则统一启用 post；不使用 Q、CI 或任务路由重新选择。
- 主比较固定 post−replan；保留 velocity/direct/post/reverse/random 共同决定半径的完整过程，实际物理臂仍为五臂。
- 复用并核对 75+17 项通过的 CPU 日志与封存、11 个新文件前后及当前 SHA；未重跑。
- 当前 v12 拒绝选择与 held。选择输出需绑定实际 path、complete seal 和 result SHA；held 模板必须据此重建并取得独立授权，当前审查不放行 held。

范围：仅读入口及小元数据，不重复校准结局审计、不重新加载权重、不执行选择封存。完整证据见同名 JSON。
