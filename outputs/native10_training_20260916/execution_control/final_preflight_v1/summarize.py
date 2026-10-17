"""Summarize sealed final preflight evidence; no model or feature loading."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
OUT = ROOT/'outputs/native10_training_20260916'
MODEL = OUT/'fit_preflight/final/final_preflight_v1'
EXEC = OUT/'final_fit_execution/preflight/final_preflight_v1'
CONTROL = OUT/'execution_control/final_preflight_v1'
DEST = OUT/'final_model_handoffs/final_preflight_v1'
REPORT = ROOT/'coordination/NATIVE10_FINAL_PREFLIGHT_EXECUTOR_HANDOFF.md'


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def dump(p,d):
    with Path(p).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def check_seal(path):
    seal=read(path/'complete.json')
    assert seal['status']=='complete'
    assert set(seal['files'])=={str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p!=path/'complete.json'}
    for n,h in seal['files'].items():assert sha(path/n)==h,n
    return sha(path/'complete.json')


def main():
    seal=check_seal(MODEL);execution_seal=check_seal(EXEC)
    assert seal=='eb1e39d4ee145ebecce9b16593a9c1fd901fd7dcc2a5c9e8746f657e4c202d3e'
    result=read(MODEL/'result.json');execution=read(EXEC/'result.json');control=read(CONTROL/'result.json')
    assert result['status']=='passed' and result['all_eight_initial_states_checked']
    assert result['canonical_reload_passed'] and result['dense_diagnostics_complete']
    assert result['numeric_contract']=='canonical_strict_passed_dense_reported'
    assert not result['numerical_review_required'] and not result['batch_singleton_bit_exact']
    assert result['optimizer_updates']==result['simulator_calls']==0
    assert execution['resources']['optimizer_updates']==execution['resources']['simulator_attempts']==0
    assert (EXEC/'budget_before.jsonl').read_bytes()==(EXEC/'budget_after.jsonl').read_bytes()==(OUT/'budget/attempts.jsonl').read_bytes()
    source_sets=read(MODEL/'source_sets.json');pca=read(MODEL/'pca_fit_audit.json')
    train=source_sets['train']['effective_episode_ids'];dev=source_sets['development']['effective_episode_ids']
    assert len(train)==len(set(train))==600 and len(dev)==len(set(dev))==95 and not set(train)&set(dev)
    assert pca['fit_episode_ids']==train and pca['fit_source_count']==600 and pca['train_only']
    assert not pca['bootstrap_duplicates_used']
    sampling=read(MODEL/'sampling.json');masks=read(MODEL/'trainable_masks.json')
    bootstrap_summary={};mask_summary={};dense={};canonical={}
    for path in ('A','B'):
        bootstrap_summary[path]=[];mask_summary[path]=[];dense[path]={};canonical[path]={}
        assert len(sampling[path])==len(masks[path])==4
        for member,(sample,mask) in enumerate(zip(sampling[path],masks[path])):
            b=sample['bootstrap'];assert len(b['indices'])==len(b['episode_ids'])==600
            assert b['episode_ids']==[train[i] for i in b['indices']]
            assert set(b['episode_ids'])<=set(train) and not set(b['episode_ids'])&set(dev)
            assert b['multiplicities']==dict(Counter(b['episode_ids']))
            assert all(v==dict(unique_available=120,drawn=120) for v in b['per_task'].values())
            assert sample['minibatch_plan_shape']==[4000,32]
            bootstrap_summary[path].append(dict(member=member,source_count=600,distinct_bootstrap_sources=len(set(b['episode_ids'])),
                per_task=b['per_task'],seed=b['seed'],batch_seed=sample['batch_seed'],minibatch_plan_sha256=sample['minibatch_plan_sha256']))
            trainable=[p for p in mask['parameters'] if p['requires_grad']]
            assert all(not p['requires_grad'] for p in mask['buffers'])
            if path=='A':assert all(p['name'].startswith(('residual.','advantage.')) for p in trainable)
            else:assert len(trainable)==len(mask['parameters'])
            mask_summary[path].append(dict(member=member,trainable_names=[p['name'] for p in trainable],
                trainable_numel=sum(p['numel'] for p in trainable),total_parameter_numel=sum(p['numel'] for p in mask['parameters']),buffers_frozen=True))
        for purpose,expected in (('train',600),('development',95)):
            c=result['reload_audits'][path][purpose]
            assert c['status']=='passed' and c['source_count']==expected and c['members_checked']==4
            for key in ('feature_cache_bit_exact','thirteen_candidate_member_probability_bit_exact','member_and_ensemble_gradient_bit_exact','a0_anchor_exactly_zero','state_and_anchor_immutable'):assert c[key]
            assert c['gradient_slots']==[0,11];canonical[path][purpose]={k:v for k,v in c.items() if k!='episode_ids'}
            d=result['batch_singleton_audits'][path][purpose]
            assert d['source_count']==expected and d['diagnostics_complete'] and not d['all_bit_exact']
            dense[path][purpose]=dict(status=d['status'],source_count=expected,all_bit_exact=False,
                projected_features_max_abs_difference=max(x['projected_features']['max_abs_difference'] for x in d['members']),
                probabilities_max_abs_difference=max(x['probabilities']['max_abs_difference'] for x in d['members']),
                member_gradient_max_abs_difference=max(v['max_abs_difference'] for x in d['members'] for v in x['gradients'].values()),
                member_gradients={str(x['member']):x['gradients'] for x in d['members']},
                ensemble_gradients=d['ensemble_gradients'],diagnostic_only=True)
    DEST.mkdir(parents=True,exist_ok=False)
    guard=read('/tmp/gpu_occupancy_guard/status.json');assert len(guard['gpus'])==8 and all(g['state']=='holder' for g in guard['gpus'].values())
    dump(DEST/'gpu_holder_snapshot.json',guard)
    binding=dict(path=str(MODEL),seal_sha256=seal,result_sha256=sha(MODEL/'result.json'))
    protocol=control['protocol'];spec_sha=read(protocol['freeze'])['specification_sha256']
    summary=dict(status='passed_zero_update_final_preflight',utc=datetime.now(timezone.utc).isoformat(),
        preflight=binding,execution=dict(path=str(EXEC),seal_sha256=execution_seal,result_sha256=sha(EXEC/'result.json')),
        protocol=protocol,specification_sha256=spec_sha,ready_sha256=result['preflight_ready']['sha256'],
        input_bundle=result['identity']['input_bundle'],design=result['identity']['design'],
        coverage=result['coverage'],numeric_runtime=result['numeric_runtime'],numeric_contract=result['numeric_contract'],
        canonical=canonical,dense_diagnostics=dense,pca=dict(fit_source_count=600,train_only=True,bootstrap_duplicates_used=False,
            dimensions=[16,8],source_set_sha256=sha(MODEL/'source_sets.json'),
            pca_audit_sha256=sha(MODEL/'pca_fit_audit.json'),diagnostics={k:{n:v[n] for n in ('retained_standard_deviations','scale_floor','scale_floor_count','projected_clip_fraction')} for k,v in pca['pca_diagnostics'].items()}),
        initial_assets=result['initial_assets'],bootstrap=bootstrap_summary,trainable_masks=mask_summary,
        sealed_asset_sha256={n:sha(MODEL/n) for n in ('preprocessing.npz','sampling.json','minibatch_plans.npz','trainable_masks.json','source_sets.json')},
        cost=result['cost'],execution_wall_seconds=execution['wall_seconds'],full_orchestration_wall_seconds=control['total_wall_seconds'],
        resources=execution['resources'],resource_after=execution['resource_after'],gpu_holders_retained=8,
        training_released_by_this_handoff=False,training_updates=0,simulator_attempts=0,development_effect_selection_performed=False,
        source_ids_train_development_intersection_count=0,descriptive_train_diagnostics_are_not_a_gate=True,
        summary_script_sha256=sha(__file__))
    dump(DEST/'summary.json',summary)
    dump(DEST/'future_training_ready_binding.json',dict(stage='training_final',scope='final_critic_training',phase='final',
        input_bundle=result['identity']['input_bundle'],design_sha256=result['identity']['design']['sha256'],
        specification_sha256=spec_sha,preflight=binding,simulator_attempts_limit=0,optimizer_updates_limit=32000,
        training_updates=32000,workflow_optimizer_updates_hard_limit=51200,authorization_status='not_released_by_this_file'))
    lines=[
        '最终 600 源真实零更新预检交接（2026-09-17；工作流20260916）','',
        '真实预检已通过。A/B 全部八个初始成员在 train600 与 development95 有效 cut 上完成 canonical 同 shape 严格逐位重载；开发计划分母仍为100。此次没有训练、策略部署或新增仿真，不能据预检通过声明算法收益。','',
        f'预检目录：`{MODEL}`；seal `{seal}`；result SHA `{binding["result_sha256"]}`。',
        f'固定 specification SHA：`{spec_sha}`。',
        f'新 config SHA `{protocol["config_sha256"]}`；freeze SHA `{protocol["freeze_sha256"]}`；READY v9 SHA `{result["preflight_ready"]["sha256"]}`。','',
        'A 从原旧四成员权重/PCA初始化，逐元素恒等检查通过；B 在600个唯一train原canonical特征上各用一次拟合PCA16/8，再新初始化四个完整小MLP。PCA、bootstrap与dev集合交集为0。每成员每task120抽120、总600；固定4000×32 minibatch计划、seed、八初态及trainable masks均已封存。A仅residual/advantage可训练，B全7058参数可训练；本轮实际优化仍为0。','',
        'canonical 核验覆盖全部13概率及槽0/11的成员与ensemble动作梯度，缓存逐位一致、state/a0不变、a0相对优势严格0。a0动作梯度不要求为0。','',
        'dense跨shape均存在非逐位差异，按已批准数值决定独立报告，没有新增容差或改变canonical路径。下表为本次实测最大绝对差；不是跨环境界限、接受阈值或训练效果。原报告保留逐成员/槽的参考尺度、source IDs和shape。','',
        '| 路径/集合 | 投影特征 | 13概率 | 成员动作梯度 | ensemble动作梯度 |',
        '| --- | ---: | ---: | ---: | ---: |']
    for path in ('A','B'):
        for purpose,record in dense[path].items():
            vals=[record['projected_features_max_abs_difference'],record['probabilities_max_abs_difference'],record['member_gradient_max_abs_difference'],max(v['max_abs_difference'] for v in record['ensemble_gradients'].values())]
            lines.append('| '+path+'/'+purpose+' | '+' | '.join(f'{v:.9g}' for v in vals)+' |')
    lines += ['',
        'runtime固定为lerobot Python3.12.13、torch2.7.1+cu126、NumPy2.2.6、CPU float32、两线程。B language保留维度中4个落在原0.001 scale floor；visual为0个，未修改floor/维数。非有限值、shape/source次序、缩放/耦合及同shape重载等硬检查通过。','',
        f'完整执行耗时{execution["wall_seconds"]:.2f}秒；模型预检{result["cost"]["wall_seconds"]:.2f}秒，其中输入验证{result["cost"]["stages"]["input_audit_seconds"]:.2f}秒、旧权重导入及PCA{result["cost"]["stages"]["old_import_and_train_pca_seconds"]:.2f}秒，A/B检查{result["cost"]["stages"]["A_initialization_export_checks_seconds"]:.2f}/{result["cost"]["stages"]["B_initialization_export_checks_seconds"]:.2f}秒。峰值RSS {execution["max_process_rss_kib"]/1024**2:.3f} GiB。',
        '账本前后逐字相同：42,874/50,000 sim，19,200/51,200 optimizer；technical reserve使用0。GPU8个holder保留。',
        f'账本SHA `{execution["resource_after"]["sha256"]}`。','',
        f'执行receipt：`{EXEC}`，seal `{execution_seal}`。',
        f'结构化摘要与后续training READY精确绑定模板：`{DEST}`。',
        '原采集/P0/首轮fit/preflight/deployment封存均未更改。正式final fit仍需分析端绑定本次真实seal放行，之后必须加载同一PCA、八初态、bootstrap/minibatches与masks；本交接不自动启动下一阶段。',
        'train600方向监督诊断单独见 `coordination/NATIVE10_TRAIN600_DIRECTION_DIAGNOSTICS.md`，不构成预检或训练新增门槛。','']
    report='\n'.join(lines)
    with REPORT.open('x') as f:f.write(report)
    with (DEST/'report.md').open('x') as f:f.write(report)
    dump(DEST/'complete.json',dict(status='complete',role='final_preflight_executor_handoff',
        files={str(p.relative_to(DEST)):sha(p) for p in DEST.rglob('*') if p.is_file()},
        preflight_seal_sha256=seal,specification_sha256=spec_sha,report_path=str(REPORT),report_sha256=sha(REPORT)))
    print(json.dumps(dict(summary=str(DEST),seal_sha256=sha(DEST/'complete.json'),report=str(REPORT),report_sha256=sha(REPORT),preflight=binding),ensure_ascii=False))


if __name__=='__main__':main()
