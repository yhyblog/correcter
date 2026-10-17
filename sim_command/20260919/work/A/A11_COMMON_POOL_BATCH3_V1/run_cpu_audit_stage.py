"""Capture one saved-data CPU audit stage after formal command completion."""
from pathlib import Path
import argparse,datetime,json,subprocess,sys,time
W=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('stage',choices=('metadata','artifacts'));a=p.parse_args()
if not Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_COMMON_POOL_BATCH3_V1/OUTER_EXIT.json').exists():raise SystemExit('Outer command has not exited')
script={'metadata':'audit_after_exit.py','artifacts':'audit_artifacts_after_exit.py'}[a.stage]
base=W/('CPU_AUDIT_'+a.stage.upper());cmd=[sys.executable,'-B',str(W/script)]
started=datetime.datetime.now(datetime.timezone.utc).isoformat();tick=time.monotonic()
with Path(str(base)+'.stdout').open('xb') as so,Path(str(base)+'.stderr').open('xb') as se:
    result=subprocess.run(cmd,cwd=W,stdout=so,stderr=se,check=False)
row=dict(stage=a.stage,argv=cmd,started_utc=started,elapsed_seconds=time.monotonic()-tick,
    returncode=result.returncode,scope='saved files only; no real launcher/model/environment/hardware calls')
with Path(str(base)+'_EXIT.json').open('x') as f:json.dump(row,f,indent=2);f.write('\n')
print(json.dumps(row),flush=True);raise SystemExit(result.returncode)
