"""CPU publication from terminal scalar results. No experiment imports or launches."""
import csv
import datetime as dt
import io
import json
import math
import os
import shutil
import socket
import statistics
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path

WORK = Path(__file__).resolve().parent
BASE = WORK.parents[2]
WS = BASE.parents[2]
TASK = 'A_D24_PAPER_RESULTS_ASSEMBLY_V1'
ROOT = BASE / 'results/A' / TASK
RECEIPTS = BASE / 'receipts/A'
THREAD = '01a0b91f-7443-71b1-915d-6cdb6d6a1a13'
DEADLINE = '2026-09-23T15:00:00+00:00'
os.environ.setdefault('MPLCONFIGDIR', str(WORK / 'matplotlib_cache'))
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
                     'savefig.dpi': 180})
COLORS = dict(N='#777777', R='#cc8a22', Post='#167d9a', Velocity='#7657a2')
METHODS = ['N', 'R', 'Post', 'Velocity']
HORIZONS = [10, 20, 30, 40, 50]
SOURCE_META = {}
BOOT_INDICES = np.random.default_rng(20260921).integers(0, 10, (2000, 50, 10))
BOOT_SCOPE = ('2000 within-task source bootstrap draws, numpy.default_rng(20260921); '
              '50 fixed tasks x 10 sources, shared draws; pointwise percentile 2.5/97.5%; '
              'conditional on these tasks and frozen models, not task-population or training-seed uncertainty')


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    tmp = path.with_name(path.name + '.tmp.' + uuid.uuid4().hex)
    with tmp.open('x') as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def source(path):
    path = Path(path)
    stat = path.stat()
    SOURCE_META[str(path)] = dict(path=str(path), size_bytes=stat.st_size,
        saved_mtime_utc=dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat(), read_at_utc=utc())
    return path


def read(path):
    return json.loads(source(path).read_text())


def rows(path):
    with source(path).open(newline='') as f:
        return list(csv.DictReader(f))


def csv_save(path, values):
    keys = list(dict.fromkeys(k for r in values for k in r))
    out = io.StringIO(newline='')
    w = csv.DictWriter(out, fieldnames=keys)
    w.writeheader(); w.writerows(values)
    atomic(path, out.getvalue())


def boolean(x):
    if x is True or x == 'True': return True
    if x is False or x == 'False': return False
    raise ValueError('Unknown outcome: ' + repr(x))


def number(x):
    if x in ('', None): return None
    x = float(x)
    if not math.isfinite(x): raise ValueError('Nonfinite scalar')
    return x


def normalize(x):
    r = dict(x)
    for k in ('H', 'ordinal', 'repeat', 'env_seed', 'policy_seed'):
        if r.get(k) not in (None, ''): r[k] = int(r[k])
    r['success'] = boolean(r['success'])
    if r['status'] != 'complete' or r.get('technical_failure') not in (None, ''):
        raise ValueError('Nonvalid row must not enter a scientific success denominator')
    if r.get('terminal') not in (None, '') and not boolean(r['terminal']):
        raise ValueError('Not terminal')
    return r


def index(data):
    result = {}
    for raw in data:
        r = normalize(raw)
        key = (r['task'], r['source_id'])
        if key in result: raise ValueError('Duplicate source: ' + str(key))
        result[key] = r
    return result


def identity(left, right):
    for k in ('task', 'source_id', 'env_seed', 'policy_seed', 'ordinal'):
        if left.get(k) != right.get(k): raise ValueError('Source identity mismatch: ' + k)


def boot_interval(values, keys):
    counts = Counter(t for t, _ in keys)
    if len(keys) != 500 or len(counts) != 50 or set(counts.values()) != {10}:
        return [None, None]
    matrix = np.array(values, dtype=float).reshape(50, 10)
    estimates = matrix[np.arange(50)[None, :, None], BOOT_INDICES].mean(axis=(1, 2)) * 100
    return np.quantile(estimates, [.025, .975]).tolist()


def exact_mcnemar(rescued, harmed):
    n = rescued + harmed
    return min(1., 2 * sum(math.comb(n, k) for k in range(min(rescued, harmed) + 1)) / (1 << n)) if n else 1.


def paired(a, b, label):
    ai, bi = index(a), index(b)
    keys = sorted(set(ai) & set(bi))
    if not keys: raise ValueError('No common valid sources')
    for key in keys: identity(ai[key], bi[key])
    delta = [int(ai[k]['success']) - int(bi[k]['success']) for k in keys]
    rescue, harm = delta.count(1), delta.count(-1)
    ci = boot_interval(delta, keys)
    return dict(comparison=label, n=len(keys), candidate_successes=sum(ai[k]['success'] for k in keys),
        comparator_successes=sum(bi[k]['success'] for k in keys), difference_pp=100 * sum(delta) / len(keys),
        CI95_low_pp=ci[0], CI95_high_pp=ci[1], rescued=rescue, harmed=harm,
        both_success=sum(ai[k]['success'] and bi[k]['success'] for k in keys),
        both_failure=sum(not ai[k]['success'] and not bi[k]['success'] for k in keys),
        exact_McNemar_two_sided_p=exact_mcnemar(rescue, harm),
        uncertainty_method=BOOT_SCOPE,
        CI_null_reason=None if ci[0] is not None else 'Complete balanced 50x10 common valid cell unavailable; no imputation')


def fmt(x, digits=2):
    return 'NR' if x is None or x == '' else f'{float(x):.{digits}f}'


def tex_escape(s):
    return str(s).replace('\\', r'\textbackslash{}').replace('_', r'\_').replace('%', r'\%').replace('&', r'\&')


def tex_table(path, headers, data, note):
    text = '% ' + note.replace('\n', ' ') + '\n\\begin{tabular}{' + 'l' + 'r' * (len(headers)-1) + '}\n\\toprule\n'
    text += ' & '.join(tex_escape(x) for x in headers) + r' \\' + '\n\\midrule\n'
    text += '\n'.join(' & '.join(tex_escape(x) for x in row) + r' \\' for row in data)
    text += '\n\\bottomrule\n\\end{tabular}\n'
    atomic(path, text)


def save_figure(out, name, fig, stamp, sources):
    fig.text(.01, .008, 'Snapshot ' + stamp[:19] + ' UTC | ' + sources + ' | source details: SOURCE_INDEX.json', fontsize=5.3)
    fig.tight_layout(rect=(0, .035, 1, 1))
    for ext in ('pdf', 'svg', 'png'):
        fig.savefig(out / (name + '.' + ext))
    plt.close(fig)


