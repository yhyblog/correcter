"""Lightweight C readiness/resource publication independent of the chat."""
import fcntl
import os
from pathlib import Path
import subprocess
import time
import d24_common as d


def resource(pid):
    try:
        rows=Path('/proc/%d/status'%pid).read_text().splitlines()
        return {k:v.strip() for k,v in (line.split(':',1) for line in rows) if k in ('VmRSS','VmHWM','Threads','State')}
    except OSError:return None


def run():
    cfg=d.load(d.W/'MW_VELOCITY_BATCH.json');out=d.R/cfg['batch_id']
    state=d.C/'persistent_queue/nodes/C'
    with (state/'observer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        d.atomic(state/'OBSERVER_PROCESS.json',d.identity())
        seen_terminal=None
        while True:
            jobs=[];bybase={kind:dict(completed=0,technical=0,resident=0) for kind in ('smolvla','xvla')}
            for j in cfg['jobs']:
                p=Path(j['output']);s=d.load(p/'status.json') if (p/'status.json').exists() else {}
                r=dict(job_id=j['job_id'],kind=j['kind'],gpus=j['gpus'],status=s.get('status','not_started'),
                       completed=s.get('completed_episodes',0),technical=s.get('technical_failures',0),resources={})
                for name in ('PROCESS.json','SERVER_PROCESS.json','CLIENT_PROCESS.json'):
                    if (p/name).exists():
                        ident=d.load(p/name);r['resources'][name]=dict(identity=ident,alive=d.alive(ident),observed=resource(ident['pid']))
                if (p/'EPISODE_PROGRESS.json').exists():r['latest_episode']=d.load(p/'EPISODE_PROGRESS.json')
                jobs.append(r)
                bybase[j['kind']]['completed']+=r['completed'];bybase[j['kind']]['technical']+=r['technical']
                bybase[j['kind']]['resident']+=bool(s.get('model_resident') and s.get('status') in ('running','complete'))
            mem={}
            for line in Path('/proc/meminfo').read_text().splitlines():
                k,v=line.split(':',1)
                if k in ('MemTotal','MemAvailable'):mem[k]=v.strip()
            record=dict(at_utc=d.utc(),host=d.HOST,process=d.identity(),bybase=bybase,jobs=jobs,memory=mem,
                actual_completed=sum(x['completed'] for x in bybase.values()),actual_technical=sum(x['technical'] for x in bybase.values()),
                GPU_benchmark=False,whole_wave_holder_policy='all off while formal reservation held')
            d.atomic(state/'PROGRESS.json',record)
            if (not (out/'STABLE_HANDOFF.json').exists() and all(x['resident']==4 and x['completed']>=1 and x['technical']==0 for x in bybase.values())):
                entry=d.load(out/'FORMAL_ENTRY.json')
                handoff=dict(record,status='stable_formal_background',entry=entry,
                    batch=str(d.W/'MW_VELOCITY_BATCH.json'),fixed_original_thread=d.load(d.C/'nodes/C/identity.json')['executor_thread_id'],
                    trigger=str(state/'wakeup/jobs'/ (cfg['batch_id']+'.json')),
                    notifier_status=d.load(state/'wakeup/HEARTBEAT.json'),
                    first_actual_terminal_per_base=True,native_GPU_guidance_verified='Only actual naturally triggered episodes establish this; inspect per-episode updates',
                    model_updates=0,head_updates=0,development_rollouts=0,
                    instruction='End the LLM turn. Background queue continues; terminal events resume this fixed original thread. Never replay consumed claims.')
                d.exclusive(out/'STABLE_HANDOFF.json',handoff)
                d.atomic(d.C/'receipts/C/C_D24_MW_VELOCITY_V1_RUNNING.json',handoff)
            if (out/'RESULT.json').exists() and not d.alive(d.load(out/'PROCESS.json')):
                if seen_terminal is None:seen_terminal=time.monotonic()
                guard=d.load('/tmp/gpu_occupancy_guard/status.json')
                restored=len(guard.get('gpus',{}))==8 and all(x.get('state')=='holder' and x.get('driver_pids') for x in guard['gpus'].values())
                if restored or time.monotonic()-seen_terminal>300:
                    # This observes actual holders, not just the guard's release/launch transition.
                    metrics=subprocess.run(['nvidia-smi','--query-gpu=index,uuid,utilization.gpu,memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20)
                    d.atomic(out/'OCCUPANCY_RESTORATION_OBSERVED.json',dict(at_utc=d.utc(),host=d.HOST,
                        all8_holder_processes_observed=restored,guard=guard,GPU_sample=metrics.stdout,
                        GPU_sample_returncode=metrics.returncode,utilization_note='snapshot only; holder duty is not measured continuous utilization'))
                    break
            time.sleep(10)


if __name__=='__main__':run()
