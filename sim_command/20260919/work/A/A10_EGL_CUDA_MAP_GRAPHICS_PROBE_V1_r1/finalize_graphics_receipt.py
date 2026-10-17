"""Read-only CPU reconciliation of the completed single graphics command."""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path

WORK=Path(__file__).resolve().parent
BASE=WORK.parents[2]
TASK='A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1'
RUN=BASE/'results/A/EGL_graphics_runs'/f'{TASK}_r1_A_wave03'
PUB=BASE/'results/A/A10_EGL_CUDA_MAP_CPU_V1'
R=BASE/'receipts/A'
CLAIM=RUN.parent/'release_claims/P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1.json'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(p):return json.loads(p.read_text())


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def ident(p):return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)


def publish(p,obj,replace=False):
    assert replace or not p.exists(),p
    temporary=p.with_name(p.name+'.pending')
    with temporary.open('x') as stream:
        stream.write(obj if isinstance(obj,str) else json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
        stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,p)


ack=read(R/f'{TASK}_ACK.json')
release=read(WORK/'inputs/releases/P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1.json')
launch=read(RUN/'LAUNCH_RESULT.json')
runtime=read(RUN/'graphics/RESULT.json')
mapping=read(RUN/'graphics/device_mapping.json')
loader=read(RUN/'graphics/loader_identity.json')
cleanup=read(RUN/'graphics/cleanup.json')
renderer=read(RUN/'graphics/renderer_identity.json')
exit_record=read(WORK/'COMMAND_EXIT.json')
process=read(WORK/'PROCESS.json')
visual=read(WORK/'RGB_SCENE_INSPECTION.json')
rgb=read(WORK/'RGB_INTEGRITY.json')
events=[json.loads(line) for line in (RUN/'graphics/events.jsonl').read_text().splitlines()]
api=[json.loads(line) for line in (RUN/'graphics/api_results.jsonl').read_text().splitlines()]
caps=release['resource_caps']
grouped=collections.defaultdict(list)
for row in events:grouped[row['event_id']].append(row)
counts={key:dict(planned_cap=value,entered=0,returned=0,failed=0,incomplete=0) for key,value in caps.items()}
assert len(events)==210 and len(grouped)==105
assert all(x['monotonic_ns']<=y['monotonic_ns'] for x,y in zip(events,events[1:]))
for event_id,rows in grouped.items():
    entries=[r for r in rows if r['phase']=='entered'];terminal=[r for r in rows if r['phase'] in ('returned','failed')]
    assert len(entries)==1 and len(terminal)<=1 and rows[0]['phase']=='entered'
    key=entries[0]['operation'];assert key in caps
    assert all(r['operation']==key and r['resource_units']=={key:1} for r in rows)
    counts[key]['entered']+=1;counts[key][terminal[0]['phase'] if terminal else 'incomplete']+=1
actual={k:v['entered'] for k,v in counts.items()}
totals={phase:sum(v[phase] for v in counts.values()) for phase in ('entered','returned','failed','incomplete')}
assert totals==dict(entered=105,returned=105,failed=0,incomplete=0)
assert actual==caps==runtime['resources']['entered_budget_usage']==launch['resources']['entered_budget_usage']
assert launch['status']==runtime['status']=='complete' and launch['returncode']==exit_record['returncode']==0
assert process['launcher_invocations']==exit_record['launcher_invocations']==1
assert not runtime['error'] and cleanup['errors']==[]
assert read(CLAIM)['release_sha256']==sha(WORK/'inputs/releases/P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1.json')
assert read(CLAIM)['run_id']==release['run_id']
assert len(mapping['devices'])==8 and len({d['mapping']['pci_bus_id'] for d in mapping['devices']})==8
targets=[d for d in mapping['devices'] if d['decision']=='target'];assert len(targets)==1
target=targets[0]
assert target['egl_index']==mapping['selected_egl_index']==runtime['outcome']['selected_egl_index']==0
assert target['attribute']['value']==0
assert target['mapping']=={k:release[k] for k in ('pci_bus_id','gpu_uuid')}
frozen={x['pci_bus_id']:x['gpu_uuid'] for x in read(PUB/'proposal/PROPOSAL.json')['physical_inventory']}
for row in mapping['devices']:
    assert row['attribute']['return_code']==1 and row['attribute']['output_defined'] is True
    assert row['cuda_pci']['return_code']==0
    assert row['mapping']['gpu_uuid']==frozen[row['mapping']['pci_bus_id']]
    assert row['kernel_identity']['pci_bus_id']==row['mapping']['pci_bus_id']
    assert row['kernel_identity']['gpu_uuid']==row['mapping']['gpu_uuid']
    assert 'EGL_NV_device_cuda' in row['extensions']