def main_groups():
    grouped = defaultdict(list)
    for r in rows(BASE / 'results/A/A_D24_MAIN_ONCE_V1/FINAL_EPISODES.csv'):
        grouped[r['cell']].append(normalize(r))
    assert len(grouped) == 11 and sum(map(len, grouped.values())) == 5500
    return grouped


def initialize_static(out, stamp):
    main = main_groups()
    baseline = []
    for p in sorted((BASE / 'deadline_20260924/A/runs').glob('N_H10_*/RESULT.json')):
        baseline += read(p)['episodes']
    baseline = [normalize(x) for x in baseline]
    assert len(baseline) == 500
    main['N_H10'] = baseline
    gaf_path = BASE / 'results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1'
    gaf = [normalize(x) for x in read(gaf_path / 'EPISODES.json')]
    gaf_summary = read(gaf_path / 'FINAL_SUMMARY.json')
    assert len(gaf) == 500 and sum(r['success'] for r in gaf) == gaf_summary['successes'] == 315
    comparisons = [paired(gaf, main[f'{m}_H10'], f'GAF - {m}') for m in METHODS]
    running = 0.
    for rank, i in enumerate(sorted(range(4), key=lambda i: comparisons[i]['exact_McNemar_two_sided_p'])):
        running = max(running, min(1., (4-rank)*comparisons[i]['exact_McNemar_two_sided_p']))
        comparisons[i]['Holm_p_four_GAF_comparisons'] = running
    csv_save(out/'E3_GAF_PAIRED.csv', comparisons)
    atomic(out/'E3_GAF_PAIRED.json', dict(snapshot_utc=stamp, comparisons=comparisons,
        sign='GAF minus comparator; rescued=GAF success/comparator failure; harmed=reverse',
        multiplicity_scope='Holm only across these four exact McNemar tests; bootstrap CIs are pointwise, not simultaneous'))
    # One overlap with published main statistics verifies draw order, without rerunning the old matrix.
    old = read(BASE/'deadline_20260924/MAIN_FINAL_STATISTICS.json')
    verify = paired(main['Post_H10'], baseline, 'Post_H10-N_H10')
    accepted = old['comparisons']['Post_H10-N_H10']
    assert np.allclose([verify['CI95_low_pp'], verify['CI95_high_pp']], [accepted['CI_low_pp'], accepted['CI_high_pp']])
    vroot = BASE/'results/A/A_D24_E3_UNSTARTED_CONTINUATION_V1'
    vla = [normalize(x) for x in read(vroot/'COMBINED_EPISODES.json')['rows']]
    vs = read(vroot/'COMBINED_FINAL_SUMMARY.json')
    vc = read(vroot/'EXACT_COST_COVERAGE_ACCEPTED_LOG8.json')
    vi, ni = index(vla), index(baseline)
    assert set(vi) == set(ni) and len(vla) == 500
    for key in vi: identity(vi[key], ni[key])
    log8 = [x for x in vla if x.get('record_origin') == 'r2_saved_terminal_log_CPU_recovery']
    assert len(log8) == 8 and all(x['success'] and x.get('policy_calls') is None for x in log8)
    assert sum(x['success'] for x in vla) == vs['successes'] == 319
    csv_save(out/'E3_VLA_LOG_DERIVED_PROVENANCE.csv', [dict(source_id=x['source_id'], task=x['task'], success=x['success'],
        record_origin=x['record_origin'], policy_calls=None, flow_calls=None, elapsed_seconds=None,
        null_reason='Accepted unique terminal log; exact cost unavailable; original publication failure retained') for x in log8])
    atomic(out/'E3_VLA_COST_COVERAGE.json', vc)
    e3 = []
    for method, vals in [(m, main[m+'_H10']) for m in METHODS] + [('VLA-Corrector', vla), ('GAF-v1 adapted', gaf)]:
        n, s = len(vals), sum(x['success'] for x in vals)
        calls = [number(x.get('policy_calls')) for x in vals]
        known = [x for x in calls if x is not None]
        cov = len(known)
        e3.append(dict(method=method, H=10, valid=n, successes=s, success_rate_pct=100*s/n,
            policy_cost_coverage=cov, known_policy_calls_sum=sum(known),
            policy_calls_mean_all=sum(known)/n if cov==n else None,
            all_policy_calls_per_success=sum(known)/s if cov==n and s else None,
            log_derived_outcomes=8 if method=='VLA-Corrector' else 0,
            preserved_publication_failures=8 if method=='VLA-Corrector' else 0,
            training_scope=('epoch30 native corrector; different training data' if method=='VLA-Corrector' else
                '15 train parents; 2 fixed internal holdout parents; adapted' if method=='GAF-v1 adapted' else
                'same pi05 SFT030000; inherited five-task D/G0/Q where applicable'),
            mechanism_scope=('native repeated interventions, native thresholds' if method=='VLA-Corrector' else
                'continuous native guidance; no G0 or once gate' if method=='GAF-v1 adapted' else 'N native; R/Post/Velocity natural G0, at most once')))
    csv_save(out/'E3_COMPARISON_TABLE.csv', e3)
    tex_table(out/'E3_COMPARISON_TABLE.tex', ['Method','Success / n','SR (%)','Cost n','Calls / success'],
        [[x['method'],f"{x['successes']} / {x['valid']}",fmt(x['success_rate_pct'],1),x['policy_cost_coverage'],fmt(x['all_policy_calls_per_success'])] for x in e3],
        'Different training data/native intervention rules. VLA-Corrector cost incomplete: 492/500; eight log-derived outcomes. Snapshot '+stamp)
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.3), gridspec_kw={'width_ratios':[1.25,1]})
    for i, c in enumerate(comparisons):
        axes[0].errorbar(c['difference_pp'], i, xerr=[[c['difference_pp']-c['CI95_low_pp']],[c['CI95_high_pp']-c['difference_pp']]],fmt='o',color='#17677e',capsize=3)
    axes[0].axvline(0,color='0.6',ls='--',lw=1);axes[0].set_yticks(range(4),[x['comparison'] for x in comparisons]);axes[0].invert_yaxis()
    axes[0].set_xlabel('Success difference (pp), pointwise 95% CI');axes[0].set_title('GAF versus frozen main methods (H=10)')
    y=np.arange(4)
    axes[1].barh(y-.16,[c['rescued'] for c in comparisons],.30,label='GAF rescues',color='#167d9a')
    axes[1].barh(y+.16,[c['harmed'] for c in comparisons],.30,label='GAF harms',color='#d8996c')
    axes[1].set_yticks(y,METHODS);axes[1].invert_yaxis();axes[1].set_xlabel('Discordant sources (n=500 each)');axes[1].legend(fontsize=8)
    save_figure(out,'E3_GAF_PAIRED_FIGURE',fig,stamp,'GAF EPISODES; A main/N scalars')
    # E1: sample SD over independent complete fits, not binomial SE over repeated test identities.
    e1p=BASE/'results/B/B_D24_SPRINT_V1/r1/D24_E1_RENDER_REPAIR_r3/E1_COMPLETE_CELLS.csv'
    e1raw=rows(e1p);costs=read(BASE/'results/B/B_D24_EXTENSION_REMAINDER_V1/E1_final/E1_COST_AND_PAIR_SUMMARY.json')
    assert len(e1raw)==24 and costs['valid_episodes']==1200 and costs['invalid_original_excluded']==1120
    lookup={(x['loss'],str(x['complete_training_seed']),x['method']):x for x in costs['cell_costs']}
    e1=[]
    for loss in ['L00','L01','L10','L11']:
        entry=dict(loss=loss,complete_fit_seeds=3,distinct_test_sources=50,episodes_per_seed=50)
        for m in ['Post','Velocity']:
            part=[x for x in e1raw if x['loss']==loss and x['method']==m]
            assert sorted(int(x['complete_training_seed']) for x in part)==[9101,9102,9103]
            for x in part:
                assert int(x['n'])==50 and int(x['technical_failures'])==0
                assert int(x['successes'])==lookup[(loss,x['complete_training_seed'],m)]['successes']
            rates=[int(x['successes'])*2 for x in part]
            entry.update({m+'_mean_pct':statistics.mean(rates),m+'_fit_sample_SD_pp':statistics.stdev(rates)})
        e1.append(entry)
    csv_save(out/'E1_LOSS_ABLATION_TABLE.csv',e1);csv_save(out/'E1_SEED_APPENDIX.csv',e1raw)
    tex_table(out/'E1_LOSS_ABLATION_TABLE.tex',['Loss','Post mean +/- SD (%)','Velocity mean +/- SD (%)'],
        [[x['loss'],fmt(x['Post_mean_pct'])+' +/- '+fmt(x['Post_fit_sample_SD_pp']),fmt(x['Velocity_mean_pct'])+' +/- '+fmt(x['Velocity_fit_sample_SD_pp'])] for x in e1],
        'Three complete fit seeds, sample SD (ddof=1), same50 test sources per fit, excludes1120 invalid black-RGB results; '+stamp)
    tex_table(out/'E1_SEED_APPENDIX.tex',['Loss','Fit seed','Method','Success / 50'],[[x['loss'],x['complete_training_seed'],x['method'],x['successes']+' / 50'] for x in e1raw],'Independent complete fit seeds; '+stamp)
    fig,ax=plt.subplots(figsize=(6.2,3.5))
    for m,offset in [('Post',-.08),('Velocity',.08)]:
        y=[x[m+'_mean_pct'] for x in e1];err=[x[m+'_fit_sample_SD_pp'] for x in e1]
        ax.errorbar(np.arange(4)+offset,y,yerr=err,fmt='o-',color=COLORS[m],capsize=4,label=m+' (mean +/- fit SD)')
        for i,x in enumerate(e1):
            vals=[2*int(z['successes']) for z in e1raw if z['loss']==x['loss'] and z['method']==m]
            ax.scatter(np.arange(3)*.025 + i+offset-.025,vals,s=12,color=COLORS[m],alpha=.5)
    ax.set_xticks(range(4),['L00','L01','L10','L11']);ax.set_ylabel('Success rate (%)');ax.set_ylim(57,76);ax.legend(fontsize=8)
    ax.set_title('Loss ablation: three complete fit seeds, same 50 sources')
    save_figure(out,'E1_LOSS_ABLATION_FIGURE',fig,stamp,'B E1 valid24 cells; E1_final cost/pair summary')
    # E6 uses the corrected full per-task CSV and real paired test identities.
    ep=BASE/'results/A/A_D24_CORE_REMAINDER_V1'
    e6raw=read(ep/'E6_EPISODES.json');e6tasks=rows(ep/'E6_PER_TASK_CELLS.csv');e6s=read(ep/'E6_FINAL_SUMMARY.json')
    by={m:[normalize(x) for x in e6raw if x['method']==m] for m in ['D5','G0','DEV']}
    assert [len(by[x]) for x in ['D5','G0','DEV']]==[50,50,100]
    e6=[]
    for task in sorted({x['task'] for x in by['D5']})+['ALL five tasks']:
        a=[x for x in by['D5'] if task.startswith('ALL') or x['task']==task]
        c=[x for x in by['G0'] if task.startswith('ALL') or x['task']==task]
        d=paired(a,c,'D5 - G0')
        if not task.startswith('ALL'):
            for method,subset in [('D5',a),('G0',c)]:
                tab=next(x for x in e6tasks if x['method']==method and x['task']==task)
                assert int(tab['successes'])==sum(x['success'] for x in subset) and int(tab['n'])==len(subset)
        e6.append(dict(task=task,n_each=d['n'],D5_successes=d['candidate_successes'],G0_successes=d['comparator_successes'],
            D5_rate_pct=100*d['candidate_successes']/d['n'],G0_rate_pct=100*d['comparator_successes']/d['n'],
            D5_minus_G0_pp=d['difference_pp'],D5_rescues=d['rescued'],D5_harms=d['harmed'],both_success=d['both_success'],both_failure=d['both_failure'],
            exact_McNemar_two_sided_p=d['exact_McNemar_two_sided_p'] if task.startswith('ALL') else None))
    total=e6[-1];assert [total[k] for k in ['D5_successes','G0_successes','D5_rescues','D5_harms','both_success','both_failure']]==[30,26,5,1,25,19]
    assert total['exact_McNemar_two_sided_p']==.21875
    csv_save(out/'E6_TRIGGER_TABLE.csv',e6);csv_save(out/'E6_DEV_CALIBRATION_SEPARATE.csv',[x for x in e6tasks if x['method']=='DEV'])
    atomic(out/'E6_SCOPE.json',dict(test_sources=50,test_episodes=100,dev_sources=100,dev_episodes=100,
        calibration_summary=str(ep/'E6_FINAL_SUMMARY.json'),threshold=e6s.get('threshold'),test_selection=False,
        overall_pair=total,claim='This comparison does not establish an advantage for G0 over D5.'))
    tex_table(out/'E6_TRIGGER_TABLE.tex',['Task','D5 / n','G0 / n','D5 - G0 (pp)'],
        [[x['task'],f"{x['D5_successes']} / {x['n_each']}",f"{x['G0_successes']} / {x['n_each']}",fmt(x['D5_minus_G0_pp'],1)] for x in e6],
        'Both trigger R, same50 tests, dev100 calibration separate; exact paired p=.21875; descriptive cells, no errorbars; '+stamp)
    fig,ax=plt.subplots(figsize=(7.2,3.5));xx=np.arange(5)
    ax.bar(xx-.18,[x['G0_rate_pct'] for x in e6[:-1]],.34,label='G0 -> R (26/50)',color='#167d9a')
    ax.bar(xx+.18,[x['D5_rate_pct'] for x in e6[:-1]],.34,label='D5 -> R (30/50)',color='#b68942')
    ax.set_xticks(xx,[x['task'].replace('-v3','').replace('pick-place-wall','pick-place\nwall') for x in e6[:-1]])
    ax.set_ylim(0,110);ax.set_ylabel('Test success rate (%)');ax.legend(fontsize=8);ax.set_title('Trigger comparison: 10 paired test sources per task')
    save_figure(out,'E6_TRIGGER_FIGURE',fig,stamp,'E6_EPISODES; corrected E6_PER_TASK_CELLS')
    # E8: reuse the updated published pairing and its original method-specific intervals.
    e8p=BASE/'results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1'
    e8=rows(e8p/'E8_TABLE.csv');e8pairs=rows(e8p/'E8_PAIRED.csv');nidx=read(e8p/'COMBINED_N_INDEX.json')
    source(e8p/'E8_REPORT.md')
    for group,n,s in [('smolvla',496,234),('xvla',500,403),('pi05_libero',399,387)]:
        vals=nidx['groups'][group];assert len(vals)==n and sum(boolean(x['success']) for x in vals)==s
    gap=read(BASE/'deadline_20260924/A_LIBERO_FULL_NATIVE_SCIENTIFIC_GAP_ACCEPTANCE.json')
    assert gap['status']=='closed_incomplete_scientific_gap' and gap['Full_Post_test']==gap['Full_Velocity_test']==0
    for method in ['Full Post','Full Velocity']:
        row={k:None for k in e8[0]}
        row.update(setting='LIBERO / ALL4 / full system',base='pi05 LIBERO',suite='ALL4',method=method,
            mechanism='D2 / age2 + learned G0 + L11; not trained/tested',planned=400,valid=0,missing=400,
            status='SCIENTIFIC_GAP',source_path=str(BASE/'deadline_20260924/A_LIBERO_FULL_NATIVE_SCIENTIFIC_GAP_ACCEPTANCE.json'))
        e8.append(row)
    csv_save(out/'E8_TABLE.csv',e8);csv_save(out/'E8_PAIRED.csv',e8pairs)
    tex_table(out/'E8_TABLE.tex',['Setting','Method','Success / valid','SR (%)','Status'],
        [[x['setting'],x['method'],'NR' if x['successes'] in ('',None) else f"{x['successes']} / {x['valid']}",fmt(x['success_rate_pct']),x['status']] for x in e8],
        'Latest C valid N: Smol496/X500/LIBERO399; Full SCIENTIFIC_GAP, untested not0%; '+stamp)
    atomic(out/'LIBERO_SCOPE_AND_GAP.md',f'''# LIBERO scope and scientific gap

Snapshot: {stamp}. Sources: C E8_TABLE/E8_PAIRED/COMBINED_N_INDEX and A_LIBERO_FULL_NATIVE_SCIENTIFIC_GAP_ACCEPTANCE.json (SOURCE_INDEX.json).

| Item | Observed result | Permitted interpretation |
|---|---|---|
| N, four LIBERO suites | 387/399; one unknown | Latest C recovery includes five real valid successes. |
| Post / Velocity operator transfer | 387/400 each | BCE head, fixed intervention time, native K5; no D/G0. Identical totals do not imply identical source outcomes. |
| Full Post / Full Velocity | NR / NR; test attempts 0 / 0 | SCIENTIFIC_GAP: full system unverified. Not 0% and not operator-transfer results relabelled Full. |
| New full-system development | 40 attempts: 30 valid successes, 10 technical failures | Setting total 200/200; failures retained; no further collection. |
| G0 supervision | 7 training + 4 validation pairs; all gains zero | No varying gain target for a learned trigger; no constant-G0 training/evaluation. |
| D2 / Q-L11 | 681 / 225 D windows; Q candidate labels usable | Available fields do not establish a trained full system. Small-network updates 0. |

开发30/30成功不能作为Full测试100%。算子版采用预定时刻而非真实D/G0；开发扰动标签不能替代重规划收益。Smol另有4条N未知，LIBERO1条N未知，均不补作失败。
No new model, environment, fit, evaluation, preflight or holder operation is performed by this publication.
''')
    # Reuse E5 saved totals, definitions and timing ranges without new measurements.
    e5p=BASE/'results/A/A_D24_OURS_E5_REPORT_V1'
    for name in ['TIMING_TABLE.csv','ENTRY_TIMING_TABLE.csv','COST_COMPARISONS.csv','FIELD_DEFINITIONS.json']:
        source(e5p/name);shutil.copy2(e5p/name,out/('E5_'+name))
    params=read(e5p/'PARAMETER_COUNTS.json');assert params['total_added_unique_network_parameters']==11912530
    pars=[dict(setting='pi05 main',component=k,networks=v['members'],parameters=v['ensemble_parameters'],note='Saved parameter-shape metadata; no model load') for k,v in params['components'].items()]
    pars += [dict(setting='pi05 main',component='D+G0+Q total',networks=8,parameters=11912530,note='Existing pi05 feature backbone reused; feature computation is not free'),
        dict(setting='Smol / X transfer',component='full added deployment',networks=None,parameters=None,note='External pi05 feature network plus D/G0/Q; full unique runtime parameter count NR'),
        dict(setting='pi05 base',component='unique runtime base',networks=1,parameters=None,note='Serialized weight elements do not establish tying/unused heads; no runtime model instantiated')]
    csv_save(out/'E5_PARAMETER_TABLE.csv',pars)
    tex_table(out/'E5_PARAMETER_TABLE.tex',['Setting','Component','Parameters'],[[x['setting'],x['component'],x['parameters'] if x['parameters'] is not None else 'NR'] for x in pars],
        'Smol/X full overhead includes an external pi05 feature model; 11.9M is not its full cost. '+stamp)
    calls=read(e5p/'FIELD_DEFINITIONS.json')['per_intervention']
    csv_save(out/'E5_INTERVENTION_CALLS.csv',[dict(method=m,**v) for m,v in calls.items()])
    facts=dict(snapshot_utc=stamp,GAF_paired=comparisons,E3=e3,E1=e1,E6=total,E8_rows=len(e8),
        parameter_total=11912530,GAF_sources=500,GAF_successes=315,VLA_successes=319,VLA_log_derived=8,VLA_cost_coverage=492)
    atomic(out/'STATIC_FACTS.json',facts)
    atomic(out/'STATIC_CHECKS.json',dict(GAF_four_pairs_500=all(x['n']==500 for x in comparisons),
        seed_identity_matches=True,main_bootstrap_order_matches_published_H10=True,E1_24_valid_cells=True,
        E6_per_task_csv_matches_episodes=True,E8_N_updated_denominators_match=True,VLA_log8_costs_stay_null=True,
        scientific_compute=0,holder_changes=0,scope='Only source/denominator/numeric output checks; no old engineering test suite'))


