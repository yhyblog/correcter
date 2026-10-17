# Round2 采集准备：独立数据身份与契约审查

2026-09-16，执行端独立只读审查。结论：原注册的 round2 300 个训练主槽、候补链、LEAD fallback、B200 身份及 17,400 次预算相互一致，未发现数据身份或预算阻断。本文件不授予 READY，也不替代新入口的 CPU 检查、配置/代码冻结与实际加载校验；本次未运行模型、PCA、优化或仿真，未修改任何旧封存。

## 1. 输入身份及复算方法

路径以下以 `outputs/native10_training_20260916/` 为根。所有 canonical SHA 使用 `json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')` 后 SHA256。列表保留原 manifest 顺序，不重新排序、不按结局筛选。

| 输入 | 实际文件 SHA256 |
|---|---|
| `preparation/main_registration_v2/primary_manifest.json` | `991e13f37117d3bc41b904554602be413e281a4ae1f80f6c05c00d70d6433886` |
| 同目录 `combined_manifest.json` | `ffc9e62a38b37ac32d2dbd199eca113ef256a434dfb4cd87aa2f1dcabcde15c2` |
| 同目录 `registration.json` | `8f3777af260bd1c386f7144147a2ed316c790d593b2d0beb70e2a81476dfc809` |
| 同目录 `replacement_candidates.json` | `f6e2f4d86abfb8d2b93bfebd8efec807c3b98f3d51c981344e1dcc765da5ab07` |
| 同目录 `reserve_manifest.json` | `f5ded06a0750f7c60e6ceaa3d3af7cc3cd3c49d129e127a746b4608912a68819` |
| `main_protocols/round1_v1/config.json` | `f68b59f279ae4d03094ebe70f0185e29d7a65a8ce20903aed92ac4392f1e4fd2` |
| 同目录 `freeze.json` | `f46dda706607bf8ed52281d33a203471c2854b6c09f83e6d26d3b216a509d893` |

审查时 live `coordination/NATIVE10_ANALYSIS_READY.json` 已为 v8，SHA `decbf30a364e1cc8e56bdc225bc99cce9fe1a5d810aaa1a869604bb3aeb89ec5`；其 round2 ID 列表、canonical SHA、scope、17,400 simulator/0 optimizer 与独立复算一致。分析决定 `NATIVE10_ROUND2_COLLECTION_DECISION.md` SHA 为 `77bebf165cf6f4850dff7e411eef86300e10b4a8eb3f8ccd2eb2fc0c48bed11d`，LEAD SHA 为 `e39d35a046ab9058c9539cae876a3168d98fe2900b580ea0cc042eed1479e833`。这些是本次读到的文件身份，正式入口须绑定自己的不可变副本。

## 2. 原始 300 主槽和 600 条件候补

唯一主槽提取规则：原 `primary_manifest.json` 中 `split == 'train' and round == 2`，保持原顺序。得到 300 个唯一 ID，env_seed 连续为 **2026111300–2026111599**。逐行确认其内容与原 combined manifest、冻结 round1 config 的 `episode_manifest` 完全相同。

- 300 IDs canonical SHA：`9c1891d17b8c438162c4c2ab4ba245864e743b42cd4aa8b813baf298c922f78a`。
- 300 完整原注册 rows canonical SHA：`92c92374f27272113cffb0f312fdc6309dd1984c5d0ac0d261a32a4864c8dd27`。
- 第一槽 `disassemble-v3__2026111300`，最后槽 `stick-push-v3__2026111599`。

| task | 主槽 | 首次报警目标 | scheduled15 | scheduled45 | scheduled95 |
|---|---:|---:|---:|---:|---:|
| disassemble-v3 | 60 | 30 | 10 | 10 | 10 |
| pick-place-wall-v3 | 60 | 30 | 10 | 10 | 10 |
| shelf-place-v3 | 60 | 30 | 10 | 10 | 10 |
| stick-pull-v3 | 60 | 30 | 10 | 10 | 10 |
| stick-push-v3 | 60 | 30 | 10 | 10 | 10 |
| 合计 | 300 | 150 | 50 | 50 | 50 |

以上是注册目标分组，不能要求实际恰好产生 150 个报警 cut，更不能换 seed 凑足实际报警。

每主槽恰有原注册顺序候补 2 个，共 600 个唯一候补，env_seed **2026120600–2026121199**。全部候补与原 combined/config 逐行一致，继承主槽 task/split/round/source_horizon/cut_rule，`replacement_of` 及 `replacement_ordinal` 为原值。300 主槽对应的候补链映射 canonical SHA：`0bec5ab8ece6adfbb5659d0994f2afc5e14df253610116faf7531f879d18651c`。

