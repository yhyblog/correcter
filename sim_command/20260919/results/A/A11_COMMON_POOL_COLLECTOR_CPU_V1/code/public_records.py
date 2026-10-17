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
