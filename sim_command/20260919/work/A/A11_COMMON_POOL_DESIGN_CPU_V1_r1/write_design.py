"""Write design documents from small existing metadata; not a collector/logger.

Standard-library JSON and integer arithmetic only. No runtime/model import,
dataset payload loading, environment, hardware, launcher, claim or deletion.
"""
from pathlib import Path
import collections
import hashlib
import json
import math

R=Path('/mnt/bn/arnold-recommend/yaohaoyang')
B=R/'Corrector/sim_command/20260919'
T='A11_COMMON_POOL_DESIGN_CPU_V1'
P=B/'results/A'/T
BP=B/'results/B/B10/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z'
INPUTS={}
def file(path):
    path=Path(path); assert path.stat().st_size<3*1024*1024
    v=path.read_bytes(); INPUTS[str(path)]=dict(path=str(path),sha256=hashlib.sha256(v).hexdigest(),size_bytes=len(v))
    return v
def read(path):return json.loads(file(path))
def ref(path):
    path=Path(path)
    if str(path) not in INPUTS:file(path)
    return INPUTS[str(path)]
def put(name,obj):
    with (P/name).open('x') as f:json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')

ack=read(B/'receipts/A'/f'{T}_ACK.json')
release=read(B/'releases/P00_COMMON_POOL_DESIGN_CPU_V1.json')
for name in ['CONTROL.json','TASK_BOARD.json','MASTER_PLAN.md','tasks/A11_COMMON_POOL_DESIGN_CPU_V1.md',
             'contracts/COMMON_POOL_CPU_DESIGN_SCOPE_V1.md','contracts/P00_PREPARATION_CONTRACT_V1.md',
             'contracts/DATA_LOG_CONTRACT_V1.md','contracts/INVENTORY_DECISIONS_V1.md',
             'manifests/PV_DIRECTION_CPU_ANALYSIS_V1_ACCEPTANCE.json','receipts/A/A00_REPORT.md',
             'receipts/B/B10_REPORT.md','receipts/B/B10_RESULT.json']:
    file(B/name)
assets=read(B/'receipts/A/A00_ASSETS.json')
public=read(B/'manifests/PUBLIC_INTERFACE_V1.json')
schema=read(Path(public['files']['interface.schema.json']['path']))
assert ref(public['files']['interface.schema.json']['path'])['sha256']==public['files']['interface.schema.json']['sha256']
methods=read(BP/'configs/METHODS.json');views=read(BP/'DERIVED_VIEW_CONTRACT.json')
bmanifest=read(BP/'ARTIFACT_MANIFEST.json')
for rel in ['configs/METHODS.json','DERIVED_VIEW_CONTRACT.json']:
    expected=next(x for x in bmanifest['files'] if x['path']==rel)
    assert ref(BP/rel)['sha256']==expected['sha256']
history_access=read(B/'manifests/HISTORICAL_DATA_ACCESS_V1.json')
history_ready=read(history_access['publication']['path'])
history_lines=file(history_access['index']['path'])
assert hashlib.sha256(history_lines).hexdigest()==history_access['index']['sha256']
historical=[json.loads(x) for x in history_lines.splitlines()]
splits=read(history_access['parent_splits']['path'])
assert ref(history_access['parent_splits']['path'])['sha256']==history_access['parent_splits']['sha256']
audit_path=R/'embodied-ai-workspace/artifacts/vla-baselines/preparation/20260911/metaworld.data-audit.json'
audit=read(audit_path)
map_path=R/'vla-corrector/src/lerobot/envs/metaworld_config.json'
mapping=read(map_path)
info_path=R/'embodied-ai-workspace/datasets/metaworld-mt50/meta/info.json'
info=read(info_path)
assert ref(info_path)['sha256']==audit['metadata_sha256']
assert audit['status']=='pass' and audit['environment_ids']==50 and audit['checks']['50_demos_per_environment']
task_to_id=mapping['TASK_NAME_TO_ID'];assert sorted(task_to_id.values())==list(range(50))
past_tasks={r['task'] for r in historical}
frames=sum(r['frames'] for r in audit['per_task']);assert frames==204806
demo_pair_upper=sum(max(0,r['frames']-10) for r in audit['episodes_detail'])
assert demo_pair_upper==179806

