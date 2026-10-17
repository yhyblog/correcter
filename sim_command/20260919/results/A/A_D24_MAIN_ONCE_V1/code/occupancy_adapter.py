"""Worker family ownership plus the CPU-tested per-GPU occupancy barrier."""
from qio import process_identity,same_process,read,new_json,utc
from process_family import group_members
from qoccupancy import PerGPU

class WorkerOccupancy:
    def __init__(self,chain,devices,ack,owner):
        self.owner=owner;self.root=chain/'auxiliary_holders';self.identities={};self.retired=set()
        self.adapter=PerGPU(self.root,devices,ack,pending_gpus=[x['gpu_uuid'] for x in devices])
        self.devices=devices
    def before(self,slot):self.adapter.before_formal(self.devices[slot]['gpu_uuid'],'worker_'+str(slot))
    def started(self,slot,pid):
        row=process_identity(pid)
        if not row or row['pgid']!=self.owner['pgid']:raise RuntimeError('formal worker group identity lost')
        self.identities[(row['pid'],row['start_ticks'])]=(slot,row)
    def refresh(self,workers):
        rows=[process_identity(r['pid']) for r in group_members(self.owner['pgid'],self.owner['pid'])]
        rows=[r for r in rows if r];known={pid:slot for (pid,ticks),(slot,old) in self.identities.items() if same_process(old)}
        unknown=list(rows)
        for _ in range(len(rows)+1):
            remain=[]
            for row in unknown:
                key=(row['pid'],row['start_ticks'])
                if key in self.identities:known[row['pid']]=self.identities[key][0]
                elif row['ppid'] in known:
                    slot=known[row['ppid']];known[row['pid']]=slot;self.identities[key]=(slot,row)
                else:remain.append(row)
            if len(remain)==len(unknown):break
            unknown=remain
        for slot,w in workers.items():
            if slot in self.retired or w['proc'].poll() is None:continue
            live=[row for owner,row in self.identities.values() if owner==slot and same_process(row)]
            if not live and not unknown:
                proof=dict(cleanup_complete=True,remaining_group=[],worker_exit=w['proc'].returncode,
                    owned_family=[row for owner,row in self.identities.values() if owner==slot],observed_utc=utc())
                new_json(w['root']/'FAMILY_EXIT_ACK.json',proof)
                self.adapter.formal_exited(self.devices[slot]['gpu_uuid'],'worker_'+str(slot),proof);self.retired.add(slot)
        cached=read('/tmp/gpu_occupancy_guard/status.json');self.adapter.monitor_cached(cached)
        for gpu in self.adapter.devices:self.adapter.fill_idle(gpu,cached)
    def close(self):return self.adapter.close()
