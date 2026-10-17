"""Read-only own-session enumeration for the all-holder exit acknowledgement."""
from pathlib import Path
from qio import process_identity

def session_members(saved):
    current=process_identity()
    if any(saved[k]!=current[k] for k in ('host','boot_id')):raise RuntimeError('different holder host/boot')
    leader=process_identity(saved['pid'])
    if leader and leader['start_ticks']!=saved['start_ticks']:raise RuntimeError('holder PID reused')
    rows=[]
    for f in Path('/proc').iterdir():
        if not f.name.isdigit():continue
        try:
            bits=(f/'stat').read_text().rsplit(') ',1)[1].split()
            if int(bits[3])==saved['pid'] and bits[0]!='Z':
                row=process_identity(int(f.name))
                if row:rows.append(row)
        except (OSError,ValueError,IndexError):continue
    if any(r['start_ticks']<saved['start_ticks'] for r in rows):raise RuntimeError('invalid holder ancestry')
    return rows
