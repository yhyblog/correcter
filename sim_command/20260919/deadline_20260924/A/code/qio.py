"""Small, auditable control-plane primitives. No model or hardware imports."""
import datetime
import hashlib
import json
import os
import socket
import time
import uuid
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
CAMPAIGN = PACKAGE.parents[1]
QUEUE = CAMPAIGN / "persistent_queue"


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':')) + '\n').encode()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path, maximum=64 * 1024**2):
    p = Path(path)
    if p.stat().st_size > maximum:
        raise ValueError('JSON size limit: ' + str(p))
    return json.loads(p.read_text())


def ref(path):
    p = Path(path).absolute()
    return dict(path=str(p), realpath=str(p.resolve()), sha256=sha(p),
                size_bytes=p.stat().st_size)


def verify(row, base=CAMPAIGN):
    p = Path(row['path'])
    if not p.is_absolute():
        p = base / p
    if 'realpath' in row and str(p.resolve()) != row['realpath']:
        raise ValueError('realpath mismatch: ' + str(p))
    if 'size_bytes' in row and p.stat().st_size != row['size_bytes']:
        raise ValueError('size mismatch: ' + str(p))
    if sha(p) != row['sha256']:
        raise ValueError('SHA mismatch: ' + str(p))
    return p


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def new_json(path, value, limit=32 * 1024**2):
    path = Path(path)
    raw = canonical(value)
    if len(raw) > limit:
        raise ValueError('control record byte limit')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    sync_dir(path.parent)
    return path


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.update.' + uuid.uuid4().hex)
    new_json(temp, value)
    os.replace(temp, path)
    sync_dir(path.parent)


def append(path, value, max_bytes=64 * 1024**2):
    path = Path(path)
    raw = canonical(value)
    if path.exists() and path.stat().st_size + len(raw) > max_bytes:
        raise ValueError('control journal byte limit: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('ab') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def process_identity(pid=None):
    pid = os.getpid() if pid is None else int(pid)
    try:
        fields = Path('/proc', str(pid), 'stat').read_text().rsplit(') ', 1)[1].split()
        return dict(host=socket.gethostname(), boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    pid=pid, state=fields[0], ppid=int(fields[1]), pgid=int(fields[2]),
                    start_ticks=int(fields[19]))
    except (OSError, ValueError, IndexError):
        return None


def same_process(expected):
    actual = process_identity(expected['pid'])
    return bool(actual and actual['state'] != 'Z' and
                all(actual[k] == expected[k] for k in ('host', 'boot_id', 'pid', 'start_ticks')))


def under(path, root):
    path = Path(path).resolve()
    path.relative_to(Path(root).resolve())
    return path
