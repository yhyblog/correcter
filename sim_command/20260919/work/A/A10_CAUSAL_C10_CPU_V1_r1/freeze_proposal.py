from pathlib import Path
import ast,hashlib,json,sys
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');R=B.parents[2];P=B/'results/A/A10_CAUSAL_C10_CPU_V1';W=B/'work/A/A10_CAUSAL_C10_CPU_V1_r1';O=B/'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1';N=B/'results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1'
sys.path.insert(0,str(P/'code'))
from budget import TOTAL,BRANCHES,LAUNCHER,numeric_caps,GRAPHICS,INITIALIZATION
from core.contracts import TASK,RELEASE,HANDOFF_SPEC

def ref(p):return dict(path=str(p),realpath=str(p.resolve()),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def jput(name,value):
 p=P/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
c=json.loads((P/'config/CONFIG.json').read_text())
identity=dict(task_id=TASK,task_revision=1,release_id=RELEASE,node_role='A',run_id=TASK+'_r1_A_wave09',wave_id='A_wave09_causal_C10',shard_id='A_shelfplace_C10')
jput('proposal/IDENTITY.json',identity)
lineage=[]
for f in sorted((P/'code').rglob('*.py')):
 relative=f.relative_to(P/'code');old=None
 if relative.parts[0] in ['corrector','vendor_vla'] or str(relative)=='feature_path.py' or relative.parts[0]=='core':old=O/'code'/relative
 if relative.parts[0]=='native':old=N/'code/core'/relative.name
 if str(relative)=='dg_models.py':old=R/'ACT-RECAP/src/ac_tmil/future_aware/models.py'
 row=dict(new=ref(f),origin=ref(old) if old and old.exists() else None)
 row['relationship']='new_integration' if row['origin'] is None else ('byte_identical' if row['new']['sha256']==row['origin']['sha256'] else 'private_adaptation')
 lineage.append(row)
jput('INTEGRATION_MANIFEST.json',dict(schema='private_new_integration_lineage_v1',files=lineage,validated_whole_runtime=False,
    principal_changes=['CPU-testable causal controller and queue ownership','fresh independent prefix and observed-evidence mismatch stop',
    'strict loader extracted from PV V3; pc H20; environment enabled only via native EGL before Torch',
    'private graphics two->17 observation phases per process, initialization 1->16 controls plus native mj_forward accounting',
    'D/G0 frozen two-member real calls; residual diagnostic separate from G0 input',
    'separate Post/Velocity own-anchor objectives: 3+8 ensemble calls, unchanged own-radius math',
    'two sequential fresh children inside one inherited reservation and exit barrier'],
    shared_guard_override='Accepted installation SHA replaces obsolete native snapshot guard SHA explicitly in external manifest',
    source_packages=[str(O),str(N)],public_interface_v1_modified=False))
files=[dict(path=str(f.relative_to(P/'code')),sha256=ref(f)['sha256'],size_bytes=f.stat().st_size) for f in sorted((P/'code').rglob('*')) if f.is_file() and f.name!='CODE_MANIFEST.json']
jput('code/CODE_MANIFEST.json',dict(schema='private_code_snapshot_v1',files=files))
quote=dict(per_branch={br:dict(numeric=numeric_caps(br),initialization=INITIALIZATION,graphics=GRAPHICS,aggregate=BRANCHES[br]) for br in BRANCHES},launcher=LAUNCHER,wave=TOTAL,
    source_derived_formulas=dict(taskset='one MT1: 50 resets of temporary native instance',native_resets='50 taskset + 1 wrapper initialization + 1 diagnostic = 52 per fresh branch',
    reset_model='SawyerXYZ.reset calls reset_model then MujocoEnv.reset calls reset_model again: 104 per branch',
    settling='104 reset_model * 50 _reset_hand do_simulation * frame_skip5 = 26000 per branch',
    policy_steps='5 prefix + 10 committed correction + 1 restored-native first action = 16 per branch',
    control_substeps=[((i+1)*400)//30-(i*400)//30 for i in range(16)],render='1 full reset observation + 16 control observations = 17 per branch',
    native_forward='2 native constructor forward + 104 reset_model*(direct shelf forward + set_state forward) +16 control forwards =226 per branch',
    native_forward_scope='Python-bound mujoco.mj_forward entries; MuJoCo internal C calls not guessed',
    samples='Post(prefix+anchor+restore)=3; Velocity(prefix+anchor+guided+restore)=4; 10 flow per full sample',
    visual='6 singleton causal frame encodings + 3 images (1 real/2 padded) per full sample',
    language='1 pooled instruction embedding +1 token embedding per full sample',
    D='two members at t0 and t5 =4 per branch',G0='two members only at sole eligible monitor cut5 =2 per branch',
    Q='Post: anchor+gradient+final=3; Velocity: anchor+3*(gradient+local_after)+final=8; four frozen CPU members each',
    native_model_constructions='2 MuJoCo native envs (taskset temporary plus live) per wrapper; native C internals outside explicit API counters'),
    aliases=dict(environment_reset_calls='sum taskset + wrapper initialization + diagnostic resets; model resets counted separately',
        initialization_reset_calls='taskset_reset_calls + wrapper_initialization_reset_calls',
        encoder_forward_calls='visual_encoder_forwards + language_embedding_forwards',
        model_gpu_inference_calls='alias for complete VLA sampling entries only; not all encoder/D/G0/network calls',
        flow_forward_calls='one model.denoise_step per action_expert_forward; same operation nesting, not sum for deployment cost',
        critic_backward_calls='same four action_gradient_calls; no parameter backward/update',
        native_mj_forward_calls='initialization_mj_forward_calls + policy_mj_forward_calls',
        explicit_mj_forward_calls='inherited graphics-probe-local explicit calls =0; native_mj_forward_calls counts actual environment calls',
        model_initializations='policy+four Q+two D+two G0 each branch; init journal model_initializations0 avoids double count'),
    derived_not_extra_calls=dict(mujoco_mj_step_binding_calls=10432,mujoco_mj_rnePostConstraint_binding_calls=10432,
        mujoco_mj_resetData_binding_calls=104,policy_control_physics_substeps=426,all_physics_substeps=52426,
        full_path_explicit_graphics_events=2*sum(GRAPHICS.values()),Q_member_action_backward_paths=16),
    actual_charging='entered charged once even failure/missing terminal; actual lower on early stop; alias totals never added as separate calls',
    early_stop='first early branch stop also ends remaining planned wave; no seed replacement or retry; cut prefix mismatch stops Velocity before intervention',
    framework_internal_API_counts='not measured, not claimed zero')
jput('proposal/RESOURCE_BUDGET.json',quote)
command=P/'commands/run_proposed_causal_c10.sh';release_path=B/'releases'/(RELEASE+'.json')
proposal=dict(proposal_id='CAUSAL_C10_A_NATIVE_INDEPENDENT_REPLAY_V1',status='proposed_not_authorized',publication_is_authorization=False,
    campaign_id='corrector-sim-20260919',task_id=TASK,task_revision=1,node_role='A',owner_host='trial-303224955-trialrun-303224955-worker-0',wave_participants=['A'],
    config=ref(P/'config/CONFIG.json'),input_manifest=ref(P/'INPUT_MANIFEST.json'),external_sources=ref(P/'EXTERNAL_SOURCE_MANIFEST.json'),code_manifest=ref(P/'code/CODE_MANIFEST.json'),
    integration_manifest=ref(P/'INTEGRATION_MANIFEST.json'),budget=ref(P/'proposal/RESOURCE_BUDGET.json'),command=ref(command),
    real_command=['bash',str(command),str(release_path)],cwd=str(P),required_release_path=str(release_path),
    authorization_identity=identity,device=c['device'],cuda_environment=c['cuda_environment'],occupancy_handoff=HANDOFF_SPEC,source=c['source'],
    launcher_caps=LAUNCHER,branch_numeric_caps={br:numeric_caps(br) for br in BRANCHES},branch_caps=BRANCHES,resource_caps=TOTAL,
    branch_order=['Post','Velocity'],branch_attempts_max=2,commands_max=1,claims_max=1,max_retries=0,
    timeout_seconds=1800,kill_grace_seconds=30,restoration_observation_timeout_seconds=120,
    timeout_scope='each of two sequential GNU timeout children includes its complete SHA check, imports, loads, reset, prefix, DG0, PV, C10, H20 first action and in-process cleanup',
    timeout_outside=['parent metadata/full SHA/claim/NVML and cache setup','formal lock wait','nominal300 handoff plus final query completion allowance','reserved group drain retains lock until fully exited','restoration file observation up to120'],
    maximum_nominal_timed_children_with_grace_seconds=3660,end_to_end_strict_upper_bound_seconds=None,
    resource_estimates=dict(RAM_bytes_estimate=34359738368,RAM_conservative_reservation_bytes=68719476736,
        VRAM_bytes_estimate=17179869184,VRAM_conservative_reservation_bytes=25769803776,
        output_disk_bytes_estimate_max=268435456,peak_scope='one live child; sequential process exit verified; estimates not measured resource caps',
        device='fixed physical GPU0; all eight holders remain reserved throughout both branches',
        weight_SHA_passes='parent plus one per branch (three full passes maximum); no full SHA pass in this CPU preparation'),
    occupancy=dict(lifecycle=c['occupancy_lifecycle'],installed_guard_SHA=HANDOFF_SPEC['guard_expected_sha256'],handoff_seconds=300,
        same_lock_entire_wave=True,reservation_reacquire=False,nested_lifecycle=False,idle_subset_holders=False,
        restore_only_after_full_group_exit=True,including_failures=True,kill_external_processes=False,
        successful_poll_evidence='raw successful guard poll data absent under current guard; null, not reconstructed from manager yield timestamps'),
    state_restore=dict(complete_state_supported=False,method='two fresh fixed-seed independent replays',no_hidden_equivalence_claim=True,
        cut_compare='saved RGB/proprio/context bytes, prefix raw plan, actions/rewards/flags/time must match before V correction; mismatch stops',
        analysis_decision_required='Approve finite independent-replay alternative via a NEW release; CPU_READY is not that decision'),
    cost_semantics=dict(deployment={'Post':1,'Velocity':2},diagnostic_PV_sampling=3,prefix_sampling=2,H20_restore_sampling=2,
        shared_anchor_or_prefix_savings=0,success_rate_sample=False,no_ranking=True),
    unvalidated=['joint native+causal D/G0+PV+C10 integration','independent prefix observable agreement','native reset exact counts in the new two-process path','numerical D/G0 compatibility at this legal cut','render series/early-stop cleanup'],
    CPU_forbidden_compute_performed=False,old_releases_reusable=False,public_interface_modified=False)
jput('proposal/PROPOSAL.json',proposal)
release=dict(status='unauthorized_template',issuer='analysis',campaign_id=proposal['campaign_id'],task_id=TASK,task_revision=1,node_role='A',release_id=RELEASE,
    owner_host=proposal['owner_host'],wave_participants=['A'],max_retries=0,timeout_seconds=1800,kill_grace_seconds=30,branch_order=['Post','Velocity'],branch_attempts_max=2,
    resource_caps=TOTAL,device=c['device'],cuda_environment=c['cuda_environment'],occupancy_handoff=HANDOFF_SPEC,
    proposal_sha256=ref(P/'proposal/PROPOSAL.json')['sha256'],code_manifest_sha256=proposal['code_manifest']['sha256'],input_manifest_sha256=proposal['input_manifest']['sha256'],
    config_sha256=proposal['config']['sha256'],external_source_manifest_sha256=proposal['external_sources']['sha256'],authorization_identity=identity,
    run_id=identity['run_id'],wave_id=identity['wave_id'],shard_id=identity['shard_id'],unused_caps_reusable=False)
jput('proposal/RELEASE_TEMPLATE.json',release)
board=dict(id=TASK,owner='A',status='ready',revision=1,dependencies=['A10_CAUSAL_C10_CPU_V1'],brief='tasks/'+TASK+'.md',release='releases/'+RELEASE+'.json',expected_result='receipts/A/'+TASK+'_RESULT.json')
jput('proposal/BOARD_TASK_TEMPLATE.json',board)
control=dict(campaign_id=proposal['campaign_id'],mode='preflight',formal_gpu_runs_enabled=True,stop_requested=False,allowed_task_ids=[TASK],active_compute_release_id=RELEASE,
    active_compute_release='releases/'+RELEASE+'.json',active_compute_task_ids=[TASK],active_occupancy_handoff=HANDOFF_SPEC,current_compute_limits=TOTAL,per_task_compute_limits={TASK:TOTAL})
jput('proposal/CONTROL_REQUIRED.json',dict(status='proposed_fields_only_not_current_CONTROL',fields=control,close_previous_releases=True))
print(json.dumps(dict(proposal=str(P/'proposal/PROPOSAL.json'),source_files=len(files),caps=len(TOTAL),physical_reset=TOTAL['environment_reset_calls'],graphics=sum(GRAPHICS.values())*2),indent=2))
