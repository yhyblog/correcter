import copy,hashlib,json,sys
from pathlib import Path
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');B=ROOT/'Corrector/sim_command/20260919'
P=B/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1';O=B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1';V=B/'results/A/A11_COMMON_POOL_REVISION_CPU_V2'
sys.path.insert(0,str(P/'code'))
from budget import TOTAL,PER_ATTEMPT,PARENT,TIMEOUTS,STORAGE,numeric_caps
from native.initialization import EXPECTED_CAPS
from native.graphics_contract import CAPS
from pool_protocol import ARMS
def read(p):return json.loads(p.read_text())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
def ref(p,fmt=None):
 r=dict(path=str(p),realpath=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size_bytes=p.stat().st_size)
 if fmt:return {k:r[k] for k in ('path','sha256')}|{'format':fmt}
 return r
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
sources=read(V/'STATIC_SOURCE_EVIDENCE.json')
closure=dict(schema='shelf_full_state_v1',status='CPU_IMPLEMENTED_RUNTIME_QUALIFICATION_UNVERIFIED',
 task_allowlist=['metaworld.envs.sawyer_shelf_place_v3.SawyerShelfPlaceEnvV3'],other49='deny',
 comparison='exact typed arrays/scalars, dtype/shape/little-endian bytes including signed zero; zero tolerance',
 canonical_boundary='after actual cut5 observation and feature/history update, before bank generation or intervention',
 actual_full_state_verified_attempts=0,actual_environment_calls=0,privileged_fields_used_as_model_input=False,
 runtime_unknown_policy='reject unsupported field types, schema/fieldset mismatch, plugin/callback, source/prefix mismatch before intervention; stop wave',
 groups={
 'identity':dict(classification='immutable',fields=['task class','source signature','policy/encoder/normalizer/projection/config/package SHAs','prefix plans and frame/action/feature SHA'],basis=['frozen config/input/code/external manifests','exact prefix_records check']),
 'integration':dict(classification='captured',fields=['mjSTATE_INTEGRATION: time,qpos,qvel,act,history,qacc_warmstart,ctrl,qfrc_applied,xfrc_applied,eq_active,mocap_pos,mocap_quat,userdata,plugin_state'],reads=['mj_stateSize','mj_getState'],dtype='float64',basis=['mujoco3.6.0 mjdata.h state flag','bindings_test.py stateSize/getState shape behavior']),
 'mutable_model':dict(classification='captured',fields=['MJB byte image of compiled model including shelf body_pos,goal/site coordinates,eq_data,corner2 cam_pos,opts/dynamics/material/visual params'],reads=['mj_sizeModel','mj_saveModel'],purpose='identity serialization only, never restore',basis=['installed mj_saveModel declaration and size API'],runtime_unknown=['MJB Python buffer binding and deterministic exact bytes across fresh children are unmeasured','header/declaration alone is not real mutation coverage proof']),
 'task_python':dict(classification='captured',fields=['all actual __dict__ entries, not a selective reward-cache list','_prev_obs/_last_stable_obs','_target_pos/_last_rand_vec/_freeze_rand_vec/seeded_rand_vec','curr_path_length/max_path_length/_did_see_sim_exception','init_qpos/init_qvel/init_tcp/hand_init_pos','obj_init_pos/angle/init_config','liftThresh/objHeight/heightTarget/maxPlacingDist','nested spaces and RNG engine/state'],basis=['frozen shelf/base Python code and recursive typed serializer'],unknown='any unclassified object rejects'),
 'wrapper_python':dict(classification='captured',fields=['all actual wrapper vars','task/camera/render_mode/dimensions/_max_episode_steps','spaces including nested dictionary Box bounds/dtype/RNG'],basis=['private MetaworldEnv.__dict__ plus native task captured separately']),
 'rng':dict(classification='captured',fields=['Python random','NumPy global plus all encountered Generator/RandomState objects, max17 reads','Torch CPU and target CUDA generator, max2 reads'],basis=['reset global/env seeds before explicit reset','all policy noise uses a separate device torch.Generator','candidate/local/Q/G0 namespaces bound in source proposal'],intentional_difference='run/branch IDs and repeat suffix streams applied only after state verification'),
 'clocks':dict(classification='captured',fields=['absolute control index','data.time','frame_skip','(absolute_step*400)%30','action_scale .015','H10/target s300'],basis=['controller and native runtime_engine.step floor schedule']),
 'queue_history':dict(classification='captured',fields=['raw50 exact bytes,age5,remaining5','policy queues required empty','causal last5 features/proprio and last4 actual actions','parameter/buffer version integers'],basis=['RTC disabled and H10 controller owns queue; strict frozen eval policy']),
 'callbacks_plugins':dict(classification='captured',fields=['8 callback getter results must None','nplugin/npluginstate must0'],basis=['unsupported extension state rejected, no fallback'])},
 excluded_or_derived=[
 dict(field='native.model',classification='captured',basis='MJB identity serialization; no object address comparison'),
 dict(field='native.data integration',classification='captured',basis='getState flags'),
 dict(field='native.data derived kinematics/contact workspace',classification='recomputed',basis='frozen native step/do_simulation computes derived fields before reward/observation; no extra _get_obs or forward during comparison',runtime_proof=False),
 dict(field='native.mujoco_renderer GL handle addresses',classification='irrelevant',basis='not physics state; same frozen native viewer config/compiled camera and exact actual prefix RGB/features; never reuse/restore a handle',runtime_proof=False),
 dict(field='wrapper.expert_policy',classification='irrelevant',basis='fixed policy class identity; this collector never calls expert policy'),
 dict(field='unknown attrs/plugin/callback or undeclared model modification',classification='unknown',basis='blocks full_state_verified; no tolerance relaxation')],
 unresolved_for_future_parent=['MJB real buffer call/byte identity and static coverage inference require embedded real comparison; no real proof claimed',
 'unanticipated task/space/native state fails closed; no observable-only fallback',
 '128GiB RLIMIT_AS compatibility with CUDA virtual address mapping not measured',
 'project quota/reservation and non-writer library temporary/cache closure not known; launcher refuses without explicit storage admission evidence'],
 source_evidence=ref(V/'STATIC_SOURCE_EVIDENCE.json'),prior_contract=ref(V/'RESTORE_FIELD_CONTRACT.json'))
