# 三种纠偏的数学、坐标和执行语义：冻结实现复核笔记

2026-09-17。面向完整中文算法文档的实现依据；不包含新实验或方案修改。

## 0. 复核范围与最重要的结论

以最终 calibration_v1 与 heldout_v1 为准，两份冻结 config 的 guidance、matching、command_semantics、三种 horizon、generated_horizon、control_budget 和五臂列表逐对象相同。最终固定 critic 为 A4000 的四个成员。

- R 是四成员**成功概率相对固定 a0 的平均差**，最大化；没有 LCB/UCB、方差惩罚或 Q 门。
- velocity 与 direct 都切断原 VLA 速度网络的梯度；它们只对当前速度副本或 clean-action 副本求导。
- velocity 注入含 τ，direct 不含 τ；因为采样时间倒着走，速度上减去梯度对应 Euler 状态沿正梯度移动。
- post 从完整无引导样本的首十步求一次梯度，乘 S²得到方向，再经过共同匹配；它没有额外的 α=10 梯度步。
- 最终执行的是 matched V/D/P。即使固定部署 post，匹配半径仍依赖 V、D、P、反向 D、随机这五个方向；删除其余方向会改变当前算法。
- 评分使用 C(raw)=clip(raw,−1,1)，执行保留 raw 命令。饱和、贴边及 raw 超界坐标不被纠偏改动，不能把 raw 全部裁剪后再声称执行完全相同。
- 13槽训练候选中的 reverse_post 与共同匹配中的 reverse_matched 含义不同，前者反向 post，后者反向 direct。

[held 冻结配置](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_protocols/heldout_v1/config.json) SHA：
d86dc14afddf81a37587ff020cd36cc07e85869bf315502dc1778a97bda8f795。

[cal 冻结配置](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_protocols/calibration_v1/config.json) SHA：
c04125ae474316783e7dd6ca74c799d5441299801f22cd0910889f98511d7382。

本笔记涉及的 Corrector 核心和实际执行源文件已与 held freeze 中相应 SHA 对照；PI0.5 sampler 与三个实际 runtime/backend 文件也一致。round2_collection_v1 不属于 held 引用清单，额外核对的是其原 round2_v1 freeze，亦一致。没有导入模型或执行采样。

## 1. 明确区分三种坐标与两个 a0

设真实报警状态对应的固定观测上下文为 s：

1. **flow 内部坐标**：x_τ∈R^(50×32)。一次采样生成50步内部表示；只取前4维作为动作。纠偏目标只看首10步×4维。
2. **raw 环境命令**：无引导样本经原 postprocessor 反归一化后的 a₀^raw∈R^(50×4)。XYZ 是原 MetaWorld 控制命令量纲，不能直接写成米；夹爪是第四维控制命令。raw 可以超出 [−1,1]。
3. **critic 的有界命令表示**：b=C(a₀^raw)，其中 C 是逐元素 clip 到 [−1,1]。固定锚为 b 的首10步。

报警前队列中的旧计划，和报警后从当前状态重新采样的 a₀^raw **不是同一个东西**。正常继续臂保留旧队列；重规划及三个纠偏臂共享新的 a₀^raw。文档若只写 a0，必须说明指哪一个。

反归一化与评分变换为：

$$
S_j=(q99_j-q01_j)/2,\qquad
\mu_j=(q99_j+q01_j)/2,
$$

$$
A(u)_{t,j}=\mu_j+S_j u_{t,j},\qquad
T(u)=C(A(u)).
$$

这对应正常非退化分位数差。代码在 ActionTransform 中对 q99−q01=0 的维度以 eps 替代差值；post 的 S²则直接用原差值，因此该退化维度的 post 方向为零。不要把两处退化分支写成完全相同的斜率实现。

实际引用：
[ActionTransform.forward，22行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/actions.py:22)；
[make_bank 中 raw、bounded 与固定目标，103行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:103)；
[raw 执行语义，semantics.py 1行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/semantics.py:1)。

## 2. 四成员 critic 的 Q 与引导目标 R

