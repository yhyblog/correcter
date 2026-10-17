"""CPU preparation for the authorized successor; never launches compute."""
import collections
import hashlib
import json
import shutil
import sys
from pathlib import Path

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORKSPACE=C.parents[2]
ROOT=C/'results/B/B_D24_SMOL_AUX_RETRAIN_V1'
PREDECESSOR=C/'results/B/B_D24_POST_TRIGGER_MODES_V1/recovery_r3'
sys.path.insert(0,str(PREDECESSOR/'code'))
from qio import read, new_json, ref, sha, utc

AUTH=C/'deadline_20260924/PER_BASE_AUXILIARY_TRAINING_AUTHORIZATION_V1.json'
PROTOCOL=C/'deadline_20260924/PER_BASE_AUXILIARY_RETRAINING_V1.md'
assert sha(AUTH)=='6024320bc4b05cbdaa6e96062403c0d3f5fd1fc632c4f73872d3524cf7a4fdc3'
assert sha(PROTOCOL)=='c265d49f8b9e3cd223cc684549dd5b556a2ec1497bfbf0c2f910b5d922d816e9'
assert not ROOT.exists(), 'do not overwrite frozen successor preparation'
ROOT.mkdir()
test_path=C/'work/B/B_D24_E8_POST_V1_r1/POST_SOURCES.json'
test=read(test_path)['sources']
tasks=sorted({x['task'] for x in test})
assert len(test)==500 and len(tasks)==50

# Compare actual task/environment seeds, not source names. These small registered
# manifests include MT50 tests/reserves, revealed pilot, and historical held data.
registered=[test_path,C/'deadline_20260924/A/config/TEST_SOURCES_V1.json',
 C/'results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/config/SOURCES.json',
 WORKSPACE/'Corrector/outputs/native10_training_20260916/heldout_protocols/heldout_v1/config.json',
 WORKSPACE/'Corrector/outputs/native10_training_20260916/p0/config.json']
forbidden=set(); counts={}
def source_rows(value):
    if isinstance(value,dict):
        if 'task' in value and ('reset_seed' in value or 'env_seed' in value):yield value
        for child in value.values():yield from source_rows(child)
    elif isinstance(value,list):
        for child in value:yield from source_rows(child)
for path in registered:
    rows=list(source_rows(read(path)));counts[str(path)]=len(rows)
    for row in rows:forbidden.add((row['task'],int(row.get('reset_seed',row.get('env_seed')))))

def seed(domain,role,bits):
    return int.from_bytes(hashlib.sha256((domain+'|'+role).encode()).digest()[:8],'big') % (2**bits-1)

parents=[]; seen=set(); collisions=[]
cuts=[5,15,35,55]
for task_index,task in enumerate(tasks):
    for split,n in [('train',4),('development',1)]:
        for ordinal in range(n):
            domain=f'PER_BASE_AUX_V1/SmolVLA/{task}/{split}/{ordinal}'
            salt=0
            while True:
                salted=domain+f'/salt/{salt}'
                env_seed=seed(salted,'environment',31)
                key=(task,env_seed)
                if key not in forbidden and key not in seen:break
                collisions.append(dict(domain=domain,salt=salt,env_seed=env_seed));salt+=1
            seen.add(key)
            cut=cuts[ordinal] if split=='train' else cuts[task_index%4]
            parents.append(dict(source_id=domain,domain=domain,base='SmolVLA',task=task,
                task_ascii_index=task_index,split=split,ordinal=ordinal,cut=cut,salt=salt,
                construction_seed=env_seed,reset_seed=env_seed,env_seed=env_seed,
                policy_seed=seed(salted,'prefix_policy',63),a0_seed=seed(salted,f'fresh_a0/cut/{cut}',63),
                direction_seed=seed(salted,f'local_direction/cut/{cut}',63),
                suffix_policy_seeds=[seed(salted,f'suffix/repeat/{i}',63) for i in range(2)],
                candidates=['old','a0','local_plus','local_minus'],max_rollouts=8,
                early_terminal='record normal-only; no replacement or zero label'))
