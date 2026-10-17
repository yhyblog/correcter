# A00 资产盘点回执（A，revision 1）

结论：A00完成；完成前CONTROL v3已发布P00_PREP_V1并放行A10/B10工程准备，正式训练、推理或仿真额度仍为0。A00交付后核对下一任务合同。
已存在的π0.5-MT50完整SFT、五任务D/G0/Q、train600、MT50示范与LIBERO推理权重可作为新任务输入候选；这不等于新比较协议或全MT50 Corrector已就绪。

| 资产/能力 | 当前可用事实 | 缺口与边界 |
|---|---|---|
| A主机/GPU | trial-303224955-trialrun-303224955-worker-0；8×H100 80GB；驱动535.161.08；224逻辑CPU | 未见正式项目计算；GPU进程PID全部匹配本机guard |
| occupancy | guard PID27508；8/8 holder，每卡1013MiB、49–50% | /tmp锁是本机的；guard两个日志为共享根目录固定路径，A/B不可用混合日志判断本机状态 |
| π0.5-MT50 SFT | 持久030000/pretrained_model全7文件，9,354,084,596B；6小文件SHA匹配，9.354GB权重尺寸匹配 | 大权重只引用既有SHA，未重新全量hash；旧/tmp推理缓存缺失 |
| MT50示范 | 497文件全部存在且尺寸匹配；492 Parquet；2500 episodes/204806 frames | 历史全量数据审计证明50环境、每环境50示范；49是语言task index数 |
| 五任务D/G0 | spatial_pair_241/242各选finetune400；gate341/342选1000/1200；文件存在 | G0仍是旧execute5收益目标；不能当作已校准的nativeH/C10收益或全MT50适配 |
| Q与PCA | A4000四成员小权重SHA全部匹配；A沿用原成员PCA；B另有train600 PCA审计 | 部署solo不代表训练独立；Q仍是五任务混合候选训练 |
| train600 | 两轮各300、每轮每任务60；31,200候选二值标签+2,400 normal标签 | 公共池字段不完整；需新合同和采集/视图适配 |
| vla-corrector复现 | commit 9d23a0b，tracked clean；best_cosine epoch30与配置在；Very Hard80/100、Hard71/120为历史结果 | 原按frame-pair随机90/10划分；不能宣称与本轮episode分组及共同数据相同 |
| SmolVLA-MT50 | 独立环境、初始化、005000…050000检查点；最新保存step50000 | 原100k队列signal15中断；未见完成100k或正式Smol评测回执，不能标“训练完成” |
| X-VLA-MT50 | 固定源码、独立环境、base与seed42初始化完整 | 标准正式runs位置未见X-VLA训练/评测完成产物 |
| π0.5-LIBERO | 30k训练完成；29999的params/assets保留18文件均尺寸匹配；四套件2000 episode完成 | train_state大文件已历史清理，不能用旧archive-manifest声称可恢复优化器 |
| 缺失旧资产 | pi05-base链接指向缺失piper-work；旧SigLIP token latent链接断裂 | 不影响完整SFT目录的存在；重训旧baseline需新提取或恢复latent，A00未执行 |
| 环境/入口 | lerobot、Smol、X、openpi、LIBERO五解释器元数据探针全成功；Mesa库在 | 只做CPU元数据/语法检查，没有CUDA、渲染或模型可运行性测试 |

路径约定：R=/mnt/bn/arnold-recommend/yaohaoyang；W=R/embodied-ai-workspace；N=R/Corrector/outputs/native10_training_20260916；V=R/vla-corrector/outputs/metaworld_very_hard。
逐资产完整路径、存在性、历史hash来源和本次核验层级见同目录A00_ASSETS.json；详细CPU证据在../../work/A/A00_r1/。

## 1. 迁机输入与embodied-ai-workspace关系