记第 m 个冻结 critic 的 logit 为 z_m(s,a;b)，动作输入是首10步×4维，且候选槽0固定为 b。模型内部显式使用相对锚的动作差：

$$
z_m(s,a;b)
=h_m(s,b)+A_m(s,b,(a-b)/\sigma_{\rm residual})
-A_m(s,b,0).
$$

这里的 A_m 只是模型的 advantage 分支记号，与上一节动作反归一化 A(u)无关。为避免完整文档混淆，可以把它改记作 f_m^adv。

定义

$$
Q_m(s,a;b)=\operatorname{sigmoid}(z_m(s,a;b)),
$$

$$
\bar Q(s,a;b)=\frac14\sum_{m=1}^4 Q_m(s,a;b),
\qquad
R_s(a;b)=\frac14\sum_{m=1}^4[Q_m(s,a;b)-Q_m(s,b;b)].
$$

实现最大化 R。由于 s、b 和四个 critic 的参数都固定，第二项对候选动作梯度为零，故：

$$
\nabla_a R_s(a;b)=\nabla_a\bar Q(s,a;b).
$$

它不是四成员 logit 均值的 sigmoid，也不是下置信界；程序先分别 sigmoid，再对概率差取均值。R(b;b)=0，日志中的 candidate_mean_probability 与 mean_gain 是两个不同量。Q 是训练得到的成功概率预测，不是已证明校准的成功率，也不是环境提供的真 Q。

梯度只通向候选动作：状态特征、a0、模型参数均冻结；CPU float32 评分保留从输入命令返回的可微链。四个成员等权，没有按不确定度加权。不存在凭正 Q 增益才接受的逐源规则。

实际引用：
[TenStepCritic.forward，52行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/critic.py:52)；
[FrozenObjective 的定义及冻结，51行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:51)；
[固定槽0及概率差，109行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:109)；
[gradient，141行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:141)。

## 3. 原 flow sampler 与时间方向

PI0.5 的训练路径在代码中写为 x_τ=τ ε+(1−τ)a，速度目标是 ε−a。推理从噪声开始，时间从1递减到0：

$$
\tau_k=1-0.1k,\quad k=0,\ldots,9,\qquad
x_{\tau_k-0.1}=x_{\tau_k}-0.1\,v_\theta(x_{\tau_k},\tau_k;s).
$$

实际十次网络调用的 τ 是 1.0,0.9,…,0.1，最后一步落到0，**没有在 τ=0 再调用一次网络**。当前干预只在最后三个调用 τ∈{0.3,0.2,0.1}发生，α=10。

代码使用当前状态和当前预测速度构造 clean proxy：

$$
u=x_\tau-\tau v.
$$

在理想直线路径速度下，这恰为终点动作；实际网络下它只是当前的 clean-action 估计，不等于未来剩余 Euler 步最终必然产生的动作。

引用：
[PI0.5 训练路径，739行](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/projects/vla-corrector/src/lerobot/policies/pi05/modeling_pi05.py:739)；
[倒时间 Euler，827行](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/projects/vla-corrector/src/lerobot/policies/pi05/modeling_pi05.py:827)；
[运行时强制十个时间点，engine.py 73行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:73)；
[FlowHook 时间筛选，298行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:298)。

## 4. 两种 flow 注入：真正的梯度路径

每个选定 τ 都先调用原 denoise_step 得到 v。随后：

- 固定 x̄=stopgrad(x_τ)；
- 固定 v̄=stopgrad(v_θ(x_τ,τ;s))；
- 重新建一个小的、仅关于候选变量的 autograd 图。
- T 的 affine/真实 clamp 和 critic 对候选的导数仍在图中，没有用直通估计绕过 clamp。

令

$$
u=\bar x-\tau\bar v,\qquad
g_u=\nabla_u R_s(T(u)_{0:10};b).
$$

普通内部坐标上，链式法则是

$$
g_u=J_A^\top J_C^\top\nabla_a R_s(a;b),\quad a=T(u).
$$

严格处于裁剪区间外时 clamp 导数为0，内部为1；恰在端点按 PyTorch clamp 的边界导数约定处理。目标未读取的后40步和后28维梯度为零，代码显式检查这个窗口。

