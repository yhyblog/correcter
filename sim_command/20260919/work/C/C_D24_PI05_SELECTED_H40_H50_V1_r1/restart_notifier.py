"""Reload only the identity-verified C CPU notification daemon, retaining records."""
import os,signal,subprocess,sys,time
from pathlib import Path
C=Path(__file__).resolve().parents[3]
ROOT=C/'results/C/C_D24_PI05_SELECTED_H40_H50_V1'
sys.path.insert(0,str(ROOT/'code'))
from qio import read,new_json,utc,same_process
state=C/'persistent_queue/nodes/C/wakeup';script=C/'work/C/C_TASK_DISCOVERY_SERVICE_V1_r1/wakeup.py'
old=read(state/'PROCESS.json');identity=dict(old,host=old['hostname'])
if old['pid']!=407893 or old['start_ticks']!=1064530804 or not same_process(identity):raise RuntimeError('Unexpected notifier identity; do not signal')
args=Path('/proc',str(old['pid']),'cmdline').read_bytes().split(b'\0')
if str(script).encode() not in args or b'daemon' not in args:raise RuntimeError('Not the C notification daemon')
os.kill(old['pid'],signal.SIGTERM);end=time.monotonic()+30
while same_process(identity) and time.monotonic()<end:time.sleep(.2)
if same_process(identity):raise RuntimeError('Old notifier has not exited')
r=subprocess.run(['/usr/bin/python','-B',str(script),'start'],check=True,capture_output=True,text=True,timeout=30)
new_json(ROOT/'NOTIFIER_EXTENSION.json',dict(utc=utc(),old=old,old_exited=True,start_output=r.stdout,extended_task=ROOT.name,pending_events_and_ACKs_preserved=True,science_processes_signalled=0,synthetic_wakeups=0))
print(r.stdout)
