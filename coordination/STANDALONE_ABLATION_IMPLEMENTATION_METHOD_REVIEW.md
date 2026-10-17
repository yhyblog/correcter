# 独立纠偏实现：CPU v4 方法与入口审查

日期：2026-09-18 UTC。

**当前结论：CPU v4 有界方法与入口审查 PASS。** 成功路径的采样与梯度数学未变；已知 GuidanceError 现在立即中止、不进行 fallback，并完整记录该次已启动采样。其他异常若缺少调用证据，明确保留未知值和已知下界后停止，不能声称已知全部调用次数。本审查不释放 GPU、模型或仿真；真实数值与配对复现仍由预登记技术预检验收。

## 当前增补：仅核 CPU v3 → v4 的两文件变更

| 当前材料 | SHA256 |
|---|---|
| `outputs/standalone_ablation_20260918/preparation/cpu_v4/complete.json` | `b014ced62ba7f2f086caa3db565140a47c6f449cd1668b72ef16f76b9a33855f` |
| 同目录 `result.json` | `fba1310f82bd4640c18b425556384317e57629ee4cf54dc92308646f07b3b962` |
| `experiments/standalone_ablation_20260918/engine.py` | `8787c21c13a5f61485f09685346f16242022d4640bd507592791a35276a3c9d6` |
| 同目录 `test_engine.py` | `ca9c46c99725070ecb52bb428024c7fb5e0b2255a726a927559a27bf0249350e` |

CPU v4 seal 的 4 个文件实际 SHA 一致；XML 为 **136 tests、0 failures、0 errors、0 skipped**，退出码 0。22 个被测文件 `before == after == 本次检查时 current`。与 CPU v3 的代码清单相比，只有上述 engine 与其测试两文件变化；这两文件的 v3 SHA 分别就是下方历史 v2 表中列出的值。TASK 身份未改变。未重跑 CPU、模型或完整入口审查。

窄差分结论：

1. **成功数学不变。** Post 的 S² 梯度、V/D 原生方向和共享原语调用保持原样；新测试在移除双方 GuidanceError 处理块后，证明新旧 `propose` AST 相同。1/2/2、独立 a0 及原半径用例继续通过。采样计数按调用进入计，失败的部分采样不是一条成功生成轨迹。
2. **已知 GuidanceError 闭合。** 处理器记录 `policy_calls=1`、部分时刻/更新、耗时、梯度计数和错误，再抛带证据的异常；不再调用第二次 `native_action`。外层即使 propose 未返回，也保留失败 proposal 并合并成功/失败调用数。CPU 使用抽取的实际生产方法 AST 和 CPU 替身验证 base、direct、velocity 故障：base 失败共 1 次，已有 base 后引导失败共 2 次，无有效候选、无重采。这个修改改变故障处理，不改变任何成功候选的数学。
3. **未知异常如实停止。** 没有底层计数证据时，`actual_policy_calls` 与失败调用数为 null，`policy_call_count_known=false`；`known_policy_calls` 仅是可证实下界。入口不重试，也不把未知重采情况写成 false。若异常自身提供实际重采证据，则保留真值和实际数量。此诊断限制沿用分析端已明确的异常中止口径，不构成正常预检阻断。
4. **失败证据可封存。** NaN/Inf 显式转成带类型的诊断对象，既保留信息又可写严格 JSON；测试覆盖部分失败日志序列化。所有异常均不能输出可用候选，原 runner 停止规则未变。

下方保留 CPU v2 的历史审查与当时 pending 事实。其“额外采样没有取消”等描述只适用于 v2/v3；**当前 v4 已取消 GuidanceError 的内部 fallback**。不得用这段历史文字描述 v4，也不得把 v4 的通过回填旧 CPU seal。

---

## 历史记录：CPU v2（当时有一项 pending）

当时结论：核心方法及成功入口通过；失败 propose 内部计数记录不完整。当时尚未将未知计数明确标为下界，也未取消 GuidanceError 内部重采。以下保留原核验依据与待办，不代表当前还有同一阻断。

## 1. 身份与证据

| 材料 | SHA256 |
|---|---|
| `coordination/STANDALONE_ABLATION_TASK_20260918.md` | `363c50bedcb04d93a5904bf7ecf9873d691974e7e67d82f3a419af4c0065ff5e` |
| `outputs/standalone_ablation_20260918/preparation/cpu_v2/complete.json` | `7438671e116cfe31eb3d13868c2b309ce6b0e109e48bf989372851810c35cb44` |
| 同目录 `result.json` | `b5e83f50c41565d539234953475b24ebec431e256e2f825ecc3a35746576cf05` |
| 同目录 `pytest.xml` | `e95e1445ec0d0dc9352937c53e360cd28f8f6c9af8bf0ea61fae4aeb269a53bd` |

CPU seal 内 4 个文件实际 SHA 均一致；XML 为 **117 tests、0 failures、0 errors、0 skipped**，退出码 0。CPU 记录的 20 个新模块/测试/启动脚本满足 `code_before == code_after == 本次只读检查时 current`，没有把后来未测试的版本套用旧通过结论。

运行证据为 lerobot Python 3.12.13、NumPy 2.2.6、Torch 2.7.1+cu126，线程变量均为 2。CPU 包明确记录 0 实际模型调用、0 仿真、0 优化；本次审查也没有重跑 CPU 或实例化模型。

关键文件均位于 `experiments/standalone_ablation_20260918/`：

