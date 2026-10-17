"""One-time immutable snapshot and finite proposal publication, not execution."""
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import argparse
from campaign_io import BASE, WORK, RESULTS, atomic, heartbeat, sha, now
from core.accounting import RESOURCE_KEYS

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', type=int, default=1)
    revision = parser.parse_args().revision
    if revision < 1: raise ValueError('Positive snapshot revision required')
    heartbeat('publishing immutable A10 code snapshot and proposed finite preflight commands')
    destination = RESULTS / f'code_snapshot_v{revision}'
    stage = RESULTS / f'code_snapshot_v{revision}.staging'
    stage.mkdir(exist_ok=False)
    directories = ['core', 'legacy_basis', 'vendor_backend', 'vendor_vla']
    files = ['preflight_pi05.py', 'launch_preflight.py', 'test_cpu_contract.py', 'README.md',
             'basis_manifest.json', 'runtime_basis_manifest.json']
    for directory in directories:
        shutil.copytree(WORK / directory, stage / directory, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for filename in files:
        shutil.copyfile(WORK / filename, stage / filename)
    records = [{'path': str(p.relative_to(stage)), 'sha256': sha(p), 'bytes': p.stat().st_size}
               for p in sorted(stage.rglob('*')) if p.is_file()]
    atomic(stage / 'CODE_MANIFEST.json', {'version': f'A10-code-v{revision}', 'status': 'CPU_preparation_snapshot',
        'created_at_utc': now(), 'files': records, 'file_count': len(records),
        'logical_bytes': sum(r['bytes'] for r in records), 'gpu_validated': False,
        'historical_paths_modified': [], 'source_manifests': ['basis_manifest.json', 'runtime_basis_manifest.json']})
    os.rename(stage, destination)
    inputs = []
    assets = json.loads((BASE / 'receipts/A/A00_ASSETS.json').read_text())['assets']
    sft = next(r for r in assets if r['asset_id'] == 'pi05_mt50_sft_030000')
    for row in sft['files']:
        inputs.append({'path': row['resolved'], 'sha256': row.get('historical_sha256') or row.get('verified_sha256'),
                       'verification_now': 'size + historical identity' if row['bytes'] > 64*1024*1024 else 'sha256 matched'})
    token = ROOT / '.cache/huggingface-vla-corrector/hub/models--google--paligemma-3b-pt-224/snapshots/35e4f46485b4d07967e7e9935bc3786aad50687c'
    for p in sorted(token.iterdir()):
        if p.is_file():inputs.append({'path': str(p), 'sha256': sha(p), 'verification_now': 'full sha256'})
    directory = RESULTS / f'preflight_v{revision}'
    source_manifest = directory / 'source_manifest.json'
    source = {'source_id': 'A10-native-queue-diagnostic-shelf-place-v3-2026091900', 'task': 'shelf-place-v3',
              'parent_episode_id': 'A10-native-queue-diagnostic-shelf-place-v3-2026091900',
              'env_seed': 2026091900, 'generation_seed': 2026091901, 'suffix_seed': 2026091902,
              'split': 'development', 'proposed_only': True, 'selection': 'one fixed diagnostic identity; no outcome-based replacement'}
    atomic(source_manifest, {'campaign_id': 'corrector-sim-20260919', 'status': 'proposed_not_released',
                            'owner_host': platform.node(), 'sources': [source]})
    lineage = ROOT / 'embodied-ai-workspace/manifests/vla-baselines-20260911/legacy-pi05-mt50.files.json'
    for p in [source_manifest, lineage, RESULTS / 'interface_v1/interface.schema.json', RESULTS / 'interface_v1/examples.jsonl',
              BASE / 'contracts/P00_PREPARATION_CONTRACT_V1.md', BASE / 'contracts/DATA_LOG_CONTRACT_V1.md',
              BASE / 'contracts/INVENTORY_DECISIONS_V1.md']:
        inputs.append({'path': str(p), 'sha256': sha(p), 'verification_now': 'full sha256'})
    caps = dict.fromkeys(RESOURCE_KEYS, 0)
    caps.update(simulator_attempts=1, env_steps=1, vla_sampling_calls=5, flow_forward_calls=50)
    proposal = {'proposal_id': f'A10_NATIVE_QUEUE_PREFLIGHT_V{revision}', 'status': 'proposed_not_released',
        'task_id': 'A10_PREFLIGHT_NATIVE_V1', 'task_revision': 1, 'campaign_id': 'corrector-sim-20260919',
        'owner_host': platform.node(), 'node_role': 'A', 'wave_participants': ['A'],
        'code_manifest_path': str(destination / 'CODE_MANIFEST.json'),
        'source_manifest_path': str(source_manifest), 'source_manifest_sha256': sha(source_manifest),
        'source': source, 'checkpoint': sft['resolved'],
        'model_sha256': next(x['historical_sha256'] for x in sft['files'] if Path(x['path']).name == 'model.safetensors'),
        'interface_directory': str(RESULTS / 'interface_v1'), 'lineage_path': str(lineage),
        'required_inputs': inputs, 'horizons': [10,20,30,40,50],
        'resource_caps': caps, 'completed_rollouts': 0, 'model_initializations': 1,
        'environment_initializations': 1, 'environment_reset_calls': 1, 'state_restorations': 0,
        'max_retries': 0, 'timeout_seconds': 1800, 'kill_grace_seconds': 30,
        'max_process_wall_seconds_including_grace': 1830,
        'python': str(ROOT / 'embodied-ai-workspace/environments/lerobot/bin/python'),
        'occupancy_lifecycle': str(ROOT / 'gpu_occupancy_lifecycle.sh'),
        'hf_home': str(ROOT / '.cache/huggingface-vla-corrector'),
        'tokenizer_name': 'google/paligemma-3b-pt-224', 'tokenizer_revision': '35e4f46485b4d07967e7e9935bc3786aad50687c',
        'runtime_packages': {'torch':'2.7.1','numpy':'2.2.6','mujoco':'3.6.0','metaworld':'3.0.0','gymnasium':'1.2.3',
                             'transformers':'5.4.0','lerobot':'0.5.1','jsonschema':'4.26.0','safetensors':'0.7.0'},
        'resource_estimates': {'gpu_count': 1, 'reserved_GPU_wave': 'all eight A holders paused for the whole A-only command',
            'vram_peak_GiB_estimate': 40, 'host_ram_peak_GiB_estimate': 64, 'incremental_disk_GiB_estimate': 2,
            'estimates_are_measured': False, 'disk_quota_known': False,
            'model_weight_bytes_read': 9354050752, 'full_large_weight_hash_before_load': True,
            'output_retention': ['claim', 'events', 'resource_receipt', 'queue_checks', 'raw5plans', 'RGB/proprio current+next', 'one real transition', 'failures']},
        'not_covered': ['D/G0/Q GPU binding', 'Post/Velocity real gradient and sampler numerical checks',
                        'full episodes', 'MT50 trained corrector', 'multi-host wave barrier'],
        'abort_rule': 'stop on first budget violation, control stop, identity drift or technical failure; never retry or replace seed',
        'publication_is_authorization': False}
    atomic(directory / 'PROPOSAL.json', proposal)
    release_template = {'status': 'DRAFT_NOT_AUTHORIZED', 'campaign_id': proposal['campaign_id'],
        'task_id': proposal['task_id'], 'task_revision': 1, 'node_role': 'A', 'owner_host': platform.node(),
        'release_id': None, 'wave_id': None, 'run_id': None, 'shard_id': None,
        'proposal_sha256': sha(directory / 'PROPOSAL.json'), 'code_manifest_sha256': sha(destination / 'CODE_MANIFEST.json'),
        'resource_caps': caps, 'max_retries': 0, 'timeout_seconds': 1800, 'wave_participants': ['A'],
        'gpu_index': 0, 'gpu_uuid': 'GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe',
        'gpu_model': 'NVIDIA H100 80GB HBM3', 'driver': '535.161.08', 'runtime': 'lerobot-python3.12.13-torch2.7.1-cu126',
        'instructions': 'Analysis alone fills release/wave/run/shard, sets status released in campaign/releases and updates CONTROL active_compute_release_id/mode/allowed_task_ids/caps. This template has no authority.'}
    atomic(directory / 'RELEASE_TEMPLATE.json', release_template)
    commands = RESULTS / f'commands_v{revision}'; commands.mkdir(exist_ok=False)
    (commands / 'run_proposed_native_preflight.sh').write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\n'
        'if [[ $# != 1 ]]; then echo "usage: $0 /absolute/path/to/new-campaign-compute-release.json" >&2; exit 2; fi\n'
        f'exec /usr/bin/python3 -B "{destination}/launch_preflight.py" --campaign "{BASE}" --release "$1" --proposal "{directory}/PROPOSAL.json"\n')
    (commands / 'cpu_checks.sh').write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\n'
        f'check_dir="{BASE}/work/A/A10_cpu_checks_$(date +%s%N)"\n'
        f'PYTHONDONTWRITEBYTECODE=1 exec /usr/bin/python3 -B -m pytest -q -p no:cacheprovider "{destination}/test_cpu_contract.py" --basetemp="$check_dir"\n')
    for p in commands.glob('*.sh'):p.chmod(0o750)
    atomic(commands / 'COMMANDS.json', {'preflight': str(commands / 'run_proposed_native_preflight.sh'),
        'CPU_checks': str(commands / 'cpu_checks.sh'), 'working_directory': str(destination),
        'preflight_executed': False, 'training_launcher': None, 'formal_evaluation_launcher': None,
        'missing_reasons': {'training_launcher': 'B13 owns E1 training; P10 freezes actual budgets and initialization',
                            'formal_evaluation_launcher': 'P20/source/model releases and real MT50 backend binding pending; core scheduler prepared'},
        'core_eval_config': str(RESULTS / 'configs_v1/core_eval_matrix.json'),
        'E1_training_shape': str(RESULTS / 'configs_v1/E1_training_shape.json')})
    print(json.dumps({'snapshot_manifest': str(destination/'CODE_MANIFEST.json'), 'snapshot_sha256': sha(destination/'CODE_MANIFEST.json'),
                      'proposal': str(directory/'PROPOSAL.json'), 'proposal_sha256': sha(directory/'PROPOSAL.json'), 'code_files': len(records)}))


if __name__ == '__main__': main()