api_counts=collections.Counter(x['operation'] for x in api)
assert api_counts['egl_error_queries']==35 and all(x['raw']==0x3000 for x in api if x['operation']=='egl_error_queries')
assert [x['raw'] for x in api if x['operation']=='cuda_driver_initializations']==[0]
for name in ('egl_device_attribute_queries','cuda_device_pci_queries','egl_device_string_queries'):
    assert api_counts[name]==8
assert max(e['monotonic_ns'] for e in events if e['operation']=='cuda_device_pci_queries' and e['phase']=='returned') < min(e['monotonic_ns'] for e in events if e['operation']=='egl_platform_display_calls' and e['phase']=='entered')
assert loader['environment']==release['cuda_environment'] and loader['CUDA_before']==[]
expected_cuda=[str(PUB/'isolation/lib/libcuda.so.535.161.08')]
assert all(loader[k]==expected_cuda for k in ('CUDA_after_first_load','CUDA_after','CUDA_after_mapping'))
assert 'NVIDIA' in renderer['GL']['vendor'] and '535.161.08' in renderer['GL']['version']
assert runtime['outcome']['data_time_before']==runtime['outcome']['data_time_after']==0.0
assert rgb['npy_sha256']==runtime['outcome']['image_sha256']==sha(RUN/'graphics/rgb.npy')
assert rgb['PPM_NPY_pixels_identical'] and read(WORK/'RGB_VIEW_PROVENANCE.json')['roundtrip_pixels_identical']
assert visual['scene_consistency']=='visually_consistent' and visual['additional_render_or_readback']==0
timing={row['phase']:row for row in map(json.loads,(RUN/'wave_timing.jsonl').read_text().splitlines())}
start=timing['timed_process_started']['monotonic_seconds'];stop=timing['timed_process_exited']['monotonic_seconds']
samples=[json.loads(line) for line in (WORK/'GPU_OBSERVATIONS.jsonl').read_text().splitlines()]
inside=[s for s in samples if start<=s['query_started_monotonic_seconds']<=s['monotonic_seconds']<=stop]
assert len(inside)==18 and all(s['query_returncode']==0 for s in inside)
peaks={str(i):dict(NVML_memory_used_MiB=0,sampled_utilization_percent=0) for i in range(8)}
for sample in inside:
    lines=[list(map(int,line.split(','))) for line in sample['stdout'].splitlines()]
    assert {v[0] for v in lines}==set(range(8))
    for i,m,u in lines:
        peaks[str(i)]['NVML_memory_used_MiB']=max(peaks[str(i)]['NVML_memory_used_MiB'],m)
        peaks[str(i)]['sampled_utilization_percent']=max(peaks[str(i)]['sampled_utilization_percent'],u)
after=read(WORK/'OCCUPANCY_AFTER.json');assert after['returncode']==0
guard,_=json.JSONDecoder().raw_decode(after['stdout'][after['stdout'].index('{'):])
assert len(guard['gpus'])==8 and all(g['state']=='holder' for g in guard['gpus'].values())
post=read(WORK/'POST_EXIT_PROCESS_SNAPSHOT.json');assert post['launcher_pid_current'] is None and post['matching_processes']==[]
assert launch['restoration']['status']=='occupancy_resolved'
guard_log=(WORK/'GUARD_LOG_WINDOW.txt').read_text().splitlines()
assert sum('yielded;' in row and 'reserved=True' in row for row in guard_log)==8
assert sum('started holder manager' in row for row in guard_log)==8
for entry in ack['inputs_checked']:
    assert sha(Path(entry.get('frozen_copy',entry['path'])))==entry['sha256']
