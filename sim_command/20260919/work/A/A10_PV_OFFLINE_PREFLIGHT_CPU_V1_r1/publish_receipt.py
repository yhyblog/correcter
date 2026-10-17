"""Seal the current CPU preparation only; no runtime or release invocation."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');BASE=ROOT/'Corrector/sim_command/20260919'
TASK='A10_PV_OFFLINE_PREFLIGHT_CPU_V1';PKG=BASE/'results/A'/TASK;WORK=Path(__file__).parent
RECEIPTS=BASE/'receipts/A'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p),size_bytes=p.stat().st_size)
def read(p):return json.loads(p.read_text())
def write(p,x):
    with p.open('x') as f:f.write(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

def main():
    ack=read(RECEIPTS/(TASK+'_ACK.json'));control=read(BASE/'CONTROL.json');board=read(BASE/'TASK_BOARD.json')
    assert control['revision']==21 and board['revision']==28
    assert control['formal_gpu_runs_enabled'] is False and not any(control['current_compute_limits'].values())
    assert control['active_compute_release_id'] is None
    assert not (BASE/'releases/P10_A_PV_OFFLINE_PREFLIGHT_V1.json').exists()
    assert not (BASE/'results/A/P10_PV_release_claims/P10_A_PV_OFFLINE_PREFLIGHT_V1.json').exists()
    for r in ack['inputs_checked']:assert sha(Path(r['path']))==r['sha256']
    code=read(PKG/'code/CODE_MANIFEST.json')
    for row in code['files']:assert sha(PKG/'code'/row['path'])==row['sha256']
    proposal=read(PKG/'proposal/PROPOSAL.json')
    for key in ['config','code_manifest','input_manifest','external_sources','command']:
        assert sha(Path(proposal[key]['path']))==proposal[key]['sha256']
    template=read(PKG/'proposal/RELEASE_TEMPLATE.json')
    assert template['status']=='UNAUTHORIZED_TEMPLATE' and template['proposal_sha256']==sha(PKG/'proposal/PROPOSAL.json')
    tests=sorted(WORK.glob('targeted_tests_*/TEST_RESULT.json'))
    test=tests[-1];testdata=read(test);assert testdata['status']=='passed' and len(testdata['tests'])==28 and not testdata['blocked_scope_events']
    cfg=read(PKG/'config/CONFIG.json');small=read(WORK/'SMALL_ARTIFACT_METADATA.json')
    assert all(m['tensors'][k]['min']>0 for m in small['Q'].values() for k in ['norm_std','visual_scale','language_scale'])
    selected=read(Path(cfg['Q_assets'])/'config.json')['provenance']['selection']
    assert selected['path']=='A' and selected['step']==4000
    shutil.copyfile(WORK/'SMALL_ARTIFACT_METADATA.json',PKG/'MODEL_AND_SNAPSHOT_METADATA.json')
    review=dict(schema='PV_offline_causal_contract_review_v1',status='CPU_prepared_runtime_unexecuted',
        step0=dict(observation=cfg['source']['observation_path'],pixels=[480,480,3],proprioception=[4],history_mask=[0,0,0,0,1],proprio_mask=[0,0,0,0,1],history_padding=0,past_actions_shape=[4,4],past_actions_values=0,remaining=1.,
            existing_contract='ACT-RECAP ac_tmil.ogg.common.cpu_batch n=1; latest frame occupies last slot; fake-tested exact extracted body',future_step1_used=False,legal_alarm_cut=False),
        feature_chain=dict(policy_checkpoint=cfg['checkpoint'],policy_loads=1,
            vision='saved step0 uint8 -> exact LeRobot preprocess -> PI05 real camera resize224/[-1,1] -> embed_image [1,1,256,2048] -> canonical quantize/decode -> 16 fixed cells -> frozen projection2048x256 ->4096 ->half then float32',
            language='same saved instruction -> pinned tokenizer revision35e4f46485b4d07967e7e9935bc3786aad50687c, max200/right padding -> same PI05 token embedding times sqrt2048 -> masked mean2048',
            D_G0_or_legacy_pooled_models_required=False,reason='Historical standalone ResearchEngine.spatial reads only the fixed projection; Q uses observed_features, not D futures or pooled gates',
            projection=small['projection']['identity']),
        Q=dict(assets=cfg['Q_assets'],selection={k:v for k,v in selected.items() if not isinstance(v,(list,dict))},members=4,
            per_member_dimensions=dict(norm_mean=[4096],norm_std=[4096],visual_center=[8192],visual_basis=[8192,16],visual_scale=[16],language_center=[2048],language_basis=[2048,8],language_scale=[8],features=61,action=[10,4]),
            per_member_preprocessing='Each checkpoint carries its own bound buffers; no external-state/training-feature substitution. Checkpoint metadata includes storage SHA per buffer; equality between members is permitted and does not mean a new shared-radius algorithm.',
            historical_scope='five-task A4000 compatibility diagnostic; MT50 adaptation not complete'),
        raw_anchor=dict(source=cfg['source']['raw_plans_path'],slice=0,shape=[50,4],dtype='float32',all_five_bit_equal=small['raw']['all_five_bit_equal'],
            required_anchor='b=clip(raw[:10],-1,1)',internal_inverse_needed=False,
            missing='Unbounded internal50x32 was not saved and cannot be inferred uniquely from clipped commands; not required by these kernels. Post starts at bounded b with saved normalizer S². Velocity rebuilds the original initial noise.',
            final_tail='Each final candidate copies cached raw50, replacing only nonzero feasible C10 coordinates; tail40/mask-out/zero-delta retain raw bits'),
        noise=dict(saved_tensor_present=False,saved_sha256=cfg['source']['noise_sha256'],reconstruction=cfg['source']['noise_generator'],
            shape=[1,50,32],dtype='float32',seed=2026091901,cpu_static_route_verified=True,runtime_SHA_equality_verified=False,
            failure_rule='save actual SHA and stop before guided sampling if mismatch; no second draw, alternate seed, or baseline sample'),
        numerical_semantics=dict(ensemble='mean of each member sigmoid(candidate)-sigmoid(fixed anchor); J(b;b)=0',
            Post='one command gradient at b; S² scaling; own projection',Velocity='one sample, ten negative Euler steps; only tau .3/.2/.1 use v-10*tau*g_u, detached x/v and no VLA Jacobian',
            matching='Each branch uses only own direction/capacity/radius. XYZ30/grip10, independent zero groups, expansion allowed, C10 only. Original project_solo/audit_solo AST unchanged.',
            diagnostic_after_scores='Finite diagnostics only. Existing flow row accepted=True means injection completed, never Q improvement acceptance.',Q_acceptance_gate=False,shared_radius=False),
        loader=dict(risk_found='Inherited PI05.from_pretrained catches errors and can return uninitialized model',
            guard='Observe the existing one safetensors load and one strict state-dict load; require successful returns, same returned model object, no missing/unexpected keys/errors before any forward',
            extra_weight_loads=0,extra_model_forward_calls=0,fake_success_and_three_silent_failure_modes_passed=True),
        accounting=dict(explicit_entered_first=True,units_incremental=True,terminal_return_counts_separate=True,missing_terminal_charged=True,
            torn_record='known lower bound retained; exact total unknown; release still consumed',
            four_Q_backward_paths_per_gradient='derived 16 successful member paths, distinct from four actual torch.autograd.grad calls'),
        source_functions=ref(PKG/'DERIVATION.json'),model_metadata=ref(PKG/'MODEL_AND_SNAPSHOT_METADATA.json'),tests=ref(test))
    write(PKG/'CONTRACT_REVIEW.json',review)
    now=datetime.now(timezone.utc).isoformat()
    audit=dict(status='passed',task_id=TASK,checked_at_utc=now,code_files_verified=len(code['files']),external_source_identities_declared=len(read(PKG/'EXTERNAL_SOURCE_MANIFEST.json')['files']),
        new_reference_hashes_verified=True,protocol_unchanged_from_ACK=True,current_CONTROL=21,current_TASK_BOARD=28,current_compute_limits_zero=True,
        actual_new_compute_release_present=False,actual_new_compute_claim_present=False,
        large_weight_sha='inherited accepted V3 identity; no bytes hashed in this CPU task',
        model_initializations=0,model_forward=0,model_backward=0,Torch_imports=0,driver_dlopen=0,GPU_calls=0,
        environment_instances=0,reset=0,render=0,physics=0,holder_queries=0,holder_stops=0,deletions=0,old_artifacts_modified=False,
        metadata_checkpoint_reads=4,test_result=ref(test),tests_passed=28,
        scope_limit='CPU syntax/fake/source/metadata only, no real tensor numeric or hardware validation')
    write(WORK/'FINAL_CPU_AUDIT.json',audit)
    ready=dict(status='CPU_READY',task_id=TASK,actual_execution_authorized=False,publication_is_authorization=False,prepared_at_utc=now,
        next_task_id='A10_PV_OFFLINE_PREFLIGHT_V1',known_blockers=[],required_next_action='Analysis review and independent compute release; do not execute template',
        runtime_fail_closed_gates=['full SHA/source/host/device identity','strict PI05 loader proof','reconstructed noise SHA before guided call','single-frame causal context and dimensions','finite gradients and bounded own projections','exact explicit call counts'],
        proposal=ref(PKG/'proposal/PROPOSAL.json'),release_template=ref(PKG/'proposal/RELEASE_TEMPLATE.json'),control_required=ref(PKG/'proposal/CONTROL_REQUIRED.json'),
        code=ref(PKG/'code/CODE_MANIFEST.json'),config=ref(PKG/'config/CONFIG.json'),inputs=ref(PKG/'INPUT_MANIFEST.json'),
        contract_review=ref(PKG/'CONTRACT_REVIEW.json'),tests=ref(test),audit=ref(WORK/'FINAL_CPU_AUDIT.json'),
        actual_counts=dict(Torch_imports=0,model_calls=0,CUDA_EGL_NVML_dlopen=0,environment_reset_render_physics=0,holder_queries_stops=0,large_weight_hashes=0,deletions=0))
    write(PKG/'CPU_READY.json',ready)
    report=RECEIPTS/(TASK+'_REPORT.md')
    text=f'''# {TASK} — CPU_READY，真实计算未执行

| 项目 | 可用 / 缺口 |
|---|---|
| 因果输入 | V3 step0 RGB/proprio + raw_plans[0]；既有 n=1 合同采用 00001 mask、前四帧/历史动作零填充、remaining=1。step1 不参与。t0 不是报警 cut。 |
| 特征 / Q | 同 SFT030000 编码器；视觉 4096、语言 2048；固定空间投影及四成员各自 checkpoint 内 norm/PCA 已绑定 SHA/维度。Q 条件不需要 D/G0。A4000 为五任务兼容诊断，不代表 MT50 适配。 |
| 锚点 / 噪声 | raw50 足以提供 bounded b 和原始位模式；不需要逆推出缺失的内部 50×32。噪声只存 SHA，按冻结 seed2026091901、原 torch.normal、float32[1,50,32] 重建；真实 SHA 尚待验证，不符立即停止。 |
| CPU 检查 | 28 项通过；380 代码文件、33 外部源身份。未 import Torch/NumPy、未 dlopen/查询 CUDA/EGL/NVML、未跑模型/环境、未查停 holder、未 hash 大权重、未删除。 |

未来单次报价：加载 **1 个 PI0.5 + 4 个 CPU Q**；缓存锚点 Post **1 次动作梯度**；Velocity **1 次 guided sampling / 10 flow / 末三步 3 次动作梯度**。Q 共 **10 次 ensemble objective = 40 次成员前向**，每次成员前向包含锚点和候选两个 slot；4 次动作 autograd，16 个成员反向路径为派生计数。10 次 objective 已包含 1 锚点评分、Post 梯度/最终评分各1、Velocity 梯度/局部后评分各3、最终评分1。

编码调用另计：视觉 **4**（Q真实帧1 + guided真实/两填充相机3），语言 embedding **2**，prefix transformer **1**，action expert **10**；成员特征变换4、空间投影1。各分支投影一次，最终约束审计各重放一次，共4次自身投影/2次审计，不增加模型调用。无 Q 接受门、无共享半径；C10/尾40/零扰动 raw 位模式按原函数保留。部署口径仍 Post=1完整采样、Velocity=2；本报价仅缓存数值诊断。

加载器会吞加载异常；本入口记录原有一次权重读取和一次 strict state-dict 载入，缺失/异常即拒绝，不额外载入或推理。未来固定 A GPU UUID {cfg['device']['gpu_uuid']} / PCI {cfg['device']['pci_bus_id']}，NVML身份查询2、Torch properties1；全部环境/reset/graphics/物理/rollout/D/G0/训练/重试/删除0。

估算显存40 GiB、RAM64 GiB、新增盘2 GiB，非实测。子进程 timeout1800s、TERM后30s KILL；父层完整SHA、reservation、进程组清理和最多120s恢复观察另计，端到端无严格有限上界。真实入口完整大权重SHA共2遍；本轮0遍。全A8 holder 保持停算至整个进程组退出，失败亦清理后恢复；B不参与。

唯一拟运行命令（未执行；必须新 release）：

```sh
{proposal['command']['path']} NEW_RELEASE_JSON
```

交付目录：`results/A/{TASK}/`；入口 `CPU_READY.json`、`proposal/PROPOSAL.json`、`RELEASE_TEMPLATE.json`、`CONTROL_REQUIRED.json`，详细维度/沿革/调用合同见 `CONTRACT_REVIEW.json`、`MODEL_AND_SNAPSHOT_METADATA.json`、`INPUT_MANIFEST.json`。新 release 固定路径为 `releases/P10_A_PV_OFFLINE_PREFLIGHT_V1.json`，当前不存在且未 claim。CONTROL21/TASK_BOARD28及旧封存未改；全部本轮产物保留。等待分析验收与另行放行。
'''
    with report.open('x') as f:f.write(text)
    write(WORK/'PREPARATION_NOTES.json',dict(non_compute_issues=[
        dict(issue='initial snapshot builder looked for normalize_pci in release.py; function is imported from cuda_mapping.py',resolved='corrected extraction source; initial builder retained as prepare_snapshot_attempt01.py',real_compute_attempts=0),
        dict(issue='system Python3.11 AST cannot parse upstream Python3.12 generic class syntax in existing pipeline.py',resolved='read relevant source text directly; executable runtime remains frozen Python3.12; no runtime package imported or changed',real_compute_attempts=0)],
        tests_runs_retained=len(tests),last_tests=ref(test),all_outputs_retained=True,old_task_resubmitted=False))
    retention=dict(decision='retain_all_current_task_outputs_pending_analysis_decision',delete_authorization=False,deletions=0,
        retained_roots=[str(PKG),str(WORK)],retained_receipts=[str(RECEIPTS/(TASK+'_ACK.json')),str(report),str(RECEIPTS/(TASK+'_RESULT.json'))],
        note='Includes failed construction source, all synthetic tests/claims, metadata, snapshots, logs and future queue delivery. No cleanup was performed.')
    write(WORK/'RETENTION.json',retention)
    files=[p for root in [PKG,WORK] for p in root.rglob('*') if p.is_file()]
    files += [RECEIPTS/(TASK+'_ACK.json'),report]
    evidence=WORK/'EVIDENCE_MANIFEST.json'
    write(evidence,dict(task_id=TASK,status='sealed_CPU_preparation',files=[ref(p) for p in sorted(files)],
        excluded=['self','RESULT (references this manifest)','mutable heartbeat','later queue transport evidence'],all_retained=True))
    artifacts=[report,PKG/'CPU_READY.json',PKG/'proposal/PROPOSAL.json',PKG/'proposal/RELEASE_TEMPLATE.json',PKG/'proposal/CONTROL_REQUIRED.json',
        PKG/'code/CODE_MANIFEST.json',PKG/'config/CONFIG.json',PKG/'INPUT_MANIFEST.json',PKG/'EXTERNAL_SOURCE_MANIFEST.json',PKG/'DERIVATION.json',
        PKG/'CONTRACT_REVIEW.json',PKG/'MODEL_AND_SNAPSHOT_METADATA.json',PKG/'commands/run_proposed_pv_offline.sh',PKG/'tests/test_cpu.py',
        test,WORK/'FINAL_CPU_AUDIT.json',WORK/'PREPARATION_NOTES.json',WORK/'RETENTION.json',evidence]
    result=dict(campaign_id=ack['campaign_id'],task_id=TASK,revision=1,role='A',hostname=ack['hostname'],session_id=ack['executor_session_id'],
        status='complete',outcome='CPU_READY_unexecuted_offline_PV_proposal',started_at_utc=ack['started_at_utc'],finished_at_utc=now,
        input_identity=dict(protocol=ack['inputs_checked'],code=ref(PKG/'code/CODE_MANIFEST.json'),config=ref(PKG/'config/CONFIG.json'),data=ref(PKG/'INPUT_MANIFEST.json'),model=next(x for x in read(PKG/'INPUT_MANIFEST.json')['files'] if Path(x['path']).name=='model.safetensors')),
        artifacts=[ref(p) for p in artifacts],resource_counts=dict(ack['limits']),
        holder_queried=False,holder_stopped=False,large_model_hash_passes=0,actual_compute_release_claims=0,old_receipts_modified=False,
        failures_and_retries=dict(real_compute_attempts=0,real_compute_failures=0,real_compute_retries=0,CPU_preparation_notes=ref(WORK/'PREPARATION_NOTES.json')),
        findings=[
            'Existing one-valid-frame masked context supports step0; future step1 excluded, no fabricated history or cut collection.',
            'Same-source PI05 vision/language and frozen spatial projection required; D/G0/legacy pooled models not needed.',
            'Four selected A4000 small checkpoint identities/buffer shapes bound; five-task compatibility only.',
            'Cached unbounded raw50 supplies bounded anchor and raw bit preservation; internal latent inverse not required.',
            'Noise has a static frozen reconstruction path; actual hash equality is pending and must fail closed on mismatch.',
            'Future proposal: one guided sample/ten flow, four action gradients, ten ensemble objectives/forty Q member forwards; no VLA parameter backward.',
            'Own-radius numerical bodies retained unchanged; no Q acceptance gate/shared radius, C10/raw-tail invariants preserved.',
            'Loader proof observes the existing strict load to reject silent random-model fallback without extra weight loading.',
            '28 targeted CPU/fake checks passed; actual tensors, devices, environments and holders untouched.',
            'Unique unissued release/claim, whole-A lifecycle and partial/failure accounting prepared; deployment Post1/Velocity2 cost semantics preserved.'],
        blockers=[],runtime_validation_pending=proposal['unvalidated'],
        next_task_proposal=dict(task_id='A10_PV_OFFLINE_PREFLIGHT_V1',proposal=ref(PKG/'proposal/PROPOSAL.json'),real_command=proposal['real_command'],requires_new_analysis_release=True,authorized=False),
        publication_is_authorization=False,retained_evidence_files=len(files))
    write(RECEIPTS/(TASK+'_RESULT.json'),result)
    hb=BASE/'nodes/A'/ (TASK+'_HEARTBEAT.json');x=read(hb);x.update(status='complete',updated_at_utc=now,progress='CPU_READY sealed; awaiting analysis review and independent compute release',result=ref(RECEIPTS/(TASK+'_RESULT.json')));hb.write_text(json.dumps(x,indent=2)+'\n')
    for p in PKG.rglob('*'):
        if p.is_file():p.chmod(0o555 if p.suffix=='.sh' else 0o444)
    print(json.dumps(dict(result=ref(RECEIPTS/(TASK+'_RESULT.json')),report=ref(report),proposal=ref(PKG/'proposal/PROPOSAL.json'),evidence_files=len(files),tests=28),indent=2))

if __name__=='__main__':main()
