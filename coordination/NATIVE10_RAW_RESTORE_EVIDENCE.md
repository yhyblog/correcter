# Raw命令与独立恢复计数：已完成证据回传

2026-09-16。针对较早的raw/restore审查通知，执行端只读复核已封存P0和主批次证据。此次复核没有发起额外仿真、训练或修改旧产物。当前首轮采集已由后续READY v4放行；live READY v5明确继续该冻结波次，并单独条件放行零更新预检。

## 保存内容与不变量

P0每个bank的 `candidates/<case>/cutNNN/directions.npz` 保存 `raw_a0`、`critic_a0`、`mask`、各方法 `*_actual_delta` 和 `*_critic_commands`；最终raw计划在同目录 `plans.npz`。

主版本 `banks/round1_labels_v1/<case>/cutNNN/directions.npz` 保存 `raw_a0`、`critic_a0`、`clearance_mask`、`actual_deltas`、`critic_candidates` 及通道/随机构造量；`plans.npz` 保存13个最终raw计划；`formal_directions.npz`保留三种引导原始审计字段。实际执行命令另存在每分支 `trajectory.npz::actions`，不以生成器自报代替执行核对。

对P0封存数组复核：

- a0逐位恒等20/20；120份正式构造计划及260份13候选预览计划中，零delta坐标、mask外坐标和十步外tail均逐位保持raw基准（380/380）。
- `C(final_raw)-C(raw_a0)-actual_delta` 最大绝对误差0；critic候选与同一 `C=clip(.,-1,1)` 表示一致。
- 100个预览正反对的最大对称误差为 `2.9802322388e-8`，半/全半径关系误差同量级，低于预登记 `1e-6` 容差。实际扰动最大XYZ RMS/L∞为约 `.049999953/.149999857`，grip RMS/L∞为约 `.099999910/.299468756`。
- P0总审计61152项通过、errors=[]；400条真实分支核对执行前缀与指定raw命令一致，后缀也按正常raw前十步执行。这里的“无二次clip”指执行端未额外裁剪已生成raw计划，环境本身的既有控制限制仍保留。
- P0的13候选是构造预览，不能当成已执行的13臂结局。主阶段首固定50源已真实执行13候选＋normal、各4次，共2800分支，并通过独立全链审计。

## 实测超界与物理探针

| 统计口径 | grip超出[-1,1] | raw范围 | 最大超界量 |
|---|---:|---:|---:|
| 五任务native10队列探针的150个实际执行步 | 9/150，6.00% | [-1.0070829391, 0.9090753198] | 0.0070829391 |
| 20个P0 a0的十步执行前缀 | 11/200，5.50% | [-1.0076594353, 0.9125539064] | 0.0076594353 |

原生队列超界来自stick-pull 2/30与stick-push 7/30，其余任务0/30。a0全50步计划为11/1000，但后40步不是此次执行前缀，因此不使用这个较小比例描述执行超界。

真实物理探针为五任务各一个预登记恢复状态、四个命令 `grip=+1.5/+1/-1.5/-1`、每次最多3控制步，共20个独立计费attempt、10个raw/clipped配对。加载模型实测：两个actuator均 `ctrllimited=[1,1]`、`ctrlrange=[[-1,1],[-1,1]]`，`disableflags=0`，`clampctrl_disable_bit=256`，`control_clamping_disabled=false`，MuJoCo版本3.6.0。`actuator_forcelimited=[0,0]`，因此不能将控制限幅描述成力幅度裁剪。

10对的qpos、qvel、排除ctrl的物理向量、actuator force、广义执行力、时间及contact距离最大差均为0；contact数量/几何、success/done标志相同，reward差也为0。原始 `data.ctrl` 差为0.5，已保留并单独报告，不要求这个记录值相同。五任务均观察到环境接触，但不声称覆盖了所有夹持接触情形。

`C`会合并不同超界raw数值；本批探针未发现这种合并对应不同物理效果。结论限于当前加载后端、已测状态、两个饱和符号和三步窗口，不能据此宣称所有长轨迹、状态或reward形式均等价。所有正式臂继续保留raw接口；候选不能仅按clipped数组去重。

## 逐阶段独立bank恢复与当前预算

较早RAW_BUDGET修订正确补入了1000次：800个主源初次bank＋两轮开发各100。随后EVAL20将cal/held各由50增至100，后缀次数分别改为2/4，使分支量不变，增加capture100和bank100。目前为900个capture、1100次独立bank恢复。

| 阶段 | source capture上限 | 独立bank恢复上限 | 分支上限 | 阶段合计 |
|---|---:|---:|---:|---:|
| 第一轮300train＋100dev标签 | 400 | 400 | 22400 | 23200 |
| 首轮实际开发100源 | 0 | 100 | 2000 | 2100 |
| 第二轮300train标签 | 300 | 300 | 16800 | 17400 |
| 第二轮实际开发100源 | 0 | 100 | 2000 | 2100 |
| cal100×5×2 | 100 | 100 | 1000 | 1200 |
| held100×5×4 | 100 | 100 | 2000 | 2200 |
| 主阶段合计 | 900 | 1100 | 46200 | 48200 |

另加P0上限600，计划总数48800；技术/合法初始化替补储备1200，总硬限50000。P0已用564，包含32次并发candidate restore，不再加进主阶段1100。branch内部为续跑执行的restore包含在该branch attempt；独立新bank恢复单列 `candidate_restore`。所有失败/合法重试计数保留，不借旧653/700余额，也不凭尚未发生的复用节约追加搜索。

## 证据路径

以下产物路径相对 `Corrector/outputs/native10_training_20260916/`：

- `p0/audit_native20.json`：前500次完整审计，SHA `5e9af04e9d6d84090421ee0bf2a01f6e837cae06838787535f3b0e7909bb9085`；后续64次另见 `p0/concurrency32/audit.json`。
- `diagnostics/raw_clipped/<五个2026110000..4任务case>/summary.json`、`arrays.npz`、`complete.json`：模型限制、原始状态/力/接触数组、逐对比较及attempt身份。
- `diagnostics/native10_queue/<case>/arrays.npz::native_actions`：实际raw队列超界统计。
- `candidates/<20个P0case>/cutNNN/directions.npz::raw_a0[:10,3]`：a0执行前缀统计，源名单/cut绑定于P0审计的source_rows。
- `progress_audits/watcher_round1_v1_01_first50.json`：主13候选真实分支、原始命令、mask/映射及输入SHA审计。
- `budget/attempts.jsonl`：唯一新工作流账本。

权限及预算依据：`coordination/NATIVE10_RAW_BUDGET_AMENDMENT.md`、`NATIVE10_EVAL20_AMENDMENT.md`、`NATIVE10_ROUND1_ANALYSIS_DECISION.md`及当前READY v5。P0、主采集各自使用原冻结快照，历史材料不覆写。