memory={'child_family_maxrss_KiB':exit_record['child_rusage_maxrss_KiB'],
    'child_family_maxrss_MiB':exit_record['child_rusage_maxrss_KiB']/1024,
    'RAM_scope':'Linux RUSAGE_CHILDREN max individual-child RSS, includes launcher/graphics descendant and observer subprocesses; not simultaneous aggregate or graphics-only RSS',
    'all_observer_NVML_samples':len(samples),'timed_child_NVML_samples':len(inside),
    'sample_window':'Query begins and ends within timed child; excludes holder release/restoration samples',
    'GPU_peaks_by_index':peaks,'GPU_allocator_peak_bytes':None,
    'GPU_allocator_peak_missing_reason':'No allocator instrumentation; rounded NVML samples can miss short allocations',
    'gpu_seconds':None,'gpu_seconds_missing_reason':'No GPU event timing/utilization integral; sampled utilization0 is not zero total GPU work',
    'runtime_output_bytes':sum(p.stat().st_size for p in RUN.rglob('*') if p.is_file()),
    'output_scope':'Original new run files, excluding existing bundle and CPU audit/PNG viewing copy'}
audit={'task_id':TASK,'audited_at_utc':now,'audit_mode':'CPU reads/reconciliation of saved artifacts, no driver call or rerender',
    'launcher_invocations':1,'returncode':0,'retries':0,'planned_vs_actual':counts,'phase_totals':totals,
    'all_caps_respected':True,'billing':'Each entered event charges once; terminal metadata adds0. All105 events have returned terminal.',
    'device_target':{k:release[k] for k in ('gpu_uuid','gpu_index','gpu_model','driver','pci_bus_id')},
    'selected_egl_index':0,'selected_CUDA_handle':0,'mapping_proved_by_PCI_UUID_not_ordinal':True,
    'candidate_count':8,'all_candidate_kernel_identities_match':True,'display_after_all_PCI_queries':True,
    'raw_API_operation_counts':dict(api_counts),'EGL_error_values':[0x3000],
    'CUDA_loaded_files':expected_cuda,'frozen_visibility_matched':True,'renderer_identity':renderer,
    'data_time_before':0.0,'data_time_after':0.0,'RGB_integrity':rgb,'RGB_scene_inspection':visual,
    'timing':launch['timing'],'memory_and_disk':memory,'cleanup':cleanup,
    'occupancy':{'launcher_restoration':launch['restoration'],'fresh_status':ident(WORK/'OCCUPANCY_AFTER.json'),
        'guard_log':ident(WORK/'GUARD_LOG_WINDOW.txt'),'whole_wave_evidence':'All8 holders yielded for reservation; no holder start in timed child interval; all8 restarted18:42:56UTC after timed exit18:42:55.723607UTC; post-exit process scan empty',
        'fresh_holder_count':8,'guard_pid':guard['pid'],'holder_manager_pids':[g['manager_pid'] for g in guard['gpus'].values()],
        'process_snapshot':ident(WORK/'POST_EXIT_PROCESS_SNAPSHOT.json')},
    'CPU_prelaunch_note':read(WORK/'PRELAUNCH_PREPARATION_NOTE.json'),
    'independent_CPU_checker_run':False,'release_consumed':True,'analysis_acceptance_and_closure_pending':True,
    'old_native_v5_or_B_executed':False,'deleted_files':0,
    'run_artifacts':[ident(p) for p in sorted(RUN.rglob('*')) if p.is_file()]}
