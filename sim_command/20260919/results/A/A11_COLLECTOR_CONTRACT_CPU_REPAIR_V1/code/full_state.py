"""Typed exact field comparison. No native import; runtime supplies actual reads."""
import hashlib,json,math,struct,sys
from core.contracts import ContractError
STATE_SCHEMA='shelf_full_state_v1'
MAX_FIELDS=2048
REQUIRED=['identity','integration','mutable_model','task_python','wrapper_python',
          'rng','clocks','queue_history','callbacks_plugins']
from state_attrs import BoxBound
def typed(v, *, box_field=None):
    if type(v) is BoxBound:
        if box_field not in ('low','high') or v.field!=box_field:raise ContractError('Box bound outside declared metadata field')
        import numpy as np
        a=v.array
        if type(a) is not np.ndarray or a.dtype.kind not in 'fiu' or a.nbytes>8*1024**2:raise ContractError('invalid Box bound array')
        if a.dtype.kind=='f' and np.isnan(a).any():raise ContractError('NaN Box bound')
        return dict(type='Box_bound_metadata',field=v.field,dtype=a.dtype.str,shape=list(a.shape),bytes=a.tobytes(order='C').hex())
    if v is None or type(v) in (bool,int,str):return {'type':type(v).__name__,'value':v}
    if type(v) is float:
        if not math.isfinite(v):raise ContractError('nonfinite scalar state')
        return {'type':'float64','bits':struct.pack('<d',v).hex()}
    if type(v) is bytes:return {'type':'bytes','bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()}
    if type(v) in (list,tuple):return {'type':type(v).__name__,'items':[typed(x) for x in v]}
    if type(v) is dict:
        if any(type(k) is not str for k in v):raise ContractError('nonstring state key')
        return {'type':'dict','items':{k:typed(v[k]) for k in sorted(v)}}
    module=type(v).__module__
    if module.startswith('numpy') and hasattr(v,'dtype') and hasattr(v,'tobytes'):
        if v.dtype.hasobject:raise ContractError('object array forbidden in state')
        if v.nbytes>8*1024**2:raise ContractError('state array byte bound')
        if v.dtype.kind=='c' or v.dtype.kind=='f' and any(not math.isfinite(float(x)) for x in v.reshape(-1)):raise ContractError('nonfinite/unsupported complex state')
        return dict(type='ndarray_or_scalar',dtype=v.dtype.str,shape=list(getattr(v,'shape',[])),
            bytes=v.tobytes(order='C').hex())
    if module.startswith('numpy') and type(v).__name__.startswith(('dtype','Float','Int','UInt','Bool')):
        return dict(type='numpy_dtype',value=str(v))
    raise ContractError('unknown state type '+module+'.'+type(v).__qualname__)
def signature(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def snapshot(groups,unknown=None):
    if set(groups)!=set(REQUIRED):raise ContractError('incomplete state category schema')
    if sys.byteorder!='little':raise ContractError('unfrozen byte order')
    rows=[]
    def add(name,value):
        if type(value) is dict and value:
            for k in sorted(value):
                if type(k) is not str or '.' in k:raise ContractError('ambiguous field path')
                add(name+'.'+k,value[k])
        else:rows.append(dict(name=name,classification='captured',
            basis='STATE_FIELD_CLOSURE.json:'+name.split('.')[0],value=typed(value,box_field=name.rsplit('.',1)[-1] if name.split('.')[0] in ('task_python','wrapper_python') else None)))
    for k in REQUIRED:add(k,groups[k])
    if len(rows)>MAX_FIELDS:raise ContractError('state field count bound')
    return dict(schema=STATE_SCHEMA,byte_order=sys.byteorder,fields=rows,unknown_fields=list(unknown or []))
def compare(reference,observed):
    if reference['schema']!=STATE_SCHEMA or observed['schema']!=STATE_SCHEMA:raise ContractError('wrong state schema')
    if reference['byte_order']!=observed['byte_order']:raise ContractError('state byte order differs')
    if reference['unknown_fields'] or observed['unknown_fields']:raise ContractError('unknown state fields')
    a={x['name']:x for x in reference['fields']};b={x['name']:x for x in observed['fields']}
    if len(a)>MAX_FIELDS or len(b)>MAX_FIELDS:raise ContractError('state field count bound')
    if len(a)!=len(reference['fields']) or len(b)!=len(observed['fields']):raise ContractError('duplicate state field')
    if set(a)!=set(b) or {x.split('.')[0] for x in a}!=set(REQUIRED):raise ContractError('missing/extra state fields')
    rows=[]
    for k in sorted(a):
        x,y=a[k],b[k]
        if x['classification']!='captured' or y['classification']!='captured' or x['basis']!=y['basis']:raise ContractError('unfrozen field classification/basis')
        sx,sy=signature(x['value']),signature(y['value'])
        rows.append(dict(name=k,classification=x['classification'],
            verdict='equal' if sx==sy else 'mismatch',basis=x['basis'],
            reference_sha256=sx,observed_sha256=sy))
    ok=all(x['verdict']=='equal' for x in rows)
    return dict(schema=STATE_SCHEMA,level='full_state_verified' if ok else 'failed',
        fields=rows,unknown_fields=[],bitwise_equal=ok,tolerance=0,
        run_branch_IDs_excluded=True,physical_equality_proven=None,
        qualification_scope='exact captured fields under frozen closure contract; no broader hidden-state theorem')
