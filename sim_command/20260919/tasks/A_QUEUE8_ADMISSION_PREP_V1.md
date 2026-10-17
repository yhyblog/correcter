# A_QUEUE8_ADMISSION_PREP_V1：下一批8卡正式并发8的资源与入口准备

task_id=A_QUEUE8_ADMISSION_PREP_V1，revision1，owner=A。目标不是占卡率达标，而是8张固定GPU各运行一个独立计划父源、正式parent并发8。此任务与现有A_QUEUE_BOOTSTRAP_V1 r2合并实施，不重复造一套runner。当前Batch3继续原冻结scheduler及临时占卡覆盖，完整交付后结束；不得热改、补源、拆branch/repeat、另开claim。

## 1. 已冻结的下一批

读取 `persistent_queue/plan/NEXT8_FORMAL_CONCURRENCY_V1.json`。这是SOURCES_V2固定顺序的前8 pending：drawer-close、drawer-open、faucet-close、faucet-open、hammer、hand-insert、handle-press-side、handle-press（均-v3），全部train0/cut5。按slot0..7绑定A已有8个固定GPU UUID，源/seed/监督/每parent15cold顺序保持。原17terminal＋Batch3的8reserved排除，不根据上一批成功率替换。

配置必须明确 `formal_parent_concurrency=8`、`one_parent_per_GPU=true`。8个parent各自运行最多15顺序分支，不能同时拆同parent的repeat或以6个holder冒充8路采集。下一批计划最多120attempt及固定116向量见manifest，未用额度不改为额外数据。

## 2. 独立核实资源，不默认沿用2

在不启动任何新模型/仿真/压力测试的情况下，保存带host和UTC的有限只读资源回执：

- RAM：`/proc/meminfo`、本容器cgroup内存上限/current/peak/events，区分主机空闲与容器可用，记录其他工作负载保留量。优先复用已存正式进程RSS/HWM；必要时仅定向读当前本任务族`/proc`内存，标明单进程峰值、进程族聚合、共享页及加载临时峰值是否未知。此前64GiB/parent只是工程预留，不可直接当作实测硬最低；8×64GiB不足不能直接宣告8路不可行。提出有证据的估计、余量和算式；没有峰值证据就如实给保守可执行方案，不填造数。
- CPU：cpuset、cpu.max/有效核数、实际线程配置和有限CPU/IO pressure。拟定8个MuJoCo/模型进程的线程上限，避免8路各占满全机线程；不改变数值采集语义。
- GPU：复用已保存固定UUID/80GB容量与现有状态缓存。必要时最多2次全8卡只读NVML/nvidia-smi状态快照（身份/可用显存/活动进程/利用率），查询单独计量；无CUDA/EGL/context/Torch加载。将自有idle holder将让出的内存与无权终止的其他作业分开，不把占卡进程当科学计算。
- 容量：限定目标output/cache/temp路径的statvfs、free inode、现有共享预约账本；已知project quota可读，未知继续披露。8源准入含free floor为93,952,475,136B，564096 inode，按既有bounded风险逐次校验，不把statvfs当project quota、不重复扣A已预留额度。确认8路并发temp/cache约束，不全树扫描/删除。
- 共享输入与I/O：列一次输入体积与每cold分支必须读取的权重/manifest路径，复用已有SHA与Batch1/2/3保存的load/hash时段、`/proc/<owned pid>/io`/cgroup io.stat等有限计数；区分逻辑重复读取、page cache、实际共享后端读取。FUSE或其他不可见后端不以本地diskstats=0冒充没有压力。按8个父源、120cold上限计算逻辑载入/校验压力，列现有共享链路限速/吞吐证据与未知，不新开dd/fio/模型benchmark、不重hash大权重。

最多6组CPU/OS采样、总观察窗口≤60s，输出≤16MiB；这是本任务读系统元数据的范围，不限制正常CPU工程实现/定向synthetic检查。优先已有记录；此任务不改变当前holder或正式进程生命周期。无法测到的指标明确null，不能为了填满字段加新的GPU实验。

交 `RESOURCE_ADMISSION.json`：逐资源证据路径、时间、单位、并发8估计、余量、硬限制与unknown；给出 `requested=8`、`supported_max` 或明确的证据下界/上界，以及当前可执行的具体配置。若8被硬限制否决，逐项说明限制值、8路需求、计算公式及最大可执行整数；不能返回“按经验2”或把unknown伪称硬阻塞。若仅I/O加载冲击，可提出有上界的启动错峰/加载槽控制，保留8个独立parent正式运行，不能暗中用全局2-worker串行器限制整批。

## 3. 完成可执行8路入口

复用已冻结采集器，仅修改/补齐调度、授权和资源准入。保留同一node外层reservation与formal.lock、每父源私有目录/进程族/账本、固定UUID与独立RNG、15cold顺序。GPU上的自有holder全部退出ACK之后才启动该卡正式GPU加载；不能靠START出现后的异步stop冒充先让出。正式活动中的CPU等待/低利用率不引入同卡holder。空闲卡按最新OCCUPANCY_OVERRIDE补位，辅助费用分账。

必要CPU/fake检查仅覆盖新行为：8真实worker槽均可同时存活；slot/UUID/source唯一；每parent分支顺序；低资源拒绝与最大并发算式；8路读写目录隔离；holder退出确认在正式Popen/首GPU进入之前；单worker失败不会杀其他7路；整组退出/发布后下一批；重复claim拒绝和终端关闭后持续工作。不要重跑旧测试全集、重扫历史库存或修改科学实现。

实际控制面安装/无GPU后台检查可沿既有V2授权推进，不等待B。先交可审的package/命令/配置/小文件SHA；所有真实采集仍等待本次独立首8路计算release。配置和授权状态表统一ready/running，不再制造released-board旧问题。

## 4. 交付与后续放行

交 `receipts/A/A_QUEUE8_ADMISSION_PREP_V1_ACK.json`、`_REPORT.md`、`_RESULT.json`。输出 `RESOURCE_ADMISSION.json`、`CPU_READY.json`、8路配置与定向检查、确切shell/argv、独立辅助调度/监测分账（科学部分仍原116项）、完整未授权proposal与RELEASE_TEMPLATE。

未来正式task=`A11_COMMON_POOL_QUEUE8_FIRST_V1`，release=`P11_A_COMMON_POOL_QUEUE8_FIRST_V1`。具体code/config SHA、runtime输入、容量准入、timeout及claim/output路径在交付中绑定；proposal不是已授权真实release。分析收到资源与可执行入口证据后发布独立计算release；当前没有数据支持前，不预称8路可运行或退回2。

只对首次8路切换做这次资源/配置冻结，不回到每8源人工审批。首批使用原计划数据，不新增“8卡试验”源；首批退出/账本/发布与资源门通过后，可按该release和V2总授权明示的自动续批规则推进余下源，无需聊天逐批放行。若需要低于8，先交具体最大并发及原因，由分析在本次release明确记录。

本CPU/元数据任务不创建正式command/claim、不执行新模型/采样/flow/环境/reset/训练/评测/删除。当前Batch3和旧release机会不复用，B不作为任何前置。
