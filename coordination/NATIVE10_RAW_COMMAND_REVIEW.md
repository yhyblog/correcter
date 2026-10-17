# Native10 raw 命令锚点审查

日期：2026-09-16。只读代码/XML审查；未运行仿真或训练，未修改封存。

## 判断

**可以条件批准 P0 技术诊断。** `replan=raw_a0`、`corrected=raw_a0+可行delta` 保留正常命令语义，避免在重规划分支额外引入整体clamp。现有实现方向合理；本审查不是已完成物理等价验证的声明。P0应按以下不变量检查，主采集须待检查结果明确。

原MetaWorld Python层只显式clip XYZ，gripper raw传入`do_simulation`；但这不自动意味着raw gripper超过1会改变真实动力学。本机五任务对应XML的两个夹爪actuator均声明`ctrllimited=true, ctrlrange="-1 1"`。仍需读取实际加载model的限制与相关disable flags，并实测确认；不能仅凭XML或Python任一层下结论。

## 最小不变量

令`r=raw_a0`，`C(r)=clip(r,-1,1)`，`b=C(r)`，`delta`只由合法可行分量构造。

1. **零修正恒等**：replan和零delta输出保持raw a0逐位一致；tail `[10:]`不变；未修改坐标不因重算改变符号零。
2. **共享可行mask**：只在`1-|b|>=.05`的坐标修改；其余坐标delta严格为0。当前wrapper显式禁止`|r|>=1`修改，但`.95<|r|<1`的排除还依赖matcher，完整bank必须另审。
3. **表示一致**：实际执行差值`(r+delta)-r`等于用于评分/半径统计的delta，且`C(r+delta)=C(r)+delta`。候选评分须恰好对应这一C表示。
4. **正反对称**：正/反共享mask及对称可行半径，执行`r+delta`与`r-delta`；两侧均满足`C(r±delta)=C(r)±delta`，半半径确为同方向delta/2。不能各自clip后仍声称对称。
5. **分组半径**：在最终实际delta上检查XYZ/gripper RMS和L∞；raw命令可越界，但纠偏不能改动这些饱和分量。通道候选的零分量不得把其他候选的共同半径压成0。
6. **梯度链**：保留原ActionTransform的真实反归一化与clamp导数，不使用直通导数；flow梯度仍对相同T求导，post仍用`S²∇aR`。在远离边界的允许坐标做有限差分/解析目标检查；饱和坐标和mask外动作不能因后处理“恢复”出未记录的扰动。固定a0槽位和`R(a0)=0`继续检查。

`commands.py::preserve_raw_anchor`已做shape/finite、bounded base等于clip(raw)、tail不变、饱和坐标不改以及最终clip等于候选的检查；其实现不是把所有raw命令重新clip。P0需将这些条件扩展到真实bank和正反候选，不能只依赖合成单元样本。

## 物理等价检查与盲区判定

P0在相同恢复状态下，对有代表性的正/负饱和raw gripper及其clipped版本检查：

- 实际model的`actuator_ctrllimited`、`actuator_ctrlrange`以及是否禁用了control clamping；记录任务XML/模型身份。
- `qpos/qvel`、实际actuator force/广义执行力、接触和终止/成功标签，必要时连续若干控制步，尤其含接触阶段。
- **不要求`data.ctrl`原始记录相同**：raw输入记录本来可不同。比较的是限制生效后的物理状态和执行效果。

即便证明内部饱和等价，所有实际主臂仍按raw基线执行，不能因此偷偷改正常策略接口。训练与审计同时保存raw命令、critic表示、delta、饱和mask及实际范数。

若实际控制限制生效、上述表示不变量成立，clipped critic可以表示当前局部候选的有效动作，**没有仅因raw数值越界而阻塞P0的理由**。奖励中的raw-action数值差异与二值成功标签须分开记录，不能将reward差异自动等同动力学差异。

若相同clipped动作对应不同实际力/状态/成功标签，critic就把物理不同的动作合并了：即使同一source的饱和raw基准固定，其强度对XYZ/夹爪其他修正效果的交互仍可能不可见。此时暂停依赖该表示的大规模主采集/训练，先明确真实有效动作表示或加入缺失的raw基准信息；不得把不同raw动作仅按clipped数组去重。没有物理等价证据时也不得宣称已排除这一盲区。

## 文档修订与证据

应以新协议amendment明确raw锚点、C表示、mask、对称条件和P0检查，更新新阶段manifest/READY引用。它细化任务书“统一环境命令处理”的要求，也明确区别于旧实验的bounded前缀；原ACT-RECAP和旧Corrector封存均不改。不能将新raw执行当作旧实验算法的无条件逐位复现；旧anchor迁移检查仍按原协议运行。

代码证据：

- `Corrector/experiments/native10_training_20260916/commands.py`：raw锚点恢复与表示检查。
- `Corrector/experiments/native10_training_20260916/engine.py:102`：先以clipped表示生成/评分，再恢复raw锚点；native原生输出未作为主执行臂。
- `.miniforge3/envs/lerobot/lib/python3.12/site-packages/metaworld/sawyer_xyz_env.py:327`：XYZ clip；`:595`：raw gripper送入simulation。
- 同包`assets/sawyer_xyz/sawyer_assembly_peg.xml:23`、`sawyer_pick_place_wall_v3.xml:32`、`sawyer_shelf_placing.xml:26`、`sawyer_stick_obj.xml:24`：五任务所用夹爪actuator的XML限制。