coverage=[]
for name,task_id in sorted(task_to_id.items(),key=lambda kv:kv[1]):
    demo=next(x for x in audit['per_task'] if x['task_id']==task_id)
    old=[r for r in historical if r['task']==name]
    count=collections.Counter((x['split'],x['kind']) for x in old)
    coverage.append(dict(environment_task=name,environment_id=task_id,
        instruction=mapping['TASK_DESCRIPTIONS'][name],language_task_indices=demo['task_indices'],
        normal_demonstrations=dict(episodes=demo['episodes'],frames=demo['frames'],
            source=ref(audit_path),metadata=ref(info_path),root=audit['dataset_root'],
            observation_state='declared float32[4]',raw_actions='declared float32[4]; actual values may exceed [-1,1]',
            reward_and_success='next.reward/next.success declared; per-task outcomes/first-success not read in this task',
            RGB='declared 3x480x480 image; historical file-presence audit, not every image decoded',
            next_observation='unknown as explicit field; may use contiguous next frame within same episode only after view validation; final next frame unknown',
            terminated='unknown: no separate field in info schema',truncated='unknown: no separate field in info schema',
            normal_role='existing demonstration source; no assertion every episode is successful/optimal',
            exact_eligible_normal_pair_count=None,missing_reason='requires later frozen parent split and legal frame/outcome masks, not new simulation'),
        historical_train600=dict(parent_count=count[('train','source_prefix')],
            a0_repeat0_suffix_count=count[('train','a0_repeat0_suffix')],
            supervised_bank_present=name in past_tasks,source=ref(history_access['publication']['path']),
            recollect=False,new_MT50_pool_member=False),
        existing_train_development_trajectory_index=dict(
            source_prefix_train=count[('train','source_prefix')],source_prefix_development=count[('development','source_prefix')],
            all_indexed_segments=len(old),first_success_observed_segments=sum(x['first_success_step'] is not None for x in old),
            actions_rewards_success='indexed existing fields' if old else 'unknown outside authorized historical index',
            physics_state='privileged restoration provenance only' if old else 'unknown',
            RGB='missing in indexed historical trajectories' if old else 'unknown',
            next_observation='missing in indexed historical trajectories' if old else 'unknown',
            terminated='unknown; historical done flags merge reasons' if old else 'unknown',
            truncated='unknown; historical done flags merge reasons' if old else 'unknown',
            source=ref(history_access['index']['path'])),
        new_pool=dict(status='planned_no_collection_release',H=10,
            frozen_train_parents=None,frozen_development_parents=None,frozen_seeds=None,
            proposed_train_parents=8,proposed_development_parents=2,
            reason='equal planned allocation for all 50 actual environments; not conditional on five-task G0 alarm')))
put('POOL_COVERAGE_AND_GAPS.json',dict(schema='common-pool-coverage-draft/1',task_id=T,status='DESIGN_ONLY',
    environment_count=50,normal_demo_episodes=2500,normal_demo_frames=frames,language_index_count=49,
    duplicate_language_index=dict(index=40,environments=['push-back-v3','push-v3'],
        reason='distinct environment IDs 37/38; shared instruction does not merge parents or coverage'),
    mapping_basis=dict(config=ref(map_path),historical_audit=ref(audit_path),mapping_is_static_not_live_environment_probe=True),
    rows=coverage,
    historical_separate=dict(access_manifest=ref(B/'manifests/HISTORICAL_DATA_ACCESS_V1.json'),
        train_parents=600,development_parents=100,indexed_prefixes=700,indexed_a0_repeat0_suffixes=600,total_segments=1300,
        full_candidate_library=False,old_13x4_not_new_default=True,train600_recollection=False,
        missing_observation_next_terminated_truncated_segments=1300,held_trajectories_opened=0,
        other_legacy_eval_or_calibration_coverage='not inspected; outside this train/development index'),
    future_missing=[
        'new native H10 parents/cuts/true per-step n+1 observations and terminal provenance',
        'frozen normal-demo episode split and normalizer/token/feature identities',
        'MT50 D/G0/Q training identity; existing five-task models do not establish coverage',
        'restoration/replay equivalence and per-task initialization bounds',
        'actual project storage quota; pool free capacity is not a project quota']))

