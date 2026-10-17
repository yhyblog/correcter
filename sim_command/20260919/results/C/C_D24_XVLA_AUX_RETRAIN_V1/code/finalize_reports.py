"""CPU-only terminal reporting correction: session-wide encoder costs and caveats."""
from collections import Counter
from pathlib import Path
import csv,json
from paths import ROOT
from qio import read,atomic_json,new_json,utc

def update():
    path=ROOT/'FINAL_SUMMARY.json';summary=read(path)
    backup=ROOT/'evidence/FINAL_SUMMARY_BEFORE_COST_AUDIT.json'
    if not backup.exists():new_json(backup,summary)
    phases={}
    for phase in ['collect','evaluate']:
        counts=Counter();meters=Counter();entered=Counter();returned=Counter();external=[];native=[]
        for p in sorted((ROOT/'stages'/phase/'workers').glob('*/encoder/RESULT.json')):
            v=read(p);assert v['status']=='complete' and not v['meter']['failed']
            counts.update(v['counts']);meters.update(v['meter']['seconds']);entered.update(v['meter']['entered']);returned.update(v['meter']['returned'])
            assert v['meter']['entered']==v['meter']['returned'] and not v['meter']['entered'].get('flow_forward_calls',0)
            external.append(dict(worker=p.parents[1].name,parameters=v['identity']['external_model_parameters'],load_seconds=v['identity']['external_encoder_load_seconds'],
                ready_allocated_bytes=v['identity']['external_encoder_allocated_bytes'],peak_allocated_bytes=v['peak_allocated_bytes']))
            ready=read(p.parents[1]/'MODEL_READY.json');end=read(p.parents[1]/'CLIENT_RESULT.json')
            native.append(dict(worker=p.parents[1].name,parameters=ready['base_parameters'],load_seconds=ready['load_seconds'],
                ready_allocated_bytes=ready['base_allocated_bytes'],peak_allocated_bytes=end['peak_allocated_bytes']))
        phases[phase]=dict(worker_count=len(external),counts=dict(counts),meter_entered=dict(entered),meter_returned=dict(returned),meter_seconds=dict(meters),
            external_per_worker=external,native_per_worker=native,phase_wall_seconds=read(ROOT/'stages'/phase/'RESULT.json')['elapsed_seconds'])
    costs=dict(utc=utc(),status='reconciled_from_complete_worker_counters',phases=phases,
        per_arm_language_calls=None,per_arm_language_seconds=None,
        missing_reason='Per-episode counter baseline was captured after begin/instruction encoding. Shared per-worker caches prevent exact arm attribution from those deltas. Complete per-phase calls and times are measured above.',
        external_loaded_parameters_per_worker=4143404816,base_parameters_per_worker=879482456,new_D_G0_Q_parameters=11912530,
        external_visual_submodule_parameters=None,external_visual_submodule_missing_reason='Only total resident external pi05 parameter count was captured; its vision submodule attribute was unavailable.',
        interpretation='4.143B refers to the entire loaded frozen external pi05 model, including unused policy components; it is not a count of parameters active on every feature call.',
        timing='Encoder RPC overlaps guided native inference. Do not add overlapping counters. Eight per-worker load durations are aggregate process time, not wall time; component memory peaks are not simultaneous aggregate peaks.')
    assert phases['collect']['counts']['language_encoder_calls']==231 and phases['evaluate']['counts']['language_encoder_calls']==141
    atomic_json(ROOT/'EXTERNAL_FEATURE_COSTS.json',costs)
    for g in summary['groups']:
        g['external_encoder_and_heads_counters']['language_encoder_calls']=None
        g['external_encoder_and_heads_counters']['language_encoder_seconds']=None
        g['language_cost_missing_reason']=costs['missing_reason']
    summary.update(external_feature_cost_accounting=str(ROOT/'EXTERNAL_FEATURE_COSTS.json'),
        terminal_reporting_fix='Per-arm language costs changed from misleading zero to null plus reason; actual231 collection and141 evaluation calls counted from complete worker records. Scientific outcomes unchanged.',
        interpretation='Complete X-specific adaptation package including new C10 G0 target; revealed500 supplementary adaptation evaluation. All reported paired intervals include zero; Full does not establish improvement over R or N.')
    atomic_json(path,summary)
    paired=read(ROOT/'PAIRED_COMPARISONS.json');data=read(ROOT/'DATA_SUMMARY.json');fit=read(ROOT/'FIT_SUMMARY.json');resource=read(ROOT/'chain/UTILIZATION_SUMMARY.json')
    cells=[]
    for g in summary['groups']:
        p=paired[g['method']+'_vs_N'];cells.append(dict(method=g['method'],successes=g['successes'],valid=g['valid'],success_rate_pct=100*g['success_rate'],
            rescue_vs_N=p['rescued'],harm_vs_N=p['harmed'],delta_vs_N_pp=p['difference_pp'],CI_low_pp=p['task_cluster_bootstrap_95_CI_pp'][0],CI_high_pp=p['task_cluster_bootstrap_95_CI_pp'][1],
            trigger_once=g['trigger_once'],trigger_zero=g['trigger_zero'],policy_calls=g['policy_and_runtime_counters']['policy_queries'],flow_calls=g['policy_and_runtime_counters']['policy_flow_calls'],
            Q_ensemble_calls=g['external_encoder_and_heads_counters'].get('Q_ensemble_forward_calls',0),gradient_calls=g['external_encoder_and_heads_counters'].get('action_gradient_calls',0)))
    with (ROOT/'FINAL_CELLS.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(cells[0]));writer.writeheader();writer.writerows(cells)
    qs=[v for v in fit['members'].values() if v['kind']=='Q'];qstart=[v['history'][0]['development']['L11'] for v in qs];qend=[v['history'][-1]['development']['L11'] for v in qs]
    util=[v['sample_mean_utilization_percent'] for v in resource['GPUs'].values()]
    lines=['X-VLA 专属辅助网络：终局汇总','',
        '250 个固定父源全部完成，共 1,930 次真实采集；10 个父源在切点前终局，其余分支按协议跳过。没有补源或把缺标签填成失败。',
        'D2／G02／Q4 均从头训练至固定 4,000 步，合计 32,000 次更新。底座与外部编码器更新均为 0；Q 每成员全部 7,058 参数参与训练。','',
        '| 方法 | 成功 / 有效 | 相对 N（百分点，95% 配对区间） | 救回 / 损害 | 触发一次 / 零次 |',
        '|---|---:|---:|---:|---:|','| N（复用） | 403 / 500 | — | — | — |']
    for c in cells:lines.append(f"| {c['method']} | {c['successes']} / {c['valid']} | {c['delta_vs_N_pp']:+.1f} [{c['CI_low_pp']:+.1f}, {c['CI_high_pp']:+.1f}] | {c['rescue_vs_N']} / {c['harm_vs_N']} | {c['trigger_once']} / {c['trigger_zero']} |")
    lines+=['','三格都完成 500 回合，无技术失败、未知、未启动或重试。三种方法的首次触发源与切点完全一致。',
        'Post 相对 R 为 −0.4 个百分点，区间 [−1.6, +0.8]；Velocity 相对 R 为 −0.6，区间 [−2.0, +0.6]。所有配对区间均包含零，不能宣称 Full 优于普通重规划或 N。',
        '区间为任务聚类配对 bootstrap，2,000 次，固定 seed20260922。这是已揭晓 500 源上的补充适配评测；头部训练和 G0 的 C10 目标一起改变，不单独归因于某一个头。','',
        '旧冻结 π0.5 辅助网络迁移结果单列：Post 407/500，Velocity 403/500。新专属 Post/Velocity 相对旧对应方法分别 +0.2（区间 −3.8 至 +4.8）、+0.8（−3.4 至 +5.4）个百分点。旧 N／Post／Velocity 均未重跑。','',
        f"G0 有效训练父源 {data['G0_eligible_train_parents']} 个，其中非零收益 {data['G0_nonzero_targets']} 个；Q 可识别增益标签 {data['Q_identifiable_gain_labels']} 个、候选对 {data['Q_identifiable_pairs']} 个。train/dev 独立，PCA/norm 仅来自 train。",
        f"开发集描述：四个 Q 成员的 L11 从第1,000步的 {min(qstart):.3f}–{max(qstart):.3f} 升至固定末步的 {min(qend):.3f}–{max(qend):.3f}，提示泛化有限。保留预定4,000步权重，没有依据开发集或测试结果换 checkpoint。",'',
        '| 方法 | 策略采样 | flow 调用 | Q ensemble / 梯度调用 |', '|---|---:|---:|---:|']
    for c in cells:lines.append(f"| {c['method']} | {c['policy_calls']} | {c['flow_calls']} | {c['Q_ensemble_calls']} / {c['gradient_calls']} |")
    lines+=['',
        '外部编码成本单列：采集阶段视觉调用182,145次、语言231次；评测阶段视觉165,310次、语言141次。每回合差分计数漏掉 begin 时的首次语言编码，故每方法语言成本记为 null；完整 worker 总量已补入 EXTERNAL_FEATURE_COSTS.json，原逐源记录保留。',
        '每 worker 常驻 X-VLA 参数879,482,456，冻结外部 π0.5 总参数4,143,404,816；新 D/G0/Q 合计11,912,530参数。外部数值包含已加载但特征提取时未执行的策略组件，不把它称为活跃视觉子网络参数数。',
        '外部编码器进程峰值分配约8.77 GiB（采集）、8.82 GiB（评测，含新头）。逐 worker 原始显存、加载时间与调用时间见成本文件；RPC与引导采样耗时有重叠，不能相加成墙钟。','',
        f"整波墙钟 {read(ROOT/'RESULT.json')['elapsed_seconds']:.1f} 秒。八卡正式期间 holder 全停；每卡423次采样的平均利用率为 {min(util):.2f}%–{max(util):.2f}%，不能把常驻八卡写成持续高利用率。全部正式后代退出后，原 guard 恢复八卡 holder。",
        '累计 C attempts 为10,443，本任务3,430/4,000。无新基座训练、无成功源重放、无递归唤醒。',
        '', '证据：SOURCE_MANIFEST.json；DATA_SUMMARY.json；FIT_SUMMARY.json；FINAL_EPISODES.csv；PAIRED_COMPARISONS.json；evidence/SCIENTIFIC_TERMINAL_AUDIT.json；evidence/TERMINAL_RUNTIME_AUDIT.json。']
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    return costs

if __name__=='__main__':
    value=update();print(json.dumps(dict(status=value['status'],collection_language_calls=value['phases']['collect']['counts']['language_encoder_calls'],evaluation_language_calls=value['phases']['evaluate']['counts']['language_encoder_calls'])))
