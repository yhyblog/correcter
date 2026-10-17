"""Quote full120 branches from saved timings and metadata sizes, not live probes."""
from pathlib import Path
import ast,difflib,hashlib,json,statistics
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');B=ROOT/'Corrector/sim_command/20260919'
P=B/'results/A/A11_MT50_CONTINUATION_CPU_V1';OLD=B/'results/A/A11_BATCH_SCALING_CPU_V1'
SAVED=B/'results/A/A11_COMMON_POOL_BATCH1_V1'
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p).resolve();raw=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
timing=read(SAVED/'SAVED_TIMING_AUDIT.json');storage=read(SAVED/'SAVED_STORAGE_AUDIT.json');proposal=read(P/'proposal/PROPOSAL.json')
loads=[a['selected_numeric_intervals']['load_PI05_SFT030000']['seconds'] for a in timing['attempts']]
measured=dict(source=ref(SAVED/'SAVED_TIMING_AUDIT.json'),wave_wall_seconds=timing['outer_elapsed_seconds'],
    cold_loads=len(loads),concurrency=timing['parent_concurrency_by_saved_event_order'],
    child_host_elapsed_sum_seconds=timing['sum_known_child_elapsed_seconds'],
    load_host_interval_sum_seconds=sum(loads),mean_load_host_seconds=statistics.mean(loads),
    min_load_host_seconds=min(loads),max_load_host_seconds=max(loads),
    load_host_interval_fraction=sum(loads)/timing['sum_known_child_elapsed_seconds'],
    not_GPU_seconds=True,not_eliminable_time=True,not_physical_IO=True,
    source_coverage_warning='Batch1 contains early legal terminals and106 rather than120 cold branches; never reuse as new count cap')
oldio=read(OLD/'CAPACITY_AND_THROUGHPUT.json')['IO_quote']
sizes={x['path']:x['size_bytes'] for x in oldio['large_file_visits_per_authorization']}
seen=set();visits=[];manifest_reads=[]
def walk(r):
    if r['path'] in seen:return
    seen.add(r['path']);manifest_reads.append(r)
    m=read(r['path'])
    for f in m['files']:
        size=f.get('size_bytes',sizes.get(f['path']))
        visits.append(dict(path=f['path'],sha256=f['sha256'],size_bytes=size,
            size_basis='reference field' if 'size_bytes' in f else 'accepted previous quote metadata' if size is not None else 'unknown; no new stat/probe'))
    for child in m.get('inherited_manifests',[]):walk(child)
for k in ('code_manifest','input_manifest','external_manifest','inherited_package_manifest','config_manifest'):walk(proposal[k])
known=sum(v['size_bytes'] for v in visits if v['size_bytes'] is not None)
unknown=[v for v in visits if v['size_bytes'] is None]
checkpoint=oldio['large_file_visits_per_authorization'][0]
io=dict(full_authorizations_max=121,metadata_manifest_file_visits_per_full_check=len(visits),
    known_sized_hash_read_subtotal_per_full_check_bytes=known,
    known_sized_hash_read_subtotal_121checks_bytes=121*known,
    unknown_size_reference_visits_per_full_check=len(unknown),unknown_size_unique_paths=len({v['path'] for v in unknown}),
    unknown_size_refs=unknown,strict_total_hash_read_upper_bytes=None,
    logical_checkpoint_file_load_bytes_for120=120*checkpoint['size_bytes'],checkpoint_size_evidence=checkpoint,
    checkpoint_size_source=ref(OLD/'CAPACITY_AND_THROUGHPUT.json'),
    physical_disk_network_bytes=None,cache_hit_assumption=None,
    additional_unquoted_reads='manifest/ref/control/board polling and library/tokenizer/external cache reads; not included in known-size subtotal',
    large_weight_payloads_read_or_rehashed=0,live_capacity_or_memory_queries=0)
