"""Seal this CPU task's new outputs only; no inherited payload/weight sweep."""
import datetime,hashlib,json,socket
from pathlib import Path
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1'
W=B/'work/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1_r1'
TASK='A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1'
def ref(p):
    p=Path(p);raw=p.read_bytes()
    return dict(path=str(p),realpath=str(p.resolve()),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(p):return json.loads(Path(p).read_text())
def write(p,value):Path(p).write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
ack=read(B/'receipts/A'/f'{TASK}_ACK.json')
release=B/'releases/P00_A_COLLECTOR_CONTRACT_CPU_REPAIR_V1.json'
assert ref(release)['sha256']=='56fff8fa38bd6b9d85cceae58defedab78e4831e3520d220419418841484b289'
assert socket.gethostname()==ack['host']
for name in ('CONTROL.json','TASK_BOARD.json'):
    expected=next(r['sha256'] for r in ack['inputs'] if r['path']==name)
    assert ref(B/name)['sha256']==expected
control=read(B/'CONTROL.json');assert control['revision']==40 and control['mode']=='prepare' and all(v==0 for v in control['current_compute_limits'].values())
assert read(B/'TASK_BOARD.json')['revision']==47
r=read(release);assert all(v==0 for v in r['limits'].values())
proposal=read(P/'proposal/PROPOSAL.json')
assert proposal['status']=='UNAUTHORIZED_TEMPLATE' and all(not Path(v).exists() for v in proposal['paths'].values())
assert not (B/'releases/P11_A_COMMON_POOL_FIRST_PARENT_V2.json').exists()
for key in ('config','budget','code_manifest','input_manifest','external_manifest','closure','sidecar_ready','command_ref','preparation_manifest'):
    row=proposal[key];assert ref(row['path'])['sha256']==row['sha256'],key
for row in read(P/'code/CODE_MANIFEST.json')['files']:assert ref(row['path'])['sha256']==row['sha256']
ready=read(P/'supplement_v1/READY.json')
for row in ready['files']+[ready['producer_validation_ref']]:assert ref(row['path'])['sha256']==row['sha256']
assert read(P/'CAPS_DIFF.json')['unchanged_count']==116

artifacts=[P/f for f in [
 'CPU_READY.json','REPORT.md','CPU_CHECKS.json','CODE_DIFF.json','MINIMAL.patch','DIFF.md','CAPS_DIFF.json',
 'PROTECTED_IDENTITIES.json','INPUT_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json','PREPARATION_INPUT_MANIFEST.json',
 'code/CODE_MANIFEST.json','STATE_FIELD_CLOSURE.json','STORAGE_ADMISSION_CONTRACT.json','CPU_CAPACITY_MEMORY_EVIDENCE.json',
 'THIRD_PARTY_WRITE_POINTS.json','proposal/PROPOSAL.json','proposal/RESOURCE_BUDGET.json','proposal/SOURCE_PROPOSAL.json',
 'proposal/RELEASE_TEMPLATE.json','proposal/CONTROL_TEMPLATE.json','proposal/BOARD_TEMPLATE.json',
 'commands/run_proposed_first_parent.sh','supplement_v1/READY.json','supplement_v1/aggregate_index.schema.json',
 'supplement_v1/SYNTHETIC_EXAMPLES.json','supplement_v1/README.md']]
excluded={'EVIDENCE_MANIFEST.json','FINAL_VERIFICATION.json','QUEUE_DELIVERY.json','QUEUE_MESSAGE.json'}
files=[p for root in (P,W) for p in root.rglob('*') if p.is_file() and p.name not in excluded]
files += [B/'receipts/A'/f'{TASK}_ACK.json',B/'receipts/A'/f'{TASK}_SUPPLEMENT_READY.json']
files=sorted(set(files));records=[ref(p) for p in files]
write(P/'EVIDENCE_MANIFEST.json',dict(schema='corrector_cpu_repair_evidence_manifest_v1',task_id=TASK,
    generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=records,
    scope='only new isolated package/work outputs plus ACK/supplement receipt; inherited source manifests referenced, no weight payload traversal',
    file_count=len(records),logical_bytes_including_retained_hardlink_paths=sum(x['size_bytes'] for x in records),
    inherited_code_count=395,new_code_overlay_count=20))
result=dict(campaign_id='corrector-sim-20260919',task_id=TASK,task_revision=1,status='CPU_READY',owner='A',host=socket.gethostname(),
    executor_session_id=ack['executor_session_id'],completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    control_revision=40,task_board_revision=47,release_ref=ref(release),ack_ref=ref(B/'receipts/A'/f'{TASK}_ACK.json'),
    report_ref=ref(P/'REPORT.md'),cpu_ready_ref=ref(P/'CPU_READY.json'),manifest_ref=ref(P/'EVIDENCE_MANIFEST.json'),
    artifact_refs=[ref(p) for p in artifacts],actual_counts=r['limits'],actual_count_semantics='all real runtime operations zero; allowed explicitly synthetic CPU work is separate',
    synthetic_counts=read(P/'CPU_CHECKS.json')['synthetic_counts'],
    validation=dict(status='PASS',unique_targeted_assertions=104,final_entry_checks=2,old133_suite_executed=False,
        initial_CPU_JSON_entry_failure_recorded=True,final_CPU_JSON_entry_PASS=True),
    fixes=['typed Box bound infinities only','single episode identity and complete public null reasons',
        'public cost refs empty and private post-cleanup SHA indices','aggregate no physical alias and all-member qualification index',
        'inherited AS/RAM constraints, no new RLIMIT_AS','bounded first-parent storage and two bounded pre-gate JSONs',
        'independent unauthorized V2 identity and pure JSON publication checker'],
    inherited_public_sidecar_modified=False,shared_files_installed=False,holder_queries_or_stops=0,
    future_proposal_ref=ref(P/'proposal/PROPOSAL.json'),future_source_and_seed_unchanged=True,original_numerical_caps_unchanged_count=116,
    future_compute_authorized=False,future_paths_created=False,actual_collection_authorized=False,
    deployment_cost_view_delivered=False,private_cost_index_semantics='separate private ledgers, not public UUID events',
    unresolved=['real full_state/MJB qualification remains embedded in the original planned parent',
        'project quota/exclusive reservation unknown; statvfs only shared current capacity',
        'third-party/shared-HF/native outside-path writes and between-scan/cleanup overshoot unknown',
        'future process-group RSS peak/hard limit unknown; no implemented RSS monitor'],
    next_action='wait for analysis acceptance; no automatic collection or release reuse')
result_path=B/'receipts/A'/f'{TASK}_RESULT.json';write(result_path,result)
print(json.dumps(dict(status='CPU_READY',artifacts=len(artifacts),manifest_files=len(records),real_limit_keys=len(r['limits']),
    result_ref=ref(result_path),manifest_ref=ref(P/'EVIDENCE_MANIFEST.json'))))
