from pathlib import Path
from datetime import datetime,timezone
import ast,json,hashlib,sys
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');R=B.parents[2];P=B/'results/A/A10_CAUSAL_C10_CPU_V1';W=B/'work/A/A10_CAUSAL_C10_CPU_V1_r1'
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size_bytes=p.stat().st_size)
def put(name,x):
 p=P/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(x if isinstance(x,str) else json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
config=json.loads((P/'config/CONFIG.json').read_text());sm=json.loads(Path(config['initialization_source_manifest']).read_text())
selection=[]
for member in config['DG0']['members']:
 for kind in ['D','G0']:
  path=Path(member[kind+'_checkpoint']).parent/'complete.json';m=json.loads(path.read_text())
  assert m['checkpoint_sha256']==member[kind+'_sha256']
  if kind=='G0':assert m['world_seed']==member['D_seed'] and m['target']==config['DG0']['target'] and m['deployable'] is True
  selection.append(dict(kind=kind,metadata=ref(path),checkpoint_path=member[kind+'_checkpoint'],checkpoint_sha256=m['checkpoint_sha256'],
    selected_step=m.get('selected',{}).get('step'),target=m.get('target'),world_seed=m.get('world_seed'),parameter_count=m['parameter_count'],weight_bytes_read=False))
put('audit/DG0_ASSET_BINDING.json',dict(status='CPU_METADATA_MATCH',rows=selection,threshold=.05,threshold_changed=False,
    D_horizon=5,actual_G0_signature='BenefitModel(batch_current_context_and_next5_known_commands, D_predicted_next5_visual)',
    matured_residual_input_to_G0=False,training_target_unchanged=True,MT50_training_claim=False))
source_paths=[Path(x) for x in sm['source_hooks'].values()]+[
 P/'code/vendor_vla/src/lerobot/envs/metaworld.py',R/'ACT-RECAP/src/ac_tmil/ogg/experiment.py',
 R/'ACT-RECAP/src/ac_tmil/future_aware/models.py',R/'ACT-RECAP/src/ac_tmil/future_aware/critic.py',
 R/'ACT-RECAP/src/ac_tmil/ogg_research/experiment.py',R/'Corrector/experiments/native10_training_20260916/adapter.py',
 B/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1/code/vendor_backend/metaworld_pi05.py',B/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1/code/vendor_backend/contracts.py']
functions={str(x):[] for x in source_paths}
for path in source_paths:
 text=path.read_text();tree=ast.parse(text)
 relevant={'_make_tasks','reset','reset_model','_reset_hand','do_simulation','set_state','get_env_state','set_env_state','_make_envs_task','_format_raw_obs','capture','restore','spatial','load_world','physics_substeps_for_control_step','step','replay_actions_for_warm_start'}
 for node in ast.walk(tree):
  if isinstance(node,ast.FunctionDef) and node.name in relevant:
   functions[str(path)].append(dict(name=node.name,start_line=node.lineno,end_line=node.end_lineno,source_sha256=hashlib.sha256(ast.get_source_segment(text,node).encode()).hexdigest()))
put('audit/TARGETED_SOURCE_REVIEW.json',dict(status='CPU_STATIC_ONLY',sources=[dict(ref(p),functions=functions[str(p)]) for p in source_paths],
    checked_formulas=['MT1 singleton50task resets; wrapper1; explicit native reset1; no auto-reset controls',
        'native reset invokes reset_model twice; each reset_model hand50 calls at frame_skip5',
        'new fresh wrapper created once per child; no restore/reset between cut, C10 and H20 refill',
        'policy schedule floor((i+1)*400/30)-floor(i*400/30)',
        'native forward2construction +2per reset_model +1per successful control',
        'one full-RGB observation for reset and each returned step',
        'history at cut5 contains obs1..5 and actions1..4, reference stores t0 known actions0..4'],
    package_imports=False,large_weight_hashes=0,external_sources_not_reinventoried=True))
put('STATE_RESTORE_REVIEW.md','''# 状态恢复范围与有限替代路径

静态结论：当前后端没有可据此宣称完整状态等价的恢复接口。`SawyerMocapBase.get_env_state()` 只复制 qpos/qvel；`set_env_state()` 调用 `set_state()`，会再调用 `mj_forward`。旧 native10 adapter 的 restore 是 reset 后执行已有动作，再比较物理数组、reward/success、图像和 fingerprint；它是回放核验，不是完整状态反序列化。本包没有调用这些恢复函数。

未得到完整覆盖证明的状态包括 MuJoCo time/act/ctrl/mocap、外力和 solver warm-start/隐藏量，修改过的 model body/site 数据，环境上一观测/稳定观测/随机向量/任务隐藏状态，NumPy/Python/Torch 与环境 RNG，elapsed/原生 path length，wrapper、动作队列和 policy 内部状态。不能由 qpos/qvel、RGB 或旧 train600 轨迹推出这些状态等价。

本提案请分析批准的有限替代：同一 wave、同一 formal.lock，依次启动 Post 与 Velocity 两个新子进程。各自创建一个 wrapper（内含 taskset 临时 native 环境和实际 native 环境），以固定环境/采样 seed 重新生成并执行 5 步 prefix。没有 shared-prefix 节省，没有实际状态恢复调用。每个子进程只有一个 native EGL context，结束并确认前一进程组无残留才进入下一分支。

Velocity 到 cut5 时，CPU 比较两条保存的观测像素/proprio/context SHA、prefix raw plan SHA、动作/reward/flags/物理时间。任何差异即在 V 干预之前停止，不改 seed 或重放；即使这些证据相同，结果仍明确 `hidden_state_equivalence_proven=false`。两分支是固定开发源的独立回放诊断，不能据此作配对性能估计。

若第一分支提前成功/terminated/truncated，则停止对应路径并结束这个最小 wave，第二分支不进入。末态仍不是任务成功率样本。完整两分支的报价是上限，提前停止只据实收费，剩余额度作废。
''')
put('CAUSAL_TIMELINE.md','''# 固定 shelf-place 开发源：H20 / cut5 / C10

| 时点 | 当时真实可见输入与操作 | 保存与因果边界 |
|---|---|---|
| 初始化 | 独立新 wrapper/MT1，固定 seed；一次完整 reset RGB | 区分 native reset entered/returned 和完整 RGB observation returned；无旧缓存帧 |
| t0 | obs0 单帧 mask=00001，past actions 全零；新 raw50，队列仅前20 | D241/242 用 obs0 与已知计划 actions0..4 预测 obs1..5，预测在执行任何 prefix 动作前保存 |
| t1..t4 | 依次执行 prefix 的有界 float32 action，接收真实 reward、success、terminated、truncated 与 RGB；singleton encoder | 仅积累已到达观测与已执行动作；首次成功或原生终止先停止，不继续模型调用 |
| t5 合法性 | 先看终止，再看自然刷新；必须 age5、旧队列余15、剩余预算295≥10、仅一次干预 | cut5 不是自然刷新；参考 plan ID/动作必须与实际 0..4 一致 |
| t5 特征与残差 | 当前 history=obs1..5；past actions=actions1..4。参考 D(t0) 的末预测与真实 obs5 求原始归一化残差 | obs6 及以后不在上下文中；Q 不取旧 step0/step1 缓存 |
| t5 D/G0 | 用此时 context 和旧计划已知 actions5..9，D 预测 obs6..10；G0 消费该预测 | 既有 G0 **不消费成熟残差**；残差仅独立诊断。两成员 raw regression mean >0.05 为真实报警；目标仍 execute5_then_fixed10 |
| t5 P/V | 丢弃旧 H20 余量，各自新 a0。Post1次动作梯度；Velocity 新锚点+guided、末3flow梯度；各自独立半径、无Q接受门 | `real_G0_trigger` 与 `forced_engineering_intervention` 分开。固定 cut 未报警时可走预定工程干预，但不冒充触发成功；V 的 anchor/guided 同 seed noise SHA 必须相同 |
| t5..t15 | corrected raw50 只承诺执行前10，逐步保存真实 transition/RGB | success 与 native terminated 分列；提前停止不补满、不重试。raw40尾部位模式由既有 audit 核验 |
| t15 | 10步已执行后丢弃余40，不再从旧/纠正尾部取动作；清空 policy 两类内部队列 | 保存 discard 事件。新 native 全采样 raw50，队列 horizon20 |
| t16 | 最多执行恢复 H20 的首步 | 队列余19必须成立；不追加完整 rollout、baseline、monitor、采集或训练 |

每个分支有自己的真实 episode_id，统一 parent_source_id 只表达开发来源。私有整数 numeric/causal event、私有初始化/graphics UUID 账本分别保存；它们不拼成 public interface_v1 流。公共三文件不改。新增样本不宣称是 A11 共同池。

encoder、投影、Q 的 PCA/normalizer、D/G0 normalization 和选定权重都由新 manifests 绑定。权重 SHA 从已验收元数据继承，本 CPU 任务不读大权重；未来真实入口在任何模型调用前完整验证。实际算法文件（corrector/actions/critic/guidance/radii/raw_commands/solo）保持旧快照字节。
''')
put('audit/CPU_FIX_HISTORY.json',dict(status='resolved_before_CPU_READY',records=[
 dict(stage='snapshot_manifest_assembly',outcome='refused conflicting inherited guard SHA',resolution='explicit accepted installation supersession; no shared file write'),
 dict(stage='integration_fixture_r1',outcome='failed new counter hook: units incorrectly16 instead of incremental1',resolution='private hook changed to1; per-branch cap remains16; r3 passed'),
 dict(stage='integration_fixture_r2',outcome='test harness argparse read real sys.argv instead of stub',resolution='fixture sets/restores sys.argv; no launcher process was started; r3 passed'),
 dict(stage='standalone_publication_entry_r1',outcome='-I removed script directory from sys.path; ModuleNotFoundError core',resolution='private checker explicitly adds own code path; standalone entry then passed')],
 old_artifacts_modified=False,all_fixtures_retained=True,real_compute_retries=0))
put('COMMANDS.md',f'''# 待独立 release 的唯一真实命令（当前禁止执行）

cwd: `{P}`

```sh
bash {P}/commands/run_proposed_causal_c10.sh {B}/releases/P10_A_CAUSAL_C10_PREFLIGHT_V1.json
```

一次命令/一次 claim，两个顺序子进程最多各一次。没有 retry、baseline、环境 restore 或额外 probe。shell 显式 handoff300，冻结 guard SHA7910c567…；同一 inherited formal.lock 从停止全部8holder保持到整组退出，失败清理后恢复。不会在两子进程之间释放并重拿锁。

纯 JSON 发布检查（可运行，不执行真实 launcher）：

```sh
/usr/bin/python3 -I -S -B {P}/code/publication_check.py --control CONTROL_PREVIEW.json --board TASK_BOARD_PREVIEW.json --release RELEASE_PREVIEW.json
```

CONTROL_REQUIRED 只是拟发布字段，不是当前 CONTROL。BOARD 模板 ready，RELEASE 模板 unauthorized_template；分析独立审阅并发布 released 后才能通过真实入口。当前 CPU release 不可能通过。未来任务书还须规定命令前 ACK 与现有 claim 检查；如果真实入口在 claim 前失败，执行端仍保存外层 stdout/stderr/退出码/耗时并交失败回执，不重试。

每子进程 GNU timeout1800s + TERM/KILL grace30s，涵盖该进程的完整SHA、导入/加载、初始化、prefix、D/G0、P/V、C10/H20与进程内清理。最多2×1830=3660s为子进程名义总额。父进程预检/hash、lock等待、handoff300的最后一次既有query、进程组完全退出等待及退出后最多120s恢复观测另计，严格端到端上限为null。成功poll原始记录未持久化的限制保持，计数null，不新增查询补齐。

完整输出：LAUNCH_RESULT、父/各子私有资源账本、初始化与graphics逐项entered/returned、policy UUID原类型/映射/loader、真实prefix/transition/RGB、D预测/残差/G0分量与阈值、噪声/raw50、P/V数值与约束、tail discard/H20余19、分支与全组退出、holder恢复及产物manifest。进程被硬杀可能缺末回执，父重建已进入账本并保留未知/缺项，不填0或退额。
''')
print('Source/asset audit, timing, state gap, commands and CPU fix history written')
