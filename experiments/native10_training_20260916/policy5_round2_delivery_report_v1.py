"""Render a completed round2 policy deployment without models or new statistics.

Requires a completed 32-worker wave and sealed complete primary, independent,
and Q/raw/cost audits. Every reported outcome comes from this wave. No historical
policy labels, new confidence intervals, ranking or next-stage launch is used.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
import numpy as np
from . import policy5_round2_cost_diagnostic_v1 as supplement
from .policy5_cost_diagnostic_v1 import ROOT, METHODS, CORRECTIONS, _read, _hash, _seal, _inside, describe

STAGE = 'round2_development_policy'
SCHEMA = 'native10_round2_policy5_delivery_v1'
DISPLAY = dict(zip(METHODS, ['normal native10', 'replan', 'velocity', 'direct', 'post']))


def wave_gate(wave_path, *, root=ROOT):
    """Read technical completion only, before opening any audit outcomes."""
    root, wave = Path(root).resolve(), _inside(wave_path, Path(root)/'policy5_execution'/STAGE)
    launch_path, spec_path = wave/'launch_result.json', wave/'wave_spec.json'
    if not launch_path.is_file():
        raise ValueError('Wait for the whole wave to exit before delivery diagnostics')
    launch, spec = _read(launch_path), _read(spec_path)
    if (launch.get('status') != 'complete' or launch.get('returncode') != 0
            or launch.get('lifecycle_covers_entire_wave') is not True
            or launch.get('hold_idle') is not False
            or spec.get('stage') != STAGE or spec.get('workers') != 32
            or spec.get('original_sources') != 100 or spec.get('expected_branches') != 1900
            or spec.get('expected_candidate_restores') != 95):
        raise ValueError('Require the complete authorized round2 policy wave')
    paths = sorted(wave.glob('workers/worker_*/status.json'))
    if len(paths) != 32:
        raise ValueError('Require all 32 completed workers')
    workers, used, ids = [], {str(launch_path): _hash(launch_path), str(spec_path): _hash(spec_path)}, []
    for path in paths:
        _seal(path.parent, role='guarded_policy5_worker')
        row = _read(path)
        if (row.get('status') != 'complete' or row.get('stage') != STAGE
                or row.get('bank_version') != spec['bank_version'] or row.get('wave_id') != wave.name
                or row.get('workers') != 32 or row.get('missing_slot_ids') != []
                or row.get('source_captures') != 0 or row.get('attempted_replacement_records') != 0
                or row.get('config_sha256') != spec['config_sha256']
                or row.get('freeze_sha256') != spec['freeze_sha256']
                or row.get('completed_slot_records') != len(row.get('assigned_slot_ids', []))
                or row.get('guard_factory') != 'create_policy_collector'
                or row.get('slot_entry') != 'collect_existing_slot'):
            raise ValueError('Worker completion/source identity differs')
        workers.append(row); ids.extend(row['assigned_slot_ids'])
        for name in ('status.json', 'complete.json', 'loaded_critic_identity.json'):
            used[str(path.parent/name)] = _hash(path.parent/name)
    if (len(ids) != 100 or len(set(ids)) != 100 or {r['rank'] for r in workers} != set(range(32))
            or sum(r['actual_branch_count'] for r in workers) != 1900
            or sum(r['no_cut_sources'] for r in workers) != 5):
        raise ValueError('Worker coverage differs from the 100 original source protocol')
    wall = launch.get('wall_seconds_including_lifecycle')
    if isinstance(wall, bool) or not isinstance(wall, (int, float)) or not np.isfinite(wall) or wall <= 0:
        raise ValueError('Invalid wave wall time')
    return dict(launch=launch, spec=spec, workers=workers, episode_ids=ids, inputs=used)


def verify_loaded_metadata(records, config, bank_version):
    """Pure metadata cross-check of all actual selector load receipts."""
    binding=config['policy_deployment']['selected_training']
    selected=str(Path(config['critic_assets']).resolve())
    hashes=config['main_collection']['banks'][bank_version]['critic_member_hashes']
    paths=[str(Path(selected)/f'models/refit/member_{m}/selected.pt') for m in range(4)]
    if len(records)!=32 or set(hashes)!={'0','1','2','3'}:
        raise ValueError('Require 32 loaded four-member critic receipts')
    expected=dict(status='passed',stage=STAGE,selected_assets=selected,
        selected_seal_sha256=binding['selected_seal_sha256'],model_paths=paths,member_hashes=hashes,
        selected_reload_audit_sha256=binding['selected_reload_audit_sha256'],selection=dict(path='A',step=4000),
        optimizer_updates=0,actual_selector_paths=True,checkpoint_file_sha=True,
        frozen_parameter_buffer_versions=True,eval_cpu_no_parameter_grad=True)
    for record in records:
        if any(record.get(key)!=value for key,value in expected.items()):
            raise ValueError('Actual loaded critic metadata differs from selected A4000 export')
    return dict(status='passed',workers=32,selected_assets=selected,member_hashes=hashes,
                selected_seal_sha256=binding['selected_seal_sha256'],selection=dict(path='A',step=4000))


def _fmt(value, digits=3):
    return '未定义/缺失' if value is None else f'{value:.{digits}f}'


def render(a, i, c, runtime, config, bindings):
    """Pure rendering: retain primary statistics, with no extra inference."""
    s, q, cost = a['statistics'], c['quality'], c['cost']
    lines = ['# 第二轮 A4000 五臂实际开发测评：执行交接', '',
        f"产出日期：{datetime.now(timezone.utc).date()}；工作流标识：20260916。", '',
        '主审计与独立重聚合均通过。下表报告本轮完整100个原开发源的真实结果；'
        '这批开发初态参与过选模，结果不能称为独立验证成功。报告不重新选critic、不自动挑纠偏赢家，也不启动下一阶段。', '',
        '固定已选 A4000 四成员，原100个开发episode保留原source、cut及a0随机流。95个cut重新生成bank，'
        '五臂各4个配对后缀；5个无cut源广播原共同结局。整体每臂400个逻辑结局，实际1900个分支。', '',
        '| 方法 | 成功/400 | 成功率 |', '|---|---:|---:|']
    for m in METHODS:
        lines.append(f"| {DISPLAY[m]} | {s['overall']['success_counts'][m]} | {100*s['overall']['success_rates'][m]:.2f}% |")
    lines += ['', '| 比较 | 增益pp | 源级95% CI（pp） | 救回/损害 | 正/负/零源 |', '|---|---:|---|---:|---:|']
    for key, row in s['comparisons'].items():
        x, y = key.split('_minus_'); lo, hi = row['source_95ci']
        lines.append(f"| {DISPLAY[x]} − {DISPLAY[y]} | {100*row['gain']:+.2f} | [{100*lo:.2f}, {100*hi:.2f}] | {row['rescues']}/{row['harms']} | {row['positive_sources']}/{row['negative_sources']}/{row['zero_sources']} |")
    boot = s['bootstrap']
    lines += ['', f"原主统计完整沿用：五任务内整源等权有放回bootstrap，{boot['replicates']:,}次，seed={boot['seed']}，"
        'NumPy default_rng.choice，percentile95。源内4后缀始终配对，不能当作4个独立初态；七项区间未做多比较校正。', '',
        '| 任务 | N | normal | replan | velocity | direct | post | V/D/P 相对replan pp |', '|---|---:|---:|---:|---:|---:|---:|---|']
    for task, row in s['per_task'].items():
        rates = row['success_rates']; deltas='/'.join(f"{100*(rates[m]-rates[METHODS[1]]):+.2f}" for m in CORRECTIONS)
        lines.append('| '+task+f" | {row['sources']} | "+' | '.join(f'{100*rates[m]:.2f}%' for m in METHODS)+' | '+deltas+' |')
    lines += ['', '| 分层 | 源数 | 每臂分母 | normal/replan/V/D/P成功数 |', '|---|---:|---:|---|']
    for key, label in (('alarm_conditioned','有cut'),('no_cut_common_outcomes','无cut共同结局')):
        row=s[key]
        lines.append(f"| {label} | {row['sources']} | {row['logical_outcomes_per_arm']} | "+'/'.join(str(row['success_counts'][m]) for m in METHODS)+' |')
    lines += ['', '| 后缀repeat | normal | replan | velocity | direct | post |', '|---|---:|---:|---:|---:|---:|']
    for repeat, row in c['per_repeat'].items():
        lines.append('| '+repeat+' | '+' | '.join(str(row['success_counts'][m])+'/100' for m in METHODS)+' |')
    lines += ['', '上述repeat分层仅用于检查配对构成，不形成新的独立样本或额外CI。全部100源、逐任务/95个cut的七比较见补充result.json。', '',
        '## Q 与真实增益', '',
        'Q诊断只覆盖有候选的95个cut。5个共同结局不伪造Q、不以0补齐；其真实结局仍保留在100源主分母。'
        '评分固定状态与a0，使用C(raw)=clip(raw)和冻结critic；这里读取生成时保存的Q，不重新运行模型。', '',
        '| 方法（95源） | 平均预测ΔQ | 实测相对replan pp | Pearson / Spearman | Q正且真实正/负/零源 |', '|---|---:|---:|---|---:|']
    for m in CORRECTIONS:
        row=c['q_vs_actual'][m]['all_cut_sources']; sign=row['sign_table']
        lines.append(f"| {m} | {_fmt(row['predicted_gain'].get('mean'),6)} | {100*row['actual_gain']['mean']:+.2f} | {_fmt(row['pearson'])} / {_fmt(row['spearman'])} | {sign['q_positive_actual_positive']}/{sign['q_positive_actual_negative']}/{sign['q_positive_actual_zero']} |")
    lines += ['', 'Q相关性、符号表及逐任务结果是生成候选上的描述；Q上升不等于环境收益。'
        '本轮没有新增反向/随机臂，不能仅凭V/D/P差异把原因唯一归为评分方向或梯度进入flow的方式；不构造跨轮配对或旧critic第六臂。', '',
        '## 最终 raw 命令、mask、别名与 fallback', '',
        f"每bank的raw不同命令组数分布：{json.dumps(q['raw_unique_group_distribution'],ensure_ascii=False)}；"
        f"不同raw仅clip后碰撞源数：{q['clipped_collision_sources']}；最终RMS未匹配源数：{q['unmatched_final_rms_sources']}。", '',
        '| 方法 | XYZ RMS均值 | grip RMS均值 | XYZ/grip零通道源 | raw等于a0源 |', '|---|---:|---:|---:|---:|']
    for m in CORRECTIONS:
        row=c['final_raw_amplitude'][m]; zeros=q['zero_channel_counts'][m]
        lines.append(f"| {m} | {_fmt(row['xyz_rms'].get('mean'),6)} | {_fmt(row['gripper_rms'].get('mean'),6)} | {zeros['xyz']}/{zeros['gripper']} | {q['aliases_of_a0'][m]} |")
    lines += ['', f"raw尾段/mask外/评分映射/cap检查失败计数：`{json.dumps(q['raw_invariant_failure_counts'],sort_keys=True)}`。",
        f"可行匹配组标志：`{json.dumps(q['matching_group_flags'],sort_keys=True)}`。",
        f"fallback原始计数：`{json.dumps(cost['guidance_fallback_counts'],sort_keys=True)}`。",
        f"提前结束导致prefix不足的分支数：`{json.dumps(cost['partial_prefix_branches_by_method'],sort_keys=True)}`。", '',
        '逐源文件保留mask比例、mask外逐位恒等、raw尾段、raw与critic映射、cap、实际执行prefix幅度及每次flow更新。'
        '最终前10命令的同幅约束不限制中间flow查询；匹配允许放大原生方向。原raw超界值按既定语义保留，不从有限物理探针推断普遍clip等价。', '',
        '## 资源与成本', '',
        f"本阶段1995次仿真尝试=95次独立bank恢复+1900分支（分支内恢复已计入），阶段上限2100；0优化更新。"
        f"独立审计时全局分资源计数为 `{json.dumps(i['recorded_resource_totals'],sort_keys=True)}`。",
        f"独立重聚合通过{i['checks_passed']:,}项检查；逐次结局与原主统计完全一致，实际后缀seed/noise核对{i['suffix_seed_records_checked']:,}条。", '',
        f"8GPU×4worker波次墙钟（含lifecycle）{runtime['wave_wall_seconds']:.2f}s；"
        f"worker初始化均值{runtime['worker_loading_seconds']['mean']:.2f}s、中位{runtime['worker_loading_seconds']['median']:.2f}s。"
        '初始化包含输入校验、CUDA及模型加载，不能单独当模型加载时间。32个worker的实际loaded critic身份已逐项对照A4000四成员资产、SHA、strict reload及冻结检查回执。', '',
        '| bank/生成组件 | 记录数 | 缺失 | 均值s | 累计worker-s |', '|---|---:|---:|---:|---:|']
    for key in ('restore_seconds','candidate_bank_seconds','generation_wall_seconds','base_seconds','velocity_seconds','direct_seconds','post_seconds','objective_critic_forward_seconds'):
        row=cost['generation'].get(key,dict(observed=0,missing=95))
        lines.append(f"| {key} | {row['observed']} | {row['missing']} | {_fmt(row.get('mean'),6)} | {_fmt(row.get('sum'),3)} |")
    lines += ['', '| 分支方法 | 恢复均值s | 后缀policy均值s | 环境均值s | 分支wall均值s | 分支wall累计worker-s |', '|---|---:|---:|---:|---:|---:|']
    for m in METHODS:
        row=cost['branches_by_method'][m]
        lines.append('| '+m+' | '+' | '.join(_fmt(row[k].get('mean'),4) for k in ('restore_seconds','policy_seconds','environment_seconds','wall_seconds'))+' | '+_fmt(row['wall_seconds'].get('sum'),3)+' |')
    lines += ['', 'generation wall包含restore；candidate_bank不含source恢复。post秒数只代表额外梯度步骤，'
        '不能当作完整策略推理成本。分支policy_seconds只计执行后缀的策略采样，restore、环境执行、wall分别保留。'
        'environment_seconds也包括source replay的环境步，与restore有重叠；累计worker秒与波次墙钟不同，显存峰值不可相加。共享base、执行顺序、并发、终止长度均影响时间，'
        '本报告不宣称串行对照加速或四倍加速。', '',
        f"新增bank/rollout/collection/guard/wave文件总计{runtime['disk_total_logical_bytes']:,}逻辑字节；不含复用source、模型与本报告。", '',
        '## 随机流与方法边界', '',
        '实际入口为create_policy_collector→collect_existing_slot，原100dev身份不变；禁止capture、替补与复用旧guided动作。'
        '每个新bank在首分支前核旧新raw50 a0、base seed、initial-noise SHA及mask，并核本轮V/D/P最终raw同幅。'
        'a0随机流键为designated_a0/episode/cut/index0；后缀键为branch_suffix_decision/episode/cut/repeat/decision_index。'
        '索引零基连续，方法、critic、bank和worker不进入seed；不要求不同臂的绝对采样时刻相同。', '',
        'normal完成cut时当前native10队列剩余命令；其他臂从cut执行新10步prefix，之后统一native10。'
        '状态、a0固定，仅候选梯度参与引导；评分模型、VLA、D、G0及科学参数以本轮冻结配置为准。', '',
        '参数原样记录：', '```json', json.dumps({k:config.get(k) for k in ('source_horizon','prefix_horizon','suffix_horizon','control_budget','gate_threshold','guidance','matching','command_semantics')},ensure_ascii=False,indent=2), '```', '',
        '## 可复现证据', '', '| 文件 | SHA256 |', '|---|---|']
    for path, digest in bindings.items():
        lines.append(f'| [{Path(path).name}]({path}) | `{digest}` |')
    lines += ['', '完整数据见per_source.csv、runtime.json及cost补充result.json/commands.csv/branch_costs.csv；'
        '保留全部负收益、别名、零组、fallback与缺失计时。阶段完成后不自动开始calibration、heldout、重训练或新部署。', '']
    return '\n'.join(lines)


def run(*, audit_path, independent_path, cost_path, wave_path, output_path, root=ROOT):
    root=Path(root).resolve(); output=_inside(output_path,root/'policy_reports')
    if output.exists(): raise FileExistsError('Report output must be an independent new directory')
    wave=wave_gate(wave_path,root=root)  # Must precede all outcome/audit reads.
    paths=[_inside(p,root) for p in (audit_path,independent_path,cost_path)]
    roles=['native10_policy5_readonly_audit','independent_complete_round2_policy5_reaggregation',supplement.SCHEMA]
    for path,role in zip(paths,roles): _seal(path,role=role)
    a,i,c=[_read(p/'result.json') for p in paths]
    if (a.get('status') != 'passed' or i.get('status') != 'passed' or c.get('status') != 'complete'
            or any(x.get('stage') != STAGE for x in (a,i,c))
            or any(x.get('bank_version') != wave['spec']['bank_version'] for x in (a,i,c))
            or i.get('primary_audit_comparison',{}).get('exact') is not True
            or i['primary_audit_comparison'].get('path') != str(paths[0]/'result.json')
            or i['primary_audit_comparison'].get('sha256') != _hash(paths[0]/'result.json')
            or a['statistics'] != c.get('primary_statistics')
            or c.get('source_denominator') != 100 or c.get('command_q_denominator') != 95
            or c.get('physical_branches') != 1900):
        raise ValueError('Completed audit identities/coverage/statistics differ')
    for key in ('overall','comparisons','per_task','alarm_conditioned','no_cut_common_outcomes'):
        if a['statistics'][key] != i['statistics'][key]: raise ValueError('Independent primary statistics differ')
    used=dict(wave['inputs'])
    for item in c['inputs']:
        if _hash(item['path']) != item['sha256']: raise ValueError('Cost supplement input changed')
        used[item['path']]=item['sha256']
    config_candidates=[Path(p) for p,h in used.items() if Path(p).name=='config.json' and h==c['config_sha256']]
    if len(config_candidates)!=1: raise ValueError('Require unique cost-bound frozen config')
    config_path=config_candidates[0]; config=_read(config_path)
    values=supplement.validate_gate(config,a,a['bank_version'])
    if (set(wave['episode_ids']) != set(row['episode_id'] for row in a['per_source'])
            or wave['spec']['config_sha256'] != _hash(config_path)
            or i['config_sha256'] != _hash(config_path)):
        raise ValueError('Wave/audit source or configuration identity differs')
    for path in paths:
        for name in ('result.json','complete.json'): used[str(path/name)]=_hash(path/name)
    loaded=verify_loaded_metadata([_read(p) for p in used if Path(p).name=='loaded_critic_identity.json'],config,a['bank_version'])
    ledger=root/'budget/attempts.jsonl'; before=_hash(ledger)
    selected=config['policy_deployment']['selected_training']; selected_path=Path(selected['path'])
    if _hash(selected_path/'complete.json')!=selected['seal_sha256'] or _hash(selected_path/'selected/complete.json')!=selected['selected_seal_sha256']:
        raise ValueError('Selected training/model seals changed')
    if _hash(selected_path/'selected_reload_audit.json')!=selected['selected_reload_audit_sha256']:
        raise ValueError('Selected strict reload audit changed')
    for p in (selected_path/'complete.json',selected_path/'selected/complete.json',selected_path/'selected_reload_audit.json'):
        used[str(p)]=_hash(p)
    disk={}; bank=a['bank_version']; stage=STAGE
    for folder in (root/'banks'/bank,root/'rollouts'/stage/bank,root/'collections'/stage/bank,root/'policy_guard'/stage/bank,Path(wave_path)):
        files=[p for p in folder.rglob('*') if p.is_file()]
        disk[str(folder.relative_to(root))]=dict(files=len(files),logical_bytes=sum(p.stat().st_size for p in files))
    runtime=dict(wave_wall_seconds=wave['launch']['wall_seconds_including_lifecycle'],
        first_worker_started_utc=min(r['started_utc'] for r in wave['workers']),
        last_worker_finished_utc=max(r['finished_utc'] for r in wave['workers']),
        worker_loading_seconds=describe(r['loading_seconds'] for r in wave['workers']),actual_loaded_critic=loaded,
        disk=disk,disk_total_logical_bytes=sum(r['logical_bytes'] for r in disk.values()),
        disk_excludes_reused_sources_models_and_report=True,no_serial_speedup_claim=True,
        attempts_per_wave_second=1995/wave['launch']['wall_seconds_including_lifecycle'])
    for module in (__file__,supplement.__file__,supplement.calculations.__file__): used[str(Path(module).resolve())]=_hash(module)
    text=render(a,i,c,runtime,config,used)
    if _hash(ledger)!=before: raise ValueError('Ledger changed during read-only delivery generation')
    output.mkdir(parents=True,exist_ok=False)
    def dump(name,value):
        with (output/name).open('x') as stream: json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    dump('runtime.json',runtime)
    with (output/'report.md').open('x') as stream: stream.write(text)
    with (output/'per_source.csv').open('x',newline='') as stream:
        fields=['episode_id','task','no_cut','actual_cut','scene_fingerprint']+list(METHODS)
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in a['per_source']: writer.writerow({**{k:row[k] for k in fields[:5]},**row['success_counts']})
    provenance=dict(schema=SCHEMA,created_utc=datetime.now(timezone.utc).isoformat(),stage=STAGE,
        bank_version=bank,input_files=used,selected_training=selected,ledger_sha256_before=before,
        ledger_sha256_after=_hash(ledger),simulator_attempts=0,optimizer_updates=0,models_loaded=0,
        pca_calls=0,independent_validation_success=False,cross_round_pairing_claim=False,
        new_statistics_or_selection_rules=False,next_stage_automatically_started=False)
    if provenance['ledger_sha256_after']!=before: raise ValueError('Ledger changed before delivery sealing')
    dump('provenance.json',provenance)
    dump('complete.json',dict(status='complete',role=SCHEMA,files={p.name:_hash(p) for p in sorted(output.iterdir()) if p.is_file()},
        simulator_attempts=0,optimizer_updates=0,model_calls=0))
    return dict(status='complete',path=str(output),seal_sha256=_hash(output/'complete.json'),runtime=runtime)


def self_test():
    import tempfile
    class Checks(unittest.TestCase):
        def fixture(self):
            values=np.zeros((100,5,4),bool); values[:50,0]=True;values[:60,1:]=True
            rows=[dict(episode_id=str(n),task='synthetic',no_cut=n>=95,actual_cut=None if n>=95 else 5,
                paired_outcomes={m:values[n,j].tolist() for j,m in enumerate(METHODS)},
                success_counts=dict(zip(METHODS,values[n].sum(1).tolist()))) for n in range(100)]
            def group(x):
                p=supplement.paired_summary(x)
                return dict(sources=len(x),logical_outcomes_per_arm=4*len(x),success_counts=p['success_counts'],success_rates=p['success_rates'])
            p=supplement.paired_summary(values)
            stats=dict(overall=group(values),per_task={'synthetic':group(values)},alarm_conditioned=group(values[:95]),
                no_cut_common_outcomes=group(values[95:]),bootstrap=dict(replicates=10000,seed=2026091622),
                comparisons={k:dict(v,gain=v['mean_gain'],source_95ci=[0,0]) for k,v in p['comparisons'].items()})
            a=dict(statistics=stats)
            i=dict(recorded_resource_totals={'simulator_attempts':123,'training_updates':456},checks_passed=789,suffix_seed_records_checked=1001)
            quality=dict(raw_unique_group_distribution={'4':95},clipped_collision_sources=0,unmatched_final_rms_sources=0,
                zero_channel_counts={m:dict(xyz=0,gripper=0) for m in CORRECTIONS},aliases_of_a0=dict.fromkeys(CORRECTIONS,0),
                matching_group_flags={},raw_invariant_failure_counts={})
            c=dict(quality=quality,per_repeat={str(r):dict(success_counts=dict(zip(METHODS,values[:,:,r].sum(0).tolist()))) for r in range(4)},
                q_vs_actual={m:dict(all_cut_sources=supplement.association([0]*95,[0]*95)) for m in CORRECTIONS},
                final_raw_amplitude={m:{k:describe([.03]) for k in ('xyz_rms','gripper_rms')} for m in CORRECTIONS},
                cost=dict(generation={},guidance_fallback_counts={},partial_prefix_branches_by_method={},
                    branches_by_method={m:{k:describe([1]) for k in ('restore_seconds','policy_seconds','environment_seconds','wall_seconds')} for m in METHODS}))
            runtime=dict(wave_wall_seconds=100,worker_loading_seconds=describe([1,2]),disk_total_logical_bytes=222)
            return a,i,c,runtime
        def test_render_reads_this_wave_values(self):
            a,i,c,r=self.fixture(); text=render(a,i,c,r,{}, {})
            self.assertIn('| normal native10 | 200 | 50.00% |',text)
            self.assertIn('| replan | 240 | 60.00% |',text)
            self.assertIn('789项检查',text)
            self.assertNotIn('B200',text)
            self.assertIn('未定义/缺失',text)
        def test_render_does_not_read_files(self):
            from unittest.mock import patch
            a,i,c,r=self.fixture()
            with patch.object(Path,'read_text',side_effect=AssertionError('No I/O in rendering')):
                text=render(a,i,c,r,{}, {})
            self.assertIn('不能称为独立验证成功',text)
        def test_actual_loaded_metadata(self):
            config=dict(critic_assets='/synthetic/selected',policy_deployment=dict(selected_training=dict(
                selected_seal_sha256='s',selected_reload_audit_sha256='r')),
                main_collection=dict(banks={'v':dict(critic_member_hashes={str(m):str(m) for m in range(4)})}))
            row=dict(status='passed',stage=STAGE,selected_assets='/synthetic/selected',selected_seal_sha256='s',
                selected_reload_audit_sha256='r',model_paths=[f'/synthetic/selected/models/refit/member_{m}/selected.pt' for m in range(4)],
                member_hashes={str(m):str(m) for m in range(4)},selection=dict(path='A',step=4000),optimizer_updates=0,
                actual_selector_paths=True,checkpoint_file_sha=True,frozen_parameter_buffer_versions=True,eval_cpu_no_parameter_grad=True)
            self.assertEqual(verify_loaded_metadata([row]*32,config,'v')['workers'],32)
            row=dict(row,selection=dict(path='B',step=200))
            with self.assertRaises(ValueError): verify_loaded_metadata([row]*32,config,'v')
        def test_running_wave_rejected_before_audits(self):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                with self.assertRaisesRegex(ValueError,'whole wave'):
                    run(audit_path=root/'absent',independent_path=root/'absent2',cost_path=root/'absent3',
                        wave_path=root/'policy5_execution'/STAGE/'b'/'w',output_path=root/'policy_reports'/'v',root=root)
        def test_failed_launch_rejected(self):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);wave=root/'policy5_execution'/STAGE/'b'/'w';wave.mkdir(parents=True)
                (wave/'launch_result.json').write_text(json.dumps(dict(status='failed',returncode=1)))
                (wave/'wave_spec.json').write_text('{}')
                with self.assertRaisesRegex(ValueError,'complete authorized'): wave_gate(wave,root=root)
        def test_old_stage_path_rejected(self):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                with self.assertRaises(ValueError): wave_gate(root/'policy5_execution/round1_development_policy/b/w',root=root)
        def test_undefined_correlation_not_faked_zero(self):
            self.assertEqual(_fmt(None),'未定义/缺失');self.assertEqual(_fmt(0),'0.000')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    if not result.wasSuccessful(): raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('audit','independent','cost','wave','output'): parser.add_argument('--'+name,type=Path)
    parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args();keys=('audit','independent','cost','wave','output')
    if args.self_test:
        if any(getattr(args,k) for k in keys): parser.error('Synthetic checks cannot receive experiment paths')
        self_test();return
    if not all(getattr(args,k) for k in keys): parser.error('All five input/output paths are required')
    result=run(**{k+'_path':getattr(args,k) for k in keys},root=args.root)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__': main()
