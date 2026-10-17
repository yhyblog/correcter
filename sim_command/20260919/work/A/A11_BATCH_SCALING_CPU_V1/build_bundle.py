"""Build CPU metadata/proposals only; never invoke a model, environment or launcher."""
from pathlib import Path
import ast,copy,hashlib,json,sys,xml.etree.ElementTree as ET
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');B=ROOT/'Corrector/sim_command/20260919'
P=B/'results/A/A11_BATCH_SCALING_CPU_V1';V=B/'results/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1'
C=B/'results/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1';O=B/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1'
sys.path.insert(0,str(P/'code'));import inheritance
from task_profiles import PROFILES,FIXED_SLOTS,initialization_caps
from budget import parent_caps,batch_caps,batch_timeouts,batch_storage,scheduler_caps,attempt_caps

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):
    p=Path(p).resolve();return dict(path=str(p),realpath=str(p),sha256=sha(p),size_bytes=p.stat().st_size)
def write(p,value):
    p=Path(p);p.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n');return ref(p)

site=ROOT/'.miniforge3/envs/lerobot/lib/python3.12/site-packages';mw=site/'metaworld'
wrapper=O/'code/vendor_vla/src/lerobot/envs/metaworld.py'
common=[mw/'__init__.py',mw/'sawyer_xyz_env.py',mw/'env_dict.py',mw/'asset_path_utils.py',
    site/'gymnasium/envs/mujoco/mujoco_env.py',wrapper]
evidence=[];external=set(common)
for task,spec in PROFILES.items():
    source=site/Path(*spec['module'].split('.')).with_suffix('.py');text=source.read_text();tree=ast.parse(text)
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name==spec['cls'])
    methods={x.name:x for x in cls.body if isinstance(x,ast.FunctionDef)}
    reset=methods['reset_model'];calls=[x for x in ast.walk(reset) if isinstance(x,ast.Call)]
    hand=[x for x in calls if isinstance(x.func,ast.Attribute) and x.func.attr=='_reset_hand']
    assert len(hand)==1 and hand[0].args==[] and hand[0].keywords==[]
    model_node=methods['model_name'];xml_name=next(x.value for x in ast.walk(model_node) if isinstance(x,ast.Constant) and isinstance(x.value,str) and x.value.endswith('.xml'))
    pending=[mw/'assets'/xml_name];seen=set();options=[]
    while pending:
        path=pending.pop().resolve()
        if path in seen:continue
        seen.add(path);external.add(path);xt=ET.parse(path)
        options.extend([x.attrib for x in xt.iter('option')])
        pending.extend((path.parent/x.attrib['file']).resolve() for x in xt.iter('include'))
    assert [x['timestep'] for x in options if 'timestep' in x]==['0.0025']
    external.add(source)
    fnrows=[dict(name=n,lines=[x.lineno,x.end_lineno],source=ast.get_source_segment(text,x))
        for n,x in methods.items() if n in ('__init__','reset_model','_set_obj_xyz','_set_stick_xyz','model_name')]
    row=dict(task=task,profile=spec,source_ref=ref(source),methods=fnrows,
        XML_refs=[ref(p) for p in sorted(seen)],XML_options=options,
        per_attempt_initialization_caps=initialization_caps(task),
        derivation=dict(native_resets='MT1 50 + wrapper 1 + diagnostic 1',reset_model='2 per native reset',
            reset_hand='50 do_simulation calls per reset_model, frame_skip=5',
            initialization_physics='52*2*50*5=26000; identical numbers derived for each path',
            initialization_forward=f"2 constructor + 52*2*{spec['reset_model_forwards']}",
            policy_physics='floor(300*400/30)=4000',policy_forward='<=300 explicit base-step calls'),
        counts_conditional_on_successful_initialization=True,
        RNG_rejection_iterations_hard_bound=None,RNG_rejection_bound='child wall timeout; never add reset/sample retries',
        state_class_scope=spec['module']+'.'+spec['cls'],all_actual_instance_fields_captured=True,
        unknown_field_policy='reject before intervention; no tolerance/fallback',
        real_compatibility='shelf cut5 prior single-parent evidence only' if task=='shelf-place-v3' else 'not executed',
        cut55_compatibility='not executed',physical_equality_proven=None)
    evidence.append(row)
    hooks=dict(metaworld=str(mw/'__init__.py'),native_class=str(source),native_base=str(mw/'sawyer_xyz_env.py'),mujoco_base=str(site/'gymnasium/envs/mujoco/mujoco_env.py'))
    write(P/'config'/('INITIALIZATION_'+task+'.json'),dict(source_hooks=hooks,files=[ref(q) for q in common+[source]],task=task,static_only=True))
