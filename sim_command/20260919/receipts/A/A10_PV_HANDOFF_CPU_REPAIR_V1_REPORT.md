A10_PV_HANDOFF_CPU_REPAIR_V1 / revision1 已完成CPU_READY。当前CONTROL27/TASK_BOARD34、共享guard和旧包/回执未改；无安装、daemon重启、holder查询/停止、真实launcher/claim/GPU或模型调用。V3计算和共享安装均待分析独立授权。

最小补丁只改变新run客户端等待：CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS接受ASCII整数1..300，未设仍90；本V3固定300，非法值在start/锁/query前拒绝。300来自8×(15+5)=160加140秒调度/轮询余量；query仍原15秒timeout，超时后才返回空也不启动，非端到端上界。daemon全部函数及run的spawn/信号/等待/锁尾部字节未改。未来沿用原lifecycle active路径、同一formal.lock及继承FD，无嵌套预约/释放重拿；无需重启daemon。GPU_HOLDER_STOP_TIMEOUT_SECONDS未用作修复。

- 唯一未来共享替换路径：`/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py`。
- 原SHA：`d499982dff72c3b74ddab0e13e359edccb5f282900c534030b3816b58495fcaf`。
- 新SHA：`7910c567a47ddf68294d92fc9698cc780aeb130ddefde0337414bfcd88cb85a4`。
- 精确patch、原字节回退、安装/回退命令和独立未授权模板位于 guard_patch/；INSTALLATION_PROPOSAL列出前置SHA/CONTROL及原子替换范围。当前只准备，真实sh不安装共享文件。

V3：A10_PV_OFFLINE_PREFLIGHT_V3 / P10_A_PV_OFFLINE_PREFLIGHT_V3 / revision1；新包 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_PV_HANDOFF_CPU_REPAIR_V1`。PROPOSAL SHA=`c07750be489911e2d7363729d8ed186605f8792337c9f4118677e20a3af1ca2a`。run/wave/shard/claim/output/cache独立；board ready、正式release released、当前模板UNAUTHORIZED_TEMPLATE同源。INPUT与EXTERNAL两处guard引用均只预期新SHA；原SHA仅用于安装前比对/回退。sh显式export300，实际launcher在父NVML前校验环境，原lifecycle传给新run客户端；缺参数或未装预期补丁会拒绝。

381份运行代码中377份沿用字节不变，3份仅改身份/路径和handoff守门，新增1份纯元数据helper；诊断run数值函数字节不变。所有其他input/external条目、数值CONFIG字段、66caps、step0/raw50/noise/encoder/Q/PCA/norm、严格载入、独立自身半径、父子私有账本与1800+30诊断timeout保持。未读模型/数组/外部库字节，未hash大权重或重跑算法全套。

26个guard fake通过：120秒清空时旧90拒绝/新300只启动1次；持续外部占用、driver异常、无效值、晚返回空拒绝；原锁和继承FD覆盖组退出，TERM/KILL及信号转发只触及fake自有组。10个元数据case、实际环境/manifest临时fixture、6个安装/回退纯元数据case、发布CLI及变更AST/bash-n通过。无真实guard导入、formal.lock、进程信号、GPU/holder操作或安装入口main调用。

失败证据仅复用原poll最后观测，最多1条JSON/64行NVML host PID、错误2048字符；记录查询起止、尝试数，缺观测null，不伪称deadline新快照或container PID。run-client轮询独立于66caps中的身份核验父1+子1；名义最多300个尝试，无额外query。继承V2失败的其他原因未被新实测排除，本次无数值/硬件成功结论。短报告及manifest随RESULT；等待分析决定安装和计算后续授权，B不变、删除0。