def field_stats(vals, name):
    vv=[number(x.get(name)) for x in vals];sv=[number(x.get(name)) for x in vals if x['success']]
    known=[v for v in vv if v is not None];sk=[v for v in sv if v is not None]
    n,s=len(vals),sum(x['success'] for x in vals)
    total=math.fsum(known) if known else None;success_total=math.fsum(sk) if sk else None
    return dict(sum_all=total,mean_all=total/n if len(known)==n and n else None,
        sum_success_only=success_total,mean_success_only=success_total/s if len(sk)==s and s else None,
        amortized_per_success=total/s if len(known)==n and s else None,
        recorded_all=len(known),recorded_success=len(sk))


def build_dynamic(out, stamp, terminals):
    old=read(BASE/'deadline_20260924/MAIN_FINAL_STATISTICS.json')
    cost=rows(BASE/'results/A/A_D24_OURS_E5_REPORT_V1/PAPER_COST_TABLE.csv')
    grouped=main_groups();cells=[]
    for cell,v in old['cells'].items():
        ci=v['success_rate_ci95_pct']
        cells.append(dict(cell=cell,method=v['method'],H=v['H'],node='A',valid=v['episodes'],successes=v['successes'],
            success_rate_pct=v['success_rate_pct'],CI95_low_pct=ci[0],CI95_high_pct=ci[1],technical_failures=v['technical_failures'],
            status='complete',null_reason=None,source_path=str(BASE/'deadline_20260924/MAIN_FINAL_STATISTICS.json')))
    identity_ref=index(grouped['Post_H10'])
    added=[]
    for node, terminal in terminals.items():
        if terminal.get('state')!='consumed':continue
        source(terminal['terminal_path']);source(terminal['summary_path'])
        rr=rows(terminal['episodes_path'])
        good=defaultdict(list)
        for raw in rr:
            if raw.get('status')!='complete' or raw.get('technical_failure') not in ('',None):continue
            r=normalize(raw);cell='R_H'+str(r['H']);good[cell].append(r)
            if r['H'] not in terminal['horizons'] or r['method']!='R':raise ValueError('Wrong terminal unit')
            identity(r,identity_ref[(r['task'],r['source_id'])])
        for h in terminal['horizons']:
            cell='R_H'+str(h);vals=good.get(cell,[]);idx=index(vals);keys=sorted(idx)
            if not vals:continue
            assert len(vals)<=500
            ci=boot_interval([int(idx[k]['success']) for k in keys],keys)
            n,s=len(vals),sum(r['success'] for r in vals)
            cells.append(dict(cell=cell,method='R',H=h,node=node,valid=n,successes=s,success_rate_pct=100*s/n,
                CI95_low_pct=ci[0],CI95_high_pct=ci[1],technical_failures=terminal.get('technical_failures_by_H',{}).get(str(h)),
                status='complete' if n==500 else 'partial_valid',null_reason=None if n==500 else 'Terminal valid subset only; missing outcomes not failures',source_path=terminal['episodes_path']))
            grouped[cell]=vals
            cr=dict(cell=cell,method='R',H=h,tasks=len({x['task'] for x in vals}),attempts=terminal.get('attempts_by_H',{}).get(str(h)),
                valid_episodes=n,successes=s,technical_failures=terminal.get('technical_failures_by_H',{}).get(str(h)),
                success_rate_pct=100*s/n,success_CI_low_pct=ci[0],success_CI_high_pct=ci[1],
                policy_definition_id='R_complete_sampling_calls',complete_sampling_explicit_null_reason=None,node=node,
                timing_caveat='Cross-host R extension; no controlled same-host speed claim')
            for k in ['policy_calls','sampling_calls','flow_calls','steps','interventions']:
                cr.update({k+'_'+s:v for s,v in field_stats(vals,k).items()})
            cr.update(policy_amortized_CI_low=None,policy_amortized_CI_high=None,
                amortized_CI_null_reason='Not newly estimated for appended R; point cost from complete saved fields')
            cost.append(cr);added.append(cell)
    present={r['cell'] for r in cells}
    for h in HORIZONS:
        for m in METHODS:
            cell=f'{m}_H{h}'
            if cell not in present:
                node='B' if h in (20,30) else 'C'
                reason=terminals.get(node,{}).get('reason','Awaiting latest-run terminal publication with valid episode CSV; no assumption from startup/STABLE')
                cells.append(dict(cell=cell,method=m,H=h,node=node,valid=None,successes=None,success_rate_pct=None,
                    CI95_low_pct=None,CI95_high_pct=None,technical_failures=None,status='NR',null_reason=reason,source_path=None))
    cells.sort(key=lambda r:(r['H'],METHODS.index(r['method'])))
    cost.sort(key=lambda r:(int(r['H']),METHODS.index(r['method'])))
    csv_save(out/'MAIN_20CELL_TABLE.csv',cells);csv_save(out/'E5_AMORTIZED_COST_TABLE.csv',cost)
    by={x['cell']:x for x in cells}
    tex_table(out/'MAIN_20CELL_TABLE.tex',['H','N','R','Post','Velocity'],
        [[h]+['NR' if by[f'{m}_H{h}']['valid'] is None else f"{by[f'{m}_H{h}']['successes']}/{by[f'{m}_H{h}']['valid']} ({by[f'{m}_H{h}']['success_rate_pct']:.1f}%)" for m in METHODS] for h in HORIZONS],
        '50 fixed tasks x10 test sources; each method/H is paired, not independent source sets; five-task frozen D/G0/Q; '+stamp)
    tex_table(out/'E5_AMORTIZED_COST_TABLE.tex',['Cell','SR (%)','Mean calls / all','Mean calls / success-only','All calls / successes'],
        [[r['cell'],fmt(r['success_rate_pct'],1),fmt(r['policy_calls_mean_all']),fmt(r['policy_calls_mean_success_only']),fmt(r['policy_calls_amortized_per_success'])] for r in cost],
        'Different denominators explicitly separated; N standalone sampling field NR; policy counter source-defined; '+stamp)
    pairs=[]
    for h in HORIZONS:
        if 'R_H'+str(h) in grouped:
            for m in ['Post','Velocity']:
                p=paired(grouped[f'{m}_H{h}'],grouped[f'R_H{h}'],f'{m} - R')
                p.update(H=h,scope='Full main MT50 system; not LIBERO Full',multiplicity='Descriptive unadjusted comparisons; no whole-paper Holm claim')
                pairs.append(p)
    csv_save(out/'MAIN_FULL_MINUS_R_PAIRED.csv',pairs)
    atomic(out/'MAIN_FULL_MINUS_R_PAIRED.json',dict(snapshot_utc=stamp,comparisons=pairs,bootstrap=BOOT_SCOPE))
    tex_table(out/'MAIN_FULL_MINUS_R_PAIRED.tex',['H','Comparison','n','Delta (pp)','95% CI','Rescue / harm'],
        [[x['H'],x['comparison'],x['n'],fmt(x['difference_pp']),f"[{fmt(x['CI95_low_pp'])}, {fmt(x['CI95_high_pp'])}]",f"{x['rescued']} / {x['harmed']}"] for x in pairs],
        'Conditional fixed-task paired percentile CIs, pointwise; B/C R cross-host, elapsed time not controlled comparable; '+stamp)
    complete=sum(x['status']=='complete' for x in cells)
    fig,ax=plt.subplots(figsize=(6.8,3.8))
    for m in METHODS:
        part=[by[f'{m}_H{h}'] for h in HORIZONS]
        y=np.array([x['success_rate_pct'] if x['success_rate_pct'] is not None else np.nan for x in part])
        lo=np.array([x['CI95_low_pct'] if x['CI95_low_pct'] is not None else np.nan for x in part]);hi=np.array([x['CI95_high_pct'] if x['CI95_high_pct'] is not None else np.nan for x in part])
        ax.plot(HORIZONS,y,'o-',label=m,color=COLORS[m],lw=1.6);ax.fill_between(HORIZONS,lo,hi,color=COLORS[m],alpha=.09)
    ax.set_xticks(HORIZONS);ax.set_xlabel('Native execution horizon H');ax.set_ylabel('Success rate (%)');ax.legend(ncol=4,fontsize=8)
    ax.set_title(f'MT50 fixed-source main matrix ({complete}/20 complete cells)')
    save_figure(out,'MAIN_H_CURVES',fig,stamp,'A final16; terminal B/C R only; pointwise source-bootstrap95% CI')
    fig,axes=plt.subplots(1,2,figsize=(9,3.7))
    for m in METHODS:
        part=[r for r in cost if r['method']==m]
        axes[0].scatter([float(r['policy_calls_mean_all']) for r in part],[float(r['success_rate_pct']) for r in part],s=30,label=m,color=COLORS[m])
        for r in part:
            axes[0].annotate(str(r['H']),(float(r['policy_calls_mean_all']),float(r['success_rate_pct'])),xytext=(3,4),textcoords='offset points',fontsize=7,color=COLORS[m])
        axes[1].plot([int(r['H']) for r in part],[float(r['policy_calls_amortized_per_success']) for r in part],'o-',label=m,color=COLORS[m])
    axes[0].set_xlabel('Mean policy calls / all valid episodes');axes[0].set_ylabel('Success rate (%)');axes[0].set_title('Labels indicate H; counts are not wall time')
    axes[1].set_xlabel('H');axes[1].set_xticks(HORIZONS);axes[1].set_ylabel('All policy calls / number of successes');axes[1].set_title('Amortized calls include unsuccessful episodes');axes[1].legend(fontsize=8)
    save_figure(out,'E5_EFFECT_CALLS_FIGURE',fig,stamp,'Saved E5 scalar costs; terminal R scalars')
    # Saved timing ranges, never subtract scopes or infer missing per-entry timers.
    times=rows(BASE/'results/A/A_D24_OURS_E5_REPORT_V1/TIMING_TABLE.csv')
    for cell in added:
        for metric in ['elapsed_seconds','inference_seconds','environment_seconds']:
            vals=grouped[cell];fs=field_stats(vals,metric);v=[number(r.get(metric)) for r in vals];known=[x for x in v if x is not None]
            times.append(dict(cell=cell,metric=metric,scope='Saved cross-host episode wall' if metric=='elapsed_seconds' else 'Saved generation/correction only' if metric=='inference_seconds' else 'Saved environment-step time',
                **fs,denominator_all=len(vals),denominator_success=sum(r['success'] for r in vals),
                min_observed=min(known) if known else None,max_observed=max(known) if known else None,
                null_reason=None if len(known)==len(vals) else 'Incomplete recorded coverage',entry_timing_reference='NR: no new per-entry extraction for R extension'))
    csv_save(out/'E5_TIMING_RANGES.csv',times)
    facts=read(out/'STATIC_FACTS.json');write_documents(out,stamp,cells,pairs,cost,facts,terminals)
    state=dict(snapshot_utc=stamp,complete_cells=complete,valid_episodes=sum(x['valid'] or 0 for x in cells),
        source_identities=500,cells=cells,terminal_consumptions=terminals,remaining_cells=[x['cell'] for x in cells if x['status']!='complete'],
        scientific_compute=0,holder_changes=0,old_N_main_pilot_LIBERO_replays=0)
    atomic(out/'MAIN_STATE.json',state)
    return state