quote=dict(status='UNAUTHORIZED_FULL120_PARAMETER_QUOTE',measured_Batch1=measured,
    concurrency=2,cold_models_reused=False,parents=8,branches_per_parent=15,maximum_attempts=120,
    resource_caps=proposal['resource_caps'],scheduler_aux_caps=proposal['scheduler_caps'],timeouts=proposal['timeouts'],
    loading_only_arithmetic=dict(branches=120,observed_mean_seconds=statistics.mean(loads),
        total_host_intervals_seconds=120*statistics.mean(loads),
        half_sum_at_two_slots_arithmetic_seconds=60*statistics.mean(loads),
        label='loading component only; neither wave ETA nor lower/upper wall bound; overlap/IO/imbalance unknown'),
    full_work_parameterization=dict(
        per_task='T_task = 15*(L_task + I_task + U_task) +453*S_task +4500*C_task +4515*O_task +publication_task',
        terms=dict(L_task='cold model/tokenizer/processor load host interval; new-task mean unknown',
            I_task='all initialization work including52 resets and task-specific direct physics; latency unknown',
            U_task='hash/import/state/cleanup/log residual outside other chosen intervals; nonnegative unknown',
            S_task='one native10flow/raw50 and its prefix preprocessing outside model-load interval',
            C_task='one control call inclusive of simulator/native observation; avoid summing nested renderer again',
            O_task='feature/write work outside C_task; includes step0; nested shared times must be partitioned',
            publication_task='after entire wave compute exit; all data/cost publication budget300s total'),
        two_slot_schedule='simulate FIFO completion using8 unknown T_task; no linear speedup claim',
        wall_bound='branch1800+30, parent27900, reservedwave111900+30; preparation900/handoff300/publication300/restoration120 separate; lock/drain/end-to-end hard bound null'),
    IO_quote=io,storage=dict(proposed_bounds=proposal['storage'],admission_plus_floor_bytes=proposal['storage']['admission_bytes']+proposal['storage']['minimum_remaining_space_bytes'],
        separate_risk_acceptance_required=True,Batch1_acceptance_reused=False,
        saved_Batch1_observation=ref(SAVED/'SAVED_STORAGE_AUDIT.json'),
        saved_Batch1_final_output_inode_bytes=storage['final_output_unique_inode_bytes'],
        saved_Batch1_cache_sample_peaks=storage['sampled_private_cache_peaks'],
        old_snapshot_is_not_current_admission=True,current_available_capacity_bytes=None,
        project_quota_bytes=None,container_memory_limit_bytes=None,RSS_peak_bytes=None,VRAM_peak_bytes=None,
        monitor_overshoot_bytes=None,uncontrolled_third_party_temp_bytes=None,physical_IO_bytes=None),
    future_optimizations_implemented=False,actual_runtime_operations=0)
write(P/'RESOURCE_AND_STORAGE_QUOTE.json',quote)
write(P/'SAVED_TIMING_REFERENCE.json',measured)
table=read(P/'config/MT50_TASK_TABLE.json');lines=['# MT50 静态初始化预算','',
    '任务字典index、wrapper环境ID、示范language index分别保留。数值来自窄源码路径和XML timestep；不是实际环境/状态资格证明。',
    'taskset每attempt50 reset+1实例，wrapper1 reset+1实例，诊断1 reset；每native reset调用reset_model两次。每阶段细项在JSON。',
    '所有任务控制最多300步、4000物理子步、300显式forward、301 RGB/特征观测；合法终局即止。',
    'box-close与door-lock的direct mj_step另计104×5=520子步；do_simulation内部mj_step不重复计。',
    '', '| task | dict index | env ID | language index | reset_model forward | direct step/ reset_model | init物理 | init显式forward | 证据 |',
    '|---|---:|---:|---:|---:|---:|---:|---:|---|']
for r in sorted(table['rows'],key=lambda x:x['task']):
    c=r['initialization_caps'] or {}
    lines.append('| '+ ' | '.join(str(x) for x in [r['task'],r['task_dictionary_index'],r['wrapper_environment_id'],r['demonstration_language_index'],r.get('reset_model_forwards'),r.get('reset_model_direct_steps'),c.get('initialization_physics_substeps'),c.get('initialization_mj_forward_calls'),'复用已验收5任务' if r['evidence_reused'] else r['static_cap_status']])+' |')
