"""Existing LIBERO and MT50 difficulty/task summaries; CPU aggregation only."""
import csv
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
P = ROOT/'Corrector/sim_command/20260919'
D = P/'deadline_20260924'
F = D/'FINAL_DATA_CONSOLIDATION_20260923'
DOCS = ROOT/'Corrector/docs'
OUT = Path(__file__).resolve().parent
APP = OUT/'appendix_data'
APP.mkdir(exist_ok=True)

def load(p):
    return json.loads(Path(p).read_text())

def rows(p):
    with Path(p).open() as f:
        return list(csv.DictReader(f))

def jsave(p,x):
    Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def csave(name,x):
    with (APP/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(x[0]));w.writeheader();w.writerows(x)

def table(h,rr):
    return '\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']+['| '+' | '.join(str(x) for x in r)+' |' for r in rr])

def link(p,title):
    return f'[{title}]({p})'

def boolean(x):
    if isinstance(x,bool):return x
    assert str(x).lower() in ('true','false'),x
    return str(x).lower()=='true'

def number(x):
    return None if x in (None,'') else float(x)

for name in ['POST_LIBERO_APPENDIX_DATA.json','POST_LIBERO_APPENDIX_NOTES.md','POST_MW_TASK_DIFFICULTY.json','POST_DIFFICULTY_DESIGN.md','POST_H10_CROSSBASE_EPISODES.csv','POST_H10_CROSSBASE_TASKS.csv','POST_H10_CROSSBASE_SOURCES.json','extract_post_h10_crossbase.py','POST_EXTERNAL_FINE_DATA.json','POST_EXTERNAL_FINE_TASKS.csv','POST_EXTERNAL_FINE_GROUPS.csv','POST_EXTERNAL_FINE_EPISODES.csv','POST_VERY_HARD_SELECTION_OVERLAP.json','POST_APPENDIX_BC_REVIEW.json']:
    if (Path('/tmp')/name).exists():shutil.copy2(Path('/tmp')/name,APP/name)

mapping=load(APP/'POST_MW_TASK_DIFFICULTY.json')
diff=mapping['task_to_difficulty']
groups=mapping['group_order']
assert len(diff)==50 and {g:list(diff.values()).count(g) for g in groups}==mapping['group_counts']
disp={'pi05':'π0.5','SmolVLA':'SmolVLA','X-VLA':'X-VLA'}
horizons={'pi05':[10,20,30,40,50],'SmolVLA':[10,20,30,40,50],'X-VLA':[10,20,30]}
sources=[]
episodes=[]

def add(model,h,method,x,src,task=None):
    task=task or x.get('task')
    assert task in diff,task
    call=x.get('sampling_calls')
    if call in ('',None):call=x.get('policy_calls')
    assert call not in ('',None),(src,x.get('source_id'))
    episodes.append(dict(model=model,H=int(h),method=method,source_id=x['source_id'],task=task,difficulty=diff[task],success=boolean(x['success']),policy_calls=number(call),interventions=number(x.get('interventions',0 if method=='N' else None)),source_table=str(src),result_path=x.get('result_path','')))

for src in sorted((D/'A/runs').glob('N_H*/RESULT.json')):
    doc=load(src);assert doc['technical_failures']==0
    sources.append(str(src))
    for x in doc['episodes']:add('pi05',x['H'],'N',x,src)
src=P/'results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_EPISODES.csv';sources.append(str(src))
for x in rows(src):
    if x['method']=='R' and x['mode']=='G0-multi':add('pi05',x['H'],'R',x,src)
src=D/'L11_FINAL_ROLLUP_20260923/FINAL_EPISODES.csv';sources.append(str(src))
for x in rows(src):
    if (x['model'],x['method'],x['mode'])==('pi05','Post','G0-multi'):
        assert x['loss']=='L11' and int(x['fit_seed'])==9101
        task=x['source_id'].removeprefix('D24_NEW_TEST_').rsplit('_',1)[0]
        add('pi05',x['H'],'Post',x,src,task)
