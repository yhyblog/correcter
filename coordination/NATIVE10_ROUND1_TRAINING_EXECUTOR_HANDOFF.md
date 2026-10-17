# 首轮 A/B 训练执行交接

2026-09-16。已按 READY v6 完成 A/B 四成员训练、固定离线选模、所选模型真实保存重载及独立产物审计。选定 **B，第200步**。本轮没有新增仿真；结果仍是开发银行选模，不能称为新 flow 纠偏收益或独立验证成功。

## 输入、训练与预算闭合

完整静态输入为300/300 train有效critic源、100/100 dev主槽（95有效critic源＋5合法无报警共同结局），技术缺失0，400物理初态唯一，无替补。全部source/bank/branch、配对后缀、raw映射、alias、scene与replacement链已审计。目的ID集合无交集；A保留旧投影，B的PCA仅拟合300唯一train源16/8维。八份预检初态、bootstrap/minibatch seeds和trainable masks由正式训练直接加载，未重拟PCA或重建初态。

A lr1e-4、仅residual/advantage；B lr3e-4、全小critic MLP。两者各4成员×2400步，AdamW wd.01、clip1、batch32整源，BCE/相对a0/正反概率差损失权重1/1/.5保持。40个固定成员检查点完整，无技术失败。

本阶段 **19200/19200 optimizer updates，新增simulator attempts 0**。全仿真仍23479/50000＝P0 564＋round1 22915（400capture＋395独立bank＋22120branch），technical reserve 0/1200。原23479条仿真账本字节前缀未变；优化更新单列编号23480..42679，不应把总42679行误读为仿真数。

CPU float32、两线程，启动至模型seal 879.09秒（约14.65分钟，含输入核验与选模/重载）；首次至末次优化登记725.46秒，含期间checkpoint评估。8张GPU holder保持。日志保留一次CPU autograd CUDA探测warning，没有GPU模型计算或数值失败。

## 固定开发银行选择

| 路径 | 步数 | 旧银行选候选相对a0 | 救回 / 损害 | gain MSE |
|---|---:|---:|---:|---:|
| A | 200 | +4.00pp | 23 / 7 | 0.05180750 |
| A | 400 | +3.50pp | 23 / 9 | 0.05201815 |
| A | 800 | +2.75pp | 19 / 8 | 0.05381573 |
| A | 1600 | +0.75pp | 12 / 9 | 0.05745837 |
| A | 2400 | +3.25pp | 20 / 7 | 0.05836694 |
| B | 200 | +4.50pp | 24 / 6 | 0.05370577 |
| B | 400 | +3.50pp | 25 / 11 | 0.05384675 |
| B | 800 | +3.00pp | 24 / 12 | 0.05547971 |
| B | 1600 | +3.50pp | 25 / 11 | 0.05674827 |
| B | 2400 | +4.50pp | 27 / 9 | 0.05697172 |

B200与B2400均+4.5pp，按预登记较少harm规则选择B200（6而非9）。完整100源×4配对后缀分母：a0为257/400＝64.25%，所选候选275/400＝68.75%；救回24、损害6。5个无报警源广播已知共同结局，未删除或补造候选。

这是同一开发银行上10个检查点的选择成绩，候选由旧生成critic采集；不会因+4.5pp接近用户5pp目标就宣称算法成功。尚未用新B200生成实际velocity/direct/post并做五臂部署，也没有独立held验证。本轮完整300train的方向监督、任务与请求/实际cut分层见 `NATIVE10_ROUND1_TRAIN300_DIAGNOSTICS.md`；109/300有非alias候选结局信息，191源候选均值相同，负例和fallback均保留，未按收益改配额/半径/loss/G0。

## 训练后重载与独立审计

实际训练pipeline从B200四个训练检查点导出模型；在全部95个有cut开发源上，13候选成员概率、槽0与11的成员及集成动作梯度逐位一致，a0 gain精确0，state/a0不可变。离线/在线集成增益最大差0。再次重算选模指标一致。

独立只读审计通过73098项检查：19200唯一update IDs、8份bootstrap及全部2400×32 minibatch精确重建；40个检查点张量有限，A冻结参数及A/B buffers逐字节保持初态，所有可训练张量均已改变；独立NumPy重算十个检查点仍选B200。NumPy/Torch float64 gain MSE归约最大差1.39e-17，仅独立标量复算容差1e-12，未放宽模型概率/梯度逐位一致要求。该独立审计只读取CPU张量/封存预测，无forward/backward/optimizer/仿真；概率梯度真实检查来自上段正式pipeline产物。

## 封存与下一阶段

以下路径相对 `outputs/native10_training_20260916/`：

| 产物 | SHA256 |
|---|---|
| `fit_protocols/round1_fit_v1/config.json` | `efe92b99a5d0d27d3434d1d7c5c453d294493b2a7a4ee6038bcc6e447be9bb4d` |
| `fit_protocols/round1_fit_v1/freeze.json` | `d688d581e87ef9b8c0649aa12ca2d31030c0c4da376370d363210785e034c9c7` |
| `datasets/round1_train_full_v1/complete.json` | `08d8bf56408f65dc4302a588be987626ea2d4f420ab3a156c8c360ef8a7fd14a` |
| `datasets/round1_development_full_v1/complete.json` | `ff4084fa637fc5c50cbad1ee2010084d7b2658f42902700069b09ec71fdf8865` |
| `fit_preflight/round1/round1_preflight_v1/complete.json` | `3a97fff5235b804ec05afd6cc4dc6f25e89319c393d2fa21f70eda2296ed3930` |
| `models/round1/round1_fit_v1/complete.json` | `ff460f12c598a34a15a28ed7619ed071a60be195a3dd2f0c1c963a202ee22287` |
| `models/round1/round1_fit_v1/selected/complete.json` | `931c6f6043db92b5d9003eb2833dfc8edd0ab6c860a1979db3983cd7d893725f` |
| `models/round1/round1_fit_v1/selected_reload_audit.json` | `ce43fc0888f807ef048612ad733795bc1ad5aef24103f0ed89e3c1d51c4beb7b` |
| `training_audits/round1_fit_v1_new/complete.json` | `80184aeef52e467ae6f386ea594bae2588f8d47879fb8c9224c49586ab423a4c` |
| `preparation/round1_training_execution_v1/complete.json` | `05d106e67ba60d2f686636314ca97bc4cfce079f2fb7753a19be2e3c476690b1` |

可复现命令/日志：`preparation/round1_training_execution_v1/`。独立审计代码 `experiments/native10_training_20260916/training_result_audit_v1.py`，证据 `training_audits/round1_fit_v1_new/{audit.json,report.md,budget_snapshot.jsonl}`。所选四模型hash见模型根 `result.json` 与 `selected/ranking.json`。

建议分析端据以上已封存模型放行既定一次实际开发五臂。新阶段上限2100，不新增capture：复用原100源，95有cut预计95 bank＋1900 branch＝1995新attempt，5无报警仍占全部100源分母。应冻结独立部署入口，禁止缺源自动capture/替补；新bank执行前核原a0/随机流相同，部署报告分别给中断I、纠偏A、系统T七项配对结果。执行端正在独立新模块准备这些检查，不修改采集v4、预检v5或训练v6冻结依赖。READY v6尚未放行实际开发、第二轮、cal或held。
