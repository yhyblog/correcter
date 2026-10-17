"""Seal CPU preparation evidence; does not authorize or start future runtime."""
from pathlib import Path
import datetime,hashlib,json
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
task='A11_BATCH3_PREP_CPU_V1';P=B/'results/A'/task;W=B/'work/A'/task
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p).resolve();blob=p.read_bytes()
    return dict(path=str(p),realpath=str(p),sha256=hashlib.sha256(blob).hexdigest(),size_bytes=len(blob))
def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
    return ref(p)
proposal=read(P/'proposal/PROPOSAL.json');release=read(P/'proposal/RELEASE_TEMPLATE.json')
check=read(P/'checks/metadata/CHECK_RESULT.json');shell=read(P/'checks/SHELL_SYNTAX.json')
assert check['status']=='PASS' and check['checks']==70
assert all(x['status']=='fulfilled' and x['value']['exit_code']==0 for x in shell['results'])
assert release['status']=='UNAUTHORIZED_TEMPLATE' and not release['storage_admission']['accepts_monitoring_gaps']
assert not proposal['actual_compute_authorized'] and proposal['blockers']==[]
assert all(not Path(x).exists() and not Path(x).parent.exists() for x in proposal['paths'].values())
for name in ('CONTROL.json','TASK_BOARD.json','DISPATCH_A.json'):
    assert (B/name).read_bytes()==(W/'authorization'/name).read_bytes()
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
command=['bash',str(P/'commands/run_proposed_batch3.sh'),str(B/'releases/P11_A_COMMON_POOL_BATCH3_V1.json')]
write(P/'PROPOSED_COMMAND.json',dict(status='UNAUTHORIZED_COMMAND_PROPOSAL_ONLY',cwd=str(P),argv=command,
    frozen_command_ref=ref(P/'commands/run_proposed_batch3.sh'),command_executions=0,
    pure_JSON_publication_checker_command=['bash',str(P/'commands/check_publication_metadata.sh'),
        '--control','FULL_STAGED_CONTROL.json','--board','FULL_STAGED_TASK_BOARD.json','--release','FULL_STAGED_RELEASE.json'],
    positive_fixture_note='checks/metadata RELEASE_SYNTHETIC_ACCEPTED is an isolated fixture, not the independent future release',
    actual_proposal_ref=ref(P/'proposal/PROPOSAL.json'),runtime_paths_created=False))
changes=read(P/'MINIMAL_DIFF.json')
bindings={}
def collect(x,origin):
    if isinstance(x,dict):
        if isinstance(x.get('path'),str) and isinstance(x.get('sha256'),str):
            key=(x['path'],x['sha256'])
            row=bindings.setdefault(key,dict(path=x['path'],sha256=x['sha256'],size_bytes=x.get('size_bytes'),origins=[]))
            row['origins'].append(origin)
        for v in x.values():collect(v,origin)
    elif isinstance(x,list):
        for v in x:collect(v,origin)
for path in sorted(P.rglob('*.json')):
    if 'checks' not in path.relative_to(P).parts:collect(read(path),str(path))
new_ref_errors=[];verified=0
for row in bindings.values():
    path=Path(row['path'])
    if path.is_relative_to(P):
        actual=ref(path);verified+=1
        if actual['sha256']!=row['sha256']:new_ref_errors.append(row['path'])
        row['verification']='current_new_package_bytes'
    else:row['verification']='inherited_frozen_reference; existing acceptance/manifest identity reused; payload not rehashed here'
assert not new_ref_errors
write(P/'REFERENCE_BINDINGS.json',dict(refs=list(bindings.values()),new_package_ref_checks=verified,
    new_ref_errors=new_ref_errors,inherited_payload_rehashes=0,
    future_launcher_still_requires_full_inherited_manifest_SHA_checks=True))
ready=write(P/'CPU_READY.json',dict(task_id=task,task_revision=1,node_role='A',status='CPU_READY',
    at_utc=now,proposal_ref=ref(P/'proposal/PROPOSAL.json'),release_template=ref(P/'proposal/RELEASE_TEMPLATE.json'),
    code_manifest=ref(P/'code/CODE_MANIFEST.json'),resource_quote=ref(P/'RESOURCE_AND_STORAGE_QUOTE.json'),
    checks=ref(P/'CHECK_INDEX.json'),actual_real_operations=read(W/'authorization/P00_A_BATCH3_PREP_CPU_V1.json')['limits'],
    future_compute_authorized=False,actual_runtime_paths_created=False,storage_risk_accepted=False,
    proposed_parent_count=8,proposed_concurrency=2,proposed_attempts=120,
    fixed_source_selection='A/train ordinal0/cut5 first8 remaining exact ASCII task names after17 dispositions',
    existing_accepted_train_parents=16,existing_accepted_dev_parents=0,processed_slots=17,unexecuted_slots=483,
    scientific_initialization_lifecycle_bytes_unchanged=True,metadata_code_files_changed=3,
    repeated_old_suite_count=0,new_GPU_probe_proposals=0,development_owner_table_frozen=False,
    future_release_gates=['analysis accepts CPU package','independent Batch3 storage-risk decision and real release publication',
        'real launcher frozen identity/SHA/current capacity guard','new parent actual initialization/full-state/MJB gates'],
    no_unresolved_CPU_implementation_blocker=True))
