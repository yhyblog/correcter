"""Seal this completed command's saved evidence; no runtime or hardware imports."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
B = ROOT / 'Corrector/sim_command/20260919'
TASK = 'A11_COMMON_POOL_FIRST_PARENT_V4'
W = B / 'work/A' / (TASK + '_r1')
OUT = B / 'results/A' / TASK
PREP = B / 'results/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1'
RELEASE = B / 'releases/P11_A_COMMON_POOL_FIRST_PARENT_V4.json'
ACK = B / 'receipts/A' / (TASK + '_ACK.json')
RESULT = B / 'receipts/A' / (TASK + '_RESULT.json')

def read(p):
    return json.loads(Path(p).read_text())

def ref(p):
    p = Path(p)
    return dict(path=str(p), realpath=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), size_bytes=p.stat().st_size)

def write(p, value):
    with Path(p).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    return ref(p)

if __name__ == '__main__':
    outer = read(W / 'OUTER_EXECUTION_RESULT.json')
    r = read(RELEASE)
    run = Path(r['paths']['output'])
    summary = read(OUT / 'AUDIT_SUMMARY.json')
    coverage = read(OUT / 'BRANCH_COVERAGE.json')
    ledger = read(OUT / 'INDEPENDENT_LEDGER_AUDIT.json')
    state = read(OUT / 'STATE_AND_COMMITMENT_AUDIT.json')
    labels = read(OUT / 'INDEPENDENT_LABEL_ARITHMETIC.json')
    refs = read(OUT / 'RUNTIME_REFERENCE_AUDIT.json')
    exit_info = read(OUT / 'EXIT_AND_RESTORATION.json')
    storage = read(OUT / 'STORAGE_AUDIT.json')
    visual = read(OUT / 'VISUAL_INSPECTION.json')
    rows = coverage['per_branch']
    units = ledger['totals']['entered']
    checks = dict(command_exit_zero=outer['returncode'] == 0,
        complete_15_outcomes=summary['complete_outcomes'] == 15,
        state_comparisons_14_exact=summary['full_state_verified_branches'] == 14 and summary['full_state_raw_comparisons_equal'],
        all_116_caps=summary['within_all_116_caps'], counts_complete=summary['counts_complete'],
        no_failed_or_incomplete_events=summary['failed_event_count'] == 0 and summary['incomplete_event_count'] == 0,
        references_match=refs['status'] == 'PASS', labels_match=labels['status'] == 'PASS',
        saved_device_and_loader_match=read(OUT / 'DEVICE_AND_STRICT_LOADER_AUDIT.json')['status'] == 'PASS',
        all_child_exit_evidence=exit_info['all_started_children_exit_evidenced'],
        all_child_cleanup_complete=exit_info['all_saved_child_cleanup_complete'],
        holders_8=summary['holder_count_restored'] == 8,
        no_primary_or_cleanup_failure=not summary['primary_and_cleanup_failures'])
    status = 'LIMITED_FIRST_PARENT_COLLECTION_COMPLETE' if all(checks.values()) else 'REVIEW_REQUIRED'
    label_values = {x['label']: dict(target_mask=x['target_mask'], target=x['computed_target'], valid_pair_repeat_ids=x['valid_pair_repeat_ids']) for x in labels['checks']}
    successes = [dict(branch=x['role'], first_success_step=x['controls_returned']) for x in rows if x['success'] == 1]
    pairs = []
    for prefix in ['Q_a0', 'Q_local_plus', 'Q_local_minus', 'G0_old', 'G0_fresh0', 'G0_fresh1', 'G0_fresh2']:
        members = [x for x in rows if x['role'] in [prefix + '_r0', prefix + '_r1']]
        pairs.append(dict(arm=prefix, observed_repeat_ids=[x['repeat'] for x in members],
            both_outcomes_complete=len(members) == 2 and all(x['outcome_complete'] for x in members),
            both_full_state_verified=len(members) == 2 and all(x['full_state_verified'] for x in members)))
    delivery_check = write(OUT / 'DELIVERY_CHECKS.json', dict(status=status, checks=checks, label_values=label_values,
        complete_repeat_pairs=pairs, actual_success_terminals=successes, analysis_acceptance_pending=True))
    lines = [f'# {TASK}', '',
        f"状态：{status}，待分析验收关闭。唯一正式命令/claim 各 1；原始退出码 {outer['returncode']}，墙钟 {outer['elapsed_seconds']:.3f}s。",
        f"实际启动 {summary['started_attempts']}/15 个分支，完整终局 {summary['complete_outcomes']}；其中到达绝对 s300 共 {summary['s300_outcomes']} 个，其余合法成功提前终局见表。",
        f"实际采样 {units['vla_sampling_calls']}/453、flow {units['flow_forward_calls']}/4530、控制 {units['env_steps']}/4500、观测 {units['observation_calls']}/4515。116 项上限核对：{checks['all_116_caps']}。",
        f"模型初始化 {units['model_initializations']}、语言前向 {units['language_embedding_forwards']}、视觉编码 {units['visual_encoder_forwards']}；native reset {units['environment_reset_calls']}（初始化 {units['initialization_reset_calls']}＋诊断 {units['diagnostic_reset_calls']}），reset_model {units['reset_model_calls']}，初始化物理子步 {units['initialization_physics_substeps']}、策略物理子步 {units['policy_physics_substeps']}。",
        '', '|分支|控制步|终局 success|cut5|承诺步/丢弃尾部|恢复 H10|状态比较|',
        '|---|---:|---:|---|---|---|---|']
    for x in rows:
        suffix = '不适用：normal' if x['role'] == 'normal' else str(x['H10_suffix_resumed'])
        lines.append(f"|{x['role']}|{x['controls_returned']}|{x['success']}|{x['legal_cut_reached']}|{x['commitment_steps_returned']}/{x['discarded_raw_tail']}|{suffix}|{x['restore_level']}|")
    lines.extend(['',
        f"14 份 cut 比较的原始捕获字段和 MJB 独立复核：{summary['full_state_raw_comparisons_equal']}；资格仅限冻结完整性合同的捕获字段，physical_equality_proven 保留 null。单终局、双 repeat 与标签资格分别保存在 BRANCH_COVERAGE、STATE_AND_COMMITMENT_AUDIT、INDEPENDENT_LABEL_ARITHMETIC。",
        '配对标签：' + json.dumps(label_values, ensure_ascii=False) + '。这是单一计划父源的标签，不是方法成功率、排名或 G0 在线触发有效性。',
        f"父/子私有账本共 {summary['private_ledger_scope_count']} 个作用域，entered/returned/failed/incomplete 事件数为 {summary['entered_event_count']}/{summary['returned_event_count']}/{summary['failed_event_count']}/{summary['incomplete_event_count']}。只合计操作向量，不拼接公共 UUID 事件账本。Q/D/G0 前向、梯度、训练、重试、删除均按完整计数表记录。",
        f"存储实际保留 {storage['runtime_file_paths']} 个路径、{storage['unique_inodes']} 个唯一 inode，唯一 inode 内容 {storage['unique_inode_payload_bytes']} B；保留 .partial 硬链接别名。既有 quota、共享缓存/原生路径外写入、unlinked、扫描超调及 RSS 上界未知，不改作整批存储准入。",
        f"整组退出及清理见 EXIT_AND_RESTORATION；launcher 保存的恢复证据为 {summary['holder_count_restored']}/8 holder。成功 handoff 原始 poll 数仍为 {exit_info['successful_handoff_raw_poll_count']}；manager 日志时间不能替代该计数，墙钟不冒充 GPU 秒。",
        'RGB 仅从已有 PPM 做 CPU 无损 PNG 查看，像素比较及目视记录另存；未新增 render。源/seed/设备与 PROPOSED 嵌套身份保持冻结内容。V3 已执行关闭，V4 是新一次机会；旧 11 份计算 release 未复用。',
        'B 未参与。没有安装、重启、删除、自动补采或后续训练/评测；本次剩余额度不可复用，停止等待分析验收和关闭。', ''])
    with (OUT / 'REPORT.md').open('x') as f:
        f.write('\n'.join(lines))
    # Reuse the sealed current-run SHA inventory; do not hash model assets again.
    runtime_rows = read(OUT / 'RUNTIME_FILE_MANIFEST.json')['files']
    files = {x['path']: x for x in runtime_rows}
    for directory in [OUT, W]:
        for p in directory.rglob('*'):
            if p.is_file():
                files[str(p)] = ref(p)
    for p in [ACK, RELEASE, B / 'tasks' / (TASK + '.md'),
              Path(r['paths']['claim']), Path(r['paths']['command_record']),
              PREP / 'proposal/PROPOSAL.json', PREP / 'config/CONFIG.json',
              PREP / 'INPUT_MANIFEST.json', PREP / 'CODE_MANIFEST.json']:
        if p.exists():
            files[str(p)] = ref(p)
    manifest = write(OUT / 'EVIDENCE_MANIFEST.json', dict(schema_version=1, task_id=TASK,
        status='sealed_after_exit_CPU_audit', files=[files[k] for k in sorted(files)], file_count=len(files),
        raw_runtime_files=len(runtime_rows), retains_partial_hardlink_alias_paths=True,
        runtime_SHA_rows_reused_from_independent_audit=True, large_weight_rehash=False,
        excludes=['manifest itself', 'RESULT to avoid reference cycle', 'later delivery verification and queue delivery records'],
        scope='this run, saved authorization, selected frozen small input metadata, and postrun CPU audit'))
    artifact_paths = [p for p in sorted(OUT.iterdir()) if p.is_file()]
    artifact_paths.extend([W / 'OUTER_COMMAND_RECORD.json', W / 'OUTER_EXECUTION_RESULT.json', W / 'command.stdout', W / 'command.stderr'])
    for sub in ['launcher/LAUNCH_RESULT.json', 'launcher/PRIVATE_COST_INDEX.json', 'launcher/STORAGE_ADMISSION.json',
                'launcher/LIFECYCLE_REQUESTED.json', 'launcher/NVML_IDENTITY.json', 'launcher/HANDOFF_ENVIRONMENT.json',
                'reserved/WAVE_EXIT.json', 'reserved/PROCESS_GROUP_EXIT.json', 'reserved/PRIVATE_COST_INDEX.json',
                'reserved/ATTEMPT_COVERAGE.json', 'reserved/PAIRED_LABELS.json', 'normal/BANK.json',
                'normal/CUT_REFERENCE.json', 'normal/CUT_STATE.json', 'normal/cut_model.mjb']:
        if (run / sub).exists():
            artifact_paths.append(run / sub)
    artifacts = [files.get(str(p), None) or ref(p) for p in artifact_paths]
    result = dict(campaign_id='corrector-sim-20260919', task_id=TASK, revision=1, owner='A',
        hostname=r['owner_host'], status=status, at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        ACK=ref(ACK), release=ref(RELEASE), claim=ref(r['paths']['claim']), command_record=ref(r['paths']['command_record']),
        command_invocations=1, claim_count=1, raw_exit_code=outer['returncode'], elapsed_seconds=outer['elapsed_seconds'],
        actual_branch_attempts=summary['started_attempts'], actually_started_branches=coverage['actually_started'],
        not_started_branches=[x['role'] for x in rows if not x['started']],
        completed_rollouts=units['completed_rollouts'], legal_cut_count=sum(bool(x['legal_cut_reached']) for x in rows),
        full_state_qualified_attempts=summary['full_state_verified_branches'],
        single_outcome_qualified_attempts=summary['complete_outcomes'],
        absolute_s300_count=summary['s300_outcomes'], legal_early_success_terminals=successes,
        complete_repeat_pairs=pairs, qualified_target_labels=label_values,
        success_rate=None, success_rate_missing_reason='One fixed planned parent; not a method success-rate sample or ranking.',
        per_branch_coverage=rows, state_qualification_scope='Frozen captured-field/MJB closure only; physical_equality_proven remains null.',
        source=r['source'], device=r['device'], identity=r['identity'],
        entered=ledger['totals']['entered'], returned=ledger['totals']['returned'],
        failed=ledger['totals']['failed'], incomplete=ledger['totals']['incomplete'],
        counts_complete=summary['counts_complete'], within_all_116_caps=summary['within_all_116_caps'],
        private_ledger_scopes=summary['private_ledger_scope_count'],
        event_pairs=dict(entered=summary['entered_event_count'], returned=summary['returned_event_count'],
            failed=summary['failed_event_count'], incomplete=summary['incomplete_event_count']),
        public_cost_event_refs=[], public_cost_event_refs_reason='Private collection costs are SHA-indexed separately; no public UUID event bridge.',
        primary_and_cleanup_failures=summary['primary_and_cleanup_failures'],
        cleanup_and_restoration=ref(OUT / 'EXIT_AND_RESTORATION.json'), restored_holder_count=summary['holder_count_restored'],
        successful_handoff_raw_poll_count=exit_info['successful_handoff_raw_poll_count'],
        handoff_missing_reason=exit_info['handoff_missing_reason'],
        timeouts=r['timeouts'], GPU_seconds=None, GPU_seconds_missing_reason='No direct compute-duration measurement.',
        storage_evidence=ref(OUT / 'STORAGE_AUDIT.json'), visual_evidence=ref(OUT / 'VISUAL_INSPECTION.json'),
        report=ref(OUT / 'REPORT.md'), LAUNCH_RESULT=ref(OUT / 'LAUNCH_RESULT.json'),
        evidence_manifest=manifest, artifact_refs=artifacts, delivery_checks=delivery_check,
        release_consumed=True, release_closure_by_analysis_pending=True, remaining_caps_reusable=False,
        automatic_retry=False, old_releases_reused=[], preceding_V3_consumed_closed=True,
        postrun_audit='saved evidence CPU only; no additional model/driver/environment/holder probe',
        shared_installations=0, daemon_restarts=0, training_updates=0, deletions=0, retries=0, B_participated=False,
        public_interface_modified=False, old_packages_and_receipts_modified=False,
        scientific_interpretation='This collector and planned parent execution/data qualification only; no MT50 training completion or online trigger claim.',
        next_action='wait for analysis acceptance and closure; no automatic next parent, training or evaluation')
    result_ref = write(RESULT, result)
    # Verify the small delivery references; runtime bytes were audited once above.
    errors = []
    for x in artifacts + [manifest, ref(ACK), ref(RELEASE)]:
        if ref(x['path'])['sha256'] != x['sha256']:
            errors.append(x['path'])
    delivery = write(W / 'DELIVERY_VERIFICATION.json', dict(status='PASS' if not errors else 'FAILED',
        result=result_ref, manifest=manifest, artifact_refs=len(artifacts), manifest_files=len(files), errors=errors,
        runtime_manifest_count=len(runtime_rows), large_model_rehash=False))
    print(json.dumps(dict(result=result_ref, report=ref(OUT / 'REPORT.md'), manifest=manifest,
        verification=delivery, status=status, checks=checks, label_values=label_values), ensure_ascii=False))