def write_documents(out, stamp, cells, pairs, cost, facts, terminals):
    by={x['cell']:x for x in cells};ncomplete=sum(x['status']=='complete' for x in cells)
    table=['| H | N | R | Post | Velocity |','|---|---:|---:|---:|---:|']
    for h in HORIZONS:
        table.append('| '+str(h)+' | '+' | '.join('NR' if by[f'{m}_H{h}']['valid'] is None else f"{by[f'{m}_H{h}']['successes']}/{by[f'{m}_H{h}']['valid']} ({by[f'{m}_H{h}']['success_rate_pct']:.1f}%)" for m in METHODS)+' |')
    gaflines=['| GAF minus | n | Difference pp [95% CI] | Rescue / harm | Exact p | Holm p (4 only) |','|---|---:|---:|---:|---:|---:|']
    for x in facts['GAF_paired']:
        gaflines.append(f"| {x['comparison']} | {x['n']} | {x['difference_pp']:+.2f} [{x['CI95_low_pp']:.2f}, {x['CI95_high_pp']:.2f}] | {x['rescued']}/{x['harmed']} | {x['exact_McNemar_two_sided_p']:.5g} | {x['Holm_p_four_GAF_comparisons']:.5g} |")
    e1lines=['| Loss | Post mean ± sample SD (%) | Velocity mean ± sample SD (%) |','|---|---:|---:|']
    for x in facts['E1']:e1lines.append(f"| {x['loss']} | {x['Post_mean_pct']:.2f} ± {x['Post_fit_sample_SD_pp']:.2f} | {x['Velocity_mean_pct']:.2f} ± {x['Velocity_fit_sample_SD_pp']:.2f} |")
    text=f'''# Paper results — existing terminal evidence

Snapshot {stamp}; {ncomplete}/20 main cells complete. Source files and read times: SOURCE_INDEX.json. Tables with NR are intentionally unreported, never zero-imputed. This publication performs CPU statistics/plotting only and leaves idle holders unchanged.

## Main MT50 matrix and E5

{chr(10).join(table)}

All cells reuse the same 50 tasks × 10 fixed test source identities and π0.5-MT50 SFT030000. R/Post/Velocity use natural G0, at most one intervention and the frozen native-H/C10 rules. D/G0/Q were trained on the historical five tasks (disassemble, pick-place-wall, shelf-place, stick-pull, stick-push); these results do not claim new full-MT50 critic training. B/C R extensions run on other hosts under the matched native protocol; no controlled same-host elapsed-time claim.

MAIN_FULL_MINUS_R_PAIRED.csv gives the paired Full main-system Post/Velocity minus R comparisons at available H. Here “Full main” refers to MT50, not untrained LIBERO Full. Conditional pointwise CIs are not simultaneous, training-seed or task-population uncertainty. No test-based threshold/model/H selection is performed.

E5_AMORTIZED_COST_TABLE separates mean calls over all valid episodes, mean calls inside successful episodes, and total calls from all valid episodes divided by the number of successes. N's separately recorded sampling/intervention-entry fields remain NR. R/Post/Velocity intervention entries cost 1/1/2 complete samples and 10/10/20 flow calls; Post has 3 ensemble evaluations/12 member forwards/1 action gradient, Velocity 8/32/3. Different calls have different computation; flow counts omit encoders, D/G0 and Q.

E5_TIMING_RANGES.csv and E5_ENTRY_TIMING_TABLE.csv retain saved min/max and scopes. Generation/correction time excludes context/D/G0 included in episode wall time; subtracting the scopes is not a measured net module overhead. Sum of parallel episode times is not makespan, GPU kernel time or energy. Historical A tail-card auxiliary holders affect timing comparability; appended B/C R timing is additionally cross-host. No speed superiority over VLA fine-tuning is claimed.

D/G0/Q add **11,912,530** unique network parameters in the π0.5 main setting (D 8,948,232; G0 2,936,066; Q 28,232), reusing its existing frozen feature backbone. Smol/X transfer also invokes an external π0.5 feature network: full additional runtime parameters and cost are **NR**, not 11.9M. Serialized base weight elements do not establish unique runtime parameters.

## E3 paired external-method comparisons

{chr(10).join(gaflines)}

GAF has 315/500 (63.0%); VLA-Corrector has 319/500 (63.8%). GAF fits 15 existing train parents and selects on two fixed internal holdout parents; VLA-Corrector uses its existing epoch30 model. Training data and native intervention rules differ, so this is not a strict equal-data reproduction. GAF uses continuous guidance rather than the main once gate. The four Holm values adjust only these four exact two-sided McNemar tests; their bootstrap intervals remain pointwise.

VLA-Corrector includes eight accepted log-derived successes and eight original publication failures. Exact calls/flow/time coverage remains 492/500; known sums are labeled as such, whole-500 costs stay NR. No failure is erased or cost imputed. E3_VLA_LOG_DERIVED_PROVENANCE.csv preserves those eight source identities.

## E1 loss ablation

{chr(10).join(e1lines)}

Mean and sample SD (ddof=1) over three complete fit seeds 9101/9102/9103. Each fit evaluates the same50 sources; these are not150 independent initial states. Four Q ensemble members are not four fit seeds. The old1120 invalid black-RGB records are excluded; corrected1200 valid evaluations are represented. L11 is not uniformly best; retain the neutral result. Per-seed successes/50 are in E1_SEED_APPENDIX.csv.

## E6 trigger comparison

G0→R **26/50 (52%)**, D5→R **30/50 (60%)**. D5 rescues5 and harms1 versus G0, both succeed25 and both fail19; exact two-sided McNemar p=0.21875. This does not establish a G0 advantage. The100 development threshold-calibration episodes are separate from the100 test evaluations on50 paired test sources. Per-task counts come from the corrected full CSV, not a last-shard SUMMARY.tasks snapshot.

## E8 transfer and LIBERO scope

Latest valid N: Smol **234/496**, X **403/500**, LIBERO **387/399**. Unknown N outcomes remain Smol4 and LIBERO1. E8_PAIRED.csv directly reuses C's updated matched subsets and method-specific intervals: no denominator-only edits. Smol/X use their native horizons/protocols with an external π0.5 feature network; these are not A-main same-protocol baselines. The X training metadata has49 unique task labels, not verified all50 training coverage.

LIBERO operator Post and Velocity each reach387/400, using BCE and a fixed intervention time without D/G0. They are not Full. LIBERO Full is **SCIENTIFIC_GAP / NR**: no training or test calls, gain labels all zero on7 train+4 validation pairs; development40 attempts comprise30 valid successes and10 technical failures, exhausting200/200. D windows681/225 and Q candidate labels do not resolve that supervision gap. See LIBERO_SCOPE_AND_GAP.md.

E8 uncertainty is inherited and heterogeneous: published B paired normal CI for Post−N, C task-cluster bootstrap2000/seed20260922 for MT50 Velocity, and paired normal CI plus exact McNemar for LIBERO. Absolute Wilson intervals are descriptive. These must not be relabelled as the main within-task bootstrap or training-seed SD. [0,0] from no discordance is not equivalence evidence.

## Finite terminal observer

B and C are consumed independently, at most once each, after the latest run's true terminal exit/publication plus episode CSV. Current consumption records: {', '.join(k+':'+v.get('state','unknown') for k,v in terminals.items()) or 'none; initial16-cell snapshot'}. Deadline {DEADLINE}; late/unavailable cells remain NR with a reason. No A R launch, collection, training or holder change is permitted. On update/failure the fixed original A thread is notified for a CPU-only receipt. A transport receipt is not a handler ACK.
'''
    atomic(out/'RESULTS_FOR_PAPER.md',text)
    atomic(out/'MASTER_DOCUMENT_UPDATE.md', '# Exact merge fragment for analysis-owned master document\n\nDo not overwrite the shared master from executor A.\n\n'+text)
    captions=f'''# Figure and table captions / 图表说明

Snapshot {stamp}. Provenance and per-file timestamps are in SOURCE_INDEX.json; every PDF/SVG/PNG has a snapshot footer. LaTeX tables require booktabs. All plots are produced from saved scalars; no new timing or scientific execution.

**MAIN_H_CURVES.** EN: Fixed-source MT50 success versus native horizon H. Curves show N/R/Post/Velocity, with unavailable R cells left blank. Bands are pointwise95% percentile intervals from2000 within-task source bootstrap draws (seed20260921), conditional on50fixed tasks and frozen models. Historical five-task D/G0/Q coverage is unchanged; B/C additions are cross-host. CN：相同500源上的H扫描；阴影为固定50任务内重采样的逐点95%CI，并非训练seed区间；未完成R格留空，不据测试选择H。

**E3_GAF_PAIRED_FIGURE / E3_GAF_PAIRED.** EN: GAF minus each comparator on500paired H10sources. Positive values favor GAF. Rescues and harms denote discordant source outcomes. Intervals use the main fixed-task bootstrap; exact McNemar p values are Holm-adjusted across these four comparisons only. Training sets and native intervention semantics differ. CN：差值方向统一为GAF减对照，救回/损害按同源成败计算；四比较Holm范围不扩成整篇多重校正，CI仍为逐点。

**E1_LOSS_ABLATION_FIGURE / E1_LOSS_ABLATION_TABLE.** EN: Means and error bars are mean ± sample SD over three complete training seeds; dots are per-seed success rates on the same50test sources. Members of one ensemble are not fit seeds, and repeated test identities are not independent initial states. L11 is not consistently best. CN：误差条为三次完整fit的样本SD（ddof=1），不与其他图的95%CI混用；不预写L11最优。

**E6_TRIGGER_FIGURE / E6_TRIGGER_TABLE.** EN: Descriptive per-task success (10paired tests per task), comparing G0→R and D5→R under the same downstream R. No error bars. Separate100development episodes calibrate the D5 threshold;50paired tests yield26vs30successes, D5rescue5/harm1, exact paired p=.21875. The evidence does not establish a G0 advantage. CN：每任务10个配对测试，开发100另计；无误差条，不声称收益触发优于因果异常触发。

**E5_EFFECT_CALLS_FIGURE / E5_AMORTIZED_COST_TABLE.** EN: Success versus mean complete policy calls per valid episode (point labels indicate H), and total policy calls across all valid outcomes divided by successes. Mean calls within successful episodes is reported separately. Calls do not have equal compute cost; N's separately recorded sampling and per-entry timers are unavailable. Timing scopes and historical auxiliary-holder/cross-host effects preclude a controlled speed claim. CN：全部调用/成功数包含失败episode的成本，不能换成成功episode内均值；计数不代表等计算量或同机净模块耗时。

**E8_TABLE / E8_PAIRED.** EN: Latest valid subsets retain unresolved N outcomes (Smol4, LIBERO1) and C's updated paired intervals with their original uncertainty methods. LIBERO Post/Velocity are BCE operator transfers at a fixed intervention time without D/G0. Full remains untested, SCIENTIFIC_GAP, not0% and not relabelled operator transfer. CN：Full数值NR，未训练未测试；两种算子版相同总成功数不代表逐源完全相同。Smol/X额外π0.5特征网络开销另列NR。

**MAIN_FULL_MINUS_R_PAIRED.** EN: MT50 Post/Velocity minus same-H R on common valid source/seed identities. Pointwise within-task bootstrap95%CIs describe conditional source uncertainty, not training uncertainty; p values are descriptive and not covered by the four-GAF Holm family. “Full” here does not denote LIBERO Full. CN：主方法与R同H配对，救回/损害方向为Post或Velocity相对R；跨主机时间不作严格速度排名。
'''
    atomic(out/'CAPTIONS.md',captions)


