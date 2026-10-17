# 校准结果独立统计复核

结论：通过。封存逐源结局可完整重建100源×5臂×2后缀；预登记全局规则要求启用Post。此文件只复核proposal，不封存选择、不授权held。

## 分母与总体结果

每任务20源；96源有合法报警，4源无报警（2成功、2失败），共同结局在五臂保留。技术缺失0；200个逻辑结局/臂对应100个独立源。已独立复现全部五臂计数、七比较、五任务表及七个源bootstrap区间。

|方法|成功数/200|成功率|
|---|---:|---:|
|continue_native10|92|46.0%|
|alarm_replan10|119|59.5%|
|velocity|122|61.0%|
|direct|116|58.0%|
|post|133|66.5%|

|比较|增益pp [95%CI]|救/害|正/负/零源|
|---|---:|---:|---:|
|alarm_replan10_minus_continue_native10|+13.50 [+6.50, +20.50]|35/8|21/6/73|
|velocity_minus_alarm_replan10|+1.50 [-3.00, +6.50]|9/6|5/5/90|
|direct_minus_alarm_replan10|-1.50 [-7.00, +3.50]|8/11|5/6/89|
|post_minus_alarm_replan10|+7.00 [+3.00, +12.00]|15/1|9/0/91|
|velocity_minus_continue_native10|+15.00 [+8.50, +21.50]|35/5|21/4/75|
|direct_minus_continue_native10|+12.00 [+4.00, +20.00]|36/12|22/7/71|
|post_minus_continue_native10|+20.50 [+13.50, +27.50]|43/2|25/2/73|

## 任务分解

每任务各40个逻辑结局，以下为成功数。

|任务|normal|replan|velocity|direct|post|Post−replan净成功数|
|---|---:|---:|---:|---:|---:|---:|
|disassemble-v3|30|25|27|25|29|+4|
|pick-place-wall-v3|11|32|31|29|32|+0|
|shelf-place-v3|5|9|7|8|11|+2|
|stick-pull-v3|13|17|17|18|21|+4|
|stick-push-v3|33|36|40|36|40|+4|

Post净增14次成功分布在4个任务、9个正净收益源。wall任务净增0。Post存在1次配对损害，被同一源另一次救回抵消，因此“0负净收益源”不表示零损害。

## 选择规则与限制

完整100源等权均值为14/200=+7pp，严格大于0；proposal的`post_enabled_on_alarm=true`与原先登记公式完全一致。此判断未使用CI、Q、V/D排序或逐任务门控。无报警的4源差值均0并保留分母；不能使用96个报警源作为全局规则分母。

区间独立重算使用NumPy default_rng、seed=2026091622、10000次任务内整源有放回抽样、linear percentile 95%；任务顺序及源顺序沿封存记录。七比较未作多比较校正；仅2次后缀，不能估计可靠单源置信度。校准用于固定的二选一决策，仍不构成held独立成功。

## 输入与边界

- 主审计complete SHA `6e1568c11fc52d3f1cb1ce43e41f51be5b218faa8ddcab0fbc3183e090a70d25`。
- 主审计result SHA `454d323a64fe87516dcbf10c34435de6c58d1536d0cbb59dca1cfb1a2d55adc5`。
- 预登记方法文档SHA `bb8e6c7f7eb145337b25ba6c859bf456754eead33062989aefff0d06c3314fd8`。
- 本次读取已通过完整审计的逐源结局表，重新计算统计；没有重复轨迹审计。
- 新模型调用、仿真、优化、held读取均为0；未写选择seal。
- 机器可读复核：[calibration_result_review.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/calibration_result_review.json)，SHA `47b8d7c444eb47b26d90bdf5c7f2f187f0e98dfef84fd805e6e20cf7295e86cd`。
