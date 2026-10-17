"""Fake transports only: no actual Codex turn or external message."""
import sys
from pathlib import Path
PKG=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PKG/'queue'))
import json,socket,types,time
import qevents as m
from qio import new_json,atomic_json,read,ref
from qauthority import AUTH_SHA
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
small=out/'runtime.json';new_json(small,dict(synthetic=True));calls=[];checks=[]
def check(name,condition):
    checks.append(dict(name=name,passed=bool(condition)))
    if not condition:raise AssertionError(name)
def event(name):
    root=out/name
    d=dict(event_id='SYNTHETIC_CPU_'+name,node='A',hostname=socket.gethostname(),executor_thread_id='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',
        authorization_sha256=AUTH_SHA,code_manifest=ref(small),synthetic=True)
    new_json(root/'EVENT.json',d);new_json(root/'TRANSPORT.json',dict(state='pending',attempts=0,next_attempt_unix=0));return root/'EVENT.json'
class Handle:
    pid=999999999
def queue(argv,**kw):calls.append((argv,kw));return types.SimpleNamespace(returncode=0,stdout='SYNTHETIC queue accepted',stderr='')
def spawn(argv,**kw):calls.append((argv,kw));return Handle()
m.subprocess=types.SimpleNamespace(run=queue,Popen=spawn,DEVNULL=-3,PIPE=-1,STDOUT=-2)
p=event('busy');r=m.deliver(p,busy_fn=lambda _:True,now=lambda:100)
check('busy_existing_writer_uses_queue_no_second_writer',calls[-1][0][1]=='queue' and r['attempts']==1)
check('transport_acceptance_not_handler_ACK',r['state']=='transport_accepted' and r['handler_acknowledged'] is False)
new_json(p.parent/'HANDLER_ACK.json',dict(event_id=read(p)['event_id'],executor_thread_id=read(p)['executor_thread_id'],synthetic=True,handled=True,scientific_compute=0))
before=len(calls);r=m.deliver(p,busy_fn=lambda _:True,now=lambda:1000)
check('ACK_dedup_no_new_transport_or_compute',r['state']=='handler_acknowledged' and len(calls)==before)
p=event('unloaded');r=m.deliver(p,busy_fn=lambda _:False,now=lambda:100)
argv=calls[-1][0];check('unloaded_exact_UUID_resume',argv[1:4]==['exec','resume','01a0b91f-7443-71b1-915d-6cdb6d6a1a13'])
check('model_and_permissions_not_overridden',not any(x in argv for x in ['--last','--model','-m','--dangerously-bypass-approvals-and-sandbox','--ignore-rules','--ignore-user-config']))
check('resume_PID_not_claimed_handler',r['state']=='resume_started_not_handler_ACK')
p=event('bad_thread');d=read(p);d['executor_thread_id']='OTHER';atomic_json(p,d)
try:m.deliver(p,busy_fn=lambda _:False)
except ValueError:check('foreign_thread_rejected',True)
else:check('foreign_thread_rejected',False)
def fail(*a,**kw):raise RuntimeError('SYNTHETIC disconnected service')
m.subprocess.run=fail;p=event('bounded_error')
for n in range(4):
    state=read(p.parent/'TRANSPORT.json');state['next_attempt_unix']=0;atomic_json(p.parent/'TRANSPORT.json',state)
    r=m.deliver(p,busy_fn=lambda _:True,now=lambda:100)
check('transport_failure_max3_no_experiment_retry',r['attempts']==3 and r['state']=='transport_blocked')
new_json(out/'CHECKS.json',dict(status='PASS',checks=checks,live_callback_events=0,formal_compute=0))
print(json.dumps(dict(status='PASS',checks=len(checks))))
