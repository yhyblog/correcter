"""Finite read-only progress observer; never launches or retries science."""
import datetime,json,os,time
from pathlib import Path
R=Path(__file__).resolve().parent

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def exclusive(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
start=time.monotonic()
while time.monotonic()-start<2100:
    if (R/'RESULT.json').exists():
        exclusive(R/'FIRST_PROGRESS_OBSERVER_EXIT.json',dict(utc=utc(),reason='terminal handled by existing supervisor',scientific_compute=0));break
    p=R/'STABLE_HANDOFF.json'
    if p.exists():
        event=R/'outbox/startup_progress.json'
        if not event.exists():exclusive(event,dict(event_id='A_D24_LIBERO_FULL_NATIVE_V1_launch_r6_startup_progress',synthetic=False,utc=utc(),task_id='A_D24_LIBERO_FULL_NATIVE_V1',result=str(p),status='actual_first_control_progress',observer_only=True))
        exclusive(R/'FIRST_PROGRESS_OBSERVER_EXIT.json',dict(utc=utc(),reason='actual control progress event published; existing service dispatches callback',scientific_compute=0));break
    time.sleep(5)
else:
    exclusive(R/'FIRST_PROGRESS_OBSERVER_EXIT.json',dict(utc=utc(),reason='finite observer expired; original task timeout/terminal callback remain active',scientific_compute=0))
