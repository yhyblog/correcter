# A触发实验：发布故障修复与原授权接续

2026-09-22用户要求检查A停止问题。分析核对RESULT_r2、原始stderr和本机/proc：科学worker已退出，旧service2093892仍存活但处于终局空闲；8holder进程存在。不是正在继续计算，也不是5000条已完成。

## 原因与已保留工作

report.py:85同时展开episode与monitor字段，mode重复导致TypeError，同处planned_random_cut也重复。首格报表失败使manager中断8个在途episode，终局report再次失败。旧原始代码/claim/RESULT/r2回执不覆盖。

当前518attempt：H10 Random-once500有效/308成功；H10 G0-multi10有效/10成功；8技术中断success=null；4482未启动。全部510有效终局保留且禁止重跑。旧r2的8中断不是模型任务失败。

## 立即执行，沿原授权，无二次许可

1. ACK本决定，确认无其他新recovery已运行。只在A私有后继包修正发布器重复字段：episode身份/科学模式有明确归属；monitor字段允许同值去重或独立命名，冲突保留错误，不静默覆盖科学身份。同时处理planned_random_cut。不要修改模型、G0阈值、随机时机表、源/seed、C10或算法。
2. 用已有510有效记录做必要CPU发布验证，先交H10 Random完整表及G0-multi部分状态，不新增GPU预检，不重放终局。未知/non-finite描述性统计用null+原因，不能把NaN变0。
3. 小型改变管理器的普通报表错误路径：保存publication_error并限次CPU补发布，继续已经授权的科学队列；原始episode结果必须先落盘。科学安全/授权撤销/数据存储失败仍按现行退出，不能把所有异常都忽略。最终允许compute_complete/publication_pending分列，普通表格导出不得再次直接杀worker。
4. 独立recovery run/command，复用原科学task和stage预算。准确源表为4482未启动+8技术中断各一次=4490；从已有SAVED_EPISODE_INDEX/claims/原源表构造并检查与510有效交集为空。8中断若发现可可靠恢复的真实终局，优先CPU恢复且不重算；否则按真实技术失败的唯一一次修正。其余新失败按原单源最多一次规则且总cap5500。
5. 当前原service可由执行端按自身host/boot/start_ticks确认后停止/封存其空闲通知服务，或留作只读终局服务；不得让其重复启动。只开一个新正式预约和8常驻worker，同一全波holder规则。稳定8模型/真实返回后写STABLE_HANDOFF并结束LLM等待，后台完成剩余单元，固定原会话终局事件。
6. 保留原518消耗与历史9360：当前累计9878；此次基础4490完成后stage5008、A累计14368，仍在原stage5500及累计18000内。此决定不扩任何科学额度、不新加初态、不改变已关闭release，也不恢复475采集。
7. 新回执receipts/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RECOVERY_r2_ACK.json、_RUNNING.json以及后续_RESULT_r3等；记录旧510/新结果合并去重、原始8中断、修正次数、正式族退出与holder恢复。终局汇总回原原5000个唯一单元分母，技术重试不是新增独立样本。

原授权仍为deadline_20260924/TRIGGER_TIMING_MULTIPLICITY_AUTHORIZATION_V1.json。分析确认其允许必要私有修复与真实失败单次纠正。科学截止/8小时原任务墙钟边界保持，不因recovery重置；不等待B/C，不重跑N/once/旧pilot。
