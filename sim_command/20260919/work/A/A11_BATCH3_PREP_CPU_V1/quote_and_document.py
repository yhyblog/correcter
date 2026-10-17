"""Saved-metadata-only full120 parameter quote. Never loads model payloads."""
from pathlib import Path
import hashlib,json,statistics
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A11_BATCH3_PREP_CPU_V1';OLD=B/'results/A/A11_MT50_CONTINUATION_CPU_V1'
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p).resolve();raw=p.read_bytes()
    return dict(path=str(p),realpath=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')
    return ref(p)
proposal=read(P/'proposal/PROPOSAL.json');saved=[]
for batch in (1,2):
    root=B/f'results/A/A11_COMMON_POOL_BATCH{batch}_V1'
    timing=read(root/'SAVED_TIMING_AUDIT.json');storage=read(root/'SAVED_STORAGE_AUDIT.json')
    loads=[x['selected_numeric_intervals']['load_PI05_SFT030000']['seconds'] for x in timing['attempts']
        if 'load_PI05_SFT030000' in x['selected_numeric_intervals']]
    saved.append(dict(batch=batch,timing_ref=ref(root/'SAVED_TIMING_AUDIT.json'),storage_ref=ref(root/'SAVED_STORAGE_AUDIT.json'),
        cold_loads=len(loads),concurrency=timing['parent_concurrency_by_saved_event_order'],
        wave_wall_seconds=timing['outer_elapsed_seconds'],child_host_seconds=timing['sum_known_child_elapsed_seconds'],
        model_load_host_interval_mean_seconds=statistics.mean(loads),model_load_host_interval_sum_seconds=sum(loads),
        model_load_host_interval_min_seconds=min(loads),model_load_host_interval_max_seconds=max(loads),
        final_output_unique_inode_bytes=storage['final_output_unique_inode_bytes'],
        saved_capacity_bytes=storage['sampled_minimum_filesystem_available_bytes'],
        saved_capacity_inodes=storage['sampled_minimum_filesystem_available_inodes'],
        last_saved_monitor=storage['last_saved_monitor'],
        sampled_private_cache_peaks=storage['sampled_private_cache_peaks'],
        GPU_seconds=None,quota=None,not_current_capacity=True,
        interpretation='historical measured workload only; no scaling by observed success/s300 fractions'))
old_quote=B/'results/A/A11_BATCH_SCALING_CPU_V1/CAPACITY_AND_THROUGHPUT.json'
oldio=read(old_quote)['IO_quote'];sizes={x['path']:x['size_bytes'] for x in oldio['large_file_visits_per_authorization']}
seen=set();visits=[];manifest_refs=[]
def walk(row):
    if row['path'] in seen:return
    seen.add(row['path']);manifest_refs.append(row)
    data=read(row['path'])
    for f in data['files']:
        size=f.get('size_bytes',sizes.get(f['path']))
        visits.append(dict(path=f['path'],sha256=f['sha256'],size_bytes=size,
            size_basis='saved reference field or previously accepted size evidence; no new target stat'))
    for inherited in data.get('inherited_manifests',[]):walk(inherited)
for key in ('code_manifest','input_manifest','external_manifest','inherited_package_manifest','config_manifest'):
    walk(proposal[key])
known=sum(v['size_bytes'] for v in visits if v['size_bytes'] is not None)
unknown=[v for v in visits if v['size_bytes'] is None]
checkpoint=oldio['large_file_visits_per_authorization'][0]
io=dict(full_input_checks_max=121,file_visits_per_full_check=len(visits),
    known_sized_hash_read_subtotal_per_full_check_bytes=known,
    known_sized_hash_read_subtotal_121_checks_bytes=121*known,
    unknown_size_visits_per_full_check=len(unknown),unknown_size_refs=unknown,
    inherited_manifest_refs=manifest_refs,strict_total_read_upper_bytes=None,
    checkpoint_file_loads_max=120,checkpoint_size_evidence=checkpoint,checkpoint_size_source=ref(old_quote),
    logical_checkpoint_load_bytes_full120=120*checkpoint['size_bytes'],
    physical_disk_network_bytes=None,cache_hit_assumptions=None,
    unquoted_additional_reads='CONTROL/BOARD/ref polling, manifests, imports, tokenizer/library/native caches; no bound inferred',
    actual_large_payload_reads_or_hashes=0)
rows=[]
table=read(P/'config/MT50_TASK_TABLE.json')
for parent in proposal['parents']:
    task=parent['source']['task'];profile=next(x for x in table['rows'] if x['task']==task);ic=profile['initialization_caps']
    rows.append(dict(task=task,parent_key=parent['parent_key'],source_id=parent['source']['source_id'],
        env_seed=parent['source']['env_seed'],master_seed=parent['source']['master_seed'],
        parent_attempts=15,initialization_per_attempt=ic,
        initialization_parent_physics_cap=15*ic['initialization_physics_substeps'],
        initialization_parent_forward_cap=15*ic['initialization_mj_forward_calls'],
        static_extra_direct_substeps_per_attempt=520 if task=='door-lock-v3' else 0,
        current_source_actual_qualification='unknown; not run',physical_equality_proven=None))
storage=proposal['storage'];st=dict(proposed_bounds=storage,
    admission_plus_floor_bytes=storage['admission_bytes']+storage['minimum_remaining_space_bytes'],
    independent_risk_required=True,accepts_monitoring_gaps=False,prior_batch_risks_reused=False,
    saved_Batch1_Batch2_capacity_is_not_current_admission=True,current_capacity_bytes=None,
    project_quota_bytes=None,container_memory_limit_bytes=None,process_RSS_peak_bytes=None,VRAM_peak_bytes=None,
    uncontrolled_library_temp_bytes=None,unlinked_bytes=None,monitor_overshoot_bytes=None,physical_IO_bytes=None,
    full120_bounds_not_reduced_by_saved_outcomes=True)
quote=dict(status='UNAUTHORIZED_FULL120_PARAMETER_QUOTE',concurrency=2,parents=8,branches_per_parent=15,maximum_attempts=120,
    resource_caps=proposal['resource_caps'],scheduler_aux_caps=proposal['scheduler_caps'],timeouts=proposal['timeouts'],
    per_task_initialization=rows,saved_measurements=saved,IO_quote=io,storage=st,
    loading_component_scenarios=[dict(measurement_batch=x['batch'],
        observed_mean_host_seconds=x['model_load_host_interval_mean_seconds'],
        full120_sum_host_seconds=120*x['model_load_host_interval_mean_seconds'],
        sum_divided_by_two_arithmetic_seconds=60*x['model_load_host_interval_mean_seconds'],
        scope='loading component only; neither future ETA nor bound/GPU seconds/linear speedup') for x in saved],
    full_work_parameterization=dict(
        per_parent='T_task = 15*(L_task + I_task + U_task) + 453*S_task + 4500*C_task +4515*O_task + P_task',
        definitions=dict(L_task='cold model/tokenizer/processor host loading interval; new workload latency unknown',
            I_task='all52 resets, task-specific initialization forwards/direct steps per attempt; latency unknown',
            U_task='hash/import/full-state/cleanup/log residual outside named intervals; unknown',
            S_task='one raw50 sampling including10flow and prefix pre/post processing outside other intervals',
            C_task='one control including nested native observation/render; do not add nested render duration again',
            O_task='feature serialization/writer host work outside control; includes step0',
            P_task='parent data/cost publication; shared whole-wave publication cap300s'),
        schedule='two FIFO worker slots over8 unknown T_task; branch stays on its fixed UUID',
        success_fraction_scaling=False,new_task_actual_durations=None,
        final_drain_lock_wait_end_to_end_hard_upper_seconds=None,GPU_seconds_upper=None),
    interpretation=dict(nonnormal_comparison_branches_max=112,candidate_replacement_branches_max=96,G0_old_control_branches_max=16,
        G0_old_intervened=False,G0_old_plan_replaced=False,online_G0_forward_calls=0,
        door_lock_extra7800_is_static_only=True,box_close_actual7800_does_not_prove_door_lock_qualification=True),
    new_GPU_probe_proposed=False,model_reuse_implemented=False,real_operations=0)
write(P/'RESOURCE_AND_STORAGE_QUOTE.json',quote)
write(P/'SAVED_TIMING_REFERENCES.json',dict(saved_measurements=saved,scope='small saved metadata; no run payload rehash or live query'))
write(P/'FULL120_INITIALIZATION_QUOTE.json',dict(rows=rows,
    batch_initialization_caps={k:proposal['resource_caps'][k] for k in ('environment_reset_calls','reset_model_calls',
        'initialization_reset_calls','initialization_do_simulation_calls','initialization_physics_substeps','initialization_mj_forward_calls')},
    table_reused=ref(P/'config/MT50_TASK_TABLE.json'),door_lock_actual=None))
seed_lines=['| task | env seed | init物理/attempt | init forward/attempt |',
    '|---|---:|---:|---:|']
for x in rows:seed_lines.append(f"| {x['task']} | {x['env_seed']} | {x['initialization_per_attempt']['initialization_physics_substeps']} | {x['initialization_per_attempt']['initialization_mj_forward_calls']} |")
with (P/'RESOURCE_QUOTE.md').open('x') as f:f.write(f'''# Batch3 未授权满120资源报价

固定8源、A/train0/cut5、并发2，每源15顺序cold分支。sample3624/flow36240/control36000/obs36120，原116计数键和scheduler aux保留。初始化6240 native reset、12480 reset_model、3127800物理子步、9600显式forward；dial-turn与door-lock每attempt只有2显式forward，其他6任务106。door-lock静态额外520/attempt、满15支7800已入总cap；其实际初始化/full-state/MJB资格未知，只在未来已计划parent内验证。

{chr(10).join(seed_lines)}

Batch1/2保存墙钟分别{saved[0]['wave_wall_seconds']:.3f}s / {saved[1]['wave_wall_seconds']:.3f}s，cold载入106 /120次，实测并发均2；只供历史时序参考。满120采用JSON的逐task参数式和双槽FIFO模型，未用终局37/83比例压缩预算，也不推断GPU秒或线性加速。

121次完整输入检查的已知尺寸逻辑读取小计{121*known}B；另有{len(unknown)}次未知尺寸引用/遍，严格总上界null。120次checkpoint逻辑载入{120*checkpoint['size_bytes']}B另列，均不是实际物理IO；未重hash大权重。

本批拟准入含floor {st['admission_plus_floor_bytes']}B、564096 inode。每child writer512MiB、record32MiB、每parent私有cache2GiB及原日志限保持；并发2 RAM128GiB只是规划，RLIMIT_AS不设置。项目quota、当前容量、RSS/VRAM、第三方temp、unlinked和监测超调均未知，保存的Batch2容量不能代替本批实时准入。本模板风险接受false，需分析独立决定。

preparation900、handoff300、child1800+30、parent27900、reserved111900+30、publication300、恢复观察120秒分计；锁等待、最终清理、端到端与GPU秒硬上界null。单预约、同组同锁，全A8holder至正式后代退出和发布完成后统一恢复；本轮未查询holder或执行上述路径。
''')
checks=read(P/'checks/metadata/CHECK_RESULT.json')
write(P/'CHECK_INDEX.json',dict(status='PASS',metadata_checks=checks['checks'],metadata_result=ref(P/'checks/metadata/CHECK_RESULT.json'),
    shell_syntax=ref(P/'checks/SHELL_SYNTAX.json'),old_fixture_suites_rerun=False,new_real_operations=0))
with (P/'REPORT.md').open('x') as f:f.write(f'''# A11_BATCH3_PREP_CPU_V1

CPU准备完成，唯一新提案A11_COMMON_POOL_BATCH3_V1仍未授权。已核对CONTROL49/TASK_BOARD58及CPU release SHA，新ACK已写。V3有效索引16train/dev0、V2处置17已处理/483未执行保持；旧p04 normal-only不补源，14旧计算release不复用。

固定coffee-button、coffee-pull、coffee-push、dial-turn、door-close、door-lock、door-open、door-unlock（均-v3/A/train0/cut5），确定seed与UUID逐项见SOURCE_AND_SEED_PROPOSALS.json。真实run/cache/shard/command/claim均未创建。原50任务表、source证据及25代码文件逐字节复用；3代码文件只替换Batch3身份和bounded_batch3风险作用域字符串，精确diff附后。算法、直接mj_step hook、state、调度与全8holder生命周期不变。

70项新元数据检查和2条shell语法检查通过；覆盖17槽排除、seed/owner/cut/UUID与独立路径、CONFIG301、逐parent/116总量、完整ready/running正例，以及未授权、14旧身份、关闭/消耗、错误board和未接受/缺失/旧批存储风险拒绝。仅合成元数据，不重跑旧89/133/185或数值/环境fixture。

满120报价sample3624/flow36240/control36000/obs36120；初始化6240reset/12480reset_model/3127800物理/9600显式forward。door-lock额外7800为静态报价，已验收box-close实测7800仅作同hook证据。新源完整字段/MJB资格未知，physical_equality_proven=null。112非normal比较分支分为96候选替换和16 G0_old控制；old的intervened/plan_replaced=false，不称112在线干预。

仍并发2、15cold/parent；沿用各阶段timeout与writer/log/cache有限范围。满120参数化时间/IO/存储见RESOURCE_AND_STORAGE_QUOTE.json：拟准入含floor {st['admission_plus_floor_bytes']}B，风险false，未继承Batch2接受。保存容量不是当前quota；实际IO、RSS/VRAM和temp监测缺项保留。dev owner显式task-ordinal-owner映射留待未来冻结，本轮未重算dev。

真实Torch/dlopen/模型/环境/硬件/holder/launcher/claim/训练/安装/删除/大权重hash均0，无新GPU探针提案。原包、原回执、CONTROL/BOARD/dispatch和B不改。交本任务CPU_READY/RESULT后停止，等待分析验收及独立计算release。
''')
print(json.dumps(dict(status='QUOTED_CPU_ONLY',resource_quote=ref(P/'RESOURCE_AND_STORAGE_QUOTE.json'),
    known_hash_read_subtotal=121*known,unknown_size_visits=len(unknown),init_physics=proposal['resource_caps']['initialization_physics_substeps'],
    init_forwards=proposal['resource_caps']['initialization_mj_forward_calls']),ensure_ascii=False))
