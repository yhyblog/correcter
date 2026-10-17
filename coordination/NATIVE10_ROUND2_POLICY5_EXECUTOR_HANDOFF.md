# 第二轮 A4000 五臂实际开发测评：执行交接

产出日期：2026-09-17；工作流标识：20260916。

本次结果：Post相对仅重规划 **+4.25个百分点**，源级95%区间 **[0.25, 8.75]个百分点**，接近用户约5个百分点目标；这仍是参与选模的开发集、未校正多比较结果，不能宣称独立验证成功。

主审计与独立重聚合均通过。下表报告本轮完整100个原开发源的真实结果；这批开发初态参与过选模，结果不能称为独立验证成功。报告不重新选critic、不自动挑纠偏赢家，也不启动下一阶段。

固定已选 A4000 四成员，原100个开发episode保留原source、cut及a0随机流。95个cut重新生成bank，五臂各4个配对后缀；5个无cut源广播原共同结局。整体每臂400个逻辑结局，实际1900个分支。

| 方法 | 成功/400 | 成功率 |
|---|---:|---:|
| normal native10 | 221 | 55.25% |
| replan | 257 | 64.25% |
| velocity | 270 | 67.50% |
| direct | 268 | 67.00% |
| post | 274 | 68.50% |

| 比较 | 增益pp | 源级95% CI（pp） | 救回/损害 | 正/负/零源 |
|---|---:|---|---:|---:|
| replan − normal native10 | +9.00 | [2.75, 15.50] | 52/16 | 18/8/74 |
| velocity − replan | +3.25 | [-0.50, 7.50] | 21/8 | 9/5/86 |
| direct − replan | +2.75 | [-1.25, 7.25] | 21/10 | 9/5/86 |
| post − replan | +4.25 | [0.25, 8.75] | 25/8 | 10/4/86 |
| velocity − normal native10 | +12.25 | [5.25, 19.50] | 62/13 | 20/7/73 |
| direct − normal native10 | +11.75 | [4.50, 19.00] | 64/17 | 21/6/73 |
| post − normal native10 | +13.25 | [6.25, 20.50] | 65/12 | 22/5/73 |

原主统计完整沿用：五任务内整源等权有放回bootstrap，10,000次，seed=2026091622，NumPy default_rng.choice，percentile95。源内4后缀始终配对，不能当作4个独立初态；七项区间未做多比较校正。

| 任务 | N | normal | replan | velocity | direct | post | V/D/P 相对replan pp |
|---|---:|---:|---:|---:|---:|---:|---|
| disassemble-v3 | 20 | 85.00% | 76.25% | 85.00% | 76.25% | 86.25% | +8.75/+0.00/+10.00 |
| pick-place-wall-v3 | 20 | 55.00% | 86.25% | 87.50% | 86.25% | 86.25% | +1.25/+0.00/+0.00 |
| shelf-place-v3 | 20 | 26.25% | 28.75% | 30.00% | 31.25% | 30.00% | +1.25/+2.50/+1.25 |
| stick-pull-v3 | 20 | 22.50% | 30.00% | 35.00% | 41.25% | 40.00% | +5.00/+11.25/+10.00 |
| stick-push-v3 | 20 | 87.50% | 100.00% | 100.00% | 100.00% | 100.00% | +0.00/+0.00/+0.00 |

| 分层 | 源数 | 每臂分母 | normal/replan/V/D/P成功数 |
|---|---:|---:|---|
| 有cut | 95 | 380 | 205/241/254/252/258 |
| 无cut共同结局 | 5 | 20 | 16/16/16/16/16 |

| 后缀repeat | normal | replan | velocity | direct | post |
|---|---:|---:|---:|---:|---:|
| 0 | 54/100 | 67/100 | 68/100 | 67/100 | 69/100 |
| 1 | 55/100 | 64/100 | 67/100 | 67/100 | 68/100 |
| 2 | 58/100 | 64/100 | 68/100 | 68/100 | 70/100 |
| 3 | 54/100 | 62/100 | 67/100 | 66/100 | 67/100 |

上述repeat分层仅用于检查配对构成，不形成新的独立样本或额外CI。全部100源、逐任务/95个cut的七比较见补充result.json。

## Q 与真实增益

Q诊断只覆盖有候选的95个cut。5个共同结局不伪造Q、不以0补齐；其真实结局仍保留在100源主分母。评分固定状态与a0，使用C(raw)=clip(raw)和冻结critic；这里读取生成时保存的Q，不重新运行模型。

