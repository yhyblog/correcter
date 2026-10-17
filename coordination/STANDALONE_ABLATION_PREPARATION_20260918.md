# Standalone 消融：只读准备交接（2026-09-18）

已接单，8卡 holder 正常。当前仅核对代码、既有封存与账本，新增模型调用/仿真/训练/测试均为0；没有修改旧 READY、代码、账本或结项产物。本报告撰写期间，新 TASK 已落盘并完成读取；科学与预算现以该 TASK 为准。TASK 已允许新隔离工程/CPU准备，真实模型、预检及正式采样仍须新 READY。本次交接只完成只读准备，没有提前实施这些计算阶段。

**可行性与定位。** 复用原 held100，每任务仍为原20个真实不同初态；98个有cut、2个无报警共同结局，按任务cut数为20/18/20/20/20。只新增 standalone-post/direct/velocity 各4条配对后缀，无新capture、替补或筛源。原五臂只读保留作配对参照。此次是已揭晓 held 上的结构消融，不是新的独立测试，不用于事后选赢家或改写原A4000＋完整matched-post结论。

**隔离实现建议。** 获准工程实现后，代码放 `experiments/standalone_ablation_20260918`，输出放 `outputs/standalone_ablation_20260918`。采用新的协议/账本、单方向生成器、collector/guard、runner及只读审计；原输入的source protocol与新生成protocol分别存储，不能伪改旧来源字段。原storage的写根固定为native10目录，不能复用旧ledger写入器或全局猴子补丁改变其ROOT。

| 独立入口 | 自身必须实际计算的链条 | 正常VLA采样次数 |
|---|---|---:|
| standalone-post | 同seed重采raw a0 → 固定a0 critic → `S²·∇aR(a0)` → 自身半径 → raw命令 | 1 |
| standalone-direct | 同seed重采raw a0 → 同seed direct引导采样 → 自身方向/半径 → raw命令 | 2 |
| standalone-velocity | 同seed重采raw a0 → 同seed velocity引导采样 → 自身方向/半径 → raw命令 | 2 |

`S=(q99−q01)/2`。post不额外乘flow alpha；V/D保留alpha=10、时刻0.3/0.2/0.1及原flow导数算术。A4000四权重/PCA、VLA/D/G0、G0=.05、native10、一次报警干预、10步前缀/fixed10后缀、总300步与50步生成长度不变。

每方法在XYZ/grip各自计算：沿原mask `1−abs(C(raw_a0)) >= .05`，原方向mask后按全组RMS归一化，capacity仍由对称界 `min(group_linf_cap,1−abs(a0))/abs(unit)` 求最小值。仅把跨方向的min改为 `min(target_RMS, own_capacity)`，保留原`1−1e-6`内缩、float64中间量/float32命令、zero阈值1e-10及检查容差1e-6。XYZ RMS/cap=.05/.15，grip=.10/.40；自身零方向仅使自身该通道归零。保留可放大原生方向的语义，不改成单侧可行半径，不强制三solo同幅，也不增加二次clip。最终仍为raw a0＋可行mask内delta，尾部/mask外/零扰动signed-zero逐字节保持，critic表示等于C(实际raw命令)。

不能调用旧`make_bank/construct`生成全方向后再过滤：它们会运行V/D/post/reverse/random。旧held guard也强制完整五方向同幅，须用新的单方向guard。生成函数仅接收本方法、固定观测和seed；禁止传入fullbank、其他方向或其半径。原始方向、mask、norm、capacity、自身半径、final_raw及critic表示全部存档。

**配对与原始方向证据。** 所有100源绑定原主槽/实际源/cut/context/完整队列/初始scene及封存SHA。采样继续用旧namespace `corrector_native10_training_20260916_v1`；candidate_index=0，suffix仍按实际episode/cut/repeat/decision_index，不加solo方法或新实验名。raw50 a0、初始noise、context、模型/变换身份逐字节核对。恢复沿旧标准：physics atol=1e-10、reward atol=1e-8、rtol=0，图像及world/RNG指纹精确；不扩大容差。不同动作后只要求对应后缀决策序号的seed/noise相同，不要求后续状态、绝对时间或动作相同。