publish(WORK/'FINAL_AUDIT.json',audit)
publish(WORK/'COUNTS.tsv','resource\tplanned_cap\tentered\treturned\tfailed\tincomplete\n'+''.join(
    k+'\t'+'\t'.join(str(v[p]) for p in ('planned_cap','entered','returned','failed','incomplete'))+'\n' for k,v in counts.items()))
publish(WORK/'DEVICE_MAPPING.tsv','egl_index\treturned_CUDA_handle\tPCI\tkernel_UUID\tdecision\n'+''.join(
    f"{row['egl_index']}\t{row['attribute']['value']}\t{row['normalized_pci']}\t{row['mapping']['gpu_uuid']}\t{row['decision']}\n" for row in mapping['devices']))
report=f'''| 项目 | 实测结果 / 范围 |
|---|---|
| 一次真实执行 | rc=0，runtime/LAUNCH_RESULT均complete；仅本次静态graphics路径，待分析端验收关闭release |
| 目标身份 | EGL index0返回CUDA handle0→`0000:0f:00.0`→`GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe`，8候选PCI/内核UUID均核对；不是索引假定 |
| 库与renderer | 冻结535.161.08 CUDA路径与可见性一致；GL NVIDIA H100 80GB HBM3/PCIe/SSE2，4.6.0 NVIDIA535.161.08；EGL NVIDIA1.5 |
| RGB场景 | 已查看保存的64×64 uint8 RGB：红橙色有明暗球体、蓝灰色透视平面、黑色背景，与冻结XML相符；NPY/PPM/PNG查看副本像素相同 |
| 清理 / occupancy | cleanup无错误；context销毁、terminate、releaseThread、MjrContext free各1；全8holder在进程族退出后恢复，18:44:03 UTC再确认 |

| 资源 | planned | entered | returned | failed | incomplete |
|---|---:|---:|---:|---:|---:|
| attempt / 枚举 / cuInit（各） | 1 | 1 | 1 | 0 | 0 |
| 扩展 / 属性 / PCI（各） | 8 | 8 | 8 | 0 | 0 |
| getProcAddress / eglGetError | 5 / 35 | 5 / 35 | 5 / 35 | 0 | 0 |
| display初始化 / EGLcontext / render / RGB（各） | 1 | 1 | 1 | 0 | 0 |
| VLA / MetaWorld / reset / 物理推进 / 训练 / 重试（各） | 0 | 0 | 0 | 0 | 0 |

全项 entered/returned/failed/incomplete=105/105/0/0，所有caps满足；[完整计数]({WORK/'COUNTS.tsv'})包括库加载2、EGL/CUDA符号11/2、清理及其他辅助项。35次EGL错误查询均0x3000、cuInit/8PCI返回均0。模型静态data.time=0→0，不产生策略控制步或episode成功率。

墙钟：前置5.306s，预约/停全卡50.638s，wrapper0.004s，timed child10.003s，释放0.019s，恢复观察8.005s；launcher总73.975s（外层观察74.125s）。120+10s只约束子进程，未触发timeout。

RAM最大单个子进程RSS107.254MiB（不是并发总量）；timed child内18次完整NVML采样：GPU0峰值15MiB，其余各3MiB，利用率样本均0%。采样不等于精确GPU消耗；allocator peak和GPU-seconds仍null。run输出119250bytes，估计上限不冒充实测。

RGB NPY SHA `{rgb['npy_sha256']}`；查看器不支持PPM，因此仅CPU无损编码PNG供目视，往返像素校验一致，无新增render/readback：[RGB]({WORK/'RGB_VIEW.png'})、[目视记录]({WORK/'RGB_SCENE_INSPECTION.json'})、[像素证据]({WORK/'RGB_VIEW_PROVENANCE.json'})。

证据：[LAUNCH_RESULT]({RUN/'LAUNCH_RESULT.json'})、[device mapping]({RUN/'graphics/device_mapping.json'})、[raw API]({RUN/'graphics/api_results.jsonl'})、[FINAL_AUDIT]({WORK/'FINAL_AUDIT.json'})、[holder日志]({WORK/'GUARD_LOG_WINDOW.txt'})、[完整SHA清单]({WORK/'FINAL_ARTIFACT_MANIFEST.json'})。

ACK在先，真实命令仅1次，未另跑CPU checker。observer准备时一次路径文本断言在真实启动前修正，记录在RESULT与PRELAUNCH_PREPARATION_NOTE，不是graphics重试。冻结命令/库/设备/可见性未改，B未参与，无删除，native v5未运行。本release已消费，请分析端关闭；随后等待新任务。
'''
publish(R/f'{TASK}_REPORT.md',report)
publish(R/f'{TASK}_HEARTBEAT.json',{'task_id':TASK,'status':'completed_audit_ready','updated_at_utc':now,
    'launcher_invocations':1,'returncode':0,'phase_totals':totals,'actual_resource_counts':actual,
    'RGB_scene_consistency':'visually_consistent','holder_count_restored':8,'release_consumed':True},replace=True)
