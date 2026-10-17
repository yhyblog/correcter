"""CPU-only Batch3 metadata assembly; no model imports or actual run paths."""
from pathlib import Path
import copy,datetime,difflib,hashlib,json,sys
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A11_BATCH3_PREP_CPU_V1';W=B/'work/A/A11_BATCH3_PREP_CPU_V1'
OLD=B/'results/A/A11_MT50_CONTINUATION_CPU_V1'
def cpu_guard(event,args):
    if event=='import' and args[0].split('.')[0] in {'torch','mujoco','metaworld','pynvml','OpenGL'}:
        raise RuntimeError('CPU-only forbidden import '+args[0])
    if event in {'ctypes.dlopen','subprocess.Popen','os.system','os.kill','os.fork'}:
        raise RuntimeError('CPU-only forbidden operation '+event)
sys.addaudithook(cpu_guard)
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p).resolve();raw=p.read_bytes()
    return dict(path=str(p),realpath=str(p),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')
    return ref(p)
for name in ('code','config','evidence','proposal','commands','tests','checks'):
    (P/name).mkdir()
changes={
    'authorization.py': [('A11_COMMON_POOL_BATCH2_V1','A11_COMMON_POOL_BATCH3_V1'),('P11_A_COMMON_POOL_BATCH2_V1','P11_A_COMMON_POOL_BATCH3_V1'),('Batch2','Batch3')],
    'budget.py':[('bounded_batch2','bounded_batch3'),('Batch2 freezes concurrency2','Batch3 freezes concurrency2')],
    'batch_storage.py':[('bounded_batch2','bounded_batch3'),('this_Batch2_eight_parent_wave_only_not_Batch1_or_500_parent_quota','this_Batch3_eight_parent_wave_only_not_Batch1_Batch2_or_500_parent_quota')],
}
old_code=read(OLD/'code/CODE_MANIFEST.json')
code_diffs=[];unchanged=[];patch=[]
for entry in old_code['files']:
    source=Path(entry['path']);relative=source.relative_to(OLD/'code')
    assert source.suffix=='.py'
    raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==entry['sha256']
    target=P/'code'/relative;target.parent.mkdir(parents=True,exist_ok=True)
    text=raw.decode()
    for before,after in changes.get(str(relative),[]):
        assert before in text,(relative,before)
        text=text.replace(before,after)
    with target.open('xb') as f:f.write(text.encode())
    row=dict(relative=str(relative),previous=ref(source),new=ref(target))
    if raw==target.read_bytes():unchanged.append(row)
    else:
        code_diffs.append(row)
        patch.extend(difflib.unified_diff(raw.decode().splitlines(True),text.splitlines(True),fromfile=str(source),tofile=str(target)))
assert {x['relative'] for x in code_diffs}==set(changes)
for name in ('config/MT50_TASK_TABLE.json','TASK_SOURCE_EVIDENCE.json'):
    with (P/name).open('xb') as f:f.write((OLD/name).read_bytes())
disposition=B/'manifests/COMMON_POOL_SOURCE_DISPOSITIONS_V2.json'
accepted_path=B/'manifests/COMMON_POOL_ACCEPTED_PARENTS_V3.json'
with (P/'evidence/PROCESSED_SOURCE_DISPOSITIONS.json').open('xb') as f:f.write(disposition.read_bytes())
accepted=read(accepted_path);done=read(disposition)
assert accepted['accepted_parent_count']==16 and done['processed_planned_parent_slots']==17
sys.path.insert(0,str(P/'code'));import inheritance
from task_profiles import PROFILES,FIXED_SLOTS
from source_plan import source_identity,processed_keys
from budget import parent_caps,batch_caps,batch_timeouts,batch_storage,scheduler_caps,attempt_caps
from pool_protocol import ARMS
expected=read(W/'authorization/P00_A_BATCH3_PREP_CPU_V1.json')['proposed_next_tasks']
assert FIXED_SLOTS==[(task,0,5) for task in expected]
prior=read(OLD/'proposal/PROPOSAL.json');basecfg=read(OLD/'config/PARENT_0.json')
closure=read(OLD/'STATE_FIELD_CLOSURE.json')
closure.update(source_evidence=ref(P/'TASK_SOURCE_EVIDENCE.json'),
    status='CPU_STATIC_TABLE_REUSED;BATCH3_PARENT_ACTUAL_CLOSURE_UNPROVEN',
    unresolved_for_future_parent=['each new task/source needs the original exact captured-field/MJB gate in its planned parent',
        'unsupported fields or unequal prefix stop parent without fallback/tolerance change',
        'static initialization caps do not prove physical equality',
        'independent Batch3 storage risk acceptance required; earlier grants confer no authority'])
closure_ref=write(P/'STATE_FIELD_CLOSURE.json',closure)
hardware=read(OLD/'evidence/SAVED_GPU_IDENTITIES.json')['devices']
write(P/'evidence/SAVED_GPU_IDENTITIES.json',dict(source=ref(OLD/'evidence/SAVED_GPU_IDENTITIES.json'),devices=hardware,new_hardware_queries=0))
identity=dict(task_id='A11_COMMON_POOL_BATCH3_V1',release_id='P11_A_COMMON_POOL_BATCH3_V1',node_role='A',
    run_id='PROPOSED_A11_batch3_A_V1',wave_id='PROPOSED_A11_batch3_A_wave_V1',shard_id='PROPOSED_A11_batch3_A_shard_V1')
paths=dict(output=str(B/'results/A/P11_COMMON_POOL_BATCH3_runs'/identity['run_id']),
    cache=str(B/'work/A/P11_COMMON_POOL_BATCH3_cache'/identity['run_id']),
    claim=str(B/'results/A/P11_COMMON_POOL_BATCH3_claims'/f"{identity['release_id']}.json"),
    command_record=str(B/'results/A/P11_COMMON_POOL_BATCH3_commands'/f"{identity['release_id']}.json"))
assert all(not Path(v).exists() and not Path(v).parent.exists() for v in paths.values())
evidence=read(P/'TASK_SOURCE_EVIDENCE.json');parents=[];seeds=[]
for i,(task,ordinal,cut) in enumerate(FIXED_SLOTS):
    spec=PROFILES[task];si=source_identity(task,'train',ordinal,cut)
    source=dict(basecfg['source'],**si,task=task,ordinal=ordinal,cut=cut,instruction=spec['instruction'],
        purpose='next8 A train ordinal0/cut5 slots of original500 coverage plan',
        selection='ASCII task names; exclude all17 processed identities including normal-only; first8; never skip unknown caps')
    sr=write(P/'proposal'/f'SOURCE_{i}.json',source)
    key=f"p{i:02d}_{task.removesuffix('-v3').replace('-','_')}_train{ordinal:04d}_cut{cut}"
    old_init=read(OLD/'config'/f"INITIALIZATION_{basecfg['source']['task']}.json")
    hooks=dict(old_init['source_hooks'],native_class=spec['source_ref']['path'])
    initpath=P/'config'/f'INITIALIZATION_{task}.json'
    write(initpath,dict(source_hooks=hooks,files=evidence['common_refs']+[spec['source_ref']],task=task,static_only=True,
        static_task_table=ref(P/'config/MT50_TASK_TABLE.json')))
    cfg=copy.deepcopy(basecfg);cfg.update(source=source,device=hardware[i],
        source_signature=hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        source_manifest_ref={k:sr[k] for k in ('path','sha256')}|{'format':'json'},
        state_contract_sha256=closure_ref['sha256'],initialization_source_manifest=str(initpath))
    cfg['control']['cut']=cut;cfg['native']['device']=hardware[i]
    cr=write(P/'config'/f'PARENT_{i}.json',cfg)
    cap=parent_caps(task,cut) if spec['static_cap_status']=='known' else None
    parents.append(dict(parent_key=key,source=source,source_ref=sr,config=cr,device=hardware[i],
        identity=dict(identity,run_id=identity['run_id']+':'+key),paths={k:str(Path(paths[k])/key) for k in ('output','cache')},resource_caps=cap))
    seeds.append(dict(slot=i,source=source,owner='A',gpu_uuid=hardware[i]['gpu_uuid'],task_static_status=spec['static_cap_status'],real_seed_applied=False))
processed=processed_keys(done)
assert len(processed)==17 and not any((t,'train',o,c) in processed for t,o,c in FIXED_SLOTS)
write(P/'PLAN_COVERAGE_STATUS.json',dict(status='CPU_IDENTITIES_ONLY_NOT_SHARDS',planned=500,processed=17,remaining=483,
    accepted_train=16,accepted_development=0,normal_only=1,
    processed_keys=[dict(task=t,split=s,ordinal=o,cut=c) for t,s,o,c in sorted(processed)],
    selected_fixed_slots=FIXED_SLOTS,actual_shards_created=False,actual_seed_applications=0,
    development_owner_note='unfrozen: future explicit actual task name -> task ordinal -> owner mapping and SHA required; wrapper/dictionary/language IDs not substituted',
    all500_owner_recalculation_performed=False))
write(P/'SOURCE_AND_SEED_PROPOSALS.json',dict(status='UNAUTHORIZED_PROPOSALS_ONLY',sources=seeds,
    accepted_parent_index=ref(accepted_path),processed_dispositions=ref(disposition),actual_source_seed_or_shard_creation=0,
    frozen_selection='exact50 ASCII names; exclude all17 processed slots including normal-only; next8 A/train0/cut5',
    p04_replacement=False,unknown_task_cap_substitution=False))
command=P/'commands/run_proposed_batch3.sh'
with command.open('x') as f:f.write('#!/usr/bin/env bash\nset -euo pipefail\nif [ "$#" -ne 1 ]; then exit 64; fi\nexport CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300\nexport PYTHONDONTWRITEBYTECODE=1\ncd '+str(P)+'\nexec '+basecfg['python']+' -B '+str(P/'code/launch.py')+' --release "$1"\n')
with (P/'commands/check_publication_metadata.sh').open('x') as f:f.write('#!/usr/bin/env bash\nset -euo pipefail\ncd '+str(P)+'\nexec '+basecfg['python']+' -B '+str(P/'code/publication_check.py')+' "$@"\n')
code_ref=write(P/'code/CODE_MANIFEST.json',dict(files=[ref(P/'code'/x['relative']) for x in code_diffs+unchanged],
    inherited_manifests=[prior['code_manifest']],scope='only Batch3 authority/path storage-mode constants changed; scientific and lifecycle bytes reused'))
inp_ref=write(P/'INPUT_MANIFEST.json',dict(files=[],inherited_manifests=[prior['input_manifest']],CPU_large_weight_rehash=False))
ext_ref=write(P/'EXTERNAL_SOURCE_MANIFEST.json',dict(files=[],inherited_manifests=[prior['external_manifest']],scope='accepted50 task/source manifest reused; no external Python/XML re-audit'))
prep_ref=write(P/'INHERITED_PACKAGE_MANIFEST.json',dict(files=[],inherited_manifests=[prior['inherited_package_manifest']]))
config_ref=write(P/'CONFIG_MANIFEST.json',dict(files=[ref(q) for q in sorted((P/'config').glob('*.json'))]+[
    ref(P/'SOURCE_AND_SEED_PROPOSALS.json'),ref(P/'TASK_SOURCE_EVIDENCE.json'),closure_ref,
    ref(P/'evidence/PROCESSED_SOURCE_DISPOSITIONS.json'),ref(P/'PLAN_COVERAGE_STATUS.json')]))
proposal=dict(status='UNAUTHORIZED_PROPOSAL',task_id=identity['task_id'],task_revision=1,release_id=identity['release_id'],
    owner_host=prior['owner_host'],authorization_identity=identity,parents=parents,concurrency=2,
    resource_caps=batch_caps(parents) if all(x['resource_caps'] is not None for x in parents) else None,
    scheduler_caps=scheduler_caps(2),timeouts=batch_timeouts(2),storage=batch_storage(2),paths=paths,
    code_manifest=code_ref,input_manifest=inp_ref,external_manifest=ext_ref,inherited_package_manifest=prep_ref,
    source_evidence=ref(P/'TASK_SOURCE_EVIDENCE.json'),closure=closure_ref,sidecar_ready=prior['sidecar_ready'],
    config_manifest=config_ref,command_ref=ref(command),accepted_parent_index=ref(accepted_path),
    processed_source_dispositions=ref(P/'evidence/PROCESSED_SOURCE_DISPOSITIONS.json'),
    recommended_concurrency_reason='retain accepted Batch1/2 concurrency2; no model reuse or linear-speedup claim',
    bound_scene_state_unknowns='Batch3 task/source initialization/full-state/MJB qualification only in future planned parent; door-lock static only',
    blockers=[x['source']['task']+': unknown static cap' for x in parents if x['resource_caps'] is None],
    separate_Batch3_storage_risk_acceptance_required=True,prior_batch_risk_grants_reused=False,
    actual_compute_authorized=False,actual_sources_created=False,old_releases_reusable=False)
pr=write(P/'proposal/PROPOSAL.json',proposal)
admission=dict(mode='bounded_batch3',run_id=identity['run_id'],parent_keys=[x['parent_key'] for x in parents],
    project_quota_known=False,exclusive_reservation=False,accepts_monitoring_gaps=False,
    acceptance_scope='this_Batch3_eight_parent_wave_only_not_Batch1_Batch2_or_500_parent_quota')
release=dict(campaign_id='corrector-sim-20260919',release_id=identity['release_id'],task_ids=[identity['task_id']],task_revision=1,
    owner_host=proposal['owner_host'],status='UNAUTHORIZED_TEMPLATE',proposal_sha256=pr['sha256'],wave_participants=['A'],
    max_commands=1,max_claims=1,max_retries=0,storage_admission=admission,
    **{k:proposal[k] for k in ('authorization_identity','parents','concurrency','resource_caps','scheduler_caps','paths','timeouts','storage')})
write(P/'proposal/RELEASE_TEMPLATE.json',release)
board=dict(id=identity['task_id'],owner='A',status='ready',revision=1,dependencies=['A11_BATCH3_PREP_CPU_V1'],
    release='releases/'+identity['release_id']+'.json',expected_result='receipts/A/'+identity['task_id']+'_RESULT.json',
    **{k:identity[k] for k in ('run_id','wave_id','shard_id')})
write(P/'proposal/BOARD_TEMPLATE.json',board)
control=read(W/'authorization/CONTROL.json')
control.update(revision=control['revision']+1,mode='run',formal_gpu_runs_enabled=True,stop_requested=False,
    active_compute_release_id=identity['release_id'],active_compute_release='releases/'+identity['release_id']+'.json',
    active_compute_task_ids=[identity['task_id']],allowed_task_ids=control['allowed_task_ids']+[identity['task_id']],
    current_compute_limits=proposal['resource_caps'],active_common_pool_batch_preparation_release=None,active_batch_risk_acceptance=None)
control['per_task_compute_limits'][identity['task_id']]=proposal['resource_caps']
write(P/'proposal/CONTROL_TEMPLATE.json',dict(status='UNAUTHORIZED_FRAGMENT_NOT_INSTALLED',proposed_runtime_fields=control))
full_board=read(W/'authorization/TASK_BOARD.json');full_board['revision']+=1;full_board['tasks'].append(board)
write(P/'proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json',dict(synthetic_metadata_validation_only=True,CONTROL=control,TASK_BOARD=full_board,RELEASE=release,
    expected_result='REJECT: unauthorized release and independent Batch3 risk not accepted',active_files_written=False,compute_authorization=False))
write(P/'proposal/RESOURCE_BUDGET.json',dict(parents=[dict(parent_key=x['parent_key'],task=x['source']['task'],cut=5,
    UUID=x['device']['gpu_uuid'],caps=x['resource_caps'],attempt_caps={a[0]:attempt_caps(a[0],x['source']['task'],5) for a in ARMS}) for x in parents],
    batch_total_caps=proposal['resource_caps'],scheduler_caps=proposal['scheduler_caps'],unchanged_resource_key_count=116,
    direct_step_units='door-lock static extra520/attempt; same measured box-close hook; door-lock not empirically validated',
    entered_charged_once=True,unused_caps_not_reusable=True,cleanup_process_scans_hard_bound=None))
write(P/'MINIMAL_DIFF.json',dict(changed=code_diffs,unchanged=unchanged,
    scientific_initialization_and_scheduler_bytes_unchanged=True,public_and_sidecar_unchanged=True,
    changes_only='Batch3 TASK/RELEASE and storage mode/scope string constants; no numerical changes',
    previous_fixture_refs=[ref(OLD/'CHECK_INDEX.json'),ref(OLD/'checks/targeted01/CHECK_RESULT.json'),
        ref(B/'manifests/A11_MT50_CONTINUATION_CPU_V1_ACCEPTANCE.json')],
    old_full_suite_rerun=False))
with (P/'MINIMAL_DIFF.patch').open('x') as f:f.write(''.join(patch))
write(P/'STATIC_EVIDENCE_REUSE.json',dict(table_original=ref(OLD/'config/MT50_TASK_TABLE.json'),table_copy=ref(P/'config/MT50_TASK_TABLE.json'),
    source_evidence_original=ref(OLD/'TASK_SOURCE_EVIDENCE.json'),source_evidence_copy=ref(P/'TASK_SOURCE_EVIDENCE.json'),
    Batch2_acceptance=ref(B/'manifests/A11_COMMON_POOL_BATCH2_V1_ACCEPTANCE.json'),
    Batch2_direct_metering=ref(B/'results/A/A11_COMMON_POOL_BATCH2_V1/INITIALIZATION_STAGE_AUDIT.json'),
    box_close_direct_actual=7800,door_lock_direct_actual=None,door_lock_extra_proposed=7800,
    old_external_source_reaudits=0,old_large_run_payload_rehashes=0,hardware_queries=0))
assert all(not Path(v).exists() and not Path(v).parent.exists() for v in paths.values())
write(W/'BUILD_RESULT.json',dict(status='BUILT_UNAUTHORIZED',proposal=pr,changed_code_files=len(code_diffs),unchanged_code_files=len(unchanged),
    cap_keys=len(proposal['resource_caps']),selected=expected,real_operations=0,runtime_paths_created=False))
print(json.dumps(read(W/'BUILD_RESULT.json'),ensure_ascii=False))
