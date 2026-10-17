"""CPU documents, metadata tables and integer arithmetic only; no collector."""
from pathlib import Path
import ast
import copy
import datetime
from fractions import Fraction
import hashlib
import json
from collections import Counter

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
B = ROOT / 'Corrector/sim_command/20260919'
TASK = 'A11_COMMON_POOL_REVISION_CPU_V2'
P = B / 'results/A' / TASK
W = B / 'work/A' / (TASK + '_r1')
OLD = B / 'results/A/A11_COMMON_POOL_DESIGN_CPU_V1'
C10 = B / 'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1'
SITE = ROOT / '.miniforge3/envs/lerobot/lib/python3.12/site-packages'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
INPUTS = {}
CHECKS = []

def ref(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    return dict(path=str(path), realpath=str(path.resolve()),
                sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))

def read(path):
    path = Path(path)
    INPUTS[str(path.absolute())] = ref(path)
    return path.read_text()

def load(path):
    return json.loads(read(path))

def write(name, data):
    with (P / name).open('x') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

def check(name, ok, evidence):
    CHECKS.append(dict(check=name, passed=bool(ok), evidence=evidence))
    if not ok:
        raise AssertionError(name)

ack = load(B / f'receipts/A/{TASK}_ACK.json')
release = load(B / 'releases/P00_COMMON_POOL_REVISION_CPU_V2.json')
for path in sorted((W / 'authorization_snapshot').iterdir()):
    read(path)
review = load(B / 'manifests/COMMON_POOL_DESIGN_CPU_V1_REVIEW.json')
read(B / 'contracts/COMMON_POOL_PROTOCOL_DECISIONS_V2.md')
read(B / 'tasks/A11_COMMON_POOL_REVISION_CPU_V2.md')
algorithm = read(ROOT / 'Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md')
old_cov = load(OLD / 'POOL_COVERAGE_AND_GAPS.json')
old_draft = load(OLD / 'COMMON_POOL_DRAFT.json')
old_quote = load(OLD / 'RESOURCE_AND_STORAGE_QUOTE.json')
read(OLD / 'COLLECTION_AND_REPLAY_PROTOCOL.md')
load(OLD / 'COLLECTION_SHARDS_DRAFT.json')
old_manifest = load(OLD / 'EVIDENCE_MANIFEST.json')
old_refs = {x['path']: x for x in old_manifest['files']}
for name in ('POOL_COVERAGE_AND_GAPS.json', 'COMMON_POOL_DRAFT.json',
             'RESOURCE_AND_STORAGE_QUOTE.json', 'COLLECTION_SHARDS_DRAFT.json',
             'COLLECTION_AND_REPLAY_PROTOCOL.md'):
    current = ref(OLD / name)
    check('old_design_input_unchanged:' + name,
          current['sha256'] == old_refs[current['path']]['sha256'], current)
ext = load(C10 / 'EXTERNAL_SOURCE_MANIFEST.json')
ext_refs = {x['path']: x for x in ext['files']}
config = load(C10 / 'config/CONFIG.json')
load(B / 'manifests/A_CAUSAL_C10_PREFLIGHT_V2_FINAL_ACCEPTANCE.json')
load(B / 'manifests/PUBLIC_INTERFACE_V1.json')
fs_metadata = load(W / 'FILESYSTEM_METADATA.json')
for x in old_draft['B_frozen_contracts'].values():
    if isinstance(x, dict) and 'path' in x and str(x['path']).endswith('.json'):
        actual = ref(x['path'])
        if 'sha256' in x:
            check('B_input_identity:' + Path(x['path']).name,
                  actual['sha256'] == x['sha256'], actual)
        read(x['path'])

source_specs = {
    'wrapper': (C10 / 'code/vendor_vla/src/lerobot/envs/metaworld.py', [(157,169),(171,199),(202,260)]),
    'sampler': (C10 / 'code/vendor_vla/src/lerobot/policies/pi05/modeling_pi05.py', [(640,674),(1119,1124),(1142,1206)]),
    'features': (C10 / 'code/feature_path.py', [(97,101),(123,147),(150,165)]),
    'engine': (C10 / 'code/runtime_engine.py', [(54,87),(174,200)]),
    'queue': (C10 / 'code/causal_contract.py', [(19,58)]),
    'initialization_meter': (C10 / 'code/native/initialization.py', [(169,187)]),
    'mw_base': (SITE / 'metaworld/sawyer_xyz_env.py', [(87,131),(275,311),(513,527),(580,641),(664,718)]),
    'shelf': (SITE / 'metaworld/envs/sawyer_shelf_place_v3.py', [(118,153)]),
    'gym_mujoco': (SITE / 'gymnasium/envs/mujoco/mujoco_env.py', [(118,147)]),
    'mw_tasks': (SITE / 'metaworld/__init__.py', [(97,111),(131,169),(185,207)]),
    'env_dict': (SITE / 'metaworld/env_dict.py', [(26,77)]),
    'env_imports': (SITE / 'metaworld/envs/__init__.py', []),
    'mj_state': (SITE / 'mujoco/include/mujoco/mjdata.h', [(27,52),(244,279)]),
    'mj_api': (SITE / 'mujoco/include/mujoco/mujoco.h', [(205,237),(480,494)]),
    'mj_num': (SITE / 'mujoco/include/mujoco/mjtnum.h', [(21,30)]),
}
sources = {}
source_text = {}
for key, (path, ranges) in source_specs.items():
    text = read(path)
    source_text[key] = text
    lines = text.splitlines()
    expected = ext_refs.get(str(path))
    identity = ref(path)
    if expected:
        check('external_source_lineage:' + key,
              identity['sha256'] == expected['sha256'], identity)
    sources[key] = dict(identity=identity, ranges=[
        dict(first_line=a, last_line=z, text='\n'.join(lines[a-1:z]))
        for a,z in ranges], reviewed='targeted static text/AST only',
        inherited_SHA_matches=identity['sha256'] == expected['sha256'] if expected else None)
versions = {}
for name in ('metaworld', 'mujoco', 'gymnasium'):
    paths = list(SITE.glob(name + '-*.dist-info/METADATA'))
    check('single_package_metadata:' + name, len(paths)==1, [str(x) for x in paths])
    text = read(paths[0])
    versions[name] = dict(metadata=ref(paths[0]),
        version=next(line[9:] for line in text.splitlines() if line.startswith('Version: ')))
versions['torch_numpy_lerobot'] = dict(value=config['runtime_packages'],
    provenance='accepted C10 config only; no import or new runtime check')
write('STATIC_SOURCE_EVIDENCE.json', dict(task_id=TASK, status='STATIC_ONLY',
    versions=versions, sources=sources,
    findings=[
        'get_env_state returns only qpos/qvel; set_env_state delegates to incomplete Gym set_state.',
        '_get_obs updates _prev_obs; restore verification must not call it casually.',
        'MuJoCo3.6 integration state includes HISTORY and PLUGIN as well as time/physics/user/warmstart.',
        'mj_getState does not serialize mutable mjModel or Python task/wrapper/policy/RNG state.',
        'shelf reset mutates model.body(shelf).pos and task goal/reward caches.',
        'native reset(seed=...) documents ignored seed; global NumPy/env generators must be bound explicitly.',
        'Existing C10 driver is H20 and cut5/16-step specific, not an H10 collector.',
        'Frozen sampler encodes all three images, even two false-mask padded images.',
        'Explicit feature path preprocesses each real observation and creates padding, but encodes only its real image.',
        'No full-state roundtrip, restoration, model or environment execution performed.']))

