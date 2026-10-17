"""Runs inside the all-GPU reservation; the timed child includes all initialization."""
import argparse
import json
from pathlib import Path
import sys
import os
from core.process_family import drain_group
from core.wave_timing import write_new
from core.wave_timing import mark, run_forwarded, held_reservation_fds
from core.validation import ContractError


def main():
    parser = argparse.ArgumentParser()
    for key in ('campaign', 'release', 'proposal', 'launch-directory'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    directory = Path(args.launch_directory).resolve()
    mark(directory, 'reserved_command_started')
    # This private entry is not a replacement for launch_preflight. Fail closed
    # before starting the child if invoked without the persistent guard lock FD.
    reservation_fds = held_reservation_fds()
    if not reservation_fds:
        raise ContractError('Diagnostic must be launched through the active occupancy guard reservation')
    proposal = json.loads(Path(args.proposal).read_text())
    root = Path(__file__).resolve().parent
    command = ['timeout', '--foreground', '--signal=TERM', '--kill-after=30s',
        str(proposal['timeout_seconds']) + 's', proposal['python'], '-B', str(root / 'preflight_pi05.py'),
        '--campaign', args.campaign, '--release', args.release, '--proposal', args.proposal,
        '--launch-directory', str(directory)]
    result = None
    mark(directory, 'timed_process_started')
    try:
        result = run_forwarded(command, cwd=root, pass_fds=reservation_fds)
        return result
    finally:
        write_new(directory / 'process_family_cleanup.json', drain_group(os.getpgrp(), os.getpid()))
        mark(directory, 'timed_process_exited', returncode=result,
             abnormal_result_is_not_an_automatic_retry=True)


if __name__ == '__main__':
    sys.exit(main())