| 方法（95源） | 平均预测ΔQ | 实测相对replan pp | Pearson / Spearman | Q正且真实正/负/零源 |
|---|---:|---:|---|---:|
| velocity | 0.081334 | +3.42 | 0.351 / 0.280 | 9/4/75 |
| direct | 0.001780 | +2.89 | 0.147 / 0.172 | 8/4/49 |
| post | 0.112804 | +4.47 | 0.317 / 0.215 | 10/4/80 |

Q相关性、符号表及逐任务结果是生成候选上的描述；Q上升不等于环境收益。本轮没有新增反向/随机臂，不能仅凭V/D/P差异把原因唯一归为评分方向或梯度进入flow的方式；不构造跨轮配对或旧critic第六臂。

## 最终 raw 命令、mask、别名与 fallback

每bank的raw不同命令组数分布：{"4": 95}；不同raw仅clip后碰撞源数：0；最终RMS未匹配源数：0。

| 方法 | XYZ RMS均值 | grip RMS均值 | XYZ/grip零通道源 | raw等于a0源 |
|---|---:|---:|---:|---:|
| velocity | 0.043022 | 0.094749 | 0/2 | 0 |
| direct | 0.043022 | 0.094749 | 0/2 | 0 |
| post | 0.043022 | 0.094749 | 0/2 | 0 |

raw尾段/mask外/评分映射/cap检查失败计数：`{"alarm_replan10": {"caps_within_frozen_tolerance": 0, "outside_mask_bit_exact": 0, "raw_delta_equals_critic_delta": 0, "raw_tail_bit_exact": 0}, "direct": {"caps_within_frozen_tolerance": 0, "outside_mask_bit_exact": 0, "raw_delta_equals_critic_delta": 0, "raw_tail_bit_exact": 0}, "post": {"caps_within_frozen_tolerance": 0, "outside_mask_bit_exact": 0, "raw_delta_equals_critic_delta": 0, "raw_tail_bit_exact": 0}, "velocity": {"caps_within_frozen_tolerance": 0, "outside_mask_bit_exact": 0, "raw_delta_equals_critic_delta": 0, "raw_tail_bit_exact": 0}}`。
可行匹配组标志：`{"gripper": {"shrunk": 28, "zero_group": 2}, "xyz": {"shrunk": 65, "zero_group": 0}}`。
fallback原始计数：`{"base": {"None": 95}, "direct": {"None": 95}, "velocity": {"None": 95}}`。
提前结束导致prefix不足的分支数：`{"alarm_replan10": 0, "continue_native10": 0, "direct": 0, "post": 0, "velocity": 0}`。

逐源文件保留mask比例、mask外逐位恒等、raw尾段、raw与critic映射、cap、实际执行prefix幅度及每次flow更新。最终前10命令的同幅约束不限制中间flow查询；匹配允许放大原生方向。原raw超界值按既定语义保留，不从有限物理探针推断普遍clip等价。

## 资源与成本

本阶段1995次仿真尝试=95次独立bank恢复+1900分支（分支内恢复已计入），阶段上限2100；0优化更新。独立审计时全局分资源计数为 `{"simulator_attempts": 44869, "training_updates": 51200}`。
独立重聚合通过114,927项检查；逐次结局与原主统计完全一致，实际后缀seed/noise核对24,577条。

8GPU×4worker波次墙钟（含lifecycle）854.96s；worker初始化均值175.17s、中位175.48s。初始化包含输入校验、CUDA及模型加载，不能单独当模型加载时间。32个worker的实际loaded critic身份已逐项对照A4000四成员资产、SHA、strict reload及冻结检查回执。

| bank/生成组件 | 记录数 | 缺失 | 均值s | 累计worker-s |
|---|---:|---:|---:|---:|
| restore_seconds | 95 | 0 | 1.072470 | 101.885 |
| candidate_bank_seconds | 95 | 0 | 1.436098 | 136.429 |
| generation_wall_seconds | 95 | 0 | 2.545475 | 241.820 |
| base_seconds | 95 | 0 | 0.529303 | 50.284 |
| velocity_seconds | 95 | 0 | 0.447357 | 42.499 |
| direct_seconds | 95 | 0 | 0.427578 | 40.620 |
| post_seconds | 95 | 0 | 0.003466 | 0.329 |
| objective_critic_forward_seconds | 95 | 0 | 0.038098 | 3.619 |

| 分支方法 | 恢复均值s | 后缀policy均值s | 环境均值s | 分支wall均值s | 分支wall累计worker-s |
|---|---:|---:|---:|---:|---:|
| continue_native10 | 1.0342 | 6.8886 | 0.2685 | 8.2964 | 3152.625 |
| alarm_replan10 | 1.0333 | 5.6201 | 0.2273 | 6.9801 | 2652.428 |
| velocity | 1.0349 | 5.2244 | 0.2169 | 6.5741 | 2498.155 |
| direct | 1.0339 | 5.3026 | 0.2174 | 6.6510 | 2527.370 |
| post | 1.0338 | 5.1489 | 0.2165 | 6.4969 | 2468.812 |

