"""Seal only this CPU task's new artifacts; never scan old data/model trees."""
from pathlib import Path
import datetime,hashlib,json,socket
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');B=ROOT/'Corrector/sim_command/20260919'
P=B/'results/A/A11_BATCH_SCALING_CPU_V1';W=B/'work/A/A11_BATCH_SCALING_CPU_V1'
def read(p):return json.loads(Path(p).read_text())
cache={}
def reference(p):
    p=Path(p).absolute();s=p.stat();key=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
    if key not in cache:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        cache[key]=h.hexdigest()
    return dict(path=str(p),realpath=str(p.resolve()),sha256=cache[key],size_bytes=s.st_size)
def exclusive(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False);f.write('\n')
control=read(B/'CONTROL.json');board=read(B/'TASK_BOARD.json');proposal=read(P/'proposal/PROPOSAL.json')
assert control['revision']==45 and board['revision']==52 and not control['formal_gpu_runs_enabled']
assert all(v==0 for v in control['current_compute_limits'].values())
assert all(not Path(v).exists() for v in proposal['paths'].values())
assert not(B/'releases/P11_A_COMMON_POOL_BATCH1_V1.json').exists()
checks=read(P/'CHECK_INDEX.json');static=read(P/'checks/STATIC_AND_ENTRY_CHECKS.json')
assert checks['status']=='PASS_WITH_RETAINED_CPU_FIXTURE_FAILURES' and static['status']=='PASS'
delivery=dict(status='PASS',at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    current_CONTROL=reference(B/'CONTROL.json'),current_TASK_BOARD=reference(B/'TASK_BOARD.json'),
    current_CPU_release=reference(B/'releases/P00_A_BATCH_SCALING_CPU_V1.json'),
    current_compute_limits_all_zero=True,proposed_compute_release_absent=True,
    proposed_runtime_paths_absent=[dict(kind=k,path=v,exists=False) for k,v in proposal['paths'].items()],
    old12_compute_releases_not_reused=True,old_public_sidecar_supplement_and_B_unchanged=True,
    no_claim_no_launcher_no_GPU_no_holder_operations=True,manifest_scope='new CPU task package/work only; no old data/weight inventory')
exclusive(P/'DELIVERY_CHECKS.json',delivery)
files=[]
for root in (P,W):
    for path in sorted(root.rglob('*')):
        if path.is_file():files.append(reference(path))
manifest=dict(schema='corrector_cpu_evidence_manifest_v1',task_id='A11_BATCH_SCALING_CPU_V1',
    files=files,file_paths=len(files),distinct_inodes_hashed=len(cache),
    synthetic_artifacts_explicitly_separate_from_actual_collection=True,
    inherited_runtime_input_manifests_referenced_not_large_weight_rehashed=True,
    manifest_self_excluded=True,RESULT_and_future_queue_delivery_excluded=True)
exclusive(P/'EVIDENCE_MANIFEST.json',manifest)
names=['REPORT.md','CPU_READY.json','CHECK_INDEX.json','DELIVERY_CHECKS.json','MINIMAL_DIFF.json',
       'TASK_SOURCE_EVIDENCE.json','STATE_FIELD_CLOSURE.json','DEVICE_ASSIGNMENT_STATIC_AUDIT.json',
       'SOURCE_AND_SEED_PROPOSALS.json','SAVED_TIMING_ANALYSIS.json','CAPACITY_AND_THROUGHPUT.json',
       'RESOURCE_QUOTE.md','PROTOCOL_AND_LIFECYCLE.md','proposal/README.md','proposal/PROPOSAL.json',
       'proposal/RESOURCE_BUDGET.json','proposal/RELEASE_TEMPLATE.json','proposal/BOARD_TEMPLATE.json',
       'proposal/CONTROL_TEMPLATE.json','proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json',
       'commands/run_proposed_batch1.sh','commands/check_publication_metadata.sh',
       'checks/PUBLICATION_ENTRY_RESULT.json','checks/STATIC_AND_ENTRY_CHECKS.json',
       'supplement_batch_v1/READY.json','EVIDENCE_MANIFEST.json']
result=dict(campaign_id='corrector-sim-20260919',task_id='A11_BATCH_SCALING_CPU_V1',revision=1,owner='A',
    hostname=socket.gethostname(),status='CPU_READY_UNAUTHORIZED_BATCH1',
    at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    ACK=reference(B/'receipts/A/A11_BATCH_SCALING_CPU_V1_ACK.json'),
    release=reference(B/'releases/P00_A_BATCH_SCALING_CPU_V1.json'),
    products=[dict(name=n,**reference(P/n)) for n in names],
    summary='isolated five-task/cut5-or55 parameterization, fixed8 A train slots and bounded one-reservation multi-parent cold replay; no actual collection',
    unique_behavior_checks=checks['unique_behavior_checks'],static_checks=static['count'],
    checks_status=checks['status'],retained_CPU_fixture_failures=True,
    final_real_process_backend_fake_checks=19,final_scheduler_failure_delta_checks=7,
    proposed_runtime_task='A11_COMMON_POOL_BATCH1_V1',proposed_release_id='P11_A_COMMON_POOL_BATCH1_V1',
    proposed_sources=[dict(parent_key=p['parent_key'],source=p['source'],device=p['device'],resource_caps=p['resource_caps']) for p in proposal['parents']],
    recommended_concurrency=2,measured_concurrency=1,maximum_implemented_concurrency=8,
    concurrency_recommendation_qualification='conditional engineering proposal; only1 measured,64GiB/worker planning plus visible host RAM; cgroup/RSS/VRAM/shared IO unknown; analysis chooses freeze',
    numerical_caps=proposal['resource_caps'],scheduler_caps=proposal['scheduler_caps'],
    timeouts=proposal['timeouts'],storage=proposal['storage'],
    lifecycle='one A-only all8 reservation; each fixed-UUID parent15 sequential cold branches; entire isolated process group exits before data publication and one restoration; no idle subset holder',
    frozen_state_qualification='exact field/MJB closure; runtime validation within each planned parent; unknowns reject without fallback',
    physical_equality_proven=None,existing_accepted_independent_train_parents=1,new_accepted_parents=0,
    observed_saved_parent_wall_seconds=4337.168725160882,
    saved_timing_is_GPU_seconds=False,throughput_prediction=None,actual_disk_IO_bytes=None,
    actual_operations=checks['real_operations'],synthetic_controller_operations=checks['synthetic_controller_counts'],
    actual_future_run_claim_cache_or_source_created=False,actual_B_changes=False,
    no_large_weight_rehash=True,no_deletion=True,old12_compute_releases_reused=False,
    CPU_implementation_blockers=[],
    runtime_unknowns=['new-task/cut55 actual state/MJB qualification','container memory limit, RSS/VRAM peaks',
        'shared IO/pagecache/cold hash/load contention','project quota/outside temp/unlinked/monitor overshoot',
        'unbounded mandatory group drain and lock wait; no hard end-to-end bound'],
    next_action='wait for analysis acceptance; this RESULT grants no compute. No automatic collection/training/evaluation or seed substitution.')
path=B/'receipts/A/A11_BATCH_SCALING_CPU_V1_RESULT.json';exclusive(path,result)
print(json.dumps(dict(status=result['status'],RESULT=reference(path),manifest=reference(P/'EVIDENCE_MANIFEST.json'),
    artifacts=len(names),manifest_files=len(files),unique_behavior_checks=result['unique_behavior_checks'],real_operations=0)))
