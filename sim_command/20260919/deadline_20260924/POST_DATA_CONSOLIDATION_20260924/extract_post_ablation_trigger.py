import csv
import json
import statistics
from pathlib import Path
from collections import defaultdict

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
P = ROOT / 'Corrector/sim_command/20260919'
SOURCES = {
    'full_q_result': P / 'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json',
    'full_q_episodes': P / 'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/TECHNICAL_EPISODES_ALL_METHODS.csv',
    'l11_rollup': P / 'deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json',
    'l11_pairs': P / 'deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_L11_POST_PAIRED_STATS.json',
    'r_trigger_costs': P / 'deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv',
    'r_trigger_pairs': P / 'results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_PAIRED.json',
    'e6_once': P / 'results/A/A_D24_CORE_REMAINDER_V1/E6_FINAL_SUMMARY.json',
    'e6_multi': P / 'deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json',
    'e6_multi_pairs': P / 'results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/PAIRED.json',
}
def js(k): return json.loads(SOURCES[k].read_text())
def rows(k): return list(csv.DictReader(SOURCES[k].open()))
def val(s): return s.strip().lower() == 'true'
out = {'scope': 'Post only final full-Q ablation; L11 Post modes; Q-independent R trigger controls. Existing result aggregation only; no new experiment/bootstrap/test.', 'sources': {k: str(v) for k,v in SOURCES.items()}}

episodes = [r for r in rows('full_q_episodes') if r['method']=='Post' and r['stage'] in {'DEV','ABLATION'}]
assert len(episodes)==1800
assert len({r['unit_id'] for r in episodes})==1800
assert all(r['status']=='complete' and not r['technical_failure'] for r in episodes)
groups=defaultdict(list)
for r in episodes: groups[(r['loss'],r['stage'],int(r['fit_seed']))].append(r)
cells=[]
official=js('full_q_result')['compute_summary']['cells']
for (loss,stage,fit), rr in sorted(groups.items()):
    n=100 if stage=='DEV' else 50
    assert len(rr)==n
    successes=sum(val(r['success']) for r in rr)
    official_cell=official[f'{stage}_{loss}_s{fit}_Post_H10']
    assert official_cell['successes']==successes and official_cell['terminals']==n
    r={'loss':loss,'stage':stage,'fit_seed':fit,'H':10,'method':'Post','mode':'G0-multi','valid':n,'unique_sources':len({r['source_id'] for r in rr}),'successes':successes,'success_rate_pct':100*successes/n,'technical_missing':0}
    for field in ['sampling_calls','flow_calls','interventions','counter_action_gradients']:
        vs=[float(x[field]) for x in rr if x[field] not in ('','null','None')]
        r[field+'_observed_n']=len(vs)
        r[field+'_total']=sum(vs)
        r[field+'_mean']=sum(vs)/n if len(vs)==n else None
    cells.append(r)
out['full_q_post_cells']=cells
labels={'L00':'BCE','L10':'BCE + gain','L01':'BCE + 0.5pair','L11':'BCE + gain + 0.5pair'}
summary=[]
for loss in ['L00','L10','L01','L11']:
    row={'loss':loss,'objective':labels[loss],'selected_final':loss=='L11'}
    for stage,key in [('DEV','development'),('ABLATION','revealed_selection50')]:
        rr=sorted([r for r in cells if r['loss']==loss and r['stage']==stage], key=lambda r:r['fit_seed'])
        values=[r['success_rate_pct'] for r in rr]
        row[key]={'fit_seeds':[r['fit_seed'] for r in rr],'successes':[r['successes'] for r in rr],'n_per_fit':rr[0]['valid'],'sr_pct_per_fit':values,'mean_sr_pct':statistics.mean(values),'sample_sd_sr_pct':statistics.stdev(values),'sampling_calls_mean_over_evaluations':sum(r['sampling_calls_total'] for r in rr)/sum(r['valid'] for r in rr),'interventions_mean_over_evaluations':sum(r['interventions_total'] for r in rr)/sum(r['valid'] for r in rr)}
    summary.append(row)
