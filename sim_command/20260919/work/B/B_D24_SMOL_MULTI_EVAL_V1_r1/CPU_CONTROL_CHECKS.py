"""Exercise the actual nested controller/recorder with CPU-only synthetic inputs."""
import ast
import collections
import contextlib
import copy
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path
import numpy as np

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=C/'results/B/B_D24_SMOL_MULTI_EVAL_V1'
ONCE=C/'results/B/B_D24_SMOL_AUX_RETRAIN_V1/recovery_r2'
sys.path.insert(0,str(R/'code'))
from qio import read,new_json,atomic_json,utc,sha
from admission import release_valid
from paths import CONFIG,AUTH_SHA

def check_runtime(root,method,gate_value):
    tree=ast.parse((root/'code/native_client.py').read_text())
    target=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='evaluate_source')
    code=compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(target)],type_ignores=[])),str(root/'code/native_client.py'),'exec')
    with tempfile.TemporaryDirectory(prefix='B_synthetic_controller_') as folder:
        fake=Path(folder);out=fake/'worker';out.mkdir();seed_calls=[];monitor_calls=[]
        obs=dict(pixels=np.ones((1,1,3),np.uint8),agent_pos=np.zeros(4,np.float32))
        class Environment:
            task_description='CPU synthetic controller fixture';step=0
        env=Environment()
        def reset(env,source):env.step=0;return obs,dict(synthetic=True),None
        def step_env(env,action):env.step+=1;return obs,0.,env.step==45,False,dict(success=False)
        def seed_for(*args,**kw):seed_calls.append((args,kw));return int(args[-1])
        def rpc(kind,**kw):
            if kind=='monitor':
                monitor_calls.append(kw['step']);return dict(gate=gate_value,member_gates=[gate_value]*2)
            if kind=='gradient':return dict(gradient=np.ones((10,4),np.float32)*.01,value=0.)
            return dict(counters={})
        def project(raw,direction,matching):return raw.copy(),dict(synthetic=True),dict(actual_delta=np.zeros((10,4),np.float32))
        space=dict(np=np,collections=collections,ROOT=fake,out=out,cfg={'seed_namespace':'frozen_namespace'},
            claim_attempt=lambda *a,**k:'CPU_SYNTHETIC_ONLY',new_json=new_json,atomic_json=atomic_json,
            counters=collections.Counter(),time=time,utc=utc,traceback=traceback,AdmissionStop=type('AdmissionStop',(RuntimeError,),{}),
            episode_deadline=contextlib.nullcontext,reset=reset,rpc=rpc,observation=lambda x:x,
            generate=lambda *a,**k:(np.zeros((50,4),np.float32),dict(noise_sha256='synthetic')),
            check=lambda *a,**k:None,step_env=step_env,terminal=lambda value:value[2],seed_for=seed_for,
            native_slopes=np.ones((10,4),np.float32),matching={},project_solo=project)
        exec(code,space)
        space['evaluate_source'](env,dict(source_id='CPU_SYNTHETIC_SOURCE',task='synthetic',reset_seed=1,policy_seed=2),method)
        directory=fake/'evaluation'/method/'CPU_SYNTHETIC_SOURCE';row=read(directory/'RESULT.json')
        cuts=[e['step'] for e in row['events'] if e['trigger']]
        return dict(cuts=cuts,first_cut=row['first_cut'],count=row['interventions'],seeds=seed_calls,
            files=sorted(p.name for p in directory.glob('intervention*.npz')),monitor_calls=monitor_calls)

for p in (R/'code').glob('*.py'):ast.parse(p.read_text())
once=check_runtime(ONCE,'Post',.051);multi=check_runtime(R,'Post',.051);threshold=check_runtime(R,'R',.05)
assert once['cuts']==[5] and once['count']==1
assert multi['cuts']==[5,20,35] and multi['count']==3 and multi['first_cut']==5
assert multi['files']==['intervention_20.npz','intervention_35.npz','intervention_5.npz']
assert not threshold['cuts'] and threshold['first_cut'] is None
assert once['seeds'][0]==multi['seeds'][0]
assert all(e[0][0]=='D24_designated_a0' and e[0][1]=='CPU_SYNTHETIC_SOURCE' and e[0][2]==2 for e in multi['seeds'])
assert all(not any(c<t<c+10 for c in multi['cuts']) for t in multi['monitor_calls'])
control=read(C/'CONTROL.json');queue=read(C/'persistent_queue/CONTROL.json');grant=read(C/CONFIG['grant'])
assert release_valid(control,queue,grant,CONFIG['task_id'],AUTH_SHA)
assert sha(R/'code/native_velocity.py')==sha(ONCE/'code/native_velocity.py')
index=read(R/'SOURCE_INDEX.json');assert len(index['pending'])==1500 and not index['retained']
assert len({(x['method'],x['source_id']) for x in index['pending']})==1500
checks=['actual controller: once cut5;multi cuts5/20/35;first_cut remains5','strict threshold excludes equality','C10 lock excludes reentry and monitoring inside commitment','per-cut evidence files preserve all3interventions','candidate RNG key unchanged at common cut','same native action bridge and 1500unique sources','current released multi authorization valid']
new_json(R/'evidence/CPU_CHECKS.json',dict(status='PASS',at_utc=utc(),checks=checks,synthetic_only=True,GPU_calls=0,model_loads=0,real_rollouts=0,optimizer_updates=0))
print(json.dumps(dict(status='PASS',checks=checks)))
