# B00：服务器 B 资产与环境盘点

| 项目 | 实际可用情况 | 缺口 / 本轮判断 |
|---|---|---|
| B 身份 | `trial-303225685-trialrun-303225685-worker-0`；会话 `01a0b9c5-1e4b-7b73-9336-229e6df349a2` | 与 A 不同；CONTROL revision 2 已登记相同身份 |
| GPU / CPU / 内存 | 8×H100 80GB HBM3，每卡 81559 MiB；驱动 535.161.08；224 CPU，双 Xeon 8480+；主机可见内存约 1.97 TiB | GPU 环境仅做只读查询；未做模型 GPU 加载或推理 |
| 占卡与共享挂载 | 8 卡 holder 正常，约49–50%；本机 `/tmp/gpu_occupancy_guard`；ByteFuse 共享根可读写并完成 B marker 回读 | guard 的工作区日志路径 A/B 共用，有混写风险；本机 PID/status 和本报告主机快照才作为 B 状态依据 |
| 本地临时盘 | `/tmp` 为本机 ext4/NVMe，约 3035.6 GiB 可用 | 旧 `/tmp/act_recap_future_aware_20260914/checkpoint_cache` 在 B 不存在；两个旧 processor 引用已找到共享同 SHA 文件，不复制 A 的临时目录 |
| π0.5＋MT50 | `models/vla-sft-030000` 指向共享真实 SFT 030000，7 文件大小及6个小文件 SHA 通过；safetensors 头与文件长度匹配 | 大模型全量 SHA 本轮未重算，GPU 功能与本轮 MT50 纠偏适配尚未验证 |
| VLA-Corrector | `models/vla-corrector-h1-k10` 中 config 与 best-cosine 存在；CPU 权重读取32 tensors、42,509,568有限参数，完整 SHA 与交接一致 | 旧 `latents_pi05_mt50` 已缺失；不重跑原 SFT/复现；共同数据新训练需要新 latent 视图及单独预算 |
| SmolVLA＋MT50 | seed42 的 `050000` 权重和训练状态可读，training_step=50000；配置、归一化和模型头齐全 | 未发现100k完成权重；历史队列为 interrupted。50k是部分训练资产，需指挥端决定是否锁定使用或另派恢复任务 |
| X-VLA＋MT50 | base 与 MT50 seed42 初始化均存在，初始化6文件检查通过 | 权威 workspace `runs/metaworld/xvla` 不存在；未找到训练完成的 MT50 checkpoint，不能把初始化视作完成适配 |
| π0.5＋LIBERO | 官方参考16文件、自己训练29999推理保留18文件均存在且大小/小文件 SHA 通过 | 29999包含30k最终推理权重；中间 payload 和优化器已按旧清理单删除，不能按旧 archive 声称可恢复训练 |
| LIBERO 四套件 | Spatial/Object/Goal/Long(`libero_10`) 的环境与970文件资产清单通过；40任务映射存在 | 需新的 Corrector 特征/动作接口；官方和本地 SFT normalization 不同，严禁互换 |
| 训练原始数据 | MT50 2,500 episodes / 204,806 frames / 492 Parquet；LIBERO 1,693 / 273,465 / 1,693 Parquet，下载清单1699文件检查通过 | MT50 49个语言索引对应50环境，属既有映射；当前B只核元数据/样本schema，未重做全量图像解码 |
| 五任务600源 bank | 实查600源、每任务120；动作 `(600,13,10,4)`，结局 `(600,13,4)`，历史/语言/本体等26字段 | 无逐步 next观测、reward、termination或首次成功时间字段；不能直接当成GAF/QGF完整轨迹视图 |
| GAF / QGF | 官方 README、GAF-v1目标及两者训练代码已只读核对 | 在工作区根、projects/upstream、环境入口中未发现对应 clone/专属环境/已训练 critic；B10需冻结 commit，未下载部署 |

以上均是本机盘点结果；旧实验配置、历史结果和权重没有更改。正式资源计数：训练更新=0、VLA采样=0、模拟尝试=0、完成rollout=0、实验GPU秒=0。后台占卡按既有政策继续，单列为非实验活动。