out['full_q_post_summary']=summary
out['ablation_notes']=[
    'Every member trained from untrained initialization with all Q parameters trainable; four losses x three fits x four members, 4000 updates/member. No old residual/advantage-only fine-tuning mixed in.',
    'Development uses five tasks x 20 distinct sources=100; revealed supplementary selection uses five tasks x 10 sources=50. Three fits reuse the same source set. 3 x 50 is not 150 independent states.',
    'L11 chosen by user from revealed selection50: highest three-fit mean tied with L00; L11 has smaller observed sample SD among tied best means. L10 has smaller SD but lower mean. Deployment fit9101 fixed.',
    'Selection50 overlaps MT50 main500. L11 H10 main result reuses 50 ablation results. Do not describe main500 as untouched blind test.',
    'Historical development-only selection chose L01. It is preserved history and is not current L11 selection evidence.',
    'Call means added here use direct sums over saved valid episode rows; costs include valid task failures, no new inference or tests.',
]

trigger=[]
for c in js('l11_rollup')['cells']:
    if c['model']=='pi05' and c['method']=='Post' and c['H']==10:
        trigger.append({'scope':'MT50 main500; L11 fit9101 Post', 'method':'Post','mode':c['mode'],'H':10,'valid':c['valid'],'successes':c['successes'],'sr_pct':100*c['success_rate'],'policy_calls_total':c['sampling_calls_observed_sum'],'policy_calls_mean':c['sampling_calls_mean'],'flow_calls_total':c['flow_calls_observed_sum'],'interventions_total':c['interventions_observed_sum'],'interventions_mean':c['interventions_mean'],'source':'l11_rollup'})
for r in rows('r_trigger_costs'):
    if r['branch']!='R': continue
    trigger.append({'scope':'MT50 main500; Q-independent R','method':'R','mode':r['mode'],'H':int(r['H']),'valid':int(r['valid']),'successes':int(r['successes']),'sr_pct':float(r['success_rate_pct']),'policy_calls_total':int(r['policy_calls_valid_total']),'policy_calls_mean':float(r['policy_calls_valid_mean']),'flow_calls_total':int(r['counter_flow_valid_total']),'interventions_total':round(float(r['trigger_mean'])*int(r['valid'])),'interventions_mean':float(r['trigger_mean']),'intervention_episode_counts':{'zero':int(r['trigger_zero']),'one':int(r['trigger_once']),'two_or_more':int(r['trigger_ge2'])},'source':'r_trigger_costs'})
out['trigger_modes_main500']=trigger
out['l11_post_multi_once_pair']=next(c for c in js('l11_pairs')['comparisons'] if 'multi' in c['comparison'])
out['r_trigger_paired_as_published']=js('r_trigger_pairs')
out['trigger_notes']=[
    'R has no Q so these once/random/multi data remain reusable after L11 change. Historical Post random-once uses old Q; do not relabel it L11.',
    'Random-once schedule fixed before execution, independent of trajectory/G0/outcome; before-slot termination or invalid slot does not trigger retry, forced intervention or another sampled time.',
    'G0-once and Random-once actual intervention rates differ. Difference is policy-level mechanism evidence, not perfectly intervention-count matched pure timing effect.',
    'R paired bootstrap intervals are previously published 2000 within-task replicates seed20260921; pointwise, not multiple-corrected. L11 Post multi-once has separately published paired normal interval and exact McNemar p. Do not mix interval definitions.',
]

e6=[]
once=js('e6_once')
for k in ['G0','D5']:
    c=once['cells'][k];n=c['terminal_episodes']
    e6.append({'scope':'E6 disjoint five-task ordinal10..19 test50','method':'R','mode':f'{k}-once','H':10,'valid':n,'successes':c['successes'],'sr_pct':100*c['successes']/n,'policy_calls_total':c['sampling_calls'],'policy_calls_mean':c['sampling_calls']/n,'flow_calls_total':c['flow_calls'],'interventions_total':c['interventions'],'interventions_mean':c['interventions']/n,'intervention_episode_counts':{'zero':n-c['interventions'],'one':c['interventions'],'two_or_more':0},'source':'e6_once'})
for c in js('e6_multi')['e6_multi']:
    e6.append({'scope':'E6 disjoint five-task ordinal10..19 test50','method':'R','mode':c['mode'],'H':c['H'],'valid':c['n'],'successes':c['successes'],'sr_pct':100*c['success_rate'],'policy_calls_total':c['total']['sampling_calls'],'policy_calls_mean':c['mean']['sampling_calls'],'flow_calls_total':c['total']['flow_calls'],'interventions_total':c['total']['interventions'],'interventions_mean':c['mean']['interventions'],'intervention_episode_counts':c['trigger_episode_counts'],'source':'e6_multi'})