write(P/'STATE_FIELD_CLOSURE.json',closure)
support=dict(task='shelf-place-v3',paths={
 'cold_policy_replay':{'implemented':True,'synthetic_checked':True,'real_verified':False},
 'normal_plus14_sequential_children':{'implemented':True,'real_verified':False},
 'full_state_compare':{'implemented':True,'real_verified':False,'unknown_rejects':True},
 'snapshot_restore':{'implemented':False},'normal_reuse':{'implemented':False},
 'persistent_worker':{'implemented':False},'recorded_action_replay':{'implemented':False},
 'all_other49_tasks':{'allowed':False,'implemented':False},'cross_machine_reservation':{'implemented':False,'required_for_A_only':False}},
 planned_parent_count=1,active_parent_count=0,real_claim_count=0,B_compatibility_feedback='not received; no joint integration claim')
write(P/'SUPPORT_MATRIX.json',support)
cfg=read(O/'config/CONFIG.json')
for k in ['Q_assets','guidance','deployment_sampling_calls','Q_scope','DG0']:cfg.pop(k,None)
cfg['schema']='common_pool_first_parent_H10_collector_v1'
source=dict(task='shelf-place-v3',env_seed=2026092000,master_seed=2026092001,split='train',
 instruction='Pick and place a puck onto a shelf',source_id='PROPOSED_MT50_shelf_train_0000',parent_source_id='PROPOSED_MT50_shelf_train_0000_parent',
 status='UNAUTHORIZED_TEMPLATE',purpose='first planned parent of coverage batch; not extra diagnostic',cut=5,absolute_target=300,
 selection='fixed proposed ordinal0 train cut5; no outcome-dependent seed replacement',prefix_mode='cold_policy_replay',
 policy_noise_rng='torch.Generator on fixed target device; exact saved float32(1,50,32) noise',
 local_probe_rng='CPython3.12 random.Random.gauss;12 nodes; independent seed derived by pool_protocol.stream_seed')
