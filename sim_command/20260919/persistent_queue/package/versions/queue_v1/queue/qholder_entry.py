"""CPU-only launch acknowledgement before permission to enter holder GPU code."""
import argparse
import os
import select
import time
from pathlib import Path
from qio import new_json,process_identity,utc

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--go-fd',required=True,type=int);p.add_argument('--holder',required=True);a=p.parse_args()
    root=Path(a.root);own=process_identity()
    if os.getsid(0)!=own['pid'] or own['pgid']!=own['pid']:raise RuntimeError('private holder session required')
    new_json(root/'STARTED.json',dict(process=own,session=os.getsid(0),utc=utc(),monotonic=time.monotonic(),GPU_compute_entered=False))
    ready=select.select([a.go_fd],[],[],15)[0]
    if not ready or os.read(a.go_fd,3)!=b'GO\n':return 2
    os.close(a.go_fd)
    if not (root/'GO_RECORDED.json').exists():raise RuntimeError('no durable holder ownership record')
    new_json(root/'EXEC_ENTERED.json',dict(utc=utc(),monotonic=time.monotonic(),process=own,holder_duty=.95))
    os.execv('/usr/bin/python',['/usr/bin/python','-B',a.holder,'--devices','0','--size','8192','--dtype','bf16',
        '--target-util','0.95','--period-seconds','0.20','--log-interval','60'])

if __name__=='__main__':raise SystemExit(main())
