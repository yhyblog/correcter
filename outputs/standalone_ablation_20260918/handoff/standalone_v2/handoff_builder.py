from pathlib import Path
from datetime import datetime,timezone
import json,csv,shutil,os
from experiments.standalone_ablation_20260918 import storage
R=storage.ROOT;version='standalone_v2';A=R/'audits'/version;I=R/'independent_audits'/version;C=R/'protocols'/version;CTRL=R/'execution_control'/version;out=R/'handoff'/version
storage.sealed(A);storage.sealed(I);runtime=storage.read(CTRL/'result.json');assert runtime['status']=='complete'
r=storage.read(A/'result.json');assert r['status']=='passed' and r['completed_sources']==100
s=r['statistics'];d=r['diagnostics'];cfg=storage.read(C/'config.json');assert s['source_denominator']==100 and s['logical_outcomes_per_arm']==400
out.mkdir(parents=True,exist_ok=False)
ref=lambda p:dict(path=str(p),sha256=storage.sha256(p))
refdir=lambda p:dict(path=str(p),seal_sha256=storage.sha256(p/'complete.json'))
labels={'continue_native10':'正常 native10','alarm_replan10':'仅报警重规划 R','velocity':'原 matched-V','direct':'原 matched-D','post':'原 matched-P','solo_velocity':'standalone velocity','solo_direct':'standalone direct','solo_post':'standalone post'}
pp=lambda x:f'{100*x:.2f}'
ci=lambda x:'['+', '.join(pp(v) for v in x)+']'
# The whole input is sealed; these exports never create labels or select a method.
params=dict(task=cfg['task_document'],ready=cfg['analysis_ready'],config=ref(C/'config.json'),freeze=ref(C/'freeze.json'),critic=cfg['selected_model'],source_horizon=cfg['source_horizon'],prefix_horizon=cfg['prefix_horizon'],suffix_horizon=cfg['suffix_horizon'],control_budget=cfg['control_budget'],generated_horizon=cfg['generated_horizon'],gate_threshold=cfg['gate_threshold'],guidance=cfg['guidance'],matching_numerical_constants={k:cfg['matching'][k] for k in ('xyz_rms','gripper_rms','xyz_linf','gripper_linf','boundary_clearance','tolerance','zero_threshold')},solo_rule=cfg['solo_rule'],seed_namespace=cfg['seed_namespace'],execution_plans=cfg['execution_plans'],statistics=cfg['statistics'],operational_runtime=cfg['operational_runtime'],new_model_training=False,new_captures=False,cohort='previously revealed held100 structural ablation; not a fresh independent heldout',no_posthoc_method_selection=True)
storage.dump(out/'parameters.json',params)
with (out/'per_source.csv').open('x',newline='') as stream:
 columns=['primary_id','task','scene_fingerprint','cut','no_cut']+[m+'_outcomes' for m in s['methods']]+list(s['overall']['comparisons'])
 writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
 for row in s['per_source']:
  values=dict(primary_id=row['planned_slot_id'],task=row['task'],scene_fingerprint=row['scene_fingerprint'],cut=row['actual_cut'],no_cut=row['no_cut'])
  values.update({m+'_outcomes':''.join('1' if v else '0' for v in row['outcomes'][m]) for m in s['methods']});values.update(row['paired_source_gains']);writer.writerow(values)
