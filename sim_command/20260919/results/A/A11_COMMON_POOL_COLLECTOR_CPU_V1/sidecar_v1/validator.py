"""Stdlib validation for the published common_pool_sidecar_v1 schema."""
import hashlib
import json
import re
from pathlib import Path
class SidecarError(ValueError):pass
def validate_shape(value,schema,where='$'):
    if 'anyOf' in schema:
        for choice in schema['anyOf']:
            try:validate_shape(value,choice,where);return
            except SidecarError:pass
        raise SidecarError(where+': no nullable/union branch matches')
    if 'const' in schema and value!=schema['const']:raise SidecarError(where+': const')
    if 'enum' in schema and (value not in schema['enum'] or isinstance(value,bool) and not any(type(x) is bool for x in schema['enum'])):
        raise SidecarError(where+': enum')
    kind=schema.get('type')
    checks={'object':lambda:type(value) is dict,'array':lambda:type(value) is list,
        'string':lambda:type(value) is str,'integer':lambda:type(value) is int,
        'boolean':lambda:type(value) is bool,'null':lambda:value is None}
    if kind and not checks[kind]():raise SidecarError(where+': type '+kind)
    if kind=='object':
        if set(schema.get('required',[]))-value.keys():raise SidecarError(where+': missing required')
        if schema.get('additionalProperties') is False and value.keys()-schema['properties'].keys():
            raise SidecarError(where+': unknown fields')
        for k,v in value.items():
            if k in schema['properties']:validate_shape(v,schema['properties'][k],where+'.'+k)
    if kind=='array':
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',10**9):raise SidecarError(where+': size')
        if schema.get('uniqueItems') and len({json.dumps(x,sort_keys=True) for x in value})!=len(value):raise SidecarError(where+': duplicate')
        for i,v in enumerate(value):validate_shape(v,schema.get('items',{}),where+'['+str(i)+']')
    if kind=='integer' and value<schema.get('minimum',value):raise SidecarError(where+': minimum')
    if kind=='string' and 'pattern' in schema and re.fullmatch(schema['pattern'],value) is None:raise SidecarError(where+': pattern')
def validate(record,schema_path=None):
    path=Path(schema_path) if schema_path else Path(__file__).with_name('schema.json')
    raw=path.read_bytes();schema=json.loads(raw);validate_shape(record,schema)
    if record['schema_sha256']!=hashlib.sha256(raw).hexdigest():raise SidecarError('schema SHA mismatch')
    p=record['protocol'];o=record['outcome'];r=record['repeats'];state=record['restoration']
    if p['absolute_end_step']<p['absolute_start_step']:raise SidecarError('reverse time')
    if p['target_namespace'] in ('Q_C10','G0_C5'):
        if p['parent_absolute_target_state']!=300 or p['cut_step'] is None:raise SidecarError('target missing')
        if p['commitment_steps']!={'Q_C10':10,'G0_C5':5}[p['target_namespace']]:raise SidecarError('C5/C10 mismatch')
        if r['planned_repeat_ids']!=[0,1]:raise SidecarError('planned repeats')
    if not o['outcome_complete'] and o['success'] is not None:raise SidecarError('incomplete label')
    if o['outcome_complete'] and o['success'] is None:raise SidecarError('complete missing label')
    if o['reason'] in ('technical_failure','timeout','quota_exhausted','unknown_timelimit','missing_observation','short_stage_only') and (o['outcome_complete'] or o['success'] is not None):
        raise SidecarError('censored label')
    if o['reason']=='absolute_s300_complete' and o['last_observed_parent_state']!=300:raise SidecarError('absolute horizon')
    if not set(r['valid_pair_repeat_ids'])<=set(r['complete_repeat_ids'])<=set(r['planned_repeat_ids']):raise SidecarError('repeat subsets')
    if state['level']=='full_state_verified':
        if state['unknown_fields'] or not state['fields'] or state['verification_ref'] is None:raise SidecarError('missing full-state evidence')
        if any(f['classification']=='unknown' or f['verdict'] not in ('equal','not_applicable') for f in state['fields']):raise SidecarError('state field not proven')
    if not record['synthetic'] and record['record_ref'] is None:raise SidecarError('real record ref absent')
    return True