source_ref=write(P/'TASK_SOURCE_EVIDENCE.json',dict(scope='narrow static Python/XML dependency audit; no imports, meshes or model rehash',
    common_refs=[ref(x) for x in common],tasks=evidence,other45='default reject; remain in overall 500 coverage plan',
    common_derivations=['MT1 __init__ -> _make_tasks _N_GOALS50', 'wrapper _make_envs_task one MT1 and one env, one native reset',
        'SawyerXYZEnv.reset calls reset_model then Gymnasium.reset calls reset_model',
        'SawyerXYZEnv._reset_hand default50; MujocoEnv.set_state mj_forward once',
        'task reset_model setters/explicit mj_forward traced separately per task']))
closure=read(C/'STATE_FIELD_CLOSURE.json');closure.update(schema='common_pool_five_task_full_state_v2',
    task_allowlist=[v['module']+'.'+v['cls'] for v in PROFILES.values()],other45='deny',
    canonical_boundary='after actual cut5/cut55 observation/history, before bank generation or intervention',
    source_evidence=source_ref,physical_equality_proven=None,
    runtime_unknown_policy='unsupported fields/mismatch stop this parent; system identity/storage faults stop whole wave',
    status='CPU_PARAMETERIZED_RUNTIME_QUALIFICATION_PER_NEW_PARENT_PENDING')
closure.pop('other49',None)
closure['groups']['task_python']['basis']=['five frozen task classes/base source and exact typed serializer; no omitted task attributes']
closure['groups']['mutable_model']['fields']=['MJB complete compiled model byte image including per-task bodies/sites and corner2 camera/options']
closure['groups']['rng']['fields']=['Python/NumPy states as prior contract; Torch CPU and the parent-assigned target device state, never hardcoded CUDA0']
closure['unresolved_for_future_parent']=['actual new-task/cut55 MJB/state compatibility unmeasured; rejected in the same planned parent if unsupported',
    'frozen closure is not a theorem of complete physical equivalence', 'peak RSS/project quota/cache/unlinked/overshoot unknown; no new RLIMIT_AS']
closure_ref=write(P/'STATE_FIELD_CLOSURE.json',closure)
basecfg=read(V/'config/CONFIG.json');oldproposal=read(V/'proposal/PROPOSAL.json')
accepted=read(B/'manifests/COMMON_POOL_ACCEPTED_PARENTS_V1.json')
saved_nvml=B/'results/A/P11_COMMON_POOL_V4_runs/PROPOSED_A11_shelf_train0000_parent_V4/normal/NVML_IDENTITY.json'
hardware=read(saved_nvml)['rows'];gpu_inventory=[]
for index,uid,model,driver,pci in hardware:
    gpu_inventory.append(dict(gpu_index=int(index),gpu_uuid=uid,gpu_model=model,driver=driver,pci_bus_id=pci[-12:].lower()))
write(P/'evidence/SAVED_GPU_IDENTITIES.json',dict(source=ref(saved_nvml),devices=gpu_inventory,new_hardware_queries=0))
identity=dict(task_id='A11_COMMON_POOL_BATCH1_V1',release_id='P11_A_COMMON_POOL_BATCH1_V1',node_role='A',
    run_id='PROPOSED_A11_batch1_A_V1',wave_id='PROPOSED_A11_batch1_A_wave_V1',shard_id='PROPOSED_A11_batch1_A_shard_V1')
paths=dict(output=str(B/'results/A/P11_COMMON_POOL_BATCH1_runs'/identity['run_id']),
    cache=str(B/'work/A/P11_COMMON_POOL_BATCH1_cache'/identity['run_id']),
    claim=str(B/'results/A/P11_COMMON_POOL_BATCH1_claims/P11_A_COMMON_POOL_BATCH1_V1.json'),
    command_record=str(B/'results/A/P11_COMMON_POOL_BATCH1_commands/P11_A_COMMON_POOL_BATCH1_V1.json'))