# Resolve all 50 class-to-source identities using TWO small mapping modules.
# Do not open the other 49 task implementations or hash their payloads.
env_tree = ast.parse(source_text['env_dict'])
mapping_node = next(n.value for n in env_tree.body if isinstance(n, ast.Assign)
    and any(isinstance(t,ast.Name) and t.id=='ENV_CLS_MAP' for t in n.targets))
class_by_task = {ast.literal_eval(k): v.attr for k,v in zip(mapping_node.keys,mapping_node.values)}
imports = {}
for node in ast.parse(source_text['env_imports']).body:
    if isinstance(node, ast.ImportFrom):
        for alias in node.names:
            imports[alias.asname or alias.name] = node.module
task_init = []
cov = copy.deepcopy(old_cov)
cov.update(schema='common-pool-coverage-design/2', task_id=TASK,
    status='CPU_DESIGN_REVISED_NOT_COLLECTION_READY', no_new_inventory=True,
    inherited_coverage=ref(OLD / 'POOL_COVERAGE_AND_GAPS.json'),
    future_missing=[
        'full-state implementation/first planned parent proof and task-specific initialization bounds',
        'actual parent IDs/seeds/explicit shards and independent finite releases',
        'same-source feature/normalizer and B sidecar/eligibility adapter acceptance',
        'project quota reservation and finite storage bounds',
        'eligible sample count and component training sufficiency remain unknown'])
for row in cov['rows']:
    task = row['environment_task']
    cls = class_by_task[task]
    source_path = str(SITE / (imports[cls].replace('.', '/') + '.py'))
    inherited = ext_refs[source_path]
    shelf = task == 'shelf-place-v3'
    row['new_pool'] = dict(status='design_only_not_released', H=10,
        design_train_parents=8, design_development_parents=2,
        design_cuts=[5,55], real_parent_IDs=None, real_seeds=None,
        actual_legal_cuts=None, eligible_paired_sources=None,
        current_collection_cap=0, guarantee_of_training_sufficiency=False)
    row['method_eligibility'] = dict(
        LVM='normal contiguous t..t+10 with actual tokens and original action_t/normalizer identity; terminal flags not required',
        D5='true contiguous5 arrived observations and actual executed commands; cannot inherit LVM action relaxation',
        GAF='actual action window and complete compatible target; terminal flags/horizon not relaxed',
        Q_gain_pair_G0='full_state_verified and BOTH planned aligned complete repeats; currently unproven')
    init = dict(task=task, environment_id=row['environment_id'], class_name=cls,
        task_source_identity_inherited=inherited,
        mapping_evidence=[sources['env_dict']['identity'],sources['env_imports']['identity']],
        common_static_basis=['MT1 _N_GOALS=50 normal construction reset call sites',
            'wrapper constructs second env, one wrapper reset, one explicit reset for reference path',
            'task-specific reset_model/RNG rejection loops/extra physics may differ'],
        current_task_source_read=shelf,
        verified_all_initialization_caps=None, full_state_roundtrip_passed=False,
        status='shelf accepted prior path reference only' if shelf else 'task-specific initialization/restore UNKNOWN',
        shelf_reference_per_attempt=dict(environment_instances=2,native_resets=52,
            reset_model=104,initialization_physics_substeps=26000) if shelf else None,
        remaining=['task-specific reset_model calls and physics/forward/render side effects',
            'task Python/model mutation closure and seed/RNG behavior',
            'loop termination/cap guard and full-state restore proof'],
        next_gate='static bounded task adapter review then checks in the first already planned parent for that task; not 50 separate GPU experiments')
    task_init.append(init)
    row['initialization_review_status'] = init['status']
write('POOL_COVERAGE_AND_GAPS.json',cov)
write('TASK_INITIALIZATION_GAPS.json',dict(task_id=TASK,rows=task_init,
    shelf_reference_not_universal=True, other49_caps_unknown=True,
    live_probes=0, independent_task_experiments_proposed=0))

