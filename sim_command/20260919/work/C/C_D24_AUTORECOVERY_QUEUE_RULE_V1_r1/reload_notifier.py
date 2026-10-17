"""Restart the verified CPU notifier only; retained task events are idempotent."""
import os,signal,subprocess,time
from pathlib import Path
from c_recovery_policy import C,ROOT,live_identity
from ops_io import read,new_json,utc
state=C/'persistent_queue/nodes/C/wakeup';script=C/'work/C/C_TASK_DISCOVERY_SERVICE_V1_r1/wakeup.py'
old=read(state/'PROCESS.json')
if old['pid']!=433273 or old['start_ticks']!=1064833054 or not live_identity(old):raise RuntimeError('Notifier identity changed; do not signal')
args=Path('/proc',str(old['pid']),'cmdline').read_bytes().split(b'\0')
if str(script).encode() not in args or b'daemon' not in args:raise RuntimeError('Not the C CPU notifier')
os.kill(old['pid'],signal.SIGTERM);end=time.monotonic()+30
while live_identity(old) and time.monotonic()<end:time.sleep(.2)
if live_identity(old):raise RuntimeError('Notifier has not exited')
result=subprocess.run(['/usr/bin/python','-B',str(script),'start'],capture_output=True,text=True,check=True,timeout=30)
new_json(ROOT/'NOTIFIER_EXTENSION.json',dict(utc=utc(),old=old,old_exited=True,new_start=result.stdout,scientific_queue_processes_signalled=0,synthetic_events=0,preserved_pending_events_and_ACKs=True))
print(result.stdout)
