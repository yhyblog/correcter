A10_PV_AUTH_METADATA_CPU_V1 / revision1 已完成，CPU_READY；当前 CONTROL24/TASK_BOARD31 及全部零计算额度未改。新包：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_PV_AUTH_METADATA_CPU_V1`。

未来身份固定为 `A10_PV_OFFLINE_PREFLIGHT_V2` / `P10_A_PV_OFFLINE_PREFLIGHT_V2` / revision1；完整 `BOARD_TASK_TEMPLATE.json` 与 `CONTROL_REQUIRED.board_task` 同源且逐项相等，初始 board.status=ready（冻结入口亦接受 ACK 后 running），未来 release.status=released。当前 RELEASE_TEMPLATE.status=UNAUTHORIZED_TEMPLATE，V2 真实 release 不存在，真实命令/claim=0。

- 新 PROPOSAL SHA256：`9e7a80a211eba6a4e3c65bd2fb3764fe0fbd974c4190c9f2e77091c04a62e02c`。
- 新 CODE_MANIFEST SHA256：`6aebda83f18a1698e815d522866106a0e84eb1adf669b7d097131f3f858ac161`。
- 新 RELEASE_TEMPLATE SHA256：`194735851bcf6ac4bbfdc6bb0d189bf91bd6d9bf58e5f72a0205e386c285738a`。
- `A10_PV_OFFLINE_PREFLIGHT_V2_r1_A_wave07`、`corrector-sim-20260919-A-PV-offline-V2-wave07`、`A-PV-offline-V2-shelf-place-step0-cached-once`；claim/output/cache 均采用独立 P10_PV_V2 路径，见 PROPOSED_COMMAND.json。

380 份运行代码中 377 份字节不变；仅 contracts/launch/diagnostic 三文件改身份或路径字符串，归一化 AST 相等，diagnostic.run 源码字节不变。sh 仅改包根。输入清单、外部源清单、CONFIG 字节不变，沿用已验收 SHA；未读取其模型/数组/外部库条目，未 hash 大权重。66 项 caps、step0/raw50/seed/noise、encoder/PCA/norm、严格载入、独立自身半径/只 C10/raw 尾部、私有父子账本、1800+30 子进程 timeout 和全 A8 holder 生命周期不变。逐文件证明见 DIFF_MANIFEST，精确补丁见 work/A/A10_PV_AUTH_METADATA_CPU_V1_r1/RUNTIME_IDENTITY_PATH.diff 和 AUTHORIZATION_METADATA.diff。

41 项定向实际元数据函数 fixture 全符合预期：ready/running 通过；released、旧 V1、错 active identity/path/caps/revision、五项 SHA、host/device/cuda/timeout 拒绝。另验证关闭文件及独占写入重复拒绝；重复保护仅对已有临时标记调用实际 write_new，并核对 claim 的调用 AST，claim 函数从未执行。纯 JSON 发布入口 2 项检查及实际 CLI fixture 通过；变更 AST 与 bash -n 通过，未重跑完整算法/fake 套件。用法见 PUBLICATION_CHECK_USAGE.md；它不跟随大文件引用、不发放授权。

未来单次预算仍 1 offline attempt / 1 guided / 10 flow，Post1 + Velocity3 动作梯度，10 ensemble / 40 成员前向，完整 66 项及父子分账沿用原提案。缓存诊断 Post0/Velocity1 不能充当部署成本 Post1/Velocity2。数值行为仍待验证；历史五任务 Q 的适用范围未扩大。

本任务 Torch/dlopen/NVML/CUDA/EGL、模型/梯度、环境/reset/render/物理/训练、真实 launcher/claim、holder 查询/停止、删除均 0。旧包/回执未改，B 不变。本次只提交 CPU_READY 与未授权 V2 提案，等待分析独立 release；V1 仍为命令1、claim0、计算0、holder未停的已关闭证据。