新 bank 的 `episode_ids` 只能是上述 300 主槽；600 候补是有条件的替补身份，不是新增计划分母。`main_runner.py:164–220` 按原顺序解析，只有首次动作前 `initialization_failed` / `duplicate_initial_scene` 激活下一候补；无报警、无合法 cut、普通失败、Q 或候选收益均不构成替补理由。`main_collection.py:212–229` 还要求每个前置候选有封存的 pre-action rejection，`success is None` 且动作数为 0。

## 3. fallback 占位字段的有效解析

原 150 个 scheduled rows 保留 `cut_rule.fallback = 'none_pending_analysis_review'`，另 150 个 first_alarm rows 没有 fallback 字段。原 manifest 必须保持原字节；新配置单独记录原请求字段和有效 `analysis_lead_v1`，明确该历史占位被 LEAD 第 3 节和 round2 决定覆盖。

有效规则为 scheduled15→5、45→15→5、95→45→15→5；训练首次报警组没有合法报警时按 15→5。`main_collection.py:56–87` 仅以可达合法 cut 和首次合法报警作选择，不以占位字段禁用 fallback，不接收 success/Q 参数。无合法 cut 保留缺失及理由。其他 split 不启用训练 fallback。

`main_collection.py:316–350` 在下一动作执行前保存仍存活、队列中点合法且剩余至少 10 步的早期 5/15/45/95 anchor；`context.npz` 来自该时刻的历史、proprio、past actions、language、remaining。`summary.json` 保留原 `case.cut_rule`，以及 `requested_cut`、`actual_cut`、`selection_reason`、`selection_category`、`selection_audit.priority_order`、`selection_uses_outcome_labels=False`。事后 fallback 不可把 episode 后续终局写入这些模型状态特征，也不代表可部署报警策略。

半/全通道半径也要提前解析：原 `prepare_main.py:60–65` 按 `(task, split, round)` 内原顺序 index，对 train 用 `.5 if (index//2)%2 == 0 else 1.`。应用于新 300 槽得到半/全各 150，每 task 各 30；首次报警目标半/全各 75，scheduled 每个目标半/全各 25。完整新 map canonical SHA 为 `27b7d171cb439dea68408203011eefebbf918161d6a3f4ce78d8eb6b7afb6362`。不能原样复用只含旧 400 槽的 radius map；新 map 键恰为 300 主槽，候补按 `replacement_of` 继承主槽半径（`main_collection.py:170–173, 419–424`），无需新增候补 radius 键。

## 4. 资源账本和余量

只读 `budget/attempts.jsonl` SHA `9bfb286467094c4c5fd6b26385b857b550febb854aa349827336baff4da74586`：44,674 条记录、44,674 个唯一 number，其中 simulator **25,474**、optimizer **19,200**；按 resource 分别求 amount，不把二者相加当 simulator。

| stage | 已用 simulator | simulator 上限 | 当前余额 |
|---|---:|---:|---:|
| p0 | 564 | 600 | 36 |
| round1_labels | 22,915 | 23,200 | 285 |
| round1_development_policy | 1,995 | 2,100 | 105 |
| round2_labels | 0 | 17,400 | 17,400 |
| round2_development_policy | 0 | 2,100 | 2,100 |
| calibration | 0 | 1,200 | 1,200 |
| heldout | 0 | 2,200 | 2,200 |
| technical_reserve | 0 | 1,200 | 1,200 |
| 全工作流 | 25,474 | 50,000 | 24,526 |

本阶段每源上界 `1 capture + 1 bank restore + 13×4 candidate branches + 1×4 normal branches = 58`，共 `58×300 = 17,400`。每个 branch 的恢复已经包含在该 branch attempt 中，不额外漏记/双计。alias 仍完整执行 13×4，不能借此授权改成标签复用。

若 round2 用满且不动储备，累计 simulator **42,874**，余额 **7,126 = 5,500 后续阶段 + 1,200 技术储备 + 426 旧阶段未用**。预算表的计划 48,800 与技术储备 1,200 合计 50,000；未用额度不是自动扩展试验授权。替补 capture 记 technical_reserve，后续 bank/labels 仍记 round2_labels，失败及已尝试 capture 不回滚。储备属于整个工作流，不能为 round2 重置额度。