- W是物理目录和符号链接混合索引，不是可独立拷贝的完整备份。本次顶层55入口，7个断链；其中Corrector相关主要是pi05-base及旧latent，其余为Piper旧资源。
- W/projects/vla-corrector、W/models/vla-sft-030000、W/datasets/metaworld-mt50指向VLA原项目持久路径；Corrector复用其π0.5与环境，并从ACT-RECAP取D/G0与运行适配。
- B若共享同一持久挂载可直接核对W/models/vla-sft-030000；不应把A的/tmp路径或PID当成B的现状。
- 推理迁移必须带全7件：config.json、model.safetensors、train_config.json、policy_preprocessor.json、policy_preprocessor_step_2_normalizer_processor.safetensors、policy_postprocessor.json、policy_postprocessor_step_0_unnormalizer_processor.safetensors。
- 完整SFT权重历史SHA=dff338a91dbe534ca3c4525ba82df9324662e3c87131f42ed6e3d1b7bf0e94d4；证据W/manifests/vla-baselines-20260911/legacy-pi05-mt50.files.json。本次核对7件尺寸和6小件SHA；大权重身份尚非迁机后重hash证明。
- 另需固定VLA代码/复现脚本、tokenizer白名单、处理器和归一化、D/G0模型及normalization、Q完整selected目录、新campaign配置与source manifest。继续SFT还需要optimizer等training_state，不能只拿推理目录。
- 五环境分别为Python3.12/Torch2.7.1/TF5.4.0的legacy；Python3.12/Torch2.7.1/TF4.57.1的Smol与X；Python3.11/JAX0.5.3/Flax0.10.2的openpi；Python3.8/MuJoCo3.2.3/robosuite1.4.1的LIBERO仿真。
- Smol/X虚拟环境依赖.miniforge3/envs/lerobot，openpi依赖.miniforge3/envs/piper-wine，LIBERO依赖W/cache/python的3.8基座。独立迁移不能漏掉这些解释器基座和editable源码。
- ACT-RECAP HEAD=3063947且有既有tracked修改，Corrector本身不是独立Git仓库；新协议应绑实际文件SHA/快照，不能仅写Git HEAD。

## 2. 公共训练池与split事实

- N/input_bundles/final_train600_input_v1/manifest.json是合并输入身份；N/datasets/round1_train_full_v1与round2_train_full_v1各有arrays.npz、rows.json、metadata.json、complete.json。
- arrays含history[5,4096]、proprio[5,4]及mask、past_actions[4,4]、language[2048]、remaining、13×10×4 raw/bounded actions、13×4 outcomes、alias/pair权重、物理attempt IDs、episode/task/split/cut/round；normal的4次结果单独存control_outcomes，不是a0槽。
- a0是新重规划计划；normal保持原队列。bank下plans.npz保留13个50×4计划；generation/metadata保存噪声与生成器身份。
- N/sources、N/banks、N/rollouts保留原始树。已抽查源和a0后缀trajectory.npz：逐步action、reward、success、done、physics_state、完整生成计划和sampling seed确实存在，不是只有终局均值。
- 这些trajectory没有逐步RGB/next RGB/完整模型观测，done合并了终止语义，未分开terminated与truncated；不能把MuJoCo真实state当作合法观测。离线补图/特征如需恢复环境或编码要另计正式成本。
- 外部VLA-Corrector需要(t,t+10)的256×2048 token级latent；Q的4096维cut聚合特征不能直接替代。旧101GiB缓存缺失，底座/示范仍在，新提取或共享轨迹视图由P00/P10定义。
- 原实际主源为train600/dev100/cal100/held100，另P0=20；2720注册记录包含备用，不能当作实际完成源数。dev有效cut95，其他5源保留共同终局。
- 同一episode及其cut/候选/后缀归同一split；held已揭晓，禁止回流新训练或充当新独立测试。原MT50示范元数据只有train集合，新共同池仍需显式episode级划分。
- π0.5 SFT使用完整MT50示范、seed1000、30000更新；已有2500-episode MT50正常策略评测run.json为complete。旧五任务D/G0/Q及local labels不证明其他45任务或H20/30/40/50已适配。

## 3. 外部baseline与E8现状

- 先读了R/vla-corrector/reproduction/metaworld_very_hard/HANDOFF.md与RUN_LOG.md，再针对split/接口读实现。
- 旧VLA-Corrector：MLP 20m、42,509,568参数、h1/k10/action4、cosine loss、30 epoch、batch512、seed42；179806个episode内合法frame-pair按random_split分成161826/17980，非episode分组。
- 可用旧入口04_eval_very_hard.sh：π0.5生成50/正常执行10、预算300、k10、eta1、attract_delta_z_correction、apply_every1、cooldown10；不能用其旧连续seed或旧对照直接完成新E3。
- Smol/X复用W/projects/vla-baselines/launchers/runtime.sh及eval_metaworld.py；Smol生成50、X生成30且环境4维/内部20维。新P/V需要各底座flow/action映射，不能只换checkpoint路径。
- LIBERO复用serve_pi05.py+eval_libero.py的GPU服务/CPU环境分离接口；JAX、7维动作、双相机/任务文本、归一化与MW不同，P/V需要独立适配。
- LIBERO最终1933/2000=96.65%来自已发布summary；只表明旧底座验收完成，不是本方法E8的结果。29999保留清单优先于清理前archive-manifest。
- 旧baseline README仍写“仅准备”已过时：以9月13/14实际queue状态、保留清单及最终summary为准；历史machine-A/B与本轮A/B身份不可混用。