publish(WORK/'NEW_ARTIFACTS_INVENTORY.json',{'task_id':TASK,'retention':'Keep all pending analysis decision; no deletion release',
    'created_roots':[str(WORK),str(RUN)],'created_singletons':[str(CLAIM)],'receipt_prefix':str(R/TASK),
    'PNG_viewing_copy_retained':True,'temporary_and_CPU_prelaunch_evidence_retained':True,'actual_deletions':0})
files={p for root in (WORK,RUN) for p in root.rglob('*') if p.is_file()}
files.update([CLAIM,*[R/f'{TASK}_{name}' for name in ('ACK.json','REPORT.md','HEARTBEAT.json')]])
manifest={'task_id':TASK,'created_at_utc':now,'file_count':len(files),'files':[ident(p) for p in sorted(files)],
    'scope':'All new runtime/claim/CPU observer/audit/visual/retention evidence and ACK/report/final heartbeat; excludes manifest self/final RESULT/later queue to avoid cycles'}
publish(WORK/'FINAL_ARTIFACT_MANIFEST.json',manifest)
artifacts={
    'short_report':R/f'{TASK}_REPORT.md','complete_manifest':WORK/'FINAL_ARTIFACT_MANIFEST.json',
    'audit':WORK/'FINAL_AUDIT.json','counts_table':WORK/'COUNTS.tsv','mapping_table':WORK/'DEVICE_MAPPING.tsv',
    'runtime_result':RUN/'graphics/RESULT.json','LAUNCH_RESULT':RUN/'LAUNCH_RESULT.json',
    'device_mapping':RUN/'graphics/device_mapping.json','loader_identity':RUN/'graphics/loader_identity.json',
    'renderer_identity':RUN/'graphics/renderer_identity.json','raw_API':RUN/'graphics/api_results.jsonl',
    'events':RUN/'graphics/events.jsonl','cleanup':RUN/'graphics/cleanup.json',
    'RGB_npy':RUN/'graphics/rgb.npy','RGB_ppm':RUN/'graphics/rgb.ppm','RGB_view':WORK/'RGB_VIEW.png',
    'RGB_integrity':WORK/'RGB_INTEGRITY.json','RGB_scene_inspection':WORK/'RGB_SCENE_INSPECTION.json',
    'RGB_view_provenance':WORK/'RGB_VIEW_PROVENANCE.json','occupancy_after':WORK/'OCCUPANCY_AFTER.json',
    'guard_log':WORK/'GUARD_LOG_WINDOW.txt','process_exit':WORK/'POST_EXIT_PROCESS_SNAPSHOT.json',
    'command_exit':WORK/'COMMAND_EXIT.json','prelaunch_note':WORK/'PRELAUNCH_PREPARATION_NOTE.json',
    'retention_inventory':WORK/'NEW_ARTIFACTS_INVENTORY.json'}