### 4.1 velocity 模式

把 v̄ 的独立副本设为 leaf，定义 u(v_leaf)=x̄−τv_leaf，因此

$$
\nabla_{v_{\rm leaf}}R_s(T(\bar x-\tau v_{\rm leaf});b)
=-\tau g_u.
$$

代码执行梯度上升：

$$
\widetilde v_V=\bar v+\alpha\nabla_{v_{\rm leaf}}R
=\bar v-\alpha\tau g_u.
$$

这里“对速度求导”是对速度数值的独立副本求导，**不包含 v_θ 对 x、网络权重或早期采样轨迹的 Jacobian**。

### 4.2 direct 模式

直接把 u=x̄−τv̄ 的副本设为 leaf，对其求 g_u，再改速度：

$$
\widetilde v_D=\bar v-\alpha g_u.
$$

它没有把完整 R(T(x−τv_θ(x))) 对 x 求导。把它描述成包含 I−τ∂v_θ/∂x 的 full-Jacobian 引导，是错误的。

### 4.3 为什么速度上减梯度仍沿正方向移动

Euler 步长为−0.1。对于同一个当前 x、v、g 的局部比较：

$$
\Delta x_V^{\rm extra}=+0.1\alpha\tau g_u,\qquad
\Delta x_D^{\rm extra}=+0.1\alpha g_u.
$$

α=10时局部额外位移分别为 τg_u 和 g_u。只对**同一局部状态**成立；两条采样轨迹更新后不同，后续的速度和梯度也不同，不能据此把最终 direct 输出看成最终 velocity 输出除以 τ。

诊断中用“改过的速度再估一次 clean”：

$$
\widetilde u_V=u+\alpha\tau^2g_u,\qquad
\widetilde u_D=u+\alpha\tau g_u.
$$

这与真正的单个 Euler 状态位移是两件事。代码中的 objective_after 对应这个局部 clean proxy 的评分，不是整条采样或真实环境的保证收益。

### 4.4 局部优化的限制

每个注入点只做一次修改，没有回溯减半、候选线搜索、逐步 trust-region 投影，也不要求 objective_after 大于 objective_before。日志 accepted=True 不能解释成“通过了增益检验”。若指定的 GuidanceError 发生，engine 使用同一 seed 无引导重采样并记 fallback；这不是按效果挑选方案。

修改后的速度被 detach 后返回 sampler。后续 VLA 前向会看到已修改的 x，因而可产生跨时间步、跨动作维度的前向耦合；这仍不构成跨步反向传播。最终50步生成结果可能整体变化，最终 matcher 只抽取首10步方向，并把其余40步恢复为 a0 尾段。

引用：
[detach、leaf、真实变换及 autograd，guidance.py 234行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:234)；
[窗口检查与更新，250行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:250)；
[after诊断与接受日志，259行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:259)；
[同seed无引导错误fallback，engine.py 54行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:54)。

## 5. post：采样后的单次方向与 S²

完整无引导生成 a₀^raw 后，以 b=C(a₀^raw)首10步为 leaf，在命令坐标求

$$
g_a=\nabla_a R_s(a;b)\big|_{a=b}.
$$

实际 post 方向是逐维

$$
d_P=g_a\odot S^2.
$$

它的几何来源：若在非饱和位置按 clean 坐标做欧氏梯度上升，δu∝Sᵀg_a；映回命令坐标 δa∝Sδu=SSᵀg_a。对角 S 就是 S²。

实现没有先把 raw 锚反解成 u 再运行 flow；它直接对 b求一次梯度，显式乘 S²。从乘 S²到进入 construct 之间，没有额外的步长标量、方向裁剪、投影或优化迭代。边界附近的坐标随后被共同 mask 清零。最终 step size 由匹配算法决定，并非 α=10；不做多次 post 迭代、Q 准入或 post 回溯。即使 R(b)=0，候选动作的梯度也可以非零，因为锚槽 b 是独立固定常量。

引用：
[实际 engine 的 post，119行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:119)；
[独立同义 post_direction 接口，guidance.py 191行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:191)。