重要限制：旧`formal_directions.npz`保存post原始gradient/metric direction及各matched最终delta，但没有保存V/D未匹配原生50×4输出。不能反解matched delta并称原始方向逐位复现。建议预检用只读旧joint实现重新生成，先对旧已存a0/全部matched/post数组逐位核对，再由隔离的诊断钩子保存该次原始V/D，供solo逐位比较；这个参考调用必须与solo入口及成本记录分离。所有正式源可核a0/noise/post原始方向，并以保存的旧半径对新V/D方向作原matched重投影检查；该检查不等于证明历史未保存的V/D原始数组逐位相同，旧零半径也不能证明方向身份。不得把只验证5源写成全98源原生方向验证。

**必要CPU与小预检建议，尚未运行。** 新增有针对性的合成检查：自身半径/容量及零通道；另一方向为零不再压零；饱和mask/signed-zero/tail与C(raw)；本方法结果对其他方向输入缺失、篡改及执行顺序不敏感；固定slot0只对候选求导；后缀关闭guidance且索引不跳不重；原source来源/种子绑定；未释放scope、旧READY、错误模型及越预算均拒绝。用哨兵把旧fullbank/多方向construct/不允许的其他guided模式/reverse/random入口设为调用即失败，配合真实运行调用计数；仅静态grep不足以证明隔离。旧75+17或79项套件不重跑。

建议预登记每任务原manifest中首个合法cut：disassemble 2026111750/cut15、pick-wall 2026111751/cut5、shelf 2026111752/cut5、stick-pull 2026111753/cut65、stick-push 2026111754/cut5，均未按成功/Q选择。每源旧joint与新solo bundle各恢复一次，重放原五臂各repeat0，并运行新三臂各repeat0：`5×(2 restore+5旧分支+3新分支)=50` attempts。旧五臂重放核对原轨迹/命令/结局；新三臂核语义和随机流，不能要求其结局等于旧matched。预检数据不替代正式四重复，正式再跑仍计费。新TASK第6.2节已采用这5源、rep0及50次预检方案；后续READY仍须绑定真实实现与CPU产物。如需更多复现，必须计入阶段上限。

**计费与成本。** 原权威账本连续99,383条，48183sim/51200opt、reserve0；剩余仿真1817，优化余额0。一个bank attempt对应一次真实reset＋原动作重放至cut；branch自己的restore已包含在branch attempt内，不重复计费。新账本必须锚定旧不可变SHA和48183基数，原子检查`48183 + new_attempts <= 50000`；旧1200技术储备不是额外1200，也不能自动继承为新scope权限。

| 新TASK已固定的补充预算 | 次数 |
|---|---:|
| 正式：98次建bank恢复＋98×3×4分支 | 1274 |
| 上述5源小预检，含旧五臂复现 | 50 |
| 计划新增 / 合并旧账本后 | 1324 / 49507 |
| 补充scope硬限（TASK已固定） | 1500 |
| scope内未用计划余量（分阶段受限） | 176 |
| 满scope后全局值 / 尚未释放余额 | 49683 / 317 |

新TASK分阶段硬限为预检60、正式1400、技术修复储备40（初始锁定），合计1500；176计划余量不能跨阶段任意使用。

1274仅在每源实际只恢复一次、同一不变状态上顺序运行三个独立生成入口时成立；每入口仍重新采自己的a0、建自己的objective，不能共享a0/梯度计算。若工程选择每方法单独reset/replay，则正式应计294次bank恢复＋1176分支=1470，含上述预检为1520，已超过TASK规定1500新scope，必须在新TASK中改预算，不能记成1274。失败/重试/额外恢复全部先记账，不冲销；本方案没有新初始化替补。原2个无报警源保留100分母及已知共同结局，无新增分支。

成本分别实测共享restore、每方法完整生成墙钟（自身a0＋critic特征/objective＋自身guided采样或post梯度＋自身匹配）、最终评分/身份审计、分支restore/suffix、加载与整波墙钟。GPU同步后计时，保存VLA采样/denoise/objective成员forward/backward计数、fallback和峰值显存。post约一个objective forward/backward，V/D原三时刻约6 forward/3 backward，四成员与额外评分分开计；以真实计数为准。禁止把旧post单个梯度耗时当独立总成本；禁止把一次共享a0当三个方法都已重采。可以分别列“本次观测下完整生成”和“若单独运行加一次恢复”的成本，后者明确为组合值，不能伪称三次独立恢复实测或串行加速。