size=sum(p.stat().st_size for p in R.rglob('*') if p.is_file())
resources=dict(**{k:runtime[k] for k in ('new_simulator_attempts','global_simulator_attempts','new_optimizer_updates','global_optimizer_updates','by_stage')},formal_bank_restores=98,formal_branches=1176,preflight_bank_restores=10,preflight_branches=40,new_capture_attempts=0,new_initialization_replacements=0,repairs_used=0,global_limit=50000,global_remaining=50000-runtime['global_simulator_attempts'],supplement_cap=1500,supplement_remaining=1500-runtime['new_simulator_attempts'],holder_check=runtime['holder_check'],output_bytes_at_handoff=size,output_size_time_utc=datetime.now(timezone.utc).isoformat())
storage.dump(out/'resources.json',resources)
summary=dict(status='complete',utc=datetime.now(timezone.utc).isoformat(),new_independent_heldout=False,winner_selected=False,overall=s['overall'],per_task=s['per_task'],alarm_conditioned=s['alarm_conditioned'],primary_family=s['common_primary_comparisons'],bootstrap=s['bootstrap'],diagnostics=d['method_summaries'],cost=d['cost'],resources=resources,evidence=dict(full_audit=refdir(A),independent_reaggregation=refdir(I),preflight=refdir(R/'preflight_audits'/version),runtime_result=ref(CTRL/'result.json'),config=ref(C/'config.json'),freeze=ref(C/'freeze.json'),parameters=ref(out/'parameters.json'),per_source=ref(out/'per_source.csv')),limitations=s['limitations']+d['limitations'])
storage.dump(out/'summary.json',summary)
lines=['# Standalone 结构消融：完整结果与参数','',f"封存时间：{summary['utc']}。原已揭晓 held100、五任务各20个不同初态，98个cut＋2个共同结局；每源4个配对后缀。固定A4000，不训练、不改G0或种子，不作事后赢家选择。",'', '本轮回答拆除其他生成分支后的效果与成本：三个入口各自产生a0及自身方向，半径只依赖自身容量。它是已揭晓队列的结构消融，不能称为新的独立held验证。','', '## 八臂成功率','', '| 方法 | 成功/400 | 成功率 | 数据来源 |','|---|---:|---:|---|']
for m in s['methods']:lines.append(f"| {labels[m]} | {s['overall']['success_counts'][m]}/400 | {pp(s['overall']['success_rates'][m])}% | {'封存旧对照' if m in s['reused_methods'] else '新增独立入口实测'} |")
lines+=['','## 三项共同主要比较：solo − R','', '区间单位为百分点；每次任务内整源抽样，4后缀不当作独立初态。同时报告普通95%与三比较Bonferroni 98.333%源bootstrap区间。','', '| 比较 | 差值pp | 95% CI | 98.333% CI | 救回/损害 | 正/负/零源 |','|---|---:|---|---|---:|---:|']
for key in s['common_primary_comparisons']:
 v=s['overall']['comparisons'][key];lines.append(f"| {key} | {pp(v['gain'])} | {ci(v['source_95ci'])} | {ci(v['source_bonferroni_98_333333ci'])} | {v['rescues']}/{v['harms']} | {v['positive_sources']}/{v['negative_sources']}/{v['zero_sources']} |")
lines+=['','三项均保留。post和velocity的Bonferroni校正区间均高于0，direct的校正区间跨0。post相对R为+9.5pp，相对原matched-post仅+0.5pp（描述性95%区间含0）；本队列支持post拆掉其他方向生成后仍有正收益，但不证明它优于原完整matched-post。三项点估计超过5pp，不等于真实收益至少5pp。该队列已经揭晓，不能将此消融作为新的独立验证或据此重选模型/方法。','', '## 结构诊断与次要比较','', '| 比较 | 差值pp | 描述性95% CI | 救回/损害 | 正/负/零源 |','|---|---:|---|---:|---:|']
for key in s['secondary_comparisons']+s['reference_comparisons']:
 v=s['overall']['comparisons'][key];lines.append(f"| {key} | {pp(v['gain'])} | {ci(v['source_95ci'])} | {v['rescues']}/{v['harms']} | {v['positive_sources']}/{v['negative_sources']}/{v['zero_sources']} |")