本回执 campaign=`corrector-sim-20260919`，task=`B00`，revision=1。工作区根为 `/mnt/bn/arnold-recommend/yaohaoyang`；表内 `models/...` 相对 `embodied-ai-workspace`。共享读写证据为 `nodes/B/shared_mount_marker.json`；A00 ACK 可读，盘点期间 A00 最终回执尚未发布，未阻塞独立核验。

## 环境与可复用入口

| runtime | 当前 CPU 可读版本 | 入口/边界 |
|---|---|---|
| mw-pi05-legacy | Python3.12.13、Torch2.7.1、Transformers5.4.0、LeRobot0.5.1、MetaWorld3.0.0、MuJoCo3.6.0 | 共享 `.miniforge3/envs/lerobot`；CPU torch2.7.1+cu126读取权重通过 |
| mw-smolvla-lr044 / mw-xvla-lr044 | Python3.12.13、Torch2.7.1、Transformers4.57.1、LeRobot0.4.4、MetaWorld3.0.0、MuJoCo3.6.0 | 独立 prefix，仍依赖共享 lerobot Python 基座 |
| pi05-openpi-jax | Python3.11.14、JAX/jaxlib0.5.3、Flax0.10.2、Optax0.2.4、Orbax0.11.13 | 独立 prefix，引用 piper-wine 基座；无 GPU 后端调用 |
| libero-sim-openpi | Python3.8.20、MuJoCo3.2.3、robosuite1.4.1、LIBERO0.1.0 | 独立旧仿真环境；仅metadata/spec检查，未实例化环境 |

`projects/vla-baselines/launchers/runtime.sh` 按环境隔离；`eval_metaworld.py`、`serve_pi05.py`、`eval_libero.py` 可作为新适配入口。配置固定 Smol H50/K10/4维，X-VLA H30/K10/4维（内部20维、domain0），LIBERO H10/K5/7维动作、8维state、双图；新release必须明确保留或改变这些值。MetaWorld的300步/4维半径不能照搬到LIBERO。

四个源码 HEAD 已登记：VLA-Corrector `9d23a0ba6fad562d3ed1a68fc52c8a12459abb41`；两套LeRobot `8fff0fde7c79f23a93d845d1a50e985de01f8b8a`；openpi `215abfb217dbac7d5f1273282331b9b1866c0479`。另保存实际读取代码文件 SHA，HEAD 不替代工作树文件身份。七个入口AST解析通过。

## 基线建议与数据视图

