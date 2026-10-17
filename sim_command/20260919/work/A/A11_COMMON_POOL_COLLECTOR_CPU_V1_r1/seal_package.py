import hashlib,json,socket,sys
from datetime import datetime,timezone
from pathlib import Path
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');task='A11_COMMON_POOL_COLLECTOR_CPU_V1'
P=B/'results/A'/task;W=B/'work/A'/f'{task}_r1';receipts=B/'receipts/A'
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p),realpath=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size_bytes=p.stat().st_size)
def write(p,j):
    with p.open('x') as f:json.dump(j,f,ensure_ascii=False,indent=2,sort_keys=True);f.write('\n')
release=B/'releases/P00_A_COMMON_POOL_COLLECTOR_CPU_V1.json';r=read(release);c=read(B/'CONTROL.json');board=read(B/'TASK_BOARD.json')
assert ref(release)['sha256']=='e731cfbd2905b85e5ad5aa81e979cb17ea4851a085b1ee3c05f1e1f390d96dc5'
assert c['revision']==39 and board['revision']==46 and c['mode']=='prepare'
assert not any(c['current_compute_limits'].values()) and socket.gethostname()==r['owner_host']
assert ref(P/'sidecar_v1/READY.json')['sha256']=='56adfa1657553af79e0b740c643ddcc0616520c62c50983594e0cfa72e9650d9'
old=read(P/'INHERITED_CODE.json');new=read(P/'code/CODE_MANIFEST.json');oldby={x['path']:x for x in old['files']};diff=[]
for row in new['files']:
    f=Path(row['path']);assert ref(f)['sha256']==row['sha256'];rel=str(f.relative_to(P/'code'));prior=oldby.get(rel)
    original=None if prior is None else prior.get('origin_sha256') or ref(Path(prior['origin']))['sha256']
    diff.append(dict(path=rel,kind='new' if prior is None else 'unchanged_copy' if original==row['sha256'] else 'modified_private_copy',
        old_sha256=original,new_sha256=row['sha256'],origin=prior['origin'] if prior else None))
write(P/'CODE_DIFF.json',dict(files=diff,summary={k:sum(x['kind']==k for x in diff) for k in ['new','unchanged_copy','modified_private_copy']},old_files_modified=False))
checkpaths=[W/'synthetic_v2/CHECK_RESULT.json',W/'final_delta_v1/RESULT.json',W/'publication_final/CHECK_RESULT.json']
checks=[read(p) for p in checkpaths];assert all(j['status']=='PASS' for j in checks)
initial=read(W/'synthetic_v1/CHECK_RESULT.json');assert initial['status']=='FAIL'
ops={k:initial['operations'].get(k,0)+checks[0]['operations'].get(k,0) for k in set(initial['operations'])|set(checks[0]['operations'])}
write(P/'CPU_CHECKS.json',dict(status='PASS',main_fixture_checks=133,final_delta_checks=21,final_publication_checks=8,
    evidence=[ref(p) for p in checkpaths],earlier_failed_fixture=ref(W/'synthetic_v1/CHECK_RESULT.json'),
    earlier_failure_resolution='test output root made absolute; first failure/partial bytes retained; not a real launcher retry',
    failed_seal_metadata_attempt=ref(W/'SEAL_ATTEMPT_1.json'),
    final_fixture_uses_actual_controller_and_recorder=True,synthetic_operations_across_fixture_attempts=ops,
    actual_signals_or_process_probes=0,actual_claims=0,actual_launcher_invocations=0,real_limits={k:0 for k in r['limits']},
    CPU_interpreter=sys.version,forbidden_module_assertions_passed=True,
    scope_notes=['main fixture preceded final targeted field/cap/storage changes; only relevant delta checks repeated',
      'raw50 float32 synthetic arrays800bytes; no real candidate/trajectory projections or hardware',
      'model/library manifest references inherited; CPU tests do not follow/hash them']))
prop=read(P/'proposal/PROPOSAL.json');open_items=[
 'project quota/exclusive reservation unknown; storage_admission remains null and runtime entry refuses',
 'third-party library temporary/cache write closure unproved; shared free space or environment exports are insufficient',
 'MJB real buffer binding/exact fresh-child bytes and complete shelf runtime qualification unmeasured; first-parent gate only, no added probe',
 'RLIMIT_AS128GiB compatibility with CUDA address reservation unmeasured; no relaxation/retry',
 'B consumption/compatibility receipt not received; no joint integration claim',
 'other49 task support denied; no batch collection or training release']
