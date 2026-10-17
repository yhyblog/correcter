"""Source-clustered paired analyses. Technical gaps are never negative outcomes."""
import collections,csv,json,math
from pathlib import Path
import paths
from paths import ROOT
from common import read,write,seed,terminal_path

def csvwrite(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def ci(values,groups):
    import numpy as np
    if not values:return dict(mean=None,lo=None,hi=None,n=0,parents=0)
    sums=collections.defaultdict(list)
    for v,g in zip(values,groups):sums[g].append(v)
    x=np.array([[sum(v),len(v)] for v in sums.values()]);rng=np.random.default_rng(92401)
    chosen=rng.integers(len(x),size=(1000,len(x)));s=x[chosen].sum(axis=1);dist=s[:,0]/s[:,1]
    return dict(mean=float(np.mean(values)),lo=float(np.quantile(dist,.025)),hi=float(np.quantile(dist,.975)),n=len(values),parents=len(x))

def main():
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    dest=ROOT/'analysis';dest.mkdir(exist_ok=True)
    rows=[];statuses=collections.Counter();byid={};missing=[]
    for phase in ['local','budget','cost']:
        p=ROOT/('JOBS_'+phase+'.json')
        if not p.exists():continue
        for j in read(p):
            rp=terminal_path(j)
            if not rp.exists():missing.append(j['id']);statuses['missing']+=1;continue
            r=read(rp);statuses[r['status']]+=1
            if r['status']!='complete' or not isinstance(r.get('success'),bool):continue
            r['phase']=phase;byid[j['id']]=r;rows.append(r)
    if (ROOT/'ALIASES.json').exists():
        for alias in read(ROOT/'ALIASES.json'):
            original=byid.get(alias['reuse_unit'])
            if original:
                r=dict(original,job=alias['job'],exact_raw_alias_of=alias['reuse_unit']);rows.append(r)
    local=[r for r in rows if r['job']['kind']=='branch'];closed=[r for r in rows if r['job']['kind']=='closed']
    flat=[]
    for r in rows:
        j=r['job'];flat.append(dict(unit=j['id'],source=j['source']['source_id'],task=j['source']['task'],phase=r['phase'],arm=j.get('arm'),rep=j.get('rep'),cut=r.get('cut'),suffix=j.get('suffix'),C=j.get('C'),H=j.get('H'),trigger=j.get('trigger'),threshold=j.get('threshold'),method=j.get('method'),success=r['success'],steps=r['steps'],interventions=r['interventions'],policy_calls=r['policy_calls'],inference_seconds=r['inference_seconds'],alias_of=r.get('exact_raw_alias_of')))
    csvwrite(dest/'VALID_OUTCOMES.csv',flat)
    paired={(r['job']['source']['source_id'],r['cut'],r['job']['rep'],r['job']['arm'],r['job']['C'],r['job']['suffix']):r for r in local}
    # A: different estimands remain separate; draw noise averaged within each cut.
    A=[];ranking=[];bins=[];source_scores={}
    for p in (ROOT/'pool').glob('*/cut*/FINAL_SCORE.json'):
        r=read(p);source_scores[r['source']['source_id'],r['cut']]=r['score']
    for C,suffix in [(5,'native10'),(10,'native10'),(10,'deploy10')]:
        statevalues=collections.defaultdict(list)
        for key,r in paired.items():
            s,cut,rep,arm,c,suf=key
            if (arm,c,suf)!=('R',C,suffix):continue
            old=paired.get((s,cut,rep,'continue',10,suffix))
            if old:statevalues[s,cut].append(int(r['success'])-int(old['success']))
        pool=[]
        for (s,cut),v in statevalues.items():
            score=source_scores.get((s,cut),{})
            row=dict(source=s,cut=cut,C=C,suffix=suffix,draws=len(v),gain=float(np.mean(v)),**score);A.append(row)
            if len(v)==4 and all(score.get(k) is not None for k in ['G0','D5','risk']):pool.append(row)
        if not pool:continue
        for fraction in np.arange(.1,1.01,.1):
            k=max(1,int(math.ceil(len(pool)*fraction)))
            for signal in ['G0','D5','risk','nod','random']:
                if signal=='nod' and any(r.get('nod') is None for r in pool):continue
                order=sorted(pool,key=lambda r:seed('rank',r['source'],r['cut'])) if signal=='random' else sorted(pool,key=lambda r:(-r[signal],r['source'],r['cut']))
                chosen=order[:k];ranking.append(dict(C=C,suffix=suffix,signal=signal,fraction=float(fraction),selected=k,pool=len(pool),**ci([r['gain'] for r in chosen],[r['source'] for r in chosen])))
        order=sorted(pool,key=lambda r:r['G0'])
        for b,ix in enumerate(np.array_split(np.arange(len(order)),5)):
            if not len(ix):continue
            selected=[order[i] for i in ix]
            bins.append(dict(C=C,suffix=suffix,bin=b,prediction=float(np.mean([r['G0'] for r in selected])),**ci([r['gain'] for r in selected],[r['source'] for r in selected])))
    csvwrite(dest/'A_STATE_GAINS.csv',A);csvwrite(dest/'A_RANKING.csv',ranking);csvwrite(dest/'A_BINS.csv',bins)
    # C/D: common a0, common suffix draw. Paired rescue and harm are retained.
    effects=[];metrics=[]
    for suffix in ['native10','deploy10']:
        for arm in sorted({r['job']['arm'] for r in local}-{'continue','R'}):
            pairs=[]
            for key,r in paired.items():
                s,cut,rep,a,C,suf=key
                if (a,C,suf)!=(arm,10,suffix):continue
                base=paired.get((s,cut,rep,'R',10,suffix))
                if base:pairs.append((r,base))
            vals=[int(r['success'])-int(b['success']) for r,b in pairs];groups=[r['job']['source']['source_id'] for r,b in pairs]
            stat=ci(vals,groups);effects.append(dict(suffix=suffix,arm=arm,**stat,rescue=float(np.mean(np.array(vals)==1)) if vals else None,harm=float(np.mean(np.array(vals)==-1)) if vals else None))
            if suffix=='native10' and arm in ['L00','L10','L01','L11'] and pairs:
                briers=[];bces=[];delta=collections.defaultdict(list);direction=collections.defaultdict(list)
                for r,b in pairs:
                    j=r['job'];meta=read(j['bank_meta']);pr=meta['predictions'][arm];p=pr['corrected']['candidate_mean_probability'];y=int(r['success']);briers.append((p-y)**2);p=np.clip(p,1e-7,1-1e-7);bces.append(float(-y*np.log(p)-(1-y)*np.log(1-p)))
                    delta[j['source']['source_id'],r['cut']].append((pr['corrected']['mean_gain'],y-int(b['success'])))
                    plus=paired.get((j['source']['source_id'],r['cut'],j['rep'],'probe_plus',10,suffix));minus=paired.get((j['source']['source_id'],r['cut'],j['rep'],'probe_minus',10,suffix))
                    if plus and minus:direction[j['source']['source_id'],r['cut']].append((pr['probe_plus']['candidate_mean_probability']-pr['probe_minus']['candidate_mean_probability'],int(plus['success'])-int(minus['success'])))
                errs=[abs(np.mean(v,axis=0)[0]-np.mean(v,axis=0)[1]) for v in delta.values()];correct=[]
                for v in direction.values():
                    predicted,actual=np.mean(v,axis=0)
                    if actual!=0:correct.append(float(np.sign(predicted)==np.sign(actual)))
                metrics.append(dict(loss=arm,brier=float(np.mean(briers)),BCE=float(np.mean(bces)),anchor_gain_MAE=float(np.mean(errs)),novel_direction_accuracy=float(np.mean(correct)) if correct else None,informative_direction_states=len(correct),paired_draws=len(pairs)))
    csvwrite(dest/'CD_LOCAL_EFFECTS.csv',effects);csvwrite(dest/'C_PREDICTION_METRICS.csv',metrics)
    operator_rows=[];operator_groups=collections.defaultdict(list);bank_count=0;metric_equal=0
    bankjobs=read(ROOT/'JOBS_banks.json') if (ROOT/'JOBS_banks.json').exists() else []
    for j in bankjobs:
        rp=terminal_path(j)
        if not rp.exists() or read(rp)['status']!='complete':continue
        m=read(read(rp)['metadata_path']);bank_count+=1;metric_equal+=m['metric_action_max_difference']<=1e-7
        for arm,d in m['diagnostics'].items():operator_groups[arm].append(dict(**d,seconds=m['repair_seconds'].get(arm)))
    for arm,vals in operator_groups.items():
        times=[x['seconds'] for x in vals if x['seconds'] is not None]
        operator_rows.append(dict(arm=arm,anchors=len(vals),zero_fraction=float(np.mean([x['zero'] for x in vals])),xyz_rms=float(np.mean([x['xyz_rms'] for x in vals])),gripper_rms=float(np.mean([x['gripper_rms'] for x in vals])),coordinate_limit_fraction=float(np.mean([x['boundary_fraction'] for x in vals])),mutable_fraction=float(np.mean([x['mask_fraction'] for x in vals])),mean_repair_seconds=float(np.mean(times)) if times else None,repair_time_scope='bank operator computation; compare online total costs separately'))
    csvwrite(dest/'D_OPERATOR_DIAGNOSTICS.csv',operator_rows)
    write(dest/'D_METRIC_EQUIVALENCE.json',dict(anchors=bank_count,equal_within_1e_7=metric_equal,reason='Group-common coordinate scale cancels during independent group normalization; raw-identical arms reuse exact matching outcomes, explicitly indexed in ALIASES.json.'))
    costs=[];grouped=collections.defaultdict(list)
    for r in closed:
        j=r['job'];grouped[r['phase'],j['H'],j['trigger'],j['threshold'],j['method']].append(r)
    for (phase,H,trig,thr,method),rs in grouped.items():
        stat=ci([int(r['success']) for r in rs],[r['job']['source']['source_id'] for r in rs]);costs.append(dict(phase=phase,H=H,trigger=trig,threshold=thr,method=method,expected_parents=100,**stat,actual_interventions=float(np.mean([r['interventions'] for r in rs])),policy_calls=float(np.mean([r['policy_calls'] for r in rs])),monitor_calls=float(np.mean([r['monitors'] for r in rs])),action_gradients=float(np.mean([r['action_gradients'] for r in rs])),inference_seconds=float(np.mean([r['inference_seconds'] for r in rs])),total_inference_seconds=sum(r['inference_seconds'] for r in rs),rpc_seconds=float(np.mean([r['rpc_seconds'] for r in rs]))))
    csvwrite(dest/'BE_SUCCESS_COST.csv',costs)
    latency=[]
    for key,rs in grouped.items():
        if key[0]!='cost':continue
        for kind in ['plan','monitor','intervene']:
            vals=[v for r in rs for v in r.get('warm_timing_samples',{}).get(kind,[])]
            if vals:latency.append(dict(H=key[1],trigger=key[2],method=key[4],operation=kind,n=len(vals),mean_seconds=float(np.mean(vals)),p50=float(np.quantile(vals,.5)),p95=float(np.quantile(vals,.95)),p99=float(np.quantile(vals,.99)),concurrency_per_gpu=1,batch_size=1,warmup='exclude first occurrence per episode'))
    csvwrite(dest/'E_LOCAL_LATENCY.csv',latency)
    def savefig(name):
        plt.tight_layout();plt.savefig(dest/(name+'.png'),dpi=180);plt.savefig(dest/(name+'.pdf'));plt.close()
    if ranking:
        fig,ax=plt.subplots(figsize=(6,4))
        for sig in ['G0','D5','risk','nod','random']:
            r=[x for x in ranking if x['C']==10 and x['suffix']=='native10' and x['signal']==sig]
            ax.plot([x['fraction'] for x in r],[x['mean'] for x in r],marker='o',label=sig)
        ax.set(xlabel='Fraction selected in frozen state pool',ylabel='Paired replan success gain');ax.legend();savefig('A_GAIN_RANKING')
    if bins:
        fig,ax=plt.subplots(figsize=(6,4))
        for C,suffix in [(5,'native10'),(10,'native10'),(10,'deploy10')]:
            r=[x for x in bins if x['C']==C and x['suffix']==suffix]
            ax.plot([x['prediction'] for x in r],[x['mean'] for x in r],marker='o',label=f'C{C}/{suffix}')
        ax.set(xlabel='Mean G0 score',ylabel='Paired actual replan gain');ax.legend();savefig('A_GAIN_BINS')
    if A:
        r=[x for x in A if x['C']==10 and x['suffix']=='native10' and x.get('D5') is not None]
        if r:
            fig,ax=plt.subplots(figsize=(6,4));sc=ax.scatter([x['D5'] for x in r],[x['gain'] for x in r],c=[x['G0'] for x in r],s=22);fig.colorbar(sc,label='G0 benefit score');ax.set(xlabel='Causal D5 error',ylabel='Replan gain');savefig('A_ANOMALY_GAIN')
    if effects:
        r=[x for x in effects if x['suffix']=='native10' and x['mean'] is not None];fig,ax=plt.subplots(figsize=(9,4));ax.bar([x['arm'] for x in r],[x['mean'] for x in r],yerr=np.maximum(0,np.array([[x['mean']-x['lo'] for x in r],[x['hi']-x['mean'] for x in r]])),capsize=3);ax.axhline(0,color='black',linewidth=.7);ax.tick_params(axis='x',rotation=50);ax.set(ylabel='Paired gain over same raw a0');savefig('CD_REPAIR_GAIN')
    for phase in ['budget','cost']:
        r=[x for x in costs if x['phase']==phase]
        if r:
            fig,ax=plt.subplots(figsize=(7,4))
            for label in sorted({x['trigger'] if phase=='budget' else x['method'] for x in r}):
                group=[x for x in r if (x['trigger'] if phase=='budget' else x['method'])==label];group.sort(key=lambda x:x['inference_seconds']);ax.plot([x['inference_seconds'] for x in group],[x['mean'] for x in group],marker='o',label=label)
            ax.set(xlabel='Mean synchronized inference service seconds / episode',ylabel='Success rate');ax.legend();savefig('B_BUDGET' if phase=='budget' else 'E_COST_EFFECT')
    coverage=[]
    for s in read(ROOT/'SOURCES.json'):
        cuts=sorted(read(p)['cut'] for p in (ROOT/'pool'/s['source_id']).glob('cut*/snapshot/STATE.json'))
        coverage.append(dict(source=s['source_id'],split=s['split'],task=s['task'],planned_cuts='5;25;75',captured_cuts=';'.join(map(str,cuts)),captured_count=len(cuts),no_cut=len(cuts)==0))
    csvwrite(dest/'STATE_POOL_COVERAGE.csv',coverage)
    summary=dict(status='analysis_exported',real_units=dict(statuses),raw_aliases=len(rows)-len(byid),missing_units=missing,local_paired_rows=len(local),closed_episodes=len(closed),A_states=len(A),scope='five trained auxiliary tasks; fresh parent episodes; not unseen-task transfer',uncertainty='1000 paired parent-cluster bootstrap draws',technical_missing_imputed=False,thresholds_selected_on_test=False,local_cost_not_full_episode_cost=True)
    write(dest/'SUMMARY.json',summary)
    (dest/'RESULTS.md').write_text('# Supplemental mechanism experiments\n\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n\nA_STATE_GAINS, CD_LOCAL_EFFECTS, C_PREDICTION_METRICS, BE_SUCCESS_COST and E_LOCAL_LATENCY contain the primary inspectable values. A ranking uses complete four-draw labels and the common available-score pool; missing comparisons remain excluded with counts. Each local condition keeps the original 300-step total budget. Native10 and the C10/Post/G0-multi deployment suffix are separate estimands. No significance claim follows merely from the point estimate.\n\nRisk has the same causal inputs/capacity as G0, with failure supervision and parent-balanced sampling. The no-D model is retrained with the effect input fixed to zero throughout fitting and inference. Historical G0 used cut sampling, so this is not an exact training-random-stream-only loss switch.\n\nCost figures use the separate E stage with one simulator per GPU; serialized model service time includes synchronization and excludes RPC queue wait, which is reported separately. Diagnostic bank generation is separate from online Post cost.\n')
    return summary

if __name__=='__main__':print(json.dumps(main()))
