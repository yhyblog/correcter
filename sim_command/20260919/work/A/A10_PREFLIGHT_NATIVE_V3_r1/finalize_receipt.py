from pathlib import Path
import datetime
import hashlib
import json
import os

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'A10_PREFLIGHT_NATIVE_V3'
W = B/'work/A'/f'{TASK}_r1'
RUN = B/'results/A/P10_launcher_runs/A10_PREFLIGHT_NATIVE_V3_r1_A_wave05'
P = B/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1'
RECEIPTS = B/'receipts/A'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=sha(path), size_bytes=path.stat().st_size)


def publish(path, value, text=False, replace=False):
    path = Path(path)
    assert replace or not path.exists(), 'Immutable final already exists: ' + str(path)
    temp = path.with_name(path.name + '.publish.tmp')
    temp.write_text(value if text else json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


D = Path(read(RUN/'diagnostic_link.json')['path'])
R = read(W/'inputs/releases__P10_A_NATIVE_PREFLIGHT_V3.json')
ACK = read(RECEIPTS/f'{TASK}_ACK.json')
AUDIT = read(W/'FINAL_LEDGER_AUDIT.json')
OUTPUTS = read(W/'SAVED_OUTPUTS_AUDIT.json')
VISUAL = read(W/'RGB_VISUAL_AUDIT.json')
FINAL = read(W/'FINAL_AUDIT.json')
PROPOSAL = read(P/'proposal/PROPOSAL.json')
CHECKS = read(D/'checks.json')
CLAIM = B/'results/A/P10_native_release_claims/P10_A_NATIVE_PREFLIGHT_V3.json'
CACHE = B/'work/A/P10_runtime_cache'/R['run_id']
assert AUDIT['native_preflight_outcome'] == 'complete' and OUTPUTS['status'] == 'saved_output_CPU_checks_passed'
assert FINAL['all_eight_holders_restored'] and FINAL['all_formal_group_members_exited']
finished = datetime.datetime.now(datetime.timezone.utc).isoformat()
report = f'''| 项目 | 实际结果 |
|---|---|
| 本次执行 | 冻结 sh 1 次，退出 0；有限原生工程预检完成，claim/release 已消费，重试 0 |
| 诊断 / 采样 / 控制 | 1 attempt；H=10/20/30/40/50 各 1 native、10 flow，共 5/50；1 真实控制步 /13 子步 |
| 初始化 | 1 模型、2 原生环境+1 wrapper；52 native reset、104 reset_model、5200 settling 调用、26000 初始化子步；全部 entered/returned 一致 |
| graphics | 108 entered /108 returned /0 failed /0 incomplete；35 次 EGL error 均 SUCCESS；EGL/MjrContext 各 1、render/readPixels 各 2 |
| 观测 | 诊断 native reset 返回 1；初态/步后完整观测各 1，可用 NPZ 共 2；与 reset 返回分开计数 |
| 设备与 UUID | 固定 PCI 0000:0f:00.0 / GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe；8 设备映射一致；本次实测原类型 torch._C._CUuuid，真实类 token 匹配，str 1 次，格式/目标均通过 |
| loader / renderer | Torch 绑定后仍为冻结隔离 libcuda.so.535.161.08；GL/EGL vendor 均 NVIDIA；旧 V2 具体对象类型仍未知 |
| 5H 队列 | raw_plans 形状 5×50×4 float32，五组计划逐位相等、noise SHA 相同，首出队后长度 9/19/29/39/49 |
| transition | 真实 step0→1，与当前/next NPZ、首动作及 raw50 引用 SHA 一致；reward=0、success=false、terminal_success=null，完整 rollout=0 |
| RGB 目视 | 红机械臂/木桌/立式木架/蓝方块/绿目标点，前后同视角且有细微变化；符合 shelf-place；待分析目视验收 |
| 清理与 occupancy | cleanup errors=[]；进程组 244701 全部退出后 8 holder 于 20:19:23 UTC 恢复，manager245508–245515，guard27508；无残留正式进程 |
| 未执行 | monitor/critic/反向/更新/训练/完整 rollout/重试/删除均 0；未额外 checker、UUID 探针或 render |

三套账本已独立重算并与 LAUNCH_RESULT 一致；公共事件 63 返回、0 失败/未终结。子进程 218.908 秒，launcher 端到端 306.243 秒（前置13.944、停holder预约63.355、恢复观察10.005秒）；1800+30 只约束子进程。

去除父子重叠的 CUDA event 计时仅覆盖采样测量区间，共 2.480890 秒；全 GPU 利用率积分/总 GPU 秒未知，保留 null。PyTorch allocator 峰值 allocated8.892 / reserved9.217 GiB，不代表设备总显存；CPU 单进程观测 RSS37.987 / HWM39.341 GiB，不是进程树总峰值。

[初态 PNG]({W}/RGB_views/RGB_diagnostic.png) · [步后 PNG]({W}/RGB_views/RGB_post_control.png)；两图仅从已保存像素 CPU 无损编码，NPZ=PPM=PNG 逐像素一致，无裁切/翻转/缩放或新 render。两帧23915像素发生变化；场景判定依据目视，未仅凭非空缓冲。

[LAUNCH_RESULT]({RUN}/LAUNCH_RESULT.json) · [最终审计]({W}/FINAL_AUDIT.json) · [实际计数]({W}/ACTUAL_COUNTS.json) · [保存产物审计]({W}/SAVED_OUTPUTS_AUDIT.json) · [类型与设备证据]({W}/POLICY_UUID_EVIDENCE.json)。原始三账本、两观测、5H计划、transition、loader、cleanup 与 guard 日志均随 RESULT/manifest 保留。

正式运行无失败。CPU 图像审计首版过严拦截 NumPy 的 Python 当前进程句柄初始化，未进入 GPU；保留失败证据后，仅放行该 CPU 句柄的 r2 审计通过，正式重试仍0。全部新缓存/临时证据保留；旧包、旧回执不改。

请分析端验收本次有限工程预检并关闭 P10_A_NATIVE_PREFLIGHT_V3。未用额度不复用；这不是完整 episode 成功率、P/V 数值或 MT50 性能证据。不自动进入其他阶段。
'''
publish(RECEIPTS/f'{TASK}_REPORT.md', report, text=True)
heartbeat = dict(task_id=TASK, task_revision=1, node_role='A', status='complete_receipt_ready',
    started_at_utc=ACK['started_at_utc'], finished_at_utc=finished, updated_at_utc=finished,
    progress=dict(real_sh_invocations=1, release_consumed=True, diagnostic_returncode=0,
        graphics_entered=108, native_sampling_calls=5, flow_forward_calls=50,
        policy_steps=1, RGB_frames=2, restored_holders=8), automatic_retries=0,
    awaiting_analysis_acceptance=True, no_auto_next_stage=True)
publish(RECEIPTS/f'{TASK}_HEARTBEAT.json', heartbeat, replace=True)

files = [f for root in [W, RUN, D, CACHE] if root.exists() for f in root.rglob('*')
         if f.is_file() and f.name not in {'EVIDENCE_MANIFEST.json', 'RETENTION_INVENTORY.json'}]
files += [CLAIM, RECEIPTS/f'{TASK}_ACK.json', RECEIPTS/f'{TASK}_REPORT.md', RECEIPTS/f'{TASK}_HEARTBEAT.json']
files = sorted(set(files))
assert all(f.stat().st_size < 64*1024*1024 and not f.is_symlink() for f in files), 'No extra weight hash or external symlink traversal'
records = [ref(f) for f in files]
retention = dict(task_id=TASK, delete_authorized=False, deletions=0,
    policy='All current-run evidence/cache retained; any delete/keep/defer decision belongs to analysis',
    files=[dict(path=str(f), realpath=str(f.resolve()), size_bytes=f.stat().st_size,
        project='Corrector', reason='Current consumed native V3 run evidence/cache; includes retained completion temp file') for f in files],
    file_count=len(files), total_bytes=sum(record['size_bytes'] for record in records))
publish(W/'RETENTION_INVENTORY.json', retention)
records.append(ref(W/'RETENTION_INVENTORY.json'))
publish(W/'EVIDENCE_MANIFEST.json', dict(task_id=TASK, files=records,
    exclusions=['Manifest itself', 'Final RESULT', 'Post-publication audit and queue delivery appended in same work directory'],
    all_evidence_retained=True, no_model_weights_hashed_in_receipt_audit=True))
artifacts = [RECEIPTS/f'{TASK}_REPORT.md', RUN/'LAUNCH_RESULT.json', RUN/'launch_identity.json',
    RUN/'diagnostic_link.json', RUN/'wave_timing.jsonl', RUN/'process_family_cleanup.json', CLAIM]
artifacts += [D/name for name in ('CLAIM.json', 'COMPLETE.json', 'resource_receipt.json', 'events.jsonl',
    'initialization_receipt.json', 'initialization_events.jsonl', 'graphics_receipt.json', 'graphics_events.jsonl',
    'graphics_api_results.jsonl', 'graphics_cleanup.json', 'observation_events.jsonl', 'policy_device_type.json',
    'policy_device.json', 'device_mapping.json', 'loader_identity.json', 'renderer_identity.json',
    'artifact_status.json', 'checks.json', 'raw_plans.npy', 'transition.json', 'observation_step0.npz',
    'observation_step1.npz', 'RGB_diagnostic.ppm', 'RGB_post_control.ppm', 'RGB_provenance.json')]
artifacts += [W/name for name in ('FINAL_AUDIT.json', 'FINAL_LEDGER_AUDIT.json', 'ACTUAL_COUNTS.json',
    'GRAPHICS_COUNTS.csv', 'POLICY_UUID_EVIDENCE.json', 'ARTIFACT_STATUS_AUDIT.json', 'SAVED_OUTPUTS_AUDIT.json',
    'RGB_VISUAL_AUDIT.json', 'RGB_views/RGB_diagnostic.png', 'RGB_views/RGB_post_control.png',
    'COMMAND_EXIT.json', 'COMMAND_STDOUT_STDERR.log', 'CPU_PROCESS_AND_GUARD_OBSERVATIONS.jsonl',
    'OCCUPANCY_BEFORE.json', 'OCCUPANCY_AFTER_COMMAND.json', 'POST_COMMAND_PROCESSES.json',
    'GUARD_LOG_WINDOW.log', 'CPU_AUDIT_TOOL_FAILURE.json', 'EVIDENCE_MANIFEST.json', 'RETENTION_INVENTORY.json')]
counts = dict(**AUDIT['counts']['public']['counts'], **AUDIT['counts']['initialization']['entered_budget_usage'],
    **AUDIT['counts']['observations'], completed_rollouts=0, gpu_seconds=None,
    GPU_seconds_missing_reason='No device utilization integral; scoped CUDA event timing below is not total GPU time',
    measured_outermost_device_seconds=AUDIT['counts']['measured_outermost_device_seconds'],
    measured_device_scope=AUDIT['counts']['measured_device_scope'],
    real_sh_invocations=1, release_claims=1, native_nvml_identity_queries=2,
    explicit_graphics_entered=108, explicit_graphics_returned=108, explicit_graphics_failed=0,
    explicit_graphics_incomplete=0, graphics_counts=AUDIT['counts']['graphics']['entered_budget_usage'],
    peak_total_GPU_memory_bytes=None, peak_pytorch_allocated_bytes=CHECKS['peak_cuda_allocated_bytes'],
    peak_pytorch_reserved_bytes=CHECKS['peak_cuda_reserved_bytes'],
    observed_peak_process_RSS_KiB=AUDIT['CPU_observation']['peak_observed_per_process_RSS_KiB'],
    observed_peak_process_HWM_KiB=AUDIT['CPU_observation']['peak_observed_per_process_HWM_KiB'],
    CPU_memory_scope='Maximum sampled single matching process, not process-tree sum or guaranteed whole-wave peak',
    CPU_PNG_encodings=2, extra_render_or_RGB_readback_calls=0, extra_CPU_checker_invocations=0,
    extra_GPU_queries_by_observer_or_audit=0, extra_UUID_probes=0, extra_large_weight_hashes=0,
    deletions=0, retries=0, new_evidence_bytes_before_final_receipt=retention['total_bytes'])
result = dict(campaign_id=R['campaign_id'], task_id=TASK, revision=1, task_revision=1, role='A', node_role='A',
    hostname=ACK['hostname'], session_id=ACK['executor_session_id'], status='complete',
    technical_failure=False, receipt_work_complete=True, started_at_utc=ACK['started_at_utc'], finished_at_utc=finished,
    release_id=R['release_id'], run_id=R['run_id'], wave_id=R['wave_id'], shard_id=R['shard_id'],
    input_identity=dict(protocol=ref(W/'inputs/tasks__A10_PREFLIGHT_NATIVE_V3.md'),
        release=ref(W/'inputs/releases__P10_A_NATIVE_PREFLIGHT_V3.json'), CONTROL=ref(W/'inputs/CONTROL.json'),
        TASK_BOARD=ref(W/'inputs/TASK_BOARD.json'), code=ref(P/'code/CODE_MANIFEST.json'),
        config=ref(P/'proposal/PROPOSAL.json'), integration=ref(P/'INTEGRATION_MANIFEST.json'),
        data=ref(P/'proposal/source_manifest.json'), model=dict(path=str(Path(PROPOSAL['checkpoint'])/'model.safetensors'),
            sha256=PROPOSAL['model_sha256'], size_bytes=9354050752, model_loaded=True,
            verification_basis='Both frozen real entry authorization/SHA passes completed; no extra checker or third weight hash')),
    artifacts=[ref(f) for f in artifacts], resource_counts=counts, failures_and_retries=[],
    CPU_audit_tool_recovery=read(W/'CPU_AUDIT_TOOL_FAILURE.json'), formal_compute_retries=0,
    timing=AUDIT['timing'], occupancy=AUDIT['occupancy'], policy_UUID=AUDIT['policy_UUID'],
    saved_output_audit=ref(W/'SAVED_OUTPUTS_AUDIT.json'), RGB_visual_audit=ref(W/'RGB_VISUAL_AUDIT.json'),
    findings=[
        'Exactly one frozen command completed with exit0; one consumed release claim, no retries or other compute stages.',
        'All8 EGL CUDA-handle mappings and fixed PCI/UUID/visibility passed; post-Torch loader remained on frozen535 libcuda.',
        'This run recorded torch._C._CUuuid before conversion, exact trusted class identity, one str conversion, canonical format and strict target match. Old V2 type remains unknown.',
        '1diagnostic/5native/50flow/1control13substeps,52native reset/104reset_model/26000init substeps; all three ledgers independently reconciled.',
        '108explicit graphics entered/returned,0failed/incomplete; one EGL/MJR context,2render/readbacks; cleanup clean.',
        '5x50x4 raw plans bitwise equal with equal measured noise hashes; queue lengths9/19/29/39/49,10flows per sample.',
        'Real one-step transition references both saved observations and the actual first command; reward0,successfalse,terminal_successnull,0fullrollouts.',
        'Two480x480corner2 saved frames visually match shelf-place; NPZ/PPM/CPU-PNG pixels equal with no extra render.',
        'Formal process group fully exited before all8holders restored; guard27508 retained, no matching residual process.',
        'Only scoped CUDA-event timing and PyTorch allocator peaks measured; total GPU-seconds/physical peak unknown. All evidence/cache retained, deletion0.'
    ], blockers=[], next_task_proposal=dict(status='await_analysis_acceptance_and_release_closure',
        scope='Analysis owns next stage; no automatic P/V, collection, training or evaluation',
        compute_authorized_by_this_receipt=False, reuse_current_release=False),
    release_consumed=True, remaining_budget_reusable=False, analysis_closure_requested=True,
    analysis_acceptance_pending=True, formal_task_success_rate_sample=False,
    all_evidence_retained=True, artifact_reference_count=len(artifacts), evidence_manifest_files=len(records))
publish(RECEIPTS/f'{TASK}_RESULT.json', result)
print(json.dumps(dict(RESULT=ref(RECEIPTS/f'{TASK}_RESULT.json'), REPORT=ref(RECEIPTS/f'{TASK}_REPORT.md'),
    LAUNCH_RESULT=ref(RUN/'LAUNCH_RESULT.json'), artifact_references=len(artifacts),
    evidence_manifest_files=len(records), retained_bytes=retention['total_bytes']), ensure_ascii=False, indent=2))
