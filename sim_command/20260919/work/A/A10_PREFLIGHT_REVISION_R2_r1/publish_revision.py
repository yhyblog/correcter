"""Publish new immutable A-only CPU preparation artifacts. Never launches work."""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORK = Path(__file__).resolve().parent
OUT = BASE / 'results/A/A10_PREFLIGHT_REVISION_R2'
OLD = BASE / 'results/A/A10'
sys.path.insert(0, str(WORK / 'code'))
from core.initialization import EXPECTED_CAPS, CONTROL_MINIMUM_LIMITS


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def publish(path, value):
    assert not path.exists(), str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(pending, path)


assert not OUT.exists(), str(OUT)
OUT.mkdir()
code = OUT / 'code_snapshot_v4'
pending_code = OUT / 'code_snapshot_v4.pending'
shutil.copytree(WORK / 'code', pending_code)
files = sorted(p for p in pending_code.rglob('*') if p.is_file())
assert not any('__pycache__' in p.parts or '.pytest_cache' in p.parts for p in files)
parent_manifest = OLD / 'code_snapshot_v3/CODE_MANIFEST.json'
publish(pending_code / 'CODE_MANIFEST.json', {
    'version': 'A10-code-v4', 'status': 'CPU_preparation_snapshot',
    'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'parent_manifest': {'path': str(parent_manifest), 'sha256': sha(parent_manifest)},
    'files': [{'path': str(p.relative_to(pending_code)), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in files],
})
os.rename(pending_code, code)
pre = OUT / 'preflight_v4'
pre.mkdir()
publish(pre / 'external_source_manifest.json', (WORK / 'external_source_manifest.json').read_text())
publish(pre / 'source_manifest.json', (OLD / 'preflight_v3/source_manifest.json').read_text())
proposal = json.loads((OLD / 'preflight_v3/PROPOSAL.json').read_text())
proposal.update(proposal_id='A10_NATIVE_QUEUE_PREFLIGHT_V4', code_manifest_path=str(code / 'CODE_MANIFEST.json'),
    source_manifest_path=str(pre / 'source_manifest.json'), environment_initializations=2, environment_reset_calls=52,
    initialization_reset_calls=51, diagnostic_reset_calls=1, diagnostic_initial_states=1,
    taskset_seed=42, taskset_generated_goals=50, initialization_caps=EXPECTED_CAPS,
    control_minimum_limits=CONTROL_MINIMUM_LIMITS,
    external_source_manifest_path=str(pre / 'external_source_manifest.json'),
    external_source_manifest_sha256=sha(pre / 'external_source_manifest.json'),
    timeout_scope='diagnostic_process_only_including_all_initialization',
    restoration_observation_timeout_seconds=120,
    nominal_timed_child_TERM_deadline_seconds=1800, nominal_timed_child_KILL_deadline_seconds=1830,
    end_to_end_strict_upper_bound_seconds=None,
    timeout_accounting={
        'inside': ['repeated authorization/input SHA/device/runtime verification', 'heavy imports', 'model loading',
                   'all task-set/wrapper/diagnostic resets and initialization physics',
                   'five native samples', 'one policy control', 'diagnostic validation and cleanup'],
        'outside': ['prelaunch CPU authorization and full input hashing', 'NVML identity check and guard-active check',
                    'all-GPU reservation and holder release', 'reserved wrapper setup',
                    'reservation release', 'up to 120s occupancy-restoration observation'],
        'actual_times': 'LAUNCH_RESULT.json records preparation/reservation/timed-process/release/restoration/end-to-end; missing markers are null',
        'not_an_end_to_end_1830_second_bound': True,
    },
    counter_scope={
        'environment_instances': 'two native SawyerShelfPlaceEnvV3 constructor attempts; one additional Python wrapper counted separately',
        'environment_reset_calls': 'native SawyerXYZEnv.reset entries, 50 task-set +1 wrapper initialization +1 diagnostic',
        'reset_model_calls': 'two per native reset: direct call, then Gymnasium MujocoEnv.reset delegation',
        'initialization_physics_substeps': '104 reset_model *50 hand do_simulation *5 frames =26000; includes diagnostic reset settling',
        'policy_physics_substeps': 'one native control, zero-based 30Hz index0 =>floor(400/30)=13',
        'overlapping_dimensions': 'Do not sum aggregate reset count with its source subcounts or add settling frames to policy control count',
        'failure': 'durable entered attempts remain charged; returned/failed/incomplete tracked separately; no retries/refunds',
    })
proposal.pop('max_process_wall_seconds_including_grace', None)
for ref in proposal['required_inputs']:
    if ref['path'] == str(OLD / 'preflight_v3/source_manifest.json'):
        ref['path'] = str(pre / 'source_manifest.json')
proposal['required_inputs'].append({'path': str(pre / 'external_source_manifest.json'), 'sha256': sha(pre / 'external_source_manifest.json'), 'verification_now': 'full sha256; all 118 source identities checked CPU-only'})
workspace = BASE.parents[2]
for name in ('gpu_occupancy_lifecycle.sh', 'gpu_occupancy_guard.py', 'gpu_hold.py'):
    path = workspace / name
    proposal['required_inputs'].append({'path': str(path), 'sha256': sha(path), 'verification_now': 'full sha256'})
proposal['resource_estimates'].update(
    full_large_weight_hash_passes_before_or_inside_timed_child=2,
    model_weight_hash_bytes_read=2 * proposal['resource_estimates']['model_weight_bytes_read'],
    initialization_journal_records_upper_bound=10730,
    source_package_bytes_hashed=728991,
    estimate_note='40GiB VRAM/64GiB RAM/2GiB disk remain estimates; two full weight hash passes plus model loader I/O; no real runtime measurement',
)
proposal['resource_estimates']['output_retention'].extend(['initialization_events_and_receipt', 'wave_timing', 'LAUNCH_RESULT', 'restoration_observation'])
publish(pre / 'PROPOSAL.json', proposal)
template = json.loads((OLD / 'preflight_v3/RELEASE_TEMPLATE.json').read_text())
template.update(proposal_sha256=sha(pre / 'PROPOSAL.json'), code_manifest_sha256=sha(code / 'CODE_MANIFEST.json'),
    initialization_caps=EXPECTED_CAPS, kill_grace_seconds=30, timeout_scope=proposal['timeout_scope'],
    external_source_manifest_sha256=proposal['external_source_manifest_sha256'])
template['instructions'] = ('DRAFT only. Analysis must fill unique release/wave/run/shard IDs, set status=released in campaign/releases, '
    'register exact task/revision/owner/release/status in TASK_BOARD, and update CONTROL mode/active_compute_release_id/allowed_task_ids '
    'with every control_minimum_limits field from PROPOSAL. CPU checker never starts a wave; real launcher separately verifies current NVML identity.')
publish(pre / 'RELEASE_TEMPLATE.json', template)
publish(pre / 'RESOURCE_RECEIPT_TEMPLATE.json', {
    'status': 'TEMPLATE_NOT_EXECUTED', 'resource_caps': proposal['resource_caps'], 'initialization_caps': EXPECTED_CAPS,
    'actual_resource_counts': None, 'actual_initialization_entered': None, 'actual_initialization_returned': None,
    'actual_initialization_counts_by_source': None, 'actual_timing': None,
    'missing_reason': 'Future diagnostic has no compute release and has not executed; R2 CPU task counts are reported separately as zero',
})
commands = OUT / 'commands_v4'
commands.mkdir()
common = f'--campaign "{BASE}" --release "$1" --proposal "{pre / "PROPOSAL.json"}"'
publish(commands / 'run_proposed_native_preflight.sh', f'''#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 1 ]]; then echo "usage: $0 /absolute/path/to/new-compute-release.json" >&2; exit 2; fi
exec /usr/bin/python3 -B "{code / 'launch_preflight.py'}" {common}
''')
publish(commands / 'check_authorization_cpu.sh', f'''#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 1 ]]; then echo "usage: $0 /absolute/path/to/release.json" >&2; exit 2; fi
exec /usr/bin/python3 -B "{code / 'authorize_cpu.py'}" {common}
''')
for path in commands.glob('*.sh'):
    path.chmod(0o755)
publish(commands / 'COMMANDS.json', {
    'real_preflight': str(commands / 'run_proposed_native_preflight.sh'),
    'CPU_authorization_only': str(commands / 'check_authorization_cpu.sh'),
    'working_directory': str(code), 'preflight_executed': False, 'interface_revision': 'corrector-sim-interface/1',
    'CPU_negative_test_release': str(BASE / 'releases/P00_PREFLIGHT_CORRECTIONS_V1.json'),
    'CPU_negative_test_expected_exit_code': 2,
    'forbidden_dry_run': 'Do not execute real preflight shell as a dry run',
    'future_release_required': True,
})
publish(pre / 'INITIALIZATION_STATIC_AUDIT.json', {
    'scope': 'source-only, no imports of simulator/model packages and no reset',
    'external_source_manifest': {'path': str(pre / 'external_source_manifest.json'), 'sha256': sha(pre / 'external_source_manifest.json')},
    'static_success_path_counts_and_finite_caps': EXPECTED_CAPS,
    'derivation': [
        {'source': 'vendor_vla/src/lerobot/envs/metaworld.py:158', 'fact': 'MT1(shelf-place-v3, seed=42), then second native instance, set_task, one env.reset'},
        {'source': 'metaworld/__init__.py:97,114,193', 'fact': '_N_GOALS=50; MT1 calls _make_tasks once with one environment; one construction and exactly 50 native reset calls; no retry loop'},
        {'source': 'vendor_backend/metaworld_pi05.py:219', 'fact': 'reset_episode ensures wrapper once then performs one diagnostic reset after explicit seed setup'},
        {'source': 'metaworld/sawyer_xyz_env.py:664; gymnasium/envs/mujoco/mujoco_env.py:169', 'fact': 'each native reset executes reset_model directly and again via super.reset =>104 calls'},
        {'source': 'metaworld/envs/sawyer_shelf_place_v3.py:122; metaworld/sawyer_xyz_env.py:684', 'fact': 'each shelf reset_model calls _reset_hand(steps=50), each hand call do_simulation has frame_skip5 =>5200 calls/26000 substeps'},
        {'source': 'metaworld/envs/sawyer_shelf_place_v3.py:26-33,128', 'fact': 'goal y in[.8,.9], object y in[.5,.6]: separation>=.2, so rejection while(<.1) does not repeat for valid frozen bounds; no retry or extra episode'},
        {'source': 'vendor_backend/metaworld_pi05.py:266; vendor_backend/contracts.py:224', 'fact': 'one backend native step bypasses wrapper auto-reset; control index0 at400/30Hz requests13 substeps'},
    ],
    'constructor_and_forward_work': 'MjModel/MjData construction, mj_resetData, mj_forward and rendering are initialization/diagnostic overhead, not extra policy steps; included in child wall time. Dynamic physics nstep requests are separately counted.',
    'count_guard': 'instrument exact native constructors/reset/reset_model/do_simulation before entry; hard stop before any count exceeds the frozen cap; retain partial work and source',
    'actual_preparation_counts': {'model_GPU_inference_calls': 0, 'environment_instances': 0, 'environment_reset_calls': 0,
                                  'simulator_attempts': 0, 'optimizer_updates': 0},
    'real_environment_executability': 'unverified; no GPU/reset/simulation ran',
})
publish(OUT / 'CPU_READY_v4.json', {
    'task_id': 'A10_PREFLIGHT_REVISION_R2', 'status': 'CPU_correction_artifacts_published_not_compute_release',
    'code_manifest': {'path': str(code / 'CODE_MANIFEST.json'), 'sha256': sha(code / 'CODE_MANIFEST.json')},
    'proposal': {'path': str(pre / 'PROPOSAL.json'), 'sha256': sha(pre / 'PROPOSAL.json')},
    'release_template': {'path': str(pre / 'RELEASE_TEMPLATE.json'), 'sha256': sha(pre / 'RELEASE_TEMPLATE.json')},
    'commands': {'path': str(commands / 'COMMANDS.json'), 'sha256': sha(commands / 'COMMANDS.json')},
    'public_interface_unchanged': str(OLD / 'interface_v1/INTERFACE_READY.json'),
    'publication_is_authorization': False,
})
print(json.dumps({'published': str(OUT), 'code_manifest_sha256': sha(code / 'CODE_MANIFEST.json'),
                  'proposal_sha256': sha(pre / 'PROPOSAL.json'), 'code_file_count': len(files)}))
