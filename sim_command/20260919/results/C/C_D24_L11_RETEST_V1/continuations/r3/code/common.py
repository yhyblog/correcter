import contextlib,os
from pathlib import Path
from paths import ROOT,WORKSPACE
from qio import read
from admission import boundary as _boundary,AdmissionStop,claim_unit
def boundary(admission=False):return _boundary(admission,model='X-VLA')
def reservation_fds():
    result=[]
    for p in Path('/proc/self/fd').iterdir():
        try:
            if os.readlink(p)=='/tmp/gpu_occupancy_guard/formal.lock':result.append(int(p.name))
        except OSError:pass
    if len(result)!=1:raise RuntimeError('requires inherited original reservation')
    return tuple(result)
def runtime_command(environment,script,*args):
    base=WORKSPACE/'embodied-ai-workspace';prefix='lerobot' if environment=='mw-pi05-legacy' else environment
    return ['bash',str(base/'projects/vla-baselines/launchers/runtime.sh'),environment,str(base/'environments'/prefix/'bin/python'),'-B',str(ROOT/'xcode'/script),*map(str,args)]
def claim_attempt(identity,**extra):
    method,sid=identity.split('/',1)
    unit_id=f'X-VLA|{sid}|{method}|G0-multi|10|L11|9101'
    import hashlib
    return claim_unit(read(ROOT/'units'/(hashlib.sha256(unit_id.encode()).hexdigest()+'.json')))
def claim_work(*args,**kwargs):return True
def remaining_seconds():return 43200
def episode_deadline(*args,**kwargs):return contextlib.nullcontext()