## 6. 五方向共同匹配：部署算法的一部分

### 6.1 从同一个 a0 构造五个原始方向

令 b 为有界无引导首10步，b_V、b_D 为两次有引导完整采样结果裁剪后的首10步：

$$
d_V=b_V-b,\quad d_D=b_D-b,\quad d_P=S^2g_a,
\quad d_{\rm reverse}=-d_D,\quad d_{\rm random}=\text{平滑高斯方向}.
$$

三次 VLA 采样（无引导、velocity、direct）用相同候选 seed，并核初始噪声 SHA 一致。post 不再采一条 VLA 轨迹。

共同匹配中的 random：每个动作维度独立采3个标准高斯结点，结点时间为0、4.5、9，对整数0,…,9线性插值，得到10×4方向。其 seed 来自与结局无关的 matching_random 身份域。

### 6.2 两组分别计算，但各组内五方向共享半径

分组：

| 组 g | RMS计数范围 | 目标ρ_g | 单坐标L∞上限L_g |
|---|---|---:|---:|
| XYZ | 首10步×3维，共30个数 | 0.05 | 0.15 |
| gripper | 首10步×1维，共10个数 | 0.10 | 0.40 |

RMS 对整组求均值，**包括被 mask 清零的坐标**，不是只对活跃坐标求均值。

共同 mask 和对称边界余量：

$$
M_{t,j}=\mathbf1[1-|b_{t,j}|\ge0.05],\qquad
B_{t,j}=\min(1-|b_{t,j}|,L_g).
$$

对每个方向 k∈{V,D,P,reverse,random}：

$$
\bar d_{k,g}=M_g\odot d_{k,g},\quad
n_{k,g}=\operatorname{RMS}(\bar d_{k,g}),\quad
e_{k,g}=\bar d_{k,g}/\max(n_{k,g},10^{-10}),
$$

$$
c_{k,g}=\min_{|e_{k,g,i}|>10^{-10}}
\frac{B_{g,i}}{|e_{k,g,i}|}.
$$

若没有活跃元素，其容量记0。若五个方向中任一个组范数不大于10⁻¹⁰，组半径 r_g=0；否则

$$
r_g=(1-10^{-6})\,
\max\{0,\min(\rho_g,c_{V,g},c_{D,g},c_{P,g},
c_{{reverse},g},c_{{random},g})\},
$$

$$
\delta_{k,g}=r_g e_{k,g}.
$$

最后产生 float32 的 b+δ，重新核 RMS、L∞、边界和五方向同幅，允许误差10⁻⁶。

### 6.3 需要写清楚的影响

- 共同半径可以低于目标0.05/0.10，因此这两个数是请求值和上限，不能说每源实际都达到它们。
- 任一方向的某组为零，会让**五方向该组全部为零**；XYZ和gripper分别处理，源不删除。
- 匹配会把方向归一化，因此可以放大原生 V/D 的小位移；它不是“只缩小原始采样改动”。
- 反向 D先按原始差取负，之后与D接受相同 mask、归一化和半径，最终是“反向已投影 D”，在float32容差内 δ_reverse=−δ_D。
- random 虽未作为部署物理臂执行，仍参与半径最小值；固定 post 后继续生成 V/D/reverse/random 是现有科学方案的一部分。
- 这些限制只作用于最终命令。flow中间 clean proxy 和速度没有接受这套共同半径限制。
- 某次有引导采样fallback为a0后，零方向可能把共同组半径压到0；不能将这一行为误写成“只有失败臂回退，post仍独立执行”。

引用：
[五方向次序，config.py 3行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/config.py:3)；
[完整共同匹配，candidates.py 12行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/candidates.py:12)；
[同seed生成与噪声核对，engine.py 103行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:103)。

## 7. raw命令恢复、贴边夹爪与真实执行

matcher 首先在有界 b 上得到候选 b+δ，接着 preserve_raw_anchor：