| 文件 | 本次被审 SHA256 |
|---|---|
| `candidates.py` | `399f52e14f015d79cf529d3c16147ddc9fa2f8a96529549b2f428449657d0309` |
| `engine.py` | `48183f90a82d744884a0746c348937fbcfdb2b3ad87133e5856e1f5a5732c29c` |
| `reference_generation.py` | `a87d634cad3553bf5643368912aa274a15f23479c3b9330f77457f5eac6ae939` |
| `collection.py` | `6dbbdc164b48e4ae53e5db4c79f8ea859f08ee048193ff17ee8c0247e4b3cb4d` |
| `audit.py` | `5fee82e59935c8d0edbceb2ef3cf014cea3507f7f7dacfff37b587d908dc15ab` |
| `protocol.py` | `c20302fbe365914e76178443568dd99d77cb1daaead0aa9cbac76265c8cf4818` |
| `test_candidates.py` | `e8494d649e7e9ee99f583336127039b20f49c690c08768244c3242446ab7339e` |
| `test_engine.py` | `c9aa10da317c06b61ec1131a246321cdb7bc46afb93dc97a788816ee55517b44` |
| `test_reference_generation.py` | `6048c42103830bc14c23f958857fe379b29a0cd5e960a1f0caca82174a88d7a7` |

## 2. 核心方法与成功入口

- `generate_solo` 每次先生成自己的无引导 a0；Post 只求一次原命令梯度乘 S²，D/V 仅再运行自身引导。没有读取其他方法数组、其他半径或 fullbank 作为生成输入。成功返回的采样数固定为 **1/2/2**；CPU stub 检查调用顺序、同种子和跨入口重新生成 a0，未把这些测试冒充实际 VLA 数值复现。
- 原 `FrozenObjective`、`ActionTransform` 与 `FlowHook` 继续被使用，未替换成 full-Jacobian、直通 clamp 或新目标。配置检查固定 alpha=10、tau=.3/.2/.1；实际审计还要求三次相应 mode 更新、原概率增益语义和窗口外梯度为零。
- 自身半径保留 mask、整组 RMS、对称容量、cap、数值内缩；只由本方向决定零组，没有 random/reverse 依赖。CPU 有已知数值预期的稀疏组 RMS/坐标 cap 用例、微小非零方向放大、局部零组、解除旧共同零组以及自身半径不低于旧半径用例，证据不只依赖同一函数自重放。
- raw 恢复有超界夹爪、mask 边界、signed zero、零组和尾段用例。候选仍只修改首 10 步允许的非零增量，未把整个 raw 计划额外裁剪后执行。
- 原生方向校验路径完整：Post 与旧封存原梯度/S²方向逐位比较；V/D 从自身 guided raw 经 C 形成差值，并在预检与独立重新生成的旧完整实现所捕获的 native raw 比较。旧 V/D 原生数组原本未封存，该事实明确保留，不从旧 matched delta 反推。
- 完整入口计时包括自身 a0、目标设置、修正、最终评分和核验；加载/恢复另计。它包含实际诊断开销，不应改称纯梯度成本或无诊断部署延迟。

## 3. 已闭合的参考入口与 AST 问题

`collection.py` 已正确导入 `reference_generation.compare_archived_identity` 和 `generate_reference`，前者仅在新候选生成之后比较；完整参考生成限于预检，不能在正式阶段产生其他方向作为输入。

参考证明同时固定原文件 SHA `43bfe0799c3815e29b06be26475dfbb6c70df7bf431cedc630d9eb7622dd65ea` 和正式 Python 3.12 的 AST SHA `d5f80efca25d652610d1157d44631b75734e47356a4600e3241fa3bd1691b110`。未删除字段规避校验，未动态信任任意当前 AST；未登记 Python 版本及被改动原文件都拒绝。原函数 AST 直接编译，数学没有重写。CPU v1 的版本序列化差异已闭合。

## 4. 内部 fallback 的准确边界及唯一待办

**额外采样没有取消。** 新 `propose` 保留与原实现一致的内部流程：guided 抛 `GuidanceError` 时再做一次无引导采样。只要这次 fallback 正常返回，stats 记录 `policy_calls=2` 和 fallback 原因；独立入口保存该 proposal 后立即拒绝候选，不重试整个入口。故成功 1/2/2 与失败时多一次内部采样是两种情况，`automatic_retry=False` 只能解释为不自动重试入口/波次。

但当前记录在 `engine.propose(...)` 返回后才加入 `proposal_records`。若 fallback 自身也抛异常，或 propose 在已采样后校验失败，该 propose 的实际已启动底层采样没有进入 `completed_proposal_policy_calls`；runner 只是转存同份 evidence，无法补回。这不是纠偏方向错误，也不会产生可用失败候选，但不满足所有失败 guided/fallback 尝试可追溯的验收条件。

**最小闭合条件：** 在每次底层 `native_action` 进入前记录 started，完成/异常均保留状态；即使 propose 未返回，也保留当前 proposal 的实际尝试数与错误。区分“propose 调用次数”“底层采样已启动/已完成次数”及“是否内部 fallback”。保留采样、梯度及 fallback 原算术；补充覆盖 fallback 自身异常和采样后校验异常的 CPU 证据，再绑定新代码与新 CPU seal。不得把 CPU v2 的通过记录移作修改后代码的验收证据。

实际旧轨迹复现、原生 V/D 逐位比较和完整配对可用性仍由已登记真实预检验证；本报告不提前声称这些模型层检查已经完成。