parents=[];configs=[];seedrows=[]
for i,(task,ordinal,cut) in enumerate(FIXED_SLOTS):
    slug='shelf' if task=='shelf-place-v3' else task.removesuffix('-v3').replace('-','_')
    sid=f'PROPOSED_MT50_{slug}_train_{ordinal:04d}'
    seed_input=f'common_pool_batch_source_v1|{task}|train|{ordinal}|cut{cut}'
    env_seed=int.from_bytes(hashlib.sha256((seed_input+'|env').encode()).digest()[:4],'little')%(2**31-1)
    master_seed=int.from_bytes(hashlib.sha256((seed_input+'|master').encode()).digest()[:8],'little')%(2**63-1)
    source=dict(basecfg['source'],source_id=sid,parent_source_id=sid+'_parent',task=task,ordinal=ordinal,cut=cut,
        env_seed=env_seed,master_seed=master_seed,instruction=PROFILES[task]['instruction'],
        purpose='eight fixed remaining A train slots of original 500-parent coverage plan',
        selection='ordinal0 then1, task dictionary order, skip accepted shelf0; no result-based selection',
        proposal_seed_rule=seed_input)
    sr=write(P/'proposal'/('SOURCE_'+str(i)+'.json'),source)
    key=f'p{i:02d}_{slug}_train{ordinal:04d}_cut{cut}'
    cfg=copy.deepcopy(basecfg);cfg.update(source=source,device=gpu_inventory[i],source_signature=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        source_manifest_ref={k:sr[k] for k in ('path','sha256')}|{'format':'json'},state_contract_sha256=closure_ref['sha256'],
        initialization_source_manifest=str(P/'config'/('INITIALIZATION_'+task+'.json')),
        schema='common_pool_batch_parent_H10_v1')
    cfg['control']['cut']=cut;cfg['native']['device']=gpu_inventory[i]
    cr=write(P/'config'/('PARENT_'+str(i)+'.json'),cfg);configs.append(cfg)
    parent=dict(parent_key=key,source=source,source_ref=sr,config=cr,device=gpu_inventory[i],
        identity=dict(identity,run_id=identity['run_id']+':'+key),
        paths={k:str(Path(paths[k])/key) for k in ('output','cache')},resource_caps=parent_caps(task,cut))
    parents.append(parent);seedrows.append(dict(slot=i,source=source,seed_input=seed_input,owner='A',gpu_uuid=gpu_inventory[i]['gpu_uuid']))
assert len({p['source']['env_seed'] for p in parents})==8
assert all(p['source']['source_id'] not in {x['source']['source_id'] for x in accepted['parents']} for p in parents)
assert all(p['source']['env_seed'] not in {x['source']['env_seed'] for x in accepted['parents']} for p in parents)
write(P/'SOURCE_AND_SEED_PROPOSALS.json',dict(status='UNAUTHORIZED_PROPOSALS_ONLY',sources=seedrows,
    accepted_parent_index=ref(B/'manifests/COMMON_POOL_ACCEPTED_PARENTS_V1.json'),actual_source_seed_or_shard_creation=0,
    next_unassigned_slot=dict(task='stick-push-v3',ordinal=1,cut=55),remaining45_tasks_retained_in_coverage=True))
concurrency=2
command=P/'commands/run_proposed_batch1.sh'
command.write_text('#!/usr/bin/env bash\nset -euo pipefail\nif [ "$#" -ne 1 ]; then exit 64; fi\nexport CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300\nexport PYTHONDONTWRITEBYTECODE=1\ncd '+str(P)+'\nexec '+basecfg['python']+' -B '+str(P/'code/launch.py')+' --release "$1"\n')
checker=P/'commands/check_publication_metadata.sh'
checker.write_text('#!/usr/bin/env bash\nset -euo pipefail\ncd '+str(P)+'\nexec '+basecfg['python']+' -B '+str(P/'code/publication_check.py')+' "$@"\n')
code_ref=write(P/'code/CODE_MANIFEST.json',dict(files=[ref(q) for q in sorted((P/'code').rglob('*.py'))],
    inherited_manifests=[oldproposal['code_manifest']],scope='new isolated overlay plus immutable accepted code chain'))
input_ref=write(P/'INPUT_MANIFEST.json',dict(files=[],inherited_manifests=[oldproposal['input_manifest']],
    CPU_large_weight_rehash=False,existing_input_SHA_bindings_reused=True))
ext_ref=write(P/'EXTERNAL_SOURCE_MANIFEST.json',dict(files=[ref(q) for q in sorted(external)],
    inherited_manifests=[oldproposal['external_manifest']],scope='new five-task Python/XML plus unchanged driver/runtime input identities'))
prep_ref=write(P/'INHERITED_PACKAGE_MANIFEST.json',dict(files=[],inherited_manifests=[oldproposal['preparation_manifest']]))
config_ref=write(P/'CONFIG_MANIFEST.json',dict(files=[ref(q) for q in sorted((P/'config').glob('*.json'))]+[
    ref(P/'SOURCE_AND_SEED_PROPOSALS.json'),source_ref,closure_ref]))