建议优先准备 **GAF-v1，π0.5/MetaWorld适配**；这是基于数据字段和PyTorch工程的建议，尚非锁定发布。保留 discounted success-to-go、MSE、episode级split、独立critic ensemble、梯度裁剪/门控及冻结底座；变化项是底座/环境、policy-side state与文本特征来源、物理动作4维、实际执行chunk和reverse-time采样接口。现有13候选四次终局标签不能代替首次成功时间；不退化成BCE或冒称v3。依据：[v1 §III-D/E](https://arxiv.org/html/2607.02092v1)、[公开训练入口](https://github.com/ylhaichen/guided-action-flow/blob/main/scripts/train_critic.py)。

QGF保留作备选：公开工程为JAX/OGBench，训练包括chunk IQL的Q/target-Q/V、expectile及TD目标；迁到现有PyTorch π0.5需要明确跨框架梯度桥或经等价检查的实现，不能仅把现有direct引导改名。需要连续观测、真实执行长度、逐步/聚合奖励、next观测、终止与截断；生成50条但只执行10条不得构造虚假的50步转移。依据：[官方README](https://github.com/zhouzypaul/qgf)、[QGF损失实现](https://github.com/zhouzypaul/qgf/blob/main/agents/qgf.py)。GAF-v3视觉Transformer完整代码尚未确认；QPILOTS不纳入本轮必跑。

MT50示范样本schema已有 `observation.image/state`、`action`、`next.reward/success`、episode/frame索引，可从同episode后续真实帧建立正常动态视图；`observation.environment_state`为特权信息，禁止进入部署输入。其首次成功/终止边界仍需B10逐episode审核。LIBERO固定SFT有图像、state、actions和索引，但无同名reward/success/terminal列，不能臆造失败轨迹或成功时刻。

600源bank可直接支持冻结范围内E1损失矩阵的输入审计，不需要为已有候选标签重采。GAF/QGF缺失的真实后续字段若在原轨迹档案中存在，只需索引；不存在则只能在已分配的共同采集波次记录，不能从终局均值补出时序。当前只检查bank字段，未声称全历史原轨迹均缺失。相同原episode的所有cut/候选/后缀必须整体分组，测试日志不得回流训练。

VLA-Corrector共享检查点保留h1/k10、token_dim2048、action_dim4与既有cosine动态预测目标；正常示范视图和新公共池的筛选规则需单独登记。现有权重训练历史不得写成与新critic完全相同数据；latent缓存缺失只影响新训练准备，不否定保留模型资产。

## E6与B10准备清单、估算

E6优先评估复用既有D的5步预测：在`t-5`保存预测及实际待执行动作，真实`t`观测到达后计算预测误差，只有预测对应的动作确实连续执行且未跨reset/分支时才打分；接同一下游R、相同合法cut、每episode最多一次。固定开发集阈值及预热规则后再测试，不用未来观测提前报警，也不用G0分数改名为异常。

可替代的旧LVM接口是 `src/siglip_dynamics/inference/safety_module.py::predict_delta_z` 与 `circuit_breaker.py::compute_error`（余弦误差）；现模型k10和既有动态阈值需对齐新5步监测协议，不能直接宣称已可比。B10只选择一个异常触发器，保留是否缺预测/动作对齐失败等诊断。

以下是工程工作量粗估，非授权GPU预算或已测吞吐；以P00输入合同为前提。

| B10子项 | 估计工程时间 | 新增采集 / 计算依赖 |
|---|---:|---|
| 公共episode视图、split/实际prefix校验；VLA-Corrector接口 | 4–8小时 | CPU可先做；缺失latent再提取需单独模型调用额度 |
| GAF-v1版本冻结、状态/语言/动作映射和采样hook契约 | 8–16小时 | CPU接口可做；共同rollout需success时序，不另采私有池 |
| E6因果预测误差接口、开发阈值规则；E1四损失配置 | 4–8小时 | E1旧600源可复用；四损失×建议3训练seed=12训练run，非现在启动 |
| E8 Smol/X适配与checkpoint口径 | 6–12小时 | Smol50k使用/续训需决定；X-VLA完成模型缺口需另派任务 |
| E8 LIBERO JAX引导、双图/7维动作、suite规则 | 12–24小时 | 底座推理权重/数据现成；D/G0/Q跨环境训练与特征预算未给定 |

公共训练源数量、每源后缀、更新上限和吞吐未冻结，不能报可信总GPU小时。后续报价按 `训练updates×秒/update×GPU数`、`每源实际调用及仿真步数` 分列，未知值保持null。现有LIBERO正常示范无需重采；重建旧latent历史规模约101GiB是旧交接估计，B00未生成。Orbax正式训练需本地POSIX staging后共享校验归档，B当前临时盘空间足够准备但不代表获准训练。

当前仅B00放行；完成后保持待命并检查CONTROL/TASK_BOARD。B10及其后任务须满足最新依赖/release，正式GPU波次全机停holder并用生命周期包装，联合波次还须遵守完成屏障。

## 证据范围

结构化资产入口：`receipts/B/B00_ASSETS.json`；原始CPU/硬件/清单检查及输入快照在 `work/B/B00_r1_trial-303225685-trialrun-303225685-worker-0_20260919T145623Z/`。重点文件：`host_inventory.json`、`environments.json`、`physical_paths.json`、`asset_verification.json`、`extra_asset_verification.json`。

8份清单共3219条文件记录完成大小核验，955条小文件记录重算SHA，无缺失/不符；大数据/大VLA权重只核大小及部分header，未声称全量哈希重验。VLA-Corrector的170MB权重另外完成全SHA及CPU有限性检查。未安装依赖、下载大型资产、修改公共代码/环境或运行历史实验。
