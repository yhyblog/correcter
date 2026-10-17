"""Whole formal wave: never launch a holder, including early-finished GPUs."""
from qio import process_identity,read,new_json,utc
class WorkerOccupancy:
    def __init__(self,chain,devices,ack,owner):
        self.owner=owner;self.chain=chain
        new_json(chain/'WHOLE_WAVE_POLICY.json',dict(utc=utc(),all_holders_off=True,auxiliary_holders_enabled=False,original_holder_exit_ack=ack['status']))
    def before(self,slot):
        rows=read('/tmp/gpu_occupancy_guard/status.json')['gpus']
        if len(rows)!=8 or any(x['state']!='reserved' for x in rows.values()):raise RuntimeError('Whole-wave reservation missing before worker entry')
    def started(self,slot,pid):
        row=process_identity(pid)
        if not row or row['pgid']!=self.owner['pgid']:raise RuntimeError('worker escaped formal group')
    def refresh(self,workers):pass
    def close(self):return []
