"""CPU-testable attribute reader; only the caller's exact Box class marks bounds.

Runtime supplies gymnasium.spaces.Box after authorized imports. Fixtures supply
an explicit synthetic class; no name/module-string duck typing admits bounds.
"""
from dataclasses import dataclass
from core.contracts import ContractError

@dataclass(frozen=True)
class BoxBound:
    field: str
    array: object

def capture_attrs(obj, *, box_type, numpy, read_rng, exclude=None, container_space_types=()):
    exclude=exclude or {}
    def descend(value):
        if isinstance(value,(numpy.random.Generator,numpy.random.RandomState)):
            return read_rng(value)
        if type(value) is box_type or type(value) in container_space_types:
            return capture_attrs(value,box_type=box_type,numpy=numpy,read_rng=read_rng,container_space_types=container_space_types)
        if type(value) is dict:return {k:descend(v) for k,v in value.items()}
        if type(value) in (list,tuple):return type(value)(descend(v) for v in value)
        return value
    result={}
    for key,value in vars(obj).items():
        if key in exclude:
            result[key]={'classification':'irrelevant','basis':exclude[key],
                         'class':type(value).__module__+':'+type(value).__qualname__}
        elif type(obj) is box_type and key in ('low','high'):
            if type(value) is not numpy.ndarray or value.dtype.kind not in 'fiu':
                raise ContractError('Box bound must be an exact numeric ndarray')
            result[key]=BoxBound(key,value)
        else:result[key]=descend(value)
    return result