restore_groups = [
 dict(id='identity', fields=['environment task/class/version/source/XML/assets identity',
    'task payload bytes and decoded goal/rand_vec identity','model dimensions/precision/compile options',
    'policy/checkpoint/config/normalizer/PCA/encoder preprocessing signatures',
    'camera/flip/image shape; wrapper/action semantics/clock implementation'],
    serialization='versioned canonical metadata + immutable raw-byte SHA references; no model weights rehash now',
    comparison='exact identity equality before any intervention; version mismatch rejects',
    evidence=['wrapper','mw_tasks','env_dict','mj_num'],static='interfaces identified',runtime='unverified'),
 dict(id='mjData_integration',fields=['time','qpos[nq]','qvel[nv]','act[na]',
    'history[nhistory]','qacc_warmstart[nv]','ctrl[nu]','qfrc_applied[nv]',
    'xfrc_applied[nbody,6]','eq_active[neq]','mocap_pos[nmocap,3]',
    'mocap_quat[nmocap,4]','userdata[nuserdata]','plugin_state[npluginstate]'],
    serialization='mj_stateSize/mj_getState with installed mjSTATE_INTEGRATION; preserve native dtype/shape/endianness and raw bytes. Persist signature and model dimensions, no JSON float roundtrip.',
    comparison='proposed exact dtype/shape/bytes at same canonical cut boundary, including signed zero; nonfinite/missing rejects. No invented positive tolerance.',
    evidence=['mj_state','mj_api','mj_num'],static='state signature/header verified',runtime='size/precision/roundtrip/plugin closure unverified'),
 dict(id='mjModel_mutations',fields=['body_pos including shelf body','site_pos/goal and runtime goal-site data',
    'eq_data/weld reset state','cam_pos[corner2]','opt.timestep/integrator/solver/options',
    'all other mutable dynamics fields (geom/body/actuator/contact parameters) affecting transition',
    'vis offscreen settings and visual/material fields affecting observation'],
    serialization='future model snapshot via versioned MJB/mj_saveModel or exhaustive typed mutation manifest over immutable baseline; MJB is a proposal, not a proved complete runtime adapter',
    comparison='exact baseline identities and all declared mutable fields; undeclared runtime mutation blocks eligibility',
    evidence=['mj_api','mw_base','shelf','wrapper','gym_mujoco'],static='some actual mutations found; complete per-task closure missing',runtime='unverified'),
 dict(id='task_python',fields=['_target_pos','_last_rand_vec','_freeze_rand_vec','seeded_rand_vec',
    '_set_task_called','_partially_observable','curr_path_length','max_path_length',
    '_prev_obs','_last_stable_obs','_did_see_sim_exception','init_qpos','init_qvel',
    'hand_init_pos','init_tcp','obj_init_pos','obj_init_angle','init_config',
    'shelf liftThresh/objHeight/heightTarget/maxPlacingDist',
    'all other task-specific reward/goal/transition caches'],
    serialization='typed allowlist arrays/raw scalars + explicit nulls and shapes; no blind __dict__/pickle restore of native/render handles',
    comparison='exact serialized bytes/scalars; unknown stateful field blocks; simulator exception never treated as absorbing failure',
    evidence=['mw_base','shelf'],static='base/shelf examples bound; other49 class closure pending',runtime='unverified'),
 dict(id='rng',fields=['Python random state','NumPy legacy global RandomState',
    'env.np_random.bit_generator class/state','action/observation/goal space RNGs',
    'all explicit local generators','Torch CPU and each USED CUDA generator',
    'source continuation/candidate-generation/local-probe/Q_C10/G0_C5 namespaces',
    'repeat and suffix decision ordinals, saved raw noise SHA'],
    serialization='future typed state/byte blobs with RNG engine, package/version and stream IDs; no seeds generated now',
    comparison='exact source-state identity at cut before intentional prescribed branch-stream selection; branch injection recorded separately. Candidate generation may not advance continuation stream.',
    evidence=['mw_base','mw_tasks','engine'],static='seed reset caveat and current fork path found',runtime='unverified'),
 dict(id='clocks_wrappers_flags',fields=['parent_absolute_control_step','branch_local_step',
    'curr_path_length/_elapsed_steps if wrapper present','frame_skip',
    'physics_time and integer phase (absolute_step*400)%30',
    'physics/control rates and action_scale','success_so_far/first_success_step',
    'terminated/truncated and TimeLimit provenance','max_episode_steps'],
    serialization='integers/booleans exact; floating physical time stored losslessly; wrapper stack explicit',
    comparison='exact absolute clock/phase; prescribed substeps=floor((t+1)*400/30)-floor(t*400/30), not restarted at suffix zero. Positive physical-state tolerance is not licensed by timing audit tolerance.',
    evidence=['engine','initialization_meter','wrapper','mw_base'],static='13/14 scheduler identified',runtime='new H10 adapter unimplemented'),
 dict(id='policy_queue_history',fields=['controller.raw50/remaining rows/age/plan_id/horizon',
    'policy._action_queue','policy._queues[ACTION]','RTC/cache enabled flags (must bind disabled or fully serialize)',
    'causal last5 frame features/proprio and mask','last4 actual executed actions',
    'language embedding and preprocessing/PCA identities','raw plan/noise/postprocess identities'],
    serialization='float32 raw bytes plus exact queue ordering/age and absolute timestamps; copy full50 including unexecuted tail',
    comparison='all pre-intervention queues/history bitwise equal; old queue age5/remaining5 for nativeH10. Candidate-specific change only after full verification.',
    evidence=['queue','sampler','engine','features'],static='old H20 fields identified; H10 collection implementation still absent',runtime='unverified'),
 dict(id='derived_and_external_state',fields=['derived contact/kinematic/reward caches',
    'plugin_data/external plugin state and callbacks, if present',
    'render context/viewer camera state','unclassified Python attributes/native state'],
    serialization='classify each as captured, deterministically recomputed from bound fields, immutable, or irrelevant with cited proof; unknown cannot be omitted',
    comparison='derived observation bytes are secondary checks, never substitute full-state equality; no tolerance assigned to unknown fields. Native handles not blindly deserialized.',
    evidence=['mj_state','mj_api','mw_base','gym_mujoco'],static='API does not prove complete external/plugin/render closure',runtime='unknown blocks pairing'),
]
write('RESTORE_FIELD_CONTRACT.json',dict(task_id=TASK,status='DESIGN_NOT_ROUNDTRIP_PROOF',
    required_comparability='full_state_verified',passed_real_roundtrips=0,
    groups=restore_groups,
    canonical_boundary='after the real cut observation and its history update, before any candidate generation/intervention; snapshot reference retained through all repeats',
    verification_order=[
        'Bind immutable task/model/policy/feature/config/source identities and future field schema before outcomes.',
        'Capture physical integration, mutable model, Python/task/wrapper, RNG and queues/history at the canonical cut; preserve bytes and SHA.',
        'For cold replay, reproduce original prefix with fixed sources/noise and compare planned prefix transitions/state; for snapshot path, restore model before data, then task/wrapper/RNG/queue/history.',
        'If restoring data requires mj_forward/derived rebuild, price it explicitly; verify what it changes, restore warmstart/state as needed under a reviewed sequence. Do not call _get_obs to check state.',
        'Compare all captured transition-relevant fields and canonical context before intervention. Unknown/mismatch => pairing false, no threshold relaxation.',
        'Record full_state_verified only from actual complete evidence. Then select the predeclared repeat suffix stream, preserving matched identity across arms.',
        'Use already planned old/normal transitions to check boundary behavior where applicable; candidate outcomes cannot select tolerances or decide equivalence.',
        'On any missing evidence/technical failure retain receipts and masks; no retry/replacement. First planned full parent outcome gate precedes wider collection.'
    ],
    tolerance_policy=dict(raw_arrays='bitwise proposed; no current real verification',
        identity_and_integers='exact',physical_tolerance=None,
        physical_tolerance_reason='no demonstrated invariant supports a nonzero tolerance; analysis must approve any change before data/outcomes',
        action_projection_numeric_tolerance=1e-6,
        action_tolerance_is_not_restore_tolerance=True),
    first_planned_parent_gate='Integrate serializer/cold-replay comparison into already planned first parent per newly admitted task adapter; no added50 standalone experiments. Unknown task init caps block its release.',
    observables_only_admits_gain_pair_G0=False, privileged_state_is_model_input=False,
    new_restore_implementation=False))

