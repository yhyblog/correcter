"""Targeted final scheduler traceback/exit-barrier delta; synthetic only."""
import json,sys,traceback
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'));import inheritance
from batch_scheduler import run_schedule,GlobalFault
from core.event_recorder import EventRecorder
from budget import batch_timeouts,scheduler_caps
OUT=Path(sys.argv[1]);OUT.mkdir(parents=True,exist_ok=False)
checks=[]
def check(name,value):checks.append(dict(name=name,passed=bool(value)));assert value,name
class Backend:
    synthetic=True
    def __init__(self,publish_failure=False):self.started=False;self.drained=False;self.publish_failure=publish_failure
    def refresh(self):pass
    def start(self,p,j):self.started=True;return j
    def poll(self,h):return None
    def drain(self):self.drained=True;return dict(status='all_formal_group_members_exited',synthetic=True)
    def was_started(self,p):return self.started
    def publish(self,p):
        assert self.drained
        if self.publish_failure:raise OSError('synthetic publication storage failure')
        return dict(synthetic=True,partial=True)
parent=dict(parent_key='SYNTHETIC_PARENT',source=dict(task='stick-pull-v3',cut=55,source_id='SYNTHETIC_SOURCE',parent_source_id='SYNTHETIC_PARENT'),device=dict(gpu_uuid='SYNTHETIC_GPU'))
try:
    for label,fault in [('signal',False),('publication_failure',True)]:
        backend=Backend(fault);calls=[0];ticks=[0.]
        def gate():
            calls[0]+=1
            if calls[0]>1:raise GlobalFault('synthetic signal / CONTROL stop')
        recorder=EventRecorder(OUT/(label+'.jsonl'),branch='batch_manager',source_id='SYNTHETIC',parent_source_id='SYNTHETIC',synthetic=True)
        r=run_schedule([parent],1,backend,gate=gate,emit=recorder.emit,limits=scheduler_caps(1),timeouts=batch_timeouts(1),
            clock=lambda:ticks[0],pause=lambda t:ticks.__setitem__(0,ticks[0]+t))
        (OUT/(label+'.json')).write_text(json.dumps(r,indent=2)+'\n')
        check(label+'_keeps_live_primary_traceback','raise GlobalFault' in r['primary']['traceback'] and r['primary']['synthetic'])
        check(label+'_exit_before_partial_publish',r['cleanup']['status']=='all_formal_group_members_exited' and r['branch_starts']==1)
        check(label+'_no_false_complete',r['status']=='partial_or_failed' and r['interrupted_active'][0]['parent_key']=='SYNTHETIC_PARENT')
        if fault:check('secondary_publication_traceback_retained','raise OSError' in r['publication_failures'][0]['traceback'])
    status='PASS';failure=None
except BaseException:status='FAIL';failure=traceback.format_exc()
result=dict(status=status,checks=checks,synthetic=True,failure=failure,real_process_hardware_holder_launcher_operations=0)
(OUT/'CHECK_RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=status,checks=len(checks),failure=failure)))
sys.exit(0 if status=='PASS' else 1)