## 4. A10接口工作量（仅建议，未改旧实现）

| 新接口 | 现有位置/事实 | 建议准备单元 |
|---|---|---|
| nativeH与C10分离 | native10/semantics.py的Native10Queue使用固定HORIZON10；snapshot/prefix/合法cut也绑定它 | 新隔离队列+恢复序列；五H正常周期、C10干预及恢复nativeH的CPU边界检查 |
| source/restore/branch | native10/main_collection.py及standalone/collection.py校验/写死source与suffix10 | 新capture/restore schema与source ID；跨H只配初态、同H配cut；不复用冻结collector直接跑新协议 |
| standalone P/V | standalone/engine.py已有独立生成、失败日志和1/2调用事实，但绑定A4000/旧OGG | 提取新接口并显式绑定新模型与协议；数学保持分析端定义 |
| 完整调用和时间 | _JournalRuntime.native_action记录enter/return/error，generate_solo记录组件耗时；旧trace只聚合部分时间 | 统一episode/source/bank/suffix调用账本，分开VLA采样、flow前向、D/G0/Q及CUDA同步事件计时 |
| 原始transition与统计行 | main_collection trajectory与summary已有actions/rewards/seed/配对ID，缺完整观测和终止区分 | 观测/next观测引用、terminated/truncated、success_step、执行prefix、host/shard/H/C、model/data/code SHA、失败和资源逐源行 |

工作量按上述5个准备单元核价，另有跨主机路径/日志与资产绑定1单元；A10做CPU接口验证和成本报价，P00先固定数据字段/分组/方法，P10才冻结正式数量与上限。

## 5. 数量与资源估算口径

- A00实际simulator_attempts/completed_rollouts/vla_sampling_calls/optimizer_updates/gpu_seconds全部0；既有AGENTS占卡不属于本任务实验计算。
- 采集attempt按capture、bank恢复、每个物理分支含恢复、预检、技术失败分别累加；不可用逻辑结果单元数替代物理attempt。
- 若沿旧13候选+normal、每项4后缀，完整cut源示例为1 capture+1 bank恢复+14×4分支=58 attempts；此例不是新协议数量承诺。
- E4有16逻辑单元；50任务、每任务n初态、K后缀时逻辑规模为50nK×16，E3再加50nK×2。跨方法源恢复、无报警复用、早终止和故障另作实际attempt账；n/K未发布。
- 每条未提前结束nativeH轨迹的普通完整采样参考上界为ceil(300/H)=30/15/10/8/6；报警会改变节拍。每个独立干预入口R/P/V采样1/1/2；prefix恢复、后缀和失败进入同一总账，不能只报入口常数。
- 优化按实际完整训练seed×ensemble成员×每成员更新累加；E1四损失×建议3seed不等于四成员ensemble。D/G0/Q及外部模型更新上限、数据规模、存储预算、失败/重试上限仍待P10。
- 旧49507/50000的493余额不转作新预算；历史并发耗时不可作为A/B受控加速比。A的/tmp当前约2.81TiB可用，存储/加载与采集成本需由新受限预检报价。

## 6. 审计范围、失败与下一步

- 17个实际存在的Python/shell入口通过AST或bash -n；初始猜测native10/collection.py不存在，正确实现是main_collection.py，已检查，未执行模型代码。
- G0两件与Q四件small checkpoint SHA匹配；已核查清单的MW497、SFT7、LIBERO970、Smol初始化6、X初始化6均存在且尺寸一致，小文件hash无漂移；LIBERO最终保留18件同样通过尺寸/小文件检查。
- 轨迹字段为源+后缀样本及压缩数组header核查，未重新执行旧全量统计/仿真审计。大型权重没有重复hash，完整新机模型/渲染可运行性未声明通过。
- CONTROL从v1变v2、v2变v3时本地严格revision门分别让node probe及发布器退出1；前者登记B身份，后者发布A10/B10零计算准备。重新读取确认A00正文/SHA及授权未改，改为每批核对A00身份、范围及零预算后继续。另git -C Corrector rev-parse退出128，已确认无独立Git，改用文件SHA。均未触及模型/仿真。
- 只写nodes/A、receipts/A和work/A；未改CONTROL/TASK_BOARD、旧封存/READY/环境/权重。建议新P00/A10采用上述字段、split及路径结论；交付后读取已发布P00_PREP_V1及A10任务书，不自动启动任何正式计算。