src=F/'FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv';sources.append(str(src))
for x in rows(src):
    if x['method'] in ['N','R','Post']:add(x['model'],x['H'],x['method'],x,src)
src=APP/'POST_H10_CROSSBASE_EPISODES.csv';sources.append(str(src))
for x in rows(src):add(x['model'],10,x['method'],x,src)
assert len(episodes)==19496
keys=[(x['model'],x['H'],x['method'],x['source_id']) for x in episodes]
assert len(set(keys))==len(keys)
task_buckets=defaultdict(list)
for x in episodes:task_buckets[(x['model'],x['H'],x['method'],x['task'])].append(x)
assert len(task_buckets)==1950

task_metrics={}
for key,ee in task_buckets.items():
    model,h,method,task=key
    cv=[x['policy_calls'] for x in ee if x['policy_calls'] is not None]
    iv=[x['interventions'] for x in ee if x['interventions'] is not None]
    assert len(ee) in [9,10]
    if len(ee)==9:assert model=='SmolVLA' and h==10 and method=='N'
    task_metrics[key]=dict(model=model,H=h,method=method,task=task,difficulty=diff[task],planned=10,valid=len(ee),unknown=10-len(ee),successes=sum(x['success'] for x in ee),sr_pct=100*sum(x['success'] for x in ee)/len(ee),policy_calls_known=len(cv),policy_calls_total=sum(cv),policy_calls_mean=sum(cv)/len(cv) if cv else None,interventions_known=len(iv),interventions_total=sum(iv),interventions_mean=sum(iv)/len(iv) if iv else None)

master=load(DOCS/'data/EXPERIMENT_FOR_POST_VALUES_20260924.json')
for row in master['main']:
    for m in ['N','R','Post']:
        rr=[x for k,x in task_metrics.items() if k[:3]==(row['model'],row['H'],m)]
        assert len(rr)==50
        assert sum(x['valid'] for x in rr)==row[m+'_valid']
        assert sum(x['successes'] for x in rr)==row[m+'_successes']
        assert abs(sum(x['policy_calls_total'] for x in rr)/sum(x['policy_calls_known'] for x in rr)-row[m+'_calls'])<1e-9
for old in rows(F/'FINAL_L11_POST_PER_TASK.csv'):
    for h in horizons['pi05']:
        for m in ['N','R','Post']:
            assert task_metrics[('pi05',h,m,old['task'])]['successes']==int(old[f'{m}_H{h}_success'])

group_rows=[]
group_methods=[]
for model,hs in horizons.items():
    for h in hs:
        for g in groups:
            row=dict(model=model,H=h,difficulty=g,tasks=mapping['group_counts'][g])
            for m in ['N','R','Post']:
                rr=[v for k,v in task_metrics.items() if k[:3]==(model,h,m) and v['difficulty']==g]
                assert len(rr)==row['tasks']
                q=dict(model=model,H=h,method=m,difficulty=g,tasks=len(rr),planned=sum(x['planned'] for x in rr),valid=sum(x['valid'] for x in rr),unknown=sum(x['unknown'] for x in rr),successes=sum(x['successes'] for x in rr),macro_sr_pct=sum(x['sr_pct'] for x in rr)/len(rr),micro_sr_pct=100*sum(x['successes'] for x in rr)/sum(x['valid'] for x in rr),macro_policy_calls=sum(x['policy_calls_mean'] for x in rr)/len(rr),micro_policy_calls=sum(x['policy_calls_total'] for x in rr)/sum(x['policy_calls_known'] for x in rr),policy_calls_total=sum(x['policy_calls_total'] for x in rr),policy_calls_known=sum(x['policy_calls_known'] for x in rr))
                group_methods.append(q)
                for k in ['valid','unknown','successes','macro_sr_pct','micro_sr_pct','macro_policy_calls','micro_policy_calls']:row[m+'_'+k]=q[k]
            group_rows.append(row)