lines += ['', '50静态可报价，0静态未知；仅5任务已有某些旧parent实际闭合证据。新8任务均未实测，不宣称完整隐藏状态等价。RNG拒绝循环次数和成功初始化概率未知；分支wall timeout沿用，不新增重采。']
(P/'MT50_INITIALIZATION_BUDGET.md').write_text('\n'.join(lines)+'\n')
changed=[];unchanged=[];patches=[]
for f in sorted((P/'code').rglob('*.py')):
    rel=f.relative_to(P/'code');orig=OLD/'code'/rel
    row=dict(relative=str(rel),new=ref(f),previous=ref(orig) if orig.exists() else None)
    ast.parse(f.read_text(),filename=str(f))
    if orig.exists() and orig.read_bytes()==f.read_bytes():unchanged.append(row)
    else:
        changed.append(row);patches+=list(difflib.unified_diff(orig.read_text().splitlines(True) if orig.exists() else [],f.read_text().splitlines(True),fromfile=str(orig),tofile=str(f)))
algorithm_names=['controller.py','pool_protocol.py','batch_scheduler.py','process_backend.py','execution.py','runtime_engine.py','runtime_state.py','full_state.py','public_records.py','sidecar_output.py','shared_plans.py','launch.py','reserved.py']
assert all(any(x['relative']==name for x in unchanged) for name in algorithm_names)
write(P/'MINIMAL_DIFF.json',dict(changed=changed,unchanged=unchanged,unchanged_algorithm_and_lifecycle_files=algorithm_names,
    public_interface_changed=False,sidecar_changed=False,numerical_candidate_or_label_algorithm_changed=False,
    runtime_implementation_changes='table support/source exclusion and source seeds/future identity/concurrency2/new risk scope/direct-step accounting only'))
(P/'MINIMAL_DIFF.patch').write_text(''.join(patches))
(P/'RESOURCE_QUOTE.md').write_text(f'''# Batch2 未授权资源报价

固定8源、并发2、每源15 cold分支；按满120分支计，sample3624/flow36240/control36000/obs36120。52 reset/attempt独立由每任务共同调用路径推导；本批初始化6240reset、12480reset_model、3127800物理子步、12720显式forward。box-close的7800额外子步已入原116计数键，未把未启动/提前终局作为节省上界。

Batch1保存墙钟{measured['wave_wall_seconds']:.3f}s、106 cold载入、峰值并发2。平均载入host区间{measured['mean_load_host_seconds']:.6f}s，占child host区间和{100*measured['load_host_interval_fraction']:.4f}%；不是GPU秒或可消除时间。仅载入的120次算术分量为{120*statistics.mean(loads):.3f} host秒；不能据此承诺工期。各任务完整时长采用JSON参数式，新的任务几何/初始化/IO延迟未知。

已知尺寸完整校验的121遍逻辑读取小计{121*known}B，另有{len(unknown)}次未知尺寸引用/遍，严格总上界null；120次checkpoint逻辑载入1122486090240B，不是实际物理IO。未hash大权重。

Batch2拟定准入加floor为{quote['storage']['admission_plus_floor_bytes']}B和564096 inode；每child512MiB、单record32MiB、每parent私有cache2GiB等原受控字节限保留。并发2 RAM128GiB只是规划；项目quota、容器限制、RSS/VRAM、第三方临时写入及监测间超调未知。未查询当前容量。Batch1风险接受已关闭，本模板accepts_monitoring_gaps=false；未来须分析独立接受后再发布。

preparation900、handoff300、child1800+30、parent27900、reserved111900+30、publication300、restoration观察120秒分别计。锁等待、最终清理、端到端和GPU秒硬上界仍null。全A单预约、全部正式后代退出后发布/恢复；不做模型复用或闲置子集holder优化。
''')
print(json.dumps(dict(changed_code_files=len(changed),unchanged_code_files=len(unchanged),
    mean_load_seconds=measured['mean_load_host_seconds'],load_host_fraction=measured['load_host_interval_fraction'],
    known_hash_logical_subtotal=121*known,unknown_size_visits=len(unknown),real_operations=0)))