assert len(parents)==250 and len(seen)==250 and not (seen & forbidden)
assert collections.Counter(p['split'] for p in parents)=={'train':200,'development':50}
assert collections.Counter(p['cut'] for p in parents if p['split']=='train')=={5:50,15:50,35:50,55:50}
assert len({p['policy_seed'] for p in parents})==250
assert len({s for p in parents for s in p['suffix_policy_seeds']})==500
new_json(ROOT/'SOURCE_MANIFEST.json',dict(task_id='B_D24_SMOL_AUX_RETRAIN_V1',base='SmolVLA',
    at_utc=utc(),frozen_before_first_admission=True,parents=parents,train_count=200,development_count=50,
    task_order='ASCII lexical order of the frozen MT50 task names',
    source_namespace='PER_BASE_AUX_V1/SmolVLA/{task}/{split}/{ordinal}',
    seed_derivation='SHA256(domain + /salt/<n> + |role), first8bytes big-endian modulo2**bits-1; env31bits policy63bits',
    salt_collision_records=collisions,registered_forbidden_inputs=[ref(p) for p in registered],
    registered_source_counts=counts,unique_forbidden_task_environment_seeds=len(forbidden),
    task_environment_seed_overlap=0,train_development_parent_overlap=0,
    test_sources_reference=ref(test_path),test_outcomes_read=False))

base_config=C/'work/B/B_D24_E8_POST_V1_r1/configs/smol50k_Post_shard0_r1.json'
base=read(base_config)
method=dict(task_id='B_D24_SMOL_AUX_RETRAIN_V1',at_utc=utc(),authorization=ref(AUTH),protocol=ref(PROTOCOL),
    source_manifest=ref(ROOT/'SOURCE_MANIFEST.json'),base='SmolVLA',checkpoint=base['checkpoint'],
    checkpoint_config_sha256=base['checkpoint_config_sha256'],checkpoint_weight_bytes=base['checkpoint_weight_bytes'],
    frozen_base_updates=0,frozen_external_encoder_updates=0,raw_H=50,native_K=10,NFE=10,control_budget=300,
    actual_environment=dict(suite='MetaWorld MT50',renderer='Mesa llvmpipe',control_hz=80,physics_hz=400,
        frame_skip=5,action_scale=.01,camera='corner2',RGB=[480,480],action='bounded environment 4D',state='actual observed agent_pos 4D'),
    features=dict(encoder='frozen pi05 external visual/language',base_config=ref(C/'work/B/B_D24_E8_POST_V1_r1/BASE.json'),
        projection='existing fixed projection',fitted_PCA_and_norm='new train parents only',
        native_Smol_embedding_claim=False,external_parameters_memory_calls_timing_separately_accounted=True),
    collection=dict(parents=250,rollout_cap=2000,candidates=['old','a0','local_plus','local_minus'],paired_suffix_repeats=2,
        ordinary_fresh_a0_per_parent=1,cut_selection='fixed before collection, never old G0 or outcomes',
        old='preserve true old queue, then natural native K10',a0='fresh C10,discard tail,resume nativeK10',
        direction='opposite smooth Gaussian knots at0/4.5/9; source/cut seeded; no Q direction',
        xyz_rho=.05,gripper_rho=.10,xyz_cap=.15,gripper_cap=.40,boundary_mask_clearance=.05,
        radius='own symmetric feasible radius',trajectory='actual encoded observations/proprio/actions/masks/future5; no fabricated qpos observations',
        replay='same-seed prefix with basic action/observation agreement or existing reliable restore; no full-state proof',
        ineligible='normal-only or technical, never force cut or impute failure'),
    targets=dict(D='future5 from mature actual5-step windows',
        G0='mean(fresh a0 C10 then nativeK10 success over2suffixes) minus mean(true old continuation success over2suffixes)',
        Q='real bounded4D command plans; outcome and identifiable gain/pair masks distinct; suffixes not independent parents'),
    training=dict(initialization='all eight heads from scratch',D_seeds=[1241,1242],G0_seeds=[1341,1342],Q_seeds=list(range(19301,19305)),
        updates_per_member=4000,total_update_cap=32000,Q_member_parameters=7058,
        Q_trainable=['E_s','E_a','H','E_delta','Fadv'],Q_loss='L11: BCE + gain MSE +0.5 pair MSE',
        normalization_and_PCA_train_only=True,checkpoint='fixed4000 final; dev descriptive only',
        cutoff='all-constant G0 target or missing required Q candidate supervision stops affected Full units; no forced gate/no favorable resampling'),
    evaluation=dict(arms=['R','Post','Velocity'],sources_per_arm=500,sources=ref(test_path),baseline_N_reruns=0,
        G0_threshold=.05,comparison='strict greater than',monitor_every=5,intervention_cap=1,commitment=10,
        native_restore_K=10,Q_acceptance_gate=False,Post_and_Velocity='existing native coordinate bridge and own radius rules',
        provenance='supplementary adaptation on previously revealed500, not new unseen test',
        causal_scope='complete base-specific adaptation package; do not isolate individual-head effects or promise improvement'),
    budget=dict(first_collection_cap=2000,test_first_entries=1500,total_attempt_cap=4000,
        corrected_technical_retry_max_per_unit=1,node_cumulative_attempt_cap=20000,old_attempts_never_reset=True,
        original_Post_stage_cap_unchanged=5500,max_wall_hours=12,admission_cutoff_utc='2026-09-23T12:00:00Z',tables_due_utc='2026-09-23T15:00:00Z'),
    concurrency=dict(target_resident_workers=8,training_members_per_gpu=1,all_holders_off_for_entire_formal_family=True),
    implementation_status='CPU source/method preparation frozen; private collector/head-training/deployment integration required before first admission')
