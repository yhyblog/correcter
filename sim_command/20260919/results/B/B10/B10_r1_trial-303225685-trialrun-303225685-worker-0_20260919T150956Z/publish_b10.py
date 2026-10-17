"""Publish immutable B10 CPU artifacts; RESULT is the final publication operation."""
import ast
import json
import os
from pathlib import Path
import shutil
import socket
from datetime import datetime,timezone
from prepare_delivery import W,C,R,sha,dump,ref

def main():
    result_path=C/'receipts/B/B10_RESULT.json'
    if result_path.exists():raise RuntimeError('Final result exists: use an addendum, do not overwrite')
    control=json.loads((C/'CONTROL.json').read_text());board=json.loads((C/'TASK_BOARD.json').read_text())
    assert not control['stop_requested'] and 'B10' in control['allowed_task_ids']
    assert not control['formal_gpu_runs_enabled']
    checks=json.loads((W/'evidence/CPU_CHECK_RESULT.json').read_text());assert checks['status']=='pass' and checks['tests_run']==27 and not checks['torch_cuda_initialized']
    for p in W.rglob('*.py'):
        if '.git' not in p.parts and '__pycache__' not in p.parts:ast.parse(p.read_text(),filename=str(p))
    # Input snapshots and live handoff evidence are separate from runtime code identity.
    for name in ['CONTROL.json','TASK_BOARD.json']:
        shutil.copy2(C/name,W/'evidence'/('FINAL_'+name))
    shutil.copy2(C/'receipts/B/A10_INTERFACE_FEEDBACK.md',W/'evidence/A10_INTERFACE_FEEDBACK_FINAL.md')
    files=[]
    for p in sorted(W.rglob('*')):
        rel=p.relative_to(W)
        if not p.is_file() or any(part in ('.git','__pycache__') for part in rel.parts):continue
        if rel.parts[0] in ('evidence','inputs') or p.name in ('CODE_SNAPSHOT.json','REPORT.md','RESULT.json','ARTIFACT_MANIFEST.json'):continue
        files.append({'path':str(rel),'sha256':sha(p),'bytes':p.stat().st_size})
    code={'schema':'B10-code-snapshot/1','work_dir':str(W),'files':files,'readonly_after_publication':True,'public_upstream_commit':'ee67a70e576dc7f02a00cff86c9dd97f868c896f','public_interface_schema_sha256':'7d52f22e9d2e622a18a9a71fdac822ed50413aa3838aa3ad40d98e0bee10500f'}
    dump(W/'CODE_SNAPSHOT.json',code)
    report=f'''# B10：CPU 接口准备完成，正式计算未执行

| 内容 | 已完成 | 后续缺口 |
|---|---|---|
| A 公共接口 v1 | 三文件SHA一致；七类A样例、23条B样例通过；事件与双账本兼容 | 实际VLA/仿真driver尚未作为不可变入口发布 |
| VLA-Corrector | h1/k10、原cosine(delta_z)视图及原生频率适配清单；旧模型只读；有限GPU预检命令 | 新公共正常示范token view、训练recipe/预算与开发阈值待冻结 |
| E3 GAF-v1 adapted | 公开commit固定；discounted success-to-go/MSE；每次采样引导；CPU梯度与上游一致 | 共同真实逐步manifest、规范化state/语言特征绑定；未训练critic |
| E6 D5→R | 同D两成员因果五步误差、动作/reset对齐、同合法窗口/最多一次、开发干预率匹配 | 开发预测/实际feature traces与阈值为null；未新采集 |
| E1 | 4损失×3完整训练seed×4成员=48份同初始化/容量/更新范围配置 | 4000更新/成员为提案，需单独release；两个算子共用fit |
| E8 | Smol50k、X初始化、LIBERO自身29999资产与维度路径沿用B00 | X缺已训练MT50权重；各底座D/G0/Q适配另计 |
| 存储 | 两个精确X下载临时候选，共3519073692逻辑bytes | 依赖/对端使用尚未排除，建议defer；B未删除共享历史 |

本轮27项CPU测试通过，torch.cuda.is_initialized=false；训练更新、模型GPU推理、VLA采样、simulator attempts、rollout和正式GPU秒均为0。合成CPU autograd触发一次设备枚举警告，未建立CUDA运行时。最后本机guard PID35861运行，8卡均holder，约49–50%利用率；该占卡不列入实验GPU成本。

## 方法与数据口径

GAF论文固定 [arXiv2607.02092v1](https://arxiv.org/abs/2607.02092v1)，[公开代码commit](https://github.com/ylhaichen/guided-action-flow/tree/ee67a70e576dc7f02a00cff86c9dd97f868c896f) 单独锁定，不声称官方关联。参数3成员/768×4/beta2/clip1/gate10/min0.1；π0.5、MW四维state/action及实际10步窗口明确标adapted。每个实际10-flow完整采样至多30 critic forward、10 action backward、0 VLA backward；不接G0一次门控。

成功时间采用动作后的状态step+1；GAF与上游action-index约定一致，target=gamma**(first_success_state-start_step-1)，gamma=.99/真实控制步；成功后1、完整失败0、未知结局不标失败。parent分组，branch/suffix不拼接；生成50不冒充执行50。历史raw有reward/success而bank没有，两者已区分；缺失图像/next/terminated-truncated不虚构。

E6误差为两成员×5个已到达观测×4096维的delta_scale标准化均方误差；预测必须早5步保存、动作逐项相符且物理分支一致。缺失不报警并记录覆盖率。开发阈值选最接近G0的episode干预数，平局偏少；匹配精度受1/Ndev和并列分数限制，不按测试结果追平。

E1保留旧600真实源、7058参数、同成员初始SHA、冻结PCA、只更新residual/advantage、相同bootstrap与4000步预算提案；L_ab=BCE+a·gain+0.5b·pair。旧初始化完整训练沿革单列，未声称共同新增数据等于全部历史数据相同。

## 命令与有限报价

工作目录：`{W}`。依赖：既有lerobot Python3.12/torch2.7.1及numpy/jsonschema，精确版本见DEPENDENCIES.json。代码清单SHA=`{sha(W/'CODE_SNAPSHOT.json')}`。

| 命令/配置 | 未放行的数量提案 | 边界 |
|---|---|---|
| commands/preview_lvm.sh | CPU输入SHA检查，已运行；9个唯一输入文件SHA核验 | 不调用模型 |
| commands/run_formal_job.sh + configs/lvm_gpu_probe_2.json | 初始化1、GPU forward2、仿真/VLA/更新0；VRAM估计2GiB，输出0.1GiB | timeout180s+kill grace20s；重试0；无真实特征/渲染结论 |
| 同wrapper + configs/e1_*.json | 48 CPU fits，合计192000更新，初始化48；RAM估计3GiB，输出0.2GiB | 每成员1800s+20s；只保留final+lineage；未执行 |
| 同wrapper + configs/gaf_v1_member_*.json | 3 GPU fits，合计30000更新/训练前向；开发前向至多1200，初始化3；VRAM估计4GiB | 每成员3600s+20s，dev最多10240条，超出拒绝；共同view为null |
| commands/EVALUATION_REQUEST.json | E3/E6/E8实际闭环次数尚未放行，driver=null | 先绑定A不可变driver；不是假装可运行的eval命令 |

以上容量是工程估计/超时上界，不是实测速度。新token提取帧数、E8次数和X-VLA最低充分训练步数未知，明确null；旧X-VLA有限recipe为30k/8GPU/effective batch64，仅供后续单独决策，不重启历史队列。

wrapper只接受独立本机wave，先验release/任务/host/code/config/input SHA，claim防重复，逐批检查stop/额度，完整命令都经occupancy lifecycle，8卡holder全部暂停至退出含失败。联合A/B wave被拒绝，须先冻结共享完成/失败屏障；不在单卡提前完成时恢复holder。自动重试0；失败claim保留供分析恢复决定。

接口本身无阻塞。真实接入前必须附加entered-before-call durable journal；部分失败和缺末事件仍计已进入资源，entered/returned/failed保留同操作元数据且仅计一次。E3多次决策读完整事件流，episode单值只是摘要；N不分摊shadow监测或a0，嵌套墙钟不相加。

## 交接证据与请求

产物目录：`{R}`，包含代码镜像、configs/commands、输入与SHA、CPU检查、结构化样例和资源报价。接口反馈：`receipts/B/A10_INTERFACE_FEEDBACK.md`；存储候选：`receipts/B/STORAGE_CANDIDATES.json`。B00盘点已被分析端验收，本轮不重跑历史实验。

请分析端按P10先决定2次LVM预检及A/B真实driver集成的有限独立wave；冻结公共数据/特征与D开发记录后再发布训练。X-VLA新训练、联合wave屏障及正式P20评测分别决定。当前CONTROL revision{control['revision']}、TASK_BOARD revision{board['revision']}，没有后续已放行B计算任务。
'''
    (W/'REPORT.md').write_text(report)
    R.mkdir(parents=True,exist_ok=True)
    # Copy everything reviewable except VCS/cache metadata. Existing run dir was only reserved.
    if (R/'ARTIFACT_MANIFEST.json').exists():raise RuntimeError('Run artifacts already finalized')
    for p in sorted(W.rglob('*')):
        rel=p.relative_to(W)
        if not p.is_file() or any(part in ('.git','__pycache__') for part in rel.parts):continue
        if p.name in ('RESULT.json','ARTIFACT_MANIFEST.json'):continue
        dest=R/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    artifacts=[{'path':str(p.relative_to(R)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(R.rglob('*')) if p.is_file()]
    dump(R/'ARTIFACT_MANIFEST.json',{'root':str(R),'files':artifacts})
    for item in artifacts:assert sha(R/item['path'])==item['sha256']
    ack=json.loads((C/'receipts/B/B10_ACK.json').read_text())
    result={'campaign_id':'corrector-sim-20260919','task_id':'B10','revision':1,'role':'B','hostname':socket.gethostname(),'session_id':ack['executor_session_id'],'run_id':W.name,'status':'complete','completion_scope':'Authorized P00 CPU preparation only; real integration/training/evaluation not passed or released','started_at_utc':ack['started_at_utc'],'finished_at_utc':datetime.now(timezone.utc).isoformat(),'input_identity':{'protocol':ack['inputs_checked']+[ref(C/'contracts/INVENTORY_DECISIONS_V1.md'),ref(C/'contracts/INTERFACE_V1_INTEGRATION_NOTES.md'),ref(C/'manifests/PUBLIC_INTERFACE_V1.json')],'code':[ref(W/'CODE_SNAPSHOT.json'),ref(W/'upstream_lock.json'),ref(W/'SOURCE_REFERENCES.json')],'config':[ref(W/'configs/JOB_INDEX.json'),ref(W/'configs/METHODS.json')],'data':[ref(C/'receipts/B/B00_ASSETS.json'),ref(W/'evidence/CONFIG_INPUT_CHECK.json'),{'path':None,'sha256':None,'reason':'Common actual parent-split trajectory/feature manifest not published; synthetic examples not data'}],'model':[ref(W/'configs/lvm_gpu_probe_2.json'),ref(W/'configs/E1_MATRIX.json'),{'path':str(C/'receipts/B/B00_RESULT.json'),'sha256':sha(C/'receipts/B/B00_RESULT.json'),'reason':'Inherited full inventory; large VLA payload hashes were not all rehashed, as disclosed in B00'}],'control_revision_at_finish':control['revision'],'task_board_revision_at_finish':board['revision']},'artifacts':[ref(R/'REPORT.md'),ref(R/'ARTIFACT_MANIFEST.json'),ref(R/'CODE_SNAPSHOT.json'),ref(R/'evidence/CPU_CHECK_RESULT.json'),ref(R/'configs/RESOURCE_QUOTE.json'),ref(C/'receipts/B/A10_INTERFACE_FEEDBACK.md'),ref(C/'receipts/B/STORAGE_CANDIDATES.json')],'resource_counts':checks['resource_counts'],'failures_and_retries':[{'command':'git clone --depth 1 https://github.com/ylhaichen/guided-action-flow <B-owned upstream directory>','exit_code':128,'reason':'Sandbox proxy/DNS resolution unavailable','recovery':'Explicit sandbox network escalation succeeded; pinned commit and tracked file hashes recorded','formal_resource_use':0},{'command':'validate_delivery.py initial evidence export','exit_code':1,'reason':'view_manifest has no generic identity key','recovery':'Exporter corrected against actual immutable schema; final27 CPU tests and23 B records pass','formal_resource_use':0},{'command':'inline configuration audit importing future_jobs from workspace root','exit_code':1,'reason':'Python module search path omitted work/B run','recovery':'Explicit work path;52 configs and9 unique input SHA checked','formal_resource_use':0},{'command':'read-only discovery of TASK_BOARD.md / ASSETS.json / contracts.py; rg in alternate working directory','exit_code':'1/2/127 according to missing path/tool','reason':'Guessed filenames or cwd-specific PATH','recovery':'Read actual TASK_BOARD.json, B00_ASSETS.json and Python directory/file checks; no inputs mutated','formal_resource_use':0}],'findings':['B00 remains accepted; B10 authorized CPU preparation complete, all formal resources zero.','27 CPU tests,7 A examples and23 B examples pass; CUDA runtime uninitialized.','GAF-v1 adapted uniquely selected and versioned; every-sample native guidance retained; no official-repository claim.','E6 uses same D causal5-step prediction error with R/one intervention and development-rate matching; threshold remains null.','E1 four losses/three complete seeds/four members prepared with shared initialization and exact original loss arithmetic;48 fit configs, no training.','VLA-Corrector common normal-demo cosine view prepared; token extraction and real-data recipe not fabricated.','Smol50k and own LIBERO29999 retained; X-VLA trained MT50 checkpoint missing.','One finite LVM GPU command ready for later release; GAF training blocked on common views; real evaluation driver not yet published.','Two exact partial-download storage candidates total3519073692 bytes deferred to analysis/A; nothing deleted.','8 local GPU holders healthy at final check; no next B compute release currently active.'],'blockers':[{'scope':'future GAF/LVM training','missing':'Frozen common real parent-split manifest, complete per-step observations/actions/outcomes and feature/normalizer bindings','resolution':'A index existing true data, preserve missing fields; freeze new common collection/extraction only under separately priced release'},{'scope':'future E6 calibration','missing':'Aligned D predictions/actual features and frozen development identity/threshold','resolution':'Use existing valid development records first; no unbudgeted sweep'},{'scope':'future real preflight/evaluation','missing':'Immutable A runtime entrypoint and explicit finite release; joint-wave barrier if two-host wave','resolution':'Bind B adapters+durable events to A driver before P10 real integration; wrapper rejects joint wave'},{'scope':'E8 X-VLA','missing':'Trained MT50 weights','resolution':'Analysis choose verified external asset or independently released finite new SFT; retain base/init'}],'next_task_proposal':'Analysis P10: inspect two-forward LVM single-host preflight, bind real A driver/common data and define further finite tasks; no executor self-release.'}
    # Publish report/status first; RESULT is last and never overwritten.
    dump(R/'RESULT.json',result)
    report_receipt=C/'receipts/B/B10_REPORT.md';temp=report_receipt.with_suffix('.tmp');temp.write_text(report);os.replace(temp,report_receipt)
    heartbeat=json.loads((C/'receipts/B/B10_HEARTBEAT.json').read_text());heartbeat.update(status='complete',updated_at_utc=result['finished_at_utc'],progress='B10 CPU artifacts published; waiting for analysis acceptance/P10; formal counts remain zero');dump(C/'receipts/B/B10_HEARTBEAT.json',heartbeat)
    dump(C/'nodes/B/dispatch_status.json',{'task_id':'B10','status':'complete_waiting_for_next_release','control_revision':control['revision'],'task_board_revision':board['revision'],'updated_at_utc':result['finished_at_utc'],'result_path':str(result_path),'formal_compute_started':False})
    dump(result_path,result)
    print(json.dumps({'result':str(result_path),'artifact_files':len(artifacts),'tests':checks['tests_run'],'code_sha256':sha(W/'CODE_SNAPSHOT.json')},ensure_ascii=False))

if __name__=='__main__':main()