write(P/'proposal/SOURCE_PROPOSAL.json',source);cfg['source']=source;cfg['source_manifest_ref']=ref(P/'proposal/SOURCE_PROPOSAL.json','json')
cfg['source_signature']=digest(source)
cfg['control']=dict(H=10,cut=5,episode_max_steps=300,physics_hz=400,control_hz=30,native_action_scale=.015,
 camera='corner2',width=480,height=480,branch_order=[j[0] for j in ARMS],normal_reuse=False,cold_replay=True,maximum_attempts=15)
cfg['native']['graphics_caps']=CAPS
old_inputs=read(O/'INPUT_MANIFEST.json')['files'];inputs=[]
for row in old_inputs:
 s=row['path']
 if s.startswith(cfg['checkpoint']+'/') or s==cfg['projection'] or cfg['hf_home'] in s or s.endswith(('gpu_occupancy_lifecycle.sh','gpu_occupancy_guard.py')):
  inputs.append(dict(row,verification_now='inherited accepted C10 V2 SHA; no content hash/read now'))
model=next(x for x in inputs if x['path'].endswith('/model.safetensors'))
norm=next(x for x in inputs if x['path'].endswith('/policy_postprocessor_step_0_unnormalizer_processor.safetensors'))
cfg['model_sha256']=model['sha256'];cfg['normalizer_ref']={k:norm[k] for k in ('path','sha256')}|{'format':'safetensors'}
cfg['feature_signature']=digest(dict(model=model['sha256'],projection=next(x['sha256'] for x in inputs if x['path']==cfg['projection']),
 pipeline='feature_path canonical_decode -> PCA -> 4096 float32;1actual image; sample3images',preprocessor=next(x['sha256'] for x in inputs if x['path'].endswith('/policy_preprocessor.json'))))
cfg['action_signature']=digest(dict(dtype='little float32 raw50x4',execution='clamp[-1,1]',scale=.015,C=[10,5],nativeH=10))
cfg['state_contract_sha256']=ref(P/'STATE_FIELD_CLOSURE.json')['sha256']
cfg['collection_policy']=dict(name='pi05_SFT_MT50',version='030000_H10_common_pool',checkpoint={k:model[k] for k in ('path','sha256')}|{'format':'safetensors'},
 training_lineage_ref=ref(B/'contracts/COMMON_POOL_PROTOCOL_DECISIONS_V2.md','markdown'))
write(P/'config/CONFIG.json',cfg)
public=B/'results/A/A10/interface_v1/interface.schema.json';inputs.append(ref(public))
write(P/'INPUT_MANIFEST.json',dict(schema='collector_input_manifest_v1',files=inputs,large_weight_rehashes_this_task=0,
 provenance=ref(O/'INPUT_MANIFEST.json'),future_verification='parent plus each started child hashes frozen inputs under separate timeouts; no current model read'))
external=read(O/'EXTERNAL_SOURCE_MANIFEST.json')
external['inherited_from']=ref(O/'EXTERNAL_SOURCE_MANIFEST.json');external['current_CPU_large_or_library_scan']=False
external['note']='Inherited file identities only; no external imports, dlopen, hardware or large file hashing now.'
stdlib=ROOT/'.miniforge3/envs/lerobot/lib/python3.12'
for item in [stdlib/'random.py',*sorted((stdlib/'lib-dynload').glob('_random.*.so'))]:
 if str(item) not in {x['path'] for x in external['files']}:
  external['files'].append(dict(ref(item),verification_now='targeted small RNG implementation identity; file bytes only, not imported/dlopen'))
write(P/'EXTERNAL_SOURCE_MANIFEST.json',external)
# Bind only extra source files actually read in this task; source text, not imports.
extra=[];site=ROOT/'.miniforge3/envs/lerobot/lib/python3.12/site-packages'
for rel in ['mujoco/introspect/functions.py','mujoco/bindings_test.py','mujoco/include/mujoco/mjdata.h','mujoco/include/mujoco/mjmodel.h','gymnasium/spaces/dict.py']:
 extra.append(ref(site/rel))
