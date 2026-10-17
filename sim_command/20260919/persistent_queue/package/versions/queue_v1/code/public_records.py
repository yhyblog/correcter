"""Small stdlib validator for the unchanged public episode/transition schema."""
import json,math,re
from functools import lru_cache
from core.contracts import CAMPAIGN,sha,ContractError
SCHEMA=CAMPAIGN/'results/A/A10/interface_v1/interface.schema.json'
SHA='7d52f22e9d2e622a18a9a71fdac822ed50413aa3838aa3ad40d98e0bee10500f'
@lru_cache(maxsize=1)
def schema():
    if sha(SCHEMA)!=SHA:raise ContractError('public v1 SHA changed')
    return json.loads(SCHEMA.read_text())
def shape(v,s,root,path='$'):
    if '$ref' in s:return shape(v,root['$defs'][s['$ref'].split('/')[-1]],root,path)
    if 'anyOf' in s:
        for choice in s['anyOf']:
            try:shape(v,choice,root,path);return
            except ContractError:pass
        raise ContractError('public union '+path)
    if 'const' in s and v!=s['const']:raise ContractError('public const '+path)
    if 'enum' in s and v not in s['enum']:raise ContractError('public enum '+path)
    t=s.get('type')
    good={'object':type(v) is dict,'array':type(v) is list,'string':type(v) is str,
        'integer':type(v) is int,'number':type(v) in (int,float) and math.isfinite(v),
        'boolean':type(v) is bool,'null':v is None}
    if t and not good[t]:raise ContractError('public type '+path)
    if t=='object':
        props=s.get('properties',{});extra=s.get('additionalProperties',True)
        if set(s.get('required',[]))-v.keys() or extra is False and v.keys()-props.keys():raise ContractError('public keys '+path)
        for k,x in v.items():
            if k in props:shape(x,props[k],root,path+'.'+k)
            elif isinstance(extra,dict):shape(x,extra,root,path+'.'+k)
    if t=='array':
        if len(v)<s.get('minItems',0):raise ContractError('public array '+path)
        for i,x in enumerate(v):shape(x,s.get('items',{}),root,path+f'[{i}]')
    if t=='string' and (len(v)<s.get('minLength',0) or 'pattern' in s and re.fullmatch(s['pattern'],v) is None):raise ContractError('public string '+path)
    if t in ('integer','number') and v<s.get('minimum',v):raise ContractError('public minimum '+path)
def validate_public(value):
    root=schema();kind=value.get('record_type')
    if kind not in ('episode','transition'):raise ContractError('only collector public records')
    shape(value,root['$defs'][kind],root)
    return True

from pathlib import Path
from episode_identity import episode_id,source_fields
from pool_protocol import unpack,raw_group
from shared_plans import transition_chunk_ref,validate_chunk_ref
NULL_REASONS={
 'train_seed':'training seed is not declared by the inherited policy checkpoint',
 'success':'finite parent outcome incomplete; no terminal success label',
 'first_success_step':'no observed first success',
 'cut_step':'attempt ended before the legal cut',
 'entry_generation_id':'normal trajectory has no cut bank entry',
 'method.training_lineage_ref':'collection checkpoint has no published training-lineage reference',
 'collection_policy.training_lineage_ref':'collection checkpoint has no published training-lineage reference',
 'executed_actions_ref':'executed actions are inline in normalized_actions',
 'a0_ref':'anchor belongs to cut bank/sidecar and is not duplicated in this transition',
 'candidate_family':'normal trajectory has no intervention candidate',
 'suffix_seed':'per-sample immutable plan identity records the stream seed',
 'terminal_success':'transition does not assert a complete terminal parent label',
}
COST_REASON='public deployment-cost view not delivered; actual collection costs are indexed separately in PRIVATE_COST_INDEX.json after ledger cleanup and process exit'
def null_paths(value,prefix=''):
    if value is None:yield prefix
    elif type(value) is dict:
        for key,item in value.items():
            if key!='missing_reasons':yield from null_paths(item,(prefix+'.' if prefix else '')+key)
    elif type(value) is list:
        for i,item in enumerate(value):yield from null_paths(item,prefix+'.'+str(i))