fields=[
    dict(group='causal_identity',fields=['dataset_revision','parent_episode_id','source_id','branch_id','suffix_id','split','task','instruction','source_seed','generation_seed','suffix_seed','repeat_id'],consumers=['D5','G0','Q','VLA-Corrector-adapted','GAF-v1-adapted']),
    dict(group='true_transition',fields=['obs_t RGB/state refs','actual raw/normalized action','obs_t+1 refs','reward','success','first_success_state_index','terminated','truncated','technical_status','outcome_complete'],consumers=['D5','G0','Q','VLA-Corrector-adapted','GAF-v1-adapted']),
    dict(group='plans',fields=['old raw50/queue age/remaining','fresh a0 raw50','candidate raw50','executed prefix C5/C10','discarded tail identity','noise bytes/ref/SHA and RNG stream identity'],consumers=['G0','Q','GAF-v1-adapted']),
    dict(group='core_features',fields=['observed history[5,4096] and masks','proprio[5,4] and masks','past_actions[4,4]','language[2048]','remaining','raw_normalizer','PCA train-parent fit identity'],consumers=['D5','G0','Q']),
    dict(group='token_features',fields=['frozen encoder signature','tokens[256,2048] at t and t+10','action_t[4]','normal-demo selection mask'],consumers=['VLA-Corrector-adapted']),
    dict(group='GAF_features',fields=['legal policy state[4]','language[2048]','actually executed action chunk[10,4]','first_success_state','discount .99 per actual control'],consumers=['GAF-v1-adapted']),
    dict(group='privileged_restore_only',fields=['sim/model/task state','wrapper timers','RNG states','policy queue/history state','verification hashes'],consumers=['restore/replay validator only; prohibited in policy/D/G0/Q/GAF inputs']),
]
method_views=[
    dict(method='D5',target='next five arrived 4096D observation features conditional on current legal history and exact next5 executed commands',
         horizon=5,input_groups=['causal_identity','core_features','true_transition'],
         selection='contiguous five-step windows in same physical parent/branch; commands match recorded execution; early terminal missing future is masked, never invented',
         normal_only=False,labels_need_complete_terminal_suffix=False,
         initialization='historical two D members 241/242, five-task lineage; MT50 training/init choice pending',
         missing='new actual feature manifest and recipe; no D forwards needed merely to store D targets'),
    dict(method='G0',target='mean terminal success(fresh first5 then native10) minus mean terminal success(old queue next5 then native10)',
         historical_label_commitment=5,deployment_commitment=10,
         input_groups=['causal_identity','core_features','plans','true_transition'],
         selection='same cut/parent; target5 branches only; complete valid suffix outcomes; restoration/comparability eligibility explicit',
         normal_only=False,labels_need_complete_terminal_suffix=True,
         input_semantics='current context + known old next5 + D5 prediction; mature residual is separate diagnostic, not a new G0 input',
         initialization='five-task gate341/342 with original regression semantics; no sigmoid or G10 relabel',
         missing='MT50 component fit, D/G0 feature binding and comparable complete target5 pairs'),
    dict(method='Q',target='success under fixed candidate C10 then fresh native10 continuation; BCE plus unchanged gain/pair semantics',
         horizon=10,input_groups=['causal_identity','core_features','plans','true_transition'],
         selection='complete target10 suffix labels; candidate/a0 comparison only same parent/cut with admitted comparability; raw alias-aware weights',
         normal_only=False,labels_need_complete_terminal_suffix=True,
         initialization='historical four-member A4000 uses five tasks/train600 and per-member PCA; MT50 init/fit/normalizer choices pending',
         missing='new action bank with outcomes and parent-only PCA/normalizer fitting; no training now'),
    dict(method='VLA-Corrector-adapted',target=methods['VLA-Corrector-adapted']['target'],horizon=10,
         input_groups=['causal_identity','true_transition','token_features'],
         selection='existing normal demonstration episode-internal (t,t+10); all 11 states/10 actual actions contiguous and policy-compatible; no branch splice or success-based replacement',
         normal_only=True,normal_definition='demonstration collection role, not merely an a0 family or a successful corrected trajectory',
         initialization='old best_cosine h1/k10 remains historical; original random frame-pair90/10 lineage disclosed; new component training choice pending',
         missing='old token cache absent; new single shared extraction and parent-grouped view required; no token/PCA substitution'),
    dict(method='GAF-v1-adapted',target=methods['GAF-v1-adapted']['target'],horizon=10,
         input_groups=['causal_identity','true_transition','GAF_features'],
         selection='complete contiguous true trajectories; actual ten-action windows only, exclude terminal-short chunks lacking declared padding/mask support; never pretend generated50 was executed50',
         normal_only=False,discount=.99,discount_unit='one actual control action',
         target_formula='gamma**(first_success_state-start_step-1) before success; 1 at/after success; 0 only for complete negative outcome; censored excluded',
         initialization='three independent critics, original MSE/guidance mechanism per B10; no training performed',
         missing='frozen legal state/language transform and real complete-view manifest; B live readiness not assumed'),
]
families=[
    dict(id='a0',recommended_count=1,label_window=10,generation='one fresh unguided pi05 raw50 at cut',
         necessary_for='Q detached anchor and R-like fresh action; may also supply first5 action data for separate G0 fresh target',
         incremental_generation=dict(VLA=1,flow=10,Q=0,D=0,G0=0,gradient=0)),
    dict(id='independent_native',recommended_count=1,label_window=10,generation='one independent frozen-seed unguided pi05 raw50 at same cut',
         necessary_for='minimal same-policy action variation for gain/pair; does not claim broad guided-action coverage',
         incremental_generation=dict(VLA=1,flow=10,Q=0,D=0,G0=0,gradient=0)),
    dict(id='G0_old5',recommended_count=1,label_window=5,generation='already recorded old queue next5; not a fresh candidate',
         necessary_for='unchanged execute5_then_fixed10 counterfactual target',incremental_generation=dict(VLA=0,flow=0,Q=0,D=0,G0=0,gradient=0)),
    dict(id='G0_fresh5',recommended_count=1,label_window=5,generation='reference a0 first5; different commitment from Q a0',
         necessary_for='fresh minus old five-step target; no implicit label alias with C10',incremental_generation=dict(VLA=0,flow=0,Q=0,D=0,G0=0,gradient=0)),
    dict(id='normal',recommended_count=1,label_window=None,generation='source normal H10 trajectory continues old queue at cut',
         necessary_for='unmodified parent baseline and normal trajectory provenance',
         incremental_generation='included in full source generation, not an a0 slot or copied terminal label'),
]
draft=dict(schema='common-raw-pool-design-draft/1',status='QUOTATION_NOT_EXECUTABLE',task_id=T,
    pool_namespaces=dict(new='MT50_H10_COMMON_RAW_PENDING',demo='EXISTING_MT50_DEMOS_REFERENCE_VIEW_PENDING',
        historical_E1='HISTORICAL_FIVE_TASK_TRAIN600_SEALED',history_index='HISTORICAL_TRAIN_DEV_ACCESS_V1'),
    fixed=dict(backbone='pi05-MT50-SFT030000',environments=50,H=10,generated_length=50,C_Q=10,D_horizon=5,G0_label_commitment=5,G0_followup_H=10,
        monitor_stride=5,native_suffix_H=10,common_protocol_step_horizon=300,E8_included=False,real_robot_included=False),
    frozen_execution=dict(train_parents_per_task=None,development_parents_per_task=None,cuts_per_parent=None,
        candidate_families=None,repeats=None,source_seeds=None,shards=None,collector_code=None,restore_implementation=None,release=None),
    recommendation_not_frozen=dict(train_parents_per_task=8,development_parents_per_task=2,total_parents=500,
        cuts_per_parent=1,cut_schedule='alternate preassigned 5 and 55 by ordinal within each task/split; 4+4 train and1+1 development; no outcome/G0 selection',
        Q_candidates=2,repeat_count_Q=2,repeat_count_G0=2,
        rationale='minimal coverage/field-closure tranche with both target windows and two independent suffix seeds; no claim of statistical power or sufficient final learning',
        selected_demo_parents_train_per_task=40,selected_demo_parents_dev_per_task=10,
        effective_legal_cut_or_complete_label_count=None,
        scarcity_action='keep no-cut/no-alarm/early-end/failure entries and report coverage; no refill or seed substitution'),
    parent_split=dict(unit='parent episode',rule='analysis freezes task-balanced parent manifest and seeds before any outcomes; all cuts/candidates/repeats/features inherit split',
        demo_rule='separate original episode IDs; propose40/10 per actual task by precommitted salted ordering, salt/IDs pending; never frame-pair random split',
        demo_dev_limit='base pi05 already trained on all2500 demos; this is component development, not unseen-to-backbone test',
        historical_held_policy='never load or route to new train/new independent test',
        future_test='new independent namespace only after analysis locks methods; not created now'),
    candidate_families=families,
    deferred_families=dict(Post='0 selected; historical five-task Q cannot imply MT50 competence; any future native Post family requires separately priced frozen generation',
        Velocity='0 selected; no diagnostic rerun or parameter change; optional active-clean logging only in independently planned future guided call',
        random_perturbation='not selected; amplitude/distribution would need a separate analysis decision; no new radius or sweep'),
    field_view_matrix=fields,method_views=method_views,
    B_frozen_contracts=dict(methods=ref(BP/'configs/METHODS.json'),view_contract=ref(BP/'DERIVED_VIEW_CONTRACT.json'),
        no_official_GAF_repository_claim=True,public_interface=ref(B/'manifests/PUBLIC_INTERFACE_V1.json')),
    shared_features=dict(key='observation content SHA + encoder/checkpoint/input preprocessing/layer/dtype signature',
        cache='one physical extraction per identical signature; consumers reference immutable arrays; do not count two logical readers as two forwards',
        tokens_not_PCA=True,signature_equivalence_must_be_verified=True,
        policy_internal_encoder_reuse='not assumed; conservative quote counts explicit extraction plus sampling encoders',
        fitting='PCA/normalizer statistics fit on train parent IDs only; fixed pretrained action normalizer remains distinct',
        future_extraction_authorized=False),
    interface_v1=dict(immutable=True,schema=public['files']['interface.schema.json'],
        existing_wire_fields=list(schema['$defs']['transition']['properties']),
        sidecar_design='raw_data_manifest indexes SHA-bound wire record files plus a separate keyed collection_evidence index; existing observation/context refs may point at versioned bundles',
        sidecar_fields=['repeat_id','target_id/commitment/followup policy','logical vs physical alias IDs','outcome completeness/censor mask',
            'snapshot/replay proof and RNG refs','per-step termination arrays','feature signatures/token refs','candidate/generation/cost-event lineage'],
        no_extra_wire_keys='v1 additionalProperties=false; sidecars use separate schema/manifest and adapter opt-in, not unrecognized transition keys',
        real_ref_identity='path+SHA+format must exist before publication; draft nulls are not real wire records',
        B_sidecar_consumer_ready=False,requires_new_schema_v2_now=False),
    initialization_lineage=['pi05 SFT030000: all50 tasks/2500 demonstrations/30k updates inherited',
        'D/G0/Q: historical five-task fitting and train600 lineage; not labeled MT50 adapted',
        'VLA-Corrector old h1/k10 and random-pair split remain separate; no equal-total-training-data claim',
        'GAF independent MSE ensemble adapted as B10; no completed training asset claimed'],
    actual_counts={k:0 for k in release['limits']})
