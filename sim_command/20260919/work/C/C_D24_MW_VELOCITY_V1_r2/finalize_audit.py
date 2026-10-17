"""Read durable small results and publish the C terminal audit; never launch work."""
import collections
import csv
import hashlib
import json
import math
from pathlib import Path

import d24_common as d
import velocity_summary as summary


EVENT = 'C_38fec09295ddb4a366b37bbcf237380e'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cfg_path = d.W / 'MW_VELOCITY_BATCH.json'
    cfg = d.load(cfg_path)
    out = d.R / cfg['batch_id']
    state = d.C / 'persistent_queue/nodes/C'
    event_path = state / 'wakeup/outbox' / (EVENT + '.json')
    event = d.load(event_path)
    ident = d.load(d.C / 'nodes/C/identity.json')
    runtime_path = out / 'FINAL_RUNTIME_OBSERVATION.json'
    runtime = d.load(runtime_path)
    result = d.load(out / 'RESULT.json')
    saved = d.load(out / 'SUMMARY.json')
    claim = d.load(out / 'CLAIM.json')
    auth_path = d.C / 'deadline_20260924/C_AUTHORIZATION_V1.json'
    auth = d.load(auth_path)
    assert sha(auth_path) == d.AUTH_SHA
    assert event['event_id'] == EVENT and event['synthetic'] is False
    assert event['hostname'] == runtime['host'] == ident['hostname'] == d.HOST
    assert runtime['boot_id'] == ident['boot_id']
    assert runtime['current_thread'] == event['executor_thread_id'] == ident['executor_thread_id']
    assert sha(event['job']['claim_identity']['path']) == event['job']['claim_identity']['sha256']
    assert sha(cfg_path) == claim['config_sha256']
    assert event['job']['process_identity'] == claim['process'] == d.load(out / 'PROCESS.json')
    assert event['result'] == result
    assert result['status'] == 'complete' and result['exit_code'] == 0
    assert result['all_owned_descendants_exited'] and result['occupancy_handoff_complete']
    assert not any(p['alive'] for p in runtime['formal_identities'])
    assert not runtime['formal_live_group_members'] and not runtime['observer']['alive']
    assert d.load(out / 'DRAIN.json')['remaining'] == {}
    restore = d.load(out / 'OCCUPANCY_RESTORATION_OBSERVED.json')
    assert restore['all8_holder_processes_observed']
    assert result['at_utc'] < restore['at_utc'] < runtime['at_utc']
    assert runtime['guard_snapshot_age_seconds'] < 30
    assert len(runtime['holder_identities']) == 8
    gpu = list(csv.reader(runtime['GPU_sample']['stdout'].splitlines(), skipinitialspace=True))
    apps = list(csv.reader(runtime['GPU_processes']['stdout'].splitlines(), skipinitialspace=True))
    assert runtime['GPU_sample']['returncode'] == runtime['GPU_processes']['returncode'] == 0
    assert {v[0]: v[1] for v in gpu} == {v['index']: v['uuid'] for v in ident['gpus']}
    assert len(apps) == 8
    for i, uuid, *_ in gpu:
        g = runtime['guard']['gpus'][i]
        assert g['state'] == 'holder'
        assert {int(a[1]) for a in apps if a[0] == uuid} == set(g['driver_pids'])

    source_path = Path(auth['source_path'])
    sources = d.load(source_path)['sources']
    expected = {s['source_id']: s for s in sources}
    assert len(sources) == len(expected) == 500
    rows = {k: {} for k in ('smolvla', 'xvla')}
    retry_records, job_checks, current_paths, prior_paths = [], [], set(), set()
    optional = collections.Counter()
    for job in cfg['jobs']:
        jc = d.load(job['config'])
        jp = Path(job['output'])
        kind = job['kind']
        jobclaim = d.load(d.R / 'claims' / (job['job_id'] + '.json'))
        assert sha(job['config']) == jobclaim['config_sha256']
        assert sha(source_path) == jc['source_table_sha256']
        assert d.load(jp / 'CONFIG.json') == jc
        terminal = d.load(jp / 'TERMINAL.json')
        assert terminal == result['jobs'][job['job_id']]
        assert terminal['status'] == 'complete' and terminal['exit_code'] == 0
        assert terminal['all_owned_descendants_exited']
        assert terminal['worker_status']['completed_episodes'] == len(jc['episodes'])
        assert {p.parent.name for p in (jp / 'episodes').glob('*/RESULT.json')} == {s['source_id'] for s in jc['episodes']}
        assert {p.stem for p in (jp / 'episode_claims').glob('*.json')} == {s['source_id'] for s in jc['episodes']}
        for source in jc['episodes']:
            sid = source['source_id']
            assert source == expected[sid] and sid not in rows[kind]
            rp = jp / 'episodes' / sid / 'RESULT.json'
            row = d.load(rp)
            current_paths.add(str(rp))
            rows[kind][sid] = row
            assert all(row[k] == v for k, v in source.items())
            assert row['status'] == 'complete' and type(row['success']) is bool
            for key in ('checkpoint', 'H', 'K', 'NFE', 'action_dim', 'state_dim', 'max_interventions', 'commitment'):
                assert row[key] == jc[key], (kind, sid, key)
            assert row['H'] == (50 if kind == 'smolvla' else 30)
            assert row['K'] == row['NFE'] == row['commitment'] == 10
            assert row['action_dim'] == row['state_dim'] == 4
            assert row['max_interventions'] == 1 and row['interventions'] in (0, 1)
            assert row['action_gradients'] == 3 * row['interventions']
            assert row['flow_calls'] == 10 * row['queries']
            assert row['candidate_queries'] == 2 * row['interventions']
            assert row['queries'] == row['candidate_queries'] + row['natural_queries']
            assert 0 < row['steps'] <= 300
            assert row['env_seed'] == source['reset_seed']
            assert row['physics']['timestep'] == .0025 and row['physics']['frame_skip'] == 5
            assert row['physics']['action_scale'] == .01
            assert row['renderer'] == 'B native Mesa llvmpipe EGL, corner2 480x480'
            for key in ('elapsed_seconds', 'inference_seconds', 'environment_seconds', 'preprocessing_seconds', 'corrector_seconds'):
                assert math.isfinite(row[key]) and row[key] >= 0, (kind, sid, key)
            unit_path = d.R / 'unit_claims' / kind / (sid + '__Velocity__repeat0.json')
            unit = d.load(unit_path)
            assert unit['source'] == source and unit['base'] == kind and unit['method'] == 'Velocity'
            assert unit['repeat'] == 0
            if sid in jc['retry_sources']:
                prior_path = jc['retry_sources'][sid]
                prior = d.load(prior_path)
                prior_paths.add(prior_path)
                assert prior['source_id'] == sid and prior['status'] == 'technical_failure'
                assert prior['success'] is None and prior['steps'] == 0 and 'EGL' in prior['error']
                assert row['attempt'] == 2 and row['retry_of_result'] == prior_path
                assert str(Path(unit['output']) / 'episodes' / sid / 'RESULT.json') == prior_path
                retry_path = d.R / 'unit_retry_claims' / kind / (sid + '__Velocity__repeat0__retry1.json')
                retry = d.load(retry_path)
                assert retry['attempt'] == 2 and retry['source'] == source
                assert retry['retry_of'] == prior_path and retry['original_unit_claim'] == str(unit_path)
                assert retry['output'] == str(jp)
                retry_records.append(dict(base=kind, source_id=sid, original_result=prior_path,
                                          retry_claim=str(retry_path), final_result=str(rp), final_success=row['success']))
            else:
                assert row['attempt'] == 1 and row['retry_of_result'] is None
                assert unit['output'] == str(jp)
            stat_path = rp.with_name('OPTIONAL_STATS.json')
            if stat_path.exists():
                stat = d.load(stat_path)
                optional['present'] += 1
                optional['trajectory_saved'] += bool(stat.get('trajectory_saved'))
                optional['null_top_level_fields'] += sum(v is None for v in stat.values())
            else:
                optional['missing'] += 1
        job_checks.append(dict(job_id=job['job_id'], base=kind, gpu=job['gpus'][0],
                              valid=len(jc['episodes']), status='complete', descendants_exited=True))
    assert len(retry_records) == 8
    assert len(list((d.R / 'unit_retry_claims').glob('*/*.json'))) == 8
    assert len(list((d.R / 'unit_claims').glob('*/*.json'))) == 1000
    all_physical = {str(p) for p in (d.R / 'jobs').glob('*/episodes/*/RESULT.json')}
    assert all_physical == current_paths | prior_paths and len(all_physical) == 1008
    assert len(all_physical) <= auth['max_physical_attempts_C_total']

    nindex = d.load(cfg['baseline_index'])
    postcfg = d.load(cfg['post_batch'])
    n_missing = {}
    for kind, vv in rows.items():
        assert set(vv) == set(expected)
        assert collections.Counter(r['task_id'] for r in vv.values()) == {i: 10 for i in range(50)}
        assert {p.stem.split('__')[0] for p in (d.R / 'unit_claims' / kind).glob('*.json')} == set(expected)
        nn = {r['source_id']: r for r in nindex[kind]}
        pp = summary.read_rows([j for j in postcfg['jobs'] if j['kind'] == kind])
        assert len(nn) == len(nindex[kind]) and set(nn) <= set(expected) and set(pp) == set(expected)
        for old in (nn, pp):
            assert summary.valid(old) == old
            for sid, row in old.items():
                assert all(row[k] == v for k, v in expected[sid].items())
                assert row['checkpoint'] == vv[sid]['checkpoint']
        n_missing[kind] = sorted(set(expected) - set(nn))
        published = next(g for g in saved['groups'] if g['base'] == kind)
        assert published['valid'] == 500 and published['successes'] == sum(r['success'] for r in vv.values())
        assert published['technical_failures'] == published['unknown'] == published['unstarted'] == 0
        assert published['versus_N'] == summary.paired(vv, nn)
        assert published['versus_Post'] == summary.paired(vv, pp)
        for skey, rkey in [('interventions', 'interventions'), ('policy_calls', 'queries'), ('flow_calls', 'flow_calls'),
                          ('action_gradients', 'action_gradients'), ('total_episode_seconds', 'elapsed_seconds'),
                          ('total_base_inference_seconds', 'inference_seconds'), ('total_corrector_seconds', 'corrector_seconds')]:
            assert math.isclose(published[skey], sum(r[rkey] for r in vv.values()), rel_tol=1e-12)

    metrics = [json.loads(line) for line in (out / 'gpu_metrics.jsonl').read_text().splitlines() if line.strip()]
    samples = collections.defaultdict(list)
    guard_states = collections.Counter()
    stale_holder_samples = []
    for m in metrics:
        assert not m['auxiliary_gpus'] and m['exit_code'] == 0
        for i, uuid, util, mem in csv.reader(m['rows'].splitlines(), skipinitialspace=True):
            assert ident['gpus'][int(i)]['uuid'] == uuid
            samples[i].append((float(util), float(mem)))
        states = {g['state'] for g in m['guard']['gpus'].values()}
        guard_states[','.join(sorted(states))] += 1
        if 'holder' in states:
            stale_holder_samples.append(dict(at_utc=m['at_utc'], guard_updated_unix=m['guard']['updated']))
    util_summary = {i: dict(samples=len(v), mean_utilization_pct=sum(u for u, _ in v)/len(v),
                           min_utilization_pct=min(u for u, _ in v), max_utilization_pct=max(u for u, _ in v),
                           max_memory_used_mib=max(mem for _, mem in v)) for i, v in sorted(samples.items())}
    metric_summary = dict(path=str(out / 'gpu_metrics.jsonl'), records=len(metrics), first=metrics[0]['at_utc'],
                          last=metrics[-1]['at_utc'], per_gpu=util_summary, guard_state_sample_counts=dict(guard_states),
                          stale_guard_holder_samples=stale_holder_samples, auxiliary_gpu_samples=0,
                          interpretation='Samples include loading, CPU rendering, gaps and idle tail; not continuous utilization or a controlled speed comparison. Entry NVML contexts were empty; the initial guard JSON was stale.')

    audit_path = d.C / 'receipts/C/events' / (EVENT + '_AUDIT.json')
    report_path = out / 'FINAL_REPORT.md'
    audit = dict(event_id=EVENT, at_utc=d.utc(), status='complete_audited', hostname=d.HOST,
                 boot_id=ident['boot_id'], handler_thread=ident['executor_thread_id'], event_path=str(event_path),
                 event_claim_sha_verified=True, batch_config_sha_verified=True, job_config_sha_verified=True,
                 task_id='C_D24_MW_VELOCITY_V1', batch_id=cfg['batch_id'], jobs=job_checks,
                 scientific_units=1000, valid_final_sources=1000, sources_per_base=500, final_technical_failures=0,
                 final_unknown=0, final_unstarted=0, physical_attempts=1008, preserved_prior_technical_attempts=8,
                 corrected_retries=retry_records, successful_source_replays=0, max_attempts_per_unit=2,
                 development_attempts=0, base_optimizer_updates=0, head_optimizer_updates=0,
                 callback_scientific_launches=0, callback_notifications_created=0,
                 source_identity_seeds_native_dimensions_protocol_and_costs_verified=True,
                 authoritative_results='durable per-episode RESULT.json; no log-derived substitutions',
                 summary_recomputed_matches=True, summary_path=str(out / 'SUMMARY.json'), groups=saved['groups'],
                 N_unavailable_sources=n_missing, optional_stats=dict(optional), runtime_observation=str(runtime_path),
                 all_formal_processes_exited=True, all_formal_process_groups_empty=True, formal_identity_count=26,
                 all8_holders_restored=True, restoration_observed_at_utc=restore['at_utc'],
                 restoration_evidence=str(out / 'OCCUPANCY_RESTORATION_OBSERVED.json'),
                 current_holder_observation_at_utc=runtime['at_utc'], guard_pid=runtime['guard']['pid'],
                 GPU_utilization=metric_summary, batch_elapsed_seconds=result['elapsed_seconds'],
                 method_path=str(d.W / 'METHOD.md'), protocol='B native 80Hz control, .0025 timestep, frame_skip5, action_scale .01; onboarding 30Hz/.015 prose discrepancy retained explicitly',
                 adaptation=saved['adaptation'], transfer=saved['transfer'], cost_note=saved['cost_note'],
                 interpretation='Smol positive point estimates and X neutral/negative estimates; all paired descriptive 95% intervals contain or touch zero. No consistent improvement or equivalence claim.',
                 notification_route=d.load(state / 'wakeup/delivery' / (EVENT + '.json'))['route'],
                 unattended_exec_resume_proven=False,
                 notification_limit='Original interactive queue callback handled here; unlocked-writer headless exec resume remains unproven. No recursive event emitted.',
                 progress_metadata_repair='Observer counted completed models as resident after exit. Preserve its terminal snapshot, set current resident=0 using host process evidence; scientific results and execution code unchanged.',
                 report_path=str(report_path), audit_path=str(audit_path), next_authorized_C_scientific_work=None)

    lines = ['C SmolVLA / X-VLA Velocity：最终结果（2026-09-22 UTC）。两个底座各 500 固定测试源均已完成；N/Post 复用 B 已有结果。', '',
             '| 底座 | N 成功/有效（成功率） | Post 成功/有效（成功率） | Velocity 成功/有效（成功率） | Velocity Wilson 95% CI |',
             '|---|---:|---:|---:|---:|']
    names = {'smolvla': 'SmolVLA 050000', 'xvla': 'X-VLA 030000'}
    for g in saved['groups']:
        lo, hi = g['success_wilson95_pct']
        lines.append(f"| {names[g['base']]} | {g['N_successes']}/{g['N_valid']} ({100*g['N_successes']/g['N_valid']:.2f}%) | {g['Post_successes']}/{g['Post_valid']} ({100*g['Post_successes']/g['Post_valid']:.2f}%) | {g['successes']}/{g['valid']} ({g['success_rate_pct']:.2f}%) | [{lo:.2f}%, {hi:.2f}%] |")
    lines += ['', '| 底座 | 配对比较 | 有效对数 | 由失败变成功 | 由成功变失败 | 成功率差（百分点） | 任务聚类 bootstrap 95% CI（百分点） |',
              '|---|---|---:|---:|---:|---:|---:|']
    for g in saved['groups']:
        for comparator in ('N', 'Post'):
            p = g['versus_' + comparator]
            lo, hi = p['task_cluster_bootstrap_95_ci_pp']
            lines.append(f"| {names[g['base']]} | Velocity − {comparator} | {p['paired_valid']} | {p['rescued']} | {p['harmed']} | {p['difference_pp']:+.2f} | [{lo:+.2f}, {hi:+.2f}] |")
    lines += ['', '配对仅使用同一 source 的有效终局。Smol N 有 4 个未知源，未当作失败，也未补跑；其 496 对中的 Velocity 成功数为 246。差值区间按 50 个任务聚类、2000 次重采样、固定 seed 20260922 计算，为描述性区间，均包含或接触零；不能据此宣称跨底座稳定改善或等效。', '',
              'C 总计 1008 次物理尝试：1000 个唯一测试单元，加 8 次已保留的初始 EGL 技术失败。缺失 XDG_RUNTIME_DIR 导致初始 8 次均在动作 0 前失败；创建 C 私有目录后各重试一次，全部取得有效终局。无成功源重放、无新增开发 rollout、无底座或小模型训练。最终 technical/unknown/unstarted 均为 0。', '',
              '配置为 Smol H50 / X H30、K10、NFE10、G0 > 0.05、最多干预一次、commitment10、alpha10、最后三个原生时间点 0.3/0.2/0.1、自身独立半径。Smol 在原生 Euler velocity 中引导；X 使用原生 clean-prediction remixer 的 velocity 重参数化，保留固定噪声混合器，不能称作 Euler。动作梯度经过各底座自身反归一化和真实 clamp，冻结模型，无 Q 接受筛选。外部 pi05 特征/PCA/D/G0/Q 的训练覆盖仍是历史五任务。', '',
              'C 保留 B 冻结 N/Post 的实际环境：timestep 0.0025、frame_skip 5，即 80Hz 控制 / 400Hz 物理、action_scale 0.01、Mesa llvmpipe EGL、corner2 480×480、300 步上限。启动文案中的 30Hz / 0.015 与已有 B 实验不符，此处明确披露；未为 C 改变环境协议。', '']
    for g in saved['groups']:
        lines.append(f"{names[g['base']]}：干预 {g['interventions']} 次，policy calls {g['policy_calls']}，flow calls {g['flow_calls']}，action gradients {g['action_gradients']}；episode 时间合计 {g['total_episode_seconds']:.2f}s，base inference {g['total_base_inference_seconds']:.2f}s，corrector {g['total_corrector_seconds']:.2f}s。")
    lines += ['', f"C 使用 8 张 H100 80GB，Smol/X 各四路。r2 整批墙钟 {result['elapsed_seconds']:.2f}s（{result['elapsed_seconds']/60:.2f} 分钟），包括加载、交接、CPU 渲染、间隙和末尾空卡时间。base inference 已包含同步梯度 RPC，与 corrector 时间重叠，不能相加。与 B 的跨机器原始耗时不能作为算法加速结论。", '',
              f"正式入口记录 GPU compute contexts 为空；整波未启动辅助 holder，保留单个 formal.lock。{len(metrics)} 个利用率快照已汇总在审计 JSON；初始 guard JSON 尚残留旧 holder 状态，不能据此推断同卡共存，亦不把采样当连续保证。整组正式后代于 {d.load(out/'DRAIN.json')['at_utc']} 已清空；{restore['at_utc']} 观察到八卡占卡恢复，{runtime['at_utc']} 再核对 26 个登记正式进程及所属组全退出、八个原 guard holder 均在运行。占卡不计入科学预算，其 duty 设置不是实测持续利用率。", '',
              '终局通知进入固定原线程 01a0c793-10d2-7791-a250-fd65d88e1ccb。本轮只读核验并发布审计，没有启动科学任务或递归唤醒。queue 路由已有真实原线程处理证据；writer 释放后的 headless exec resume 尚未证实。终局 observer 的 resident 计数沿用了已加载状态，已保留原快照并按进程退出证据更正当前 resident=0。', '',
              f"可追溯产物：[审计]({audit_path})；[数值汇总]({out/'SUMMARY.json'})；[逐任务表]({out/'TASKS.csv'})；[原生适配说明]({d.W/'METHOD.md'})；[本机进程/占卡快照]({runtime_path})。所有原始逐源结果和初始失败均保留。"]

    # Current metadata only; immutable episode rows, claims and prior evidence remain untouched.
    progress_path = state / 'PROGRESS.json'
    progress = d.load(progress_path)
    original_progress = out / 'OBSERVER_TERMINAL_PROGRESS_BEFORE_AUDIT.json'
    if not original_progress.exists():
        d.exclusive(original_progress, progress)
    progress.update(status='complete_audited', at_utc=audit['at_utc'], audit_path=str(audit_path), active_formal_processes=0,
                    all8_holders_restored=True, observer_exited=True, previous_observation=str(original_progress),
                    resident_definition='currently alive model client; verified from FINAL_RUNTIME_OBSERVATION.json')
    for base in progress['bybase'].values():
        base['resident'] = 0
    for j in progress['jobs']:
        for resource in j['resources'].values():
            resource['alive'] = False
    d.atomic(progress_path, progress)
    report_path.write_text('\n'.join(lines) + '\n')
    d.atomic(out / 'FINAL_AUDIT.json', audit)
    d.atomic(audit_path, audit)
    receipt = dict(audit, whole_task_complete=True, groups=saved['groups'])
    d.atomic(d.C / 'receipts/C/C_D24_MW_VELOCITY_V1_RESULT_r3.json', receipt)
    d.atomic(d.C / 'nodes/C/COMPLETION.json', dict(task_id=audit['task_id'], status='complete_audited',
             at_utc=audit['at_utc'], summary_path=str(out / 'SUMMARY.json'), report_path=str(report_path),
             audit_path=str(audit_path), valid_sources=1000, active_formal_processes=0,
             all8_holders_restored=True, guard_pid=runtime['guard']['pid'], new_scientific_work=None))
    ack_path = d.C / 'receipts/C/C_D24_MW_VELOCITY_V1_ACK.json'
    ack = d.load(ack_path)
    if not (out / 'TASK_ACK_BEFORE_FINAL_AUDIT.json').exists():
        d.exclusive(out / 'TASK_ACK_BEFORE_FINAL_AUDIT.json', ack)
    ack.update(status='complete_audited', updated_at_utc=audit['at_utc'], summary_path=str(out / 'SUMMARY.json'),
               report_path=str(report_path), audit_path=str(audit_path), whole_task_complete=True,
               actual_protocol_disclosure=str(d.W / 'METHOD.md'), active_formal_processes=0,
               all8_holders_restored=True, interactive_queue_same_thread_callback_verified=True)
    d.atomic(ack_path, ack)
    print(json.dumps(dict(audit_path=str(audit_path), report_path=str(report_path), valid=1000, physical_attempts=1008,
                          optional_stats=dict(optional), metrics_records=len(metrics), guard_sample_states=dict(guard_states),
                          successes={k: sum(r['success'] for r in v.values()) for k, v in rows.items()})))


if __name__ == '__main__':
    main()