def complete_missing_reasons(record):
    for key in null_paths(record):
        if key not in NULL_REASONS:raise ContractError('unclassified public null '+key)
        record['missing_reasons'][key]=NULL_REASONS[key]
    return record
_shape_validate_public=validate_public
def validate_public(value):
    _shape_validate_public(value)
    for key in null_paths(value):
        if not isinstance(value.get('missing_reasons',{}).get(key),str) or not value['missing_reasons'][key].strip():
            raise ContractError('public null reason missing '+key)
    source=value['source'];eid=episode_id(source['parent_episode_id'],source['branch_id'])
    if value['record_type']=='episode':
        if value['episode_id']!=eid:raise ContractError('episode identity mismatch')
        if value['cost_event_refs']!=[] or not value['missing_reasons'].get('cost_event_refs'):raise ContractError('private costs cannot be public UUID refs')
    else:
        if value['next_step']!=value['step']+value['executed_prefix_length']:raise ContractError('transition step mismatch')
        for key in ('normalized_actions','raw_actions','rewards','successes'):
            if len(value[key])!=value['executed_prefix_length']:raise ContractError('transition inline length mismatch')
    return True

def make_transition(engine,raw_plan,raw_index,action,reward,success,terminated,truncated,step,key):
    source=engine.cfg['source'];method=engine.cfg['collection_policy']
    record=dict(interface_version='corrector-sim-interface/1',synthetic=engine.synthetic,missing_reasons={},
        record_type='transition',identity=engine.identity,dataset_revision='MT50_H10_COMMON_FIRST_PARENT_V1',
        split=source['split'],environment=dict(name='MetaWorld',version='3.0.0',task=engine.task,instruction=source['instruction']),
        source=source_fields(source,engine.job[0],engine.job[2]),
        collection_policy=method,seed=source['env_seed'],step=step,H=10,generated_length=50,executed_prefix_length=1,
        observation_ref=engine.last_observation,proprioception=engine.last_proprio,
        next_observation_ref=None,next_step=step+1,raw_actions=[list(unpack(raw_plan)[raw_index*4:raw_index*4+4])],
        normalized_actions=[action],normalizer_ref=engine.cfg['normalizer_ref'],generated_chunk_ref=transition_chunk_ref(engine,raw_plan,step),
        executed_actions_ref=None,rewards=[float(reward)],successes=[success],first_success_step=step+1 if success else None,
        terminated=bool(terminated),truncated=bool(truncated),cut_reason=f'prescheduled_cut{engine.cut}_no_G0_call',
        anchor_id=source['parent_source_id']+f':cut{engine.cut}',a0_ref=None,candidate_family=engine.job[1],
        raw_alias_group=raw_group(raw_plan,10),suffix_seed=None,terminal_success=None,data_origin='new')
    return record

def publish_transition(engine,transition,next_ref,step):
    transition.update(next_observation_ref=next_ref,next_step=step)
    expected=episode_id(engine.cfg['source']['parent_source_id'],engine.job[0])
    if episode_id(transition['source']['parent_episode_id'],transition['source']['branch_id'])!=expected:
        raise ContractError('cross-episode transition identity')
    if transition['source']!=source_fields(engine.cfg['source'],engine.job[0],engine.job[2]):raise ContractError('transition source/branch identity mismatch')
    for key in ('observation_ref','next_observation_ref'):
        ref=transition[key];path=Path(ref['path'])
        if not path.resolve().is_relative_to(engine.out.resolve()) or sha(path)!=ref['sha256']:
            raise ContractError('cross-episode or dangling transition reference '+key)
    validate_chunk_ref(engine,transition)
    complete_missing_reasons(transition);validate_public(transition)
    return engine.store.json(f'transitions/step{step-1:03d}.json',transition)
