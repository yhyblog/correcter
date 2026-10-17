import fcntl
import subprocess
from pathlib import Path
from paths import CONFIG,CAMPAIGN
from qio import atomic_json,utc
_wave_lock=None
def acquire_wave(root):
    global _wave_lock
    _wave_lock=(Path(CONFIG['local_dir'])/'science_owner.lock').open('a')
    fcntl.flock(_wave_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
def register_manifest(path):
    record=dict(utc=utc(),manifest=str(path),science_blocks=False)
    try:
        p=subprocess.run(['/usr/bin/python',str(CAMPAIGN/'work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py'),'register','--manifest',str(path)],capture_output=True,text=True,timeout=25)
        record.update(exit_code=p.returncode,stdout=p.stdout[-2000:],stderr=p.stderr[-2000:],registered=p.returncode==0)
    except Exception as exc:record.update(registered=False,error=repr(exc))
    atomic_json(Path(path).parent/'TRIGGER_REGISTRATION_STATUS.json',record)
    return record
