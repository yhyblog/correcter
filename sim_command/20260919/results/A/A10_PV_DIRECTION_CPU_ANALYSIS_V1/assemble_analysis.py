"""Package the authorized saved-data analysis; stdlib text/JSON only.

Reads the already produced arithmetic tables and narrow source text. Does not
import the arithmetic runner or any project/runtime module, or execute formulas.
All writes are new files in this task's private package.
"""
import ast
import csv
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
B = P.parents[2]
C0 = B / 'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1'
C5 = B / 'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1'


def load(path):
    return json.loads(Path(path).read_text())


def ref(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path), size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def put(name, data):
    text = data if isinstance(data, str) else json.dumps(
        data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with (P / name).open('x') as handle:
        handle.write(text)


inputs = load(P / 'INPUT_MANIFEST.json')
input_index = {x['path']: x for x in inputs['files']}
directions = load(P / 'DIRECTION_STAGES.json')
objectives = load(P / 'OBJECTIVE_RECOMPUTATION.json')['rows']
taus = load(P / 'TAU_LOCAL_ANALYSIS.json')['rows']
identity = load(P / 'IDENTITY_PROOF.json')
checks = load(P / 'RELATION_CHECKS.json')
assert len(checks['checks']) == 78 and all(x['passed'] for x in checks['checks'])

# Span endpoints are inclusive; only source text/AST, never imports or exec.
spans = {
    'corrector/guidance.py': [
        ('objective_and_saved_probabilities', 109, 156),
        ('gradient_summary_and_Post_S_squared', 182, 206),
        ('local_velocity_update', 218, 280),
        ('flow_hook_tau_and_dispatch', 298, 318)],
    'corrector/actions.py': [('ActionTransform_forward', 22, 26)],
    'corrector/solo.py': [('fixed_constraints_and_own_radius', 23, 77)],
    'corrector/raw_commands.py': [('preserve_raw_anchor', 5, 28)],
    'vendor_vla/src/lerobot/policies/pi05/modeling_pi05.py': [
        ('time_and_Euler', 827, 863), ('native_output_projection', 899, 902)],
}
source_rows = []
for package, state in [(C0, 'step0'), (C5, 'cut5')]:
    code_manifest = load(package / 'code/CODE_MANIFEST.json')
    code_index = {x['path']: x for x in code_manifest['files']}
    selected = dict(spans)
    if state == 'step0':
        selected['diagnostic.py'] = [
            ('saved_context_and_shared_objective', 147, 176),
            ('Post_saved_gradient_and_score', 189, 197),
            ('Velocity_saved_derivative_and_score', 219, 238)]
    else:
        selected['runtime_engine.py'] = [('intervention_saved_fields', 203, 246)]
    for relative, selections in selected.items():
        path = package / 'code' / relative
        item = ref(path)
        assert item['sha256'] == input_index[str(path)]['sha256']
        assert item['sha256'] == code_index[relative]['sha256']
        source = path.read_text()
        ast.parse(source)
        lines = source.splitlines()
        excerpts = []
        for name, first, last in selections:
            assert 1 <= first <= last <= len(lines)
            excerpts.append(dict(name=name, first_line=first, last_line=last,
                                 numbered_text='\n'.join(
                                     f'{i}: {lines[i-1]}' for i in range(first, last+1))))
        source_rows.append(dict(**item, state=state,
                                verified_against_code_manifest=True,
                                loaded_as_text_only=True, excerpts=excerpts))
put('FORMULA_SOURCE_MAP.json', dict(
    files=source_rows, source_files_imported=0, formula_calls=0,
    source_manifest_refs=[ref(C0/'code/CODE_MANIFEST.json'), ref(C5/'code/CODE_MANIFEST.json')],
    scope='five shared formula files plus each saved-data caller; no repository-wide audit',
    legacy_docstring_note='guidance.py:196-197 mentions historical shared radii. '
                         'The executed callers above call project_solo separately; '
                         'the saved groups declare other_direction_capacities_used=false.'))

formula_text = '''本任务的公式、坐标与证据边界

逐行源码及两个冻结包的完整文件 SHA 见 FORMULA_SOURCE_MAP.json；只按文本读取，未导入或调用。字段、shape、dtype、payload SHA 见 ARRAY_FIELDS_AND_UNITS.json。

令 raw a0 为原生 50×4 环境命令，b0=clamp(raw a0,−1,1)[:10]。J(b;b0)=四个冻结成员 sigmoid 概率差的均值，第一槽 b0 固定 detach。保存的 Post g=dJ/db|b0 是命令坐标梯度。命令是环境的归一化控制量，不是米或物理速度；flow 的 τ/dt 也不是仿真时间。

ActionTransform 为 u=S y+c、b=clamp(u,−1,1)，S=(q99−q01)/2，c=(q99+q01)/2。两状态保存 S=[1.8894232511520386,2.2244925498962402,3.2869668006896973,0.3156581223011017]。零 quantile 差有 eps 分支，此处保存 S 全非零。c 的数值没有从日志恢复，差分公式不需要 c；未打开 normalizer 权重补值。

Post：dP=S² g，随后按锚点 boundary-clearance mask、独立组半径处理。S² 为未裁剪线性变换在命令坐标的度量；实际 Post 在 b0 求导再作 mask，不能将其说成已观测的逐 τ clean 梯度。代码 guidance.py:201–205；保存 raw_direction 与 float32 S²g 算术核对通过。

Velocity：y=x−τv；g_y=dJ/dy=S D g_b，其中 D 是该局部 clean 经命令变换后的真实 clamp 雅可比。g_b 是该局部点的命令梯度，未保存，不能用锚点 g 替换。保存 action_gradient_tau_k / action_gradient_k 是 d=dJ/dv=−τg_y，1×50×32；仅前 10×4 非零。代码 guidance.py:235–256。在固定 x 上，v′=v+αd，α=10；理想实数算术 δy=−ταd=ατ²g_y，未裁剪命令位移为 Sδy。因而原点评价的一阶局部增量是 α||d||²≥0；这是线性预测，不是有限步的单调保证。

十次 Euler 的 dt=−0.1；原代码 x_next=x+dt*v_returned。纯注入部分理想位移 dt*αd=|dt|ατg_y，其与同一局部 g_y 的点积为 α|dt|/τ ||d||²≥0。这不是下一 τ 的 J 预测，后续 denoise 的响应、有限步曲率、新 clamp 活跃集和转换舍入未由该式消除。静态代数未见表面反号，不等于根因已排除。未经证据不改符号、α 或阈值。

局部 before/after 的 J 评价的是 clamp(S*(x−τv)+c) 与 clamp(S*(x−τupdated)+c)，其中 updated 在 flow_update 中转为 float32 计算。返回时又 cast 回输入 velocity.dtype；原 sampler 再执行 Euler。末 τ 浮点值为 0.10000000149011612；dt 来源为 Python −1/10。完整逐 τ 输入、返回 dtype/字节与 Euler 输出没有保存；step0 的 own_internal_guided 仅为最终 Euler x 的 float32 导出，cut5 连这个最终内部 x 也没有保存。不能把末 τ after 当成独立最终 guided Q；目前该评分为 null。

独立半径：m=(1−|b0|≥0.05)；d_m=m*d；每组 n=RMS(d_m)，XYZ 的 30 个坐标、gripper 的 10 个坐标均含 mask 零位。保存 e=d_m/max(n,1e−10)，组 capacity 由 min(1−|b0|,Linf)/|e| 限定；保存 r=min(requested_RMS,capacity)*(1−1e−6)，小零组 r=0；requested_delta=r*e。float64 运算后写回 float32，并仅将变动位替换进 raw a0，以保留原 raw 饱和位和尾部。这次只验证已有数组/已记录 scalar 之间的恒等关系，没有重新执行投影或求新 capacity。

本次两状态四分支 gripper mask 后均为零，XYZ 的正组缩放保持 masked 方向的点积符号；float32 写回的微差也未改号。这是这四个保存样本的结果，不是多组独立缩放普遍保持全局点积的定理。guided_native_raw_delta 以 raw a0 为原点；guided_clamped_delta 以 b0 为原点，分别报告，不把 raw 数值当作未裁剪即可执行的控制量。

字段名注意：flow_update 的 gradient_norm 是 clean g_y 范数，injection_gradient_norm 才是 dJ/dv 范数；clean_unclipped_linf 实际来自变换后的 before_unclipped 环境命令，不是内部 y 范数。clipping_fraction/boundary_fraction 是更新前局部 C10×4 的统计；更新后的裁剪集合没有保存。accepted=true、halvings=0 只说明固定更新完成，没有 Q 接受条件。

anchor/final 的成员概率可独立重算 J。每 τ 仅保存 before/after J 标量，局部成员概率未保存；可作标量差，不能补成独立概率重算。J+保存 anchor mean 给出的局部均值也只是派生数（原 float32 reduction 有微小舍入），不是另一次网络评价。概率上升余量 1−(anchor_mean+J_before) 有界；一阶预测超过余量表明线性外推不能等于有限变化，不能据此单独确认 α、曲率或饱和是根因。

只读算术入口为 analyze_saved.py；只读表示来源不改，结果以 exclusive-create 写入本任务包。它拒绝覆盖当前结果。复核可按其公式与 input SHA 表独立读取；不要直接重跑入口覆盖本包。后续 CPU 包装仅读取其表格与源码文本。所有旧产物保持不变。
'''
put('FORMULAS_AND_UNITS.md', formula_text)

hypotheses = [
    dict(id='H1', hypothesis='错误符号/坐标漏换算', status='静态公式未见表面反号；不足以排除实现路径或记录缺项',
         evidence='S²g、dJ/dv=−τg_y、v+10d、负 dt 在同一局部坐标的理想一阶符号相容。保存导数范数匹配。',
         missing='逐 τ x/v/clean/实际返回 dtype 与 Euler 字节；局部命令梯度未保存。',
         decision='不改符号，不跨状态或局部点复用锚点梯度。'),
    dict(id='H2', hypothesis='大有限步长与局部曲率', status='与已有数据相容，非已证根因',
         evidence='cut5 三局部 J 都下降；step0 前两次也下降。cut5 τ.3/.1 及 step0 τ.3 的正一阶预测超过概率剩余上界。',
         missing='完整有限位移、沿路径曲率与反事实；本任务无 Hessian/有限差分 Q。',
         decision='不扫 α，不回溯，不加 Q 门。'),
    dict(id='H3', hypothesis='clamp 饱和/活跃集变化', status='更新前饱和明确；更新后的因果作用未知',
         evidence='更新前 clip 为 25%–35%，每 τ z 全 10 位超界；command_delta_linf 与 clean 量纲不同。',
         missing='逐 τ before/after 命令向量及更新后边界集合；边界雅可比具体活跃位。',
         decision='不从标量反演向量或补裁剪后 Q。'),
    dict(id='H4', hypothesis='flow 传播/局部梯度点漂移/舍入', status='无法在已有轨迹中定位首次反向 τ',
         evidence='最终 cut5 guided 原生差和 bounded 差均与自身锚点 g 反向；局部 d 不是该锚点 g。',
         missing='x_t、native v、pre/post-cast updated v、实际 Euler x_next；独立最终 guided Q。',
         decision='末 τ local-after 不替代独立 guided 评分。'),
    dict(id='H5', hypothesis='独立半径投影首次造成负方向', status='该 cut5 样本的起因命题不支持；对 Q 的影响仍未知',
         evidence='guided native dot=−0.1186394967、clamped=−0.1158273949、masked=−0.1168174869、actual=−0.06851491684；负号早于该后处理。',
         missing='投影前独立 J 不存在，不能量化投影改善或损伤多少 Q。',
         decision='保持自身半径，不引入共享半径。'),
    dict(id='H6', hypothesis='可从两个状态推出分支排名/完整方法失败率', status='不能推导',
         evidence='两状态不同；cut5 G0=−0.0577081237 未触发，两支固定强制工程干预。五任务历史 Q 仅兼容诊断。',
         missing='受控方法评价及有效统计分母；本任务不补采。',
         decision='风险保留，不选赢家，不宣称 MT50 训练/评测完成。'),
]
missing = [
    dict(field='per_tau_x_t_1x50x32', step0=None, cut5=None, reason='未保存；不得由标量/导数反演'),
    dict(field='per_tau_native_v_1x50x32', step0=None, cut5=None, reason='未保存'),
    dict(field='per_tau_updated_v_precast_1x50x32', step0=None, cut5=None, reason='仅保存差范数，完整向量未知'),
    dict(field='per_tau_returned_v_postcast_1x50x32_and_original_dtype', step0=None, cut5=None, reason='未保存原 dtype/字节'),
    dict(field='per_tau_actual_post_Euler_x', step0=None, cut5=None, reason='逐 τ 未保存；step0 只有最终 x 的 float32 导出'),
    dict(field='per_tau_full_clean_before_and_after', step0=None, cut5=None, reason='未保存；不得模型重算补齐'),
    dict(field='per_tau_command_before_unclipped_before_after_and_active_sets', step0=None, cut5=None, reason='只有更新前 clip 和位移范数标量'),
    dict(field='per_tau_member_probabilities_before_and_after', step0=None, cut5=None, reason='只有 scalar J；不能独立概率复算局部 J'),
    dict(field='independent_final_guided_before_projection_Q', step0=None, cut5=None, reason='无此独立调用；末 τ local-after 不是替代证据'),
    dict(field='exact_quantile_offset_c', step0=None, cut5=None, reason='本次不加载 normalizer；保存 S 足够核差分尺度'),
    dict(field='per_tau_local_command_gradient', step0=None, cut5=None, reason='只保存 dJ/dv，可代数换成 g_y；clamp 零位不可逆，不恢复 g_b'),
]
put('HYPOTHESES_AND_MISSING.json', dict(hypotheses=hypotheses, missing_evidence=missing,
    conclusion_scope='saved-state geometry and frozen formula algebra; no causal root-cause or method ranking claim',
    algorithm_changes=0, new_experiment_required_by_this_task=False))
with (P/'HYPOTHESES.csv').open('x', newline='') as handle:
    writer=csv.DictWriter(handle, fieldnames=list(hypotheses[0]));writer.writeheader();writer.writerows(hypotheses)
with (P/'MISSING_EVIDENCE.csv').open('x', newline='') as handle:
    writer=csv.DictWriter(handle, fieldnames=list(missing[0]));writer.writeheader();writer.writerows(missing)

logging_quote = dict(
    status='OPTIONAL_NOT_AUTHORIZED_NOT_IMPLEMENTED',
    purpose='If analysis later needs to localize the already observed risk, add snapshots to an independently authorized guided call; no new run is requested here.',
    stages=3, shapes_scope='same C10×4 objective / 1×50×32 native tensors; no new source, seed, sweep or sampling',
    per_stage_reuse=[
        dict(fields=['x_t','native_v','updated_v_precast','returned_v_postcast','actual_x_next_after_Euler'], shape=[1,50,32], arrays=5, bytes_if_f32=32000),
        dict(fields=['clean_before_active','clean_after_active'], shape=[1,10,4], arrays=2, bytes_if_f32=320),
        dict(fields=['command_before_unclipped','command_before_clamped','command_after_clamped'], shape=[1,10,4], arrays=3, bytes_if_f32=480),
        dict(fields=['member_probabilities_before','member_probabilities_after'], shape=[4,2], arrays=2, bytes_if_f32=64,
             note='copy the existing CPU last_member_probabilities immediately before it is overwritten; no new objective call')],
    once_fields=['q01[4]','q99[4]','source/context/anchor/S/seed/noise identity refs'],
    metadata=['tau scalar and original time tensor dtype/bit representation','dt scalar representation','all tensor original dtype/shape and stage IDs',
              'coordinate system and objective point','GPU-to-CPU copy timing if later authorized','unchanged parameter/count/acceptance semantics'],
    derivative_arrays='reuse existing saved dJ/dv; no extra gradients or duplicate payload required',
    finite_storage_estimate=dict(
        interpretation='uncompressed payload estimate if all numerical tensor items use at most 4 bytes/element; retain original dtypes, bind a larger quote before any future run if this assumption fails',
        minimum_active_clean_payload_bytes=3*(32000+320+480+64)+32,
        minimum_payload_plus_headers_metadata_estimate_bytes=131072,
        optional_full_clean_extra_payload_bytes=3*2*(1600-40)*4,
        optional_full_clean_total_payload_bytes=3*(32000+320+480+64)+32+3*2*(1600-40)*4,
        optional_full_clean_plus_headers_metadata_estimate_bytes=196608,
        compression_credit=0,
        peak_runtime_staging_memory='unknown; estimates above are saved payload, not peak CPU/GPU allocator memory or timing'),
    new_operations_if_logging_reuse_is_later_authorized=dict(
        model_forwards=0, model_backwards=0, action_gradients=0, objective_ensemble_forwards=0,
        VLA_samples=0, flow_steps=0, projection_calls=0, encoders=0, DG0=0,
        environment_resets=0, environment_steps=0, render=0,
        added_tensor_exports_to_CPU_upper_bound=32,
        added_tensor_exports_basis='10 tensor snapshots per injection ×3 plus 2 quantile buffers; preserve raw dtype; already-CPU member probabilities require six small CPU copies',
        dtype_or_byte_formatting='metadata and serialization only; reuse expressions already evaluated, do not recompute clean/flow/model',
        GPU_sync_latency='unknown, not treated as zero; account under a separate future release if exports synchronize'),
    separate_optional_final_guided_score=dict(
        authorized=False, compute_now=0,
        object='clamp(actual saved/native final guided raw50, -1,1)[:10] using the same context and frozen a0',
        ensemble_objective_two_slot_forwards=1, member_two_slot_forwards=4, action_gradient_calls=0,
        additional_VLA_sampling=0, additional_flow=0, additional_environment_or_render=0,
        saved_member_probability_payload_bytes_if_f32=32,
        note='this is an additional Q evaluation; cannot claim it is already provided by last-tau local-after'),
    decision='No new release, launcher, GPU proposal or algorithm patch is created. Analysis decides whether these fields are necessary in an already-planned future diagnostic.',
)
assert logging_quote['finite_storage_estimate']['minimum_active_clean_payload_bytes']==98624
assert logging_quote['finite_storage_estimate']['optional_full_clean_total_payload_bytes']==136064
put('OPTIONAL_FUTURE_LOGGING_QUOTE.json', logging_quote)

def stage(state, branch, name):
    return next(x for x in directions['rows'] if (x['state'],x['branch'],x['stage'])==(state,branch,name))

direction_rows=[]
for state in ['step0','cut5']:
    for branch in ['Post','Velocity']:
        row=stage(state,branch,'actual_delta')
        score=next(x for x in objectives if x['state']==state and x['branch']==branch and x['evaluation_object'].startswith('clamp('))
        direction_rows.append(f"| {state} | {branch} | {row['dot_g']:+.9f} | {row['cosine_g']:+.6f} | {score['J_recomputed_f64']:+.9f} | {score['positive_members']}/{score['negative_members']} |")
tau_rows=[f"| {x['state']} | {x['tau']:.1f} | {x['first_order_local_J_change']:+.6f} | {x['local_J_change']:+.6f} | {x['logged_clipping_fraction']:.1%} |" for x in taus]
put('REPORT.md', '''A10_PV_DIRECTION_CPU_ANALYSIS_V1 revision1 — CPU_READY，待分析验收。

cut5 的 Velocity 负方向已存在于保存的最终 guided 原生命令差：与该状态锚点 g 点积 −0.118639497；clamp 后 −0.115827395，mask 后 −0.116817487，独立半径和 float32 写回后 −0.068514917。该样本的负号不是在上述后处理中首次产生。step0 对应各阶段均为正。完整逐 τ 向量缺失，不能定位首次反向的 τ 或确认根因。

已先证明每个状态内部 P/V 的 context、raw/bounded anchor 和 Q 身份一致；cut5 为两个独立回放进程，依赖已验收的同资产冻结证据，不宣称隐藏环境状态等价。每个状态仅使用自身保存的 Post 命令梯度；两状态不构成受控消融。

| 状态 | 分支 | g·实际 delta | cosine | 最终 J=ΔQ | 成员升/降 |
|---|---|---:|---:|---:|---:|
'''+'\n'.join(direction_rows)+'''

J 由保存的四成员概率重算；逐阶段 32 行含 raw/clamp/mask/unit/半径后的 delta/最终 proposal、XYZ/gripper 范数及裁剪统计。四分支 mask 后 gripper 均为零；XYZ 实际 RMS 分别为 step0 P≈0.039216、V≈0.050000，cut5 P≈0.050000、V≈0.044475；没有共享半径。详细身份、关系、坐标及源行/SHA 见随附 JSON/CSV。

窄公式核对：Post 为 S²g；Velocity 为 d=dJ/dv=−τg_clean，v′=v+10d，Euler dt=−0.1。同一局部点的一阶预测为 10||d||²；保存局部 J 的实际变化如下（clip 为更新前局部命令）：

| 状态 | τ | 一阶预测 | 保存局部 ΔJ | clip |
|---|---:|---:|---:|---:|
'''+'\n'.join(tau_rows)+'''

step0 τ.3、cut5 τ.3/.1 的预测超过剩余概率上界。这说明线性预测不能保证有限步收益，尚不能区分大有限步/曲率、clamp、flow 传播或舍入的作用；不据此改 α/符号或加 Q 门。accepted=true 只表示固定更新执行。每 τ 缺完整 x/v/updated_v/clean、命令向量和成员概率；局部 J 只可对已存标量作差。末 τ local-after 不冒充独立最终 guided Q，该值明确为 null。

cut5 G0=−0.0577081237 未触发，两支是固定强制工程干预。风险继续保留；这不是完整方法失败率/任务成功率或分支排名，历史五任务 Q 不代表 MT50 完成。

标准库小数组核对 78 项通过，未调用投影实现或重建候选；本次模型/梯度/环境/硬件/holder/launcher/claim/训练/删除/大权重 hash 全 0，旧证据未改。INPUT_MANIFEST 及 FORMULA_SOURCE_MAP 固定来源；analyze_saved.py 和原始 CPU 执行回执可复核。最终证据清单见 EVIDENCE_MANIFEST.json。

建议先按上述范围归档，无需强行新实验。若分析后续确需定位，OPTIONAL_FUTURE_LOGGING_QUOTE.json 报价复用已有中间量：三 τ 约 98,624 B 数组（含完整 clean 则 136,064 B），至多 32 次额外张量导出，模型计算增量 0，但同步延迟未知；独立最终 guided 评分需另增 1 ensemble/4 member forward，均未授权、未实现、未执行。
''')
put('ASSEMBLY_RESULT.json', dict(status='PASS', source_files=12, source_files_imported=0,
    new_model_or_projection_calls=0, new_derived_array_generation=0,
    new_files=['FORMULA_SOURCE_MAP.json','FORMULAS_AND_UNITS.md','HYPOTHESES_AND_MISSING.json',
               'HYPOTHESES.csv','MISSING_EVIDENCE.csv','OPTIONAL_FUTURE_LOGGING_QUOTE.json','REPORT.md'],
    publication_scope='private task evidence only; no shared code or CONTROL/BOARD edits'))
print(json.dumps(dict(status='PASS',source_files=len(source_rows),hypotheses=len(hypotheses),missing_fields=len(missing)),ensure_ascii=False))
