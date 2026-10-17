"""One CPU-only startup observer. Persist an event; existing daemon delivers it."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from qio import new_json,read,process_identity,same_process,utc,ref

def main():
    new_json(ROOT/'evidence/STARTUP_OBSERVER_STARTED.json',dict(process=process_identity(),utc=utc(),hardware_queries=0))
    until=time.monotonic()+2400
    while True:
        ready=list((ROOT/'chain/workers').glob('*/MODEL_READY.json'))
        live=[p for p in ready if same_process(read(p)['process'])]
        episodes=list((ROOT/'runs').glob('*/episodes/*/RESULT.json'))
        exits=list((ROOT/'chain/workers').glob('*/WORKER_EXIT.json'))
        failed=[p for p in exits if read(p).get('fatal') or read(p).get('cleanup')]
        stopped=(ROOT/'chain/CHAIN_RESULT.json').exists()
        if (len(live)==8 and episodes) or failed or stopped or time.monotonic()>=until:
            doc=dict(utc=utc(),model_ready_slots=[p.parent.name for p in ready],live_ready_slots=[p.parent.name for p in live],
                completed_episode_results=len(episodes),failed_workers=[ref(p) for p in failed],
                status='eight_models_loaded_and_episode_returned' if len(live)==8 and episodes and not failed else 'startup_requires_review',
                first_episode=ref(episodes[0]) if episodes else None,extra_GPU_queries=0,
                heartbeat=read(ROOT/'HEARTBEAT.json'),model_identity_refs=[ref(p) for p in ready],
                no_extra_scientific_attempt=True,formal_stage='main_once5500')
            evidence=ROOT/'evidence/STARTUP_OBSERVED.json';new_json(evidence,doc)
            new_json(ROOT/'outbox/startup_observed.json',dict(event_id='D24_A_main_once_startup_observed_v1',kind=doc['status'],
                synthetic=False,result=str(evidence),utc=utc(),relaunch_forbidden=True))
            return 0
        time.sleep(5)
if __name__=='__main__':raise SystemExit(main())
