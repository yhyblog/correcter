"""CPU-only proposal assembly; does not release or invoke the actual command."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');BASE=ROOT/'Corrector/sim_command/20260919'
WORK=Path(__file__).parent;PKG=BASE/'results/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1';CODE=PKG/'code'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p),size_bytes=p.stat().st_size)
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')

def main():
    cfg=json.loads((PKG/'config/CONFIG.json').read_text())
    original=BASE/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1/EXTERNAL_SOURCE_MANIFEST.json'
    archive=WORK/'INHERITED_EXTERNAL_SOURCE_MANIFEST.json'
    if not archive.exists():shutil.copyfile(original,archive)
    old=json.loads(archive.read_text());rows=[]
    for row in old['files']:
        s=row['path']
        if '/site-packages/torch/' in s or '/site-packages/numpy/' in s or '/numpy-2.2.6.dist-info/' in s or Path(s).name in ['python','gpu_occupancy_guard.py','gpu_occupancy_lifecycle.sh','nvidia-smi','timeout','libcuda.so.535.161.08','libc.so.6','libm.so.6','libdl.so.2','libpthread.so.0','librt.so.1','ld-linux-x86-64.so.2']:
            rows.append(dict(row,verification_now='inherited accepted V3 SHA; no fresh driver/library read or scan'))
    site=ROOT/'.miniforge3/envs/lerobot/lib/python3.12/site-packages'
    for name in ['transformers/modeling_utils.py','transformers/tokenization_utils_base.py','transformers/tokenization_utils_tokenizers.py',
        'transformers/models/gemma/modeling_gemma.py','transformers/models/paligemma/modeling_paligemma.py',
        'transformers/models/siglip/modeling_siglip.py','transformers/models/auto/tokenization_auto.py','safetensors/torch.py']:
        p=site/name
        if not p.is_file():raise ValueError('Expected targeted dependency source absent: '+str(p))
        rows.append(dict(ref(p),realpath=str(p.resolve()),verification_now='targeted source text SHA; no import'))
    dump(PKG/'EXTERNAL_SOURCE_MANIFEST.json',dict(schema='PV_targeted_external_sources_v1',files=rows,
        inherited_basis=ref(original),scope='Needed accepted runtime identities plus targeted feature/model sources; no EGL/MetaWorld source chain or fresh package inventory',
        full_environment_binary_fingerprint=False))
    command=PKG/'commands/run_proposed_pv_offline.sh'
    command.write_text('#!/bin/sh\nset -eu\n[ "$#" -eq 1 ] || { echo "usage: run_proposed_pv_offline.sh NEW_RELEASE_JSON" >&2; exit 2; }\nexec '+cfg['python']+' -B '+str(CODE/'launch.py')+' --release "$1"\n')
    command.chmod(0o755)
    files=[dict(path=str(p.relative_to(CODE)),sha256=sha(p),size_bytes=p.stat().st_size) for p in sorted(CODE.rglob('*')) if p.is_file() and p.name!='CODE_MANIFEST.json']
    dump(CODE/'CODE_MANIFEST.json',dict(schema='PV_private_code_v1',root=str(CODE),files=files))
    zero=['simulator_attempts','environment_instances','wrapper_instances','taskset_constructions','environment_reset_calls','reset_model_calls',
        'initialization_physics_substeps','policy_physics_substeps','physics_steps','env_steps','graphics_context_creations','render_calls','rgb_readback_calls',
        'explicit_EGL_calls','explicit_CUDA_driver_calls','explicit_driver_dlopen_calls','completed_rollouts','monitor_calls','D_forward_calls','G0_forward_calls',
        'vla_backward_calls','vla_parameter_backward_calls','critic_parameter_updates','optimizer_updates','training_updates','retries','deletions','baseline_sampling_calls']
    diag=dict.fromkeys(zero,0)
    diag.update(offline_attempts=1,native_nvml_identity_queries=1,policy_device_selections=1,policy_device_property_queries=1,
        model_initializations=5,policy_model_loads=1,policy_state_file_loads=1,policy_state_dict_loads=1,critic_model_loads=4,tokenizer_loads=1,preprocessor_loads=1,postprocessor_loads=1,
        normalizer_transform_loads=1,projection_loads=1,context_builds=1,preprocessor_calls=2,tokenizer_calls=3,image_preprocessing_calls=2,
        visual_encoder_forwards=4,language_embedding_forwards=2,encoder_forward_calls=6,spatial_projection_calls=1,
        prefix_transformer_forwards=1,action_expert_forwards=10,flow_forward_calls=10,noise_draws=1,vla_sampling_calls=1,model_gpu_inference_calls=1,
        critic_feature_transforms=4,critic_forward_calls=40,objective_forward_calls=10,action_gradient_calls=4,critic_backward_calls=4,
        post_action_gradient_calls=1,velocity_action_gradient_calls=3,own_projection_calls=4,raw_constraint_audits=2,postprocessor_calls=1)
    launch={'native_nvml_identity_queries':1};total=dict(diag);total['native_nvml_identity_queries']=2
    proposal=dict(proposal_id='A10_PV_OFFLINE_PREFLIGHT_V1_proposal_r1',status='proposed_not_released',publication_is_authorization=False,
        campaign_id='corrector-sim-20260919',task_id='A10_PV_OFFLINE_PREFLIGHT_V1',task_revision=1,node_role='A',owner_host='trial-303224955-trialrun-303224955-worker-0',wave_participants=['A'],
        config=ref(PKG/'config/CONFIG.json'),input_manifest=ref(PKG/'INPUT_MANIFEST.json'),code_manifest=ref(CODE/'CODE_MANIFEST.json'),
        external_sources=ref(PKG/'EXTERNAL_SOURCE_MANIFEST.json'),command=ref(command),
        real_command=[str(command),'NEW_RELEASE_JSON'],required_release_path=str(BASE/'releases/P10_A_PV_OFFLINE_PREFLIGHT_V1.json'),
        device=cfg['device'],cuda_environment=cfg['cuda_environment'],source=cfg['source'],resource_caps=total,diagnostic_caps=diag,launcher_caps=launch,
        max_retries=0,timeout_seconds=1800,kill_grace_seconds=30,restoration_observation_timeout_seconds=120,
        timeout_scope='timed diagnostic child only: second full input SHA pass, imports, model loads, encoders, Post and Velocity, in-process finalization',
        timeout_outside=['first full input SHA/device check','guard active check/reservation/holder release','entire process-group drain after child exits','reservation release','occupancy restoration observation up to120s'],
        timed_child_TERM_deadline_seconds=1800,timed_child_KILL_nominal_deadline_seconds=1830,end_to_end_strict_upper_bound_seconds=None,
        process_family_scope='existing isolated lifecycle session, inherited formal.lock through timeout/child; no detached descendants; TERM then KILL, retain reservation until no live members; post-KILL drain has no finite hard bound',
        occupancy='All eight A holders stopped through entire formal process group, including failures; restore only after group exit. B is absent.',
        cost_semantics=dict(kind='cached single-snapshot numerical diagnostic',deployment_samples=dict(Post=1,Velocity=2),diagnostic_samples=dict(Post=0,Velocity=1),deployment_cost_comparison=False),
        call_quote=dict(Q=dict(member_loads=4,feature_transforms=4,objective_calls=10,member_forward_calls=40,
            slots_per_member_forward=2,anchor_slot_evaluations=40,candidate_slot_evaluations=40,action_gradients=4,
            successful_member_backward_paths_derived=16,parameter_updates=0,
            objective_breakdown={'shared_anchor_score':1,'Post_gradient':1,'Post_final_score':1,'Velocity_three_gradient_points':3,'Velocity_three_local_after_scores':3,'Velocity_final_score':1},
            note='local after/final scores are finite diagnostics only; no improvement acceptance gate or retry'),
            encoder=dict(SFT_model_loads=1,Q_visual=1,guided_visual_including_two_padded_cameras=3,Q_language_embedding=1,guided_language_embedding=1,
                prefix_transformer=1,flow_action_expert=10,D=0,G0=0,legacy_pooling_models=0,spatial_projection=1),
            matching=dict(own_projection=2,independent_replay_in_constraint_audit=2,raw_constraint_audits=2,model_calls_in_matching=0)),
        counter_scope='Incremental entered-first explicit operations; returned separately. Nested aliases (encoder6=vision4+language2; model_initializations5=policy1+Q4; critic_backward4=action_gradient4=Post1+Velocity3; GPU model inference1=sampling1) must not be summed. Torch/CUDA/cuBLAS internal calls and kernel counts are unmeasured, not asserted zero. NVML identity2 excludes persistent guard polling.',
        noise_rule='Exactly one original model.sample_noise torch.normal after default CPU/current-CUDA seed2026091901; [1,50,32]float32. Require saved V3 SHA before guided sampling; pass tensor explicitly. No mismatch repair, extra draw or baseline.',
        input_gaps=dict(missing_saved_noise_tensor='rebuildable by frozen RNG, runtime SHA validation still pending',missing_internal_raw50x32='not needed: Post uses bounded command anchor; Velocity uses rebuilt initial noise and saved bounded anchor',future_features='must compute same-source step0 vision/language after release',known_blockers=[]),
        resource_estimates=dict(gpu_count=1,reserved_holder_GPU_count=8,vram_peak_GiB=40,host_RAM_peak_GiB=64,additional_disk_GiB=2,estimates_measured=False,
            model_weight_bytes=9354050752,large_weight_hash_passes=2,large_weight_hash_bytes=18708101504,CPU_preparation_large_weight_hash_passes=0,
            D_G0_models_loaded=0,Q_models_placement='CPU, frozen eval; two threads during Q arithmetic',policy_encoder_placement='fixed cuda:0 H100, original checkpoint precision; no AMP override',
            extra_notes='Q gradients traverse detached candidate actions and CPU/GPU copies, never VLA parameters. All outputs/cache/logs retained; no delete operation.'),
        unvalidated=['real encoder outputs at step0','runtime noise hash equality','Q/P/V finite numerical behavior on this snapshot','MT50 Q adaptation','D/G0 triggers','C10 execution and complete task outcomes'],
        successful_output_is_task_success_sample=False)
    dump(PKG/'proposal/PROPOSAL.json',proposal)
    release=dict(status='UNAUTHORIZED_TEMPLATE',issuer='analysis',campaign_id=proposal['campaign_id'],task_id=proposal['task_id'],task_revision=1,node_role='A',owner_host=proposal['owner_host'],
        release_id='P10_A_PV_OFFLINE_PREFLIGHT_V1',wave_id='ANALYSIS_ASSIGN_UNIQUE',run_id='ANALYSIS_ASSIGN_UNIQUE',shard_id='ANALYSIS_ASSIGN_UNIQUE',
        proposal_sha256=sha(PKG/'proposal/PROPOSAL.json'),code_manifest_sha256=proposal['code_manifest']['sha256'],input_manifest_sha256=proposal['input_manifest']['sha256'],
        config_sha256=proposal['config']['sha256'],external_source_manifest_sha256=proposal['external_sources']['sha256'],resource_caps=total,
        device=cfg['device'],cuda_environment=cfg['cuda_environment'],wave_participants=['A'],max_retries=0,timeout_seconds=1800,kill_grace_seconds=30,
        template_is_authorization=False,real_command=[str(command),str(BASE/'releases/P10_A_PV_OFFLINE_PREFLIGHT_V1.json')])
    dump(PKG/'proposal/RELEASE_TEMPLATE.json',release)
    dump(PKG/'proposal/CONTROL_REQUIRED.json',dict(status='requirements_only_not_active_control',mode='preflight',formal_gpu_runs_enabled=True,stop_requested=False,
        active_compute_release_id=release['release_id'],active_compute_release='releases/'+release['release_id']+'.json',active_compute_task_ids=[proposal['task_id']],
        allowed_task_id_to_add=proposal['task_id'],current_compute_limits=total,per_task_compute_limits={proposal['task_id']:total},
        board_task=dict(id=proposal['task_id'],owner='A',revision=1,status='ready',release='releases/'+release['release_id']+'.json'),
        analysis_must='Publish new task and released identity; preserve all old closures. This file does not alter CONTROL or grant compute. Use replacement finite cap table; do not inherit CPU zero Torch/model limits.'))
    print(json.dumps(dict(code_files=len(files),external_sources=len(rows),proposal=ref(PKG/'proposal/PROPOSAL.json'))))

if __name__=='__main__':main()
