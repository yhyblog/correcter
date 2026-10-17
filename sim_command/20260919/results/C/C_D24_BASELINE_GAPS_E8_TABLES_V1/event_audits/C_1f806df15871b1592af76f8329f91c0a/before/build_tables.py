"""E8 publication from frozen terminal rows. CPU-only; no scientific launches."""
import csv
import datetime
import importlib.util
import json
import math
from pathlib import Path

import d24_common as d


def csv_write(path, rows):
    with path.open('w', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def wilson(w,n):
    if not n:return (None,None)
    z=1.959963984540054;p=w/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return (100*max(0,center-half),100*min(1,center+half))


def index(rows, path, origin):
    out={}
    for raw in rows:
        r=dict(raw)
        assert r['status']=='complete' and type(r.get('success')) is bool
        assert r['source_id'] not in out
        r['baseline_origin']=origin;r['provenance_path']=str(path)
        out[r['source_id']]=r
    return out


def native_rows(batch_path, kind=None):
    result={}
    for job in d.load(batch_path)['jobs']:
        if kind and job.get('kind')!=kind:continue
        for p in (Path(job['output'])/'episodes').glob('*/RESULT.json'):
            r=d.load(p)
            if r.get('status')!='complete' or type(r.get('success')) is not bool:continue
            assert r['source_id'] not in result
            result[r['source_id']]=dict(r,provenance_path=str(p))
    return result


def main():
    now=d.utc();R=d.R;C=d.C
    b_ext=C/'results/B/B_D24_EXTENSION_REMAINDER_V1/r1'
    mw_summary_path=C/'results/C/C_D24_MW_VELOCITY_V1/D24_C_MW_VELOCITY_r2/SUMMARY.json'
    mw_summary=d.load(mw_summary_path)
    mw_post_path=b_ext/'D24_E8_MW_POST_r1/N_POST_SUMMARY.json'
    mw_post=d.load(mw_post_path)
    mw_ci_path=b_ext/'D24_E8_MW_POST_r1/PAIRED_UNCERTAINTY.json'
    mw_ci=d.load(mw_ci_path)
    lib_post_path=b_ext/'D24_E8_LIBERO_POST_r1/N_POST_SUMMARY.json'
    lib_post=d.load(lib_post_path)
    lib_v_path=b_ext/'D24_E8_LIBERO_VELOCITY_r1/N_POST_VELOCITY_SUMMARY.json'
    lib_v=d.load(lib_v_path)
    assert lib_v['status']=='complete' and lib_v['Velocity_valid']==400
    n_path=C/'work/C/C_D24_MW_VELOCITY_V1_r2/VALID_N_INDEX.json'
    n_input=d.load(n_path)
    lib_n_path=C/'work/B/B_D24_LIBERO_POST_V1_r1/N_VALID_BASELINE.json'
    ns={k:index(n_input[k],n_path,'B_original_valid_N') for k in ('smolvla','xvla')}
    original_lib_n=index(d.load(lib_n_path),lib_n_path,'B_original_valid_N')
    ns['pi05_libero']=dict(original_lib_n)
    assert [len(ns[k]) for k in ('smolvla','xvla','pi05_libero')]==[496,500,394]
    disposition=d.load(R/'N_GAP_DISPOSITION.json')
    cfg=d.load(d.W/'N_GAP_BATCH.json')
    new_valid=[];new_attempts=0
    for gap in disposition['entries']:
        sid=gap['source']['source_id']
        if not gap['eligible_for_C_attempt']:
            gap.update(current_status='unknown',current_success=None,C_attempts=0)
            continue
        job=next(j for j in cfg['jobs'] if d.load(j['config'])['episodes'][0]['source_id']==sid)
        p=Path(job['output'])/'episodes'/sid/'RESULT.json'
        claimed=(R/'unit_claims'/(sid+'__N__corrected1.json')).exists()
        new_attempts+=claimed
        pending_status=('execution_unknown' if (R/cfg['batch_id']/'RESULT.json').exists() else 'running') if claimed else 'pending_authorized'
        gap.update(C_attempts=int(claimed),current_status=pending_status,current_success=None,
                   retry_opportunities_remaining=0 if claimed else 1)
        if p.exists():
            row=d.load(p)
            assert row['method']=='N' and row['attempt']==2 and row['C_attempt']==1 and row['no_corrector']
            assert all(row[k]==v for k,v in gap['source'].items())
            gap.update(current_status=row['status'],current_success=row['success'],C_result=str(p),retry_opportunities_remaining=0)
            if row['status']=='complete' and type(row['success']) is bool:
                assert sid not in ns['pi05_libero']
                ns['pi05_libero'][sid]=dict(row,baseline_origin='C_single_corrected_N_attempt',provenance_path=str(p))
                new_valid.append(sid)
    assert new_attempts<=5 and 1008+new_attempts<=2400
    disposition.update(updated_at_utc=now,new_attempts_so_far=new_attempts,new_valid_terminals=len(new_valid),
                       exhausted_retry_slots=sum(g.get('C_attempts',0) and g.get('current_status') in ('technical_failure','execution_unknown') for g in disposition['entries']),
                       remaining_missing=len(disposition['entries'])-len(new_valid),
                       status='reconciled_all_eligible_terminal' if all(g.get('current_status') in ('complete','technical_failure','unknown') for g in disposition['entries']) else 'reconciled_continuation_running')
    d.atomic(R/'N_GAP_DISPOSITION.json',disposition)
    d.atomic(R/'COMBINED_N_INDEX.json',dict(at_utc=now,task_id=cfg['task_id'],status='partial_coverage_missing_explicit',
             groups={k:list(v.values()) for k,v in ns.items()},original_valid_counts=dict(smolvla=496,xvla=500,pi05_libero=394),
             recovered_from_logs=0,new_C_valid=len(new_valid),new_C_sources=new_valid,
             missing=[dict(source_id=g['source']['source_id'],status=g['current_status'],success=None) for g in disposition['entries'] if g['current_status']!='complete'],
             baseline_provenance='B original records preserved; C retry terminal records additive and individually traceable'))

    # Reuse B's exact paired normal/McNemar implementation for newly resolved N pairs.
    paired_file=C/'work/B/B_D24_LIBERO_VELOCITY_V1_r1/velocity_summary.py'
    spec=importlib.util.spec_from_file_location('frozen_B_paired',paired_file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    paired=module.paired
    tables=[];pairs=[];published_pairs=[]
    names={'smolvla':'SmolVLA 050000','xvla':'X-VLA 030000'}

    def table_row(setting,base,suite,method,wins,n,planned,source,mechanism,baseline_version='current'):
        low,high=wilson(wins,n)
        tables.append(dict(setting=setting,base=base,suite=suite,method=method,mechanism=mechanism,
             successes=wins,valid=n,planned=planned,missing=planned-n,success_rate_pct=100*wins/n if n else None,
             descriptive_wilson95_low_pct=low,descriptive_wilson95_high_pct=high,
             baseline_version=baseline_version,source_path=str(source),status='complete' if n==planned else 'partial_valid'))

    def pair_row(setting,comparison,p,source,method,version='current',new_pairs=0):
        if 'rescued' in p:
            n=p['paired_valid'];win=p['rescued'];loss=p['harmed'];a=p['new_successes'];b=p['old_successes'];ci=p['task_cluster_bootstrap_95_ci_pp'];pv=None
        else:
            n=p['paired_valid'];win=p['candidate_only'];loss=p['baseline_only'];a=p['candidate_successes'];b=p['baseline_successes'];ci=p.get('normal95_CI_pp');pv=p.get('exact_McNemar_two_sided_p')
        return dict(setting=setting,comparison=comparison,paired_valid=n,candidate_successes=a,baseline_successes=b,
                    rescued=win,harmed=loss,difference_pp=p['difference_pp'],CI95_low_pp=ci[0] if ci else None,
                    CI95_high_pp=ci[1] if ci else None,uncertainty_method=method,exact_McNemar_two_sided_p=pv,
                    baseline_version=version,new_C_pairs=new_pairs,source_path=str(source))

    for kind in ('smolvla','xvla'):
        g=next(g for g in mw_summary['groups'] if g['base']==kind)
        pg=next(g for g in mw_post['groups'] if g['model']==kind)
        pci=next(g for g in mw_ci['groups'] if g['model']==kind)
        setting=names[kind]+' / MT50'
        for method,wins,n,source in [('N',g['N_successes'],g['N_valid'],n_path),('Post',g['Post_successes'],g['Post_valid'],mw_post_path),('Velocity',g['successes'],g['valid'],mw_summary_path)]:
            table_row(setting,names[kind],'MT50',method,wins,n,500,source,'N' if method=='N' else 'Full mechanism; frozen pi05 five-task head transfer')
        p=dict(paired_valid=pg['paired_valid'],candidate_successes=pg['paired_Post_successes'],baseline_successes=pg['paired_N_successes'],candidate_only=pg['Post_only'],baseline_only=pg['N_only'],difference_pp=pg['paired_success_difference_pp'],normal95_CI_pp=pci['paired_normal_95_interval_pp'],exact_McNemar_two_sided_p=pci['exact_McNemar_two_sided_p'])
        pairs.append(pair_row(setting,'Post - N',p,mw_ci_path,'published B paired episode normal 95%'))
        for comp in ('N','Post'):
            pairs.append(pair_row(setting,'Velocity - '+comp,g['versus_'+comp],mw_summary_path,'published C task-cluster bootstrap 95%; 2000 draws; seed20260922'))

    post_index=C/'work/B/B_D24_LIBERO_VELOCITY_V1_r1/POST_VALID_BASELINE.json'
    post_rows={r['source_id']:r for r in d.load(post_index)}
    v_batch=C/'work/B/B_D24_LIBERO_VELOCITY_V1_r1/LIBERO_VELOCITY_BATCH.json'
    v_rows=native_rows(v_batch)
    assert len(post_rows)==len(v_rows)==400
    assert sum(r['success'] for r in post_rows.values())==lib_v['Post_successes'] if 'Post_successes' in lib_v else sum(r['success'] for r in post_rows.values())==387
    assert sum(r['success'] for r in v_rows.values())==lib_v['Velocity_successes']
    for sid,nr in ns['pi05_libero'].items():
        for old in (post_rows[sid],v_rows[sid]):
            assert all(old[k]==nr[k] for k in ('source_id','reset_seed','policy_seed','task_id','episode','suite','checkpoint','H','K'))
    suites=['libero_spatial','libero_object','libero_goal','libero_10','all_four_suites']
    for suite in suites:
        select=lambda records:{s:r for s,r in records.items() if suite=='all_four_suites' or r['suite']==suite}
        nn=select(ns['pi05_libero']);on=select(original_lib_n);pp=select(post_rows);vv=select(v_rows)
        planned=400 if suite=='all_four_suites' else 100
        setting='pi05 official / '+suite
        for method,data,source in [('N',nn,R/'COMBINED_N_INDEX.json'),('Post',pp,lib_post_path),('Velocity',vv,lib_v_path)]:
            table_row(setting,'pi05 official',suite,method,sum(r['success'] for r in data.values()),len(data),planned,source,
                      'N' if method=='N' else 'Operator transfer; no D/G0; not Full',
                      'B394_plus_C'+str(len(new_valid)) if method=='N' else 'frozen_B_operator')
        old_v=lib_v if suite=='all_four_suites' else next(g for g in lib_v['groups'] if g['suite']==suite)
        assert paired(vv,on)==old_v['versus_N']
        assert paired(vv,pp)==old_v['versus_Post']
        for label,candidate,baseline in [('Post - N',pp,nn),('Velocity - N',vv,nn),('Velocity - Post',vv,pp)]:
            old_baseline=on if label.endswith(' - N') else pp
            old_pair=paired(candidate,old_baseline)
            p=paired(candidate,baseline)
            new_n=len(baseline)-len(old_baseline)
            source=R/'COMBINED_N_INDEX.json' if new_n else lib_v_path if label.startswith('Velocity') else lib_post_path
            method='B paired episode normal 95% and exact McNemar; same frozen formula'
            pairs.append(pair_row(setting,label,p,source,method,new_pairs=new_n))
            published_pairs.append(pair_row(setting,label,old_pair,lib_v_path if label.startswith('Velocity') else lib_post_path,method,'B_original_N394'))
    d.atomic(R/'E8_PAIRED_PUBLISHED.json',dict(at_utc=now,rows=published_pairs,
               note='Original B394 valid paired subsets retained separately; revised subsets use identical formula after eligible C baseline completion. MW published intervals are copied without method changes.'))
    csv_write(R/'E8_TABLE.csv',tables);csv_write(R/'E8_PAIRED.csv',pairs)

    a_summary_path=C/'results/A/A_D24_LIBERO_FULL_NATIVE_V1/FINAL_SUMMARY.json'
    a_summary=d.load(a_summary_path) if a_summary_path.exists() else None
    a_rows=[]
    for method in ('Full-Post','Full-Velocity'):
        phase=(a_summary or {}).get('phases',{}).get(method,{})
        n=phase.get('valid',0);wins=phase.get('successes',0)
        accepted=bool((a_summary or {}).get('Full_claimed'))
        a_rows.append(dict(setting='pi05 official / LIBERO native Full',method=method,planned=400,
             valid=n,successes=wins if n else None,success_rate_pct=100*wins/n if n else None,
             status='published_full' if accepted and n==400 else 'pending_or_unavailable_Full',
             observed_snapshot_status=(a_summary or {}).get('status','not_published'),Full_claimed=accepted,
             protocol=(a_summary or {}).get('protocol','D2/age2/G0 old3-fresh3_then_native5/C5/nativeK5'),
             source_path=str(a_summary_path)))
    csv_write(R/'E8_FULL_NATIVE_TABLE.csv',a_rows)
    if a_summary:d.atomic(R/'A_FULL_SNAPSHOT.json',a_summary)

    settings=list(dict.fromkeys(t['setting'] for t in tables))
    rows_for=lambda s:{r['method']:r for r in tables if r['setting']==s}
    lines=['E8 跨底座 / 跨 suite 结果；N 基线缺项独立追踪。', '',f'生成时间：{now}。C 新增 N 有效终局 {len(new_valid)}/5；新物理尝试 {new_attempts}，C 累计 {1008+new_attempts}/2400。此前 1000 条 Velocity 未重跑。', '',
           '| 设置 | N 成功/有效 | Post 成功/有效 | Velocity 成功/有效 |', '|---|---:|---:|---:|']
    tex=[r'\begin{tabular}{lrrr}',r'\toprule',r'Setting & N & Post & Velocity \\',r'\midrule']
    for setting in settings:
        row=rows_for(setting)
        fmt=lambda x:f"{x['successes']}/{x['valid']} ({x['success_rate_pct']:.2f}%)"
        lines.append('| '+setting+' | '+' | '.join(fmt(row[m]) for m in ('N','Post','Velocity'))+' |')
        tex.append(setting.replace('_',r'\_')+' & '+' & '.join(fmt(row[m]).replace('%',r'\%') for m in ('N','Post','Velocity'))+r' \\')
    tex += [r'\bottomrule',r'\end{tabular}',r'% Missing outcomes excluded; LIBERO operator transfer has no D/G0 and uses random resets, not official fixed initial states.']
    (R/'E8_TABLE.tex').write_text('\n'.join(tex)+'\n')
    lines += ['', '| 设置 | 配对比较 | 有效对数 | 救回 / 损害 | 差值 pp | 描述性 95% CI pp |', '|---|---|---:|---:|---:|---:|']
    for p in pairs:
        ci='未发布' if p['CI95_low_pp'] is None else f"[{p['CI95_low_pp']:+.2f}, {p['CI95_high_pp']:+.2f}]"
        lines.append(f"| {p['setting']} | {p['comparison']} | {p['paired_valid']} | {p['rescued']} / {p['harmed']} | {p['difference_pp']:+.2f} | {ci} |")
    lines += ['', '配对以相同 source、原 seed、checkpoint 和动作协议为键，排除技术失败/未知；缺失不算失败。MW 的 N 基线保持 Smol 496/X 500；LIBERO 的 B 原 394 与 C 新补记录在 COMBINED_N_INDEX.json 中逐条区分。原 B394 对比另存 E8_PAIRED_PUBLISHED.json，保留历史分母和区间。', '',
              '已有统计直接引用：MW 的 Post−N 沿 B 已发布的配对正态区间；MW 的 Velocity 比较沿 C 已发布的任务聚类 bootstrap（2000 次，seed20260922）。LIBERO 沿 B 原有配对 episode 正态区间及 exact McNemar；有新增有效 N 时仅以原公式更新有效配对集合，不为显著性切换统计方法。区间是描述性的，未校正多重比较，不能据少数正点估计声称普遍增益。没有观测到不一致对时，原正态公式会退化为 [0,0]；这不构成等效证据。', '',
              '图中的绝对成功率使用统一的描述性 Wilson 95% 区间，仅说明有效样本内的二项比例不确定性，不替代配对差检验或任务聚类推断。图表不跨模型池化，也不将 A 的 pi05 H10 主设置与 Smol/X 做逐源配对。', '',
              'Smol/X：继承 B 的实际 80Hz / action_scale 0.01、Mesa、固定 MT50 源，保留原生 H50/H30、K10、NFE10。纠偏为冻结 pi05 五任务特征/D/G0/Q 的迁移；X 原生 clean-prediction remixer 的 Velocity 重参数化不等同于 Euler。X 既有训练集覆盖 49 个唯一任务标签，不能声称完整 50 任务训练覆盖。', '',
              'LIBERO 算子版：官方 pi05 权重与自身 normalizer，H10/K5/NFE10，固定 command20 干预，Post/Velocity 均无 D/G0，不是 Full。使用原随机 reset/policy seeds，未按官方固定初态 benchmark 协议。小头训练仅 120 候选/24 父源，其中 5 个负例；40 个验证候选全成功，不能据其验证准确率声称故障判别能力。Post 与 Velocity 总成功数相同也不意味着逐源结果相同。', '',
              'A 的 native Full-LIBERO 独立列在 E8_FULL_NATIVE_TABLE.csv，采用 D2/age2/G0-execute3_then_native5/C5 等原生时距。当前有效 Full 数据尚未达到完整发布时标为 pending/unavailable，不用 B 算子结果替代。FINAL_SUMMARY 文件名本身不证明科学终局，保留实际 status/valid/Full_claimed。', '',
              '| A 原生 Full 单元 | 有效 / 计划 | 状态 |', '|---|---:|---|']
    for a in a_rows:lines.append(f"| {a['method']} | {a['valid']}/{a['planned']} | {a['status']}（快照 {a['observed_snapshot_status']}） |")
    lines += ['', '10 槽处置：4 个 Smol 和 1 个 LIBERO 有已消费 claim，但窄查原终局日志未得到唯一有效或明确失败记录，保留 unknown。其余 5 个 LIBERO 在第一次物理尝试遇到 CONTROL 瞬时读取/连接故障，旧 B 整组退出证据已保存；C 各仅允许一次明确修正尝试，无自动第二轮。旧 B 的初始 EGL 启动失败尚未进入这些 episode，因此不算这些 source 已用掉一次纠错。全部原始 B/C 结果保留。', '',
              '成本：旧原 N 历史计数 1401；本次新增 '+str(new_attempts)+'。C 旧 1008 加新增 '+str(new_attempts)+'；底座/小头 optimizer 与 development 均新增 0。五个合法独立缺项分配五卡；CPU 整理保留占卡，正式整波八卡 holder 全停，全部正式后代退出后恢复。占卡成本单列，跨机器和不同并发原始耗时不作为算法速度对比。', '',
              '产物：N_GAP_DISPOSITION.json（逐槽证据）、COMBINED_N_INDEX.json（逐条来源）、E8_TABLE.csv/.tex、E8_PAIRED.csv、E8_PAIRED_PUBLISHED.json、E8_FULL_NATIVE_TABLE.csv、E8_SUCCESS_RATES.pdf/.svg；build_tables.py 和 plot_e8.py 可从已保存小结果复现，无实验启动。']
    (R/'E8_REPORT.md').write_text('\n'.join(lines)+'\n')
    d.atomic(R/'TABLE_BUILD.json',dict(at_utc=now,status='published_current_available_evidence',table_rows=len(tables),paired_rows=len(pairs),
            new_C_N_valid=len(new_valid),new_C_attempts=new_attempts,A_Full_complete=all(a['status']=='published_full' for a in a_rows),
            no_scientific_launch=True,inputs=[str(p) for p in (n_path,lib_n_path,mw_summary_path,mw_post_path,mw_ci_path,lib_post_path,lib_v_path,post_index,v_batch,a_summary_path)],
            missingness='unknown retained as unknown; no denominator filling',existing_statistics_reused=True))
    print(json.dumps(dict(table_rows=len(tables),paired_rows=len(pairs),new_C_N_valid=len(new_valid),new_C_attempts=new_attempts,
                          N_counts={k:dict(valid=len(v),successes=sum(r['success'] for r in v.values())) for k,v in ns.items()},report=str(R/'E8_REPORT.md'))))


if __name__=='__main__':
    main()
