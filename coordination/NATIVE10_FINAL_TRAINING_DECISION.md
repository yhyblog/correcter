# 最终 600 源 A/B 训练：分析端阶段决定

2026-09-17 UTC。本决定须与后续 READY 的真实预检与审查 SHA 绑定后生效；文档单独出现不启动 fit。保持全部旧封存、数据、方法与数值约定。

## 真实预检的分析判断

本次实际预检已执行，而非仅 metadata preview 或合成测试。pipeline 产物为 `outputs/native10_training_20260916/fit_preflight/final/final_preflight_v1`，seal `eb1e39d4ee145ebecce9b16593a9c1fd901fd7dcc2a5c9e8746f657e4c202d3e`，result SHA `d693a7d1fa4f1d5a0be4f2141966f35d97390e6e427c4c5cb6803bfc8791c79d`；执行 seal 为 `d2ba158591ea7fee9c9caca75e7ad2fc2f9b236c3709a35344512d6ab14ec23d`。

报告覆盖 A/B 全八成员、600 有效 train 源与 95 有效 dev cut。canonical 同 shape 特征/13 候选概率/槽 0 与 11 成员及集成动作梯度导出重载严格通过。dev 的 5 个无 cut 源仍保留在原 100 源选模分母内。

真实 dense 与 singleton 的最大绝对差如下，合并 train/dev 及成员报告：

| 路径 | 投影特征 | 候选概率 | 成员动作梯度 | 集成动作梯度 |
|---|---:|---:|---:|---:|
| A | 1.49012e-4 | 1.82986e-5 | 2.52128e-5 | 1.15633e-5 |
| B | 2.84752e-4 | 3.57628e-7 | 1.16415e-8 | 4.65661e-9 |

观测原特征差为 0；报告中全部计算有限，状态/a0/动作/权重保持不变，a0 相对优势为 0，梯度按源求和且不存在额外 1/N 缩放。按既定数值决定，dense 的跨 shape 非逐位一致作为真实诊断保留，不能宣称其 bitexact，也不据此引入新阈值、修改 PCA floor、改损失为逐源执行或推断所有近零梯度方向都不受影响。canonical 选择/部署路径保持不变；训练沿用原 batch loss。

预检为 0 仿真、0 优化，账本逐字不变，累计 42,874 sim / 19,200 optimizer。A 旧资产身份、B train-only PCA/初始化、八成员 bootstrap/minibatch/masks 的独立审查须通过并随 READY 绑定。不存在需通过额外预检反复运行来寻找更好初态的授权。

## 正式训练唯一释放范围

- stage：`training_final`；scope：`final_critic_training`。
- 新增仿真上限 0；新增优化上限 32,000；工作流优化硬上限 51,200。
- A/B 两路径各 4 成员，每成员最多 4,000 更新。既定检查点为 200、400、800、1600、2400、3200、4000，不新增密集搜索或重复训练。
- 采用当前封存的 600 train 联合包与原 100 dev；两轮真实 collection/生成 critic 身份保留。每任务 120 个训练源，按源等权，按任务的 source bootstrap 与源内候选/正反组去重规则不变。
- 必须复用本次真实预检已封存的 PCA、变换、全部初态权重、bootstrap、minibatch 依据与 trainable masks。禁止重拟 PCA、重新随机初始化或另选采样计划；允许按既定种子重建后与封存序列逐项核实。
- A 学习率 1e-4，仅既定 residual/advantage 开放更新；B 学习率 3e-4，既定小 critic 全 MLP 更新。大 VLA、D、特征提取器保持冻结。
- 损失沿用 BCE success + 1.0×相对 a0 概率增益 MSE + 0.5×正反概率差 MSE；AdamW weight decay 0.01、梯度裁剪 1、batch 32 完整源。不得根据并行训练监督诊断更改权重、样本权重、cut 或候选。
- 使用同一 lerobot CPU float32、2 线程 runtime；训练不占用 GPU，保持 holder。任何改变计算设备/线程/数值方法须明确技术审查，不因追求更好开发收益临时切换。

## 选模与科学解释

全部固定 A/B 集成检查点共用原 dev 候选银行，按原规则选择唯一 critic：每源预测平均成功率最大，a0 赢得平局；最大化完整 100 源配对净增益，其次更少损害、较小 gain MSE、较早检查点，最后优先 B。5 个无 cut 源保留共同结局。该规则不因数据扩大而改为选最后一步，也不因当前最好结果较小而追加训练轮次。

较大训练规模的实质是 600 个独立状态及两轮方向上的真实标签；31,200 个候选结局不是同等数量的独立状态。训练方向诊断用于判断信号稀疏性及后续解释，不是本次新选择门槛。原 dev 经多阶段方法开发，候选银行选模仍只是连续 flow 引导的代理指标，不能据它宣布独立成功。

## 执行与交付

独立 final-fit config/freeze 须绑定当前 READY、本决定、真实 preflight/input/specification/初态资产、实际代码与既有验证证据。预检装载校验通过后，在该冻结下直接执行一次，不再请求重复许可。原 preflight、旧 round1 fit 或任何采集均不重跑。

完成后交付全部固定检查点、唯一选择及排序理由、实际可训练/冻结参数检查、所选模型 canonical 概率/梯度重载、逐成员优化账本及总资源、成本与 seal。不得根据中途收益换配置或提前运行策略测评。

本次不释放 `round2_development_policy`、calibration 或 heldout。最终模型训练与独立审查完成后，分析端再决定已登记的第二次 100 源五臂开发策略测评；所有后续测评仍保持每任务 20 个不同物理初始状态。
