"""Read only the already listed VLA payload candidates and retained X base."""
import datetime
import hashlib
import json
import os
from pathlib import Path

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORKSPACE = BASE.parents[2]
WORK = Path(__file__).resolve().parent
REVIEW = WORK / 'storage_dependency'
REVIEW.mkdir(exist_ok=True)
source = json.loads((BASE / 'receipts/A/STORAGE_REFERENCE_CHECK_r1.json').read_text())
paths = []
for candidate in source['A_candidates']:
    root = Path(candidate['absolute_path'])
    if '/smolvla/' in str(root) and root.name in {f'{i:06d}' for i in range(5000, 50000, 5000)}:
        for name in ('pretrained_model/model.safetensors', 'training_state/optimizer_state.safetensors'):
            paths.append((root / name, 'Smol_intermediate_large_payload'))
for candidate in source['B_reported_candidates_metadata_confirmed_by_A']:
    for entry in candidate['files']:
        paths.append((Path(entry['path']), 'X_download_fragment'))
paths.append((WORKSPACE / 'embodied-ai-workspace/models/base/xvla-cdb7964/model.safetensors', 'retained_X_base'))
assert len(paths) == 28, len(paths)
records = []
for index, (path, purpose) in enumerate(paths, 1):
    resolved = path.resolve(strict=True)
    assert resolved.is_relative_to(WORKSPACE / 'embodied-ai-workspace')
    before = resolved.stat()
    h = hashlib.sha256()
    with resolved.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    after = resolved.stat()
    assert (before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino)
    row = {'path': str(path), 'realpath': str(resolved), 'purpose': purpose, 'bytes': before.st_size,
           'mtime_ns': before.st_mtime_ns, 'device': before.st_dev, 'inode': before.st_ino,
           'nlink': before.st_nlink, 'sha256': h.hexdigest(), 'changed_during_hash': False}
    records.append(row)
    with (REVIEW / 'payload_hash_progress.jsonl').open('a') as stream:
        stream.write(json.dumps(row) + '\n')
        stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'completed': index, 'total': len(paths), 'path': str(path), 'bytes': before.st_size}), flush=True)
path = REVIEW / 'PAYLOAD_IDENTITIES.json'
assert not path.exists()
temp = path.with_suffix('.pending.json')
temp.write_text(json.dumps({'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'file_count': len(records), 'logical_bytes_read': sum(r['bytes'] for r in records),
    'records': records, 'read_only': True, 'deleted_files': 0}, indent=2) + '\n')
os.replace(temp, path)
print(json.dumps({'completed_manifest': str(path)}), flush=True)
