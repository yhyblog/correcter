# A10：公共数据/评测/日志接口准备

revision=1；owner=A；release=P00_PREP_V1；依赖A00完整盘点回执及[公共准备合同](../contracts/P00_PREPARATION_CONTRACT_V1.md)。本机A00_RESULT.json为complete、资源计数为0且写明缺口后，可继续本任务，不必等B完成。若A00自身受阻，先交具体blocker，不虚构完成。

授权仅限隔离代码/配置编辑、CPU静态/合成检查和已有资产格式审计；GPU模型调用、训练更新及simulator attempts均为0。不要启动真实环境step或载入模型到GPU。

交付：
1. 以当前独立Post/Velocity为基准的隔离代码快照；H与C分离，H>10干预后恢复nativeH。
2. 统一逐episode/调用事件schema，部署成本与实际研究消耗双账本，shadow监测不计N部署成本。
3. 原始轨迹字段与分支/后缀数据视图，按parent episode防止split泄漏。
4. task/source/seed分片入口和幂等恢复方式，不读取旧READY。
5. CPU/静态检查、必要小预检命令、精确预计数量和资源回执。

将公共接口schema与最小样例尽早写到results/A/A10/interface_v1/，单独发布INTERFACE_READY.json供B读取，并向分析端报告路径；后续变更升revision，不原地改变已交给B的接口。工作代码只写work/A，实际产物与报价写results/A/A10。

最终交receipts/A/A10_ACK.json、A10_REPORT.md、A10_RESULT.json。报告必须给出可执行的有限GPU预检命令文件和逐项计数（但本任务不运行）；若预检不能精确预估次数，说明原因和可测量的停止上限。必要资产缺口列入RESULT，已完成的独立接口工作仍可交付。

不在公共仓库原地覆盖封存；仅准备代码/配置。GPU预检需本轮带具体数量的release。B实现外部适配时只依赖已发布接口，不同时编辑公共runner。
