# B10 CPU 准备包

本目录为 B10/P00 的隔离代码和配置。27 项 CPU 检查通过；这不是 GPU 预检、训练或科学结果通过。CONTROL 当前所有正式计算上限为 0。

| 接口 | 入口 | 输入与输出 |
|---|---|---|
| A 公共记录 | public_interface.validate_record | 原版 corrector-sim-interface/1；七类记录，null 有原因，禁止真实记录引用 synthetic |
| 真实逐步数据 | public_to_trajectory | 同一 parent/source/branch/suffix 的 prefix1 transitions + SHA 索引的 policy state/task features；输出连续 trajectory |
| GAF 数据 | gaf_view | 完整 train/development 轨迹；输出真实10步窗口、discounted success-to-go、父轨迹身份与特征版本 |
| LVM 数据 | lvm_pair_indices | 显式 normal_demo 轨迹；输出同一真实 episode 的 t/t+10 token 引用，不提取模型特征 |
| GAF 每次采样引导 | GAFVelocityAdapter / pi05_denoiser_hook | 当前 x_t、v_t、t、规范化4维 state 和冻结2048维语言；只修改前10步×4维，保持其他时间与 padding |
| E6 因果监测 | CausalD5Monitor | 早先保存的 D 预测、5步后实际观测、实际动作及完整物理分支身份；输出 score/eligible/triggered 或 null+原因 |
| E1 损失 | e1_loss | logits[源,13]、4个真实结局/候选、alias权重；BCE+a·gain+0.5b·pair |
| 公共事件 | public_events / attach_durable_public_journal | 相同 event_id 生命周期；entered 之前持久化，完整事件流支持重复 E3 决策 |

GAF 参数取 v1 论文所述3成员、768×4、beta2、clip1、gate scale10/min0.1；本轮 π0.5/MetaWorld/10步目标是明确适配。代码 commit、逐文件 SHA 和论文版本分别记录；不称未验证关联的仓库为官方。训练10000更新/成员仅是有限预算提案，不宣称等同论文30 epochs。

GAF 的真实特征提取绑定仍缺失；也没有可训练的共同真实逐步 manifest。两项必须在正式训练前冻结。历史 raw 的 reward/success 已由 A 找到，但缺失逐步 RGB/完整 observation、未拆 terminated/truncated 的记录不能伪造补全。

VLA-Corrector保留原 cosine(delta_z) 目标、正常示范视图和原生每步检查/冷却10/可多次干预。旧帧随机split不可沿用到新公共parent split；旧 checkpoint 只读，共用新 token 提取待单独预算。

E6 在 s 保存两成员预测，s+5 用5个已到达特征计算按各成员 delta_scale 标准化的平均平方误差。动作、分支或 reset 不符不报警；自然重规划边界、成功/终止、队列不足和余量不足均不干预。开发阈值按 episode 干预次数最接近 G0，平局偏少；粒度至少1/Ndev并受分数并列影响。真实阈值与开发记录身份当前为 null。

E1 四损失×3个完整训练seed×4个成员=48 fits；Post/Velocity共用同一fit，不重复训练。同成员在所有分支使用相同初始化、7058参数、冻结PCA、仅residual/advantage可更新、同源bootstrap序列及4000步预算提案。旧完整训练沿革独立披露，不把成员数当完整seed数。

E8：Smol50k保留；X-VLA只有base/初始化、无完成MT50权重；LIBERO用自身29999/30k最终推理资产。各自H/C、动作维度、normalizer和D/G0/Q需独立适配，不重启旧队列。

## 命令、工作目录与依赖

工作目录是本 README 所在的冻结 work/B run。Python 为工作区 `.miniforge3/envs/lerobot/bin/python`；精确版本见 DEPENDENCIES.json。未安装或升级环境。

CPU 预览：`bash commands/preview_lvm.sh`。只校验输入SHA并展示未放行的预算。

正式作业文件：`commands/run_formal_job.sh CONFIG RELEASE UNIQUE_OUTPUT`。它先核对 CONTROL/任务板/本机release/config/code/input SHA，再以 occupancy lifecycle 包住超时受限命令。用法中的三项必须绑定分析端真实发布，不以本目录报价文件冒充release。

- 最小 LVM 预检：config=`configs/lvm_gpu_probe_2.json`；模型初始化1，GPU模型forward最多2，VLA采样0、仿真0、更新0；超时180秒、自动重试0；合成token仅验形状/有限值，不能替代真实特征与渲染预检。
- E1训练：config=`configs/e1_L00_s9101_m1041.json` 等48个文件；完整清单 `configs/E1_MATRIX.json` 与 `configs/JOB_INDEX.json`。该数值小模型在CPU训练，但仍属于需release的正式优化工作。
- GAF训练：config=`configs/gaf_v1_member_9201.json` 等3个文件。共同train/dev视图目前null；命令会拒绝启动，需版本化绑定真实SHA。完整成功结局、parent分组与特征身份须匹配；开发数据超过10240条时拒绝，不能静默截断。
- 评测请求文件：`commands/EVALUATION_REQUEST.json`。A 的不可变真实driver尚未发布，实际eval entrypoint为null；未伪造可执行闭环命令。先由P10绑定A driver与B adapter做有限真实集成，后续P20再给正式评测次数。

单机launcher只接受参与主机恰为本机的独立wave，完整命令退出后才释放8卡reservation，失败也恢复占卡；不在单作业或GPU提前完成时启动idle子集holder。联合A/B wave当前拒绝，需共同完成/失败屏障冻结后再接入；超时不等于对端完成。无自动重试；已claim的作业必须由分析端明确恢复决定，不能换output重跑。

正式执行必须给当前物理调用附加 durable journal；默认内存 EventLedger 用于合成CPU测试。实际双账本按A相同规则读取唯一entered事件，终态重复元数据不再加数。未返回和技术失败保留已进入资源；N不承担旁路D/G0，复用a0不按方法数摊薄，嵌套墙钟取区间并集，设备计时未知不冒充CPU提交时间。

CODE_SNAPSHOT.json冻结代码、配置、上游来源与接口；发布后不编辑，正式release绑定其SHA。evidence中的所有样例均synthetic，禁止进入真实训练/测试。共享输入保持只读，B没有删除共享历史资产。
