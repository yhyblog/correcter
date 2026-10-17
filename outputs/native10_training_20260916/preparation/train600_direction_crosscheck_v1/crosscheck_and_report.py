from pathlib import Path
from collections import Counter
import hashlib,json,math,shutil
root=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector');out=root/'outputs/native10_training_20260916'
p=out/'progress_audits/train600_direction_v1';r=json.loads((p/'result.json').read_text())
indpath=root/'coordination/NATIVE10_TRAIN600_DIAGNOSTIC_INDEPENDENT_CHECK.json';ind=json.loads(indpath.read_text())
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
checks=[];float_diff=[]
def same(a,b,label):
 if isinstance(a,dict):
  assert set(a)<=set(b),label
  for k,v in a.items():same(v,b[k],label+'.'+k)
 elif isinstance(a,list):
  assert len(a)==len(b),label
  for i,(x,y) in enumerate(zip(a,b)):same(x,y,label+str(i))
 elif isinstance(a,float):
  d=abs(a-b);float_diff.append(d)
  assert math.isfinite(b) and d<=1e-12,(label,a,b)
 else:assert a==b,(label,a,b)
 checks.append(label)
def compare(a,b,label):
 same(a['sources'],b['sources'],label+'.sources')
 for arm,v in a['arms'].items():
  mapped={**b['arms'][arm],'paired_slots':b['arms'][arm]['slots']};same(v,mapped,label+'.arms.'+arm)
 for source,target in [('correction_vs_a0','correction_vs_a0'),('system_vs_normal','system_vs_normal'),('positive_vs_negative','direction_positive_vs_negative')]:
  for name,v in a[source].items():same(v,b[target][name],label+'.'+source+'.'+name)
 same(a['interruption_a0_vs_normal'],b['interruption'],label+'.I')
 for k,v in a['information'].items():
  if k in b['information']:same(v,b['information'][k],label+'.information.'+k)
 same(a['task_counts'],b['task_counts'],label+'.tasks');same(a['actual_cut_counts'],b['actual_cut_counts'],label+'.cuts')
 same(a['actual_selection_counts'],b['selection_categories'],label+'.selection')
for name,iname in [('round1','round1'),('round2','round2'),('combined','combined_train600')]:
 a=ind['results'][iname];d=r['diagnostics'][name];compare(a,d['total'],name)
 for group,values in a['groups'].items():
  for key,value in values.items():compare(value,d['groups'][group][key],name+'.'+group+'.'+key)
 for src,target in [('registered_cut_counts','registered_cut'),('selection_reason_counts','selection_reason')]:
  same(a[src],{k:v['sources'] for k,v in d['groups'][target].items()},name+'.'+src)
ledger=Path(r['ledger_before']['path']);assert sha(ledger)==r['ledger_before']['sha256']==r['ledger_after']['sha256']
resources=Counter()
for line in ledger.read_text().splitlines():
 x=json.loads(line);resources[x['resource']]+=x['amount']
assert resources=={'simulator_attempts':42874,'training_updates':19200}
dest=out/'preparation/train600_direction_crosscheck_v1';dest.mkdir(exist_ok=False)
check=dict(status='passed',diagnostic_result_path=str(p/'result.json'),diagnostic_result_sha256=sha(p/'result.json'),
 diagnostic_seal_sha256=sha(p/'complete.json'),independent_path=str(indpath),independent_sha256=sha(indpath),
 independently_recomputed_fields_verified=len(checks),maximum_float_operation_order_difference=max(float_diff),
 exact_integer_counts=True,numeric_check_note='1e-12 only reconciles algebraically equal descriptive float rate calculations; no CI or scientific acceptance rule changed.',
 old_round1_full_regression=r['old_round1_regression'],ledger_sha256=r['ledger_before']['sha256'],ledger_resource_totals=dict(resources),
 no_simulator_or_optimizer_increment=True,development_effects_read=False,model_loads=0,pca_calls=0)
