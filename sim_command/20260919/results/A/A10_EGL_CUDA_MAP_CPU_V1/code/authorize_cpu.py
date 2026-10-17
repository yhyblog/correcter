"""Pure CPU authorization entry; never invokes NVML, EGL, MuJoCo or the lifecycle."""
import argparse
import json
import sys
from pathlib import Path
from probe_contract import authorize

def main():
    parser = argparse.ArgumentParser()
    for name in ('campaign','release','proposal'): parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    try:
        if Path(__file__).resolve().parent.parent != Path(args.proposal).resolve().parent.parent:
            raise ValueError('Executable must belong to the proposed bundle')
        r, p = authorize(args.campaign,args.release,args.proposal)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps(dict(status='denied', error=str(e), CPU_only=True, graphics_started=False))); return 2
    print(json.dumps(dict(status='CPU_authorization_and_SHA_validated', release_id=r['release_id'],
        resource_caps=p['resource_caps'], CPU_only=True, graphics_started=False, runtime_validated=False)))
    return 0

if __name__ == '__main__': sys.exit(main())