write(P/'CPU_READY.json',dict(task_id=task,revision=1,status='CPU_READY',outcome='isolated_implementation_and_proposal_pending_analysis',
    future_execution_ready=False,code_manifest=ref(P/'code/CODE_MANIFEST.json'),input_manifest=ref(P/'INPUT_MANIFEST.json'),
    external_manifest=ref(P/'EXTERNAL_SOURCE_MANIFEST.json'),preparation_manifest=ref(P/'PREPARATION_INPUT_MANIFEST.json'),
    code_diff=ref(P/'CODE_DIFF.json'),checks=ref(P/'CPU_CHECKS.json'),sidecar_ready=ref(P/'sidecar_v1/READY.json'),
    future_proposal=ref(P/'proposal/PROPOSAL.json'),field_closure=ref(P/'STATE_FIELD_CLOSURE.json'),support_matrix=ref(P/'SUPPORT_MATRIX.json'),
    real_full_state_verified_attempts=0,real_seed_shard_claim_created=False,collector_or_logger_implemented=True,
    blocked_or_unverified=open_items,all_real_limits_zero=True,public_interface_modified=False,B_feedback_status='not_received'))
items=[]
for root in [P,W]:
    items.extend(p for p in sorted(root.rglob('*')) if p.is_file() and p.name!='EVIDENCE_MANIFEST.json')
items += [receipts/(task+'_ACK.json'),receipts/(task+'_SIDECAR_READY.json')]
files=[ref(p) for p in sorted(set(items))];inodes={}
for p in items:
    st=p.stat();inodes[(st.st_dev,st.st_ino)]=st.st_size
write(P/'EVIDENCE_MANIFEST.json',dict(schema='task_evidence_manifest_v1',task_id=task,files=files,file_count=len(files),
    byte_count_by_path=sum(x['size_bytes'] for x in files),payload_bytes_by_unique_inode=sum(inodes.values()),
    excludes=['this manifest itself','RESULT and post-seal verification/queue receipts'],
    scope='only new task package/work and ACK/sidecar receipt; no inventory rescan or inherited weight hashing',
    retention='all outputs including failed fixtures/partial hardlinks retained; analysis decides keep/defer/delete; deletions0'))
artifacts=[p for p in sorted(P.rglob('*')) if p.is_file() and ('code' not in p.relative_to(P).parts or p.name=='CODE_MANIFEST.json')]
result=dict(campaign_id='corrector-sim-20260919',task_id=task,task_revision=1,owner='A',host=socket.gethostname(),
    executor_session_id='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',status='CPU_READY',outcome='isolated_collector_CPU_implementation_complete_with_open_runtime_admission_gates',
    completed_at_utc=datetime.now(timezone.utc).isoformat(),release=ref(release),ACK=ref(receipts/(task+'_ACK.json')),
    control_revision=39,task_board_revision=46,report=ref(P/'REPORT.md'),CPU_READY=ref(P/'CPU_READY.json'),
    evidence_manifest=ref(P/'EVIDENCE_MANIFEST.json'),artifacts=[ref(p) for p in artifacts],artifact_count=len(artifacts),manifest_file_count=len(files),
    scope='isolated CPU implementation/synthetic tests; no real runtime, active shard or claim',
    checks=dict(main=133,delta=21,final_metadata_shell=8,status='PASS',prior_fixture_failure_preserved=True),
    first_parent_proposed_caps=dict(attempts=15,controls=4500,samples=453,flow=4530,observations=4515,native_resets=780,reset_model=1560,initialization_substeps=390000,caps_count=116),
    current_actual_counts={k:0 for k in r['limits']},synthetic_CPU_operations=ops,
    real_seed_shard_claim_created=False,collector_or_logger_implemented=True,
    old_outputs_control_board_B_modified=False,public_interface_v1_modified=False,
    unresolved_before_collection=open_items,future_compute_authorized=False,automatic_next_stage=False,
    sidecar_ready=ref(P/'sidecar_v1/READY.json'),B_integration_status='shared_consumption_published_feedback_not_received',
    post_seal_audit_path=str(W/'FINAL_VERIFICATION.json'),delivery_target='01a0b91f-355f-7cd1-ae36-412500534ffb')
write(receipts/(task+'_RESULT.json'),result)
print(json.dumps(dict(RESULT=ref(receipts/(task+'_RESULT.json')),REPORT=ref(P/'REPORT.md'),CPU_READY=ref(P/'CPU_READY.json'),
    manifest=ref(P/'EVIDENCE_MANIFEST.json'),artifact_count=len(artifacts),manifest_files=len(files),code_files=len(new['files']),
    code_diff=read(P/'CODE_DIFF.json')['summary'],synthetic_operations=ops),ensure_ascii=False))