result={'campaign_id':release['campaign_id'],'task_id':TASK,'revision':1,'role':'A','hostname':ack['hostname'],
    'session_id':ack['executor_session_id'],'status':'complete','started_at_utc':ack['started_at_utc'],'finished_at_utc':now,
    'release_id':release['release_id'],'run_id':release['run_id'],'wave_id':release['wave_id'],'shard_id':release['shard_id'],
    'input_identity':{'protocol':[ident(WORK/'inputs'/rel) for rel in ['CONTROL.json','TASK_BOARD.json',
        'tasks/'+TASK+'.md','releases/P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1.json','contracts/REPORT_CONTRACT.md',
        'manifests/EGL_CUDA_MAP_CPU_V1_ACCEPTANCE.json']],
        'code':[ident(PUB/name) for name in ['BUNDLE_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json','commands/run_proposed_graphics_probe.sh']],
        'config':ident(PUB/'proposal/PROPOSAL.json'),'data':ident(PUB/'scene.xml'),
        'model':{'path':None,'sha256':None,'reason':'No policy/model weights; only authorized static MuJoCo model from frozen scene XML'},
        'verification':'Frozen real launcher performed full bundle/external identity checks; audit verifies output and small input identities, no independent checker'},
    'artifacts':{key:ident(path) for key,path in artifacts.items()},
    'resource_counts':{**actual,'gpu_seconds':None,'deletions':0},
    'GPU_seconds_missing_reason':memory['gpu_seconds_missing_reason'],'planned_vs_actual':counts,'phase_totals':totals,
    'timing':launch['timing'],'memory_and_disk':memory,
    'outcome':{**runtime['outcome'],'RGB_visually_matches_frozen_scene':True,'scope':'static graphics only',
        'episode_success_rate':None,'episode_failure_rate':None,'native_v5_validated':False,'analysis_acceptance_pending':True},
    'failures_and_retries':[{'scope':'CPU observer preparation before any real launch','exit_code':1,
        'error':'Literal absolute-path assertion was too strict for BASE-relative source construction',
        'recovery':'Corrected only CPU preparation assertion; ACK remained intact, frozen executable unchanged; graphics invocations before correction0',
        'graphics_retries':0,'evidence':str(WORK/'PRELAUNCH_PREPARATION_NOTE.json')}],
    'real_probe_failures':0,'real_probe_retries':0,'cleanup_errors':[],
    'findings':[
        'One frozen real command executed successfully after ACK; returncode0 and exclusive release claim retained.',
        'All8 EGL CUDA handles returned valid PCI/kernel UUID identities; fixed target unique before any display/context.',
        'Frozen535 CUDA loaded path and visibility matched; NVIDIA GL/EGL renderer identity recorded.',
        'Exactly1 EGL context,1 static model/data,1 explicit forward,1 render and1 RGB readback; data.time stayed0.',
        'Saved image visibly contains the frozen red-orange sphere and blue-grey plane; NPY/PPM/PNG-view pixels match, no additional render.',
        '105entered/105returned/0failed/0incomplete; all35 EGL error reads were SUCCESS, every cap respected.',
        'Cleanup succeeded; all8holders yielded during reservation and restarted after process-family exit, fresh status confirmed.',
        'GPU0 sampled memory peak15MiB/other cards3MiB; RAM max-child107.254MiB; precise GPU-seconds and allocator peak remain unknown.',
        'VLA/MetaWorld/reset/physics advancement/training/deletion/retry0; B and native v5 not run.',
        'Release consumed; analysis acceptance/closure requested, old evidence and all new artifacts preserved.',
    ],'blockers':[],
    'next_task_proposal':{'owner':'analysis','action':'Inspect saved RGB and receipts, close consumed release, then decide any separate native-chain task/release','automatically_started':False},
    'release_consumed':True,'analysis_close_requested':True,'all_new_artifacts_retained':True}
publish(R/f'{TASK}_RESULT.json',result)
print(json.dumps({'RESULT':ident(R/f'{TASK}_RESULT.json'),'LAUNCH_RESULT':ident(RUN/'LAUNCH_RESULT.json'),
    'report_lines':len(report.splitlines()),'result_artifacts':len(artifacts),'manifest_files':len(files),
    'phase_totals':totals,'memory':memory},ensure_ascii=False))