write(P/'TARGETED_SOURCE_REFERENCES.json',dict(files=extra,review='text only; declarations are not real native-call proof',prior=ref(V/'STATIC_SOURCE_EVIDENCE.json')))
future_release=B/'releases/P11_A_COMMON_POOL_FIRST_PARENT_V1.json'
script='#!/bin/sh\nset -eu\nexport CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300\n[ "$#" -eq 1 ] || exit 2\nexec '+cfg['python']+' -B '+str(P/'code/launch.py')+' --release "$1"\n'
(P/'commands/run_proposed_first_parent.sh').write_text(script)
storage=copy.deepcopy(STORAGE)
storage.update(child_stdout_bytes=32*1024**2,child_stderr_bytes=32*1024**2,parent_stdout_bytes=32*1024**2,parent_stderr_bytes=32*1024**2,
 wave_log_bytes=32*32*1024**2,
 required_reserved_bytes=STORAGE['wave_new_payload_bytes']+32*32*1024**2+STORAGE['metadata_filesystem_overhead_reservation_bytes'],
 nominal_uncompressed_RGB_bytes=15*301*(480*480*3+len(b'P6\n480 480\n255\n')),
 hard_limit_scope='Store bounded payload plus RLIMIT_FSIZE32MiB per log/record; same-inode partial links retained; no payload doubling',
 temporary_buffer='writer uses same inode retained partial; at most32MiB raw/JSON+32MiB encoding copy; CUDA cache disabled; unknown library temp writes require admission evidence',
 address_space_limit='RLIMIT_AS128GiB per process; stricter than resident RAM, unmeasured CUDA VA compatibility; no automatic relaxation')
write(P/'proposal/RESOURCE_BUDGET.json',dict(scope='UNAUTHORIZED_ONE_PLANNED_PARENT',resource_caps=TOTAL,parent_caps=PARENT,
 per_attempt_caps=PER_ATTEMPT,numeric_caps={j[0]:numeric_caps(j[0]) for j in ARMS},initialization_caps_per_child=EXPECTED_CAPS,graphics_caps_per_child=CAPS,
 arithmetic=dict(attempts=15,controls=4500,samples=453,flow=4530,observations=4515,native_reset_returns_upper=780,reset_model=1560,initialization_substeps=390000,control_substeps=60000),
 timeouts=TIMEOUTS,timeout_notes=['900 prep includes full SHA/NVML/guard active','formal.lock wait has no frozen finite timeout; null, not handoff300','handoff300 begins after formal lock acquired; polling15s may overshoot nominal','each child1800+30 includes imports/full rehash/model/init/env/serializations/cleanup','wave27900 admission alarm raises then drains, not hard kill of reserved wrapper','drain waits until actual group empty including uninterruptible processes; no finite hard exit promise','restoration120 read-only observation after lifecycle exits; not query supplement'],
 storage=storage,hash_passes_upper=16,source_count_scope='first planned train parent, not extra diagnostic or 500 valid-source guarantee',
 ledger_semantics='entered incremental units charged once, absent terminal charged; aliases are not summed as independent physical calls',
 no_Q_D_G0_models=True,shared_state_scope='shelf static adapter only; real full-state comparison required before each intervention'))
write(P/'code/CODE_MANIFEST.json',dict(schema='code_manifest_v1',files=[ref(x) for x in sorted((P/'code').rglob('*')) if x.is_file() and x.name!='CODE_MANIFEST.json' and '__pycache__' not in x.parts]))
write(P/'PREPARATION_INPUT_MANIFEST.json',dict(files=[ref(x) for x in [P/'proposal/SOURCE_PROPOSAL.json',
 B/'contracts/COMMON_POOL_PROTOCOL_DECISIONS_V2.md',B/'contracts/TASK_STATE_CONTRACT_V1.md',P/'STATE_FIELD_CLOSURE.json',
 *sorted((P/'sidecar_v1').iterdir())]],scope='small bound protocol/source/sidecar files; no model content'))
identity=dict(task_id='A11_COMMON_POOL_FIRST_PARENT_V1',task_revision=1,release_id='P11_A_COMMON_POOL_FIRST_PARENT_V1',node_role='A',
 run_id='PROPOSED_A11_shelf_train0000_parent_V1',wave_id='PROPOSED_A11_first_parent_A_only',shard_id='PROPOSED_A11_shelf_train_cut5_parent0000')
