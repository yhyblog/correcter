"""New-workflow-only writes, immutable completed records and attempt accounting."""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import numpy as np

PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE / 'outputs/native10_training_20260916'
LOCK_PATH = Path('/tmp/corrector_native10_training_20260916_budget.lock')
CACHE_PATH = Path('/tmp/corrector_native10_training_20260916_budget_state.json')


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def destination(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Writes outside the new workflow output are forbidden')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def dump(path, value, *, exclusive=True):
    path = destination(path)
    if exclusive and path.exists():
        raise FileExistsError(path)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if exclusive:
        # Mounted storage does not promise hard-link/flock support. Exclusive
        # creation prevents replacement; only a later complete.json seals it.
        with path.open('x') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        temporary = path.with_name(path.name + '.writing.' + uuid.uuid4().hex)
        temporary.write_text(payload)
        temporary.replace(path)



def arrays(path, **values):
    path = destination(path)
    if path.exists():
        raise FileExistsError(path)
    with path.open('xb') as stream:
        np.savez_compressed(stream, **values)


def seal(path, **metadata):
    path = destination(path / 'complete.json').parent
    records = {str(p.relative_to(path)): sha256(p) for p in sorted(path.rglob('*')) if p.is_file()}
    dump(path / 'complete.json', dict(status='complete', files=records, **metadata))


class AttemptLedger:
    """Reserve before simulator creation/reset. Failures and retries stay counted.

    The analysis document hash and immutable protocol are checked on every reserve.
    Optimizer updates have a separate resource; neither is inferred from old budgets.
    """
    def __init__(self, config):
        self.config = config

    def reserve(self, stage, kind, identity, *, resource='simulator_attempts', requested=1):
        from .protocol import require_stage_budget
        folder = destination(ROOT / 'budget/attempts.jsonl').parent
        path = folder / 'attempts.jsonl'
        state_path = CACHE_PATH
        with LOCK_PATH.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            size = path.stat().st_size if path.exists() else 0
            state = json.loads(state_path.read_text()) if state_path.exists() else None
            if state is None or state.get('ledger') != str(path) or state.get('bytes') != size:
                rows = [json.loads(row) for row in path.read_text().splitlines()] if path.exists() else []
                state = dict(ledger=str(path), bytes=size, records=len(rows), totals={}, stages={})
                for row in rows:
                    key = row['resource']
                    state['totals'][key] = state['totals'].get(key, 0) + row['amount']
                    stage_key = row['stage'] + ':' + key
                    state['stages'][stage_key] = state['stages'].get(stage_key, 0) + row['amount']
            stage_key = stage + ':' + resource
            used = state['stages'].get(stage_key, 0)
            total = state['totals'].get(resource, 0)
            require_stage_budget(self.config, stage, used=used, requested=requested,
                                 total_used=total, resource=resource)
            approval = self.config['analysis_approval']
            if sha256(approval['document_path']) != approval['document_sha256']:
                raise ValueError('Analysis protocol document changed')
            row = dict(number=state['records']+1, stage=stage, kind=kind, identity=str(identity),
                       resource=resource, amount=requested, unix=time.time(),
                       protocol_sha256=approval['protocol_sha256'])
            with path.open('a') as stream:
                stream.write(json.dumps(row) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            state.update(bytes=path.stat().st_size, records=row['number'])
            state['totals'][resource] = total + requested
            state['stages'][stage_key] = used + requested
            temporary = state_path.with_suffix('.writing.' + uuid.uuid4().hex)
            temporary.write_text(json.dumps(state))
            temporary.replace(state_path)
            return row
