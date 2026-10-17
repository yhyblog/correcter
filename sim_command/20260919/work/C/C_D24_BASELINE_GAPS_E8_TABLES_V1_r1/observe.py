"""Finite host-side supervision, handoff and holder restoration evidence."""
import fcntl
from pathlib import Path
import subprocess
import time
import d24_common as d
from gap_summary import summarize


def main():
    cfg_path=d.W/'N_GAP_BATCH.json'
    cfg=d.load(cfg_path);out=d.R/cfg['batch_id']
    with (out/'observer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        d.atomic(out/'OBSERVER_PROCESS.json',d.identity())
        while True:
            s=summarize(cfg_path);jobs=[]
            for j in cfg['jobs']:
                p=Path(j['output'])
                state=d.load(p/'status.json') if (p/'status.json').exists() else {}
                ready=(p/'SERVER_READY.json').exists()
                alive=d.alive(d.load(p/'SERVER_PROCESS.json')) if (p/'SERVER_PROCESS.json').exists() else False
                jobs.append(dict(job_id=j['job_id'],ready=ready,server_alive=alive,status=state.get('status')))
            record=dict(at_utc=d.utc(),process=d.identity(),summary=s,jobs=jobs)
            d.atomic(d.C/'nodes/C/C_D24_BASELINE_GAPS_E8_TABLES_V1_PROGRESS.json',record)
            if s['valid'] and all(j['ready'] for j in jobs) and not (out/'STABLE_HANDOFF.json').exists():
                d.exclusive(out/'STABLE_HANDOFF.json',dict(record,status='stable_finite_background',
                    fixed_original_thread=d.load(d.C/'nodes/C/identity.json')['executor_thread_id'],
                    callback=str(d.C/'persistent_queue/nodes/C/wakeup/jobs'/(cfg['batch_id']+'.json')),
                    no_unknown_replay=True,previous_1000_Velocity_replays=0))
            if (out/'RESULT.json').exists() and not d.alive(d.load(out/'PROCESS.json')):
                guard=d.load('/tmp/gpu_occupancy_guard/status.json')
                restored=len(guard['gpus'])==8 and all(v['state']=='holder' and v.get('driver_pids') for v in guard['gpus'].values())
                gpu=subprocess.run(['nvidia-smi','--query-gpu=index,uuid,utilization.gpu,memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20)
                d.atomic(out/'OCCUPANCY_RESTORATION_OBSERVED.json',dict(at_utc=d.utc(),host=d.HOST,
                    all8_holder_processes_observed=restored,guard=guard,GPU_sample=gpu.stdout,GPU_sample_returncode=gpu.returncode))
                break
            time.sleep(10)


if __name__=='__main__':
    main()
