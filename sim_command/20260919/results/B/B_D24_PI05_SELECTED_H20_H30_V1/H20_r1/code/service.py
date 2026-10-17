"""B private predeclared CPU continuation entry; no conversation dependency."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,'/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1_r1')
from quota_runtime import entry_prepare,empty_stage
cfg=entry_prepare(root)
if cfg['planned_current']==0:
    raise SystemExit(empty_stage(root))
sys.path.insert(0,str(root/'code'))
import runpy
runpy.run_path(str(root/'code/service_impl.py'),run_name='__main__')