proposal=dict(status='UNAUTHORIZED_PROPOSAL',task_id='A11_COMMON_POOL_BATCH1_V1',task_revision=1,
    release_id='P11_A_COMMON_POOL_BATCH1_V1',owner_host='trial-303224955-trialrun-303224955-worker-0',
    authorization_identity=identity,parents=parents,concurrency=concurrency,
    resource_caps=batch_caps(parents),scheduler_caps=scheduler_caps(concurrency),
    timeouts=batch_timeouts(concurrency),storage=batch_storage(concurrency),paths=paths,
    code_manifest=code_ref,input_manifest=input_ref,external_manifest=ext_ref,inherited_package_manifest=prep_ref,
    source_evidence=source_ref,closure=closure_ref,sidecar_ready=oldproposal['sidecar_ready'],
    config_manifest=config_ref,command_ref=ref(command),accepted_parent_index=ref(B/'manifests/COMMON_POOL_ACCEPTED_PARENTS_V1.json'),
    recommended_concurrency_reason='2 is a conservative proposed first parallel wave under64GiB/worker planning and ample visible host RAM; only1 has measured runtime, cgroup/RSS/IO unknowns require analysis risk decision',
    bound_scene_state_unknowns='new task/cut qualification occurs in that planned parent; no extra reset/probe/tolerance',
    actual_compute_authorized=False,actual_sources_created=False,old_releases_reusable=False)
pr=write(P/'proposal/PROPOSAL.json',proposal)
storage_admission=dict(mode='bounded_batch1',run_id=identity['run_id'],parent_keys=[x['parent_key'] for x in parents],
    project_quota_known=False,exclusive_reservation=False,accepts_monitoring_gaps=True,
    acceptance_scope='this_eight_parent_batch_only_not_500_parent_quota')
release=dict(campaign_id='corrector-sim-20260919',release_id=proposal['release_id'],task_ids=[proposal['task_id']],task_revision=1,
    owner_host=proposal['owner_host'],status='UNAUTHORIZED_TEMPLATE',proposal_sha256=pr['sha256'],
    wave_participants=['A'],max_commands=1,max_claims=1,max_retries=0,storage_admission=storage_admission,
    **{k:proposal[k] for k in ('authorization_identity','parents','concurrency','resource_caps','scheduler_caps','paths','timeouts','storage')})
write(P/'proposal/RELEASE_TEMPLATE.json',release)
board=dict(id=proposal['task_id'],owner='A',status='ready',revision=1,dependencies=['A11_BATCH_SCALING_CPU_V1'],
    release='releases/'+proposal['release_id']+'.json',expected_result='receipts/A/'+proposal['task_id']+'_RESULT.json',
    **{k:identity[k] for k in ('run_id','wave_id','shard_id')})
write(P/'proposal/BOARD_TEMPLATE.json',board)
control=dict(mode='run',formal_gpu_runs_enabled=True,stop_requested=False,active_compute_release_id=proposal['release_id'],
    active_compute_release='releases/'+proposal['release_id']+'.json',active_compute_task_ids=[proposal['task_id']],
    allowed_task_ids=list(dict.fromkeys(read(B/'CONTROL.json')['allowed_task_ids']+[proposal['task_id']])),
    current_compute_limits=proposal['resource_caps'],
    per_task_compute_limits=dict(read(B/'CONTROL.json')['per_task_compute_limits'],**{proposal['task_id']:proposal['resource_caps']}))
write(P/'proposal/CONTROL_TEMPLATE.json',dict(status='UNAUTHORIZED_FRAGMENT_NOT_INSTALLED',proposed_runtime_fields=control))
write(P/'proposal/RESOURCE_BUDGET.json',dict(parents=[dict(parent_key=x['parent_key'],task=x['source']['task'],cut=x['source']['cut'],
    UUID=x['device']['gpu_uuid'],caps=x['resource_caps'],attempt_caps={j:attempt_caps(j,x['source']['task'],x['source']['cut']) for j in basecfg['control']['branch_order']}) for x in parents],
    batch_total_caps=proposal['resource_caps'],scheduler_caps=proposal['scheduler_caps'],
    overhead='each parent includes1 launcher NVML identity plus15 child NVML identities; scheduler makes no additional hardware query',
    entered_charged_once=True,unused_caps_not_reusable=True,cleanup_process_scans_hard_bound=None,
    cleanup_missing_bound_reason='inherited reservation must remain until kernel confirms whole group exit; mandatory drain not time-truncated'))
full_control=read(B/'CONTROL.json');full_control.update(control);full_control['revision']+=1
full_board=read(B/'TASK_BOARD.json');full_board['tasks'].append(board);full_board['revision']+=1
write(P/'proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json',dict(synthetic_metadata_validation_only=True,
    CONTROL=full_control,TASK_BOARD=full_board,RELEASE=dict(release,status='released'),
    active_files_written=False,compute_authorization=False))
for q in (P/'code').rglob('*.py'):ast.parse(q.read_text(),filename=str(q))
print(json.dumps(dict(parents=len(parents),concurrency=concurrency,resource_caps=len(proposal['resource_caps']),
    proposal=pr,actual_sources_or_claims_created=0,real_operations=0)))
