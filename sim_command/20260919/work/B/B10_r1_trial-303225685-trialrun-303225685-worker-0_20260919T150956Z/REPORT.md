# B10：CPU 接口准备完成，正式计算未执行

| 内容 | 已完成 | 后续缺口 |
|---|---|---|
| A 公共接口 v1 | 三文件SHA一致；七类A样例、23条B样例通过；事件与双账本兼容 | 实际VLA/仿真driver尚未作为不可变入口发布 |
| VLA-Corrector | h1/k10、原cosine(delta_z)视图及原生频率适配清单；旧模型只读；有限GPU预检命令 | 新公共正常示范token view、训练recipe/预算与开发阈值待冻结 |
| E3 GAF-v1 adapted | 公开commit固定；discounted success-to-go/MSE；每次采样引导；CPU梯度与上游一致 | 共同真实逐步manifest、规范化state/语言特征绑定；未训练critic |
| E6 D5→R | 同D两成员因果五步误差、动作/reset对齐、同合法窗口/最多一次、开发干预率匹配 | 开发预测/实际feature traces与阈值为null；未新采集 |
| E1 | 4损失×3完整训练seed×4成员=48份同初始化/容量/更新范围配置 | 4000更新/成员为提案，需单独release；两个算子共用fit |
| E8 | Smol50k、X初始化、LIBERO自身29999资产与维度路径沿用B00 | X缺已训练MT50权重；各底座D/G0/Q适配另计 |
| 存储 | 两个精确X下载临时候选，共3519073692逻辑bytes | 依赖/对端使用尚未排除，建议defer；B未删除共享历史 |

本轮27项CPU测试通过，torch.cuda.is_initialized=false；训练更新、模型GPU推理、VLA采样、simulator attempts、rollout和正式GPU秒均为0。合成CPU autograd触发一次设备枚举警告，未建立CUDA运行时。最后本机guard PID35861运行，8卡均holder，约49–50%利用率；该占卡不列入实验GPU成本。

## 方法与数据口径

GAF论文固定 [arXiv2607.02092v1](https://arxiv.org/abs/2607.02092v1)，[公开代码commit](https://github.com/ylhaichen/guided-action-flow/tree/ee67a70e576dc7f02a00cff86c9dd97f868c896f) 单独锁定，不声称官方关联。参数3成员/768×4/beta2/clip1/gate10/min0.1；π0.5、MW四维state/action及实际10步窗口明确标adapted。每个实际10-flow完整采样至多30 critic forward、10 action backward、0 VLA backward；不接G0一次门控。

成功时间采用动作后的状态step+1；GAF与上游action-index约定一致，target=gamma**(first_success_state-start_step-1)，gamma=.99/真实控制步；成功后1、完整失败0、未知结局不标失败。parent分组，branch/suffix不拼接；生成50不冒充执行50。历史raw有reward/success而bank没有，两者已区分；缺失图像/next/terminated-truncated不虚构。

E6误差为两成员×5个已到达观测×4096维的delta_scale标准化均方误差；预测必须早5步保存、动作逐项相符且物理分支一致。缺失不报警并记录覆盖率。开发阈值选最接近G0的episode干预数，平局偏少；匹配精度受1/Ndev和并列分数限制，不按测试结果追平。

E1保留旧600真实源、7058参数、同成员初始SHA、冻结PCA、只更新residual/advantage、相同bootstrap与4000步预算提案；L_ab=BCE+a·gain+0.5b·pair。旧初始化完整训练沿革单列，未声称共同新增数据等于全部历史数据相同。

## 命令与有限报价

工作目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z`。依赖：既有lerobot Python3.12/torch2.7.1及numpy/jsonschema，精确版本见DEPENDENCIES.json。代码清单SHA=`a2812caf67f72e552c871f423972e1c39bec5b645574a56d7d75618b35c03fd3`。

| 命令/配置 | 未放行的数量提案 | 边界 |
|---|---|---|
| commands/preview_lvm.sh | CPU输入SHA检查，已运行；9个唯一输入文件SHA核验 | 不调用模型 |
| commands/run_formal_job.sh + configs/lvm_gpu_probe_2.json | 初始化1、GPU forward2、仿真/VLA/更新0；VRAM估计2GiB，输出0.1GiB | timeout180s+kill grace20s；重试0；无真实特征/渲染结论 |
| 同wrapper + configs/e1_*.json | 48 CPU fits，合计192000更新，初始化48；RAM估计3GiB，输出0.2GiB | 每成员1800s+20s；只保留final+lineage；未执行 |
| 同wrapper + configs/gaf_v1_member_*.json | 3 GPU fits，合计30000更新/训练前向；开发前向至多1200，初始化3；VRAM估计4GiB | 每成员3600s+20s，dev最多10240条，超出拒绝；共同view为null |
| commands/EVALUATION_REQUEST.json | E3/E6/E8实际闭环次数尚未放行，driver=null | 先绑定A不可变driver；不是假装可运行的eval命令 |

以上容量是工程估计/超时上界，不是实测速度。新token提取帧数、E8次数和X-VLA最低充分训练步数未知，明确null；旧X-VLA有限recipe为30k/8GPU/effective batch64，仅供后续单独决策，不重启历史队列。

wrapper只接受独立本机wave，先验release/任务/host/code/config/input SHA，claim防重复，逐批检查stop/额度，完整命令都经occupancy lifecycle，8卡holder全部暂停至退出含失败。联合A/B wave被拒绝，须先冻结共享完成/失败屏障；不在单卡提前完成时恢复holder。自动重试0；失败claim保留供分析恢复决定。

接口本身无阻塞。真实接入前必须附加entered-before-call durable journal；部分失败和缺末事件仍计已进入资源，entered/returned/failed保留同操作元数据且仅计一次。E3多次决策读完整事件流，episode单值只是摘要；N不分摊shadow监测或a0，嵌套墙钟不相加。

## 交接证据与请求

产物目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B10/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z`，包含代码镜像、configs/commands、输入与SHA、CPU检查、结构化样例和资源报价。接口反馈：`receipts/B/A10_INTERFACE_FEEDBACK.md`；存储候选：`receipts/B/STORAGE_CANDIDATES.json`。B00盘点已被分析端验收，本轮不重跑历史实验。

请分析端按P10先决定2次LVM预检及A/B真实driver集成的有限独立wave；冻结公共数据/特征与D开发记录后再发布训练。X-VLA新训练、联合wave屏障及正式P20评测分别决定。当前CONTROL revision5、TASK_BOARD revision7，没有后续已放行B计算任务。
