"""Minimal CPU proposal/identity delta. No capacity, hardware or weight checks."""
import copy,difflib,hashlib,json,sys
from pathlib import Path
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1'
S=B/'results/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1'
O=B/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1'
W=B/'work/A/A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1_r1'
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p);raw=p.read_bytes();return dict(path=str(p),realpath=str(p.resolve()),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
prior=read(S/'proposal/PROPOSAL.json')
assert (P/'config/CONFIG.json').read_bytes()==(S/'config/CONFIG.json').read_bytes()
supplement='''This supplement is the immutable successor to the prior supplement_v1, whose READY SHA is dd330a43d5a7b0e6304975d399c561388b3bbb7befd2e609dd223f4a41de9edd. The public interface_v1 and common_pool_sidecar_v1 bytes and all private-cost/aggregate semantics are inherited unchanged.

Only the old rule that all generated_chunk_ref paths must be branch-local is superseded. observation_ref and next_observation_ref remain strictly within the current physical branch with SHA checks. Prefix, G0_old and native suffix chunks keep the local rule. A shared candidate is allowed only during this branch's entered cut commitment, for exactly its requested plan_key.

normal/BANK.json uses private common_pool_bank_v2 metadata: parent_source_id, source_id, cut=5, source_signature, source_manifest_ref, run_id and synthetic scope. Each declared plan_key binds its exact logical_alias_of, raw50_ref path/SHA/format, raw50_realpath, shape=[50,4], dtype=<f4 and size_bytes=800. a0 aliases fresh0 exactly. Normal BRANCH_RESULT anchors BANK path/realpath/SHA/format; prepare_bank_reference and the actual Engine.load_bank verify that anchor, source-manifest content, all six entries and each raw50 payload. This is not a public schema change.

Each non-normal branch saves BANK_REFERENCE_VERIFICATION.json. It is a private SHA-bound whitelist with source context and plan-key mapping. During shared publication, BANK SHA and raw content are checked again and generated_chunk_ref must exactly match the requested key. Being under normal, matching another plan's hash, or presenting an arbitrary external file is insufficient. Candidate keys remain distinct even for bit-identical raw arrays; a0/fresh0 reuse plans only, never Q-C10/G0-C5 outcomes. No BANK payload is copied to each branch.

Public intervened=true means a replacement candidate was committed and at least one commitment engine.step returned, with actual recorder entry and full-state evidence. Precut endings and failures before commitment stay false. Normal is false. G0_old is also false: its private evidence records commitment_entered, returned steps and kind=old_queue_control with plan_replaced=false. Other candidate branches are kind=forced_collection_candidate. online_G0_triggered is always false in this collector; these flags do not claim an online G0 benefit trigger. Failure RESOURCE_LEDGER retains the actual private intervention state; no old evidence is backfilled.

Actual runtime qualification remains unmeasured; linked cases are explicit small synthetic CPU fixtures. B may consume this successor for its current CPU views through shared files. No B acknowledgement, actual sample compatibility or compute authorization is asserted.
'''
(P/'supplement_v2/README.md').write_text(supplement)
positive=W/'targeted_v1/positive'
write(P/'supplement_v2/SYNTHETIC_EXAMPLES.json',dict(synthetic=True,actual_collection=False,
    BANK=ref(positive/'normal/BANK.json'),normal_anchor=ref(positive/'normal/BRANCH_RESULT.json'),
    shared_branches=[dict(branch=n,whitelist_ref=ref(positive/n/'BANK_REFERENCE_VERIFICATION.json'),
        transition_ref=ref(positive/n/'transitions/step005.json'),episode_ref=ref(positive/n/'EPISODE_PUBLIC_V1.json'))
        for n in ('Q_a0_r0','Q_local_plus_r0','Q_local_minus_r0','G0_fresh0_r0','G0_fresh1_r0','G0_fresh2_r0')],
    old_queue_control=ref(positive/'G0_old_r0/EPISODE_PUBLIC_V1.json'),precut=ref(W/'targeted_v1/precut/Q_a0_r0/EPISODE_PUBLIC_V1.json')))
write(P/'supplement_v2/READY.json',dict(status='CPU_SUPPLEMENT_READY',supplement_version=2,
    task_id='A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1',predecessor_ready_ref=ref(S/'supplement_v1/READY.json'),
    original_sidecar_ready_ref=ref(O/'sidecar_v1/READY.json'),public_interface_changed=False,sidecar_v1_changed=False,
    files=[ref(P/'supplement_v2'/f) for f in ('README.md','SYNTHETIC_EXAMPLES.json')],
    producer_refs=[ref(P/'code'/f) for f in ('shared_plans.py','public_records.py','controller.py','intervention.py','sidecar_output.py')],
    compute_authorized=False,B_consumption_status='shared successor available; no B ACK asserted'))

write(P/'CPU_REFERENCE_DELTA.json',dict(status='UNAUTHORIZED_QUOTE',original_numerical_caps_unchanged=116,
    shared_committed_controls_max=90,arithmetic='Q:6x10=60; G0_fresh:6x5=30; G0_old:2x5 local',
    all_model_physics_sampling_delta=0,all_timeout_delta=0,storage_contract_exactly_inherited=True,
    current_capacity_or_quota_reaudit=False,
    additional_CPU_SHA=dict(transition_raw_payload_digest=4500,bytes_per_payload=800,
        normal_result_BANK_anchor_digest=14,loader_BANK_manifest_digest=14,source_manifest_digest=14,
        shared_publish_BANK_manifest_digest=90,whitelist_Store_payload_digest=14,
        BANK_or_source_manifest_each_max_bytes=65536,
        raw_file_verification='per-transition raw file check replaces existing chunk SHA check, not a second physical operation; six loader raw checks retained',
        authorization_passes_max=16,new_overlay_code_refs_per_pass='see CODE_MANIFEST; no additional large-weight pass'),
    additional_metadata=dict(branch_whitelist_files_max=14,each_serialized_hard_bytes=131072,
        allocation='existing per-attempt Store envelope, no writer/log/temp budget expansion',
        existing_BANK_enriched=True,bank_document_read_max_bytes=65536,normal_RESULT_anchor_read_max_bytes=65536,
        full_BANK_raw_copies_per_branch=0),
    original_storage_contract_ref=ref(S/'STORAGE_ADMISSION_CONTRACT.json'),
    accepted_resource_review_ref=ref(B/'manifests/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1_REVIEW.json')))
budget=read(S/'proposal/RESOURCE_BUDGET.json');budget['shared_plan_reference_CPU_delta']=read(P/'CPU_REFERENCE_DELTA.json')
write(P/'proposal/RESOURCE_BUDGET.json',budget)
(P/'proposal/SOURCE_PROPOSAL.json').write_bytes((S/'proposal/SOURCE_PROPOSAL.json').read_bytes())

rows=[];diff=[];patch=[]
for f in sorted((P/'code').rglob('*.py')):
    row=ref(f);rows.append(row);rel=f.relative_to(P/'code');old=S/'code'/rel
    if not old.exists():old=O/'code'/rel
    if old.exists():
        oldref=ref(old);same=oldref['sha256']==row['sha256']
        diff.append(dict(relative_path=str(rel),change='unchanged_bytes_new_package_identity' if same else 'modified',old=oldref,new=row))
        if not same:patch.extend(difflib.unified_diff(old.read_text().splitlines(True),f.read_text().splitlines(True),fromfile=str(old),tofile=str(f)))
    else:diff.append(dict(relative_path=str(rel),change='new_helper',old=None,new=row))
write(P/'code/CODE_MANIFEST.json',dict(files=rows,inherited_manifests=[ref(S/'code/CODE_MANIFEST.json'),ref(O/'code/CODE_MANIFEST.json')],
    import_order='V3 overlay > accepted repair overlay > original collector; frozen native/vendor original',no_large_weight_hashes_in_CPU_task=True))
write(P/'CODE_DIFF.json',dict(files=diff,scope='two producer fixes plus new isolated V3 identity/import paths',inherited_refs=[ref(S/'code/CODE_MANIFEST.json'),ref(O/'code/CODE_MANIFEST.json')]))
(P/'MINIMAL.patch').write_text(''.join(patch))
write(P/'INPUT_MANIFEST.json',dict(files=[],inherited_manifests=[ref(O/'INPUT_MANIFEST.json')],weights_rehashed_now=0))
write(P/'EXTERNAL_SOURCE_MANIFEST.json',dict(files=[],inherited_manifests=[ref(O/'EXTERNAL_SOURCE_MANIFEST.json')],no_driver_queries=True))
prep=[B/'tasks/A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1.md',B/'contracts/A11_SHARED_PLAN_REFERENCE_DECISIONS_V1.md',
    B/'releases/P00_A_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1.json',B/'manifests/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1_REVIEW.json',
    P/'CPU_REFERENCE_DELTA.json',P/'supplement_v2/READY.json',P/'supplement_v2/README.md',P/'supplement_v2/SYNTHETIC_EXAMPLES.json']
write(P/'PREPARATION_INPUT_MANIFEST.json',dict(files=[ref(f) for f in prep],inherited_manifests=[ref(S/'PREPARATION_INPUT_MANIFEST.json'),ref(O/'PREPARATION_INPUT_MANIFEST.json')]))

proposal=copy.deepcopy(prior);task='A11_COMMON_POOL_FIRST_PARENT_V3';release='P11_A_COMMON_POOL_FIRST_PARENT_V3'
proposal['task_id']=task
for key,value in proposal['authorization_identity'].items():
    if type(value) is str:proposal['authorization_identity'][key]=value.replace('_V2','_V3')
for key,value in proposal['paths'].items():proposal['paths'][key]=value.replace('_V2','_V3')
proposal.update(cwd=str(P),command=['bash',str(P/'commands/run_proposed_first_parent.sh'),str(B/'releases'/(release+'.json'))],
    supplementary_protocol_ref=ref(P/'supplement_v2/READY.json'),reference_CPU_delta_ref=ref(P/'CPU_REFERENCE_DELTA.json'),
    current_future_readiness='UNAUTHORIZED; two producer repairs prepared. Bounded-first-parent risk accepted in principle by analysis; separate release still required. Full-state/MJB qualification remains in the same planned parent.')
for key,rel in [('config','config/CONFIG.json'),('budget','proposal/RESOURCE_BUDGET.json'),('code_manifest','code/CODE_MANIFEST.json'),
    ('input_manifest','INPUT_MANIFEST.json'),('external_manifest','EXTERNAL_SOURCE_MANIFEST.json'),('preparation_manifest','PREPARATION_INPUT_MANIFEST.json'),('command_ref','commands/run_proposed_first_parent.sh')]:proposal[key]=ref(P/rel)
proposal['command_sha256']=proposal['command_ref']['sha256']
assert proposal['resource_caps']==prior['resource_caps'] and proposal['storage']==prior['storage'] and proposal['timeouts']==prior['timeouts'] and proposal['source']==prior['source']
assert all(not Path(v).exists() for v in proposal['paths'].values())
write(P/'proposal/PROPOSAL.json',proposal)
rt=read(S/'proposal/RELEASE_TEMPLATE.json');rt.update(status='UNAUTHORIZED_TEMPLATE',identity=proposal['authorization_identity'],release_id=release,task_ids=[task],paths=proposal['paths'],proposal_sha256=ref(P/'proposal/PROPOSAL.json')['sha256'])
rt['storage_admission']['run_id']=proposal['authorization_identity']['run_id']
write(P/'proposal/RELEASE_TEMPLATE.json',rt)
control=read(S/'proposal/CONTROL_TEMPLATE.json');control.update(active_compute_release='releases/'+release+'.json',active_compute_release_id=release,active_compute_task_ids=[task],allowed_task_ids=[task],per_task_compute_limits={task:proposal['resource_caps']})
write(P/'proposal/CONTROL_TEMPLATE.json',control)
board=read(S/'proposal/BOARD_TEMPLATE.json');board['tasks'][0].update(id=task,release='releases/'+release+'.json',**{k:proposal['authorization_identity'][k] for k in ('run_id','wave_id','shard_id')})
write(P/'proposal/BOARD_TEMPLATE.json',board)
write(P/'CAPS_IDENTITY_DIFF.json',dict(status='PASS',unchanged_numerical_caps=116,changed_numerical_caps=0,
    caps=[dict(name=k,old=prior['resource_caps'][k],new=proposal['resource_caps'][k]) for k in sorted(proposal['resource_caps'])],
    source_exact_equal=True,source_file_bytes_equal=(P/'proposal/SOURCE_PROPOSAL.json').read_bytes()==(S/'proposal/SOURCE_PROPOSAL.json').read_bytes(),
    config_file_bytes_equal=True,timeouts_exact_equal=True,storage_exact_equal=True,old_paths=prior['paths'],new_paths=proposal['paths'],future_paths_absent=True))
write(B/'receipts/A/A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1_SUPPLEMENT_READY.json',dict(status='CPU_SUPPLEMENT_READY',
    task_id='A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1',ready_ref=ref(P/'supplement_v2/READY.json'),predecessor_not_modified=True,
    B_dispatch_or_session_modified=False,compute_authorized=False))
print(json.dumps(dict(status='FROZEN_UNAUTHORIZED_V3',code_overlay_files=len(rows),proposal_ref=ref(P/'proposal/PROPOSAL.json'),supplement_ready_ref=ref(P/'supplement_v2/READY.json'))))
