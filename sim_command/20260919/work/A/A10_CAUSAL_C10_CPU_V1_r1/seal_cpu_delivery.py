from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');P=B/'results/A/A10_CAUSAL_C10_CPU_V1';W=B/'work/A/A10_CAUSAL_C10_CPU_V1_r1'
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p),realpath=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size_bytes=p.stat().st_size)
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def new(p,x):
 with p.open('x') as f:f.write(x if isinstance(x,str) else json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
# Seal final private edits; original accepted snapshots have never been changed.
for name in ['INTEGRATION_MANIFEST.json','code/CODE_MANIFEST.json']:
 f=P/name;d=read(f)
 if name=='INTEGRATION_MANIFEST.json':
  for row in d['files']:row['new']=ref(Path(row['new']['path']))
 else:
  for row in d['files']:
   q=P/'code'/row['path'];row.update(sha256=ref(q)['sha256'],size_bytes=q.stat().st_size)
 write(f,d)
f=P/'proposal/PROPOSAL.json';proposal=read(f)
for k,name in [('code_manifest','code/CODE_MANIFEST.json'),('integration_manifest','INTEGRATION_MANIFEST.json')]:proposal[k]=ref(P/name)
write(f,proposal)
f=P/'proposal/RELEASE_TEMPLATE.json';release=read(f);release.update(proposal_sha256=ref(P/'proposal/PROPOSAL.json')['sha256'],code_manifest_sha256=proposal['code_manifest']['sha256']);write(f,release)
fixture=W/'sealed_publication_fixture';fixture.mkdir(exist_ok=False)
for name in ['CONTROL.json','TASK_BOARD.json']:(fixture/name).write_bytes((W/'final_publication_fixture'/name).read_bytes())
release['status']='released';write(fixture/'RELEASE.json',release)
cmd=['/usr/bin/python3','-I','-S','-B',str(P/'code/publication_check.py'),'--control',str(fixture/'CONTROL.json'),'--board',str(fixture/'TASK_BOARD.json'),'--release',str(fixture/'RELEASE.json')]
x=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
new(W/'SEALED_PUBLICATION_CHECK.json',dict(status='PASS' if x.returncode==0 else 'FAIL',command=cmd,returncode=x.returncode,stdout=x.stdout,stderr=x.stderr))
assert x.returncode==0
checks=[W/'integration_fixture_r3/RESULT.json',W/'publication_fixture_r1/RESULT.json',W/'FINAL_STATIC_COMMANDS.json',W/'FINAL_TARGETED_SOURCE_CHECK.json',W/'SEALED_PUBLICATION_CHECK.json']
for f in checks:assert read(f)['status']=='PASS'
# Current authorization is still CPU only. These are metadata reads only.
c=read(B/'CONTROL.json');board=read(B/'TASK_BOARD.json')
assert c['revision']==32 and board['revision']==39 and c['mode']=='prepare' and c['active_compute_release_id'] is None and not c['formal_gpu_runs_enabled']
assert all(v==0 for v in c['current_compute_limits'].values())
assert ref(B/'releases/P00_CAUSAL_C10_CPU_V1.json')['sha256']=='a5597bbc90461f9918b02425f62a4e44fdbc9a04d3906dcffd43faec5ca3b74d'
for k in ['config','input_manifest','external_sources','code_manifest','integration_manifest','budget','command']:
 assert ref(Path(proposal[k]['path']))['sha256']==proposal[k]['sha256']
for row in read(P/'code/CODE_MANIFEST.json')['files']:assert ref(P/'code'/row['path'])['sha256']==row['sha256']
now=datetime.now(timezone.utc).isoformat();caps=proposal['resource_caps']
ready=dict(status='CPU_READY',task_id='A10_CAUSAL_C10_CPU_V1',revision=1,at_utc=now,compute_authorized=False,
    CPU_release=ref(B/'releases/P00_CAUSAL_C10_CPU_V1.json'),ACK=ref(B/'receipts/A/A10_CAUSAL_C10_CPU_V1_ACK.json'),
    proposal=ref(P/'proposal/PROPOSAL.json'),code_manifest=proposal['code_manifest'],integration_manifest=proposal['integration_manifest'],
    input_manifest=proposal['input_manifest'],external_manifest=proposal['external_sources'],checks=[ref(f) for f in checks],
    validated='new CPU temporal/queue/accounting/auth/exit fixtures and changed AST/shell only; 16 integration checks and 19 authorization cases',
    unvalidated=proposal['unvalidated'],full_state_restore_available=False,alternative='two fresh sequential independent seeded prefixes, conditional on analysis independent release',
    future_task_id=proposal['task_id'],future_release_id=proposal['authorization_identity']['release_id'],future_caps=proposal['resource_caps'],
    this_task_actual_compute=dict(torch_imports=0,driver_dlopen=0,NVML_calls=0,CUDA_calls=0,EGL_calls=0,model_calls=0,gradients=0,
        environments=0,resets=0,render=0,physics=0,holder_queries=0,holder_stops=0,real_launchers=0,claims=0,installations=0,restarts=0,training=0,deletions=0,large_weight_hashes=0),
    limits='CPU_READY does not certify native runtime, D/G0 numerical success, triggered method, matched hidden state, deployment cost or task success rate')
new(P/'CPU_READY.json',ready)
report=f'''# A10_CAUSAL_C10_CPU_V1 — CPU_READY

ACK 已写；当前仍为 CONTROL32 / TASK_BOARD39、prepare、全部计算0。已交独立私有包及未授权 `A10_CAUSAL_C10_PREFLIGHT_V1` 提案，未创建真实 release/claim。

已实现固定 shelf-place、H20/cut5 的因果队列控制器：t0 的 D 预测在动作前保存，cut5 只使用已到达帧/实际动作；真实 G0 阈值0.05与预定强制工程干预分别标记。既有 G0 消费当前 context、已知下一5命令及 D 预测；成熟残差独立保存，不擅自增加为 G0 输入，目标仍 execute5_then_fixed10。P/V独立自身半径、raw尾部位约束及无Q接受门保持。

现有 restore 仅 reset+回放或 qpos/qvel，并无完整隐藏状态恢复证明。因此报价**同一占卡wave内两个顺序新子进程、各自固定seed重建prefix**；V cut5 的观测/动作/上下文对不上即停止，即使相同也不宣称隐藏状态等价。每路径至多 prefix5+C10十步+恢复H20首步，余量19；首次成功/原生终止先停，不换seed、不补基线。是否采用该替代由分析新release决定。

| 完整两路径上限 | 数量 |
|---|---:|
| 命令 / claim / 独立分支attempt | 1 / 1 / 2 |
| wrapper / native环境 / taskset | 2 / 4 / 2 |
| native reset / reset_model / 初始化子步 | 104 / 208 / 52,000 |
| 真实控制步 / 控制子步 / RGB | 32 / 426 / 34 |
| native mj_forward / 显式graphics事件 | 452 / 306 |
| 完整VLA采样 / flow | 7 / 70 |
| encoder / D / G0 | 42 / 8 / 4 |
| Q ensemble / 成员前向 / 动作梯度 | 11 / 44 / 4 |

完整111项caps、别名与每分支账本见 `proposal/RESOURCE_BUDGET.json`；Post部署1次、Velocity部署2次口径保留，另计prefix与H20恢复，无共享a0节省。每子进程1800+30s，handoff名义300s另计；同formal.lock持续到完整进程组退出，失败也清理后恢复全部8holder。既有成功poll原始记录缺失仍报null。RAM约32GiB（建议预留64）、VRAM约16GiB（预留24）、新证据≤256MiB均为估计，未实测。

定向CPU检查通过：16项因果/队列/计量/退出fixture、19项授权状态fixture、改变文件AST、sh语法及最终纯JSON入口。六份corrector数值文件逐字节继承、UUID parser AST不变；393代码文件manifest。准备期修复了新计数hook增量和测试入口问题，旧证据未动，早期CPU fixture保留在work，详见 `audit/CPU_FIX_HISTORY.json`。

本包把原生EGL/严格loader/旧P/V与D/G0接成了新的整体，**尚未实测整体**。不声称触发有效性、MT50训练、任务成功率或排名。当前Torch/dlopen/NVML/GPU/环境/holder操作/真实launcher/claim/安装/训练/删除/大权重重hash全部0；公共interface_v1及旧八release不变。完成后仅等待分析审阅与独立计算release。

主要交付：`CPU_READY.json`、`CAUSAL_TIMELINE.md`、`STATE_RESTORE_REVIEW.md`、`COMMANDS.md`、`proposal/PROPOSAL.json`、`audit/TARGETED_SOURCE_REVIEW.json`。
'''
new(P/'REPORT.md',report)
# Package manifest covers all files incl docs/checkers; code itself separately
# sealed. Work evidence also includes retained failures; no temporary deletion.
package_files=[ref(f) for f in sorted(P.rglob('*')) if f.is_file() and f.name!='ARTIFACT_MANIFEST.json']
work_files=[ref(f) for f in sorted(W.rglob('*')) if f.is_file() and f.name not in ['QUEUE_MESSAGE.txt','QUEUE_DELIVERY.json']]
new(P/'ARTIFACT_MANIFEST.json',dict(schema='CPU_preparation_artifact_manifest_v1',task_id='A10_CAUSAL_C10_CPU_V1',at_utc=now,
    files=package_files,work_evidence=work_files,inherited_external_and_weight_bytes_not_rehashed=True,
    excluded_self=str(P/'ARTIFACT_MANIFEST.json'),later_excluded=['receipt RESULT references this manifest','queue delivery receipt created after handoff']))
outputs=['CPU_READY.json','REPORT.md','ARTIFACT_MANIFEST.json','CAUSAL_TIMELINE.md','STATE_RESTORE_REVIEW.md','COMMANDS.md',
    'code/CODE_MANIFEST.json','INTEGRATION_MANIFEST.json','INPUT_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json','config/CONFIG.json',
    'proposal/PROPOSAL.json','proposal/RESOURCE_BUDGET.json','proposal/IDENTITY.json','proposal/RELEASE_TEMPLATE.json','proposal/BOARD_TASK_TEMPLATE.json','proposal/CONTROL_REQUIRED.json',
    'commands/run_proposed_causal_c10.sh','code/publication_check.py','audit/DG0_ASSET_BINDING.json','audit/TARGETED_SOURCE_REVIEW.json','audit/CPU_FIX_HISTORY.json']
result=dict(campaign_id='corrector-sim-20260919',task_id='A10_CAUSAL_C10_CPU_V1',revision=1,owner='A',status='CPU_READY',hostname='trial-303224955-trialrun-303224955-worker-0',
    session_id='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',at_utc=now,ACK=ref(B/'receipts/A/A10_CAUSAL_C10_CPU_V1_ACK.json'),
    release=ref(B/'releases/P00_CAUSAL_C10_CPU_V1.json'),CONTROL=ref(B/'CONTROL.json'),TASK_BOARD=ref(B/'TASK_BOARD.json'),
    summary='H20/cut5 causal DG0 + independent P/V C10 suffix then H20 queue restore prepared; CPU-only fixtures PASS; new compute not authorized',
    artifacts=[ref(P/f) for f in outputs]+[ref(f) for f in checks],actual_compute=ready['this_task_actual_compute'],
    proposed_compute=proposal['resource_caps'],future_proposal=ref(P/'proposal/PROPOSAL.json'),
    method_decision_for_analysis='approve/reject two-fresh-prefix finite alternative; full hidden-state restoration unavailable',
    limitations=ready['limits'],unvalidated=proposal['unvalidated'],old_releases_reused=False,public_interface_modified=False,
    automatic_next_stage=False,wait_for='analysis review then separate single compute release',B_participates=False)
receipt=B/'receipts/A/A10_CAUSAL_C10_CPU_V1_RESULT.json';new(receipt,result)
print(json.dumps(dict(status='CPU_READY',RESULT=ref(receipt),REPORT=ref(P/'REPORT.md'),CPU_READY=ref(P/'CPU_READY.json'),PROPOSAL=ref(P/'proposal/PROPOSAL.json'),
    package_evidence_files=len(package_files),work_evidence_files=len(work_files),artifact_refs=len(result['artifacts'])),indent=2,ensure_ascii=False))
