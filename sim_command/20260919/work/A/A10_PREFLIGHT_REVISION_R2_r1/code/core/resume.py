"""Explicit source shards and append-only attempt ownership; no legacy READY discovery."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import uuid
from .validation import ContractError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def core_cells(Hs):
    """MASTER_PLAN E4/E9 has 16 cells, not a 5x4 Cartesian product."""
    return [{'H': H, 'method': method} for H in Hs
            for method in (('N', 'R', 'Post', 'Velocity') if H == 10 else ('N', 'Post', 'Velocity'))]


def validate_shards(shards):
    sources, splits, assignments = {}, {}, []
    for shard in shards:
        identity = shard['identity']
        if shard.get('assignment_rule') != 'explicit_analysis_manifest' or not all(identity.get(k) for k in ('shard_id', 'hostname', 'release_id')):
            raise ContractError('Explicit analysis-assigned host/shard/release required')
        for row in shard['sources']:
            source = row['source_id']
            if source in sources:
                raise ContractError(f'Source repeated across shard rows: {source}')
            if row['host'] != identity['hostname'] or row['node_role'] != identity['node_role']:
                raise ContractError('Source assigned to a different host than its shard')
            sources[source] = identity['hostname']
            parent = row['parent_episode_id']
            if parent in splits and splits[parent] != row['split']:
                raise ContractError('Parent episode split leakage in source shards')
            splits[parent] = row['split']
            if not row['Hs'] or len(set(row['Hs'])) != len(row['Hs']) or any(h not in (10, 20, 30, 40, 50) for h in row['Hs']):
                raise ContractError('Invalid source horizons')
            required_methods = {c['method'] for c in core_cells(row['Hs'])}
            if set(row['methods']) != required_methods or len(row['methods']) != len(required_methods):
                raise ContractError('Required core cells must remain on the same host; external addenda use their own frozen matrix')
            if type(row['seed']) is not int or row['seed'] < 0:
                raise ContractError('Explicit nonnegative source seed required')
            assignments.append({**row, 'shard_id': identity['shard_id'], 'cells': core_cells(row['Hs'])})
    return assignments


class RunStore:
    """A failed/incomplete physical attempt is never silently retried or replaced."""
    def __init__(self, root, identity):
        required = {'campaign_id', 'task_id', 'task_revision', 'release_id', 'code_sha256',
                    'config_sha256', 'data_sha256', 'model_sha256', 'shard_sha256', 'hostname', 'source_id'}
        if not required <= identity.keys():
            raise ContractError('Incomplete run identity')
        self.identity, self.key = identity, digest(identity)
        self.path = Path(root) / self.key
        self.token = None

    def claim(self):
        self.path.mkdir(parents=True, exist_ok=True)
        completed = self.path / 'COMPLETE.json'
        if completed.exists():
            record = json.loads(completed.read_text())
            if record['identity'] != self.identity:
                raise ContractError('Completed identity mismatch')
            for artifact in record['artifacts']:
                target = (self.path / artifact['path']).resolve()
                if not target.is_relative_to(self.path.resolve()) or sha(target) != artifact['sha256']:
                    raise ContractError('Completed artifact missing, outside run, or changed')
            return {'status': 'reuse_complete', 'receipt': record, 'new_physical_attempts': 0}
        claim = self.path / 'CLAIM.json'
        record = {'identity': self.identity, 'token': uuid.uuid4().hex, 'pid': os.getpid(),
                  'process_start_ticks': Path('/proc/self/stat').read_text().split()[21],
                  'hostname': platform.node(), 'created_at_utc': datetime.now(timezone.utc).isoformat()}
        try:
            with claim.open('x') as stream:
                stream.write(json.dumps(record, indent=2) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as error:
            raise ContractError('Claim exists without verified completion; analysis recovery release required, no stale takeover') from error
        self.token = record['token']
        return {'status': 'claimed', 'new_physical_attempts': 0, 'path': str(self.path)}

    def complete(self, artifacts, resources):
        claim = json.loads((self.path / 'CLAIM.json').read_text())
        if self.token is None or claim['token'] != self.token:
            raise ContractError('Not this claim owner')
        records = []
        for path in artifacts:
            target = Path(path).resolve()
            if not target.is_relative_to(self.path.resolve()) or not target.is_file():
                raise ContractError('Artifact must be a file within owned run')
            records.append({'path': str(target.relative_to(self.path.resolve())), 'sha256': sha(target), 'bytes': target.stat().st_size})
        record = {'identity': self.identity, 'artifacts': records, 'resources': resources, 'status': 'complete'}
        temporary = self.path / ('complete.tmp.' + self.token)
        temporary.write_text(json.dumps(record, allow_nan=False, indent=2) + '\n')
        os.link(temporary, self.path / 'COMPLETE.json')  # atomic no-overwrite publication
        # Retain the tiny temp as evidence; no deletion without a cleanup manifest.
        return record
