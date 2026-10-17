"""Package completed calibration evidence; never create a policy selection seal."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
ROOT = BASE/'outputs/native10_training_20260916'
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, v):
    with Path(p).open('x') as s:
        json.dump(v, s, ensure_ascii=False, indent=2, allow_nan=False); s.write('\n')

def run():
    audit = ROOT/'calibration_audits/calibration_v1'
    diag = ROOT/'calibration_diagnostics/calibration_v1'
    independent = ROOT/'calibration_independent_audits/calibration_v1'
    if not (independent/'complete.json').is_file():
        raise RuntimeError('Independent arithmetic receipt not yet complete')
    a, d = read(audit/'result.json'), read(diag/'result.json')
    s = a['statistics']
    protocol = ROOT/'calibration_protocols/calibration_v1'
    c = read(protocol/'config.json')
    control = ROOT/'execution_control/calibration_v1'
    wave = ROOT/'calibration_execution/calibration/calibration_policy_v1/calibration_v1_01'
    cpu = ROOT/'preparation/calibration_postprocess_cpu_20260917_v1'
    out = ROOT/'calibration_handoffs/calibration_v1'
    assert a['status'] == 'passed' and d['status'] == 'complete'
    assert a['selection_proposal']['status'] == 'proposal_only'
    assert a['new_attempts'] == 1156 and a['resource_totals'] == dict(simulator_attempts=46025, training_updates=51200)
    refs = [protocol/'config.json', protocol/'freeze.json', protocol/'authorization_inventory.json',
        Path(c['analysis_ready']['path']), audit/'complete.json', audit/'result.json',
        diag/'complete.json', diag/'result.json', diag/'report.md', diag/'per_source.csv',
        independent/'complete.json', independent/'result.json', cpu/'complete.json', cpu/'result.json',
        ROOT/'preparation/calibration_cpu_20260917_v2/complete.json',
        control/'actual_launch.json', control/'freeze_failure.json', control/'freeze_result.json',
        control/'result.json', control/'gpu_after_wave.json', wave/'launch_result.json',
        ROOT/'execution_control/calibration_postprocess_v1/result.json',
        BASE/'coordination/NATIVE10_CALIBRATION_LAUNCH_EXECUTOR_CHECK.json',
        BASE/'analysis/native10_ready_v12_metadata_fix_publication.json', Path(__file__).resolve()]
    files = {str(p): sha(p) for p in refs}
    params = {key: c[key] for key in ('source_horizon','prefix_horizon','suffix_horizon','control_budget',
        'generated_horizon','gate_threshold','guidance','matching','command_semantics','cpu','seed_namespace')}
    params.update(fixed_critic='A4000', selected_training=c['calibration_collection']['selected_training'],
        critic_member_hashes=c['main_collection']['banks']['calibration_policy_v1']['critic_member_hashes'],
        effective_cut_policy=c['calibration_collection']['effective_cut_policy'],
        physical_arms=s['methods'], replicates=2, planned_sources=100, sources_per_task=20,
        acceptance_rule=c['calibration_collection']['global_acceptance'], bootstrap=s['bootstrap'],
        config_path=str(protocol/'config.json'), config_sha256=files[str(protocol/'config.json')])
    summary = dict(status='completed_calibration_proposal_only', created_utc=datetime.now(timezone.utc).isoformat(),
        schema='native10_calibration_executor_handoff_v1', fixed_critic='A4000', preregistered_primary_method='post',
        planned_sources=100, cut_sources=96, no_cut_sources=4, no_cut_true_successes=2,
        sources_per_task=20, physical_branches=960, logical_outcomes_per_arm=200,
        replacement_captures=0, technical_missing=0, overall=s['overall'], per_task=s['per_task'],
        selection_proposal=a['selection_proposal'], resources=dict(new_simulator_attempts=1156,
            source_capture=100, independent_bank_restore=96, branch_including_restore=960,
            simulator_total=46025, simulator_hard_limit=50000, new_optimizer_updates=0,
            optimizer_total=51200, optimizer_hard_limit=51200, reserve_used=0, shared_reserve_limit=1200),
        audit=dict(path=str(audit), seal_sha256=sha(audit/'complete.json'),
            unique_indexed_artifacts=len(a['artifacts']), suffix_seed_records_checked=a['suffix_seed_records_checked']),
        independent_arithmetic=dict(path=str(independent), seal_sha256=sha(independent/'complete.json')),
        diagnostics=dict(path=str(diag), seal_sha256=sha(diag/'complete.json')),
        quality=d['quality'], cost=d['cost'], runtime=d['runtime'],
        authorization_boundary=dict(corrected_v12_sha256='5cec3558223d18ba9f2b160c478590b8d0ec9b161989f794e6dbcd7983f10138',
            initial_metadata_freeze_failure_consumed_attempts=0, correction_only_two_path_equals_to_fields=True,
            all_163_authorization_references_in_prelaunch_freeze=True,
            old_sealed_artifacts_unchanged=True, selection_seal_created=False,
            heldout_initialization_or_simulation=False, new_training=False),
        limitations=['Calibration governs only a global post on/off proposal; it is not independent heldout success.',
            'The seven source-level intervals are unadjusted; only the preregistered post-R mean controls the proposal.',
            'Two paired suffixes are not independent initial states; no per-state effect confidence claim.',
            'No extra simulation, model prediction, checkpoint selection, Q gate or method changes follow these results.'])
    text = ('# Native10 校准执行交接\n\n'
        '原100个校准主槽全部完成，各任务20个真实不同初态；96个报警源、4个无报警共同结局（2成功、2失败），完整分母保留。'
        'A4000与post均在校准前固定。post 133/200=66.5%，仅重规划119/200=59.5%；额外+7.0pp，源级95% CI [3.0,12.0]，救回15/损害1，正/负/零源9/0/91。'
        '按冻结的mean(P−R)>0规则仅生成启用post提案，未封存部署选择，未初始化或运行held。校准幅度达到约5pp目标，但不是独立验证成功。\n\n'
        '全轨迹、scene、原槽/替补、实际A4000、raw映射/同幅及13,872条后缀种子记录审计通过；6,356项文件入索引。'
        '没有技术缺失、重试、初始化替补或新增优化。五臂总率46/59.5/61/58/66.5%；七比较及逐任务/逐源在完整报告中。'
        '一条配对损害落在净零源，故源级负源0不等于配对损害0。\n\n'
        '实际计费1156=100capture+96bank+960branch；全局46025/50000sim、51200/51200opt，技术储备0/1200。'
        'lifecycle墙钟580.12s，8卡holder恢复。新产物约103.20MB逻辑字节。命令XYZ/grip平均RMS .042460/.088905，三纠偏幅度匹配；'
        '无raw别名、clip碰撞或同幅失败，5个源grip零通道，未丢源。Q相关仅作描述，未增加门槛。\n\n'
        '首个v12元数据freeze因两条历史from/to引用未带path被严格清单拒绝，发生在任何仿真前。分析端仅补path=to重发同v12；'
        '实际启动绑定修正版5cec3558…，163项授权引用的原件与快照全部进入新freeze。原失败证据保留；没有修改旧封存或重跑已完成波次。\n\n'
        f'完整报告：[calibration report]({diag}/report.md)；逐源：[per_source.csv]({diag}/per_source.csv)。\n\n'
        f'审计：`{audit}`，seal `{sha(audit/"complete.json")}`。\n\n'
        f'诊断：`{diag}`，seal `{sha(diag/"complete.json")}`。\n\n'
        f'独立重聚合：`{independent}`，seal `{sha(independent/"complete.json")}`。\n\n'
        '本交接包summary.json含七比较、逐任务、提案与资源；parameters.json含原冻结科学参数；evidence.json列精确SHA。'
        '后续只等分析端对选择封存/held的阶段决定，不重新选模型或校准方法。\n')
    out.mkdir(parents=True, exist_ok=False)
    dump(out/'summary.json', summary); dump(out/'parameters.json', params)
    dump(out/'evidence.json', dict(files=files, role='completed_calibration_evidence_not_deployment_selection'))
    (out/'report.md').write_text(text)
    dump(out/'complete.json', dict(role='native10_calibration_executor_handoff', status='complete',
        files={p.name:sha(p) for p in out.iterdir() if p.is_file()}, selection_seal_created=False, heldout_release=False))
    handoff = BASE/'coordination/NATIVE10_CALIBRATION_EXECUTOR_HANDOFF.md'
    with handoff.open('x') as stream:
        stream.write(text+f'\n交接包：`{out}`；seal `{sha(out/"complete.json")}`。\n')
    receipt = dict(path=str(out), seal_sha256=sha(out/'complete.json'), summary_sha256=sha(out/'summary.json'),
        handoff=str(handoff), handoff_sha256=sha(handoff), selection_seal_created=False)
    dump(ROOT/'execution_control/calibration_postprocess_v1/handoff_receipt.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))

if __name__ == '__main__': run()
