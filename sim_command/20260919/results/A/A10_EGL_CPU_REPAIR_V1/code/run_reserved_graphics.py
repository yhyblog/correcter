"""Private wrapper preserving the guard lock through timeout and the graphics child."""
import argparse
import json
from pathlib import Path
import sys
from wave_timing import mark, run_forwarded, held_reservation_fds
from probe_contract import Refused


def main():
    parser = argparse.ArgumentParser()
    for name in ('campaign','release','proposal','launch-directory'): parser.add_argument('--'+name, required=True)
    args = parser.parse_args(); out = Path(args.launch_directory)
    mark(out, 'reserved_command_started')
    fds = held_reservation_fds()
    if not fds: raise Refused('All A GPUs must be reserved before the graphics process')
    proposal = json.loads(Path(args.proposal).read_text())
    root = Path(args.proposal).resolve().parent.parent
    command = ['timeout','--foreground','--signal=TERM','--kill-after=10s','120s',proposal['python'],
        '-B',str(root/'code/graphics_probe.py'),'--campaign',args.campaign,'--release',args.release,
        '--proposal',args.proposal,'--launch-directory',str(out)]
    mark(out, 'timed_process_started'); rc = None
    try:
        rc = run_forwarded(command, cwd=root, pass_fds=fds); return rc
    finally:
        mark(out, 'timed_process_exited', returncode=rc, automatic_retry=False)


if __name__ == '__main__': sys.exit(main())