1. 复制完整 a₀^raw。
2. 仅在 δ≠0 的坐标复制有界匹配候选值。
3. δ=0 的坐标保持原始位模式，包括 signed zero。
4. 所有第11–50步保持 a₀^raw 尾段，首十步 mask 外保持原 raw。
5. 再核 C(a^raw)=b+δ，以及
   C(a^raw)−C(a₀^raw)=a^raw−a₀^raw（容差10⁻⁶）。

这是命令**差值和评分代理**的一致性，不是环境动力学全局等价的证明。

例子：

- raw grip=1.2：b=1，M=0，δ=0。所有臂保持 raw grip=1.2，critic统一看1；不会只把replan改成1。
- raw grip=0.98：余量0.02<0.05，仍保持不变。
- raw grip=0.8：M=1，允许对称边界幅度至多min(0.2,0.4)=0.2；还受组RMS、其他方向容量和安全缩小因子限制。

backend 直接把float32命令传给 native_env.step；本纠偏层不追加裁剪。环境自身如何施加控制限制属于另一层语义，不能拿C(raw)替代所有raw并宣称普遍物理等价。

部署实际五臂：

- continue_native10：从保存的旧队列继续剩余命令。
- alarm_replan10：执行新 a₀^raw 的首10步。
- velocity/direct/post：执行对应最终 matched raw候选的首10步。
- reverse/random保留生成与匹配证据，不作为这五臂外的物理实验臂。

前缀完成后，所有臂恢复普通 native10：每次完整VLA生成50步，只执行前10步，到期重采样。成功/结束可提前停止，总环境步数预算300。它是一次报警干预，不是在每个后缀决策点持续引导。

后缀 seed 按 episode/cut/repeat/后缀决策序号配对，不含方法或worker。正常继续臂和中断臂的采样绝对时刻可以不同；“配对噪声”不代表相同绝对时刻、相同状态。

引用：
[preserve_raw_anchor，5行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/commands.py:5)；
[raw审计，bank_audit.py 6行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/bank_audit.py:6)；
[环境接收raw，metaworld_pi05.py 288行](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/collection/metaworld_pi05.py:288)；
[前缀选择，semantics.py 230行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/semantics.py:230)；
[实际分支与普通后缀，main_collection.py 465行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:465)；
[随机流协议，protocol.py 135行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/protocol.py:135)。

## 8. 13个训练候选：与五方向匹配的关系

13槽是 critic 的动作数据覆盖，不是部署13选1。槽0始终为新的raw a0；正常旧队列继续是额外对照，不进入critic候选槽。

| 槽 | 名称 | 对 a0 的扰动 |
|---:|---|---|
| 0 | a0 | 0 |
| 1–2 | xyz_positive / xyz_negative | ±λ × 最终post的XYZ实际扰动，grip=0 |
| 3–4 | gripper_positive / gripper_negative | ±λ × 最终post的grip实际扰动，XYZ=0 |
| 5–6 | random_half_positive / negative | ±0.5 × 独立随机全幅的已实现扰动 |
| 7–8 | random_full_positive / negative | ±独立随机全幅扰动 |
| 9 | velocity | 原final matched velocity，保持不变 |
| 10 | direct | 原final matched direct，保持不变 |
| 11 | post | 原final matched post，保持不变 |
| 12 | reverse_post | −原final matched post实际扰动 |

λ只能是事先注册的0.5或1，不按结局选。**这个注册倍率只作用于XYZ±、grip±四个通道探针，不是改变整源formal V/D/P目标RMS的另一套tier。** 原冻结注册中，round1的train300为150个λ=.5和150个λ=1，另dev100为50/50；round2的train300亦为150/150。两轮formal matcher均固定请求XYZ RMS=.05、grip RMS=.10，L∞=.15/.40；部署也沿用这组配置。

训练的多幅度覆盖来自通道探针λ=.5/1以及独立随机半/全幅正负探针。不能把它说成“半数source的所有纠偏用.025/.05、半数用.05/.10”。通道探针即便λ=1也只保留一个通道；其幅度以该源post的实际可行扰动为基底，通常不能保证达到目标RMS。

