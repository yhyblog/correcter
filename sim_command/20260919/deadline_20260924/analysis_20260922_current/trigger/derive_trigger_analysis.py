from pathlib import Path
import csv,json,math,statistics,collections,datetime
P=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
O=Path(__file__).parent
roots={'Velocity':P/'results/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RECOVERY_r3','Post':P/'results/B/B_D24_POST_TRIGGER_MODES_V1/recovery_r3','R':P/'results/C/C_D24_R_TRIGGER_MODES_V1'}
def readcsv(p): return list(csv.DictReader(open(p)))
def dump(n,obj): (O/n).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def writecsv(n,rows):
 with open(O/n,'w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def ok(r):
 assert r['success'].lower() in ['true','false']
 return r['success'].lower()=='true'
def pct(xs,q):
 xs=sorted(xs); pos=(len(xs)-1)*q;i=int(pos);return xs[i]+(xs[min(i+1,len(xs)-1)]-xs[i])*(pos-i)
def number(r,k): return None if r.get(k) in [None,'','null','None'] else float(r[k])
def pair(left,right):
 assert left.keys()==right.keys()
 c=collections.Counter((ok(left[k]),ok(right[k])) for k in left)
 n=len(left);resc=c[True,False];harm=c[False,True]
 return dict(paired_valid=n,left_successes=c[True,True]+resc,right_successes=c[True,True]+harm,rescued=resc,harmed=harm,both_success=c[True,True],both_failure=c[False,False],difference_pp=100*(resc-harm)/n)
def mcnemar(a,b):
 n=a+b
 return min(1.,2*sum(math.comb(n,k) for k in range(min(a,b)+1))/2**n) if n else 1.
sourcefile=P/'deadline_20260924/TRIGGER_MODE_SOURCES_V1.json';sources=json.load(open(sourcefile))['rows'];source_ids={r['source_id'] for r in sources};assert len(source_ids)==500
mainpath=P/'results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/MAIN_20CELL_TABLE.csv';main=readcsv(mainpath)
nbase={int(r['H']):int(r['successes']) for r in main if r['method']=='N'}
bases=[P/'results/A/A_D24_MAIN_ONCE_V1/FINAL_EPISODES.csv',P/'results/B/B_D24_R_H20_H30_V1/FINAL_EPISODES.csv',P/'results/C/C_D24_R_H40_H50_V1/r2/EPISODES.csv']
groups=collections.defaultdict(dict);inputpaths=[str(mainpath),str(sourcefile)]+[str(x) for x in bases]
for p in bases:
 for r in readcsv(p):
  key=(r['method'],'G0-once',int(r['H'])); sid=r['source_id'];assert sid not in groups[key];groups[key][sid]=r
for b,root in roots.items():
 p=root/'FINAL_EPISODES.csv';inputpaths.append(str(p))
 for r in readcsv(p):
  key=(b,r['mode'],int(r['H']));sid=r['source_id'];assert sid not in groups[key];groups[key][sid]=r
checks=[];cells=[]
for (b,mode,h),d in sorted(groups.items()):
 assert len(d)==500 and d.keys()==source_ids
 taskcount=collections.Counter(r['task'] for r in d.values());assert len(taskcount)==50 and set(taskcount.values())=={10}
 assert all(r['status']=='complete' for r in d.values())
 assert all(int(r['ordinal']) in range(10) for r in d.values())
 if mode!='G0-once':
  for sid,r in d.items():
   old=groups[b,'G0-once',h][sid]
   assert all(r[k]==old[k] for k in ['source_id','env_seed','policy_seed','task','ordinal'])
 ints=[int(r['interventions']) for r in d.values()];success=sum(ok(r) for r in d.values())
 calls=[number(r,'policy_calls') for r in d.values()];assert all(x is not None for x in calls)
 counterkeys=['counter_sampling','counter_flow','counter_Q_ensemble_forward','counter_action_gradients','counter_D_forward','counter_G0_forward']
 out=dict(branch=b,mode=mode,H=h,valid=500,successes=success,success_rate_pct=success/5,unresolved_technical_or_missing=0,trigger_zero=ints.count(0),trigger_once=ints.count(1),trigger_ge2=sum(x>=2 for x in ints),trigger_mean=statistics.mean(ints),trigger_median=statistics.median(ints),trigger_p95=pct(ints,.95),trigger_max=max(ints),first_cut5=sum(r['first_cut']=='5' for r in d.values()),policy_calls_valid_total=int(sum(calls)),policy_calls_valid_mean=statistics.mean(calls),all_valid_calls_per_success=sum(calls)/success)
 for k in counterkeys:
  vals=[number(r,k) for r in d.values()];out[k+'_valid_total']=int(sum(vals)) if all(x is not None for x in vals) else None
 out['cost_scope']='all500 valid episodes including task failures; historical technical attempts excluded here and separately preserved'
 cells.append(out);checks.append(dict(branch=b,mode=mode,H=h,unique_sources=500,tasks=50,per_task=10,status_complete=500,identity_matches_once=True))
ci_map={}
for b,root in roots.items():
 path=root/'FINAL_PAIRED.csv';inputpaths.append(str(path))
 for r in readcsv(path):
  mode=r.get('mode') or r['comparison'].split(' - ')[0]; h=int(r['H'])
  if b=='Post': ci=json.loads(r['pointwise95_CI_pp'])
  elif b=='R': ci=[float(r['bootstrap95_low_pp']),float(r['bootstrap95_high_pp'])]
  else: ci=[float(r['CI95_low_pp']),float(r['CI95_high_pp'])]
  ci_map[b,mode,h]=(ci,r,str(path))
comparisons=[]
for b in ['R','Post','Velocity']:
 for mode in ['Random-once','G0-multi']:
  for h in [10,20,30,40,50]:
   s=pair(groups[b,mode,h],groups[b,'G0-once',h]);ci,saved,path=ci_map[b,mode,h]
   assert (s['rescued'],s['harmed'])==(int(saved['rescued']),int(saved['harmed']))
   s.update(branch=b,mode=mode,H=h,comparison=mode+' - G0-once',CI95_pointwise_low_pp=ci[0],CI95_pointwise_high_pp=ci[1],CI_provenance='transcribed existing executor fixed-task within-task bootstrap2000 seed20260921',CI_source=path,p_exact_two_sided_mcnemar=mcnemar(s['rescued'],s['harmed']),p_provenance='new CPU math.comb exact binomial calculation from validated discordant pairs',holm_family=mode+' vs G0-once,15 contrasts across3branches x5H')
   comparisons.append(s)
for mode in ['Random-once','G0-multi']:
 ordered=sorted([r for r in comparisons if r['mode']==mode],key=lambda r:r['p_exact_two_sided_mcnemar']);prev=0
 for i,r in enumerate(ordered):
  p=min(1,max(prev,(15-i)*r['p_exact_two_sided_mcnemar']));prev=p;r['p_Holm_15']=p;r['Holm_reject_0_05']=p<.05
cross=[]
for mode in ['G0-once','Random-once','G0-multi']:
 for b in ['Post','Velocity']:
  for h in [10,20,30,40,50]:
   s=pair(groups[b,mode,h],groups['R',mode,h]);s.update(mode=mode,H=h,comparison=b+' - R',CI95=None,statistical_scope='new CPU paired counts and nominal exact McNemar; exploratory, no multiple-comparison-adjusted significance claim',p_exact_two_sided_unadjusted_descriptive=mcnemar(s['rescued'],s['harmed']));cross.append(s)
wide=[]
for h in [10,20,30,40,50]:
 r=dict(H=h,N_successes=nbase[h],N_pct=nbase[h]/5,cell_n=500)
 for b in ['R','Post','Velocity']:
  for mode in ['G0-once','Random-once','G0-multi']:
   s=sum(ok(x) for x in groups[b,mode,h].values());r[b+'_'+mode+'_successes']=s;r[b+'_'+mode+'_pct']=s/5
 wide.append(r)
cellmap={(r['branch'],r['mode'],r['H']):r for r in cells}
cost=[]
for b in ['R','Post','Velocity']:
 for h in [10,20,30,40,50]:
  once=cellmap[b,'G0-once',h];multi=cellmap[b,'G0-multi',h]
  cost.append(dict(branch=b,H=h,once_successes=once['successes'],multi_successes=multi['successes'],success_delta_pp=multi['success_rate_pct']-once['success_rate_pct'],once_trigger_mean=once['trigger_mean'],multi_trigger_mean=multi['trigger_mean'],once_policy_calls_mean=once['policy_calls_valid_mean'],multi_policy_calls_mean=multi['policy_calls_valid_mean'],policy_calls_pct_increase=100*(multi['policy_calls_valid_total']/once['policy_calls_valid_total']-1),once_all_calls_per_success=once['all_valid_calls_per_success'],multi_all_calls_per_success=multi['all_valid_calls_per_success'],all_calls_per_success_pct_increase=100*(multi['all_valid_calls_per_success']/once['all_valid_calls_per_success']-1),cost_scope='valid500 episodes; technical-retry overhead separately retained'))
writecsv('TRIGGER_SUCCESS_TABLE.csv',wide);writecsv('TRIGGER_CELLS_AND_COSTS.csv',cells);writecsv('PAIRED_TIMING_MULTIPLICITY_WITH_HOLM.csv',comparisons);writecsv('FULL_MINUS_R_PAIRED_DESCRIPTIVE.csv',cross);writecsv('MULTI_ONCE_COST_COMPARISON.csv',cost)
# Preserve historical operational failures separately from final scientific coverage.
coverage={'new_cells':30,'new_valid_episodes':15000,'unique_initial_sources':500,'reused_once_cells':15,'reused_once_valid_episodes':7500,'reused_N_cells':5,'reused_N_valid_episodes':2500,'total_unique_cell_episode_outcomes':25000,'stage_attempts':{'Velocity':5016,'Post':5009,'R':5000},'historical_technical_attempts':{'Velocity':16,'Post':9,'R':0},'unresolved_scientific_outcomes':0,'counter_note':'5000 scientific outcomes per branch. Historical 25 failed attempts kept and not relabeled success=false. Post failure-to-cell attribution can be incomplete in final cells; use stage count.'}
summary={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_paths':inputpaths,'coverage':coverage,'validation':'Basic CSV key/count/status/envseed/policyseed pairing and saved paired-count arithmetic; no model/GPU/source-code/full-state/hash audit.','checks':checks,'statistics':{'reused':'pointwise bootstrap2000 within fixed50tasks, seed20260921','new':'elementary paired counts, exact two-sided McNemar and separate15-comparison Holm per newmode','not_performed':'new bootstrap, model training, scientific launches, selection of best method on heldout'},'tables':wide,'paired':comparisons,'costs':cost,'cross_branch':cross,'limitations':['Same previously revealed500 sources; supplementary not fresh confirmatory validation.','G0-once actual intervention rates differ from Random-once; compare executable strategies, not pure timing at fixed realized budget.','Auxiliary D/G0/Q are historical five-task heads, no fullMT50 refit.','Post/Velocity/R ran on different hosts; compare logical calls cautiously, do not claim controlled timing superiority.','Random logs shadowD/G0 whose time/cost is included; do not describe this as minimal deployable random cost.','Table cost recomputation covers all valid task episodes, excluding historical technical-retry overhead retained in original receipts.','Task/source/bootstrap uncertainty does not include independent training seeds.']}
dump('TRIGGER_ANALYSIS.json',summary)
print('SUCCESS TABLE')
for r in wide: print(r)
print('HOLM')
for r in comparisons:print(r['branch'],r['mode'],r['H'],r['difference_pp'],r['rescued'],r['harmed'],r['p_Holm_15'])
print('MULTI COST')
for r in cost:print(r['branch'],r['H'],round(r['policy_calls_pct_increase'],1),round(r['all_calls_per_success_pct_increase'],1))
print('MULTI FULL-R')
for r in cross:
 if r['mode']=='G0-multi': print(r)

# Optional descriptive N_H10 scalar reference is transcribed separately in HIGH_H_POLICY_CALL_TRADEOFF.json; no cross-H paired CI computed.
