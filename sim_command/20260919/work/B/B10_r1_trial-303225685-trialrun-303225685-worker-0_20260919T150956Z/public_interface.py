"""Consume A's immutable interface v1; do not edit or extend its published schema."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from b10_adapters import ContractError,require,validate_trajectory

HERE=Path(__file__).resolve().parent
INTERFACE=HERE/'a_interface_v1'

def validator():
    import jsonschema
    ready=json.loads((INTERFACE/'INTERFACE_READY.json').read_text())
    for name,expected in ready['files'].items():
        require(hashlib.sha256((INTERFACE/name).read_bytes()).hexdigest()==expected,'Public interface file identity changed')
    return jsonschema.Draft202012Validator(json.loads((INTERFACE/'interface.schema.json').read_text()))

def validate_record(record,*,allow_synthetic=False):
    json.dumps(record,allow_nan=False)
    validator().validate(record)
    require(allow_synthetic or not record['synthetic'],'Synthetic data cannot enter a real view')
    def walk(value,path=''):
        if value is None:require(bool(record['missing_reasons'].get(path)),'Null lacks missing reason: '+path)
        elif isinstance(value,dict):
            if 'path' in value and str(value['path']).startswith('synthetic://'):require(record['synthetic'],'Synthetic reference in real data')
            for key,item in value.items():
                if key!='missing_reasons':walk(item,key if not path else path+'.'+key)
        elif isinstance(value,list):
            for i,item in enumerate(value):walk(item,f'{path}.{i}')
    walk(record)
    if record['record_type']=='transition':
        length=record['executed_prefix_length']
        require(record['next_step']==record['step']+length,'Actual next observation step differs from executed length')
        for name in ['raw_actions','normalized_actions','rewards','successes']:
            if record[name] is not None:require(len(record[name])==length,'Actual prefix length mismatch: '+name)
        if record['data_origin']=='historical_revealed_held':require(record['split'] in ('historical','development'),'Revealed held data cannot become train/test')
    if record['record_type']=='context':require(record['observation_max_step']<=record['environment_step'],'Context contains future observations')
    return record

def public_to_trajectory(records,*,state_features_by_sha,task_features,state_feature_sha256,language_feature_sha256,allow_synthetic=False):
    require(bool(records),'Empty transition sequence')
    for row in records:
        validate_record(row,allow_synthetic=allow_synthetic)
        require(row['record_type']=='transition','Only transition records are accepted')
        require(row['executed_prefix_length']==1,'Need per-step observations/state features; aggregate endpoint records cannot create intermediate observations')
        for key in ['observation_ref','next_observation_ref','normalized_actions','raw_actions','normalizer_ref','rewards','successes','terminated','truncated']:
            require(row[key] is not None,'Baseline learning field unavailable: '+key)
    first=records[0];last=records[-1]
    for a,b in zip(records,records[1:]):
        require(a['source']==b['source'] and a['split']==b['split'],'Cannot concatenate branch/suffix/split identities')
        require(a['next_step']==b['step'] and a['next_observation_ref']==b['observation_ref'],'Noncontiguous real observations')
        require(a['normalizer_ref']==b['normalizer_ref'] and a['collection_policy']==b['collection_policy'],'Mixed action/model identities')
    refs=[r['observation_ref'] for r in records]+[last['next_observation_ref']]
    for reference in refs[:-1]:require(reference['sha256'] in state_features_by_sha,'Missing frozen policy-state feature')
    first_success=next((r['step']+1 for r in records if r['successes'][0]),None)
    result={'dataset_revision':first['dataset_revision'],'split':first['split'],'task':first['environment']['task'],'instruction':first['environment']['instruction'],**{k:first['source'][k] for k in ('parent_episode_id','source_id','branch_id','suffix_id')},'collection_policy_sha256':first['collection_policy']['checkpoint']['sha256'],'seed':first['seed'],'H':first['H'],'generated_length':first['generated_length'],'executed_prefix_length':first['H'],'normalizer_sha256':first['normalizer_ref']['sha256'],'state_feature_sha256':state_feature_sha256,'language_feature_sha256':language_feature_sha256,'steps':[r['step'] for r in records],'observation_refs':refs,'policy_state':[state_features_by_sha[r['observation_ref']['sha256']] for r in records],'task_features':task_features,'action_policy':[r['normalized_actions'][0] for r in records],'raw_actions':[r['raw_actions'][0] for r in records],'rewards':[r['rewards'][0] for r in records],'successes':[r['successes'][0] for r in records],'first_success_step':first_success,'terminated':[r['terminated'] for r in records],'truncated':[r['truncated'] for r in records],'cut_reason':last['cut_reason'],'generated_chunk_ref':first['generated_chunk_ref'],'outcome_complete':bool(last['terminated'] or last['truncated'] or last['cut_reason'] in ('success','budget','time_limit')),'synthetic_only':first['synthetic']}
    # Only actual recorded prefixes are admissible; this per-step wire view is length one.
    result['executed_prefix_length']=1
    validate_trajectory(result)
    return result

def public_events(ledger,context,*,hardware,synthetic=False,decision_index=0,sampling_index=0,methods=None,research_only=False):
    mapping={'flow_forward':'flow_forward_calls','critic_forward':'critic_forward_calls','critic_backward':'critic_backward_calls','guided_sample':'vla_sampling_calls','monitor':'monitor_calls'}
    keys=['simulator_attempts','env_steps','vla_sampling_calls','flow_forward_calls','vla_backward_calls','critic_forward_calls','critic_backward_calls','monitor_calls','optimizer_updates']
    out=[]
    for event in ledger.events:
        phase=event['status'];units=dict.fromkeys(keys,0)
        # Same operation metadata on all phases. Only unique entered events are summed.
        if event['event_type'] in mapping:units[mapping[event['event_type']]]=event.get('count',1)
        reasons={'device_elapsed':'not measured by this adapter; runtime must attach synchronized device time','timing_parent_id':'root operation in this adapter ledger'}
        if phase=='entered':reasons['wall_end']='operation not complete'
        if phase!='failed':reasons['error']='no failure'
        for name in ['gpu_index','gpu_uuid']:
            if hardware[name] is None:reasons['hardware.'+name]='CPU synthetic execution'
        attribution=([context['method']['name']] if methods is None else list(methods))
        require(not research_only or not attribution,'Research-only events cannot carry deployment attribution')
        row={'interface_version':'corrector-sim-interface/1','synthetic':synthetic,'missing_reasons':reasons,'record_type':'event','identity':deepcopy(context['identity']),'episode_id':context['episode_id'],'event_id':context['identity']['run_id']+'/'+context['episode_id']+'/b10/'+ledger.ledger_id+'/'+str(event['event_id']),'event_type':event['event_type'],'decision_index':decision_index,'sampling_index':sampling_index,'environment_step':context['environment_step'],'phase':phase,'wall_start':event['wall_start'],'wall_end':event['wall_end'],'device_elapsed':None,'timing_parent_id':None,'is_deployment_required_for_methods':attribution,'is_research_only':research_only,'hardware':deepcopy(hardware),'resource_units':units,'measurement_scope':'operation','count':event.get('count',1),'error':event.get('error')}
        validate_record(row,allow_synthetic=synthetic);out.append(row)
    return out

def attach_durable_public_journal(ledger,path,context,**event_options):
    """Bind before real sampling; each entered row is fsynced before its operation.

    Use one unique journal per adapter invocation, with explicit decision/sampling
    indices. The shared aggregator reconciles all files using globally unique IDs.
    CPU tests may use an in-memory ledger; real runtime integration must attach here
    or bridge the same entered/returned callbacks to A's durable EventJournal.
    """
    require(not ledger.events and ledger.on_event is None,'Journal must bind an unused ledger')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.touch(exist_ok=False)
    def append(event):
        proxy=SimpleNamespace(events=[event],ledger_id=ledger.ledger_id)
        row=public_events(proxy,context,**event_options)[0]
        with path.open('a') as handle:
            handle.write(json.dumps(row,allow_nan=False)+'\n');handle.flush();os.fsync(handle.fileno())
    ledger.on_event=append
    return path
