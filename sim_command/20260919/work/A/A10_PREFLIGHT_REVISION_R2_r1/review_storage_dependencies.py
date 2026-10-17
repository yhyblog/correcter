"""Targeted VLA references/metadata only; never deletes or resumes old work."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
SPACE = BASE.parents[2]
VLA = SPACE / 'embodied-ai-workspace'
WORK = Path(__file__).resolve().parent / 'storage_dependency'
SMOL = VLA / 'artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints'
X = VLA / 'models/base/xvla-cdb7964'
PAYLOAD = WORK / 'PAYLOAD_IDENTITIES.json'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ref(path):
    return {'path': str(path), 'sha256': sha(path)}


def publish(path, value):
    assert not path.exists(), str(path)
    tmp = path.with_name(path.name + '.pending')
    tmp.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, path)


def header(path):
    with path.open('rb') as stream:
        size = struct.unpack('<Q', stream.read(8))[0]
        assert 0 < size < 16 * 1024 * 1024
        raw = stream.read(size)
    value = json.loads(raw)
    tensors = {k: v for k, v in value.items() if k != '__metadata__'}
    end = max(v['data_offsets'][1] for v in tensors.values())
    assert path.stat().st_size == 8 + size + end
    layout = {k: {'shape': v['shape'], 'dtype': v['dtype']} for k, v in tensors.items()}
    return {'path': str(path), 'tensor_count': len(tensors), 'header_sha256': hashlib.sha256(raw).hexdigest(),
            'layout_sha256': hashlib.sha256(json.dumps(layout, sort_keys=True).encode()).hexdigest(),
            'payload_exactly_covers_file': True, 'format_metadata': value.get('__metadata__'),
            'weights_loaded': False}


payloads = json.loads(PAYLOAD.read_text())
for row in payloads['records']:
    path = Path(row['realpath'])
    stat = path.stat()
    assert (stat.st_size, stat.st_mtime_ns, stat.st_ino) == (row['bytes'], row['mtime_ns'], row['inode'])
retained_x = next(r for r in payloads['records'] if r['purpose'] == 'retained_X_base')
download_path = VLA / 'artifacts/vla-baselines/preparation/20260911/xvla.download.json'
download = json.loads(download_path.read_text())
expected = next(r for r in download['files'] if r['path'] == 'model.safetensors')
metadata = (X / '.cache/huggingface/download/model.safetensors.metadata').read_text().splitlines()
assert retained_x['sha256'] == expected['sha256'] == expected['remote_lfs_sha256'] == metadata[1]
assert retained_x['bytes'] == expected['bytes']
assert metadata[0] == download['source']['revision'] == 'cdb7964e4fe842935d671bfab5a5ebe00a96648c'

roots = [VLA / 'projects/vla-baselines/configs', VLA / 'projects/vla-baselines/protocols',
         VLA / 'artifacts/vla-baselines/coordination/20260912/machine-b',
         VLA / 'artifacts/vla-baselines/evaluations/metaworld',
         VLA / 'artifacts/vla-baselines/preparation/smoke-eval/smolvla',
         VLA / 'artifacts/vla-baselines/preparation/smoke-eval/xvla',
         BASE / 'contracts', BASE / 'manifests', BASE / 'releases']
b_result = json.loads((BASE / 'receipts/B/B10_RESULT.json').read_text())
for p in sorted((BASE / 'results/B/B10').glob('*/configs')):
    roots.append(p)
cmd = ['rg', '--files', *map(str, roots), '-g', '*.json', '-g', '*.md', '-g', '*.py', '-g', '*.sh', '-g', '*.log']
listing = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.splitlines()
files = [Path(p) for p in listing]
explicit = [VLA / 'projects/vla-baselines/launchers/train_metaworld.py',
            VLA / 'projects/vla-baselines/launchers/resume_xvla_ranges.py', download_path,
            VLA / 'projects/upstream/lerobot-smolvla-8fff0fd/src/lerobot/utils/train_utils.py',
            VLA / 'projects/upstream/lerobot-smolvla-8fff0fd/src/lerobot/configs/train.py',
            VLA / 'projects/upstream/lerobot-smolvla-8fff0fd/src/lerobot/scripts/lerobot_train.py',
            SMOL / '050000/pretrained_model/train_config.json']
files = sorted(set(files + explicit))
candidate_dirs = [SMOL / f'{step:06d}' for step in range(5000, 50000, 5000)]
strong_hits, stage_number_mentions, file_refs = [], [], []
for path in files:
    text = path.read_text(errors='replace')
    file_refs.append(ref(path))
    bookkeeping = any(word in path.name.lower() for word in ('inventory', 'storage', 'candidates', 'retention', 'acceptance'))
    for line_no, line in enumerate(text.splitlines(), 1):
        for directory in candidate_dirs:
            qualified_relative = 'mt50-smolvla-s42-mb-20260912-v1/checkpoints/' + directory.name
            if str(directory) in line or qualified_relative in line:
                strong_hits.append({'file': str(path), 'line': line_no, 'candidate': str(directory),
                                    'kind': 'inventory_or_retention_bookkeeping' if bookkeeping else 'specific_runtime_reference_requires_review',
                                    'excerpt': line.strip()[:400]})
        if re.search(r'Checkpoint policy after step (?:5000|10000|15000|20000|25000|30000|35000|40000|45000)\b', line):
            stage_number_mentions.append({'file': str(path), 'normalized_text_line': line_no,
                'kind': 'checkpoint_creation_history_not_selected_model_dependency', 'excerpt': line.strip()[:250]})
specific_hits = [h for h in strong_hits if h['kind'] == 'specific_runtime_reference_requires_review']

headers = [header(SMOL / '050000/pretrained_model/model.safetensors'),
           header(SMOL / '050000/training_state/optimizer_state.safetensors')]
for directory in candidate_dirs:
    value = header(directory / 'pretrained_model/model.safetensors')
    assert value['layout_sha256'] == headers[0]['layout_sha256']
    headers.append(value)
assert (SMOL / 'last').resolve() == SMOL / '050000'
cfg = json.loads((SMOL / '050000/pretrained_model/train_config.json').read_text())
assert cfg['resume'] is False and cfg['policy']['use_peft'] is False
assert json.loads((SMOL / '050000/training_state/training_step.json').read_text())['step'] == 50000
small_retained = []
for directory in [*candidate_dirs, SMOL / '050000']:
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.name not in ('model.safetensors', 'optimizer_state.safetensors'):
            small_retained.append({**ref(path), 'bytes': path.stat().st_size})
log_path = VLA / 'artifacts/vla-baselines/coordination/20260912/machine-b/mt50-smolvla-s42-mb-20260912-v1.log'
log = log_path.read_text(errors='replace')
progress = list(map(int, re.findall(r'(\d+)/100000', log)))
checkpoint_steps = list(map(int, re.findall(r'Checkpoint policy after step (\d+)', log)))
status_path = VLA / 'artifacts/vla-baselines/coordination/20260912/machine-b/queue-status.json'
status = json.loads(status_path.read_text())
assert status['compute_running'] is False and status['phase'] == 'failed'

evidence = {
    'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope_roots': list(map(str, roots)), 'reference_files_count': len(file_refs), 'reference_files': file_refs,
    'candidate_specific_hits': strong_hits, 'noninventory_specific_reference_count': len(specific_hits),
    'checkpoint_save_history': stage_number_mentions, 'safetensors_header_checks': headers,
    'retained_small_configs_processors_rng_scheduler_and_lineage': small_retained,
    'Smol_latest_complete_checkpoint': 50000, 'Smol_last_alias_target': str((SMOL / 'last').resolve()),
    'Smol_largest_observed_log_progress': max(progress), 'Smol_logged_checkpoint_steps': checkpoint_steps,
    'Smol_old_queue_status': {'path': str(status_path), 'sha256': sha(status_path),
        'old_host': status['hostname'], 'phase': status['phase'], 'compute_running': status['compute_running'], 'error': status['error']},
    'Smol_resume_chain': 'TrainPipelineConfig resume binds the chosen config parent to policy weights and its checkpoint parent to load_training_state; load_training_state reads only that checkpoint training_state. 050000 is self-contained, not a delta depending on005000..045000.',
    'Smol_compatibility_limit': 'Header/file-format and source dependency checks only; no model loading or claim of new-host GPU runtime compatibility',
    'X_retained_complete_base': retained_x, 'X_source_download_receipt': ref(download_path),
    'X_source_revision': metadata[0], 'X_download_complete_current_full_SHA_matches': True,
    'previous_false_positive': 'A previous basename030000 search hit legacy-pi05-mt50 inventory; that is Pi05 SFT, not a dependency on Smol030000. Qualified-path review excludes it.',
    'scope_limit': 'Known current Corrector campaign and VLA-baselines queue/config/evaluation lineage; this is not a global scan or a lease against future users on other nodes',
    'probe_recovery': 'Direct env site-packages/train_utils path absent (rg exit2); editable .pth located the pinned upstream lerobot-smolvla source; no code executed.',
}
publish(WORK / 'REFERENCE_AND_LINEAGE_REVIEW.json', evidence)
print(json.dumps({'reference_files': len(file_refs), 'specific_dependency_hits': len(specific_hits),
    'Smol_checkpoint': 50000, 'Smol_log_progress': max(progress), 'X_full_SHA_matches': True,
    'large_candidate_files': 27, 'delete_count': 0}))
