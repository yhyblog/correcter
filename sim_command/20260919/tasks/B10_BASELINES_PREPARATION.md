# B10：外部基线/E6/E8接口准备

revision=1；owner=B；release=P00_PREP_V1；依赖B00完整盘点回执及[公共准备合同](../contracts/P00_PREPARATION_CONTRACT_V1.md)。本机B00_RESULT.json为complete、资源计数为0且写明缺口后，可继续本任务，不必等A完成。若B00自身受阻，先交具体blocker，不虚构完成。

授权仅限隔离代码/配置编辑、CPU静态/合成检查、已有资产格式审计和必要公开小型源代码checkout；不下载大权重、不改共享Python环境。GPU模型调用、训练更新及simulator attempts均为0。

交付：
1. 本地VLA-Corrector在共同数据上训练与同协议评估的适配清单；旧复现checkpoint保持只读。
2. 选择一个公开critic近邻并冻结版本/目标/动作与观测映射，优先根据字段兼容及可用工程决定GAF-v1或QGF，不依据测试效果挑选。
3. E6视觉异常触发接口与开发阈值规则，固定下游R、每episode最多一次；与完整原VLA-Corrector的多次触发规则区分。
4. E1四损失训练矩阵的代码配置与旧600源身份，保持同初始化/更新范围/模型容量。
5. E8资产与动作接口准备；先复用已有环境，不把缺少checkpoint变成未经安排的新VLA SFT。
6. 数据视图、代码快照、CPU/静态检查、正式GPU任务的数量与成本报价。

先完成不依赖公共runner的视图/基线审计和隔离adapter；A的results/A/A10/interface_v1/INTERFACE_READY.json到达后核对接口。不要因A尚未发布schema就无事等待，也不要同时修改A接口。所有差异写到receipts/B/A10_INTERFACE_FEEDBACK.md供A与分析端读取。

代码写work/B，产物与报价写results/B/B10；交B10_ACK.json、B10_REPORT.md、B10_RESULT.json。列可执行的有限GPU预检命令文件和计数，不在本任务运行。已有VLA-Corrector优先，公开近邻版本/字段不确定时交明确候选建议，不默认升级成更多基线。

训练等待同一公共数据manifest与单独release；不额外采私有训练数据、不改A的公共接口、不给QPILOTS新增在线训练。