ack=B/'receipts/A'/f'{task}_ACK.json'
files=[p for root in (P,W) for p in sorted(root.rglob('*')) if p.is_file() and not p.name.startswith('QUEUE')]
files.append(ack)
manifest=write(P/'EVIDENCE_MANIFEST.json',dict(task_id=task,task_revision=1,created_at_utc=now,
    files=[ref(p) for p in sorted(set(files))],reference_bindings=ref(P/'REFERENCE_BINDINGS.json'),
    original_packages_and_receipts_unchanged=True,CPU_large_weight_and_old_runtime_payload_hashes=0))
result=write(B/'receipts/A'/f'{task}_RESULT.json',dict(task_id=task,task_revision=1,node_role='A',status='CPU_READY',
    created_at_utc=now,ack=ref(ack),cpu_ready=ready,report=ref(P/'REPORT.md'),evidence_manifest=manifest,
    proposal=ref(P/'proposal/PROPOSAL.json'),proposal_sha256=ref(P/'proposal/PROPOSAL.json')['sha256'],
    exact_diff=ref(P/'MINIMAL_DIFF.json'),diff_patch=ref(P/'MINIMAL_DIFF.patch'),
    check_count=70,shell_syntax_checks=2,checks_passed=True,old_suites_rerun=0,
    changed_runtime_code_files=[x['relative'] for x in changes['changed']],unchanged_runtime_code_count=len(changes['unchanged']),
    scientific_initialization_scheduler_lifecycle_changes=False,
    selected_sources=[dict(task=x['source']['task'],source_id=x['source']['source_id'],env_seed=x['source']['env_seed'],
        master_seed=x['source']['master_seed'],owner='A',split='train',ordinal=0,cut=5,device=x['device']) for x in proposal['parents']],
    proposed_resource_caps=proposal['resource_caps'],scheduler_caps=proposal['scheduler_caps'],timeouts=proposal['timeouts'],
    actual_real_operations=read(W/'authorization/P00_A_BATCH3_PREP_CPU_V1.json')['limits'],
    current_compute_authorized=False,future_compute_authorized=False,real_run_cache_shard_claim_created=False,
    bounded_batch3_storage_risk_accepted=False,prior_storage_risk_reused=False,
    door_lock_extra_direct_step_proposal=7800,door_lock_actual_qualification=None,physical_equality_proven=None,
    proposed_non_normal_comparison_branches=112,proposed_candidate_replacement_branches=96,proposed_G0_old_control_branches=16,
    G0_old_intervened=False,G0_old_plan_replaced=False,
    accepted_index_unchanged='COMMON_POOL_ACCEPTED_PARENTS_V3.json',accepted_train_parents=16,accepted_dev_parents=0,
    processed_slots=17,unexecuted_slots=483,old_compute_release_count_closed=14,
    B_modified_or_messaged=False,old_reports_modified=False,
    artifacts=[ref(P/name) for name in ['SOURCE_AND_SEED_PROPOSALS.json','PLAN_COVERAGE_STATUS.json','RESOURCE_AND_STORAGE_QUOTE.json',
        'RESOURCE_QUOTE.md','FULL120_INITIALIZATION_QUOTE.json','STATIC_EVIDENCE_REUSE.json','SAVED_TIMING_REFERENCES.json',
        'PROPOSED_COMMAND.json','REFERENCE_BINDINGS.json','CHECK_INDEX.json','proposal/RESOURCE_BUDGET.json',
        'proposal/RELEASE_TEMPLATE.json','proposal/BOARD_TEMPLATE.json','proposal/CONTROL_TEMPLATE.json','proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json']],
    disposition='Await analysis acceptance and a separate compute release. No automatic next stage.'))
print(json.dumps(dict(status='CPU_READY',result=result,report=ref(P/'REPORT.md'),manifest=manifest,proposal=ref(P/'proposal/PROPOSAL.json')),ensure_ascii=False))