**正式新READY必须明确的字段。** 已发布 `STANDALONE_ABLATION_TASK_20260918.md`，后续使用独立 `STANDALONE_ABLATION_ANALYSIS_READY.json`，保持原NATIVE10 READY v14不变。工程准备、真实预检和正式采样分别授权，不能从version号或旧held scope推断权限。

| 字段组 | 必须绑定的实际内容 |
|---|---|
| task/authorization | task path＋SHA、READY精确字节SHA、scope→stage显式映射、locked stages |
| inputs | 原100ID与顺序、98cut/2common及source/cut/context/queue/scene/旧bank/旧五臂seal；旧collection protocol与新protocol分列 |
| models | A4000 selected seal、四权重/PCA、VLA/D/G0/transform与实际runtime dtype/线程/软件版本 |
| science | 原完整固定参数、自身半径公式/零组/内缩、无其他方向依赖、各入口重新采a0、原fallback处理与计数规则 |
| random/pairing | 原namespace、candidate_index0、4repeat、suffix decision index、100源完整分母、无capture/替补 |
| budget | 旧ledger SHA＋48183/51200基数、新ledger/锁路径、预检/正式/技术余量、总新cap≤1817、合并50000/0新优化 |
| entry/freeze | 新代码/test SHA、必要CPU结果seal、调用隔离证据、真实预检完整seal、不可变输入清单含所有授权原件/快照 |
| analysis | 预登记比较族、主要/次要比较、方向、任务内整源bootstrap排序/seed/draws/区间、多比较口径及禁止事后选优 |
| lifecycle | 全波GPU预留、hold_idle=false、加载前释放holder、整波退出后恢复8holder；不得自动新波 |

TASK已固定三个共同主要比较：solo_post/direct/velocity分别对R；各报95% CI，同时报三比较Bonferroni家族98.333333%区间，分位点为0.05/6及1−0.05/6。次要比较为三个solo分别对各自旧matched、分别对normal，另列旧R−N来源明确的参照。全8方法共同作任务内整源bootstrap10000次，seed=2026091801，percentile/linear；不能沿用旧seed代替本轮CI。家族结论以调整区间为准并注明bootstrap近似；区间跨0不等于等效或非劣。own-only同时改变幅度与零组，不能把solo−matched差异单独归因为flow梯度入口。A4000仍由混合候选训练；仅部署分支独立，不能声称训练数据与其他方向无关。不得根据中途结果改半径、选方法、丢负例或补源。

**证据。** [机器可读准备与100源绑定](STANDALONE_ABLATION_PREPARATION_20260918.json)保存完整SHA、5源预检清单及预算草案。[新任务状态](STANDALONE_ABLATION_EXECUTOR_STATUS.json)记录接单、holder与0新增资源。

- 原账本及held审计账本快照SHA均为 `3f293430a26d7c0405c33b797788fdfd099f3b8d0a42aec7c37a89338a4ef552`。
- 原held config/freeze：`d86dc14afddf81a37587ff020cd36cc07e85869bf315502dc1778a97bda8f795` / `a2db97fd0c76650e730b58836b0cd6059d25c76f42e5da4e2ce06611784d11b8`。
- 原100ID canonical：`f05bbfeb92da78d8fb9242bd28b116cf6f5a4cff252b5ad0487506e0bd108afc`；本准备source绑定：`ee761d22e0a7009de1bc27bea446abca084d02de7104a1bc58b5a33a4cdc1a8e`。
- 原held审计seal：`d776f54ceb94879bc1945a6e5e02736d04ba9d7e4652e02e06280be3a85a833e`；scene快照为900个accepted，held100与原800同任务物理指纹无交集。
- 代码依据：`src/corrector/candidates.py:12–40`；`experiments/native10_training_20260916/engine.py:103–151`；`main_collection.py:396–526`；`adapter.py:124–152`；`protocol.py:135–155`；`storage.py:67–114`。均只读引用。

新TASK精确绑定：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/coordination/STANDALONE_ABLATION_TASK_20260918.md`，SHA `7d5a3e55b907c0a65f095189cb155914150703473a9f8d5f49066122211a75be`。当前实际下一步是新隔离实现、必要CPU与future-ready契约，属于TASK已授权的工程范围；真实模型/预检/正式波次仍等待绑定实际材料的新READY。当前无技术或环境阻断，本次准备新增计算资源为0。