XYZ/grip通道候选取的是**已经实现的post命令差**，不是把原post梯度再单独归一化。如果post某通道实际RMS≤10⁻¹⁰，则那个通道改用独立平滑高斯方向的可行投影，再乘λ；记录fallback，不能伪称来自post梯度。

13槽所用随机流从注册random_seed的SeedSequence分出3路：联合随机、XYZ退化fallback、grip退化fallback。每路都是3×4高斯结点、0/4.5/9线性插值。

独立随机候选的XYZ/grip分别使用自己的对称可行半径；**不对13个候选再取一个共同最小半径**。V/D/P输入被验证并保留原样，因此新增训练探针不会重新缩放部署候选。正负候选和半/全幅关系以实际float32命令差核对，容差10⁻⁶。

**两个反向概念必须分开：**

- matcher内部 reverse_matched=反向direct，参与五方向共同半径；
- 训练槽12 reverse_post=反向post，用于监督方向性。

全部13槽保留。别名判定依据完整首10步raw float32字节（含signed zero），不依据clip后的相等。记录每个别名组的1/组大小去重权重供训练使用；当前采集不借此省掉物理分支，所有候选按原协议真实执行，正常对照另算。

引用：
[固定13槽与配对，candidates13.py 16行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/candidates13.py:16)；
[独立投影与raw输出，97行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/candidates13.py:97)；
[formal候选保留、通道fallback，167行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/candidates13.py:167)；
[13槽生成与别名，218行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/candidates13.py:218)；
[注册通道尺度传入，main_collection.py 419行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:419)；
[每源原样执行、不复用标签，509行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:509)。

## 9. 可直接用于主文档的算法小步骤

在一个合法报警处，对固定s：

1. 保存正常分支的旧队列和物理状态；生成候选的过程不推进环境。
2. 用注册seed运行无引导PI0.5，得到新的raw a0；令b=C(a0)。
3. 用s、固定b、固定A4000四成员构建R。
4. 同seed运行velocity与direct两次采样，分别只在τ=.3/.2/.1按上述局部公式改速度；核三者初始噪声相同。
5. 在b求一次命令梯度，乘S²得到post方向。
6. 构造V/D/P/反向D/平滑random，按XYZ与grip分别计算共同mask、单位RMS和共同可行半径。
7. 得到匹配候选，恢复raw锚、首10步外尾段和mask外坐标，验证命令差与C(raw)差一致。
8. 将所有候选、方向、Q诊断和随机流身份封存，再执行所需物理臂；不按本次Q或未来结局换动作。
9. 正式固定策略在首次合法报警时选post；calibration已按完整100源的mean(post−replan)>0规则作一次全局选择，held不再选方法。
10. 执行选定raw前缀最多10步，然后统一普通native10直到结束/成功/300步；不继续重复纠偏。

实际 cal/held collector 都调用同一 MainCollector.prepare_bank 和 Native10Engine.make_bank：
[HeldoutCollector.prepare_bank，436行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/heldout_collection_v1.py:436)；
[held工厂调用create_engine，442行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/heldout_collection_v1.py:442)；
[cal同一路径，353行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/calibration_collection_v1.py:353)；
[最终固定选择结果](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_selections/final_selection_v1/result.json)。

## 10. 主文档应避免的表述

1. “flow引导通过整条VLA反传”——当前没有。
2. “R是reward或LCB”——当前是固定锚的均值成功概率差。
3. “α10同时控制post最终幅度”——post不使用该α，最终匹配另定幅度。
4. “速度更新减梯度，所以在降低Q”——忽略了倒时间Euler的负步长。
5. “after Q提高才接受”——当前没有此接受条件。
6. “post已独立于其他候选，成本只算一个梯度”——当前共同半径保留其他方向生成依赖。
7. “所有动作均clip到[−1,1]后执行”——critic代理裁剪，raw执行保留原饱和值。
8. “正常对照也强制再执行新的10步”——正常保留旧队列余量；新10步是重规划/纠偏前缀。
9. “13槽共同归一化、同名reverse完全相同”——两者均不成立。
10. “三种算法同幅意味着中间查询、方向、成本也相同”——只约束最终首10步命令的分组RMS与边界。
