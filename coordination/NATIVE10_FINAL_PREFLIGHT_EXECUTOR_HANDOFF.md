最终 600 源真实零更新预检交接（2026-09-17；工作流20260916）

真实预检已通过。A/B 全部八个初始成员在 train600 与 development95 有效 cut 上完成 canonical 同 shape 严格逐位重载；开发计划分母仍为100。此次没有训练、策略部署或新增仿真，不能据预检通过声明算法收益。

预检目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/fit_preflight/final/final_preflight_v1`；seal `eb1e39d4ee145ebecce9b16593a9c1fd901fd7dcc2a5c9e8746f657e4c202d3e`；result SHA `d693a7d1fa4f1d5a0be4f2141966f35d97390e6e427c4c5cb6803bfc8791c79d`。
固定 specification SHA：`08891c3ee6feb71aa41a8cfa7cb0fbed61930e16eb8938cf5bfeff1dd24ad946`。
新 config SHA `c7fcdf6a8f3c6c633ffcedbe5ad8e263c0f99b9c53655c9badd83ab060c220ca`；freeze SHA `90a3095500a2ee71da4016f96cff5ee084bf9fc2cc97ae97a92b23bedc6edf5a`；READY v9 SHA `684fa1d88290a68a64e21e898695a9271602e5bec0ecff7c707962ad625ff521`。

A 从原旧四成员权重/PCA初始化，逐元素恒等检查通过；B 在600个唯一train原canonical特征上各用一次拟合PCA16/8，再新初始化四个完整小MLP。PCA、bootstrap与dev集合交集为0。每成员每task120抽120、总600；固定4000×32 minibatch计划、seed、八初态及trainable masks均已封存。A仅residual/advantage可训练，B全7058参数可训练；本轮实际优化仍为0。

canonical 核验覆盖全部13概率及槽0/11的成员与ensemble动作梯度，缓存逐位一致、state/a0不变、a0相对优势严格0。a0动作梯度不要求为0。

dense跨shape均存在非逐位差异，按已批准数值决定独立报告，没有新增容差或改变canonical路径。下表为本次实测最大绝对差；不是跨环境界限、接受阈值或训练效果。原报告保留逐成员/槽的参考尺度、source IDs和shape。

| 路径/集合 | 投影特征 | 13概率 | 成员动作梯度 | ensemble动作梯度 |
| --- | ---: | ---: | ---: | ---: |
| A/train | 0.000149011619 | 1.82986259e-05 | 2.52127647e-05 | 1.15633011e-05 |
| A/development | 0.000134110458 | 1.37090683e-05 | 1.52587891e-05 | 8.5234642e-06 |
| B/train | 0.000284751877 | 3.57627869e-07 | 1.16415322e-08 | 4.65661287e-09 |
| B/development | 0.000238418579 | 2.98023224e-07 | 1.09430403e-08 | 3.78349796e-09 |

runtime固定为lerobot Python3.12.13、torch2.7.1+cu126、NumPy2.2.6、CPU float32、两线程。B language保留维度中4个落在原0.001 scale floor；visual为0个，未修改floor/维数。非有限值、shape/source次序、缩放/耦合及同shape重载等硬检查通过。

完整执行耗时426.22秒；模型预检419.45秒，其中输入验证263.51秒、旧权重导入及PCA2.31秒，A/B检查76.42/76.33秒。峰值RSS 1.681 GiB。
账本前后逐字相同：42,874/50,000 sim，19,200/51,200 optimizer；technical reserve使用0。GPU8个holder保留。
账本SHA `189cdf5c04a3782b5e540c3761fa682481dedad6ea91e703e705713e2d076973`。

执行receipt：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_fit_execution/preflight/final_preflight_v1`，seal `d2ba158591ea7fee9c9caca75e7ad2fc2f9b236c3709a35344512d6ab14ec23d`。
结构化摘要与后续training READY精确绑定模板：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/final_model_handoffs/final_preflight_v1`。
原采集/P0/首轮fit/preflight/deployment封存均未更改。正式final fit仍需分析端绑定本次真实seal放行，之后必须加载同一PCA、八初态、bootstrap/minibatches与masks；本交接不自动启动下一阶段。
train600方向监督诊断单独见 `coordination/NATIVE10_TRAIN600_DIRECTION_DIAGNOSTICS.md`，不构成预检或训练新增门槛。
