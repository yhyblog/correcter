"""Actual stdlib batch publication, shared by runtime and synthetic fixtures."""
from pathlib import Path
from core.contracts import ContractError,configure_store
from audit_indices import private_cost_index,reference
from pool_protocol import ARMS
from sidecar_output import aggregate

def publish_parent(parent,store,cleanup,*,synthetic=False):
    if cleanup.get('status')!='all_formal_group_members_exited':
        raise ContractError('parent publication needs complete batch group exit')
    out=Path(parent['paths']['output']);configure_store(store)
    try:
        store.json('PROCESS_GROUP_EXIT.json',dict(cleanup,synthetic=synthetic,
            parent_key=parent['parent_key'],barrier_scope='whole A batch; no parent-local holder restoration'))
        store.json('ATTEMPT_COVERAGE.json',dict(synthetic=synthetic,planned=[dict(role=n,family=f,repeat=r,
            started=(out/n).exists(),result_present=(out/n/'BRANCH_RESULT.json').exists(),
            sidecar_present=(out/n/'SIDECAR_V1.json').exists()) for n,f,r in ARMS],
            actual_complete_qualification_must_be_read_from_each_sidecar=True,never_fill_missing=True))
        cost=private_cost_index(out,store,synthetic=synthetic);labels=aggregate(out,store)
        return dict(parent_key=parent['parent_key'],labels=labels,private_cost_index=cost,
            synthetic=synthetic,analysis_acceptance_pending=True)
    finally:configure_store(None)

def launcher_index(store,parent,*,synthetic=False):
    parent=Path(parent);files=[];missing=[]
    for path,fmt in [(store.root/'LAUNCH_RESULT.json','private_launch_result_json'),
                     (store.root/'events.jsonl','private_batch_launcher_numeric_jsonl'),
                     (parent/'reserved/PROCESS_GROUP_EXIT.json','whole_wave_process_group_exit'),
                     (parent/'reserved/SCHEDULER_EVENTS.jsonl','private_batch_scheduler_events')]:
        if path.exists():files.append(reference(path,fmt))
        else:missing.append(dict(path=str(path),reason='not entered or not saved; never inferred zero'))
    return store.json('PRIVATE_COST_INDEX.json',dict(schema_version='private_batch_launcher_index_v1',
        synthetic=synthetic,files=files,missing=missing,public_cost_event_refs=[],public_UUID_bridge=False,
        scope='launcher, scheduler and each parent private scope remain separate; per-parent indices live under each reserved directory'))
