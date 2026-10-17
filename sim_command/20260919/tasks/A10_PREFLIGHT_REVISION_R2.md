# A10 后续：修正有限预检初始化预算（CPU）

task_id=`A10_PREFLIGHT_REVISION_R2`，task_revision=1，owner=A。A10 r1 的 CPU 准备交付验收，既有回执与不可变 interface_v1/v3 保持原样。新产物另发布版本；此任务不运行 GPU、仿真、环境 reset 或训练。

审核发现：v3 运行链路构造 `metaworld.MT1`，默认生成50个任务并调用50次 reset；正式环境包装还有1次 reset，诊断 reset 再1次，因此真实 reset 至少52、环境实例至少2，而提案写1/1。不能将隐式初始化成本记为零。

请做最小修正：

1. 只对这个初始化链路作定向静态审计，区分 task-set 构造/初始化重置与诊断 episode reset；给明确有限上界，记录实际发生数和来源。仍只允许1个诊断初态、1个诊断 attempt、5次native采样/50 flow、1个策略环境控制步、0完整rollout/反向/monitor/更新、0重试。
2. 新 proposal/release 模板/资源回执同时列出环境实例数、初始化 reset 与诊断 reset 的预算及实际计数。若底层 reset 内有不同于策略控制步的初始化仿真工作，说明其归属，不冒充已执行策略步或额外测试episode；预检墙钟覆盖全部初始化。
3. 将决定上述计数的实际 MetaWorld 外部包源身份绑定到输入 manifest；不原地改共享环境。允许保持现有标准初始化，不为省几个 reset 改成不同环境协议。
4. CPU 检查修正后的预算/计数与授权拒绝路径。只复查变更涉及的必要检查，不重复整套无关准备；已有真实环境可运行性仍未验证。
5. 另发不可变新版 proposal、命令与代码清单，给分析端短差异报告、明确 release 必填字段与 CPU 授权验证命令。命令仍为独立 A-only wave，保留1800+30秒、无重试和全机 holder 生命周期政策。

补充：1800+30秒在现实现中仅限 lifecycle 内诊断进程，前置 CPU hash、GPU 释放/恢复时间不在其中。新版报价明确 timeout 作用域并分别记实际准备/预约/计算/恢复时间，不把1830秒当端到端严格上界。提供纯 CPU 授权校验入口，不用实际 `.sh` 作为 dry-run。

写 `receipts/A/A10_PREFLIGHT_REVISION_R2_{ACK,REPORT,RESULT}` 对应 JSON/MD 回执；产物位于本角色 results/work。接口 v1 不改，不重跑 A00/A10 r1，不重新采集600源。

可并行完成[存储依赖定向核查](STORAGE_DEPENDENCY_REVIEW_V1.md)的 A 部分；只盘点，不删除。
