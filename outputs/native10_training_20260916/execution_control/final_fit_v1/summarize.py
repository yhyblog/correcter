"""Package the complete final training and read-only audit for analysis handoff."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
OUT=ROOT/'outputs/native10_training_20260916'
MODEL=OUT/'models/final/final_fit_v1'
EXEC=OUT/'final_fit_execution/fit/final_fit_v1'
AUDIT=OUT/'final_training_audits/final_fit_v1'
DEST=OUT/'final_model_handoffs/final_fit_v1'
REPORT=ROOT/'coordination/NATIVE10_FINAL_TRAINING_EXECUTOR_HANDOFF.md'


def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(p,d):
    with Path(p).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def binding(p):return dict(path=str(p),seal_sha256=sha(p/'complete.json'))


def main():
    d=read(MODEL/'result.json');e=read(EXEC/'result.json');a=read(AUDIT/'audit.json')
    assert d['status']=='complete' and e['status']=='complete' and a['status']=='passed'
    assert d['optimizer_updates']==a['optimizer_updates_verified']==a['unique_update_ids']==32000
    assert d['selection']==a['selected_record'] and a['selection_recomputed']
    assert a['checkpoint_state_dicts_checked']==56 and a['compared_ensemble_checkpoints']==14
    assert a['initial_state_dicts_checked']==8 and a['selected_exports_checked']==4
    assert a['budget_unchanged_by_auditor'] and a['all_actual_minibatches_equal_sealed_plans']
    assert a['preprocessing_reused_without_refitting']
    assert a['budget_snapshot_sha256']==sha(OUT/'budget/attempts.jsonl')
    chosen=d['selection'];assert (chosen['path'],chosen['step'])==('A',4000)
    metrics_keys=('planned_episodes','reached_episodes','gain','rescues','harms','baseline_success','selected_success','gain_mse')
    comparisons=[dict(path=x['path'],step=x['step'],**{k:x['metrics'][k] for k in metrics_keys}) for x in d['compared_checkpoints']]
    selected=dict(path=chosen['path'],step=chosen['step'],**{k:chosen['metrics'][k] for k in metrics_keys})
    ranked=sorted(comparisons,key=lambda x:(-x['gain'],x['harms'],x['gain_mse'],x['step'],0 if x['path']=='B' else 1))
    assert ranked[0]==selected
    reason='A3200/A4000/B200 have equal gain .045; A harms5 < B200 harms6; A4000 gainMSE .056607967428307496 < A3200 .05809580086090618. Earlier-step/prefer-B ties are not reached.'
    reload=read(MODEL/'selected_reload_audit.json')
    assert reload['status']=='passed' and reload['source_count']==95 and reload['gradient_slots']==[0,11]
    for key in ('feature_cache_bit_exact','thirteen_candidate_member_probability_bit_exact','member_and_ensemble_gradient_bit_exact','a0_anchor_exactly_zero','state_and_anchor_immutable'):assert reload[key]
    control=read(OUT/'execution_control/final_fit_v1/result.json')
    cfg=read(MODEL/'config.json');guard=read('/tmp/gpu_occupancy_guard/status.json')
    assert len(guard['gpus'])==8 and all(x['state']=='holder' for x in guard['gpus'].values())
    DEST.mkdir(parents=True,exist_ok=False)
    dump(DEST/'gpu_holder_snapshot.json',guard)
    selected_binding=dict(**binding(MODEL/'selected'),model_hashes=d['model_hashes'],
        ranking_path=str(MODEL/'selected/ranking.json'),ranking_sha256=sha(MODEL/'selected/ranking.json'))
    summary=dict(status='complete_audited_final_training',utc=datetime.now(timezone.utc).isoformat(),
        protocol=control['protocol'],ready=cfg['analysis_ready'],specification_sha256=read(control['protocol']['freeze'])['specification_sha256'],
        preflight=d['preflight_binding'],input_bundle=d['input_bundle'],design=cfg['final_training_pipeline']['design'],
        model=dict(**binding(MODEL),result_sha256=sha(MODEL/'result.json')),
        execution=dict(**binding(EXEC),result_sha256=sha(EXEC/'result.json')),
        independent_audit=dict(**binding(AUDIT),audit_sha256=sha(AUDIT/'audit.json')),
        selected=selected,selected_assets=selected_binding,selection_reason=reason,compared_checkpoints=comparisons,
        resource_delta=dict(simulator_attempts=0,optimizer_updates=32000,unique_update_identities=32000,
            first_attempt=min(d['optimizer_attempt_numbers']),last_attempt=max(d['optimizer_attempt_numbers'])),
        resources_after=e['resource_after'],coverage=d['coverage'],all_eight_members_steps=4000,
        checkpoint_counts=dict(ensemble=14,member=56,initial_states=8,selected_exports=4),
        audit_checks=dict(all_actual_minibatches_equal_sealed_plans=True,preprocessing_refitted=False,
            new_initialization_generated=False,frozen_tensors_and_buffers_unchanged=True,
            exact_original_selection_recomputed=True,selected_exports_equal_chosen_checkpoints=True),
        selected_reload={k:v for k,v in reload.items() if k!='episode_ids'},
        costs=a['cost'],gpu_holders_retained=8,independent_validation_success=False,
        real_policy_evaluation_performed=False,next_stage_automatically_started=False,
        limitation='Original development candidate-bank proxy; no final flow deployment or independent validation claim.',
        summary_script_sha256=sha(__file__))
    dump(DEST/'summary.json',summary)
    dump(DEST/'selected_model_binding.json',selected_binding)
    lines=['最终600源A/B训练交接（2026-09-17；工作流20260916）','',
        '最终训练及独立只读审计均已完成。A/B各四成员、每成员4000更新，合计32000新增优化、0新增仿真；14组固定ensemble检查点/56个成员检查点齐全。旧封存未修改。','',
        '**唯一选模：A4000。** 原dev100源×4后缀的候选银行选择从a0 257/400（64.25%）到275/400（68.75%），净+4.50pp，救回23/损害5；保留95cut及5共同结局、每任务20源的完整100分母。此数值是开发候选银行选模代理，不是实际flow纠偏部署，也不是独立成功验证。','',
        '排序理由：A3200、A4000、B200均+4.50pp；A两项损害5少于B200的6，优先A。A4000 gain MSE 0.056607967428307496小于A3200的0.05809580086090618，因此选A4000；更早检查点/最后优先B的平局规则未触发。未因结果临时改变规则。','',
        '| 路径/步数 | 代理净收益pp | 救回/损害 | gain MSE |',
        '| --- | ---: | ---: | ---: |']
    for x in comparisons:lines.append(f'| {x["path"]}/{x["step"]} | {100*x["gain"]:+.2f} | {x["rescues"]}/{x["harms"]} | {x["gain_mse"]:.10f} |')
    lines += ['',
        'A学习率1e-4、仅residual/advantage 2529参数可训练；B学习率3e-4、完整小critic MLP 7058参数可训练。AdamW wd=.01、clip=1、batch=32完整源，BCE/相对a0/正反差损失1/1/.5。训练均从同一真实预检的PCA、八初态、source bootstrap和minibatch计划恢复；没有重拟PCA或重新初始化，600训练源等权，两轮生成critic/真实protocol身份保留。','',
        '独立审计确认32000个update身份、8×4000计数、全部4000×32实际采样序列与封存计划一致，所有声明冻结的参数和预处理buffer逐字节不变，4个selected导出等于被选检查点。原dev100规则独立NumPy重聚合一致；浮点归约最大差1.3877787807814457e-17仅属原标量审计口径，未修改canonical数值容差或排序键。','',
        '所选A4000的真实重载审计覆盖95有效dev源、四成员13候选概率及槽0/11成员和ensemble梯度，canonical同shape严格逐位通过。完成后的独立审计只核封存重载证据及CPU state_dict，没有再次实例化模型、forward或重算梯度。','',
        f'执行UTC {e["started_utc"]} → {e["finished_utc"]}。含入口核验墙钟{e["wall_seconds"]:.2f}秒（{e["wall_seconds"]/60:.2f}分钟），训练管线墙钟{d["cost"]["wall_seconds"]:.2f}秒、CPU{d["cost"]["cpu_seconds"]:.2f}秒，峰值RSS{e["max_process_rss_kib"]/1024**2:.3f}GiB；独立审计{a["cost"]["auditor"]["wall_seconds"]:.2f}秒。runtime仍lerobot/torch2.7.1+cu126/NumPy2.2.6/CPU float32两线程，8卡holder保留。','',
        '资源累计42,874/50,000 simulator attempts、51,200/51,200 optimizer updates，technical reserve消耗0。没有失败、重试、新仿真或下一阶段自动启动。当前policy2/cal/held仍待分析端阶段决定。','',
        f'- 训练配置：`{control["protocol"]["config"]}`，SHA `{control["protocol"]["config_sha256"]}`；freeze `{control["protocol"]["freeze_sha256"]}`。',
        f'- READY v10 SHA `{cfg["analysis_ready"]["sha256"]}`；specification `{summary["specification_sha256"]}`。',
        f'- 模型：`{MODEL}`；seal `{summary["model"]["seal_sha256"]}`；result SHA `{summary["model"]["result_sha256"]}`。',
        f'- 唯一selected：`{MODEL/"selected"}`；seal `{selected_binding["seal_sha256"]}`；四成员权重SHA详见同目录ranking.json与交接summary。',
        f'- 独立审计：`{AUDIT}`；seal `{summary["independent_audit"]["seal_sha256"]}`；audit SHA `{summary["independent_audit"]["audit_sha256"]}`。',
        f'- 执行receipt：`{EXEC}`；seal `{summary["execution"]["seal_sha256"]}`。',
        f'- 当前账本SHA `{e["resource_after"]["sha256"]}`；新update号码62075..94074，仿真增量0。',
        f'- 结构化交接与selected绑定：`{DEST}`。','',
        '结论仅为既定训练和技术审计完成；真实纠偏相对仅重规划能否再提升约5个百分点，仍须下一阶段真实配对策略测评判断。','']
    report='\n'.join(lines)
    with REPORT.open('x') as f:f.write(report)
    with (DEST/'report.md').open('x') as f:f.write(report)
    dump(DEST/'complete.json',dict(status='complete',role='final_training_executor_handoff',
        files={str(p.relative_to(DEST)):sha(p) for p in DEST.rglob('*') if p.is_file()},
        model_seal_sha256=summary['model']['seal_sha256'],report_path=str(REPORT),report_sha256=sha(REPORT)))
    print(json.dumps(dict(path=str(DEST),seal_sha256=sha(DEST/'complete.json'),report=str(REPORT),report_sha256=sha(REPORT)),ensure_ascii=False))


if __name__=='__main__':main()
