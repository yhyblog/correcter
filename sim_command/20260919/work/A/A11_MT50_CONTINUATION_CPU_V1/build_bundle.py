"""Assemble one unauthorized Batch2 package. No real runtime paths are created."""
from pathlib import Path
import ast,copy,hashlib,json,sys
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');B=ROOT/'Corrector/sim_command/20260919'
P=B/'results/A/A11_MT50_CONTINUATION_CPU_V1';OLD=B/'results/A/A11_BATCH_SCALING_CPU_V1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):
    p=Path(p).resolve();return dict(path=str(p),realpath=str(p),sha256=sha(p),size_bytes=p.stat().st_size)
def write(p,v):
    Path(p).write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n');return ref(p)
disposition=B/'manifests/COMMON_POOL_SOURCE_DISPOSITIONS_V1.json'
(P/'evidence/PROCESSED_SOURCE_DISPOSITIONS.json').write_bytes(disposition.read_bytes())
sys.path.insert(0,str(P/'code'));import inheritance
from task_profiles import PROFILES,FIXED_SLOTS,initialization_caps
from source_plan import source_identity,processed_keys
from budget import parent_caps,batch_caps,batch_timeouts,batch_storage,scheduler_caps,attempt_caps
from pool_protocol import ARMS
old=read(OLD/'proposal/PROPOSAL.json');basecfg=read(OLD/'config/PARENT_0.json')
accepted_path=B/'manifests/COMMON_POOL_ACCEPTED_PARENTS_V2.json';accepted=read(accepted_path);done=read(disposition)
assert accepted['accepted_parent_count']==8 and done['processed_planned_parent_slots']==9
old_state=read(OLD/'STATE_FIELD_CLOSURE.json')
old_state.update(task_allowlist=[x['module']+'.'+x['cls'] for x in PROFILES.values() if x['static_cap_status']=='known'],
    source_evidence=ref(P/'TASK_SOURCE_EVIDENCE.json'),
    status='CPU_MT50_STATIC_SUPPORT;PER_NEW_PARENT_ACTUAL_CLOSURE_UNPROVEN',physical_equality_proven=None,
    schema_name_retained='legacy common_pool_five_task_full_state_v2 encoding/fields/tolerance unchanged; allowlist extended via table',
    other45='static source support only; no live initialization or state proof',
    unresolved_for_future_parent=['every newly selected task/source requires actual exact closure and MJB comparison within its planned parent',
        'unsupported fields or unequal prefix stop parent without fallback/tolerance changes',
        'static caps do not prove physical equality',
        'Batch1 storage risk grant closed; separate Batch2 decision required'])
old_state['groups']['task_python']['basis']=['MT50 task source/base and unchanged typed serializer; no omitted task attributes']
closure_ref=write(P/'STATE_FIELD_CLOSURE.json',old_state)
hardware=read(OLD/'evidence/SAVED_GPU_IDENTITIES.json')['devices']
write(P/'evidence/SAVED_GPU_IDENTITIES.json',dict(source=ref(OLD/'evidence/SAVED_GPU_IDENTITIES.json'),devices=hardware,new_hardware_queries=0))
identity=dict(task_id='A11_COMMON_POOL_BATCH2_V1',release_id='P11_A_COMMON_POOL_BATCH2_V1',node_role='A',
    run_id='PROPOSED_A11_batch2_A_V1',wave_id='PROPOSED_A11_batch2_A_wave_V1',shard_id='PROPOSED_A11_batch2_A_shard_V1')
paths=dict(output=str(B/'results/A/P11_COMMON_POOL_BATCH2_runs'/identity['run_id']),
    cache=str(B/'work/A/P11_COMMON_POOL_BATCH2_cache'/identity['run_id']),
    claim=str(B/'results/A/P11_COMMON_POOL_BATCH2_claims'/f"{identity['release_id']}.json"),
    command_record=str(B/'results/A/P11_COMMON_POOL_BATCH2_commands'/f"{identity['release_id']}.json"))