put('COMMON_POOL_DRAFT.json',draft)

put('COLLECTION_SHARDS_DRAFT.json',dict(schema='collection-shard-design-draft/1',status='UNFROZEN_NON_EXECUTABLE',
    actual_A11_B11_collection='planned',release_id=None,global_manifest_sha256=None,real_seed_list=None,sources=[],
    identities=dict(pool='analysis-assigned immutable dataset revision',
        parent='pool/task-name/preassigned-parent-ordinal (seed and initial-state identity in frozen manifest)',
        source='parent/H10/scheduled-cut-step',branch='source/target-id/candidate-family/candidate-id',
        suffix='branch/repeat-id/suffix-seed-identity',generation='source/generation-kind/generation-seed/noise-SHA',
        physical_attempt='logical unit + attempt ordinal bound by independent release; retries default0',
        actual_event='run/node/process/episode-or-source/event_id; entered/returned/failed identify one operation'),
    ownership=dict(rule='analysis materializes explicit disjoint A/B parent lists before release; runtime never hashes/races to claim unassigned sources',
        proposed_balance='alternate parent ordinals within every task and split, 4train+1dev each host per task for this quote',
        whole_parent_one_owner=True,all_branches_repeats_and_restore_same_owner=True,
        actual_host_shards=None,host_move='only analysis explicit reassignment after verified old process exit; preserve IDs/seeds and failure evidence'),
    paths=dict(template='results/<owner>/<released_run_id>/shards/<shard_id>/parents/<parent_id>/<target>/<candidate>/<repeat>/<attempt>/',
        staging='unique attempt staging tree; no overwrite or deletion',completion='atomic complete record after all referenced files/SHA/counts and fsync; immutable thereafter',
        aggregate='A writes results/A/<released_pool_id>/data_manifest.json; analysis freezes its reference in manifests/',
        B_views='B-owned independent immutable view indices; common raw pool read-only'),
    idempotency=dict(completed='identity/hash-valid complete unit is reused, never rerun',
        failed_or_incomplete='retain failed/partial outputs and spent entered costs; no stale-heartbeat takeover or automatic retry',
        conflicts='mismatched identity/path/seed/complete hash fails closed; do not force overwrite',
        recovery='analysis decides resume-missing-units vs new attempt/release; no replacement seed, success filling or reuse of closed budget',
        alias='logical family IDs persist; one physical execution linked only with proven identical target, state/context, committed actions, seed stream, suffix policy and completion'),
    barriers=dict(per_attempt='complete command/process family exited, durable outcome/failure and cleanup evidence',
        per_node='all child groups exited -> compute_exited receipt -> local occupancy restoration under that released lifecycle, including failure',
        publication='all participating shard manifests plus both required compute_exited/failure receipts; no missing shard treated as zero failures',
        joint_wave='none created. Any later joint wave requires separately frozen shared barrier; both nodes retain whole8 reservation until both compute_exited, including early/failed children',
        independent_waves='only if releases explicitly define truly independent waves; publication still waits for assigned parents on both hosts',
        B_current='no assumption B live compute-ready; existing B CPU preparation unchanged'),
    public_shard_schema='interface_v1 shard_manifest with assignment_rule explicit_analysis_manifest only after concrete identities freeze'))