# Synthetic IDs only: no real seed, source, shard or claim.
synthetic_parents=[]
cross=Counter()
for row in cov['rows']:
    t=row['environment_id']
    for split,n in [('train',8),('development',2)]:
        for i in range(n):
            cut=5 if i%2==0 else 55
            owner=('A','B')[(i//2)%2] if split=='train' else ('A','B')[(t+i%2)%2]
            pid=f'SYNTHETIC_ONLY_T{t:02d}_{split}_{i}'
            synthetic_parents.append(dict(synthetic=True,parent_id=pid,task_ordinal=t,
                split=split,parent_ordinal=i,cut=cut,owner_symbol=owner,
                real_source_id=None,seed=None,runnable=False))
            cross[(t,split,cut,owner)]+=1
cross_rows=[dict(task_ordinal=t,split=s,cut=c,owner_symbol=h,count=cross[(t,s,c,h)])
    for t in range(50) for s in ('train','development') for c in (5,55) for h in ('A','B')]
check('synthetic_500_parent_unique',len(synthetic_parents)==500 and
    len({x['parent_id'] for x in synthetic_parents})==500,dict(count=len(synthetic_parents)))
check('train_task_split_cut_host_balance',all(cross[(t,'train',c,h)]==2
    for t in range(50) for c in (5,55) for h in ('A','B')), '2 per task/cut/host')
check('development_cross_task_cut_host_balance',all(sum(cross[(t,'development',c,h)]
    for t in range(50))==25 for c in (5,55) for h in ('A','B')),'25 per host/cut across50')
check('no_real_seed_or_runnable_shard',all(x['seed'] is None and x['real_source_id'] is None
    and not x['runnable'] for x in synthetic_parents),'all500 synthetic only')
check('parent_not_split',len({x['parent_id']:x['owner_symbol'] for x in synthetic_parents})==500,
    'all candidate/repeat/features inherit one parent owner')
write('SYNTHETIC_SHARD_CROSSTAB.json',dict(task_id=TASK,synthetic=True,
    real_shard=False, rows=cross_rows, synthetic_parent_design_rows=synthetic_parents,
    totals=dict(parents=500,train=400,development=100,A=250,B=250,
        train_per_host=200,development_per_host=50,cut5=250,cut55=250)))
write('COLLECTION_SHARDS_DRAFT.json',dict(schema='collection-shards-design/2',task_id=TASK,
    status='SYNTHETIC_DESIGN_NOT_EXECUTABLE',actual_A11_B11_collection='planned',
    real_release=None,global_manifest_SHA=None,real_seed_list=None,sources=[],
    train_owner_rule='owner=(A,B)[floor(parent_ordinal/2)%2]; cut=(5,55)[parent_ordinal%2]',
    dev_owner_rule='owner=(A,B)[(task_ordinal+cut_ordinal)%2]; cut=(5,55)[parent_ordinal%2]',
    planned_distribution=dict(tasks=50,train_per_task=8,development_per_task=2),
    crosscheck='SYNTHETIC_SHARD_CROSSTAB.json',
    ownership='parent+all its Q/G0 candidates/repeats/normal/features indivisible; never split by method',
    future_identity_fields=['campaign','release_revision','protocol_SHA','parent_manifest_SHA',
        'owner_host','task_ID','split','parent_ordinal','absolute_cut','repeat_ID',
        'target_namespace','policy/feature_signature','raw_C10_or_C5_SHA','physical_attempt_ID'],
    idempotency=['future explicit frozen owner list only; task/seed already owned cannot be claimed elsewhere',
        'immutable attempt start and complete evidence keyed identities; completed units referenced, not rerun',
        'failed/partial units retained and never silently retried or taken over on heartbeat expiry',
        'logical aliases reference one physical attempt only after predeclared equivalence; physical work counted once',
        'no actual locks/claims/leases/shards produced by this CPU task'],
    barriers=dict(
        joint_compute_exit='local compute_exited is fact only. Keep local reservation and all8 holders stopped until all released participants have exited every process group, including failure cleanup.',
        joint_release='analysis/released coordinator issues global-all-exited evidence; only then each node releases its reservation. Missing node evidence does not authorize local early holder restart.',
        single_node='single-node wave may release after its own whole group exits under its released lifecycle',
        data_publication='separate immutable-data barrier: every admitted shard has exit, manifest/SHA/eligibility audit and analysis approval; compute barrier alone does not publish data',
        fail_closed='coordination implementation and bounded failure/drain protocol not built or authorized now'),
    B_current_task_unchanged=True))

# Metadata-only label examples. Tokens below are symbolic raw-byte identities,
# not computed actions, raw plans, seeds, candidate generators or projections.
arms=['Q/a0','Q/local_plus','Q/local_minus','G0/old','G0/fresh0','G0/fresh1','G0/fresh2']
base_outcomes={'Q/a0':[0,1],'Q/local_plus':[1,1],'Q/local_minus':[0,0],
    'G0/old':[0,0],'G0/fresh0':[1,0],'G0/fresh1':[0,1],'G0/fresh2':[1,1]}
def synthetic_case(name, missing=None, full=True, alias=False):
    outcomes=copy.deepcopy(base_outcomes)
    if alias:
        outcomes['Q/local_plus']=outcomes['Q/a0'][:]
        outcomes['Q/local_minus']=outcomes['Q/a0'][:]
    if missing:
        outcomes[missing[0]][missing[1]]=None
    rows=[]
    for arm in arms:
        target='Q_C10' if arm.startswith('Q/') else 'G0_C5'
        for repeat in (0,1):
            y=outcomes[arm][repeat]
            rows.append(dict(synthetic=True,logical_arm=arm,repeat_id=repeat,
                physical_attempt_id=f'SYNTHETIC_{name}_{arm.replace("/","_")}_r{repeat}',
                planned=True,entered=y is not None,completed=y is not None,
                missing=y is None,success_label=y,outcome_complete=y is not None,
                comparability='full_state_verified' if full else 'independent_replay_observable_match',
                target_namespace=target,parent_absolute_target_state=300,
                suffix_stream_symbol=f'SYNTHETIC_PARENT/cut5/{target}/r{repeat}/decision_j'))
    def common(xs):
        return [r for r in (0,1) if full and all(outcomes[x][r] is not None for x in xs)]
    def pairdata(xs, nonalias=True):
        ids=common(xs);valid=ids==[0,1] and nonalias
        return dict(valid_pair_repeat_ids=ids,required_repeat_ids=[0,1],
            target_mask=valid,target=(float(sum(Fraction(outcomes[xs[0]][r]-outcomes[xs[1]][r],2)
                for r in (0,1))) if valid else None))
    gain={arm:pairdata([arm,'Q/a0'],not alias) for arm in ('Q/local_plus','Q/local_minus')}
    pair=pairdata(['Q/local_plus','Q/local_minus'],not alias)
    gids=common(['G0/old','G0/fresh0','G0/fresh1','G0/fresh2'])
    gv=gids==[0,1]
    gt=sum(Fraction(outcomes['G0/fresh'+str(k)][r],6)
        for k in range(3) for r in (0,1))-sum(Fraction(outcomes['G0/old'][r],2)
        for r in (0,1)) if gv else None
    bce={arm:dict(valid_repeat_ids=[r for r in (0,1) if outcomes[arm][r] is not None],
        effective_repeat_count=sum(y is not None for y in outcomes[arm]),
        mask=any(y is not None for y in outcomes[arm]),
        mean=float(sum(Fraction(y,1) for y in outcomes[arm] if y is not None)/
            sum(y is not None for y in outcomes[arm])) if any(y is not None for y in outcomes[arm]) else None)
        for arm in arms if arm.startswith('Q/')}
    return dict(case=name,synthetic=True,not_real_evidence=True,
        raw_C10_identity_symbols=dict(a0='R0',local_plus='R0' if alias else 'RP',
                                     local_minus='R0' if alias else 'RM'),
        pair=['Q/local_plus','Q/local_minus'],rows=rows,planned_branch_attempts=14,
        physical_branch_attempts_entered=sum(x['entered'] for x in rows),
        physical_dedup_discount=0,bce=bce,gain=gain,pair_label=pair,
        G0=dict(valid_pair_repeat_ids=gids,required_repeat_ids=[0,1],target_mask=gv,
                target=float(gt) if gt is not None else None),
        actual_cpu_candidate_generations=0,actual_cpu_projections=0)
cases=[synthetic_case('complete'),synthetic_case('zero_direction_raw_alias',alias=True),
    synthetic_case('missing_Q_minus_repeat1',missing=('Q/local_minus',1)),
    synthetic_case('missing_G0_fresh2_repeat1',missing=('G0/fresh2',1)),
    synthetic_case('observables_only',full=False)]
check('synthetic_complete_pair',cases[0]['pair_label']['target']==1.0 and
      cases[0]['G0']['target']==float(Fraction(2,3)),cases[0]['pair_label'])
check('zero_raw_alias_no_fake_pair',not cases[1]['pair_label']['target_mask'] and
      all(not x['target_mask'] for x in cases[1]['gain'].values()),
      'BCE retained once per distinct raw group; no generated direction')
check('missing_repeat_not_single_repeat_pair',cases[2]['pair_label']['valid_pair_repeat_ids']==[0]
      and not cases[2]['pair_label']['target_mask']
      and cases[2]['bce']['Q/local_minus']['effective_repeat_count']==1, cases[2]['pair_label'])
check('G0_all_four_arms_two_repeat_intersection',cases[3]['G0']['valid_pair_repeat_ids']==[0]
      and cases[3]['G0']['target'] is None,cases[3]['G0'])
check('observables_only_no_paired_labels',not cases[4]['pair_label']['target_mask']
      and not cases[4]['G0']['target_mask'], 'pointwise BCE stays separately eligible')
write('SYNTHETIC_CANDIDATE_LABELS.json',dict(task_id=TASK,synthetic=True,cases=cases,
    alias_examples=[
        dict(case='same_C10_different_raw50_tail',raw_C10_equal=True,raw50_equal=False,
             same_protocol=True,training_alias=True,extra_supervision_from_tail=False),
        dict(case='same_clamped_C10_different_raw_C10',raw_C10_equal=False,
             bounded_C10_equal=True,training_alias=False),
        dict(case='Q_a0_vs_G0_fresh0',same_generation=True,
             same_physical_outcome=False,reason='C10 versus C5 target namespace')],
    normal_reuse=dict(predeclared=True,required_same_physical_attempt=True,
        logical_roles=['normal','G0/old/repeat0'],counts_as_repeat1=False,
        status='synthetic rule only; actual equivalence unproven'),
    empty_pair_loss='0 inner term, parent retained in outer source average; no claim Full has usable pair supervision for that parent'))

def scenario(normal_reuse):
    branches_per_parent = 13 if normal_reuse else 14
    g0_per_parent = 7 if normal_reuse else 8
    totals=Counter()
    by_cut=[]
    for cut in (5,55):
        parents=250
        prefix_samples=(cut+9)//10
        q_suffix_samples=(300-cut-10+9)//10
        g_suffix_samples=(300-cut-5+9)//10
        row=dict(cut=cut,parents=parents,Q_physical_branches=parents*6,
            G0_physical_branches=parents*g0_per_parent,
            source_controls=parents*300,
            prefix_controls=parents*branches_per_parent*cut,
            Q_suffix_controls=parents*6*(300-cut),
            G0_suffix_controls=parents*g0_per_parent*(300-cut),
            source_samples=parents*30,candidate_generation_samples=parents*3,
            prefix_samples=parents*branches_per_parent*prefix_samples,
            Q_suffix_samples=parents*6*q_suffix_samples,
            G0_suffix_samples=parents*g0_per_parent*g_suffix_samples)
        by_cut.append(row)
        for key,val in row.items():
            if key not in ('cut','parents'):
                totals[key]+=val
    attempts=500*(1+branches_per_parent)
    controls=sum(totals[x] for x in ('source_controls','prefix_controls','Q_suffix_controls','G0_suffix_controls'))
    samples=sum(totals[x] for x in ('source_samples','candidate_generation_samples',
        'prefix_samples','Q_suffix_samples','G0_suffix_samples'))
    observations=controls+attempts
    explicit_rows=observations+204806
    policy_visual=3*samples
    state_captures=500+500*branches_per_parent
    parts=dict(
        new_RGB_raw_pixels=observations*480*480*3,
        core_visual_features_float32=explicit_rows*4096*4,
        normal_demonstration_tokens_float32=204806*256*2048*4,
        trajectory_metadata_reservation_4KiB_per_control=controls*4096,
        sample_raw50_noise_journal_reservation_64KiB_per_sample=samples*65536,
        cut_and_replayed_cut_state_reservation_1MiB_each=state_captures*1048576,
        local_candidate_metadata_reservation_16KiB_per_parent=500*16384,
        task_language_feature_cache=50*2048*4)
    output=sum(parts.values())
    staging=2*301*480*480*3
    model_cache=2*old_quote['storage']['peak']['optional_per_host_pi05_weight_cache_bytes']
    plan_allowance=(output+9)//10
    return dict(name='conditional_normal_Gold_repeat0_reuse' if normal_reuse else 'cold_policy_replay_no_reuse',
        kind='DESIGN_SCENARIO_NOT_EXECUTABLE_CAPS',
        assumptions=['500 legal cuts; no early stop; exact absolute s300 endpoint',
            'one native H10 source + Q3x2 + G0(1old+3fresh)x2',
            'cold policy prefix replay; no physical raw-alias discount',
            'feature batch_size=1 and no cache/dedup/compression discount',
            'restoration/identity checks are additional operations; task-specific closure not proven'],
        requires_normal_alias_proof=normal_reuse,
        normal_sources=500,Q_logical_suffix_labels=3000,G0_logical_suffix_labels=4000,
        logical_total_outcomes=7500,
        physical_attempts=attempts,physical_Q_attempts=3000,
        physical_G0_attempts=500*g0_per_parent,physical_shared_normal_Gold_results=500 if normal_reuse else 0,
        per_cut=by_cut,components=dict(totals),
        controls=controls,samples=samples,flow_forwards=10*samples,
        noise_full50_draws=samples,prefix_transformer_forwards=samples,
        action_expert_forwards=10*samples,observations=observations,
        reset_complete_observations=attempts,control_observations=controls,
        render_calls=observations,rgb_readbacks=observations,
        policy_visual_forwards=policy_visual,policy_language_forwards=samples,
        explicit_visual_feature_rows=explicit_rows,explicit_visual_feature_forwards=explicit_rows,
        explicit_language_feature_forwards=50,
        total_visual_forwards=policy_visual+explicit_rows,
        total_language_forwards=samples+50,
        preprocessing=dict(
            policy_batch_preprocessor_calls=samples,
            explicit_feature_preprocessor_calls=explicit_rows,
            image_preprocess_function_calls=samples+explicit_rows,
            real_image_rows_preprocessed=samples+explicit_rows,
            padded_image_tensors_created=2*(samples+explicit_rows),
            policy_real_images_encoded=samples,policy_padding_images_encoded=2*samples,
            explicit_real_images_encoded=explicit_rows,explicit_padding_images_encoded=0,
            tokenizer_calls_if_current_feature_path_reused=samples+explicit_rows+50,
            sample_postprocessor_calls=samples,
            note='sample internal encoders and explicit feature extraction are distinct physical calls. Same tokens feed compatible aggregate/LVM views without a second explicit extraction. Batch>1 needs its own rows/calls accounting.'),
        CPU_candidate_design_cost=dict(cuts=500,standard_normal_nodes=6000,
            interpolated_direction_values=20000,groups_normalized=1000,
            own_symmetric_radius_group_calculations=1000,local_raw50_plans_written=1000,
            float32_candidate_C10_values_written_upper=40000,
            formula='one12-node smooth direction and one own radius per XYZ/gripper group per cut, reused with ±sign; no extra model sample or Q/gradient',
            RNG_draw_calls=None,RNG_draw_calls_reason='node count fixed; actual RNG API batching/version future-bound',
            CPU_wall_time_seconds=None,serialization_cost_included_as_reservation_not_measured=True),
        Q_forward=0,D_forward=0,G0_forward=0,action_gradients=0,model_backward=0,training_updates=0,
        full_state_verification_proposal=dict(
            captures=state_captures,cut_comparisons=500*branches_per_parent,
            proposed_mj_getState_calls=state_captures,
            proposed_mj_stateSize_calls=attempts,
            actual_snapshot_restores_in_cold_replay=0,
            extra_validation_renders_selected=0,extra_validation_models_selected=0,
            model_and_Python_and_RNG_field_copies='one complete field set per capture; schema/type closure required before finite release',
            caveat='comparison uses existing cut observation and direct captured fields, no _get_obs. These proposed API coefficients need implementation audit; API reads do not themselves prove full_state_verified.',
            all_task_fields_and_auxiliary_caps_closed=False),
        shelf_like_reference_only=dict(environment_instances=2*attempts,MT1_tasksets=attempts,
            taskset_native_resets=50*attempts,wrapper_native_resets=attempts,
            explicit_native_resets=attempts,native_resets=52*attempts,
            reset_model_calls=104*attempts,initialization_physics_substeps=26000*attempts,
            not_a_universal_MT50_bound=True),
        physics_reference=dict(
            exact_300step_schedule_substeps=attempts*4000,
            safe14_per_control_if_same_wrapper=14*controls,
            note='both exclude initialization; exact4000/attempt requires proven same400Hz/30Hz absolute scheduler, not all tasks validated'),
        cold_model_loads=dict(policy_model_loads_upper=attempts,
            shared_encoder_additional_checkpoint_loads=0,
            separate_demo_feature_worker_loads='W_demo, still to be bounded',
            standalone_D_G0_Q_loads=0,
            old_C10_launcher_is_not_collector=True),
        graphics_auxiliary=dict(fresh_worker_count='W_graphics <= attempts only after future launch topology binding',
            per_fresh_worker_reference=old_quote['initialization_and_restore']['graphics_auxiliary_reference_per_fresh_worker'],
            additional_scene_updates_and_setbuffer='scale with actual observations plus explicitly released restore effects',
            note='reference counters are not complete future release; loader/identity/error/cleanup and task-specific initialization need finite reviewed caps'),
        storage=dict(parts_bytes=parts,selected_output_bytes=output,
            selected_output_TiB=output/(1024**4),
            pixel_payload_is_uncompressed=True,compression_discount=0,
            exact_container_hard_bound_bytes=None,
            planning_allowance10pct_bytes=plan_allowance,
            writer_staging_2_workers_301_RGB_each_bytes=staging,
            optional_two_host_pi05_cache_bytes=model_cache,
            planning_peak_bytes=output+plan_allowance+staging+model_cache,
            planning_peak_TiB=(output+plan_allowance+staging+model_cache)/(1024**4),
            optional_new_rollout_tokens_float32_bytes=observations*256*2048*4,
            optional_new_rollout_tokens_selected=False,
            existing_demo_payload_copy_bytes=0,
            state_and_journal_sizes_are_estimates=True,
            missing_hard_bounds=['serialized full model/task/RNG state may exceed1MiB',
                'field/initialization/feature/exception journals and container headers',
                'per-worker feature batching/temporary/failure retention'],
            project_quota_bytes=None,project_remaining_bytes=None,capacity_reserved=False))

scenarios=[scenario(False),scenario(True)]
check('7500_no_reuse_crosscheck',
      [scenarios[0][k] for k in ('physical_attempts','controls','samples','flow_forwards','observations')]
      ==[7500,2250000,226500,2265000,2257500], 'analysis contract exact totals')
check('7000_conditional_reuse_crosscheck',
      [scenarios[1][k] for k in ('physical_attempts','controls','samples','flow_forwards','observations')]
      ==[7000,2100000,211500,2115000,2107000], 'one physical normal/old0 per parent, repeat1 separate')
for s in scenarios:
    check('visual_and_language:'+s['name'],s['policy_visual_forwards']==3*s['samples']
        and s['policy_language_forwards']==s['samples'],
        dict(policy_visual=s['policy_visual_forwards'],policy_language=s['policy_language_forwards'],
            explicit=s['explicit_visual_feature_forwards'],total_visual=s['total_visual_forwards']))
    check('storage_sum:'+s['name'],sum(s['storage']['parts_bytes'].values())==s['storage']['selected_output_bytes'],
        s['storage']['selected_output_bytes'])
short=[]
for cut in (5,55):
    src=cut+11;q=6*(cut+11);g=8*(cut+6)
    n=(src+9)//10+3+14*((cut+9)//10+1)
    short.append(dict(cut=cut,normal_control_milestone=src,Q_each_control_milestone=cut+11,
        G0_each_control_milestone=cut+6,physical_attempts_no_reuse=15,
        controls_through_milestones=src+q+g,full_samples_through_milestones=n,
        flow=10*n,observations=src+q+g+15,policy_visual=3*n,
        policy_language=n,explicit_visual_features=src+q+g+15,
        extra_instruction_features=1,candidate_generations=3,
        committed_Q_steps=60,committed_G0_steps=40,
        terminal_negative_labels_allowed=0,
        bound='all reach cut/no early stop, first native suffix step only; actual early stop lowers cost without refill'))
quote=dict(schema='common-pool-revised-quote/2',task_id=TASK,
    status='DESIGN_QUOTATION_NOT_RELEASE',actual_compute_authorized=False,
    design_tranche=dict(tasks=50,train_per_task=8,development_per_task=2,parents=500,
        cuts=[5,55],parents_per_cut=250,guaranteed_legal_or_trainable_parents=None,
        source_IDs=None,seeds=None,executable_shards=None,live_budget=None),
    formulas=dict(attempts='P + L*(3*2 + (1+3)*2) - I_reuse*L; P=L=500 in worked scenario',
        controls='P*T + sum_physical_branches(c+(T-c)); T=parent_absolute300, not300 after cut',
        samples='P*ceil(T/10) +3*L + sum_Q(ceil(c/10)+ceil((T-c-10)/10)) + sum_G0(ceil(c/10)+ceil((T-c-5)/10))',
        native_continuation='after C5 or C10 discard unexecuted raw tail and sample H10; last partial chunk ends at s300',
        flow='10*complete_samples; failed partial calls charged entered/returned separately',
        local_candidates='local± use one CPU smooth direction, no additional VLA beyond3fresh/cut',
        controls_and_observations='one initial real observation per attempt plus one per actual control',
        encoders='3*sample policy visual + explicit real-observation feature forwards; sample language + task language features',
        legal_cut_shortfall='P fixed planned source population; L<=P actual reached legal cuts. No source/seed/cut replacement or outcome-based refill'),
    scenarios=scenarios,
    optimizations_not_implemented=dict(
        recorded_action_prefix_replay=[dict(scenario=s['name'],
            removed_policy_prefix_samples=s['components']['prefix_samples'],
            alternative_samples=s['samples']-s['components']['prefix_samples'],
            alternative_flow=10*(s['samples']-s['components']['prefix_samples']),
            controls_unchanged=s['controls'],observations_unchanged=s['observations'])
            for s in scenarios],
        resident_workers='W_policy loads instead of attempts; W and exact lifetime/RAM/VRAM/cleanup bounds not frozen; no saved compute claimed now',
        cached_tasksets='no reset/init discount until validated task-specific implementation',
        snapshot_restores='remove prefix controls only with proven field closure/roundtrip; add restore, mj_forward/rebuild, RNG/queue copies and validation overhead; not selected base quote',
        shared_features='one extraction per identical image+encoder/preprocessor/layer/dtype SHA signature; no internal-policy encoder reuse or dedup credit assumed',
        lossless_images='stream immutable lossless output; exact pixels/dtype checked, compressed-size estimate not a hard cap; no images re-encoded now'),
    next_collector_acceptance=dict(status='NOT_IMPLEMENTED_NOT_RELEASED',
        order=['CPU rule/identity/alias/repeat/censor fixtures under implementation task',
            'finite implementation and exact caps review, then independent release',
            'first already planned parent: full-state checks before outcomes, threefresh/±raw identities, two repeats and C5/C10 phase checks',
            'short milestones followed by full parent s300/real success/terminal qualification before wider collection'],
        milestones_are_subsets_not_added_experiments=True,short_milestone_quotes=short,
        cold_shelf_reference_for15_attempts=dict(native_resets=780,reset_model=1560,initialization_substeps=390000),
        restore_checks_and_extra_calls='priced separately from short milestones using full-state field/API coefficients; unresolved ones block release',
        expected_checks=['a0/fresh0 shared generation only','±C10 pair and raw tail preservation',
            'G0 fresh0/1/2 x repeat0/1 and old0/1 distinct identities',
            'missing repeat/zero alias/observables-only masks','absolute clock and s300 boundary',
            'parent ownership, no second writer/retry','whole-group exit and joint barrier'],
        early_stop='retain all partial stages and actual costs, do not manufacture coverage',
        full_MT50_or_training_sufficiency_proven=False),
    init_status='TASK_INITIALIZATION_GAPS.json; shelf reference only, other49 unknown',
    filesystem_metadata=ref(W/'FILESYSTEM_METADATA.json'),
    quota_blocker='statvfs is a virtual shared filesystem report, not project quota; no quota command/API/ID or reserved bytes established',
    workers_and_time=dict(actual_worker_count=None,wall_seconds=None,
        model_VRAM_planning_per_worker_bytes=24*1024**3,
        model_RAM_planning_per_worker_bytes=64*1024**3,
        estimates_not_measured_caps=True,
        loader_IO_hash_cleanup_and_storage_throughput='future finite budget required, no hardware benchmark now'),
    current_compute={k:0 for k in release['limits']},
    legacy4500_scenario='archived V1 only; never retained as current budget',
    optional_velocity_logging='not implemented/not selected; no new replay, guided Q remains null',
    all_outputs_retained=True,deletion_authorized=False)
write('RESOURCE_AND_STORAGE_QUOTE.json',quote)

methods=copy.deepcopy(old_draft['method_views'])
for v in methods:
    name=v['method']
    if name=='Q':
        v['selection']='a0/local_plus/local_minus C10 then H10 through parent absolute s300; BCE per own complete repeats; gain/pair only full_state_verified with both matched planned repeats'
        v['pair_definition']=['local_plus','local_minus']
        v['repeats']=2
        v['target']='empirical success through original-parent s300 inclusive under fixed candidate C10 then nativeH10; unchanged source BCE+gain+0.5pair'
    elif name=='G0':
        v['target']='(1/3)*sum_k=0..2((y_freshk,0+y_freshk,1)/2) - (y_old,0+y_old,1)/2 through parent absolute s300 inclusive'
        v['selection']='old and three fresh C5 arms; full_state_verified and common complete repeat IDs exactly[0,1]'
        v['fresh_count']=3;v['repeats_per_arm']=2
    elif name=='VLA-Corrector-adapted':
        v['selection']='normal demonstration same original episode, observed contiguous t..t+10, true endpoint tokens and original action_t representation/normalizer identity; no complete terminal flag requirement'
        v['eligibility_independent_of_outcome_complete']=True
        v['requires_actual_execution_action_mapping']=False
        v['requires_original_action_representation_identity']=True
        v['missing']='real endpoint tokens/encoder/action normalizer and future parent split must be bound; missing terminal fields remain null but are not an LVM-only rejection'
    elif name in ('D5','GAF-v1-adapted'):
        v['LVM_relaxation_applies']=False
    if name=='GAF-v1-adapted':
        v['complete_target_for_new_pool']='parent absolute s300 inclusive or admitted earlier success/absorbing termination; old demo compatibility must be separately proven'
draft=dict(schema='common-pool-protocol-design/2',task_id=TASK,
    status='CPU_DESIGN_READY_FOR_REVIEW_NOT_COLLECTOR_READY',
    authoritative_decisions=ref(B/'contracts/COMMON_POOL_PROTOCOL_DECISIONS_V2.md'),
    design_fixed=dict(tasks=50,train_per_task=8,development_per_task=2,parents=500,
        H=10,raw_generation_length=50,flow_steps=10,cut_schedule=[5,55],Q_commitment=10,
        G0_commitment=5,continuation_H=10,parent_absolute_target_state=300,
        Q_candidates=['a0','local_plus','local_minus'],Q_repeats=2,
        G0_arms=['old','fresh0','fresh1','fresh2'],G0_repeats=2,
        generated_native_plans_per_legal_cut=3),
    not_frozen=dict(real_parent_IDs=None,seeds=None,shards=None,resource_caps=None,
        collector_version=None,actual_legal_cuts=None,valid_paired_source_count=None,
        MT50_training_recipe=None,initialization_choices=None),
    quantity_claim='500 planned parents is coverage design only; no guarantee500 valid cuts, paired labels, enough variation or adequate training/statistical power',
    pool_namespaces=old_draft['pool_namespaces'],
    parent_split=old_draft['parent_split'],
    historical_train600_recollect=False,scope_additions=[],
    local_probe=dict(
        generator='critic independent 12 standard-normal nodes,3 per action dimension at t=0,4.5,9, linear interpolation to t=0..9',
        future_RNG_binding='dedicated stream independent of source/fresh/suffix; save engine/API/version+12raw nodes+40 interpolated values; actual seed and implementation remain null',
        groups=dict(XYZ=dict(coordinates=30,RMS_target=0.05,Linf=0.15),
                    gripper=dict(coordinates=10,RMS_target=0.10,Linf=0.40)),
        anchor='b=clamp(a0_raw[:10],-1,1); M=(1-|b|>=0.05)',
        formula='dbar=M*d; n=RMS over all30 or10 including masked zeroes; n<=1e-10 => delta_group0. Otherwise e=dbar/max(n,1e-10), B_j=min(1-|b_j|,L_g), c=min_{|e_j|>1e-10} B_j/|e_j|; r=(1-1e-6)*max(0,min(rho_g,c)); delta=r*e.',
        raw_writeback='copy a0 raw50 twice; only nonzero active C10 coordinates receive +/-delta; inactive/zero/tail bytes remain a0. Save float32 actual raw/executed deltas separately; no claim bitwise antisymmetry after writeback.',
        guard='existing boundary/RMS/Linf tolerance1e-6; not a state-restore tolerance; no min(r,n), shared P/V radius, old Q, redraw, parameter sweep or Q acceptance gate',
        actual_candidate_generator_run=False,actual_projection_run=False),
    alias=dict(key='same parent+cut+Q_C10 protocol + first10 raw-command bytes',
        clamped_equal_is_alias=False,different_tail_creates_new_supervision=False,
        raw50_and_noise_full_identities_retained=True,
        physical_no_reuse_main_quote=True,
        training='distinct raw groups equal weight within source; alias slots1/group_size; baseline group excluded gain; pair only distinct plus/minus raw groups; unordered duplicates once; empty sets0 without dropping/reweighting parent',
        alias_outcome_conflict='if raw-alias same-repeat trajectories/outcomes disagree, retain conflict and block paired label pending identity/state review; do not pool repeats or choose favorable representative'),
    outcomes=dict(target='ever success from original parent through result state s300 inclusive',
        cut_precondition='reached predetermined5/55, nonterminal/no prior success, nativeH10 queue age5 with5 old actions, sufficientC10 remaining',
        failure_zero='no success with complete observed absolute horizon300, or pre-frozen genuine absorbing negative terminal',
        null='technical exception, quota/timeout, unknown TimeLimit, missing observation/outcome or private early stop',
        fields=['parent_absolute_step','cut_absolute_step','remaining_target_controls',
            'first_success_step','outcome_complete','completion_reason','terminated','truncated','terminal_semantics_identity']),
    paired_eligibility=dict(required='full_state_verified',required_repeat_ids=[0,1],
        gain_intersection='a0 and selected candidate',pair_intersection='local_plus and local_minus',
        G0_intersection='old and fresh0/1/2',fields=['valid_pair_repeat_ids','planned','entered','completed','missing','target_mask'],
        one_repeat_target_allowed=False,pointwise_BCE='own complete repeats only with explicit count; no implicit full paired eligibility',
        loss='L_success_i + L_gain_i + 0.5 L_pair_i; source mean. No radius division, TD, hinge or teacher labels. Training initialization/weights for partial BCE deferred to training contract.'),
    streams=dict(candidate='three independent fresh generation streams indexed0/1/2; fresh0=a0, isolated from continuation; one independent local-probe stream',
        suffix='protocol target namespace + parent/cut/repeat/decision_index; no host/candidate-family component',
        namespaces=['Q_C10','G0_C5'],repeat_ids=[0,1],
        prefix='same parent source-generation identities for cold replay; candidate generation does not advance source RNG',
        normal='prospectively assign normal cut continuation to G0_old repeat0 only in conditional-reuse mode; match whole execution/target/cut-age/state/action/noise/policy and complete outcome, never posthoc equality'),
    method_views=methods,field_view_matrix=old_draft['field_view_matrix'],
    field_view_matrix_interpretation='consumer roster describes accessible raw fields, not an all-fields-required gate. Method-specific selection above and FIELD_VIEW_MATRIX.md control eligibility; null terminal flags do not reject LVM-only rows.',
    shared_features=old_draft['shared_features'],
    B_frozen_contracts=old_draft['B_frozen_contracts'],
    B_adapter_confirmation_required=['LVM qualification independent of D5/GAF terminal/executed-action gates',
        'sidecar target namespace/repeat/mask/full-state and raw-alias group consumption',
        'new component split/normalizer/encoder/train recipe under later task'],
    interface_v1=old_draft['interface_v1'],
    new_sidecar_fields=['parent_absolute_target_state','outcome_complete/reason',
        'target_namespace','candidate/fresh/repeat IDs','raw_C10_group','physical_attempt_ref',
        'valid_pair_repeat_ids','full_state_verification_ref','method_eligibility_masks',
        'actual raw/writeback/executed action identities','normal_reuse_evidence_ref'],
    initialization_lineage=old_draft['initialization_lineage'],
    shared_pool_is_equal_historical_training_data=False,
    optional_velocity_logging_memo='previous decision retained: not implemented/executed; no standalone replay or independent final guidedQ',
    current_real_counts={k:0 for k in release['limits']})
write('COMMON_POOL_DRAFT.json',draft)

alignment=[
 ('Q_PAIR','native-independent Q slot removed; a0 and local± each2; true pair and alias/zero/missing masks','COMMON_POOL_DRAFT.json'),
 ('G0_ESTIMATOR','threefresh each2 vs old2; shared a0 generation only; C5/C10 physical outcomes separate','SYNTHETIC_CANDIDATE_LABELS.json'),
 ('PAIRED_LABELS','full_state_verified and complete aligned two-repeat intersection; no observable-only counterfactual labels','RESTORE_FIELD_CONTRACT.json'),
 ('HORIZON','absolute parent s300 inclusive and explicit complete/censor reasons','COLLECTION_AND_REPLAY_PROTOCOL.md'),
 ('ENCODER_QUOTE','3policy visual+1language/sample; explicit feature/preprocess/image rows separate','RESOURCE_AND_STORAGE_QUOTE.json'),
 ('CUT_HOST','train task/split/cut balance2 eachhost; dev25 eachcut/host across50','SYNTHETIC_SHARD_CROSSTAB.json'),
 ('LVM_ELIGIBILITY','terminal flags not needed for LVM-only continuous normal tokens/action_t view; D5/GAF not relaxed','FIELD_VIEW_MATRIX.md'),
 ('JOINT_BARRIER','all-node exit before reservation release, data publication separate','COLLECTION_SHARDS_DRAFT.json')]
write('DECISIONS_ALIGNMENT.json',dict(task_id=TASK,decision_contract=ref(B/'contracts/COMMON_POOL_PROTOCOL_DECISIONS_V2.md'),
    items=[dict(id=i,implemented_design=d,evidence=f) for i,d,f in alignment],
    design_sizes=dict(no_reuse=7500,conditional_reuse=7000),
    actual_collection_or_training_authorized=False,
    unknowns=['real full-state verification for any new parent','other49 initialization caps',
        'eligible source/sample yield','quota/storage hard bound','new collector/B adapter implementation',
        'exact real IDs/seeds/shards/resource limits']))
check('50_task_init_rows_with49_unknown',len(task_init)==50 and
      sum(x['shelf_reference_per_attempt'] is None for x in task_init)==49,'no shelf universal cap')
check('all_130_release_operations_zero',len(release['limits'])==130 and
      all(x==0 for x in release['limits'].values()),'task CPU scope maintained')
check('no_real_restore_proof',all(not x['full_state_roundtrip_passed'] for x in task_init),'0 real roundtrips')
check('new_candidate_count',draft['design_fixed']['generated_native_plans_per_legal_cut']==3 and
      draft['design_fixed']['Q_repeats']==2,'Q± adds no VLA generation')
write('CPU_DESIGN_CHECKS.json',dict(task_id=TASK,at_utc=NOW,status='PASS',
    checked_scope='integer arithmetic, symbolic labels/masks, AST/text identities and synthetic owner tables only',
    tests=CHECKS,check_count=len(CHECKS),
    actual_models_environments_candidate_generators_projections=0))
write('INPUT_MANIFEST.json',dict(task_id=TASK,files=list(INPUTS.values()),
    inherited_other49_task_source_refs='TASK_INITIALIZATION_GAPS.json (metadata references only; not freshly hashed/opened)',
    historical_data_coverage='reused accepted V1 small metadata; no raw trajectory/held/image read',
    weights_or_hardware_opened=False,models_imported=False,
    source_selection='two mapping modules plus base/shelf/wrapper/sampler/feature/state APIs; no full library inventory'))
print(json.dumps(dict(status='CPU_DOCUMENTS_BUILT',task_id=TASK,checks=len(CHECKS),
    attempts=[s['physical_attempts'] for s in scenarios],
    samples=[s['samples'] for s in scenarios],
    visual=[s['total_visual_forwards'] for s in scenarios],
    output_bytes=[s['storage']['selected_output_bytes'] for s in scenarios],
    planning_peak_TiB=[s['storage']['planning_peak_TiB'] for s in scenarios]),ensure_ascii=False))