new_json(ROOT/'METHOD_FROZEN.json',method)
shutil.copy2(PROTOCOL,ROOT/'PROTOCOL_FROZEN.md')
plan=dict(task_id=method['task_id'],node='B',at_utc=utc(),status='queued_after_current_Post_family',
    authorization=ref(AUTH),source_manifest=ref(ROOT/'SOURCE_MANIFEST.json'),method_frozen=ref(ROOT/'METHOD_FROZEN.json'),
    predecessor_task='B_D24_POST_TRIGGER_MODES_V1',predecessor_run='D24_B_POST_TRIGGER_MODES_r3',
    predecessor_claim=ref(PREDECESSOR/'CLAIM.json'),predecessor_result=str(PREDECESSOR/'RESULT.json'),
    registered_terminal_trigger=str(C/'persistent_queue/nodes/B/wakeup/jobs/D24_B_POST_TRIGGER_MODES_r3__D24_B_POST_TRIGGER_MODES_r3__1.json'),
    continuation='original B terminal handler reads current CONTROL and this plan; finish private runnable integration and execute authorized collection -> D/G0/Q ->1500 eval without a second approval',
    automatic_shell_launcher_ready=False,private_runtime_integration_pending=True,
    next_handler_required_work=['finish native Smol collection and eight-head training adapter against frozen method',
        'validate units/non-test split/real labels on first planned collection, no separate GPU preflight',
        'finite detached queue, cumulative budgets, original-thread terminal registration, eight actual ready workers'],
    GPU_start_condition='current own formal family has exited; reconcile terminal Post results and existing claims first',
    no_cross_node_runtime_dependency=True,no_second_approval=True,A_waits_for_B=False)
new_json(ROOT/'QUEUE_ENTRY.json',plan)
new_json(PREDECESSOR/'NEXT_AUTHORIZED_STAGE.json',dict(plan,result_root=str(ROOT)))
new_json(ROOT/'CPU_PREPARATION.json',dict(status='complete_source_and_method_preparation',at_utc=utc(),
    real_GPU_calls=0,real_rollouts=0,optimizer_updates=0,source_count=250,
    checks=['200train/50development parents','fixed cut distribution','zero actual task/env-seed overlap with registered test/held/pilot inputs',
            'unique parent and suffix random streams','original Smol Mesa80Hz/.01/K10 kept','protocol authorization hashes matched'],
    remaining='private runtime adapter and finite collection/train/eval pipeline integration before first scientific admission'))
new_json(C/'receipts/B/B_D24_SMOL_AUX_RETRAIN_V1_ACK.json',dict(task_id=method['task_id'],at_utc=utc(),
    status='ACK_CPU_sources_method_prepared_queued_after_Post',authorization=ref(AUTH),result_root=str(ROOT),
    queue_entry=ref(ROOT/'QUEUE_ENTRY.json'),CPU_preparation=ref(ROOT/'CPU_PREPARATION.json'),
    GPU_launched=False,automatic_shell_launcher_ready=False,private_runtime_integration_pending=True,
    next_action='on original Post terminal event continue implementation and authorized own Smol chain; no second approval',A_waits_for_B=False))
print(json.dumps(dict(status='prepared',root=str(ROOT),parents=len(parents),forbidden_seeds=len(forbidden),collisions=len(collisions),GPU_calls=0)))
