"""Read-only /proc census, persisting only matches to the already listed VLA paths."""
import datetime
import json
import os
from pathlib import Path
import socket

WORK = Path(__file__).resolve().parent / 'storage_dependency'
identities = json.loads((WORK / 'PAYLOAD_IDENTITIES.json').read_text())['records']
targets = {row['realpath']: row for row in identities}
matches, errors, processes = [], [], 0
operation_scripts = {'resume_xvla_ranges.py', 'prepare_assets.py', 'train_metaworld.py', 'eval_metaworld.py', 'queue_runner.py'}
operation_matches = []
for process in Path('/proc').iterdir():
    if not process.name.isdigit():
        continue
    pid = int(process.name)
    if pid == os.getpid():
        continue
    processes += 1
    try:
        for fd in (process / 'fd').iterdir():
            try:
                target = os.readlink(fd)
                if target in targets:
                    flags_text = (process / 'fdinfo' / fd.name).read_text()
                    flags = int(next(line.split()[1] for line in flags_text.splitlines() if line.startswith('flags:')), 8)
                    access = {os.O_RDONLY: 'read', os.O_WRONLY: 'write', os.O_RDWR: 'read_write'}[flags & os.O_ACCMODE]
                    matches.append({'pid': pid, 'kind': 'open_fd', 'fd': int(fd.name), 'path': target, 'access': access})
            except FileNotFoundError:
                pass  # exited/closed between snapshots
        for line in (process / 'maps').read_text().splitlines():
            parts = line.split(maxsplit=5)
            if len(parts) == 6 and parts[5] in targets:
                matches.append({'pid': pid, 'kind': 'memory_mapping', 'path': parts[5], 'permissions': parts[1]})
        argv = (process / 'cmdline').read_bytes().decode(errors='replace').split('\0')
        script_args = [arg for arg in argv if arg.endswith('.py') and Path(arg).name in operation_scripts]
        if script_args:
            try:
                cwd = os.readlink(process / 'cwd')
            except OSError:
                cwd = ''
            if 'vla-baselines' in cwd or any('vla-baselines' in arg for arg in script_args):
                operation_matches.append({'pid': pid, 'script_names': [Path(s).name for s in script_args],
                                          'kind': 'possible_VLA_operation_requires_inspection'})
    except FileNotFoundError:
        continue
    except PermissionError as error:
        errors.append({'pid': pid, 'kind': 'permission_denied', 'operation': str(error.filename)})
result = {'hostname': socket.gethostname(), 'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'read_only': True, 'target_file_count': len(targets), 'visible_process_count': processes,
    'target_FD_or_mapping_matches': matches, 'possible_operation_processes': operation_matches,
    'inaccessible_processes': errors,
    'local_no_writer_observed': not errors and not operation_matches and not any(m.get('access') in ('write', 'read_write') for m in matches),
    'local_no_reader_or_writer_observed': not errors and not operation_matches and not matches,
    'limit': 'This container process namespace at one instant only; not proof of no future opens or cross-node writers. Recheck before an exact deletion release executes.',
    'processes_terminated': 0}
path = WORK / 'LOCAL_ACTIVE_USERS.json'
assert not path.exists()
temp = path.with_suffix('.pending.json')
temp.write_text(json.dumps(result, indent=2) + '\n')
os.replace(temp, path)
print(json.dumps(result))