out['e6_trigger_rows']=e6
out['e6_once_pair_as_published']={'comparison':'D5-once minus G0-once','n':50,'rescued':5,'harmed':1,'both_success':25,'both_failure':19,'difference_pp':8.0,'mcnemar_exact_two_sided_p':0.21875,'ci':None,'ci_missing_reason':'No existing interval copied; no new test/bootstrap performed.'}
out['e6_multi_pair_as_published']=js('e6_multi_pairs')
out['e6_notes']=[
    'Separate five tasks x ten test ordinals10..19, disjoint from main ordinals0..9; same 50 reused across once/multi, H10/C10.',
    'D5 threshold0.2521600950570383 fixed on 100 development sources by matching95/100 hypothetical alarms, without reading success; not an equal multi-opportunity intervention budget.',
    'G0 did not beat D5 in observed once or multi outcomes. Multi reduces interventions vs D5 but increases policy calls; do not claim better SR or lower system cost.',
]

Path('/tmp/POST_ABLATION_TRIGGER_TABLES.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
md=['# Post ablation / trigger consolidation: source extraction','', '## Complete-Q loss ablation (same row per loss)', '', '| Loss | DEV three-fit SR (%) | DEV mean ± sample SD | Revealed50 three-fit SR (%) | Revealed50 mean ± sample SD | DEV Policy Calls | Revealed50 Policy Calls | Selected |','|---|---|---:|---|---:|---:|---:|---|']
for r in summary:
    d=r['development'];a=r['revealed_selection50']
    md.append(f"| {r['loss']}: {r['objective']} | {' / '.join(f'{v:.1f}' for v in d['sr_pct_per_fit'])} | {d['mean_sr_pct']:.2f} ± {d['sample_sd_sr_pct']:.2f} | {' / '.join(f'{v:.1f}' for v in a['sr_pct_per_fit'])} | {a['mean_sr_pct']:.2f} ± {a['sample_sd_sr_pct']:.2f} | {d['sampling_calls_mean_over_evaluations']:.3f} | {a['sampling_calls_mean_over_evaluations']:.3f} | {'Yes' if r['selected_final'] else 'No'} |")
md.extend(['','Fit order9101/9102/9103. DEV denominator100 each; revealed selection denominator50 each. Call means pool3fits because denominators equal; values are not SD.','']+['- '+n for n in out['ablation_notes']])
md.extend(['','## Modes: L11 Post and Q-independent R; same standard columns','', '| Scope | Method | Trigger / Count | H | SR (%) | Policy Calls | Mean Interventions |','|---|---|---|---:|---:|---:|---:|'])
order={'G0-once':0,'Random-once':1,'G0-multi':2}
for r in sorted(trigger,key=lambda r:(r['method']!='Post',r['H'],order[r['mode']])):
    md.append(f"| {r['scope']} | {r['method']} | {r['mode']} | {r['H']} | {r['sr_pct']:.1f} | {r['policy_calls_mean']:.3f} | {r['interventions_mean']:.3f} |")
md.extend(['']+['- '+n for n in out['trigger_notes']])
md.extend(['','## E6 trigger controls: separate50-source scope','', '| Method | Trigger / Count | H | SR (%) | Policy Calls | Mean Interventions | n0/n1/n≥2 |','|---|---|---:|---:|---:|---:|---|'])
for r in e6:
    x=r['intervention_episode_counts'];md.append(f"| R | {r['mode']} | 10 | {r['sr_pct']:.1f} | {r['policy_calls_mean']:.3f} | {r['interventions_mean']:.3f} | {x['zero']}/{x['one']}/{x['two_or_more']} |")
md.extend(['']+['- '+n for n in out['e6_notes']])
md.extend(['','## Sources','']+['- '+k+': `'+str(p)+'`' for k,p in SOURCES.items()])
Path('/tmp/POST_ABLATION_TRIGGER_NOTES.md').write_text('\n'.join(md)+'\n')
print(json.dumps({'ablation_cells':len(cells),'main_trigger_rows':len(trigger),'e6_rows':len(e6),'files':['/tmp/POST_ABLATION_TRIGGER_TABLES.json','/tmp/POST_ABLATION_TRIGGER_NOTES.md']},ensure_ascii=False))
