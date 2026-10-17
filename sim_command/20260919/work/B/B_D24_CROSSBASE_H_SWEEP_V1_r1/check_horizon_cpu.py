"""Exercise the actual private rollout function with CPU-only fake RPC/env."""
import ast
import collections
import contextlib
import hashlib
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path
import numpy as np

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_CROSSBASE_H_SWEEP_V1')
sys.path.insert(0,str(ROOT/'code'))
from qio import read,new_json,atomic_json,utc,sha
from horizon_queue import HorizonQueue
from admission import AdmissionStop

tree=ast.parse((ROOT/'code/native_client.py').read_text())
main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
body=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='evaluate_source')
compiled=compile(ast.fix_missing_locations(ast.Module(body=[body],type_ignores=[])),str(ROOT/'code/native_client.py'),'exec')
units=read(ROOT/'SOURCE_INDEX.json')['units'];cases=[]
for method in ['N','Post','R','Velocity']:
    for horizon in [40,50]:
        unit=next(u for u in units if u['method']==method and u['H']==horizon)
        source=unit['native_source_record'];calls=[];seeds=[];counts=collections.Counter();aux=collections.Counter()
        observation=dict(pixels=np.ones((2,2,3),np.uint8),agent_pos=np.zeros(4,np.float32))
        class Env:task_description='synthetic CPU queue contract'
        def rpc(kind,**fields):
            calls.append((kind,fields.get('step')))
            if kind=='begin':return dict(counters={})
            if kind=='snapshot':return dict(counters=dict(aux))
            if kind=='monitor':
                aux['monitor_calls']+=1
                return dict(gate=1.0 if fields['step'] in [35,100,225] else 0.0,member_gates=[1.,1.])
            if kind=='objective':return {}
            if kind=='gradient':
                aux['action_gradient_calls']+=1;aux['Q_ensemble_forward_calls']+=1
                return dict(gradient=np.ones((10,4),np.float32))
            raise AssertionError(kind)
        def generate(obs,instruction,candidate_seed=None,gradient=None):
            counts['policy_queries']+=1
            counts['candidate_queries' if candidate_seed is not None else 'natural_queries']+=1
            raw=np.repeat((np.arange(50,dtype=np.float32)/100)[:,None],4,axis=1)
            if gradient is not None:gradient(raw[:10])
            return raw,dict(noise_sha256='synthetic_fixed_noise',flow_calls=10)
        def seed_for(domain,sid,policy_seed,step,*,namespace):
            assert domain=='D24_designated_a0' and sid==source['source_id'] and policy_seed==source['policy_seed']
            assert namespace=='corrector_native10_training_20260916_v1'
            seeds.append(step);return step
        def project_solo(raw,direction,matching):
            return raw.copy(),{},dict(actual_delta=np.zeros((10,4)))
        with tempfile.TemporaryDirectory(prefix='B_horizon_cpu_',dir='/tmp') as folder:
            env=dict(np=np,collections=collections,hashlib=hashlib,Path=Path,time=time,traceback=traceback,
                ROOT=Path(folder),CONFIG=read(ROOT/'config/CONFIG.json'),cfg=dict(slot=1,lane=1,units=[unit],seed_namespace='corrector_native10_training_20260916_v1'),
                unit_map={(method,source['source_id']):unit},normal_H=horizon,counters=counts,
                claim_unit=lambda u:dict(unit_id=u['unit_id'],synthetic_CPU_only=True),
                new_json=new_json,atomic_json=atomic_json,utc=utc,episode_deadline=contextlib.nullcontext,
                reset=lambda e,s:(observation,dict(control_hz=80,action_scale=.01),None),
                rpc=rpc,HorizonQueue=HorizonQueue,check=lambda:None,observation=lambda o:o,
                generate=generate,seed_for=seed_for,matching={},native_slopes=np.ones((10,4)),project_solo=project_solo,
                step_env=lambda e,a:(observation,0.,False,False,dict(success=False)),terminal=lambda r:False,
                out=Path(folder)/'client',AdmissionStop=AdmissionStop)
            exec(compiled,env);env['evaluate_source'](Env(),source,method)
            result=read(Path(folder)/'episodes'/hashlib.sha256(unit['unit_id'].encode()).hexdigest()/'RESULT.json')
            assert result['status']=='complete' and result['success'] is False and result['steps']==300,result
            assert result['H']==horizon and result['raw_plan_length']==50
            if method=='N':
                assert result['interventions']==0 and not result['events'] and not result['encoder_counters']
                assert result['natural_refill_steps']==list(range(0,300,horizon))
                assert not seeds and all(kind in ['begin','snapshot'] for kind,_ in calls)
            else:
                events=[e for e in result['events'] if e['trigger']]
                assert [e['step'] for e in events]==[35,100,225]
                assert seeds==[35,100,225]
                assert all(e['C10_complete'] and e['C10_steps_executed']==10 and e['native_H_restored'] for e in events)
                assert [e['native_restore_step'] for e in events]==[45,110,235]
                assert all(e['restore_native_K']==horizon for e in events)
                assert all(not(cut<step<cut+10) for kind,step in calls if kind=='monitor' for cut in [35,100,225])
                if method=='R':assert not any(kind in ('objective','gradient') for kind,_ in calls)
            cases.append(dict(method=method,H=horizon,status='passed',synthetic_steps=300,natural_refills=result['natural_refill_steps'],intervention_steps=seeds,N_no_aux=method!='N' or not result['encoder_counters']))

# The actual rollout function is checked above; frozen numerical modules are unchanged.
source_root=ROOT.parent/'B_D24_L11_RETEST_V1'
unchanged={name:sha(ROOT/'code'/name) for name in ['native_velocity.py','feature_server.py','numeric_engine.py','counts.py']}
assert all(sha(source_root/'code'/name)==value for name,value in unchanged.items())
result=dict(utc=utc(),status='passed',synthetic_CPU_only=True,actual_environment_steps=0,GPU_calls=0,episodes_admitted=0,
            checks=cases,numerical_modules_unchanged=unchanged,
            coverage='Actual evaluate_source AST with fake environment/RPC: N no monitor/trigger/Q; H40/H50 natural refill; mature legal late cuts; three interventions without total cap; C10 lock and tail discard/refill; same candidate domain/seed arguments; R no Q/action gradient; missingness unaffected.')
new_json(ROOT/'CPU_CHECK.json',result)
print(json.dumps(dict(status='passed',cases=len(cases),GPU_calls=0,actual_environment_steps=0)))
