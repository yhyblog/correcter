"""New-only artifacts and supplementary attempts over an immutable carry-in."""
from pathlib import Path
import fcntl
import hashlib
import json
import os
import time
import uuid
import numpy as np

PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE/'outputs/standalone_ablation_20260918'
OLD_ROOT = PACKAGE/'outputs/native10_training_20260916'
LOCK_PATH = Path('/tmp/corrector_standalone_ablation_20260918_budget.lock')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def destination(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Writes must stay in the isolated standalone output root')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def dump(path, value, *, exclusive=True):
    path = destination(path)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    if exclusive:
        with path.open('x') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    else:
        temporary = path.with_name(path.name+'.writing.'+uuid.uuid4().hex)
        temporary.write_text(payload); temporary.replace(path)


def arrays(path, **values):
    with destination(path).open('xb') as stream:
        np.savez_compressed(stream, **values)


def seal(path, **metadata):
    path = destination(Path(path)/'complete.json').parent
    if (path/'complete.json').exists():
        raise FileExistsError(path/'complete.json')
    dump(path/'complete.json', dict(status='complete', **metadata,
        files={str(p.relative_to(path)): sha256(p) for p in sorted(path.rglob('*')) if p.is_file()}))


def checked(path, expected):
    path = Path(path).resolve()
    if sha256(path) != expected:
        raise ValueError('File SHA mismatch: '+str(path))
    return path


def read(path):
    return json.loads(Path(path).read_text())


def sealed(path, expected=None):
    path = Path(path).resolve()
    if expected is not None: checked(path/'complete.json', expected)
    record = read(path/'complete.json')
    if record.get('status') != 'complete' or not record.get('files'):
        raise ValueError('Complete artifact seal required')
    actual = {str(p.relative_to(path)) for p in path.rglob('*')
        if p.is_file() and p != path/'complete.json'}
    if actual != set(record['files']):
        raise ValueError('Complete artifact inventory differs from actual files')
    for name, digest in record['files'].items():
        target = (path/name).resolve()
        if not target.is_relative_to(path): raise ValueError('Sealed child escapes artifact')
        checked(target, digest)
    return record


class AttemptLedger:
    """Count before any reset/replay; failed attempts never disappear."""
    def __init__(self, config, *, root=None, lock_path=None):
        self.config = config
        self.root = Path(root) if root is not None else ROOT
        self.lock_path = Path(lock_path) if lock_path is not None else LOCK_PATH
        ref = config['carry_in']['ledger']
        self.base = checked(ref['path'], ref['sha256'])
        self.legacy = checked(config['carry_in']['legacy_ledger_path'], ref['sha256'])
        self.base_stat = self._signature()

    def _signature(self):
        return tuple((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            for st in (self.base.stat(), self.legacy.stat()))

    def reserve(self, stage, kind, identity, *, resource='simulator_attempts', requested=1):
        from .protocol import require_stage_budget, PREFLIGHT, FORMAL, REPAIR
        if resource != 'simulator_attempts' or type(requested) is not int or requested != 1:
            raise ValueError('Only one counted simulator attempt; optimizer work is forbidden')
        if stage not in (PREFLIGHT, FORMAL, REPAIR) or kind not in ('candidate_restore', 'branch_including_restore'):
            raise ValueError('Capture, initialization replacements and unknown work are forbidden')
        if not isinstance(identity, str) or not identity.strip(): raise ValueError('Attempt identity required')
        with self.lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self._signature() != self.base_stat:
                raise ValueError('Immutable carry-in ledger changed')
            path = self.root/'budget/attempts.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            if any(row['number'] != index+1 or row['resource'] != resource or row['amount'] != 1
                   for index, row in enumerate(rows)):
                raise ValueError('Malformed supplementary ledger')
            if any(row['identity'] == identity for row in rows):
                raise ValueError('Attempt identity was already reserved; use an explicitly registered retry identity')
            used = sum(row['amount'] for row in rows if row['stage'] == stage)
            total = sum(row['amount'] for row in rows)
            require_stage_budget(self.config, stage, used=used, requested=1, total_used=total, resource=resource)
            if total+1 > 1500 or 48183+total+1 > 50000:
                raise ValueError('Supplement/cross-ledger hard limit exceeded')
            row = dict(number=len(rows)+1, stage=stage, kind=kind, identity=identity,
                resource=resource, amount=1, unix=time.time(),
                protocol_sha256=self.config['analysis_approval']['protocol_sha256'],
                carry_in_ledger_sha256=self.config['carry_in']['ledger']['sha256'],
                cumulative_simulator_attempts=48183+total+1, optimizer_updates=0)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a') as stream:
                stream.write(json.dumps(row)+'\n'); stream.flush(); os.fsync(stream.fileno())
            return row