optimizer 已用 19,200，硬限 51,200，未来额度 32,000；本采集阶段及技术储备 **0 optimizer**，不开放 PCA、新初始化或最终训练。新配置应只映射 round2_labels→round2_native10_local_labels、technical_reserve→preregistered_initialization_replacements；其他历史已完成及未来运行入口继续锁定。

## 5. B200 与真实场景绑定

`models/round1/round1_fit_v1/` 中需绑定以下内容，已纯文件读取核对 READY 声明及 selected seal 列出的全部 6 个文件 SHA；没有反序列化模型或做 forward。

| 资产 | SHA256 |
|---|---|
| `complete.json` | `ff460f12c598a34a15a28ed7619ed071a60be195a3dd2f0c1c963a202ee22287` |
| `result.json` | `2b9f668b24a7c94e86a75342bd981751c6627e2569cde1ddb7868afd14c3f03f` |
| `selected_reload_audit.json` | `ce43fc0888f807ef048612ad733795bc1ad5aef24103f0ed89e3c1d51c4beb7b` |
| `selected/complete.json` | `931c6f6043db92b5d9003eb2833dfc8edd0ab6c860a1979db3983cd7d893725f` |
| `selected/ranking.json` | `6b0a7e4530bfbbadafabb9546a891fbe4bf64a6d3774df62515f9ccd9aae242d` |
| `selected/config.json` | `0fe942a745d8ad31b055ce670647da71799a78f622ca5f98175109efa24b47a6` |
| `selected/models/refit/member_0/selected.pt` | `bc93c9035409cd2b7e413dffd0e0f9f3053ac34add4b47fc5cd57be9a5cdceb3` |
| `selected/models/refit/member_1/selected.pt` | `639e78888f9ef9657cef73da4f21f0676593a58ec4bfa0f8f098d0885432fb2f` |
| `selected/models/refit/member_2/selected.pt` | `e1f06c0214243ec9fd8952cab93139feafafbc8e84a74e432e9498d68d422df3` |
| `selected/models/refit/member_3/selected.pt` | `ae18f18e36b878b37b1085778136f6faf62f7146ad0d4ca015076671b2a074eb` |

必须校验实际 loaded selector 的四成员身份、B/step200 选择及预处理配置；路径字符串相同本身不能证明权重相同。旧 VLA/D/G0 的内容身份、ActionTransform、flow 时间/强度、matching、native10/raw/10步prefix/后缀语义与总300步同时保持。新源重新生成 a0 和各候选，不能复用旧 guided 数组；只保证新源内部 a0/引导共享随机输入，不复制 policy5 对旧 dev a0 的跨 bank 恒等限制。`main_collection.py:160–166,232–235` 已有四成员和运行 engine 校验接点，新 guard 须保留其真实执行。

审查时 `scene_registry/entries.jsonl` 有 400 条已接受身份（train300/dev100），SHA `ffb5abdf935645485604d0af9c43990ac7ebce87e9c921de70ef9d0cba39d497`。正式协议冻结该启动证据的不可变副本，并在首次动作前对所有既有已初始化 split 核对真实物理 scene。活动 registry 在新采集时合法追加，不得每次按启动前整文件 SHA 拒绝合法增长；应保持旧前缀、条目身份与原有并发排他登记。不能提前初始化 calibration/heldout。

## 6. 对新准备入口的验收边界

本 review 已验证的是原契约、身份、旧语义实现和现有资产；尚不声称正在新增的 round2 prepare/runner/guard 已通过。其最终 CPU 与冻结应覆盖：精确原300主槽及原候补链；有效fallback与原占位分离；上述固定半径分配；新 primary capture 和 labels13+normal 能力；实际 B200 绑定；stage/资源隔离；mask/raw/正反/alias/配对seed；registry 起始快照与合法追加。

正式入口不能调用 policy5 existing-source-only 入口。namespace 沿用已冻结语义：source 自然决策 index 与 branch suffix decision index 分开；同源同 repeat 各 arm 共用 suffix 随机流，method 不进 suffix seed；不同 repeat 独立，不宣称不同规划相位的同一绝对环境步使用同一噪声。完成新 CPU 证据与配置/代码/READY8/300IDs/模型/场景依据冻结后，由主执行端按已批准条件启动；本次审查本身未增加任何运行权限。

后续全量静态输入保留原600计划训练槽和两个 generation critic 的 provenance；无cut/缺失不能补0或丢掉计划槽。最终训练、第二次开发测评、calibration、heldout 仍需各自阶段协议。本阶段中途只报告技术进度与成本，不按收益挑源、挑模型或提前停止。
