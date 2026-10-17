"""Post-completion calibration Q/raw/cost diagnostics; never selects a policy.

Only stored generation means and sealed outcomes are read. The frozen primary
artifact audit owns all seven comparisons and their confidence intervals. The
module does not invoke models, environments, bootstrap, calibration selection,
or heldout. Output is a new diagnostic seal, never a selected-policy seal.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from . import policy5_cost_diagnostic_v1 as pure
from .policy5_cost_diagnostic_v1 import (ROOT,METHODS,CORRECTIONS,COMPARISONS,
    _read,_hash,_canonical,_inside,_seal,_npz,_numeric,_radii,describe,association,command_diagnostics)

SCHEMA='native10_calibration_diagnostics_v1'
AUDIT_ROLE='native10_calibration_readonly_audit'
STAGE='calibration'
BANK='calibration_policy_v1'
REPLICATES=2
PRIMARY='post_minus_alarm_replan10'


def wave_gate(wave_path, *, root=ROOT):
    """Technical completion is checked before opening outcome-bearing inputs."""
    wave=_inside(wave_path,Path(root)/'calibration_execution'/STAGE)
    if not (wave/'launch_result.json').is_file(): raise ValueError('Wait for whole calibration wave exit')
    launch,spec=_read(wave/'launch_result.json'),_read(wave/'wave_spec.json')
    if (launch.get('status')!='complete' or launch.get('returncode')!=0
            or launch.get('lifecycle_covers_entire_wave') is not True or launch.get('hold_idle') is not False
            or spec.get('stage')!=STAGE or spec.get('bank_version')!=BANK or spec.get('workers')!=32
            or spec.get('paired_suffixes_per_state')!=2 or spec.get('original_primary_slots')!=100
            or spec.get('global_choice_applied_during_collection') is not False):
        raise ValueError('Calibration wave did not complete the registered technical contract')
    paths=sorted(wave.glob('workers/worker_*/status.json'))
    if len(paths)!=32: raise ValueError('Require 32 complete calibration workers')
    used={str(wave/name):_hash(wave/name) for name in ('launch_result.json','wave_spec.json')}
    rows=[];ids=[]
    for path in paths:
        _seal(path.parent,role='guarded_calibration_worker');row=_read(path)
        if (row.get('status')!='complete' or row.get('stage')!=STAGE or row.get('bank_version')!=BANK
                or row.get('workers')!=32 or row.get('wave_id')!=wave.name or row.get('missing_slot_ids')!=[]
                or row.get('config_sha256')!=spec['config_sha256'] or row.get('freeze_sha256')!=spec['freeze_sha256']
                or row.get('guard_factory')!='create_calibration_collector' or row.get('slot_entry')!='collect_calibration_slot'
                or row.get('completed_slot_records')!=len(row.get('assigned_slot_ids',[]))
                or row.get('global_choice_applied_during_collection') is not False):
            raise ValueError('Calibration worker incomplete or source/protocol identity changed')
        rows.append(row);ids.extend(row['assigned_slot_ids'])
        for name in ('status.json','complete.json','loaded_model_identity.json'):
            used[str(path.parent/name)]=_hash(path.parent/name)
    if len(ids)!=100 or len(set(ids))!=100 or {r['rank'] for r in rows}!=set(range(32)):
        raise ValueError('Calibration worker assignment lost a planned source')
    wall=_numeric(launch,'wall_seconds_including_lifecycle')
    if wall is None or wall<=0: raise ValueError('Invalid completed wave controller wall time')
    return dict(path=str(wave),launch=launch,spec=spec,workers=rows,episode_ids=ids,inputs=used)


def validate_gate(config,audit,*,config_sha256,bank_version=BANK):
    """Pure checks on full primary audit; never fabricate missing source labels."""
    bank=config['main_collection']['banks'][bank_version];ids=bank['episode_ids'];stats=audit.get('statistics',{})
    rows=audit.get('per_source',[])
    if (bank_version!=BANK or bank.get('kind')!='policy5' or bank.get('stage')!=STAGE
            or len(ids)!=100 or len(set(ids))!=100 or config['split_replicates']['calibration']!=2
            or audit.get('status')!='passed' or audit.get('role')!=AUDIT_ROLE or audit.get('stage')!=STAGE
            or audit.get('bank_version')!=bank_version or audit.get('config_sha256')!=config_sha256
            or audit.get('config_content_sha256')!=_canonical(config)
            or audit.get('protocol_sha256')!=config['analysis_approval']['protocol_sha256']
            or audit.get('planned_slots')!=100 or audit.get('technical_missing')!=0
            or len(rows)!=100 or [r.get('planned_slot_id') for r in rows]!=ids
            or stats.get('status')!='complete_statistics_proposal_only' or stats.get('source_denominator')!=100
            or stats.get('replicates')!=2 or stats.get('logical_outcomes_per_arm')!=200
            or stats.get('primary_ids')!=ids or stats.get('technical_missing')!=0):
        raise ValueError('Require matching sealed complete all-100 calibration audit')
    lookup={r['episode_id']:r for r in config['episode_manifest']};values=[];actual=[]
    for row in rows:
        primary=row['planned_slot_id'];resolved=row.get('resolved_episode_id');labels=row.get('outcomes',{})
        allowed=[primary]+config['main_collection']['replacement_candidates'].get(primary,[])
        if (resolved not in allowed or resolved in actual or lookup[resolved]['split']!='calibration'
                or row.get('task')!=lookup[resolved]['task'] or type(row.get('no_cut')) is not bool
                or set(labels)!=set(METHODS) or any(len(labels[m])!=2 or any(type(v) is not bool for v in labels[m]) for m in METHODS)):
            raise ValueError('Incomplete/duplicate calibration source or five-by-two labels')
        y=np.asarray([labels[m] for m in METHODS],dtype=bool)
        if row['no_cut']:
            if row.get('actual_cut') is not None or not np.all(y==y.flat[0]):
                raise ValueError('No-alarm source must retain one common outcome on every arm/repeat')
        elif type(row.get('actual_cut')) is not int or row['actual_cut']%10!=5 or not 5<=row['actual_cut']<=285:
            raise ValueError('Calibration requires a legal first-alarm cut')
        actual.append(resolved);values.append(y)
    values=np.asarray(values,dtype=bool);cut=sum(not r['no_cut'] for r in rows)
    if (stats.get('physical_branch_count')!=cut*10 or audit.get('physical_branches')!=cut*10
            or stats.get('resolved_source_ids')!=actual
            or stats['overall']['success_counts']!=dict(zip(METHODS,values.sum((0,2)).tolist()))):
        raise ValueError('Calibration counts differ from complete paired labels')
    for a,b in COMPARISONS:
        key=METHODS[a]+'_minus_'+METHODS[b];record=stats['overall']['comparisons'][key]
        delta=(values[:,a].astype(int)-values[:,b].astype(int)).mean(1)
        expected=dict(gain=float(delta.mean()),rescues=int((values[:,a]&~values[:,b]).sum()),
            harms=int((~values[:,a]&values[:,b]).sum()),positive_sources=int((delta>0).sum()),
            negative_sources=int((delta<0).sum()),zero_sources=int((delta==0).sum()))
        if any(record.get(k)!=v for k,v in expected.items()): raise ValueError('Primary paired statistics differ from labels')
    return values


def summarize_q(sources):
    cut=[r for r in sources if not r['no_cut']];tasks=sorted({r['task'] for r in sources})
    def group(rows,method):
        result=association([r['q'][method]['predicted_gain'] for r in rows],[r['q'][method]['actual_source_gain'] for r in rows])
        result['mean_prediction_minus_actual_gain']=(result['predicted_gain']['mean']-result['actual_gain']['mean']) if rows else None
        return result
    return {m:dict(all_cut_sources=group(cut,m),nonalias_to_a0=group([r for r in cut if not r['command_diagnostic']['methods'][m]['raw_alias_of_a0']],m),
        per_task={task:group([r for r in cut if r['task']==task],m) for task in tasks}) for m in CORRECTIONS}


def _loaded(wave,config):
    bound=config['calibration_collection']['selected_training'];selected=str(Path(config['critic_assets']).resolve())
    hashes=config['main_collection']['banks'][BANK]['critic_member_hashes']
    expected=dict(status='passed',stage=STAGE,selected_assets=selected,selected_path=selected,
        selected_seal_sha256=bound['selected_seal_sha256'],selected_reload_audit_sha256=bound['selected_reload_audit_sha256'],
        member_hashes=hashes,model_hashes=hashes,selection=dict(path='A',step=4000),optimizer_updates=0,
        actual_selector_paths=True,checkpoint_file_sha=True,frozen_parameter_buffer_versions=True,eval_cpu_no_parameter_grad=True,
        model_paths=[str(Path(selected)/f'models/refit/member_{m}/selected.pt') for m in range(4)])
    paths=[p for p in wave['inputs'] if Path(p).name=='loaded_model_identity.json']
    if len(paths)!=32: raise ValueError('Require all 32 actual loaded model receipts')
    for path in paths:
        record=_read(path)
        if any(record.get(k)!=v for k,v in expected.items()): raise ValueError('Actual loaded calibration critic differs from A4000')
    return dict(status='passed',workers=32,model_hashes=hashes,selection=dict(path='A',step=4000),selected_assets=selected)


def collect_diagnostics(config,audit,values,bound):
    """Artifact walker. Caller supplies a strict primary-audit SHA-bound reader."""
    registry={r['episode_id']:r for r in config['episode_manifest']};sources=[];banks=[];branches=[];captures=[];commands=[]
    root=Path(bound.root);protocol=config['analysis_approval']['protocol_sha256'];matching=config['matching']
    for index,row in enumerate(audit['per_source']):
        actual=row['resolved_episode_id'];case=registry[actual];source_path=root/'sources'/case['case_id']
        source=bound(source_path/'summary.json');bound(source_path/'complete.json')
        if (source.get('case')!=case or source.get('planned_slot_id')!=row['planned_slot_id']
                or source.get('protocol_sha256')!=protocol or source.get('actual_cut')!=row['actual_cut']
                or source.get('no_cut')!=row['no_cut'] or source.get('source_capture_stage') not in ('calibration','technical_reserve')
                or source.get('selection_audit',{}).get('training_fallback_allowed') is not False):
            raise ValueError('Calibration source differs from audited first-alarm identity')
        identity=dict(planned_slot_id=row['planned_slot_id'],resolved_episode_id=actual,task=row['task'])
        captures.append(dict(identity,status='accepted',source_capture_stage=source['source_capture_stage'],
            **{key:_numeric(source,key) for key in ('wall_seconds','policy_calls','policy_seconds','environment_seconds','steps')}))
        for rejected in row['resolution']['ordered_rejections']:
            reject_path=root/'sources'/rejected['episode_id'];record=bound(reject_path/'rejection.json');bound(reject_path/'complete.json')
            if record.get('before_first_action') is not True: raise ValueError('Replacement rejection followed an action')
            captures.append(dict(planned_slot_id=row['planned_slot_id'],resolved_episode_id=rejected['episode_id'],task=row['task'],
                status='rejected_before_first_action',reason=record['reason'],wall_seconds=None,policy_calls=None,policy_seconds=None,environment_seconds=None,steps=0,
                missing_cost_reason='Original rejection record does not save timing; not imputed to zero'))
        item=dict(identity,no_cut=row['no_cut'],actual_cut=row['actual_cut'],scene_fingerprint=row['scene_fingerprint'],
            success_counts=dict(zip(METHODS,values[index].sum(1).tolist())),logical_outcomes_per_arm=2)
        if row['no_cut']:
            item.update(q=None,command_diagnostic=None,physical_branches=0);sources.append(item);continue
        cut=row['actual_cut'];bank=root/'banks'/BANK/case['case_id']/f'cut{cut:03d}'
        generation=bound(bank/'generation.json');bound(bank/'complete.json');plans=bound(bank/'plans.npz',arrays=True)
        guard_path=root/'calibration_guard'/STAGE/BANK/actual
        guard=bound(guard_path/'bank_check.json');guard_seal=bound(guard_path/'complete.json')
        if (guard_seal.get('role')!='calibration_same_bank_check' or guard_seal.get('protocol_sha256')!=protocol
                or guard.get('status')!='passed' or guard.get('checked_before_branch') is not True
                or guard.get('episode_id')!=actual or guard.get('cut')!=cut
                or guard.get('source_seal_sha256')!=bound.digest(source_path/'complete.json')
                or guard.get('bank_seal_sha256')!=bound.digest(bank/'complete.json')
                or guard.get('old_development_a0_compared') is not False
                or guard.get('noise_sha256')!=generation.get('base_generation',{}).get('noise_sha256')):
            raise ValueError('Calibration before-branch same-bank guard differs')
        if (generation.get('episode_id')!=actual or generation.get('cut_step')!=cut
                or generation.get('stage')!=STAGE or generation.get('bank_version')!=BANK
                or generation.get('protocol_sha256')!=protocol
                or generation.get('model_hashes')!=config['main_collection']['banks'][BANK]['model_hashes']):
            raise ValueError('Calibration bank provenance changed')
        diagnostic=command_diagnostics(plans,matching);q={}
        predictions=generation.get('bank_predictions',{})
        if set(predictions)!=set(METHODS[1:]): raise ValueError('Saved final-bank means missing')
        for name in METHODS[1:]:
            record=predictions[name];gain=float(record['mean_gain']);prob=float(record['candidate_mean_probability']);a0=float(record['a0_mean_probability'])
            if not np.isfinite([gain,prob,a0]).all() or not 0<=prob<=1 or not 0<=a0<=1 or name==METHODS[1] and gain!=0:
                raise ValueError('Invalid saved Q/a0 anchor')
            actual_gain=float((values[index,METHODS.index(name)].astype(int)-values[index,1].astype(int)).mean())
            q[name]=dict(predicted_gain=gain,candidate_probability=prob,a0_probability=a0,actual_source_gain=actual_gain)
            commands.append(dict(identity,method=name,**diagnostic['methods'][name]['actual_delta'],raw_alias_of_a0=diagnostic['methods'][name]['raw_alias_of_a0'],
                predicted_gain=gain,actual_source_gain=actual_gain))
        cost=dict(identity,**{key:_numeric(generation,key) for key in ('restore_seconds','candidate_bank_seconds','generation_wall_seconds')})
        components={'base':generation.get('base_generation',{}),**generation.get('guidance',{}),
                    'post':generation.get('post_gradient',{}),'objective':generation.get('objective_stats',{})}
        for name,record in components.items():
            for key in ('seconds','policy_calls','objective_forward_calls','backward_calls','critic_member_forward_calls','critic_member_backward_calls','critic_forward_seconds',
                        'peak_cuda_allocated_mib','peak_cuda_reserved_mib','incremental_peak_cuda_allocated_mib'):
                cost[name+'_'+key]=_numeric(record,key)
        cost['fallbacks']={m:components[m].get('fallback') for m in ('base','velocity','direct')};banks.append(cost)
        item.update(q=q,command_diagnostic=diagnostic,physical_branches=10,generation_cost=cost,
            matching_groups=generation.get('matching',{}).get('groups'),guard=guard,
            flow_updates={m:generation['guidance'][m].get('updates',[]) for m in ('velocity','direct')},post_gradient=generation.get('post_gradient'))
        for arm,method in enumerate(METHODS):
            for repeat in range(2):
                folder=root/'rollouts'/STAGE/BANK/case['case_id']/f'cut{cut:03d}'/method/f'repeat_{repeat}'
                record=bound(folder/'summary.json');bound(folder/'complete.json')
                if (record.get('status')!='complete' or record.get('episode_id')!=actual or record.get('method')!=method or record.get('repeat')!=repeat
                        or record.get('candidate_bank_sha256')!=bound.digest(bank/'complete.json')
                        or record.get('success') is not bool(values[index,arm,repeat])):
                    raise ValueError('Calibration branch differs from audited paired labels')
                r=dict(identity,method=method,repeat=repeat,**{key:_numeric(record,key) for key in ('restore_seconds','policy_calls','policy_seconds','environment_seconds','wall_seconds',
                    'requested_prefix_steps','actual_prefix_steps','terminal_step')},executed_prefix_delta=None)
                n=record['actual_prefix_steps']
                if type(n) is not int or not 0<=n<=(5 if method==METHODS[0] else 10):raise ValueError('Invalid actual prefix length')
                if method!=METHODS[0]:
                    if record.get('command_sha256')!=diagnostic['methods'][method]['raw10_sha256']:raise ValueError('Branch raw10 differs from bank')
                    r['executed_prefix_delta']=_radii(plans[method][:n].astype(float)-plans[METHODS[1]][:n].astype(float))
                branches.append(r)
        sources.append(item)
    cut=[r for r in sources if not r['no_cut']]
    gkeys=sorted({key for r in banks for key in r if key not in ('planned_slot_id','resolved_episode_id','task','fallbacks')})
    bkeys=('restore_seconds','policy_calls','policy_seconds','environment_seconds','wall_seconds','actual_prefix_steps','terminal_step')
    quality=dict(raw_unique_group_distribution=dict(Counter(r['command_diagnostic']['raw_unique_groups'] for r in cut)),
        clipped_collision_sources=sum(r['command_diagnostic']['clipped_collision_of_distinct_raw'] for r in cut),
        unmatched_final_rms_sources=sum(not r['command_diagnostic']['correction_rms_matched'] for r in cut),
        raw_invariant_failure_counts={m:{key:sum(not r['command_diagnostic']['methods'][m][key] for r in cut)
            for key in ('raw_tail_bit_exact','outside_mask_bit_exact','raw_delta_equals_critic_delta','caps_within_frozen_tolerance')} for m in METHODS[1:]},
        zero_channel_counts={m:{g:sum(r['command_diagnostic']['methods'][m]['zero_'+g] for r in cut) for g in ('xyz','gripper')} for m in CORRECTIONS},
        aliases_of_a0={m:sum(r['command_diagnostic']['methods'][m]['raw_alias_of_a0'] for r in cut) for m in CORRECTIONS},
        matching_group_flags={g:{flag:sum((r.get('matching_groups') or {}).get(g,{}).get(flag) is True for r in cut) for flag in ('zero_group','shrunk')} for g in ('xyz','gripper')})
    return dict(per_source=sources,command_rows=commands,branch_cost_rows=branches,capture_cost_rows=captures,
        source_denominator=100,command_q_denominator=len(cut),q_missing_no_cut_sources=100-len(cut),physical_branches=len(branches),quality=quality,
        q_vs_actual=summarize_q(sources),final_raw_amplitude={m:{k:describe(r[k] for r in commands if r['method']==m)
            for k in ('xyz_rms','gripper_rms','xyz_linf','gripper_linf')} for m in METHODS[1:]},
        coverage=dict(fixed_post_physical_measurement_sources=len(cut),no_q_sources=100-len(cut),source_denominator=100,
            global_post_option_alarm_coverage=len(cut)/100,global_replan_option_correction_coverage=0,
            interpretation='Coverage of the two preregistered options only; this module does not choose or apply either option'),
        cost=dict(capture={k:describe(r.get(k) for r in captures) for k in ('wall_seconds','policy_calls','policy_seconds','environment_seconds','steps')},
            capture_records_by_status=dict(Counter(r['status'] for r in captures)),generation={k:describe(r.get(k) for r in banks) for k in gkeys},
            branches_by_method={m:{k:describe(r.get(k) for r in branches if r['method']==m) for k in bkeys} for m in METHODS},
            guidance_fallback_counts={m:dict(Counter(str(r['fallbacks'].get(m)) for r in banks)) for m in ('base','velocity','direct')},
            partial_prefix_branches_by_method={m:sum(r['actual_prefix_steps']<r['requested_prefix_steps'] for r in branches if r['method']==m) for m in METHODS}))


def _fmt(value,n=3): return '缺失/未定义' if value is None else f'{value:.{n}f}'


def render(result):
    s=result['primary_statistics'];cost=result['cost'];runtime=result['runtime'];quality=result['quality']
    lines=['# Native10 校准：完整诊断与成本', '',f"产出日期：{result['created_utc'][:10]}；工作流20260916。",'',
        '固定 A4000 四成员与 post 主注入。主审计的七个比较和区间原样引用；post−replan为预登记主比较，其他为次要描述。'
        '本模块不重新选择方法、不使用Q门、不创建策略选择seal、不放行held。校准结果不是独立成功验证。','',
        f"保留全部100计划源，每臂200个逻辑结局；{result['command_q_denominator']}个报警源有候选，"
        f"{result['q_missing_no_cut_sources']}个无报警源广播共同结局。Q仅覆盖报警源，无报警不伪造Q。",'',
        '| 方法 | 成功/200 | 成功率 |','|---|---:|---:|']
    for m in METHODS:lines.append(f"| {m} | {s['overall']['success_counts'][m]} | {100*s['overall']['success_rates'][m]:.2f}% |")
    lines+=['','| 比较 | 角色 | pp | 源级95% CI（pp） | 救回/损害 | 正/负/零源 |','|---|---|---:|---|---:|---:|']
    for key,r in s['overall']['comparisons'].items():
        lo,hi=r['source_95ci'];role='主比较' if key==PRIMARY else '次要比较'
        lines.append(f"| {key} | {role} | {100*r['gain']:+.2f} | [{100*lo:.2f}, {100*hi:.2f}] | {r['rescues']}/{r['harms']} | {r['positive_sources']}/{r['negative_sources']}/{r['zero_sources']} |")
    boot=s['bootstrap'];lines+=['',f"原统计：任务内整源bootstrap {boot['draws']:,}次，seed={boot['seed']}，percentile95/linear，未做多比较校正。"
        '同源两后缀保留配对；不估计单源置信度，不用CI或Q改选择规则。','',
        '| 任务 | N | normal/replan/V/D/P成功率 | V/D/P相对replan pp |','|---|---:|---|---|']
    for task,r in s['per_task'].items():
        rates=r['success_rates'];deltas='/'.join(f"{100*(rates[m]-rates[METHODS[1]]):+.2f}" for m in CORRECTIONS)
        lines.append(f"| {task} | {r['sources']} | "+'/'.join(f'{100*rates[m]:.2f}%' for m in METHODS)+' | '+deltas+' |')
    lines+=['','| 分层 | N | 每臂逻辑结局 | normal/replan/V/D/P成功数 |','|---|---:|---:|---|']
    for key in ('alarm_conditioned','no_cut_common_outcomes'):
        r=s[key];counts='/'.join(str(r['success_counts'][m]) for m in METHODS) if r['success_counts'] is not None else '无源'
        lines.append(f"| {key} | {r['sources']} | {r['logical_outcomes_per_arm']} | {counts} |")
    lines+=['','## 存储 Q 与真实收益','',
        '| 方法 | 有Q源数 | 平均预测ΔQ | 实测Δ成功率pp | 平均预测−实测 | Pearson/Spearman | Q正且实测正/负/零源 |',
        '|---|---:|---:|---:|---:|---|---|']
    for m in CORRECTIONS:
        r=result['q_vs_actual'][m]['all_cut_sources'];t=r['sign_table'];actual=r['actual_gain'].get('mean')
        lines.append(f"| {m} | {r['sources']} | {_fmt(r['predicted_gain'].get('mean'),6)} | {_fmt(None if actual is None else 100*actual,2)} | {_fmt(r['mean_prediction_minus_actual_gain'],6)} | {_fmt(r['pearson'])}/{_fmt(r['spearman'])} | {t['q_positive_actual_positive']}/{t['q_positive_actual_negative']}/{t['q_positive_actual_zero']} |")
    lines+=['','Q为生成时固定a0的成员均值概率差，来自保存的bank记录；没有重新推理。这里只测量均值偏差、关联和符号，不能解释为校准良好的概率或因果证据。'
        '逐任务及去除raw a0别名后的同口径诊断见result.json。',
        f"物理post候选覆盖{result['command_q_denominator']}/100源。预登记全局post选项在报警时纠偏；全局replan选项纠偏覆盖为0。此处只描述两选项覆盖，不封存或执行选择。",'',
        '## 最终 raw 命令与生成检查','',
        f"raw不同命令组数分布：`{json.dumps(quality['raw_unique_group_distribution'],sort_keys=True)}`；"
        f"clip表示碰撞源{quality['clipped_collision_sources']}；RMS未匹配源{quality['unmatched_final_rms_sources']}。",
        f"raw尾段/mask外/评分映射/cap失败计数：`{json.dumps(quality['raw_invariant_failure_counts'],sort_keys=True)}`。",'',
        '| 方法 | XYZ RMS均值 | grip RMS均值 | XYZ/grip零通道源 | raw a0别名源 |','|---|---:|---:|---:|---:|']
    for m in CORRECTIONS:
        r=result['final_raw_amplitude'][m];zero=quality['zero_channel_counts'][m]
        lines.append(f"| {m} | {_fmt(r['xyz_rms'].get('mean'),6)} | {_fmt(r['gripper_rms'].get('mean'),6)} | {zero['xyz']}/{zero['gripper']} | {quality['aliases_of_a0'][m]} |")
    lines += ['',f"匹配缩半径/零组：`{json.dumps(quality['matching_group_flags'],sort_keys=True)}`。",
        f"fallback：`{json.dumps(cost['guidance_fallback_counts'],sort_keys=True)}`。",
        f"不足原prefix步数的分支：`{json.dumps(cost['partial_prefix_branches_by_method'],sort_keys=True)}`。",'',
        '命令诊断来自本轮raw50计划，mask外、尾段与a0按既定规则保留，Q使用C(raw)=clip(raw)。same-bank guard在首分支前封存a0/初始噪声/slot0/梯度及同幅证据；'
        '没有与旧dev a0比较，也没有复用旧guided动作。最终10步幅度不限制flow中间查询；匹配可以放大原生方向。', '',
        '## 分项成本与资源','',
        f"实际物理分支{result['physical_branches']}；账本分资源计数、阶段/类型及新增attempt原样取自主审计：`{json.dumps(result['resource_summary'],sort_keys=True)}`。",
        f"波次controller墙钟（含lifecycle）{runtime['wave_controller_wall_seconds']:.2f}s；"
        f"worker初始化均值{_fmt(runtime['worker_loading_seconds'].get('mean'))}s，中位{_fmt(runtime['worker_loading_seconds'].get('median'))}s。"
        '初始化含绑定校验、CUDA和模型加载，不能等同纯模型加载。', '',
        '| 成本项 | 有记录数 | 缺失 | 均值s | 累计worker-s |','|---|---:|---:|---:|---:|']
    timing=[('source capture wall',cost['capture']['wall_seconds'])]
    timing += [(key,cost['generation'].get(key,dict(observed=0,missing=result['command_q_denominator']))) for key in ('restore_seconds','candidate_bank_seconds','generation_wall_seconds','base_seconds','velocity_seconds','direct_seconds','post_seconds')]
    for name,r in timing:lines.append(f"| {name} | {r['observed']} | {r['missing']} | {_fmt(r.get('mean'),6)} | {_fmt(r.get('sum'))} |")
    lines+=['','| 分支方法 | 恢复均值s | 后缀策略均值s | 环境均值s | wall均值s | wall累计worker-s |','|---|---:|---:|---:|---:|---:|']
    for m,r in cost['branches_by_method'].items():
        lines.append('| '+m+' | '+' | '.join(_fmt(r[k].get('mean'),4) for k in ('restore_seconds','policy_seconds','environment_seconds','wall_seconds'))+' | '+_fmt(r['wall_seconds'].get('sum'))+' |')
    lines+=['', 'source capture wall覆盖reset至报警cut或无报警终局，含报警计算；其中policy_seconds只记策略采样，不含全部D/G0计算。'
        '预动作拒绝的旧记录不保存计时，相关成本保留缺失。bank generation wall含restore，candidate_bank不含恢复；post秒数只表示额外梯度。'
        '分支policy_seconds计后缀采样，environment_seconds还含source replay，与restore重叠；wall包含恢复和后缀。'
        'worker累计秒不可当波次墙钟，GPU峰值不可相加，不据此宣称相对串行加速。',
        f"本轮新source（含预动作拒绝）/bank/branch/collection/guard/波次产物{runtime['disk_total_logical_bytes']:,}逻辑字节；不计模型及本报告。",'',
        '## 可复现证据','',
        '逐源及逐分支见per_source.csv、commands.csv、capture_costs.csv、branch_costs.csv；完整成本、guard和Q诊断见result.json。'
        '输入文件逐项SHA保存在provenance.json，避免将成千文件清单内嵌报告。',
        f"主审计：[{result['audit_path']}]({result['audit_path']})；seal `{result['audit_seal_sha256']}`。",
        '本模块0模型/PCA/仿真/优化调用；账本前后SHA相同。没有写selected-policy seal，没有读取heldout结局，也不会启动下一阶段。','']
    return '\n'.join(lines)


def run(config_path,audit_path,wave_path,*,output_path,freeze_path=None,root=ROOT):
    root=Path(root).resolve();output=_inside(output_path,root/'calibration_diagnostics')
    if output.exists():raise FileExistsError('Diagnostic output must be a new directory')
    wave=wave_gate(wave_path,root=root)  # All outcomes remain unopened if incomplete.
    audit_path=_inside(audit_path,root);_seal(audit_path,role=AUDIT_ROLE)
    config_path=Path(config_path).resolve();freeze_path=Path(freeze_path).resolve() if freeze_path else config_path.parent/'freeze.json'
    config,audit,frozen=_read(config_path),_read(audit_path/'result.json'),_read(freeze_path)
    configsha=_hash(config_path)
    if (frozen.get('config_sha256')!=configsha or frozen.get('files',{}).get(str(config_path))!=configsha
            or wave['spec']['config_sha256']!=configsha or wave['spec']['freeze_sha256']!=_hash(freeze_path)):
        raise ValueError('Calibration config/freeze/wave binding changed')
    values=validate_gate(config,audit,config_sha256=configsha)
    ids=config['main_collection']['banks'][BANK]['episode_ids'];cuts=sum(not r['no_cut'] for r in audit['per_source'])
    if (set(wave['episode_ids'])!=set(ids) or sum(w['no_cut_sources'] for w in wave['workers'])!=100-cuts
            or sum(w['actual_branch_count'] for w in wave['workers'])!=10*cuts):raise ValueError('Wave/source coverage differs from primary audit')
    artifacts={};used=dict(wave['inputs'])
    for item in audit['artifacts']:
        path=_inside(item['path'],root)
        if str(path) in artifacts:raise ValueError('Duplicate primary audit artifact identity')
        artifacts[str(path)]=item['sha256']
    class Bound:
        def __init__(self):self.root=root
        def digest(self,path):
            path=_inside(path,root);expected=artifacts.get(str(path))
            if expected is None or _hash(path)!=expected:raise ValueError('Artifact missing from primary audit or changed: '+str(path))
            used[str(path)]=expected;return expected
        def __call__(self,path,*,arrays=False):
            self.digest(path);return _npz(path) if arrays else _read(path)
    for path in (config_path,freeze_path,audit_path/'complete.json',audit_path/'result.json'):
        used[str(path)]=_hash(path)
    ledger=root/'budget/attempts.jsonl';before=_hash(ledger)
    data=collect_diagnostics(config,audit,values,Bound());loaded=_loaded(wave,config)
    if data['physical_branches']!=audit['physical_branches']:raise ValueError('Cost branch coverage differs from primary audit')
    folders=[root/'banks'/BANK,root/'rollouts'/STAGE/BANK,root/'collections'/STAGE/BANK,root/'calibration_guard'/STAGE/BANK,Path(wave_path)]
    sourceids={r['resolved_episode_id'] for r in data['capture_cost_rows']}
    folders += [root/'sources'/identity for identity in sorted(sourceids)]
    disk={}
    for folder in folders:
        files=[p for p in folder.rglob('*') if p.is_file()]
        disk[str(folder.relative_to(root))]=dict(files=len(files),logical_bytes=sum(p.stat().st_size for p in files))
    runtime=dict(wave_controller_wall_seconds=wave['launch']['wall_seconds_including_lifecycle'],
        worker_loading_seconds=describe(r['loading_seconds'] for r in wave['workers']),
        worker_wall_seconds=describe(r['wall_seconds'] for r in wave['workers']),
        first_worker_started_utc=min(r['started_utc'] for r in wave['workers']),last_worker_finished_utc=max(r['finished_utc'] for r in wave['workers']),
        disk=disk,disk_total_logical_bytes=sum(r['logical_bytes'] for r in disk.values()),
        actual_loaded_critic=loaded,no_serial_speedup_claim=True,component_times_may_overlap=True)
    for path in (Path(__file__).resolve(),Path(pure.__file__).resolve()):used[str(path)]=_hash(path)
    after=_hash(ledger)
    if before!=after:raise ValueError('Ledger changed during read-only diagnostics')
    result=dict(data,schema=SCHEMA,status='complete',created_utc=datetime.now(timezone.utc).isoformat(),stage=STAGE,bank_version=BANK,
        primary_comparison=PRIMARY,secondary_comparisons=[METHODS[a]+'_minus_'+METHODS[b] for a,b in COMPARISONS if METHODS[a]+'_minus_'+METHODS[b]!=PRIMARY],
        primary_statistics=audit['statistics'],audit_path=str(audit_path),audit_seal_sha256=_hash(audit_path/'complete.json'),
        config_sha256=configsha,protocol_sha256=config['analysis_approval']['protocol_sha256'],runtime=runtime,
        resource_summary={k:audit.get(k) for k in ('new_attempts','attempts_by_stage_kind','resource_totals')},
        selected_training=config['calibration_collection']['selected_training'],ledger_sha256_before=before,ledger_sha256_after=after,
        simulator_calls=0,model_calls=0,optimizer_updates=0,pca_calls=0,heldout_reads=0,selection_seals_written=0,
        no_q_gate=True,independent_validation_success=False,new_statistics_or_selection_rules=False,next_stage_automatically_started=False)
    report=render(result);output.mkdir(parents=True,exist_ok=False)
    def dump(name,value):
        with (output/name).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    dump('result.json',result)
    dump('provenance.json',dict(inputs=[dict(path=p,sha256=h) for p,h in sorted(used.items())],ledger_sha256_before=before,ledger_sha256_after=after,
        main_audit_owns_statistics_and_artifact_verification=True,diagnostic_rehashes_consumed_inputs_only=True))
    with (output/'report.md').open('x') as stream:stream.write(report)
    sourcecols=['planned_slot_id','resolved_episode_id','task','no_cut','actual_cut','scene_fingerprint']+list(METHODS)
    with (output/'per_source.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=sourcecols);writer.writeheader()
        for r in result['per_source']:writer.writerow({**{k:r[k] for k in sourcecols[:6]},**r['success_counts']})
    for filename,key in (('commands.csv','command_rows'),('capture_costs.csv','capture_cost_rows'),('branch_costs.csv','branch_cost_rows')):
        rows=result[key];cols=sorted({k for row in rows for k in row})
        with (output/filename).open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=cols);writer.writeheader()
            for row in rows:writer.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    if _hash(ledger)!=before:raise ValueError('Ledger changed before diagnostic sealing')
    dump('complete.json',dict(status='complete',role=SCHEMA,files={p.name:_hash(p) for p in sorted(output.iterdir()) if p.is_file()},
        simulator_calls=0,model_calls=0,optimizer_updates=0,selection_seals_written=0))
    return dict(status='complete',path=str(output),seal_sha256=_hash(output/'complete.json'),source_denominator=100,command_q_denominator=cuts)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('config','audit','wave','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--freeze',type=Path);parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args()
    print(json.dumps(run(args.config,args.audit,args.wave,output_path=args.output,freeze_path=args.freeze,root=args.root),ensure_ascii=False))


if __name__=='__main__':main()
