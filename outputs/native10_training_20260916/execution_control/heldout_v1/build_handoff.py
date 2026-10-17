"""Package the single completed heldout wave and fixed-policy assessment."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
ROOT = BASE/'outputs/native10_training_20260916'


def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, value):
    with Path(p).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def run():
    audit = ROOT/'heldout_audits/heldout_v1'
    diag = ROOT/'heldout_diagnostics/heldout_v1'
    independent = ROOT/'heldout_independent_audits/heldout_v1'
    protocol = ROOT/'heldout_protocols/heldout_v1'
    control = ROOT/'execution_control/heldout_v1'
    postprocess = ROOT/'execution_control/heldout_postprocess_v1'
    wave = ROOT/'heldout_execution/heldout/heldout_policy_v1/heldout_v1_01'
    cpu = ROOT/'preparation/heldout_postprocess_cpu_20260917_v1'
    out = ROOT/'heldout_handoffs/heldout_v1'
    for folder in (audit, diag, independent):
        seal = read(folder/'complete.json')
        assert seal['status'] == 'complete'
        for name, digest in seal['files'].items():
            assert sha(folder/name) == digest, name
    a, d, i = read(audit/'result.json'), read(diag/'result.json'), read(independent/'result.json')
    c, runtime = read(protocol/'config.json'), read(control/'result.json')
    assert a['status'] == i['status'] == 'passed' and d['status'] == 'complete'
    assert a['planned_slots'] == 100 and a['technical_missing'] == 0
    s, assessment = a['statistics'], a['primary_assessment']
    for key in ('overall', 'per_task', 'alarm_conditioned', 'no_cut_common_outcomes'):
        assert s[key] == i['statistics'][key]
    assert c['heldout_collection']['fixed_primary_comparison'] == 'post_minus_alarm_replan10'
    selection = c['heldout_collection']['final_selection']
    assert sha(Path(selection['path'])/'complete.json') == selection['seal_sha256']
    assert sha(Path(selection['path'])/'result.json') == selection['result_sha256']
    resources = runtime['resources']
    assert resources['global_totals'] == a['resource_totals']
    holder = read(control/'gpu_after_wave.json')
    assert len(holder['gpus']) == 8 and all(v['state'] == 'holder' for v in holder['gpus'].values())
    inventory = read(protocol/'authorization_inventory.json')
    refs = [protocol/'config.json', protocol/'freeze.json', protocol/'authorization_inventory.json',
        Path(c['analysis_ready']['path']), audit/'complete.json', audit/'result.json',
        diag/'complete.json', diag/'result.json', diag/'report.md', diag/'per_source.csv',
        independent/'complete.json', independent/'result.json', cpu/'complete.json', cpu/'result.json',
        control/'actual_launch.json', control/'freeze_result.json', control/'result.json',
        control/'gpu_after_wave.json', wave/'launch_result.json', postprocess/'result.json',
        Path(selection['path'])/'complete.json', Path(selection['path'])/'result.json',
        BASE/'coordination/NATIVE10_HELDOUT_LAUNCH_EXECUTOR_CHECK.json', Path(__file__).resolve()]
    files = {str(p): sha(p) for p in refs}
    params = {key: c[key] for key in ('source_horizon','prefix_horizon','suffix_horizon','control_budget',
        'generated_horizon','gate_threshold','guidance','matching','command_semantics','cpu','seed_namespace')}
    params.update(fixed_critic='A4000', final_selection=selection,
        selected_training=c['heldout_collection']['selected_training'],
        critic_member_hashes=c['main_collection']['banks']['heldout_policy_v1']['critic_member_hashes'],
        effective_cut_policy=c['heldout_collection']['effective_cut_policy'],
        physical_arms=s['methods'], replicates=4, planned_sources=100, sources_per_task=20,
        primary_comparison=s['primary_comparison'], bootstrap=s['bootstrap'],
        config_path=str(protocol/'config.json'), config_sha256=sha(protocol/'config.json'))
    summary = dict(status='completed_heldout_fixed_policy', created_utc=datetime.now(timezone.utc).isoformat(),
        schema='native10_heldout_executor_handoff_v1', fixed_critic='A4000', fixed_primary_method='post',
        planned_sources=100, cut_sources=a['reached_sources'], no_cut_sources=a['no_cut_sources'],
        no_cut_true_successes=sum(x['no_cut'] and x['common_outcome'] for x in a['per_source']),
        sources_per_task=20, physical_branches=a['physical_branches'], logical_outcomes_per_arm=400,
        technical_missing=0, overall=s['overall'], per_task=s['per_task'],
        primary_assessment=assessment, scene_audit=a['scene_audit'], resources=resources,
        audit=dict(path=str(audit), seal_sha256=sha(audit/'complete.json'),
            unique_indexed_artifacts=len(a['artifacts']), suffix_seed_records_checked=a['suffix_seed_records_checked']),
        independent_arithmetic=dict(path=str(independent), seal_sha256=sha(independent/'complete.json')),
        diagnostics=dict(path=str(diag), seal_sha256=sha(diag/'complete.json')),
        quality=d['quality'], cost=d['cost'], runtime=d['runtime'],
        authorization_boundary=dict(ready_version=14, ready_sha256=c['analysis_ready']['sha256'],
            authorization_reference_count=len(inventory['references']),
            original_and_snapshot_references_in_prelaunch_freeze=True,
            old_sealed_artifacts_unchanged=True, fixed_selection_unchanged=True,
            new_training=False, automatic_additional_wave=False, holders_restored=8),
        limitations=s['limitations'])
    main = s['overall']['comparisons']['post_minus_alarm_replan10']
    low, high = main['source_95ci']
    target = '达到' if assessment['point_estimate_target_met'] else '未达到'
    confidence = ('源级95%区间下界大于0，支持正向增益。' if assessment['ci_supports_positive_gain']
                  else '源级95%区间未排除0，尚不能确认稳定正增益，也不能据此证明严格无效。')
    text = ('# Native10 最终 heldout 执行交接\n\n'
        f'固定A4000 + matched-post在独立held100上相对仅重规划提升 **{100*main["gain"]:+.2f}个百分点**，'
        f'源级95% CI [{100*low:.2f}, {100*high:.2f}]；救回{main["rescues"]}/损害{main["harms"]}个配对后缀，'
        f'正/负/零源{main["positive_sources"]}/{main["negative_sources"]}/{main["zero_sources"]}。'
        f'点估计{target}预登记的5个百分点目标。{confidence}'
        '点估计达到目标与真实增益至少5个百分点是不同结论，后者不能由此保证。\n\n'
        f'100个原注册主槽全部完成，每任务20个真实不同初态；{a["reached_sources"]}个报警源、'
        f'{a["no_cut_sources"]}个无报警共同结局，全部保留于分母。4次后缀为源内配对，不是400个独立初态。'
        'P−R为唯一预登记主比较，其余六项为次要描述，七项区间未经多比较校正；不合并校准与held。\n\n'
        '| 物理臂 | 成功数/400 | 成功率 |\n|---|---:|---:|\n')
    for name in s['methods']:
        text += f'| {name} | {s["overall"]["success_counts"][name]} | {100*s["overall"]["success_rates"][name]:.2f}% |\n'
    text += '\n| 配对比较 | 增益pp [95% CI] | 救/害 | 正/负/零源 |\n|---|---:|---:|---:|\n'
    for name, row in s['overall']['comparisons'].items():
        ci = row['source_95ci']
        text += (f'| {name} | {100*row["gain"]:+.2f} [{100*ci[0]:.2f}, {100*ci[1]:.2f}] '
                 f'| {row["rescues"]}/{row["harms"]} | {row["positive_sources"]}/{row["negative_sources"]}/{row["zero_sources"]} |\n')
    text += '\n| 任务（各20源） | N / R / V / D / P 成功率% | P−R pp |\n|---|---:|---:|\n'
    for task, row in s['per_task'].items():
        rates = ' / '.join(f'{100*row["success_rates"][name]:.2f}' for name in s['methods'])
        text += f'| {task} | {rates} | {100*row["comparisons"]["post_minus_alarm_replan10"]["gain"]:+.2f} |\n'
    text += (f'\n全轨迹/初始scene/原槽替补链/实际A4000/raw与同幅/后缀配对/账本审计及独立重聚合通过，'
        f'{len(a["artifacts"])}项文件入索引，{a["suffix_seed_records_checked"]}条后缀种子记录核验。'
        f'held计费{resources["stage"]["simulator_attempts"]}/2200；全局'
        f'{resources["global_totals"]["simulator_attempts"]}/50000仿真、51200/51200更新；'
        f'技术储备使用{resources["technical_reserve"].get("simulator_attempts",0)}/1200。八卡holder已恢复。\n\n'
        '完整matched-post依赖V/D/P及反向、随机方向共同定半径；没有改为post原生幅度或在held后重新选择策略。'
        'Q与真实收益关系只作描述，不据此增加门限或改参数。\n\n'
        f'完整Q/raw/成本与逐任务诊断：[报告]({diag}/report.md)。\n\n'
        f'逐源结果：[per_source.csv]({diag}/per_source.csv)。\n\n'
        f'参数：[parameters.json]({out}/parameters.json)；七比较与资源：[summary.json]({out}/summary.json)。\n\n'
        f'全量审计：`{audit}`，seal `{sha(audit/"complete.json")}`。\n\n'
        f'独立重聚合：`{independent}`，seal `{sha(independent/"complete.json")}`。\n\n'
        '所有结论限定于本批五个固定任务、native10与首次合法报警的一次干预；未追加仿真、补样本或新训练。\n')
    out.mkdir(parents=True, exist_ok=False)
    dump(out/'summary.json', summary); dump(out/'parameters.json', params)
    dump(out/'evidence.json', dict(files=files, role='completed_heldout_evidence'))
    (out/'report.md').write_text(text)
    dump(out/'complete.json', dict(role='native10_heldout_executor_handoff', status='complete',
        files={p.name:sha(p) for p in out.iterdir() if p.is_file()}, automatic_next_stage=False))
    handoff = BASE/'coordination/NATIVE10_HELDOUT_EXECUTOR_HANDOFF.md'
    with handoff.open('x') as stream:
        stream.write(text+f'\n交接包：`{out}`；seal `{sha(out/"complete.json")}`。\n')
    receipt = dict(path=str(out), seal_sha256=sha(out/'complete.json'), summary_sha256=sha(out/'summary.json'),
        handoff=str(handoff), handoff_sha256=sha(handoff))
    dump(postprocess/'handoff_receipt.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__': run()
