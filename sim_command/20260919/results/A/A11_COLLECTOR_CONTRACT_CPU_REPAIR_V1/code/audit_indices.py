"""Private cost and logical-aggregate indices; never public UUID cost events."""
import json
from pathlib import Path
from core.contracts import ContractError,sha
from episode_identity import episode_id

def reference(path,format='json'):
    path=Path(path)
    return dict(path=str(path.resolve()),sha256=sha(path),format=format)
def read_reference(ref):
    if sha(ref['path'])!=ref['sha256']:raise ContractError('index reference SHA mismatch')
    return json.loads(Path(ref['path']).read_text())
def private_cost_index(parent,store,*,synthetic=False):
    parent=Path(parent);exit_path=store.root/'PROCESS_GROUP_EXIT.json'
    cleanup=json.loads(exit_path.read_text())
    if cleanup['status']!='all_formal_group_members_exited':raise ContractError('cost index requires exit barrier')
    from pool_protocol import ARMS
    rows=[]
    for name,_,_ in ARMS:
        root=parent/name;ledger=root/'RESOURCE_LEDGER.json'
        files=[];missing=[]
        for filename,fmt in [('RESOURCE_LEDGER.json','private_resource_ledger_json'),
            ('events.jsonl','private_causal_event_v1_jsonl_local_integer_ids'),
            ('numeric_events.jsonl','private_numeric_jsonl'),('initialization_events.jsonl','private_initialization_jsonl'),
            ('graphics_events.jsonl','private_graphics_jsonl')]:
            path=root/filename
            if path.exists():files.append(reference(path,fmt))
            else:missing.append(dict(path=str(path),reason='attempt not entered or file not saved; never inferred zero'))
        rows.append(dict(branch=name,resource_ledger_completed=ledger.exists(),files=files,missing=missing))
    value=dict(schema_version='private_collection_cost_index_v1',synthetic=synthetic,
        public_cost_event_refs=[],public_UUID_bridge=False,process_group_exit_ref=reference(exit_path),
        stage='after child RESOURCE_LEDGER writes and complete group exit',attempts=rows,
        missing_reason='public deployment-cost view not delivered; private entered/returned scopes remain separate')
    return store.json('PRIVATE_COST_INDEX.json',value)

def verify_member(record):
    import sys
    from inheritance import SIDECAR
    if str(SIDECAR) not in sys.path:sys.path.insert(0,str(SIDECAR))
    from validator import validate
    from public_records import validate_public
    validate(record)
    i=record['identity'];expected=episode_id(i['parent_id'],i['branch_id'])
    if i['episode_id']!=expected or i['physical_attempt_id']!=expected or record['record_id']!=expected:
        raise ContractError('member episode identity mismatch')
    e=read_reference(record['record_ref']);validate_public(e)
    if e['synthetic']!=record['synthetic'] or e['episode_id']!=expected or e['source']['source_id']!=i['source_id']:
        raise ContractError('member public reference crosses episode')
    if e['success']!=(None if record['outcome']['success'] is None else bool(record['outcome']['success'])):
        raise ContractError('member outcome/public mismatch')
    s=record['restoration']
    if s['level']=='full_state_verified':
        evidence=read_reference(s['verification_ref'])
        if evidence['level']!='full_state_verified' or evidence['fields']!=s['fields'] or evidence.get('unknown_fields'):
            raise ContractError('member state evidence mismatch')
        read_reference(s['reference_state_ref']);read_reference(s['observed_state_ref'])
    return True

def aggregate_index(store,key,aggregate_ref,label_ref,members,synthetic):
    schema=Path(__file__).resolve().parents[1]/'supplement_v1/aggregate_index.schema.json'
    value=dict(schema_version='common_pool_aggregate_index_v1',schema_sha256=sha(schema),synthetic=synthetic,
        label_key=key,aggregate_sidecar_ref=reference(aggregate_ref['path']),paired_labels_ref=reference(label_ref['path']),
        physical_alias_of=None,represents_new_physical_attempt=False,
        carrier_fields_are_physical_summary=False,members=[dict(arm=m['arm'],repeat_id=m['repeat_id'],
            sidecar_ref=m['sidecar_ref'],qualification_checked_independently=True) for m in members],
        explanation='record_ref is PAIRED_LABELS.json; select labels[label_key]. Carrier outcome/restoration are not applicable; all physical evidence is in independently checked members. Missing repeat stays masked.')
    validate_aggregate_index(value)
    return store.json('AGGREGATE_INDEX_'+key+'.json',value)
def validate_aggregate_index(value):
    from public_records import shape
    schema_path=Path(__file__).resolve().parents[1]/'supplement_v1/aggregate_index.schema.json'
    schema=json.loads(schema_path.read_text());shape(value,schema,schema)
    if value['schema_sha256']!=sha(schema_path):raise ContractError('aggregate index schema SHA mismatch')
    a=read_reference(value['aggregate_sidecar_ref']);labels=read_reference(value['paired_labels_ref'])
    if a['record_ref']!=value['paired_labels_ref'] or value['label_key'] not in labels['labels']:
        raise ContractError('aggregate label target mismatch')
    if not a['repeats']['comparison_arms'] or a['repeats']['repeat_id'] is not None or a['plans']['physical_alias_of'] is not None:
        raise ContractError('aggregate identity/alias mismatch')
    if a['record_id']!=a['identity']['parent_id']+'__aggregate_'+value['label_key']:raise ContractError('aggregate label selector mismatch')
    if a['synthetic']!=value['synthetic'] or labels['synthetic']!=value['synthetic']:raise ContractError('aggregate synthetic scope mismatch')
    members=a['repeats']['paired_members']
    expected=[dict(arm=m['arm'],repeat_id=m['repeat_id'],sidecar_ref=m['sidecar_ref'],qualification_checked_independently=True) for m in members]
    if value['members']!=expected:raise ContractError('aggregate members differ')
    for m in value['members']:verify_member(read_reference(m['sidecar_ref']))
    return True

def launcher_cost_index(store,*,synthetic=False):
    result=store.root/'LAUNCH_RESULT.json'
    value=json.loads(result.read_text())
    paths=[(result,'private_launch_result_json'),(store.root/'events.jsonl','private_parent_numeric_jsonl')]
    child_index=store.root.parent/'reserved/PRIVATE_COST_INDEX.json'
    if child_index.exists():paths.append((child_index,'private_collection_cost_index_v1'))
    files=[reference(p,fmt) for p,fmt in paths if p.exists()]
    return store.json('PRIVATE_COST_INDEX.json',dict(schema_version='private_launcher_cost_index_v1',synthetic=synthetic,
        scope='private parent and per-attempt ledgers remain separate; no public UUID bridge',files=files,
        lifecycle_result_ref=reference(result),lifecycle_entered=value['restoration']['status']!='lifecycle_not_entered_holders_unchanged',
        absent_child_index_reason=None if child_index.exists() else 'reserved stage not reached or index write failed; not inferred zero'))