assert len(group_rows)==52

task_rows=[]
task_order=sorted(diff,key=lambda t:(groups.index(diff[t]),t))
for model,hs in horizons.items():
    for task in task_order:
        for h in hs:
            row=dict(model=model,task=task,difficulty=diff[task],H=h)
            for m in ['N','R','Post']:
                q=task_metrics[(model,h,m,task)]
                for k in ['planned','valid','unknown','successes','sr_pct','policy_calls_known','policy_calls_total','policy_calls_mean','interventions_known','interventions_total','interventions_mean']:row[m+'_'+k]=q[k]
            task_rows.append(row)
csave('METAWORLD_VALID_EPISODES.csv',episodes)
csave('METAWORLD_TASK_METRICS.csv',task_rows)
csave('METAWORLD_DIFFICULTY_METRICS.csv',group_rows)
csave('METAWORLD_DIFFICULTY_LONG.csv',group_methods)

lib=load(APP/'POST_LIBERO_APPENDIX_DATA.json')
lib_suite=[]
for x in lib['suite_rows']:
    q=dict(suite=x['suite'])
    for m in ['N','Post_operator']:
        for k,v in x[m].items():q[m+'_'+k]=v
    for k,v in x['paired'].items():q['paired_'+k]=v
    lib_suite.append(q)
csave('LIBERO_SUITE_METRICS.csv',[{k:x.get(k) for k in lib_suite[0]} for x in lib_suite])
lib_task=[]
for x in lib['task_rows']:
    q=dict(suite=x['suite'],task_id=x['task_id'],task_name=x['task_name'])
    for m in ['N','Post_operator']:
        for k,v in x[m].items():q[m+'_'+k]=v
    for k,v in x['paired'].items():q['paired_'+k]=v
    lib_task.append(q)
csave('LIBERO_TASK_METRICS.csv',[{k:x.get(k) for k in lib_task[0]} for x in lib_task])

def fnum(x,n=2):return 'NR' if x is None else f'{x:.{n}f}'
suite_disp={'libero_spatial':'Spatial','libero_object':'Object','libero_goal':'Goal','libero_10':'Long (LIBERO-10)','all_four_suites':'Overall'}
lib_table=table(['Suite','Native SR (%)','Post Operator SR (%)','Native Policy Calls','Post Operator Policy Calls','Post Interventions','Full L11 Post SR (%)'],[[suite_disp[x['suite']],fnum(x['N']['success_rate_pct'])+('†' if x['N']['unknown'] else ''),fnum(x['Post_operator']['success_rate_pct']),fnum(x['N']['mean_policy_calls'],3)+('†' if x['N']['unknown'] else ''),fnum(x['Post_operator']['mean_policy_calls'],3),fnum(x['Post_operator']['mean_interventions'],3),'NR'] for x in lib['suite_rows']])
lib_pairs=table(['Suite','Rescued','Harmed','Paired ΔSR (pp)','95% CI (pp)','McNemar p','Native Paired Policy Calls','Post Paired Policy Calls'],[[suite_disp[x['suite']],x['paired']['rescued'],x['paired']['harmed'],f"{x['paired']['difference_pp']:+.2f}",f"[{x['paired']['CI95_pp'][0]:.2f}, {x['paired']['CI95_pp'][1]:.2f}]",fnum(x['paired']['p_exact_mcnemar'],3),fnum(x['paired']['N_mean_policy_calls'],3),fnum(x['paired']['Post_mean_policy_calls'],3)] for x in lib['suite_rows']])
lib_tasks=table(['Suite','Task ID','Task','Native SR (%)','Post Operator SR (%)','Native Policy Calls','Post Operator Policy Calls','Rescued / Harmed'],[[suite_disp[x['suite']],x['task_id'],x['task_name'],fnum(x['N']['success_rate_pct'],1)+('†' if x['N']['unknown'] else ''),fnum(x['Post_operator']['success_rate_pct'],1),fnum(x['N']['mean_policy_calls'],3)+('†' if x['N']['unknown'] else ''),fnum(x['Post_operator']['mean_policy_calls'],3),f"{x['paired']['rescued']} / {x['paired']['harmed']}"] for x in lib['task_rows']])
mw_groups=table(['Backbone','H','Difficulty','Tasks','Native SR (%)','Replan SR (%)','Post SR (%)','Native Policy Calls','Replan Policy Calls','Post Policy Calls'],[[disp[x['model']],x['H'],x['difficulty'],x['tasks'],fnum(x['N_macro_sr_pct'])+('†' if x['N_unknown'] else ''),fnum(x['R_macro_sr_pct']),fnum(x['Post_macro_sr_pct']),fnum(x['N_macro_policy_calls'],3)+('†' if x['N_unknown'] else ''),fnum(x['R_macro_policy_calls'],3),fnum(x['Post_macro_policy_calls'],3)] for x in group_rows])
mw_detail=[]
for model,hs in horizons.items():
    for task in task_order:
        cells=[]
        for h in [10,20,30,40,50]:
            if h not in hs:cells.append('N/A');continue
            ss=[]
            for m in ['N','R','Post']:
                x=task_metrics[(model,h,m,task)]
                ss.append(fnum(x['sr_pct'],1)+('†' if x['unknown'] else ''))
            cells.append(' / '.join(ss))
        mw_detail.append([disp[model],diff[task],task]+cells)
