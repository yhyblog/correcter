"""Keep the inherited reservation until the isolated formal process group exits."""
import os
from pathlib import Path
import signal
import time


def group_members(pgid, owner):
    rows = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) == owner:
            continue
        try:
            parts = (entry/'stat').read_text().rsplit(') ', 1)[1].split()
            if int(parts[2]) == pgid and parts[0] != 'Z':
                rows.append(dict(pid=int(entry.name), start_ticks=int(parts[19])))
        except (OSError, ValueError, IndexError):
            continue
    return rows


def drain_group(pgid, owner, *, reader=group_members, send=os.kill, clock=time.monotonic, pause=time.sleep):
    if pgid != owner:
        raise RuntimeError('Reserved wrapper must own its isolated session/process group')
    started = clock()
    signaled, actions = set(), []
    while True:
        members = reader(pgid, owner)
        if not members:
            return dict(status='all_formal_group_members_exited', process_group=pgid,
                actions=actions, elapsed_seconds=clock()-started,
                scope='guard-created isolated session; native diagnostic forbids detached descendants')
        sig = signal.SIGTERM if clock()-started < 30 else signal.SIGKILL
        for row in members:
            key = (row['pid'], row['start_ticks'], int(sig))
            if key in signaled:
                continue
            # Reconfirm membership and start identity immediately before signaling.
            if row not in reader(pgid, owner):
                continue
            try:
                send(row['pid'], sig)
                actions.append({**row, 'signal': int(sig)})
            except ProcessLookupError:
                pass
            signaled.add(key)
        # Even after KILL, keep the reservation until no live member remains.
        pause(0.2)
