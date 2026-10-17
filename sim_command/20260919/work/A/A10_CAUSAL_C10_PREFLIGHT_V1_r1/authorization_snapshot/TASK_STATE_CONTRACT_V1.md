# 分析端发布与执行端任务状态合同 v1

2026-09-19；针对本轮后续任务发布。历史快照和冻结程序不改。

- TASK_BOARD任务状态：待执行且条件已齐用 `ready`；执行已ACK并开始用 `running`；完成验收用 `complete`；失败用 `failed`。父级阶段可用 `in_progress`，不当作可执行子任务状态。`released` 不作为冻结离线P/V入口可接受的TASK_BOARD状态。
- 计算release自身的 `status=released` 表示该独立release获批；不复制到任务板。DISPATCH的queued/published只描述投递，不代表ACK、验收或计算完成。
- 任何状态都不能单独放行计算：当前CONTROL的唯一active task/release/path、allowed task、全局和单任务caps，board唯一id/owner/revision/status/release，以及冻结proposal/template/host/输入/代码身份必须全部一致。
- 分析端从执行端CONTROL_REQUIRED的board条目构建发布记录，发布前做实际元数据合同的纯CPU一致性核对；此核对不执行真实命令、不写claim、不检查GPU或加载模型。执行端不得为通过守门而自行改CONTROL/TASK_BOARD或放宽冻结代码。
- 单次命令机会与claim/compute计数分开。命令在claim之前失败时，真实claim和计算保留0；不因此自动获得重跑机会。关闭决定保存在独立CLOSED与验收文件，旧release及回执不覆写。
- V1已关闭且其代码硬编码身份。后续V2须由新的CPU修订包和独立release承接；旧机会、未进入额度和旧成功预检均不授权新计算。
