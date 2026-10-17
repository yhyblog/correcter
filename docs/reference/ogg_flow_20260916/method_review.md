# Frozen v3 flow 机制实验：独立数学与文献审查

日期：2026-09-16。此文在正式开发结局曝光前撰写。审查只读取协议、方法代码和官方文献，并运行 CPU 命令匹配测试；没有据本轮成功结果调参，也没有执行 GPU 工作。本文不表示真实纠偏已有效。

## 1. 审查范围与结论

完整读取执行任务书、flow 综述、旧 `ogg/core.py`、v3 `learning.py`，检查本地真实 π0.5 sampler，并独立审查新 `ogg_flow/common.py` 与 `ogg_flow/candidates.py`。固定 v3 四成员、VLA、D、G0，采用同一指定 a0、同一状态、十步执行前缀与 fixed10 后缀，能够将评分方向问题与 flow 注入问题分开检验。旧 v3 的 60%→54% 是离散候选选择结果，不能当作本轮连续梯度算法的既有结论。

参数冻结、源去重及分支预算的最终证据以实验目录下封存的 `config.json`、`formal_freeze.json`、预算日志和执行审计为准。本文记录的是本次代码审查快照，不替代最终运行版本身份。

## 2. 时间符号、动作单位和固定参照

本地 `modeling_pi05.py:827–858` 实际执行 `dt=-1/num_steps`，时间从 1 降到 0，更新 `x_t=x_t+dt*v_t`。令干净估计 `u=x_tau-tau*v`，目标为四成员 sigmoid 成功概率差的均值 `R(T(u))`，并记 `g=grad_u R(T(u))`。固定当前 x，原 velocity-leaf 更新为 `v'=v-alpha*tau*g`，直接注入为 `v'=v-lambda*g`。Euler 步长为 `-h`，所以额外状态变化分别是 `+h*alpha*tau*g` 与 `+h*lambda*g`。新的单步干净估计变化与这个 Euler 状态变化不同，不能把前者误作采样终点变化。这些符号是根据本地时间约定推导的。

v3 模型在 `actions[:,0]` 读取参照。正确动作输入是固定 `a0.detach()` 在槽0、可求导候选在槽1；状态特征也必须 detach。`R(a0)=0` 不意味着候选梯度在 a0 为零。全部参数保持冻结并不能自动禁止输入梯度；`FrozenSelector.score` 的 `no_grad` 评分接口不能直接承担梯度计算。

反归一化的局部线性斜率为 `S=diag((q99-q01)/2)`。在未饱和区，内部干净变量欧氏上升映射到命令空间得到 `delta_a ∝ S² grad_a R`。因此后采样方向使用 `grad_a R * ((q99-q01)/2)^2`，与 flow 内引导采用同一变量度量。直接使用未经此变换的命令梯度会同时改变度量。真实 clamp 的越界梯度为零；最终共同边界 mask 使匹配控制不在饱和坐标上强造对称修正。

## 3. 最终实际命令匹配

本轮主比较采用共同 mask `1-abs(a0)>=.05`，**不乘 clearance 权重**。XYZ 和夹爪分别将每个方法的剩余方向归一为单位 RMS，再将共同半径限制为目标值与所有方向可行半径的最小值。每坐标可行改变量同时受到 `1-abs(a0)` 和该组 Linf 上限限制。最终保存为 float32 后重新度量，而不是仅比较 latent 半径或引导强度。

此投影可放大原生输出；应称为“最终命令幅度匹配”的方法。原生 velocity/direct 两臂单独保存和执行，不能把投影后结果写成未经后处理的原生算法结果。共同 mask、分组归一和组间尺度会改变整体方向，报告须保留实际 XYZ/夹爪 RMS、Linf、边界移除率和共同回缩率。正反控制应满足 `a_plus+a_minus≈2*a0`。

若任一主方向在某组的范数为零，全部匹配方法在该组共同回退到 a0；不能删除该源。随机方向来自每维三个高斯节点在十步上的线性插值，种子固定。随机控制用于方向性比较，不构成对所有可能随机平滑分布的普遍检验。

## 4. 官方资料核对与本项目适配区别