# Integer example is a quotation, not source IDs or resource authorization.
N=50*(8+2);cuts=[5,55]*(N//2);Q=2;RQ=2;RG=2;Tmax=300
Qbranches=N*Q*RQ;Gbranches=N*2*RG;branches=Qbranches+Gbranches;attempts=N+branches
source_steps=N*Tmax;prefix_steps=(Q*RQ+2*RG)*sum(cuts)
Q_suffix=Q*RQ*sum(Tmax-c for c in cuts);G_suffix=2*RG*sum(Tmax-c for c in cuts)
steps=source_steps+prefix_steps+Q_suffix+G_suffix
prefix_samples=(Q*RQ+2*RG)*sum(math.ceil(c/10) for c in cuts)
source_samples=N*math.ceil(Tmax/10);entry_samples=N*Q
Q_suffix_samples=Q*RQ*sum(math.ceil(max(0,Tmax-c-10)/10) for c in cuts)
G_suffix_samples=2*RG*sum(math.ceil(max(0,Tmax-c-5)/10) for c in cuts)
samples=source_samples+entry_samples+prefix_samples+Q_suffix_samples+G_suffix_samples
observations=steps+attempts;feature_frames=observations+frames
rgb_bytes=observations*480*480*3;core_bytes=feature_frames*4096*4
demo_token_bytes=frames*256*2048*4;new_all_token_bytes=observations*256*2048*4
storage_parts=dict(new_RGB_uncompressed=rgb_bytes,core_features_float32=core_bytes,
    selected_normal_demo_token_cache_float32=demo_token_bytes,
    raw_trajectory_metadata_reservation=steps*4096,
    raw50_noise_and_event_reservation_per_sample=samples*8192,
    snapshot_reference_reservation_1MiB_per_cut=N*1024**2,
    task_language_cache_float32=50*2048*4)
put('RESOURCE_AND_STORAGE_QUOTE.json',dict(schema='parameterized-common-pool-quote/1',status='QUOTATION_NOT_AUTHORIZATION',
    quantity_basis='all planned cuts legal, no early exit, all suffixes reach300; real counts can be lower without refill',
    parameters=dict(MT50_tasks=50,H=10,Q_commitment=10,G0_commitment=5,flow_steps_per_full_sample=10,
        frozen_train_per_task=None,frozen_dev_per_task=None,frozen_cut_list=None,frozen_candidate_count=None,frozen_repeat_count=None,
        frozen_collection_seeds=None,frozen_physical_attempt_budget=None,
        recommended=dict(train_per_task=8,dev_per_task=2,parent_count=N,cuts_per_parent=1,cut_values=[5,55],Q_candidates=Q,Q_repeats=RQ,G0_repeats=RG),
        measured_new_success_or_legal_cut_rate=None,worker_count=None),
    parametric_formulas=dict(
        parents='P=50*(n_train+n_dev)',potential_cuts='C=P*k; legal subset L<=C, no replacement',
        physical_branch_attempts='sum_over_legal_cuts(K_Q*R_Q+2*R_G0); normal full source charged separately',
        attempts_cold_independent_replay='P + branch_attempts + separately released validation/technical attempts',
        env_controls='P*T + sum_branches(prefix_replay_controls(c)+suffix_controls(T-c)); snapshot mode still charges suffix and capture/restore separately',
        VLA='P*ceil(T/10)+sum_cuts(K_generated)+sum_branches(prefix_sampling(c)+ceil(max(0,T-c-commitment)/10))',
        policy_replay_prefix_sampling='ceil(c/10); early partial prefix includes its generating sample',
        recorded_action_replay_prefix_sampling='0 only if later implementation actually consumes saved plans/actions/RNG states; no implied free env/feature replay',
        flow='10*actual entered full samples as a planned upper bound; failed partial calls logged with actual flow entered/returned',
        rendering='one initial observation + one per actual control + any extra restore validation renders',
        feature_extraction='one explicit forward per unique (observation SHA, encoder signature); alias reuse must be proven; quote assumes no dedup discount',
        Q_D_G0='native-only candidate collection requires0; optional monitor point with existing2 members adds2 D +2 G0 forwards; not selected',
        additional_Q_candidate='per legal cut +1 VLA/+10flow generation and R_Q fresh physical suffix attempts with init/prefix/full continuation',
        additional_repeat='no generation repeat if raw plan fixed; +K_Q or+2 physical suffix attempts per cut for Q/G0 respectively',
        wallclock='sum actual service intervals by worker plus IO/init/cleanup; cannot multiply/divide old multi-host wall times into a speedup',
        failures='entered operations and partial physical steps survive any exception; unentered work remains0; missing terminal event is unknown completion, not refunded compute'),
    worked_upper_example=dict(
        source_attempts=N,potential_cuts=N,Q_suffix_attempts=Qbranches,G0_suffix_attempts=Gbranches,
        physical_attempts=attempts,terminal_label_records_upper=branches,normal_outcome_records_upper=N,
        controls=dict(source=source_steps,prefix_replay=prefix_steps,Q_suffix_including_commitment=Q_suffix,
            G0_suffix_including_commitment=G_suffix,total=steps,Q_committed=N*Q*RQ*10,G0_committed=N*2*RG*5),
        VLA_samples=dict(source=source_samples,candidate_generation=entry_samples,prefix_policy_replay=prefix_samples,
            Q_suffix_native10=Q_suffix_samples,G0_suffix_native10=G_suffix_samples,total=samples,
            recorded_action_replay_alternative=samples-prefix_samples),
        flow_forward_upper=samples*10,noise_draws_upper=samples,prefix_transformer_upper=samples,
        action_expert_forward_upper=samples*10,preprocessor_tokenizer_postprocessor_sample_calls_each=samples,
        render_observation_readbacks=observations,
        extra_shared_visual_feature_forwards=feature_frames,
        policy_visual_and_language_forwards_each_upper=samples,
        total_visual_forward_upper=samples+feature_frames,
        extra_task_language_forwards_upper=50,extra_task_tokenizer_calls_upper=50,
        image_preprocess_upper=samples+feature_frames,
        context_build_upper=observations,feature_transform_fit_calls=None,
        Q_ensemble_or_member_forward=0,D_forward=0,G0_forward=0,model_backward=0,action_gradients=0,training_updates=0,
        optional_velocity_guided_calls=0,independent_final_guided_Q=None),
    initialization_and_restore=dict(
        cold_reference='accepted shelf-place entry: MT1 makes50 tasks/resets, wrapper1 plus diagnostic1;2 env instances/52 native resets/104 reset_model/26000 init substeps per fresh attempt',
        evidence=ref(B/'manifests/A_CAUSAL_C10_PREFLIGHT_V2_FINAL_ACCEPTANCE.json'),
        source_config=ref(B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1/config/CONFIG.json'),
        shelf_like_cold_scenario=dict(env_instances=attempts*2,MT1_tasksets=attempts,MT1_resets=attempts*50,
            wrapper_resets=attempts,explicit_resets=attempts,native_resets=attempts*52,reset_model=attempts*104,init_physics_substeps=attempts*26000),
        universal_MT50_caps=None,
        missing_reason='reset_model loops/task-specific initialization and observation side effects not validated for other49 tasks; these reference multipliers are not universal upper bounds',
        control_physics='400/30 scheduler has13/14 substeps; conservative14*controls after validating same wrapper; no blanket13*controls',
        control_physics_14_per_step_scenario=14*steps,
        verified_snapshot_restores=0,proposed_snapshot_restore_calls='one per suffix attempt, only after validated save/restore; capture and validation render/forward charged',
        cached_MT1_or_resident_env_savings='not credited; requires new implementation and task-specific checks',
        model_loads='W_worker launches for a resident design; up to physical_attempts with one cold process per attempt; exact release must choose finite W',
        collector_models='pi05 + matching encoder only proposed; D/G0/Q load0 for native-only collection. Existing fixed C10 driver loads9 models/child and is not an as-is collector.',
        graphics_identity='per new graphics worker/instance: one validated mapping/context lifecycle; existing8-device caps are reference only and must be bound in future release'),
    minimal_collector_validation_quote=dict(
        status='NOT_IMPLEMENTED_NOT_RELEASED',purpose='new collector field/commitment/replay/exit validation, not an old preflight rerun',
        source='one analysis-selected new development parent; task/seed/release pending, shelf-place only as cost reference',
        physical_attempts_max=5,source_reference_attempts=1,Q_replay_attempts=2,G0_target5_attempts=2,
        controls_per_attempt=[16,16,16,11,11],controls_total_max=70,
        candidate_raw50_generations=2,VLA_samples_max=12,flow_max=120,render_max=75,
        explicit_visual_feature_extraction_max=75,extra_language_feature_forward_max=1,
        policy_visual_language_forwards_each_max=12,Q_D_G0_calls=0,gradients=0,training=0,
        native_resets_cold_shelf_scenario=260,reset_model_cold_shelf_scenario=520,init_substeps_cold_shelf_scenario=130000,
        negative_outcome_labels_claimed=0,full_training_rollouts=0,
        CPU_fixtures_required_later=['missing next/terminal masks','complete success vs declared complete failure vs cap censor vs technical error',
            'raw alias and target5/target10 no-alias','parent ownership/idempotent publication/conflict reject','cleanup and failure barrier'],
        runtime_acceptance='all finite stage/field/identity checks; two Q replays do not establish all50 hidden-state equivalence; early end retains evidence, no retry',
        timeout_proposal='per child1800s +30s grace; handoff300 separate; loader/hash/lock/drain/restoration observation scoped explicitly in future release',
        additional_MT50_gate='before production, price at most one finite init/reset/step observation check per unvalidated task;49 task-specific init caps currently unknown, cannot execute or release production from this quote'),
    storage=dict(
        compression_savings_assumed=0,shared_prefix_or_image_dedup_savings_assumed=0,
        existing_demo_bytes_reference=45864144489,existing_demo_data_copy_bytes=0,
        RGB_shape=[480,480,3],RGB_dtype='uint8',per_new_observation_RGB_bytes=691200,
        token_shape=[256,2048],token_dtype_quote='float32',token_bytes_per_frame=2097152,
        selected_token_scope='normal demonstrations only; common rollout token tensors may feed aggregates without being persisted; all methods access original RGB',
        selected_storage_parts_bytes=storage_parts,total_selected_output_bytes=sum(storage_parts.values()),
        optional_all_new_rollout_token_cache_bytes=new_all_token_bytes,optional_all_new_rollout_tokens_selected=False,
        hypothetical_fp16_demo_token_bytes=demo_token_bytes//2,hypothetical_fp16_status='not selected; would need numeric/dtype compatibility review',
        peak=dict(retained='sum selected outputs + failure/quarantine reservations; no automatic deletion',
            writer_buffer_2_workers_one301frame_episode_RGB_each=2*301*691200,
            feature_batch='batch b: b*token_bytes plus input/working tensors; reserve/load peaks need finite implementation quote',
            optional_per_host_pi05_weight_cache_bytes=9354084596,host_caches_count_example=2,
            extra_weight_cache_bytes_example=2*9354084596,
            model_VRAM_estimate_per_worker_bytes=24*1024**3,model_host_RAM_reservation_estimate_per_worker_bytes=64*1024**3,
            estimates_not_measured_caps=True),
        project_quota_bytes=None,project_remaining_bytes=None,filesystem_free_bytes=None,
        quota_reason='not queried; pool free bytes would not establish project quota. Analysis must reserve project capacity before any data release.',
        all_created_artifacts_retained=True,delete_release=None),
    decisions_needed=['actual n_train/n_dev, cut schedule, K and repeats; quote is not frozen',
        'complete terminal target/horizon rules and negative-label eligibility',
        'restoration/replay proof required for gain/pair/G0 pairing; task-specific cold-init caps',
        'component train/init recipe, exact feature cache signature/dtype and storage reservation',
        'A/B explicit shards and release/wave/barrier identities'],
    wall_time_seconds_estimate=None,wall_time_missing_reason='no collector runtime and no authorized benchmark; counts/bytes provided, latency must not be fabricated'))

put('INPUT_MANIFEST.json',dict(task_id=T,files=list(INPUTS.values()),source_bytes_only=True,
    historical_trajectory_or_image_payloads_opened=0,weight_payloads_opened=0,held_trajectory_payloads_opened=0,
    selection='explicit contract/manifest/report/config/data-audit metadata and authorized1300-row historical train/development access index only'))
put('CPU_DESIGN_CHECKS.json',dict(status='PASS',environment_rows=len(coverage),environment_ids_unique=50,
    per_environment_demos_equal50=all(x['normal_demonstrations']['episodes']==50 for x in coverage),
    demo_frames=frames,demo_episodes=2500,language_indices=49,legacy_index_segments=len(historical),
    historical_held_parents_included=splits['historical_revealed_held_included'],
    demo_t_to_tplus10_index_upper_bound=demo_pair_upper,eligible_pairs_actual=None,
    proposed_parents_equal_each_task=True,actual_seed_lists_absent=True,actual_shards_absent=True,
    example_physical_attempts=attempts,example_controls=steps,example_full_samples=samples,
    quote_vs_authorization_separate=True,B_methods_and_view_contract_SHA_verified=True,public_v1_unchanged=True,
    compute_or_collector_implementation=False))
print(json.dumps(dict(status='DESIGN_WRITTEN',environments=len(coverage),attempts_quote=attempts,
    samples_quote=samples,selected_bytes=sum(storage_parts.values()),input_files=len(INPUTS)),ensure_ascii=False))