def publish(terminals=None):
    terminals=terminals or {}
    stamp=utc();current=ROOT/'CURRENT.json'
    previous=json.loads(current.read_text()) if current.exists() else None
    rev=previous['revision']+1 if previous else 1
    out=ROOT/'revisions'/f'r{rev:02d}';out.mkdir(parents=True,exist_ok=False)
    if previous:
        prev=Path(previous['directory'])
        for p in prev.iterdir():
            if p.is_file() and p.name not in ['PUBLICATION.json','SOURCE_INDEX.json']:
                shutil.copy2(p,out/p.name)
        SOURCE_META.update(json.loads((prev/'SOURCE_INDEX.json').read_text())['sources'])
    else:
        initialize_static(out,stamp)
    state=build_dynamic(out,stamp,terminals)
    atomic(out/'SOURCE_INDEX.json',dict(snapshot_utc=stamp,sources=SOURCE_META,
        note='Terminal scalar files and existing statistics only; no model/image/tree hashing',
        static_material_origin=(json.loads((out/'STATIC_FACTS.json').read_text())['snapshot_utc'])))
    files=[dict(name=p.name,path=str(p),bytes=p.stat().st_size) for p in sorted(out.iterdir()) if p.is_file()]
    pub=dict(task_id=TASK,revision=rev,snapshot_utc=stamp,status='CURRENT_RESULTS_PUBLISHED',
        complete_main_cells=state['complete_cells'],valid_main_episodes=state['valid_episodes'],
        shared_test_source_identities=500,terminal_nodes=list(terminals),
        bootstrap=BOOT_SCOPE,files=files,source_index=str(out/'SOURCE_INDEX.json'),scientific_compute=0,holder_changes=0)
    atomic(out/'PUBLICATION.json',pub)
    for p in out.iterdir():
        link=ROOT/p.name
        if not link.exists() and not link.is_symlink():link.symlink_to(Path('CURRENT')/p.name)
    temporary=ROOT/('CURRENT.tmp.'+uuid.uuid4().hex);temporary.symlink_to(out.relative_to(ROOT));os.replace(temporary,ROOT/'CURRENT')
    atomic(current,dict(revision=rev,directory=str(out),snapshot_utc=stamp,publication=str(out/'PUBLICATION.json')))
    print(json.dumps(dict(publication=str(out/'PUBLICATION.json'),revision=rev,complete_cells=state['complete_cells'],valid_episodes=state['valid_episodes']),ensure_ascii=False),flush=True)
    assert 'torch' not in sys.modules
    return pub


if __name__=='__main__':
    if (ROOT/'CURRENT.json').exists():
        raise SystemExit('Initial publication already exists; observer owns incremental publication.')
    publish()