generation wall包含restore；candidate_bank不含source恢复。post秒数只代表额外梯度步骤，不能当作完整策略推理成本。分支policy_seconds只计执行后缀的策略采样，restore、环境执行、wall分别保留。environment_seconds也包括source replay的环境步，与restore有重叠；累计worker秒与波次墙钟不同，显存峰值不可相加。共享base、执行顺序、并发、终止长度均影响时间，本报告不宣称串行对照加速或四倍加速。

新增bank/rollout/collection/guard/wave文件总计155,323,353逻辑字节；不含复用source、模型与本报告。

## 随机流与方法边界

实际入口为create_policy_collector→collect_existing_slot，原100dev身份不变；禁止capture、替补与复用旧guided动作。每个新bank在首分支前核旧新raw50 a0、base seed、initial-noise SHA及mask，并核本轮V/D/P最终raw同幅。a0随机流键为designated_a0/episode/cut/index0；后缀键为branch_suffix_decision/episode/cut/repeat/decision_index。索引零基连续，方法、critic、bank和worker不进入seed；不要求不同臂的绝对采样时刻相同。

normal完成cut时当前native10队列剩余命令；其他臂从cut执行新10步prefix，之后统一native10。状态、a0固定，仅候选梯度参与引导；评分模型、VLA、D、G0及科学参数以本轮冻结配置为准。

参数原样记录：
```json
{
  "source_horizon": 10,
  "prefix_horizon": 10,
  "suffix_horizon": 10,
  "control_budget": 300,
  "gate_threshold": 0.05,
  "guidance": {
    "alpha": 10.0,
    "times": [
      0.3,
      0.2,
      0.1
    ],
    "clip_derivative": "true clamp through same T",
    "velocity": "v-alpha*tau*grad_u R(T(u))",
    "direct": "v-alpha*grad_u R(T(u))",
    "clean": "u=x_tau-tau*v; sampler Euler dt=-.1",
    "no_step_backtracking": true
  },
  "matching": {
    "xyz_rms": 0.05,
    "gripper_rms": 0.1,
    "xyz_linf": 0.15,
    "gripper_linf": 0.4,
    "boundary_clearance": 0.05,
    "tolerance": 1e-06,
    "zero_threshold": 1e-10,
    "algorithm": "shared mask:1-abs(a0)>=.05; normalize each group direction to unit RMS; common radius=min(target, all direction feasible radii); bounds=min(group cap,1-abs(a0)); final float32 check",
    "amplitude_can_expand_native": true,
    "native_arms_separately_executed": false,
    "post_metric": "environment grad times ((q99-q01)/2)^2, matching internal clean-action Euclidean gradient",
    "random": "independent Gaussian three knots per action dimension, linear interpolation over ten steps",
    "reverse": "negative of projected direct command delta",
    "zero_group": "if any primary direction has zero norm, all matched arms use zero for that group; never drop source",
    "shared_radius_dependencies": "Generate velocity/direct/post/reverse/random every source; reverse/random/native outputs are saved, not simulated."
  },
  "command_semantics": "raw native a0 + feasible matched delta; no replan-only clamp"
}
```

## 解释与执行审计补充

Post净增17次成功中，disassemble贡献8次、stick-pull贡献8次、shelf贡献1次。disassemble的normal/replan/post为68/61/69，任务总体上主要修复重规划的损失；这不意味着已识别每条轨迹的恢复机制，也不能把Post相对normal的13.25个百分点全部归为纠偏。V、D、P各有4个Q升高但真实收益为负的源。Direct另有34个预测ΔQ为负的源，均按原接受语义保留，未引入Q门或事后筛选。

最终1124个冻结文件核验通过。原freeze.files遗漏了7个绝对路径授权审查引用；这些文件的SHA已在冻结READY中，prepare.release在启动前核对过。执行中在本阶段297次attempt时，将全部8个绝对路径引用重新核SHA并独立归档；这是执行中的补充快照，不能称为启动前完整清单。原freeze、代码、模型与参数均未修改。最终补充文件与原READY摘要仍全部一致。

全轨迹审计、独立统计、raw/噪声/mask/同幅检查均通过。正式入口41项CPU检查，报告链9项独立审计与13项成本/报告合成检查已分别存证；后两组为执行后记录代码SHA，不声称有未保存的执行前SHA。本轮0技术缺失、0重试、0capture、0替补、0新增优化，技术储备仍0/1200。波次退出后8个holder均恢复。汇总和最终绑定检查均未调用模型或仿真。