mw_tasks=table(['Backbone','Difficulty','Task','H10 SR (%)','H20 SR (%)','H30 SR (%)','H40 SR (%)','H50 SR (%)'],mw_detail)
unknown=[x for x in group_methods if x['unknown']]
unknown_desc='；'.join(f"{x['difficulty']} 为 {x['valid']}/{x['planned']} 有效" for x in unknown)
smolrr=[x for k,x in task_metrics.items() if k[:3]==('SmolVLA',10,'N')]
smolmacro=sum(x['sr_pct'] for x in smolrr)/50

appendix=f'''## Appendix A. LIBERO：已有算子适配结果与完整方法状态

本附录补入已经执行的 LIBERO 数据，并保持配置身份独立。**现有 Post 是算子适配，不是主表的 L11＋D/G0＋multi 完整方法**：使用官方 π0.5 LIBERO 权重及 normalizer，预测 chunk=10、正常执行 K=5、NFE=10；执行20个命令后的自然重规划点固定一次纠偏，只修改5步 XYZ/夹爪，旋转与未用尾部不改，随后恢复 native K5。没有 D/G0 触发；critic 为 BCE 原生 LIBERO 头，四成员 seed9301–9304，各训练4,000步。

训练用120候选/24父源，仅5个负例；描述性验证40候选/8父源全部成功。因此不能由该验证集声称已学会可靠故障区分。测试使用保存的随机 reset/policy seeds，而非官方固定初态榜单。四个套件各10任务、每任务每方法计划10条：Native 399条有效、Post 400条有效；Goal/task0 的 Native 源 D24_LIBERO_libero_goal_t00_e08 未知，未填成失败。各自有效分母上的成功率和平均调用如下；此处不是三底座主表新增的正式 L11 格。

### A1. Suite-level results

{lib_table}

† Goal Native 为98/99，Overall Native 为387/399；Post 分别为100/100与387/400。Full L11 Post 实际测试0条，NR表示**未评测**，不是0%：现有收益监督仅7组train、4组validation且全零，尚未训练/评测完整 D/G0/L11 系统。新增开发40次中30有效、10技术失败是开发数据，不填入本表测试成功率。

### A2. Paired outcomes and calls

以下仅在共同有效源上比较 Post Operator−Native：Spatial/Object/Long各100对，Goal99对，合计399对。整体 Post 成功386、Native成功387，5救回/6损害。各自400/399分母的率差不能代替共同399对差值。区间沿用原已发布的逐episode配对正态近似及精确McNemar，未作多重校正；Object的[0,0]不证明等效。

{lib_pairs}

算子共实际纠偏247次，均为最多一次的固定时刻干预；平均调用32.0725来自完整400条Post，配对调用32.0927来自共同399条，两者口径不同。保存时间字段的范围不同，不据此比较推理速度。以上结果可以作为算子跨环境适配的附录记录，不能当成完整 L11 系统提升成功率的证据。

### A3. Per-task results

每任务通常各10条；†仅Goal/task0 Native为9条，其余字段按各自有效分母计算。救回/损害用该任务共同有效对，任务ID沿各套件的0–9编号。

{lib_tasks}

来源：{link(lib['sources']['Post_summary'],'Post 算子终局')}、{link(lib['sources']['N_combined_index'],'修复后 Native 有效索引')}、{link(lib['sources']['paired_published'],'已发布配对数据')}、{link(lib['sources']['full_result'],'Full 方法缺口终局')}。完整配置、逐任务分母与来源：{link(APP/'POST_LIBERO_APPENDIX_DATA.json','LIBERO JSON')}；可编辑导出：{link(APP/'LIBERO_SUITE_METRICS.csv','套件 CSV')}、{link(APP/'LIBERO_TASK_METRICS.csv','40任务 CSV')}。

## Appendix B. MetaWorld：按固定难度分组统计

### B1. Difficulty definition and aggregation

采用本地固定 **VLA-Corrector 仓库任务难度映射**（commit 9d23a0ba6fad562d3ed1a68fc52c8a12459abb41，配置项 DIFFICULTY_TO_TASKS）：**Easy 28、Medium 11、Hard 6、Very Hard 5**。这不是本文根据成功率新划分的等级，也不标作 MetaWorld 官方难度标准。原配置精确覆盖当前50个 -v3 任务，无需改名；所有 H、三种底座统一使用同一任务映射，不根据 Post 效果更换分组。

下表每格为**组内任务等权平均成功率与任务等权平均 Policy Calls**：先按每个任务的有效episode求均值，再对组内任务平均。数据完整时，每任务10条，与episode加权均值相同。任务组数量不相等，重建MT50总均值须按28/11/6/5加权，不能把四档均值直接平均。R/Post都是multi、Post为最终L11/fit9101，协议与正文表1相同；跨底座仍保留各自模拟器/控制协议。

† SmolVLA H10 Native 的四个未知源保留：{unknown_desc}，Hard/Very Hard完整；缺项分别位于drawer-open、handle-press-side、handle-press和hammer。该格完整50任务macro成功率为{smolmacro:.4f}%，而正文按496个有效episode合并为47.1774%；分母权重差异已在导出中同时保存macro与micro，不是数据矛盾。

**选型重叠须随表保留：π0.5 的 Very Hard 五任务恰为本次完整 Q 的五个选型任务。H10 Post 的50个源与 L11/fit9101 选型50逐源完全相同，37/50＝74.0%、平均调用15.020就是正文消融中已复用的结果；不能将其称为新的独立困难任务泛化测试。H20–50虽重新执行了不同H，仍沿用这50个已揭晓初态。** 对应源和结果路径核对见 {link(APP/'POST_VERY_HARD_SELECTION_OVERLAP.json','Very Hard 与选型源重叠记录')}。

### B2. Difficulty-level success and policy calls

{mw_groups}

这些是固定任务集合上的描述性分层，不据单个小组点差宣布显著性，也不将已有难度标签等同于每个底座上实际成功率排序。逐任务仅约10条，尤其Hard/Very Hard组较小；本次没有增加采样或新做分组统计检验。

分组来源：{link(mapping['source']['config_path'],'冻结任务映射配置')}；本次保存副本和来源身份：{link(APP/'POST_MW_TASK_DIFFICULTY.json','50任务难度映射 JSON')}。全部52个model×H×difficulty格的分母、成功数、macro/micro与调用：{link(APP/'METAWORLD_DIFFICULTY_METRICS.csv','难度汇总 CSV')}。

## Appendix C. MetaWorld：50任务逐项结果与完整 H 扫描

### C1. Native / Replan / Post across all H

每个单元格依次为 **Native / Replan / Post 的成功率（%）**。三底座各列50任务，任务按固定难度及名称排序；每任务每方法每H通常10条，†标出SmolVLA H10 Native的9条有效分母，未补造未知结果。X-VLA预测raw30，H40/H50不在本轮范围，故N/A。本表只汇总已完成multi；正文H10 once对照仍独立保留。

{mw_tasks}

每任务的成功数、有效数、未知数、Policy Calls总量与均值、干预次数已同时保存到 {link(APP/'METAWORLD_TASK_METRICS.csv','650个model×H×task格 CSV')}；原始轻量索引为 {link(APP/'METAWORLD_VALID_EPISODES.csv','19,496条有效 N/R/Post episode CSV')}，包含每条记录的来源路径。三底座合计150个task行与主表13格N/R/Post逐项回加一致；该19,496是多方法、多H的评估记录数，不是独立初态数。

'''
external=load(APP/'POST_EXTERNAL_FINE_DATA.json') if (APP/'POST_EXTERNAL_FINE_DATA.json').exists() else None
if external:
    erows=[]
    for g in groups:
        base=next(x for x in group_rows if x['model']=='pi05' and x['H']==10 and x['difficulty']==g)
        v=next(x for x in external['groups'] if x['method']=='VLA-Corrector' and x['difficulty']==g)
        a=next(x for x in external['groups'] if x['method']=='GAF-v1 adapted' and x['difficulty']==g)
        erows.append([g,base['tasks'],fnum(base['N_macro_sr_pct']),fnum(base['R_macro_sr_pct']),fnum(100*v['success_rate_macro']),fnum(100*a['success_rate_macro']),fnum(base['Post_macro_sr_pct']),fnum(v['policy_calls_mean_known_task_macro'],3)+('†' if v['policy_calls_missing'] else ''),fnum(a['policy_calls_mean_known_task_macro'],3),fnum(base['Post_macro_policy_calls'],3)])
    egroup=table(['Difficulty','Tasks','Native SR (%)','Replan SR (%)','VLA-Corrector SR (%)','GAF SR (%)','Post SR (%)','VLA-Corrector Policy Calls','GAF Policy Calls','Post Policy Calls'],erows)
    etasks=[]
    for task in task_order:
        v=next(x for x in external['tasks'] if x['method']=='VLA-Corrector' and x['task']==task)
        a=next(x for x in external['tasks'] if x['method']=='GAF-v1 adapted' and x['task']==task)
        p=task_metrics[('pi05',10,'Post',task)]
        etasks.append([diff[task],task,fnum(100*v['success_rate_macro'],1),fnum(100*a['success_rate_macro'],1),fnum(p['sr_pct'],1),fnum(v['policy_calls_mean_known_pooled'],3)+('†' if v['policy_calls_missing'] else ''),fnum(a['policy_calls_mean_known_pooled'],3),fnum(p['policy_calls_mean'],3)])
    etable=table(['Difficulty','Task','VLA-Corrector SR (%)','GAF SR (%)','Post SR (%)','VLA-Corrector Policy Calls','GAF Policy Calls','Post Policy Calls'],etasks)
    block=f'''### B3. External comparisons by difficulty

π0.5 H10 原500源的外部比较也使用同一四档映射。表中成功率与调用均按任务等权平均；† VLA-Corrector费用为每任务已知episode均值再平均，Easy缺6条、Medium缺2条费用，不能当成完整总体调用估计。8条log-derived终局仍计入成功率。GAF为本地adapted版本，训练资产不同，比较范围与正文表2相同。

{egroup}

VLA-Corrector任务等权的全MT50已知费用均值为19.8527，而正文逐已知episode加权为19.9614；差异来自8条费用未知后两种权重不同。完整覆盖的GAF/Post两种权重一致。组内费用覆盖和逐源缺项保存在 {link(APP/'POST_EXTERNAL_FINE_DATA.json','外部方法细粒度 JSON')}。

'''
    appendix=appendix.replace('## Appendix C.',block+'## Appendix C.',1)
    appendix+=f'''### C2. External methods: per-task success and policy calls

同一π0.5 H10设置，每任务10条有效成功率记录。† VLA-Corrector相应任务有一条费用未知，该均值仅来自其余9条；成功率仍含已验收的日志恢复终局。GAF/Post费用各任务完整。

{etable}

导出：{link(APP/'POST_EXTERNAL_FINE_TASKS.csv','外部逐任务 CSV')}、{link(APP/'POST_EXTERNAL_FINE_GROUPS.csv','外部难度 CSV')}。所有上述附录只汇总既有数据，不改变正式源、权重、原终局或原总表。

'''
bundle=dict(generated_utc=datetime.now(timezone.utc).isoformat(),scope='Existing final MT50 Post-multi L11 plus separate LIBERO BCE once operator; no new scientific execution',task_difficulty=mapping,metaworld_group_rows=group_rows,metaworld_task_rows=task_rows,metaworld_valid_episodes=len(episodes),metaworld_sources=sources,H10_source_audit=str(APP/'POST_H10_CROSSBASE_SOURCES.json'),selection_overlap=load(APP/'POST_VERY_HARD_SELECTION_OVERLAP.json'),libero=lib,external_fine=external)
jsave(APP/'POST_APPENDIX_VALUES.json',bundle)
(OUT/'POST_APPENDIX.md').write_text(appendix)
docfile=DOCS/'EXPERIMENT_FOR_POST.md'
backup=OUT/'EXPERIMENT_FOR_POST_before_APPENDIX.md'
if not backup.exists():shutil.copy2(docfile,backup)
s=docfile.read_text().split('\n## Appendix A.')[0]
old_intro='本文件集中管理当前 Post 配置及仍可复用的基线、完整 Q 消融、触发器对照；同类数据合表。'
new_intro=old_intro+'附录另收录 LIBERO 已有算子适配数据，以及 MetaWorld 固定难度分组和逐任务明细；LIBERO 的旧 BCE 算子与当前 L11 完整方法分别标注。'
if new_intro not in s:s=s.replace(old_intro,new_intro)
s=s.replace('这些细粒度数据通过链接集中管理，避免在本文复制超宽逐任务表。','本次已将三底座完整逐任务成功率与固定难度统计加入附录B/C，并保留包含分母和调用数的CSV。')
s=s.replace('| LIBERO full method | 完整 D/G0/L11 系统缺结果；已有 operator-only 不等价 | 暂不列正式 Post 成功率 |','| LIBERO full method | 完整 D/G0/L11 系统缺结果；已有 operator-only 不等价 | 附录A列已有Native/算子结果与40任务明细；Full仍标NR |')
docfile.write_text(s.rstrip()+'\n\n'+appendix)
master['appendix_data_file']=str(APP/'POST_APPENDIX_VALUES.json')
master['appendix_added_utc']=bundle['generated_utc']
jsave(DOCS/'data/EXPERIMENT_FOR_POST_VALUES_20260924.json',master)
jsave(APP/'BUILD_SUMMARY.json',dict(status='PASS',metaworld_episode_rows=len(episodes),metaworld_task_h_rows=len(task_rows),metaworld_difficulty_h_rows=len(group_rows),metaworld_display_task_rows=len(mw_detail),LIBERO_suites=4,LIBERO_tasks=40,LIBERO_N_valid=399,LIBERO_operator_valid=400,Full_LIBERO_test=0,group_counts=mapping['group_counts'],scientific_runs=0))
print(json.dumps(load(APP/'BUILD_SUMMARY.json'),ensure_ascii=False))