lines+=['','## 逐任务','', '| 任务（各20初态） | N | R | 原V | 原D | 原P | solo-V | solo-D | solo-P |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for task,v in s['per_task'].items():lines.append('| '+task+' | '+' | '.join(str(v['success_counts'][m])+'/80' for m in s['methods'])+' |')
lines+=['','完整逐源4位结局串与十项源均差见 `per_source.csv`；无报警2源保留共同终局，完整分母不变。','', '## 实际幅度与完整入口成本','', '完整入口计时包含各自a0、方向生成、诊断评分和检查；不把共享a0摊销时间冒充独立成本。载模、恢复与后缀时间单列，重叠计时不得相加。旧fullbank与本轮并发条件不同，不能据此宣称严格硬件加速比。','', '| 方法 | VLA采样/入口 | 入口均值s | 中位s | p95s | XYZ实际RMS均值 | grip实际RMS均值 | XYZ/grip旧零组恢复源数 |','|---|---:|---:|---:|---:|---:|---:|---:|']
for m in ('solo_post','solo_direct','solo_velocity'):
 v=d['method_summaries'][m];cost=v['full_entry_seconds_including_own_a0'];g=v['groups'];lines.append(f"| {labels[m]} | {v['actual_policy_calls']['mean']:.0f} | {cost['mean']:.4f} | {cost['median']:.4f} | {cost['p95']:.4f} | {g['xyz']['solo_actual_rms']['mean']:.6f} | {g['gripper']['solo_actual_rms']['mean']:.6f} | {g['xyz']['old_zero_recovered_sources']}/{g['gripper']['old_zero_recovered_sources']} |")
lines+=['',f"正式整波含lifecycle耗时 {d['cost']['whole_wave_seconds_including_lifecycle']:.2f}s；worker载模均值 {d['cost']['worker_model_loading_seconds']['mean']:.2f}s；每源solo bank恢复均值 {d['cost']['solo_bundle_restore_seconds']['mean']:.4f}s。分支恢复/后缀、旧reference预检成本及Q关联详见summary.json。Q仅作描述，不是接受门或梯度有效性的充分证据。",'', '## 技术、来源与预算','', '- 同freeze预检50次通过；5源旧五臂rep0完整复现、原生方向与raw身份检查通过。旧bank未保存原生V/D，不能扩大成98源历史原生V/D全部逐位复现；post历史梯度按实际存档检查。','- 正式100槽完整，32worker、98bank＋1176分支，全轨迹/raw/配对/scene/账本审计通过。独立从1960旧＋1176新summary重建标签并精确复算统计；2无报警共同结局保留。',f"- 新增{resources['new_simulator_attempts']}sim＝50＋1274，新增optimizer0；全局{resources['global_simulator_attempts']}/50000sim、51200opt，技术repair0；剩余全局{resources['global_remaining']}，当前supplement cap余额{resources['supplement_remaining']}，不自动使用。",'- 结束后现场确认8holder恢复；旧封存及失败standalone_v1保留。运行使用standalone_v2，运维修复只重绑当前lifecycle/guard及补全holder/wave/no-op身份。',f"- 输出文件总字节快照 {size}（采样、快照与审计等合计；不是新增模型权重）。",'', '## Q与实测的边界','', '98个cut源的Q预测与配对实测源增益Pearson仅约0.145（V）、0.178（D）、0.198（P）。solo-direct平均预测相对a0为−0.0324，而完整分母实际点估计为+5.75pp；扩大自身半径并不保证Q上升，也不能由Q变化推断真实纠偏收益。未增加任何Q接受门。这些相关系数仅为描述，不能作机制因果归因。','', '## 参数与可复现产物','',f"- 实际配置：`{C/'config.json'}`，SHA `{storage.sha256(C/'config.json')}`。",f"- freeze：`{C/'freeze.json'}`，SHA `{storage.sha256(C/'freeze.json')}`。",'- `parameters.json` 保存A4000四权重身份、native10/300/50、G0 .05、alpha10/tau .3/.2/.1、XYZ/grip target .05/.10与cap .15/.40、mask余量.05、自身半径及全部种子/统计规则。',f"- 完整审计：`{A}`；独立重算：`{I}`。",f"- 新隔离代码：`{storage.PACKAGE/'experiments/standalone_ablation_20260918'}`；原freeze含代码快照。",'', '本轮不新增训练、capture、替补、selection seal或后续wave。']
with (out/'REPORT.md').open('x') as f:f.write('\n'.join(lines)+'\n')
shutil.copyfile(__file__,out/'handoff_builder.py');shutil.copyfile(CTRL/'independent_statistics.py',out/'independent_statistics.py')
storage.seal(out,role='standalone_final_handoff',simulator_calls=0,model_calls=0,optimizer_updates=0)
coord=storage.PACKAGE/'coordination/STANDALONE_ABLATION_FINAL_HANDOFF_20260918.md'
with coord.open('x') as f:f.write((out/'REPORT.md').read_text())
p=storage.PACKAGE/'coordination/STANDALONE_ABLATION_EXECUTOR_STATUS.json';status=storage.read(p);status.update(updated_utc=datetime.now(timezone.utc).isoformat(),state='standalone_complete_final_handoff_delivered',active_stage=None,final_handoff=refdir(out),final_report=ref(coord),independent_statistics=refdir(I),next_step='Analysis final interpretation only; no further wave/training/selection. Keep eight holders idle.');p.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(handoff=refdir(out),report=ref(coord),primary={k:s['overall']['comparisons'][k] for k in s['common_primary_comparisons']},success=s['overall']['success_counts'],resources=resources),ensure_ascii=False,indent=2))
