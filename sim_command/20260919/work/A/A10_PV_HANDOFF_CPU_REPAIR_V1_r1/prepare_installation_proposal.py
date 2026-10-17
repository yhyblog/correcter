"""Generate exact future install/rollback proposals, without executing them."""
import json
from pathlib import Path
import hashlib

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1'
W=B/'work/A/A10_PV_HANDOFF_CPU_REPAIR_V1_r1'
identity=json.loads((P/'guard_patch/PATCH_IDENTITY.json').read_text())
spec=json.loads((P/'guard_patch/HANDOFF_SPEC.json').read_text())

def put(path,obj):
    with path.open('x') as f:f.write(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def ref(path):
    raw=path.read_bytes();return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))

script=P/'commands/transition_guard_file_cpu.py'
for operation,before,after in [('install','original','patched'),('rollback','patched','original')]:
    template=dict(status='UNAUTHORIZED_TEMPLATE',issuer='analysis',kind='single_guard_file_transition_CPU_only',
        release_id='ANALYSIS_ASSIGN_UNIQUE_'+operation.upper()+'_RELEASE',campaign_id='corrector-sim-20260919',
        owner_host='trial-303224955-trialrun-303224955-worker-0',operation=operation,target_path=identity['unique_shared_target'],
        expected_before_sha256=identity[before]['sha256'],expected_after_sha256=identity[after]['sha256'],
        shared_file_replacements=1,daemon_restarts=0,holder_queries_stops=0,GPU_model_or_hardware_calls=0,
        automatic_compute=False,automatic_rollback=False,template_is_authorization=False)
    put(P/'guard_patch'/f'{operation.upper()}_RELEASE_TEMPLATE.json',template)

put(P/'guard_patch/INSTALLATION_PROPOSAL.json',dict(status='prepared_not_authorized_not_installed',unique_shared_write_path=identity['unique_shared_target'],
    original_sha256=identity['original_shared_sha256'],patched_sha256=identity['expected_installed_sha256'],source_before=identity['original'],source_after=identity['patched'],patch=identity['unified_patch'],
    installation_entry=ref(script),install_argv=['/usr/bin/python3','-I','-S','-B',str(script),'--release','ANALYSIS_INSTALL_RELEASE_JSON','--operation','install'],
    rollback_argv=['/usr/bin/python3','-I','-S','-B',str(script),'--release','ANALYSIS_ROLLBACK_RELEASE_JSON','--operation','rollback'],
    required_analysis_CONTROL_fields=dict(mode='prepare',formal_gpu_runs_enabled=False,active_compute_task_ids=[],active_compute_release_id=None,stop_requested=False,active_guard_installation_release='releases/ANALYSIS_ASSIGNED_RELEASE_ID.json',current_compute_limits='all existing numeric limits zero'),
    preconditions=['Separate analysis release with exact target/original/new SHA and released status; not this CPU release or V3 compute template',
        'No active formal wave in analysis CONTROL; no actual GPU/process/lock inspection by installer',
        'Existing regular target has exact before SHA; replacement bytes have exact after SHA',
        'Unique retained private staging directory on same filesystem; compare inode and SHA immediately before atomic replace'],
    operation_scope=dict(shared_replacements=1,private_retained_byte_backup=1,private_replacement_staging=1,formal_lock_acquisitions=0,guard_start_status_calls=0,daemon_restarts=0,holder_queries_stops=0,GPU_queries=0,compute_launches=0,cleanup_deletions=0),
    original_mode_owner_group='preserved on staged file before atomic os.replace',atomic_replacement=True,temporary_shared_sibling_paths=[],
    current_shared_file_installations=0,current_daemon_restarts=0,
    rollback_conditions=['Analysis requests reverting a verified installed patch while CONTROL has no active compute',
        'If any install step fails before replace, do not compute; retain evidence; target should still be original',
        'Rollback requires current target exactly patched SHA and separately released rollback metadata; unexpected drift is refused, not overwritten'],
    rollback_source=identity['original'],automatic_rollback=False,
    existing_daemon_restart_required=False,restart_reason='Unchanged lifecycle active branch invokes a fresh /usr/bin/python gpu_occupancy_guard.py run process. Existing daemon retains loaded functions; guard/query/stop/start/is_running/main bytes unchanged. New run client reads parameter from inherited environment; same formal.lock and child inherited FD remain.',
    compute_requires='Independent V3 release after analysis verifies the installed SHA; real V3 sh never installs or rolls back shared files',
    limitations='CONTROL coordination is a prerequisite, not an OS deployment lock; installation must be serialized by analysis. No holder state is sampled by this CPU operation.'))