(dest/'crosscheck.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
D=r['diagnostics'];pop=[D[k]['total'] for k in ('round1','round2','combined')]
def table(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,x))+' |' for x in rows])
def ci(x):return f"{x['net_gain_pp']:+.2f} [{x['source_ci95_pp'][0]:+.2f}, {x['source_ci95_pp'][1]:+.2f}]"
text=[]
text.append('训练 600 源方向诊断（2026-09-16）\n')
text.append('已完成 train-only 只读诊断。联合 velocity/direct/post 相对 a0 的成功率差为 **+1.71/+2.29/+2.50 个百分点**；round2 分别为 +2.50/+4.00/+3.58 个百分点。这些是两套生成器收集的训练标签，不是最终 A/B 模型的独立评测，不能宣布达到“较仅重规划再提高约 5 个百分点”的目标，也不用于修改参数或选择赢家。')
text.append('两个子包各 300 个完整有效训练源；联合 600 个实际 episode 和 planned slot 均唯一，每轮每 task 60 源、联合每 task 120 源。全部共同数组、rows 和逐源 provenance 与联合 train 包逐元素/逐记录相同；4 次后缀属于同一源内配对，不能将每臂 2400 次后缀当成 2400 个独立源。仅读取联合目录的 train 部分，未调用 load_bundle、模型、PCA、仿真或优化器，未读取 development/calibration/heldout 效果。')
text.append('候选生成 teacher 保留原 provenance：round1 为旧 v3 critic 1041–1044，round2 为首轮选中的 B200 critic 0–3；四成员 SHA 和原 collection protocol 分别保存在 result.json。VLA/D/G0/实现哈希跨轮相同。两轮源、切点和 teacher 同时不同，分轮差异不能归因于 teacher 改进。')
text.append('**切点与训练监督构成。** 两轮都登记 first_alarm 150、scheduled15/45/95 各 50；requested_cut 分别为 None 150、15/45/95 各 50。实际构成如下；完整 task × registered × requested × actual × selection × reason 交叉计数及分组结果在 JSON 的 cut_cross_counts/groups，未按结果筛源。')
text.append(table(['实际选择','round1','round2','联合'],[[s,*[t['selection_categories'][s] for t in pop]] for s in ('alarm','scheduled','fallback')]))
text.append(table(['实际 cut','round1','round2','联合'],[[k,*[t['actual_cut_counts'].get(k,0) for t in pop]] for k in sorted(pop[2]['actual_cut_counts'],key=int)]))
text.append(table(['监督信息（raw 同动作去重）','round1','round2','联合'],[[label,*[t['information'][k] for t in pop]] for label,k in [
 ('raw 动作组（含 a0）','unique_raw_groups'),('非 a0 动作组','nonbase_unique_groups'),('正 / 负方向不相同的无序组对','unique_direction_pairs'),
 ('mean gain > 0 的组','gain_mean_positive_groups'),('mean gain < 0 的组','gain_mean_negative_groups'),('mean gain = 0 的组','gain_mean_zero_groups'),
 ('存在非 a0 mean 差的源','nonalias_any_mean_difference'),('存在有益候选的源','any_candidate_mean_benefit'),('存在有害候选的源','any_candidate_mean_harm'),
 ('同时存在有益和有害候选的源','both_candidate_mean_benefit_and_harm'),('正反 mean 不同的组对','unique_direction_nonzero_mean_pairs'),
 ('存在正反 mean 差的源','unique_direction_any_mean_difference'),('XYZ 全零可变 mask 的源','zero_xyz'),('gripper 全零可变 mask 的源','zero_gripper')]]))
