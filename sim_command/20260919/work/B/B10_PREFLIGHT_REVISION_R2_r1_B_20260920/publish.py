"""Freeze and publish R2 CPU proposal, with RESULT last and no compute release."""
import ast
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import preflight as p

W=p.HERE;C=p.CAMPAIGN;TASK='B10_PREFLIGHT_REVISION_R2'
R=C/'results/B'/TASK/W.name

def ref(path):
    path=Path(path);return {'path':str(path),'sha256':p.sha(path),'bytes':path.stat().st_size}

def main():
    final=C/f'receipts/B/{TASK}_RESULT.json';p.require(not final.exists(),'Final R2 exists; use an addendum')
    control=p.read(C/'CONTROL.json');board=p.read(C/'TASK_BOARD.json');ack=p.read(C/f'receipts/B/{TASK}_ACK.json')
    p.require(TASK in control['allowed_task_ids'] and not control['stop_requested'],'CPU task no longer allowed')
    p.require(not control['formal_gpu_runs_enabled'],'Unexpected compute release while publishing CPU preparation')
    checks=p.read(W/'evidence/CPU_CHECK_RESULT.json');p.require(checks['status']=='pass' and not checks['model_runtime_imports'],'CPU validation failed')
    for file in W.glob('*.py'):ast.parse(file.read_text(),filename=str(file))
    for file in (W/'commands').glob('*.sh'):subprocess.run(['bash','-n',str(file)],check=True)
    paths=[W/'config.json',W/'README.md']+list(W.glob('*.py'))+list((W/'commands').glob('*.sh'))+list((W/'local_source_snapshot').glob('*.py'))
    manifest={'schema':'B-LVM-preflight-R2-code/1','root':str(W),'files':[{'path':str(file.relative_to(W)),'sha256':p.sha(file),'bytes':file.stat().st_size} for file in sorted(paths)],'scope':'Runtime source/config/commands plus CPU preparation provenance; release template separately hashed'}
    p.atomic(W/'CODE_SNAPSHOT.json',manifest)
    config=p.read(W/'config.json');rid=config['compute_release_id'];tid=config['compute_task_id'];release_path='releases/'+rid+'.json'
    proposal={'schema_version':1,'campaign_id':config['campaign_id'],'release_id':rid,'kind':'formal_compute','status':'draft','owner':'B','hostname':config['hostname'],'participating_hosts':[config['hostname']],'task_id':tid,'task_revision':1,'job_id':config['job_id'],'config_path':str(W/'config.json'),'config_sha256':p.sha(W/'config.json'),'code_manifest_path':str(W/'CODE_SNAPSHOT.json'),'code_manifest_sha256':p.sha(W/'CODE_SNAPSHOT.json'),'gpu':config['gpu'],'inputs':config['inputs'],'limits':config['limits'],'timeout_seconds':180,'termination_grace_seconds':20,'retry_cap':0,'valid_from_utc':None,'expires_at_utc':None,'wave_id':'corrector-sim-20260919-B-LVM-preflight-R2-independent','run_id':'B10_LVM_PREFLIGHT_V1_r1_B_R2_once','output_dir':str(C/'results/B'/tid/'B10_LVM_PREFLIGHT_V1_r1_B_R2_once'),'note':'Draft CPU proposal only. Analysis alone sets released/time window and active control/task metadata after acceptance. No automatic retries, shared wave or training.'}
    p.atomic(W/'release_template.json',proposal)
    required={'notice':'Required future analysis-owned metadata, not an active CONTROL or release','CONTROL_fields':{'campaign_id':config['campaign_id'],'stop_requested':False,'formal_gpu_runs_enabled':True,'active_compute_release_id':rid,'active_compute_release':release_path,'active_compute_task_ids':[tid],'allowed_task_ids_must_include':tid,'current_compute_limits_minimum':config['limits'],'per_task_compute_limits':{tid:config['limits']},'roles_B_hostname':config['hostname']},'TASK_BOARD_entry':{'id':tid,'owner':'B','revision':1,'status':'ready','release':release_path},'release_fields_to_set_by_analysis':{'status':'released','valid_from_utc':'timezone-aware ISO8601 start','expires_at_utc':'timezone-aware ISO8601 exclusive expiry'},'published_proposal_sha256':p.sha(W/'release_template.json')}
    p.atomic(W/'CONTROL_REQUIRED.json',required)
    # Validate exact future publication metadata in memory, never write CONTROL/releases.
    shadow_control=deepcopy(control);shadow_control.update(campaign_id=config['campaign_id'],stop_requested=False,formal_gpu_runs_enabled=True,active_compute_release_id=rid,active_compute_release=release_path,active_compute_task_ids=[tid],allowed_task_ids=[tid],current_compute_limits=deepcopy(config['limits']),per_task_compute_limits={tid:deepcopy(config['limits'])})
    shadow_board={'campaign_id':config['campaign_id'],'tasks':[required['TASK_BOARD_entry']]};shadow_release=deepcopy(proposal);now=datetime.now(timezone.utc);shadow_release.update(status='released',valid_from_utc=(now-timedelta(minutes=1)).isoformat(),expires_at_utc=(now+timedelta(minutes=10)).isoformat())
    p.metadata(shadow_control,shadow_board,shadow_release,config,host=socket.gethostname(),relative_release=release_path,now=now)
    p.files(W,W/'config.json',shadow_release,config)
    p.gpu_identity(p.read(W/'evidence/GPU_IDENTITY.json')['rows'],config['gpu'])
    p.atomic(W/'evidence/FROZEN_PROPOSAL_CPU_CHECK.json',{'status':'pass','production_validation_functions':['metadata','files','gpu_identity'],'CONTROL_and_release_modified_on_disk':False,'GPU_rows':'saved local read-only nvidia-smi evidence','runtime_GPU_queries':0,'model_imports':False,'claims':0,'note':'Positive metadata/file/identity check uses in-memory future authorization, not execution permission','config_sha256':p.sha(W/'config.json'),'code_sha256':p.sha(W/'CODE_SNAPSHOT.json'),'template_sha256':p.sha(W/'release_template.json')})
    storage=p.read(C/'receipts/B/STORAGE_DEPENDENCY_REVIEW_V1.json');process=p.read(W/'evidence/STORAGE_LOCAL_PROCESS_CHECK.json')
    report=f'''# B10_PREFLIGHT_REVISION_R2：CPU 修订完成

| 项目 | 修订结果 |
|---|---|
| GPU身份 | 本机8×H100；选择UUID `{config['gpu']['uuid']}`；driver `{config['gpu']['driver_version']}`、型号、PCI逐项核对 |
| 可见设备 | 导入torch前设完整UUID为CUDA_VISIBLE_DEVICES，逻辑cuda:0仅指该卡；主机序号变化不导致换卡 |
| 授权 | unique active release id/path/task、released状态、有效期/关闭历史、board owner/revision/ready或running、host、单机wave全部一致 |
| 预算/文件 | release caps=配置；CONTROL全局+单任务caps覆盖；code/config/input/lifecycle SHA核验；每次实际调用前重查元数据 |
| 有限预检 | 1初始化、2 GPU forward、仿真/VLA/更新0、180+20秒、重试0；synthetic token不代表真实特征或任务效果 |
| CPU验证 | {checks['tests_run']}项测试通过，{len(checks['rejection_subcases'])}条登记拒绝子例；正确冻结提案的元数据/文件/保存GPU身份组合检查通过；无torch/numpy导入 |
| 存储附项 | 27文件/11父路径，18013109184逻辑bytes；元数据27/27吻合；本机{process['visible_processes_inspected']}进程无fd/maps/下载恢复命中，权限缺口{len(process['permission_gaps'])} |

本轮仅CPU代码/配置修订、文件核验和明确授权的只读GPU身份查询。模型初始化/推理、仿真、训练、正式GPU秒、删除均0。沙箱首次nvidia-smi驱动查询失败；只读升级查询成功，未据沙箱失败推断主机驱动不可用。

代码/config/命令在 `{W}`，不可变镜像在 `{R}`。原B10 r1快照及回执不变。

- 无模型校验：`bash {W}/commands/verify_release.sh <分析端绝对release路径>`。
- 后续正式命令：`bash {W}/commands/run_preflight.sh <分析端绝对release路径>`；旧P00已确认拒绝，不写claim、不加载模型。
- config SHA：`{p.sha(W/'config.json')}`；code manifest SHA：`{p.sha(W/'CODE_SNAPSHOT.json')}`。
- `release_template.json` SHA：`{p.sha(W/'release_template.json')}`，status=draft、时间null；`CONTROL_REQUIRED.json`明确未来B独立预检的task/board/active字段和caps。当前未发布计算release。
- Python使用既有`.miniforge3/envs/lerobot/bin/python`；授权/身份路径只有标准库。模型/source/输入沿用锁定旧LVM；未改共享环境。

完整命令仍经本机occupancy lifecycle暂停全部8卡holder并在退出含失败后恢复。当前先A后B的独立wave，不新增联合屏障。标明的200秒GPU作业上界含kill grace，交接/恢复耗时另记；完整命令两次nvidia-smi校验不当作CUDA模型调用。

存储回执 `receipts/B/STORAGE_DEPENDENCY_REVIEW_V1.json` 已发布：B当前/计划任务不依赖27个候选；若需求变化，先向分析端报告再读取。对照A冻结SHA来源，只复核精确路径/类型/大小/mtime，未重复哈希18GB，未把跨主机inode/device当一致性要求。仅本机时点证据；分析端决定，A删除前复核并执行，B未删除。Smol050000、X完整底座/初始化及全部小元数据/沿革继续保留。

建议分析端验收本包后按CONTROL_REQUIRED发布B单机两forward预检。当前CONTROL revision{control['revision']}，正式模型/仿真/训练上限仍0；准备完成不代表GPU预检通过。
'''
    (W/'REPORT.md').write_text(report)
    for name in ['CONTROL.json','TASK_BOARD.json']:shutil.copy2(C/name,W/'evidence'/('FINAL_'+name))
    # Small provenance only; inputs are references, never copied model payloads.
    for file in sorted(W.rglob('*')):
        rel=file.relative_to(W)
        if not file.is_file() or '__pycache__' in rel.parts:continue
        if file.name in ('ARTIFACT_MANIFEST.json','RESULT.json'):continue
        target=R/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
    items=[{'path':str(file.relative_to(R)),'sha256':p.sha(file),'bytes':file.stat().st_size} for file in sorted(R.rglob('*')) if file.is_file()]
    p.atomic(R/'ARTIFACT_MANIFEST.json',{'root':str(R),'files':items})
    for entry in items:p.require(p.sha(R/entry['path'])==entry['sha256'],'Publication checksum mismatch')
    counts={'model_initializations':0,'model_gpu_inference_calls':0,'simulator_attempts':0,'completed_rollouts':0,'vla_sampling_calls':0,'optimizer_updates':0,'gpu_seconds':0,'deletions':0}
    result={'campaign_id':config['campaign_id'],'task_id':TASK,'revision':1,'role':'B','hostname':socket.gethostname(),'session_id':ack['executor_session_id'],'run_id':W.name,'status':'complete','completion_scope':'CPU preflight authorization/GPU-identity correction and targeted local storage review; no formal compute executed','started_at_utc':ack['started_at_utc'],'finished_at_utc':datetime.now(timezone.utc).isoformat(),'input_identity':{'protocol':ack['inputs_checked'],'code':[ref(W/'local_source_snapshot/siglip_dynamics_mlp.py')]+config['lifecycle_dependencies'],'config':[ref(W/'inputs/previous_lvm_config.json')],'data':{'path':None,'sha256':None,'reason':'No real dataset or simulator needed for two synthetic-token forwards; future probe only'},'model':list(config['inputs'].values()),'hardware':ref(W/'evidence/GPU_IDENTITY.json')},'artifacts':[ref(R/'REPORT.md'),ref(R/'ARTIFACT_MANIFEST.json'),ref(R/'CODE_SNAPSHOT.json'),ref(R/'config.json'),ref(R/'release_template.json'),ref(R/'CONTROL_REQUIRED.json'),ref(R/'evidence/CPU_CHECK_RESULT.json'),ref(R/'evidence/FROZEN_PROPOSAL_CPU_CHECK.json'),ref(C/'receipts/B/STORAGE_DEPENDENCY_REVIEW_V1.json')],'resource_counts':counts,'read_only_GPU_identity_query_note':'Explicitly allowed nvidia-smi identity inspection, no CUDA runtime initialization. Initial sandbox failure followed by successful escalated read-only queries. Occupancy remains outside formal cost.','failures_and_retries':[{'command':'nvidia-smi --query-gpu=index,uuid,name,driver_version,pci.bus_id --format=csv,noheader in sandbox','exit_code':None,'exit_code_note':'Initial batched shell later ran other read-only commands; individual failing nvidia-smi status was not retained','failure':'Sandbox could not communicate with NVIDIA driver','recovery':'Same read-only identity query with escalation succeeded; actual driver535.161.08 and8 UUIDs verified','formal_compute_retries':0}],'findings':['GPU full UUID binding and host/model/driver/PCI verification precede all model imports.','Unique current CONTROL release/path/task, release status/expiry, task board identity and both global/task caps are checked; stale/foreign/draft release cannot borrow global enable.','Code/config/input/lifecycle SHA and original1-init/2-forward/180+20s/zero-retry budget preserved.','9 targeted stdlib CPU tests passed with36 recorded rejection subcases; positive frozen proposal validation passed without CUDA or claims.','All27 storage payload metadata match A identity; no B input/recovery dependency or local visible users found;50 process namespace observations,0 permission gaps.','B commits not to read candidate payloads for current/planned tasks without first reporting changed need; analysis/A retain deletion control.','Old B10 evidence and shared assets/environments remain unchanged; no GPU/model/simulation/training/deletion performed.'],'blockers':[{'scope':'actual B GPU preflight','missing':'Analysis acceptance and separately published active B-only released compute document with time window and matching caps','resolution':'Use this frozen release_template and CONTROL_REQUIRED; current CPU release is insufficient'}],'next_task_proposal':'Analysis accept R2 and storage clearance, then release B10_LVM_PREFLIGHT_V1/P10_B_LVM_PREFLIGHT_V1 as independent B-only finite wave; do not execute draft or historical task.'}
    p.atomic(R/'RESULT.json',result)
    report_receipt=C/f'receipts/B/{TASK}_REPORT.md';tmp=report_receipt.with_suffix('.tmp');tmp.write_text(report);os.replace(tmp,report_receipt)
    heartbeat=p.read(C/f'receipts/B/{TASK}_HEARTBEAT.json');heartbeat.update(status='complete',updated_at_utc=result['finished_at_utc'],progress='R2 immutable proposal and storage clearance published; awaiting analysis acceptance and separate compute release');p.atomic(C/f'receipts/B/{TASK}_HEARTBEAT.json',heartbeat)
    p.atomic(C/'nodes/B/dispatch_status.json',{'task_id':TASK,'status':'complete_waiting_for_next_release','updated_at_utc':result['finished_at_utc'],'control_revision':control['revision'],'task_board_revision':board['revision'],'result_path':str(final),'formal_compute_started':False})
    p.atomic(final,result)
    print(json.dumps({'result':str(final),'artifact_files':len(items),'code_sha256':p.sha(W/'CODE_SNAPSHOT.json'),'config_sha256':p.sha(W/'config.json'),'template_sha256':p.sha(W/'release_template.json')}))

if __name__=='__main__':main()
