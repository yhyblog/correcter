"""Render the completed policy5 evidence as an executor handoff; no model calls."""
import csv
import hashlib
import json
from pathlib import Path
import statistics

P = Path(__file__).resolve().parents[2]
R = P / 'outputs/native10_training_20260916'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(folder):
    seal = read(folder / 'complete.json')
    assert seal['status'] == 'complete'
    for rel, digest in seal['files'].items():
        assert sha(folder / rel) == digest, folder / rel
    return sha(folder / 'complete.json')


def main():
    main_audit = R / 'policy_audits/round1_policy_v1'
    independent = R / 'policy5_independent_audits/round1_policy_v1_independent'
    supplement = R / 'policy5_cost_diagnostics/round1_policy_v1'
    seals = {str(x.relative_to(P)): verify(x) for x in (main_audit, independent, supplement)}
    a, i, c = [read(x / 'result.json') for x in (main_audit, independent, supplement)]
    assert a['status'] == i['status'] == 'passed' and c['status'] == 'complete'
    assert i['primary_audit_comparison']['exact'] is True
    assert a['statistics'] == c['primary_statistics']
    dest = R / 'policy_reports/round1_policy_v1'
    dest.mkdir(parents=True, exist_ok=False)
    wave = R / 'policy5_execution/round1_development_policy/round1_policy_v1/round1_policy_v1_01'
    launch = read(wave / 'launch_result.json')
    workers = [read(q) for q in sorted(wave.glob('workers/worker_*/status.json'))]
    assert len(workers) == 32 and all(x['status'] == 'complete' for x in workers)
    loading = [x['loading_seconds'] for x in workers]
    disk = {}
    for rel in ('banks/round1_policy_v1', 'rollouts/round1_development_policy/round1_policy_v1',
                'collections/round1_development_policy/round1_policy_v1',
                'policy_guard/round1_development_policy/round1_policy_v1',
                'policy5_execution/round1_development_policy/round1_policy_v1/round1_policy_v1_01'):
        files = [x for x in (R / rel).rglob('*') if x.is_file()]
        disk[rel] = dict(files=len(files), logical_bytes=sum(x.stat().st_size for x in files))
    runtime = dict(wave_wall_seconds=launch['wall_seconds_including_lifecycle'],
        first_worker_started_utc=min(x['started_utc'] for x in workers),
        last_worker_finished_utc=max(x['finished_utc'] for x in workers),
        worker_loading_seconds=dict(mean=statistics.mean(loading), median=statistics.median(loading),
                                    minimum=min(loading), maximum=max(loading)),
        disk=disk, disk_total_logical_bytes=sum(x['logical_bytes'] for x in disk.values()),
        disk_excludes_reused_sources_models_and_report=True,
        attempts_per_wave_second=1995 / launch['wall_seconds_including_lifecycle'],
        no_serial_speedup_claim=True)
    (dest / 'runtime.json').write_text(json.dumps(runtime, indent=2) + '\n')
    methods = ['continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post']
    display = dict(zip(methods, ['normal native10', 'replan', 'velocity', 'direct', 'post']))
    with (dest / 'per_source.csv').open('w', newline='') as f:
        fields = ['episode_id', 'task', 'no_cut', 'actual_cut', 'scene_fingerprint'] + methods
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for row in a['per_source']:
            writer.writerow({**{k: row[k] for k in fields[:5]}, **row['success_counts']})
    lines = ['# 首轮 B200 五臂实际开发测评：执行交接', '',
        '本轮技术验收通过。三种纠偏相对仅重规划分别增加 **2.00、2.75、2.50 个百分点**，'
        '尚未达到约 +5pp 目标，三项源级 95% CI 均跨 0。本轮使用参与过选模的开发初态，不能称独立验证成功。', '',
        '固定 B200 四成员、原100个开发 episode（五任务各20个不同物理初态）。95个原cut各生成新bank、五臂各4个配对后缀；'
        '5个无报警源沿用已知共同结局（4成功1失败），每臂总体分母400。无源筛选、capture、替补、失败或重试。', '',
        '## 真实成功率与配对比较', '', '| 方法 | 成功/400 | 成功率 |', '|---|---:|---:|']
    s = a['statistics']
    for m in methods:
        lines.append(f"| {display[m]} | {s['overall']['success_counts'][m]} | {100*s['overall']['success_rates'][m]:.2f}% |")
    lines += ['', '| 比较 | 增益pp | 源级95% CI（pp） | 救回/损害 | 正/负/零源 |', '|---|---:|---|---:|---:|']
    for key, v in s['comparisons'].items():
        x, y = key.split('_minus_'); lo, hi = [100*z for z in v['source_95ci']]
        lines.append(f"| {display[x]} − {display[y]} | {100*v['gain']:+.2f} | [{lo:.2f}, {hi:.2f}] | {v['rescues']}/{v['harms']} | {v['positive_sources']}/{v['negative_sources']}/{v['zero_sources']} |")
    lines += ['', '区间采用固定五任务内整源等权有放回 bootstrap（10,000次，seed=2026091622，NumPy default_rng.choice，percentile95）。'
        '源内4次后缀保持配对，不作为4个独立初态；七项区间未做多比较校正。救回/损害按400对逻辑结局计数，正负零按100个源的平均差计数。', '',
        '| 任务（各20源/80逻辑结局） | normal | replan | velocity | direct | post |', '|---|---:|---:|---:|---:|---:|']
    for task, v in s['per_task'].items():
        lines.append('| ' + task + ' | ' + ' | '.join(f"{100*v['success_rates'][m]:.2f}%" for m in methods) + ' |')
    lines += ['', 'disassemble 的纠偏增益主要在弥补中断重规划造成的损害：normal85%，replan76.25%，三纠偏仍为82.5%–83.75%。'
        'pick-place-wall 的系统提升主要来自重规划；stick-push 的replan已为100%。这些任务差异用于解释结果，不据此改阈值或筛负例。', '',
        '仅95个有cut源（每臂380）时，normal/replan/V/D/P成功数为205/241/249/252/251；'
        '纠偏额外增益为2.11/2.89/2.63pp。全100源分母仍是主要报告口径。逐任务全部七比较与alarm条件分层见补充result.json。', '',
        '## 梯度、实际命令与评分诊断', '',
        '95个bank中a0/V/D/P均为4个不同raw命令组：没有a0别名或仅clip后表示碰撞。'
        'V/D/P最终前10步命令的XYZ及gripper RMS同幅差均小于冻结1e-6容差；raw尾段、mask外恒等及C(raw)映射检查全部通过。'
        'XYZ无零组，gripper有2个零组；79个XYZ组、14个gripper组按既定可行匹配规则缩小。'
        '三臂平均XYZ RMS约0.041884、gripper RMS约0.093956；无guidance fallback、无提前结束导致的不足10步干预prefix。', '',
        '18个源的53/950个原a0夹爪命令超过[-1,1]（最大绝对值1.025901），原raw值保留；评分使用同一C(raw)=clip(raw)映射。'
        '这里只报告本轮命令与表示检查，不将历史有限物理探针扩大为普遍物理等价。', '',
        '| 方法（95个cut） | 平均预测ΔQ | 实测平均Δ成功率 | Q增益与实测Pearson | Q正且真实正/负/零源 |',
        '|---|---:|---:|---:|---:|']
    for m in methods[2:]:
        v = c['q_vs_actual'][m]['all_cut_sources']; t = v['sign_table']
        lines.append(f"| {m} | {v['predicted_gain']['mean']:.5f} | {100*v['actual_gain']['mean']:+.2f}pp | {v['pearson']:.3f} | {t['q_positive_actual_positive']}/{t['q_positive_actual_negative']}/{t['q_positive_actual_zero']} |")
    lines += ['', '三种路径的Q均在95/95源上升，却仍有真实损害；生成候选上的评分幅度与实测收益关系较弱。'
        'direct/post点估计比velocity高0.75/0.50pp，尚不足以把问题单独归因于梯度进入flow的方式。'
        '这些描述更支持继续审查局部收益监督与评分判别能力，但本阶段没有正反/随机新臂，不能宣称已经因果定位为评分方向错误。'
        '不重新选B200，不新增接受阈值或自动挑本轮赢家；下一方法与阶段由分析端判断。', '',
        '## 修复、随机流和部署边界', '',
        '准备期v1留存了新guard缩进错误及30 passed/1 failed日志。后缀测试的合成case缺task/env_seed，'
        '在suffix_seed身份检查中报错，尚未执行索引断言。修复补齐合法身份，保留原采集器index=len(suffix)零基连续语义；'
        '审计拒绝跳号/重复，并核原seed及跨臂同repeat/index噪声。v1→v2另增加原slot lock，不能称仅改测试。'
        'v2为31项通过；最终48项（29guard+14runner+5audit）及另13项prepare通过。旧冻结依赖保持原SHA。', '',
        '实际worker入口为create_policy_collector→collect_existing_slot；manifest绑定原100dev及95旧cut/5共同结局。'
        '新bank由B200重新生成，首分支前核对旧新raw50 a0、base seed、initial-noise hash、mask，并核新bank内部最终raw同幅。'
        '禁止capture、初始化替补和旧guided动作复用；本轮账本仅candidate_restore及branch_including_restore。', '',
        'a0随机流键为designated_a0/episode/cut/index0；后缀为branch_suffix_decision/episode/cut/repeat/decision_index。'
        '方法、critic、bank和worker不进入采样seed。正常臂先完成cut时旧native10队列，干预臂执行新的10步prefix，之后均按native10；'
        '后缀按决策索引配对，不要求绝对采样时刻相同。旧bank seed只作身份参照，主要推断限本轮新五臂，不增oldcritic第六臂。', '',
        '## 审计、资源与成本', '',
        f"主审计通过，独立重聚合通过{i['checks_passed']:,}项检查，100×5×4逐次结局及全部主统计完全一致；24,857条实际后缀seed/noise核对通过。",
        '新增仿真1995=95次独立bank恢复+1900分支（分支内恢复已计入），低于2100阶段上限；累计25474/50000次仿真。'
        '优化累计19200，本阶段及审计均0更新；资源字段由账本分别计数，44674条记录不是44674次仿真。8GPU holder已恢复。', '',
        f"正式波次8GPU×4worker，含lifecycle墙钟{runtime['wave_wall_seconds']:.2f}s（约{runtime['wave_wall_seconds']/60:.2f}分钟）。"
        f"worker模型加载均值{statistics.mean(loading):.2f}s，中位{statistics.median(loading):.2f}s，范围{min(loading):.2f}–{max(loading):.2f}s。",
        '95个bank的均值：restore1.070s、candidate_bank1.387s、generation wall2.493s；generation wall包含restore。'
        '1900分支累计wall13393.184 worker-s，normal/replan/V/D/P每分支均8.281/6.959/6.692/6.648/6.665s。'
        'base采样均0.5174s，V0.4282s、D0.4108s；post记录的0.003262s仅为额外梯度步骤，不能当作完整策略推理成本。'
        '计时受共享base、执行顺序、并发和提前成功长度影响，组件有重叠，不能据此宣称相对串行或4倍加速。', '',
        f"本阶段新增banks/rollouts/collections/guard/wave产物共{runtime['disk_total_logical_bytes']:,}逻辑字节"
        f"（{runtime['disk_total_logical_bytes']/2**20:.2f}MiB；不含复用的原source、模型及本报告）。逐项文件数与字节见runtime.json。", '',
        '## 复现与精确身份', '',
        '正式GPU命令已归档于preparation/policy5_execution_v1/command.sh；该命令是执行证据，已完成输出不可重复覆盖。'
        '只读重聚合命令见preparation/policy5_audit_execution_v1/command.json，输出须使用新的空目录。'
        '独立重聚合脚本policy5_independent_audit_v1.py，补充脚本policy5_cost_diagnostic_v1.py，报告脚本policy5_delivery_report_v1.py均位于experiments/native10_training_20260916。', '',
        '| 产物（均在工作流outputs下） | SHA256 |', '|---|---|']
    links = ['policy_protocols/round1_policy_v1/config.json','policy_protocols/round1_policy_v1/freeze.json',
        'models/round1/round1_fit_v1/selected/complete.json','models/round1/round1_fit_v1/selected_reload_audit.json',
        'preparation/policy5_inputs_v1/complete.json','preparation/policy5_runner_cpu_20260916_v1/complete.json',
        'preparation/policy5_prepare_cpu_20260916_v1/complete.json','policy_audits/round1_policy_v1/complete.json',
        'policy5_independent_audits/round1_policy_v1_independent/complete.json','policy5_cost_diagnostics/round1_policy_v1/complete.json',
        'preparation/policy5_execution_v1/complete.json','preparation/policy5_audit_execution_v1/complete.json']
    for rel in links:
        lines.append(f'| [{rel}]({R / rel}) | `{sha(R / rel)}` |')
    lines += ['', '参数以冻结config.json为准：G0=0.05；native执行horizon10、生成50；总控制上限300；'
        'flow alpha10、时刻0.3/0.2/0.1；可行mask边界余量0.05；XYZ RMS目标0.05/L∞上限0.15，'
        'gripper RMS目标0.1/L∞上限0.4，matched容差1e-6。保持原真实clamp导数及接受语义，无新增Q阈值。', '',
        '本报告记录已经完成的一次开发测评。round2、cal、held未自动启动，保留全量负结果与异常证据；下一阶段等待分析端按现有协作授权发布明确协议。', '']
    (dest / 'report.md').write_text('\n'.join(lines))
    binding = dict(input_seals=seals, report_script_sha256=sha(Path(__file__)), simulator_attempts=0,
                   optimizer_updates=0, models_loaded=0, independent_validation_success=False)
    (dest / 'provenance.json').write_text(json.dumps(binding, indent=2) + '\n')
    files = {x.name: sha(x) for x in sorted(dest.iterdir()) if x.is_file()}
    (dest / 'complete.json').write_text(json.dumps(dict(status='complete', files=files, **binding), indent=2) + '\n')
    print(json.dumps(dict(path=str(dest), seal_sha256=sha(dest / 'complete.json'), runtime=runtime)))


if __name__ == '__main__':
    main()