本阶段1995/2100仿真；全局44869/50000仿真、51200/51200优化。剩余总额度不构成下一阶段授权；cal/held保持锁定，等待分析端对完整结果的阶段判断。

## 复现与逐源证据

下列SHA均为文件原始字节SHA256；complete.json的SHA用作该目录封存标识。参数以独立冻结config为准，代码文件清单见freeze，全部逐源配对结果见CSV。

| 证据 | 路径 | SHA256 |
|---|---|---|
| config | [config.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_protocols/round2_policy_v1/config.json) | `d2a60785fc84063e02fee965fa8ba009b3880783ac58adf5dc9ce4011c819dc0` |
| freeze | [freeze.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_protocols/round2_policy_v1/freeze.json) | `cdbb364de29b44fea522f3740c185ccc97337f9123662e720e2f7903def5f292` |
| primary_audit_seal | [complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy5_audits/round2_policy_v1/complete.json) | `2a0eab3cd529ba4eb41d4ebf25418c7a2c3ba22d1f583e06e6af9eb739f16974` |
| primary_audit_result | [result.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy5_audits/round2_policy_v1/result.json) | `7f781889632af74073969e8c3f69845ff6db3e5f2fceb3ec66b999555b92c296` |
| independent_audit_seal | [complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy5_independent_audits/round2_policy_v1_independent/complete.json) | `5e1fcf734719d57b9876707de58d65d00c5ceb3565e442e6e0e570138c0f1210` |
| independent_audit_result | [result.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy5_independent_audits/round2_policy_v1_independent/result.json) | `d4587eb1e881116ad258d34920c2636636eeae3e822b99d02659ce3a74326a40` |
| cost_diagnostics_seal | [complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy5_cost_diagnostics/round2_policy_v1/complete.json) | `95da36e91eea519979cdad6f126e39b9f3f47f8dcbda6f574c5c83ec91cadad0` |
| cost_diagnostics_result | [result.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy5_cost_diagnostics/round2_policy_v1/result.json) | `5d5906b72040063dcc914c6f76dc927af4ca9e780f06aac8940fbce966c71146` |
| full_report_seal | [complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_reports/round2_policy_v1/complete.json) | `3ed4d3304db99663bfe0cef392a9cf9ff2031716e9aae4bbb6c373a4475d9fa6` |
| per_source | [per_source.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_reports/round2_policy_v1/per_source.csv) | `1fe9b39107b597a03ab2600a900068ed42e9be6821b3b2f7fd442cfdc1908f6d` |
| selected_model_seal | [complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/models/final/final_fit_v1/selected/complete.json) | `f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a` |
| entry_cpu_seal | [complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/round2_policy_cpu_20260917_v1/complete.json) | `8dff6d4fba6b04c0a3673f6a42e5873aca659729c547388749801c4074ad0db1` |
| independent_cpu_seal | [complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/round2_policy_independent_audit_cpu_v1/complete.json) | `4a4843a43ba391dc5a79d16bd99ec818fc8278beff23f4a1954288f5ecebf92e` |
| diagnostic_cpu_seal | [complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/round2_policy_diagnostic_cpu_v1/complete.json) | `d6864c2c3fb36e1d40e7721c629e5e1c302d5f70a1fb68a49e83ff76aa2052f7` |
| authorization_supplement_seal | [complete.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/round2_policy_v1/authorization_supplement_v1/complete.json) | `8de354bc83094d319f144c5384ee807eb83dbf58ce6217fec5e48bd9654effd5` |
| end_binding_check | [end_binding_check.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/round2_policy_v1/end_binding_check.json) | `884834f938dbf01daafb71fbf7ee549c22bdf7b7cd33db8ec78aa648244a7fce` |
| gpu_after_wave | [gpu_after_wave.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/round2_policy_v1/gpu_after_wave.json) | `96c686fdfa060ed58fe880277019e0e5a3dfbb44c3f9b65d94ed953541dff6da` |
| execution_result | [result.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/round2_policy_v1/result.json) | `5b8ac41a6513eddaf338601627a7892d4cb09b3107979257afce77e8acabc947` |
| postprocess_result | [postprocess_result.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/round2_policy_v1/postprocess_result.json) | `9b63b702239fecbc79dfa0c87952149cc54be33310c54c2da97201b1c4eefcb9` |
| ready_snapshot | [NATIVE10_ANALYSIS_READY.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_protocols/round2_policy_v1/coordination/NATIVE10_ANALYSIS_READY.json) | `7af5045a44944894cc8c89eb10f8110c2098d7458718fe0550d03a42fe30b953` |
