# 第二次开发五臂入口独立审查

结论：工程准备通过，无阻断项，可按既定条件放行一次测评。当前结论不代表真实候选、轨迹或成功率已验收。

- 实际 prepare → guard → runner 接线使用固定 A4000 四成员；原开发100源、每任务20初态、95 cut及5共同结局保持。
- 新bank由实际加载的A4000生成；首branch前检查原raw50 a0、初噪声、mask、tail、critic C(raw)及本轮V/D/P同幅。旧guided动作不复用，不新增Q门或半径选择。
- capture、替补、第六臂、优化记账均被入口及ledger拒绝。预期1995仿真，阶段上限2100、优化0；全波次由lifecycle管理。
- 41项合成CPU检查通过；11份受测代码前后及当前SHA一致，沿用旧六段核心动作/噪声/同幅/账本检查。未新增测试或模型调用。
- 放行后须以新READY生成独立inputs/config/freeze，绑定CPU证据和本审查；实际模型与bank身份仍由运行时逐源验收。cal/held仍锁定。

主统计限于本轮五臂内部配对；跨轮配对需另有完整实际等价证据。

完整证据：[round2_policy_entry_review.json](round2_policy_entry_review.json)。
