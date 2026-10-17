# B：E1汇总与E8适用性接续

任务 `B_D24_EXTENSION_REMAINDER_V1`，revision1，owner B，是既有 `B_D24_SPRINT_V1` 的接续子任务。立即按已有D24授权执行必要适配/评测，不要重新申请训练评测范围。授权见 `deadline_20260924/CONTINUATION_AUTHORIZATION_20260922_V1.json`。保留已经admit的有效任务，不因本派单停止或重复启动。

## 先交E1表，同时启动E8

- `results/B/B_D24_SPRINT_V1/r1/D24_E1_RENDER_REPAIR_r3/RESULT.json`显示修正1120条已于9月22日00:02 UTC完成，退出0。合并r1仍有效的80条，形成48拟合/12 ensemble、24格×50源的1200条最终结果。
- 旧r1的1120条无效渲染必须排除，修正批次不能再跑。输出每loss/fit seed/Post-V的成功数、分母、技术失败、调用耗时和配对差值；保持B自己的renderer与冻结source协议，不拿A主表其他renderer的格替代L11对照。
- 科学汇总CPU工作不阻塞GPU执行。原48拟合不重训，不重新跑旧全套测试/证据审计。

## E8自动队列

优先Smol+Post、X+Post、LIBERO+Post，互不等待；有可执行单元即进入原后台八卡调度。各设置先固定必要适配与源表，之后自动跑完。

1. SmolVLA：使用已选050000底座，沿已完成N的H50/K10与固定500源。做Post对照，不续训Smol。冻结π0.5视觉/语言特征及D/G0/Q需要时可作外部模块，不能把不同VLA的embedding直接冒充原PCA输入。
2. X-VLA：8卡SFT已经完成30000步，N403/500、技术失败0。使用 `results/B/B_D24_SPRINT_V1/r1/jobs/xvla_mt50_s42_D24_r2/training/checkpoints/030000`，沿 `work/B/B_D24_RECOVERY_V1_r1/XVLA_EVAL_BATCH.json` 的H30/K10/NFE10、物理4维状态/动作与固定500源，直接适配Post并评测；不再SFT，不从test选checkpoint。
3. π0.5+LIBERO：保持已有官方权重/norm、H10/K5、7维动作/8维状态、四套件各100源的实际随机reset协议。先做可解释的Post适配，按真实坐标/单位处理XYZ与夹爪，未适配旋转部分保持原动作。若D/G0未接通，明确标为Post算子迁移及实际干预规则，不能称完整方法或把MetaWorld特征硬套LIBERO。
4. 上述Post接通并排队后，只有已经具备合理flow hook/动作映射的设置才补Velocity；没有则记录具体缺项，继续其他设置，不让Velocity阻塞Post。

必要开发只用原批准的每设置最多40个dev父源/200次dev rollout，可做必要小模块适配，不增加基础模型SFT，不用test成功率调阈值/半径/模型。如固定规则由文档确定即可实现，无需为了“验证一致性”新增dev或GPU预检。

N已有Smol496有效/4未知；LIBERO394有效/5技术失败/1未知；X500有效。先复用已完成有效N，不整组重跑。未知episode只有能确认未完成/无活进程且已有原始失败依据后才能按原重试规则补，不把unknown写0。Post仍按冻结源表运行，比较同时给各自有效分母与双方有效配对子集；不因失败而换源。

E6与E3新的未启动任务现归A，B不要再admit，CPU资产交A可直接读。若收到本派单时某个同单元已真实启动，保留它并报run/source/method身份，不杀任务；其他E1/E8正常接续，不等待A。

## 后台执行及交付

- 接续任务与B原D24共用累计16000 rollout attempts、500000小网更新总上限。此接续新增attempt最多6000，适配小网更新最多100000，均受原剩余额度限制；不重置计数。X已完成30000更新，不追加；Smol/LIBERO新增SFT=0。
- 直接复用现有独立后台队列和完成事件，不等待完整generic READY/callback认证。适配完成就按文档自动衔接，不每批等待分析签字。
- 正式整波全部holder停算，包括加载/间隙/提前完成卡；全部formal后代退出后恢复8holder。8卡实际有用任务优先，不终止无关进程、不在formal波内启动辅助holder。
- 只保留必要模型/动作单位/有效RGB/源分割检查及真实成功/技术失败；不开展完整SHA/隐藏状态/MJB/全套CPU/单独GPU预检。已修复渲染的必要有效性检查沿用，不重新做成前置工程项目。
- 每设置先发已完成的N/Post表、有效配对子集、调用/时间、训练覆盖与适配范围；图表CPU汇总并行。交付 `results/B/B_D24_EXTENSION_REMAINDER_V1/` 与 `receipts/B/B_D24_EXTENSION_REMAINDER_V1_*`，保留原父任务和原始结果。
- ACK后先接续可执行任务。稳定后结束会话等待，让完成事件唤醒原会话；终局自动做汇总并接下一已授权设置。北京时间9月23日20:00停止新增实验、23:00表图截止。