assert all(not Path(v).exists() for v in paths.values())
evidence=read(P/'TASK_SOURCE_EVIDENCE.json');common=evidence['common_refs'];site=ROOT/'.miniforge3/envs/lerobot/lib/python3.12/site-packages';mw=site/'metaworld'
parents=[];seeds=[]
for i,(task,ordinal,cut) in enumerate(FIXED_SLOTS):
    spec=PROFILES[task];si=source_identity(task,'train',ordinal,cut)
    source=dict(basecfg['source'],**si,task=task,ordinal=ordinal,cut=cut,instruction=spec['instruction'],
        purpose='next8 A train ordinal0/cut5 slots of original500 coverage plan',
        selection='ASCII task names; exclude all processed identities including normal-only; first8; never skip unknown caps')
    sr=write(P/'proposal'/f'SOURCE_{i}.json',source)
    slug=task.removesuffix('-v3').replace('-','_');key=f'p{i:02d}_{slug}_train{ordinal:04d}_cut{cut}'
    hooks=dict(metaworld=str(mw/'__init__.py'),native_class=spec['source_ref']['path'],native_base=str(mw/'sawyer_xyz_env.py'),mujoco_base=str(site/'gymnasium/envs/mujoco/mujoco_env.py'))
    initpath=P/'config'/('INITIALIZATION_'+task+'.json')
    write(initpath,dict(source_hooks=hooks,files=common+[spec['source_ref']],task=task,static_only=True,
        static_task_table=ref(P/'config/MT50_TASK_TABLE.json')))
    cfg=copy.deepcopy(basecfg);cfg.update(source=source,device=hardware[i],
        source_signature=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        source_manifest_ref={k:sr[k] for k in ('path','sha256')}|{'format':'json'},state_contract_sha256=closure_ref['sha256'],
        initialization_source_manifest=str(initpath),schema='common_pool_batch_parent_H10_v1')
    cfg['control']['cut']=cut;cfg['native']['device']=hardware[i]
    cr=write(P/'config'/f'PARENT_{i}.json',cfg)
    # Unknown slots are retained; profile() rejects instead of substituting a task.
    cap=parent_caps(task,cut) if spec['static_cap_status']=='known' else None
    parents.append(dict(parent_key=key,source=source,source_ref=sr,config=cr,device=hardware[i],
        identity=dict(identity,run_id=identity['run_id']+':'+key),paths={k:str(Path(paths[k])/key) for k in ('output','cache')},resource_caps=cap))
    seeds.append(dict(slot=i,source=source,owner='A',gpu_uuid=hardware[i]['gpu_uuid'],task_static_status=spec['static_cap_status'],real_seed_applied=False))
