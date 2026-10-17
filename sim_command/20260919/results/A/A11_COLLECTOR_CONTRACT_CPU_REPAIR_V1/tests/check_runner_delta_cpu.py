"""Actual revised execution.run, entirely fake Popen/signals/limits; no real process."""
import json,sys,types
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
import inheritance
import execution
OUT=Path(sys.argv[1]);OUT.mkdir(parents=True,exist_ok=False)
checks=[]
def check(name,value):
    checks.append(dict(name=name,passed=bool(value)))
    assert value,name
operations=[]
execution.resource=types.SimpleNamespace(RLIMIT_FSIZE=1,RLIMIT_CORE=2,setrlimit=lambda *a:operations.append(a))
execution.limits()
check('inherited_AS_not_read_or_changed',operations==[(1,(33554432,33554432)),(2,(0,0))])
class Timeout(Exception):pass
class Child:
    pid=424242
    def __init__(self):self.waits=[];self.done=False;self.signals=[]
    def poll(self):return 0 if self.done else None
    def wait(self,timeout=None):
        self.waits.append(timeout)
        if timeout is not None and len(self.waits)==1:raise Timeout()
        self.done=True;return 0
    def send_signal(self,s):self.signals.append(s)
signals=[];restores=[];children=[];calls=[]
def popen(*a,**kw):
    child=Child();children.append(child);calls.append(kw);return child
execution.subprocess=types.SimpleNamespace(Popen=popen,TimeoutExpired=Timeout)
execution.os=types.SimpleNamespace(killpg=lambda *a:signals.append(a))
execution.signal=types.SimpleNamespace(SIGINT=2,SIGTERM=15,SIGHUP=1,signal=lambda s,f:restores.append((s,f)) or 'fake_previous')
class Monitor:
    def __init__(self,fail=False):self.calls=0;self.fail=fail
    def check(self):
        self.calls+=1
        if self.fail:raise RuntimeError('synthetic storage threshold')
for fail in (False,True):
    mon=Monitor(fail)
    try:
        result=execution.run(['SYNTHETIC_NOT_EXECUTED'],cwd=OUT,stdout=OUT/(str(fail)+'.stdout'),stderr=OUT/(str(fail)+'.stderr'),new_session=True,pass_fds=(987654,),monitor=mon)
        assert not fail
        check('normal_monitor_then_final_check',result==0 and mon.calls==2 and children[-1].done)
    except RuntimeError:
        assert fail
        check('monitor_failure_waits_drain_before_raise',children[-1].done and children[-1].waits==[5,None])
        check('signals_only_owned_fake_group',signals==[(424242,15)])
check('reservation_fds_forwarded_unchanged',all(c['pass_fds']==(987654,) for c in calls))
check('handlers_restored_both_paths',sum(f=='fake_previous' for _,f in restores)==6)
check('no_formal_lock_open_or_reacquire','lock' not in execution.run.__code__.co_names)
(OUT/'CHECKS.json').write_text(json.dumps(dict(status='PASS',synthetic=True,checks=checks,
    actual_processes_signals_locks_resource_changes=0),indent=2)+'\n')
print(json.dumps(dict(status='PASS',checks=len(checks))))