- [QGF 官方 `agents/qgf.py`](https://github.com/zhouzypaul/qgf/blob/main/agents/qgf.py) 的 `sample_actions` 采用正向时间，先得到并 clip 一步干净估计，对 stop-gradient 后的新动作变量求 Q 梯度，再直接加入速度；默认不使用生成器 Jacobian。其 `apply_jacobian` 开关另行求干净映射的 Jacobian。联网同时核对了[原始代码页](https://raw.githubusercontent.com/zhouzypaul/qgf/main/agents/qgf.py)。本轮为保持主对照只改变注入方式，两种 flow 方法共用 T 的真实 clamp 链式导数，因此是 **QGF 式直接注入适配**，不是逐项复现官方裁剪后重建求导变量的版本。官方默认使用的 critic 聚合与本轮四成员相对成功概率均值也不同。
- [QGF 论文](https://arxiv.org/html/2606.11087v1) 说明忽略 Jacobian 的设计及其试验依据。更完整的导数不是本轮可预设的改进；本轮不据开发结局临时添加 Jacobian 方法。
- [QPILOTS 论文](https://arxiv.org/html/2606.14801v1) 区分 U 与 M；后者包含额外条件模型。它的模型训练和数据条件与本项目不同，不能把本轮固定 critic 的直接引导称为复现 QPILOTS-M。
- [GAF 论文](https://arxiv.org/html/2607.02092v1) 将推理引导用于冻结 VLA。其锁定测试从 26/40 到 27/40，提示不能用开发改善代替泛化确认；并不构成本项目评价器可靠的证据。
- [On the Guidance of Flow Matching](https://arxiv.org/html/2502.02150v3) 提供一般 guidance 框架与近似方法。普通候选经验协方差不自动等于其条件终点协方差，本轮没有宣称复现该理论保证。
- [D-Flow 正式论文](https://proceedings.mlr.press/v235/ben-hamu24a.html) 通过生成链优化初始噪声。本轮没有进行此完整反传，最终投影不等价于 D-Flow。
- 已核对 [RTC 官方研究页](https://www.pi.website/research/real_time_chunking)、[FBFM](https://arxiv.org/html/2607.29235v1)、[VGG-Flow](https://arxiv.org/html/2512.05116v2)、[πR²](https://arxiv.org/abs/2607.26055)。这些涉及反馈约束、训练或调度的不同假设，均未混入本轮固定部件的比较。

以上网络核对使用 2026-09-16 可访问的官方论文或作者代码。GitHub `main` 可继续变化；本轮方法语义由本地冻结协议与实现 SHA 确定。

## 5. 独立测试与解释边界

新增 `tests/test_ogg_flow_matching.py`，CPU 实测 **7 passed in 3.02s**。测试验证最终 float32 命令的分组 RMS、正反对称、饱和及近边界共同 mask、逐坐标 cap 引起的共同回缩、零组共同回退、整组饱和保留、十步后尾部不变、输入不被修改、随机种子复现，以及原生臂与投影臂分开保留。这些是执行命令契约测试，不是环境成功率的证据。

复现命令：

```bash
cd /mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP
env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -m pytest -q tests/test_ogg_flow_matching.py
```

机制判断须来自真实配对后缀：终点修正有效而 flow 内无效，才支持进一步检查注入时间、Jacobian 与后续采样影响；正向未优于反向/随机时，当前评分梯度缺少真实方向性支持；只提高 Q 不计纠偏成功。30源中的八次后缀不是240个独立源，开发方法的最高点不能称为独立验证成功。

审查快照 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `src/ac_tmil/ogg_flow/common.py` | `bd9fd54173e8af901e9b8b5746ae18c3117a3aebc3e502896e96dd9df72f8a97` |
| `src/ac_tmil/ogg_flow/candidates.py` | `e2a46c1168fcda3d456082ed7ca40f003e7e7f603a469c20b49a1c4683f26ef9` |
| `tests/test_ogg_flow_matching.py` | `cc2a3004290c1cc9813af1d1d55b327fd4a50952ef22126388ae39bb925cbd36` |
| `src/ac_tmil/ogg/core.py` | `ddf23e1a4905cfce9276e6708dd26ad3560b43fdd3ad7ca44a74f4a23a64b985` |
| `src/ac_tmil/ogg_research_v3/learning.py` | `e21a83fdbf6b052d2ed610c6adfeaaf186e64e9db122d6e02cb03ff372a21432` |
| `../embodied-ai-workspace/projects/vla-corrector/src/lerobot/policies/pi05/modeling_pi05.py` | `56016f6d840871b46f261990ff5decfdf4cd6759dbc5cb2a4a150bf3ccfb68a2` |