paths=dict(claim=str(B/'results/A/P11_COMMON_POOL_V1_claims/P11_A_COMMON_POOL_FIRST_PARENT_V1.json'),
 command_record=str(B/'results/A/P11_COMMON_POOL_V1_commands/P11_A_COMMON_POOL_FIRST_PARENT_V1.json'),
 output=str(B/'results/A/P11_COMMON_POOL_V1_runs'/identity['run_id']),cache=str(B/'work/A/P11_COMMON_POOL_V1_cache'/identity['run_id']))
proposal=dict(status='UNAUTHORIZED_TEMPLATE',publication_is_authorization=False,task_id=identity['task_id'],task_revision=1,
 owner_host='trial-303224955-trialrun-303224955-worker-0',wave_participants=['A'],authorization_identity=identity,device=cfg['device'],source=source,
 config=ref(P/'config/CONFIG.json'),budget=ref(P/'proposal/RESOURCE_BUDGET.json'),code_manifest=ref(P/'code/CODE_MANIFEST.json'),input_manifest=ref(P/'INPUT_MANIFEST.json'),
 external_manifest=ref(P/'EXTERNAL_SOURCE_MANIFEST.json'),closure=ref(P/'STATE_FIELD_CLOSURE.json'),sidecar_ready=ref(P/'sidecar_v1/READY.json'),
 preparation_manifest=ref(P/'PREPARATION_INPUT_MANIFEST.json'),command_ref=ref(P/'commands/run_proposed_first_parent.sh'),
 resource_caps=TOTAL,timeouts=TIMEOUTS,storage=storage,paths=paths,branch_order=ARMS,
 command=['bash',str(P/'commands/run_proposed_first_parent.sh'),str(future_release)],command_sha256=ref(P/'commands/run_proposed_first_parent.sh')['sha256'],cwd=str(P),
 embedded_checks=['normal legalcut and reference state','first Q C10 then H10 resume','all paired replay fields and exact source prefix','G0 old/fresh C5 then H10 resume','absolute s300 inclusive or earlier success, no short negative'],
 current_future_readiness='NOT_RELEASED; quota/library-temp admission missing; real state qualification and address-space compatibility unverified',
 old_compute_releases_reusable=False,public_interface_v1_modified=False,normal_reuse=False,zero_retry=True,
 method_views='episode/transition+sidecar produced; B window adapter independent; no new full token archive')
write(P/'proposal/PROPOSAL.json',proposal)
release=dict(status='UNAUTHORIZED_TEMPLATE',campaign_id='corrector-sim-20260919',release_id=identity['release_id'],task_ids=[identity['task_id']],task_revision=1,
 owner_host=proposal['owner_host'],proposal_sha256=ref(P/'proposal/PROPOSAL.json')['sha256'],identity=identity,resource_caps=TOTAL,device=cfg['device'],source=source,
 paths=paths,timeouts=TIMEOUTS,storage=storage,wave_participants=['A'],max_commands=1,max_claims=1,max_retries=0,storage_admission=None)
write(P/'proposal/RELEASE_TEMPLATE.json',release)
board=dict(status='UNAUTHORIZED_TEMPLATE',tasks=[dict(id=identity['task_id'],owner='A',status='ready',revision=1,release='releases/'+identity['release_id']+'.json',
 **{k:identity[k] for k in ('run_id','wave_id','shard_id')})])
write(P/'proposal/BOARD_TEMPLATE.json',board)
write(P/'proposal/CONTROL_TEMPLATE.json',dict(template_status='UNAUTHORIZED_TEMPLATE',mode='run',stop_requested=False,formal_gpu_runs_enabled=True,
 active_compute_release_id=identity['release_id'],active_compute_release='releases/'+identity['release_id']+'.json',active_compute_task_ids=[identity['task_id']],current_compute_limits=TOTAL,
 allowed_task_ids=[identity['task_id']],per_task_compute_limits={identity['task_id']:TOTAL}))
print(json.dumps(dict(prepared=True,caps=len(TOTAL),inputs=len(inputs),code_files=len(read(P/'code/CODE_MANIFEST.json')['files']),large_weight_hashes=0,real_calls=0,required_reserved_bytes=storage['required_reserved_bytes'])))
