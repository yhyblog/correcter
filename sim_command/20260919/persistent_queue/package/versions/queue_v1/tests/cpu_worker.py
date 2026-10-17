"""Only the explicitly synthetic model/environment boundary; no hardware imports."""
import sys
from pathlib import Path
PKG=Path(__file__).resolve().parents[1];sys.path[:0]=[str(PKG/'code'),str(PKG/'queue')]
import inheritance
import json,os,time,importlib.abc
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self,name,path,target=None):
        if name.split('.')[0] in {'torch','numpy','metaworld','mujoco','ctypes','pynvml'}:raise RuntimeError('forbidden CPU import '+name)
sys.meta_path.insert(0,Deny())
from qio import read,new_json,ref,process_identity
from synthetic_boundaries import SyntheticBoundary,drive
from pool_protocol import ARMS
from core.contracts import Meter,reconcile,configure_store
from core.failure_evidence import record_failure
from budget import numeric_caps,attempt_caps,sum_units
from task_profiles import initialization_caps
from qvalidate import failure_signature

spec=read(sys.argv[1]);branch=sys.argv[2];job=next(j for j in ARMS if j[0]==branch)
test=Path(sys.argv[3]);barrier=test/'ready';barrier.mkdir(exist_ok=True)
if branch=='normal':
    new_json(barrier/(spec['parent_key']+'.json'),dict(process=process_identity()))
    end=time.monotonic()+10
    while len(list(barrier.glob('*.json')))<8:
        if time.monotonic()>end:raise RuntimeError('eight CPU slots failed rendezvous')
        time.sleep(.05)
    time.sleep(.25)
e=SyntheticBoundary(spec,job,success_at=spec['source']['cut']+12)
e.identity['model_sha256']=e.cfg['model_sha256'];e.identity['config_sha256']=spec['config']['sha256']
cfg=read(spec['config']['path']);out=e.out;nc=numeric_caps(branch,e.cut);ic=initialization_caps(e.task,e.cut);gc=cfg['native']['graphics_caps']
configure_store(None);meter=Meter(out/'numeric_events.jsonl',nc)
for f in ['initialization_events.jsonl','graphics_events.jsonl']:(out/f).touch(exist_ok=False)
primary=None;result=None
try:
    meter.call('SYNTHETIC_attempt',lambda:None,{'simulator_attempts':1,'native_nvml_identity_queries':1})
    if spec.get('inject_failure')==branch:raise RuntimeError('synthetic isolated parent failure')
    anchor=read(Path(spec['paths']['output'])/'normal/CUT_REFERENCE.json') if branch!='normal' else None
    result=drive(e,anchor)
    meter.call('SYNTHETIC_controls',lambda:None,{'env_steps':result['controls']})
except Exception as error:
    primary=record_failure(error,branch=branch,stage='synthetic_model',category='primary',synthetic=True)
    primary['failure_scope']='parent'
n=reconcile(out/'numeric_events.jsonl',nc)
new_json(out/'NVML_IDENTITY.json',dict(synthetic=True,target=spec['device']))
new_json(out/'RESOURCE_LEDGER.json',dict(status='failed' if primary else 'complete',synthetic=True,primary=primary,cleanup=[],
    caps=attempt_caps(branch,e.task,e.cut),total_entered=sum_units(n['entered'],dict.fromkeys(ic,0),dict.fromkeys(gc,0)),
    numeric=n,initialization=dict(entered_budget_usage=dict.fromkeys(ic,0)),graphics=dict(entered_budget_usage=dict.fromkeys(gc,0)),result=result))
sys.exit(3 if primary else 0)