assert len({p['source']['env_seed'] for p in parents})==8
assert all(p['source']['source_id'] not in {x['source']['source_id'] for x in done['parents']} for p in parents)
slots=[];processed=processed_keys(done);by_source={(x['source']['task'],x['source']['split'],x['source'].get('ordinal',0),x['source']['cut']):x['status'] for x in done['parents']}
for task in sorted(PROFILES):
    task_ordinal=PROFILES[task]['wrapper_environment_id']
    for split,count in [('train',8),('development',2)]:
        for ordinal in range(count):
            cut=(5,55)[ordinal%2];owner=('A','B')[ordinal//2%2] if split=='train' else ('A','B')[(task_ordinal+ordinal%2)%2]
            key=(task,split,ordinal,cut)
            slots.append(dict(task=task,split=split,ordinal=ordinal,cut=cut,proposed_owner=owner,
                processed=key in processed,disposition=by_source.get(key,'unattempted'),
                selected_for_this_unauthorized_proposal=split=='train' and (task,ordinal,cut) in FIXED_SLOTS,
                seed=None,seed_reason='not assigned by this all500 identity-only metadata',active_shard=False))
assert sum(x['processed'] for x in slots)==9 and sum(not x['processed'] for x in slots)==491
write(P/'REMAINING_PLAN_IDENTITIES.json',dict(status='CPU_METADATA_NOT_SHARDS',planned=500,processed=9,remaining=491,
    accepted_train=8,accepted_development=0,normal_only=1,identities=slots,
    original_owner_rule_source=ref(B/'results/A/A11_COMMON_POOL_REVISION_CPU_V2/COLLECTION_SHARDS_DRAFT.json'),
    actual_shards_created=False,actual_seed_applications=0))
write(P/'SOURCE_AND_SEED_PROPOSALS.json',dict(status='UNAUTHORIZED_PROPOSALS_ONLY',sources=seeds,
    accepted_parent_index=ref(accepted_path),processed_dispositions=ref(disposition),actual_source_seed_or_shard_creation=0,
    frozen_selection='sort exact50 task names by ASCII, exclude processed A/train/ordinal0/cut5 then take8',
    p04_replacement=False,unknown_task_cap_substitution=False))
command=P/'commands/run_proposed_batch2.sh'
command.write_text('#!/usr/bin/env bash\nset -euo pipefail\nif [ "$#" -ne 1 ]; then exit 64; fi\nexport CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300\nexport PYTHONDONTWRITEBYTECODE=1\ncd '+str(P)+'\nexec '+basecfg['python']+' -B '+str(P/'code/launch.py')+' --release "$1"\n')
checker=P/'commands/check_publication_metadata.sh'
checker.write_text('#!/usr/bin/env bash\nset -euo pipefail\ncd '+str(P)+'\nexec '+basecfg['python']+' -B '+str(P/'code/publication_check.py')+' "$@"\n')
code_ref=write(P/'code/CODE_MANIFEST.json',dict(files=[ref(q) for q in sorted((P/'code').rglob('*.py'))],
    inherited_manifests=[old['code_manifest']],scope='new isolated task table/identity/direct-step metering; immutable accepted code reused'))
inp_ref=write(P/'INPUT_MANIFEST.json',dict(files=[],inherited_manifests=[old['input_manifest']],CPU_large_weight_rehash=False,existing_input_SHA_bindings_reused=True))
ext_ref=write(P/'EXTERNAL_SOURCE_MANIFEST.json',dict(files=read(P/'evidence/NEW_STATIC_EXTERNAL_FILES.json')['files'],
    inherited_manifests=[old['external_manifest']],scope='remaining45 narrow task/shared Python/XML, no payload rehash'))
prep_ref=write(P/'INHERITED_PACKAGE_MANIFEST.json',dict(files=[],inherited_manifests=[old['inherited_package_manifest']]))
config_ref=write(P/'CONFIG_MANIFEST.json',dict(files=[ref(q) for q in sorted((P/'config').glob('*.json'))]+[
    ref(P/'SOURCE_AND_SEED_PROPOSALS.json'),ref(P/'TASK_SOURCE_EVIDENCE.json'),closure_ref,
    ref(P/'evidence/PROCESSED_SOURCE_DISPOSITIONS.json'),ref(P/'REMAINING_PLAN_IDENTITIES.json')]))
proposal=dict(status='UNAUTHORIZED_PROPOSAL',task_id=identity['task_id'],task_revision=1,release_id=identity['release_id'],
    owner_host=old['owner_host'],authorization_identity=identity,parents=parents,concurrency=2,
    resource_caps=batch_caps(parents) if all(p['resource_caps'] is not None for p in parents) else None,
    scheduler_caps=scheduler_caps(2),timeouts=batch_timeouts(2),storage=batch_storage(2),paths=paths,
    code_manifest=code_ref,input_manifest=inp_ref,external_manifest=ext_ref,inherited_package_manifest=prep_ref,
    source_evidence=ref(P/'TASK_SOURCE_EVIDENCE.json'),closure=closure_ref,sidecar_ready=old['sidecar_ready'],
    config_manifest=config_ref,command_ref=ref(command),accepted_parent_index=ref(accepted_path),
    processed_source_dispositions=ref(P/'evidence/PROCESSED_SOURCE_DISPOSITIONS.json'),
    recommended_concurrency_reason='retain measured Batch1 concurrency2; no model reuse or new RAM/IO claim',
    bound_scene_state_unknowns='new8 task/source actual full-state/MJB qualification remains in planned parent; no extra probe',
    blockers=[p['source']['task']+': unknown static cap' for p in parents if p['resource_caps'] is None],
    separate_Batch2_storage_risk_acceptance_required=True,Batch1_risk_grant_reused=False,
    actual_compute_authorized=False,actual_sources_created=False,old_releases_reusable=False)
pr=write(P/'proposal/PROPOSAL.json',proposal)
admission=dict(mode='bounded_batch2',run_id=identity['run_id'],parent_keys=[p['parent_key'] for p in parents],
    project_quota_known=False,exclusive_reservation=False,accepts_monitoring_gaps=False,
    acceptance_scope='this_Batch2_eight_parent_wave_only_not_Batch1_or_500_parent_quota')
release=dict(campaign_id='corrector-sim-20260919',release_id=identity['release_id'],task_ids=[identity['task_id']],task_revision=1,
    owner_host=proposal['owner_host'],status='UNAUTHORIZED_TEMPLATE',proposal_sha256=pr['sha256'],wave_participants=['A'],
    max_commands=1,max_claims=1,max_retries=0,storage_admission=admission,
    **{k:proposal[k] for k in ('authorization_identity','parents','concurrency','resource_caps','scheduler_caps','paths','timeouts','storage')})
write(P/'proposal/RELEASE_TEMPLATE.json',release)
board=dict(id=identity['task_id'],owner='A',status='ready',revision=1,dependencies=['A11_MT50_CONTINUATION_CPU_V1'],
    release='releases/'+identity['release_id']+'.json',expected_result='receipts/A/'+identity['task_id']+'_RESULT.json',
    **{k:identity[k] for k in ('run_id','wave_id','shard_id')})
write(P/'proposal/BOARD_TEMPLATE.json',board)
control=read(B/'CONTROL.json');control.update(revision=control['revision']+1,mode='run',formal_gpu_runs_enabled=True,stop_requested=False,
    active_compute_release_id=identity['release_id'],active_compute_release='releases/'+identity['release_id']+'.json',
    active_compute_task_ids=[identity['task_id']],allowed_task_ids=list(dict.fromkeys(control['allowed_task_ids']+[identity['task_id']])),
    current_compute_limits=proposal['resource_caps'],active_common_pool_batch_preparation_release=None,
    active_batch_risk_acceptance=None)
control['per_task_compute_limits'][identity['task_id']]=proposal['resource_caps']
write(P/'proposal/CONTROL_TEMPLATE.json',dict(status='UNAUTHORIZED_FRAGMENT_NOT_INSTALLED',proposed_runtime_fields=control))
full_board=read(B/'TASK_BOARD.json');full_board['revision']+=1;full_board['tasks'].append(board)
write(P/'proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json',dict(synthetic_metadata_validation_only=True,
    CONTROL=control,TASK_BOARD=full_board,RELEASE=release,
    expected_result='REJECT: unauthorized release and missing independent Batch2 storage risk acceptance',
    active_files_written=False,compute_authorization=False))
write(P/'proposal/RESOURCE_BUDGET.json',dict(parents=[dict(parent_key=p['parent_key'],task=p['source']['task'],cut=5,
    UUID=p['device']['gpu_uuid'],caps=p['resource_caps'],attempt_caps={a[0]:attempt_caps(a[0],p['source']['task'],5) for a in ARMS}) for p in parents],
    batch_total_caps=proposal['resource_caps'],scheduler_caps=proposal['scheduler_caps'],
    unchanged_resource_key_count=116,direct_step_units='charged under existing initialization_physics_substeps only; never double-count do_simulation children',
    entered_charged_once=True,unused_caps_not_reusable=True,cleanup_process_scans_hard_bound=None,
    overhead='8 launcher identity queries plus120 child identities; no extra hardware probes'))
for q in (P/'code').rglob('*.py'):ast.parse(q.read_text(),filename=str(q))
print(json.dumps(dict(proposal=pr,selected=[p['source']['task'] for p in parents],
    cap_count=len(proposal['resource_caps']),total_init_physics=proposal['resource_caps']['initialization_physics_substeps'],
    total_init_forward=proposal['resource_caps']['initialization_mj_forward_calls'],compute_authorized=False,
    runtime_paths_created=False,storage_risk_accepted=False)))