put(P/'guard_patch/HANDOFF_OPERATION_QUOTE.json',dict(status='future_quote_not_measured',timeout_seconds=300,default_seconds=90,
    rationale='8*(15+5)=160 seconds serial stop allowance, plus140 seconds polling and scheduler margin',
    active_guard_path='frozen sh export300 -> launcher environment validation -> unchanged child_environment inheritance -> existing lifecycle active branch -> fresh guard run client parser',
    same_formal_lock='/tmp/gpu_occupancy_guard/formal.lock',nested_reservations=0,unlock_and_reacquire_windows=0,
    poll_calls_per_iteration=1,extra_observation_queries=0,nominal_max_run_client_query_attempts=300,nominal_max_default_query_attempts=90,
    query_implementation_unchanged='one existing nvidia-smi --query-compute-apps=pid; check_output timeout15s; failure propagated',
    bounded_failure_record=dict(records_max=1,retained_observations_max=1,NVML_host_PID_rows_max=64,exception_message_chars_max=2048,missing_observation=None),
    exact_poll_count='Future failure JSON poll_attempts includes raised query attempts; on success count is not additionally instrumented or inferred as measured',
    accounting='Existing guard run-client polling is separate lifecycle work, not native_nvml_identity_queries (parent1+child1). Persistent daemon polling/holder work also separate. Numeric/auxiliary66 caps unchanged.',
    deadline='Checked before and after each query; an empty result at/after deadline cannot start child. Already-entered query and OS scheduling may overrun nominal wall deadline; no end-to-end hard cap promised.',
    excluded_from_300_seconds=['formal.lock acquisition','unchanged child1800+30 timeout','entire child process-group exit drain','reservation release and holder restoration'],
    installed_guard_verification='Existing full input+external checks use only patched SHA for shared target; no extra model hash pass or hardware probe added',
    extra_runtime_CPU_operations=['bounded environment/spec string checks before parent NVML and in child environment construction','one handoff_environment.json metadata write','new guard parameter parse','one bounded failure JSON only on handoff failure'],
    current_actual_run_client_calls=0,current_installations=0))

usage=f'''当前仅为CPU准备；共享文件仍为原SHA，本包未安装、未运行guard或V3。未来安装与回退均需分析单独发布明确授权，且CONTROL无活动计算波次。不得执行UNAUTHORIZED_TEMPLATE。

唯一允许替换的共享路径：`{identity['unique_shared_target']}`。
原SHA256：`{identity['original_shared_sha256']}`。
新SHA256：`{identity['expected_installed_sha256']}`。
原始回退字节：`{identity['original']['path']}`。
补丁：`{identity['unified_patch']['path']}`；候选完整源码：`{identity['patched']['path']}`。

未来安装命令（用分析独立发布的release路径替换参数）：

```sh
/usr/bin/python3 -I -S -B {script} --release ANALYSIS_INSTALL_RELEASE_JSON --operation install
```

未来回退命令（另一个单独授权release，当前文件必须恰为新SHA）：

```sh
/usr/bin/python3 -I -S -B {script} --release ANALYSIS_ROLLBACK_RELEASE_JSON --operation rollback
```

release字段来自 INSTALL_RELEASE_TEMPLATE / ROLLBACK_RELEASE_TEMPLATE。分析须同时在CONTROL发布active_guard_installation_release对应路径，保持prepare/全部计算0/active_compute空；实际操作先检查host、release、closure、原新字节SHA和原文件inode，再在独立保留的work/A/guard_file_transitions/RELEASE_ID内暂存、保存原字节，保留mode/uid/gid，原子替换唯一共享目标。无共享兄弟临时路径，无formal.lock操作，无GPU查询、guard调用、daemon重启或自动计算。当前只做AST/纯元数据fixture，不执行安装入口。

安装前发现漂移则拒绝；安装后SHA核对失败则停止、保留证据并报告。回退须由分析决定并另行授权，当前目标恰为已知新SHA才允许恢复原字节；未知漂移不强制覆盖。未安装或回退后，V3运行入口完整SHA检查会拒绝，不能静默使用90秒。

无需重启现有daemon：原lifecycle的active分支会新建`/usr/bin/python gpu_occupancy_guard.py run`客户端，读取已安装文件及新环境参数；daemon的停止逻辑保持字节不变。没有递归调用lifecycle、二次formal.lock预约或释放后重拿。原预约FD传给reserved wrapper，后者在整个组退出前保持FD；失败后既有daemon恢复8holder。

300秒为8×(15+5)=160秒加140秒余量的名义清空等待，不等于诊断1800+30秒或端到端上界，不保证外部进程/驱动问题下成功。GPU_HOLDER_STOP_TIMEOUT_SECONDS仅影响inactive fallback，本方案不使用它。失败记录仅利用最后一次原query返回值（最多64条NVML host PID行），标注查询开始/返回时刻、query尝试数与错误；缺失观测为null，不声称是deadline新增采样，也不把host PID当container holder manager PID。
'''
with (P/'guard_patch/INSTALL_AND_ROLLBACK.md').open('x') as f:f.write(usage)
print(json.dumps(dict(status='installation_and_rollback_proposed_only',original=identity['original_shared_sha256'],patched=identity['expected_installed_sha256'],shared_writes=0),indent=2))