text.append('联合有 205/600 源出现非 a0 候选的四后缀均值差，395 源的候选均值全部相同；198 源存在正反方向均值差。7130 个非 a0 raw 组中正/负/零 gain 为 404/473/6253。候选组不是独立源，benefit/harm 源可重叠；这些数表示可观察监督信息，不是知道真实结局后可部署的 oracle 上限。21 源出现 raw alias、共 70 个重复候选槽；独立 NumPy 核验逐元素重建 alias 和三组去重权重一致。')
text.append('**14 臂成功次数。** round1、round2 分母各 1200；联合分母 2400。normal 独立于 13 个 critic 候选槽，a0 为仅重规划。')
text.append(table(['臂','round1','round2','联合成功次数','联合成功率'],[[name,pop[0]['arms'][name]['successes'],pop[1]['arms'][name]['successes'],pop[2]['arms'][name]['successes'],f"{100*pop[2]['arms'][name]['success_rate']:.2f}%"] for name in pop[2]['arms']]))
text.append('**相对 a0 的 12 个候选配对差。** 单位为百分点；方括号为源级 95% bootstrap CI。沿用旧脚本 seed=2026091621、10,000 次 task-stratified multinomial 整源重采样，保持每个分组实际 task 构成，四后缀一起重采样。CI 是训练分布事后描述，未作多重比较校正。')
text.append(table(['候选 − a0','round1 差 [CI]','round2 差 [CI]','联合差 [CI]'],[[name,*[ci(t['correction_vs_a0'][name]) for t in pop]] for name in pop[2]['correction_vs_a0']]))
text.append('**主纠偏的救回/损害与源级方向。** 救回/损害按配对后缀计数；正/负/零按该源四后缀成功数之差计数。')
text.append(table(['分布/方法','救回/损害（后缀）','正/负/零（源）'],[[f'{label}/{name}',f"{t['correction_vs_a0'][name]['rescues']}/{t['correction_vs_a0'][name]['harms']}",'/'.join(str(t['correction_vs_a0'][name][k]) for k in ('positive_sources','negative_sources','zero_sources'))] for label,t in zip(('round1','round2','联合'),pop) for name in ('velocity','direct','post')]))
text.append('**中断 I 与系统总增益 T。** I = a0 − continue_native10；T = 方法 − continue_native10。两者与纠偏自身增益 C = 方法 − a0 分开报告。')
text.append(table(['比较','round1 差 [CI]','round2 差 [CI]','联合差 [CI]','联合救回/损害'],[[label,*[ci(t['interruption'] if key is None else t['system_vs_normal'][key]) for t in pop],f"{(pop[2]['interruption'] if key is None else pop[2]['system_vs_normal'][key])['rescues']}/{(pop[2]['interruption'] if key is None else pop[2]['system_vs_normal'][key])['harms']}"] for label,key in [('I: a0 − normal',None),('T: velocity − normal','velocity'),('T: direct − normal','direct'),('T: post − normal','post')]]))
text.append('**五组正反方向。** 下表是 positive − negative（post − reverse_post），不是相对 a0 的纠偏收益。各轮完整救回/损害、正/负/零源和 raw-distinct 源数在 JSON；联合保留所有 600 源分母。')
text.append(table(['方向对','round1 差 [CI]','round2 差 [CI]','联合差 [CI]','联合救回/损害'],[[name,*[ci(t['direction_positive_vs_negative'][name]) for t in pop],f"{pop[2]['direction_positive_vs_negative'][name]['rescues']}/{pop[2]['direction_positive_vs_negative'][name]['harms']}"] for name in pop[2]['direction_positive_vs_negative']]))
text.append('联合 post − reverse_post 为 +9.00 pp，而 post − a0 为 +2.50 pp；前者只能说明这些已采集候选的正反方向有区分，不能代替后者或证明线上纠偏成功。正负标签仍稀疏、部分方向和任务存在损害；本报告保留这些负例，不新增筛选或调参规则。')
text.append('**核验与可复现证据。** 新聚合 CPU 测试 4 项通过；round1 原 result 的 total/groups/per_source 全字段（含所有旧 CI）严格相等。独立 NumPy 实现未调用新聚合函数；14 臂、V/D/P 的 C/I/T、五对方向、信息计数及三类分组共 '+str(len(checks))+' 个核对节点通过，最大浮点运算顺序差 '+str(max(float_diff))+'。未重复独立计算 CI，CI 证据为原 round1 完全回归与固定重采样实现。')
text.append('账本前后 SHA 完全相同：`'+r['ledger_before']['sha256']+'`；既有总量 42,874 simulator_attempts + 19,200 training_updates，增量均为 0；models/PCA 调用均为 0。未改旧脚本、封存产物、模型或科学参数。')
text.append('\n'.join([
 '- [统计脚本](../experiments/native10_training_20260916/summarize_train600_v1.py)，SHA `'+r['script_sha256']+'`。',
 '- [完整结果 JSON](../outputs/native10_training_20260916/progress_audits/train600_direction_v1/result.json)；[逐源 CSV](../outputs/native10_training_20260916/progress_audits/train600_direction_v1/per_source.csv)；seal `'+sha(p/'complete.json')+'`。',
 '- [CPU 与真实只读执行日志](../outputs/native10_training_20260916/preparation/train600_direction_cpu_v1/result.json)。',
 '- [独立核验](NATIVE10_TRAIN600_DIAGNOSTIC_INDEPENDENT_CHECK.json)，SHA `'+sha(indpath)+'`；[交叉核验回执](../outputs/native10_training_20260916/preparation/train600_direction_crosscheck_v1/crosscheck.json)。']))
text.append('复现命令（目录必须是新版本）：\n\n```bash\nCUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=. /mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -m experiments.native10_training_20260916.summarize_train600_v1 --destination outputs/native10_training_20260916/progress_audits/train600_direction_reproduction_v1\n```')
report=root/'coordination/NATIVE10_TRAIN600_DIRECTION_DIAGNOSTICS.md'
with report.open('x') as f:f.write('\n\n'.join(text)+'\n')
shutil.copyfile(report,dest/'report.md');shutil.copyfile(__file__,dest/'crosscheck_and_report.py')
(dest/'complete.json').write_text(json.dumps(dict(status='complete',files={f.name:sha(f) for f in dest.iterdir() if f.is_file()},report_path=str(report),report_sha256=sha(report)),indent=2)+'\n')
print(json.dumps({'crosscheck':str(dest),'checks':len(checks),'max_float_diff':max(float_diff),'seal_sha256':sha(dest/'complete.json'),'report':str(report),'report_sha256':sha(report)}))
