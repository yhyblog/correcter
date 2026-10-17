"""New native V2: exclusive claim, complete identity guards, one A-only lifecycle."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
from core.release import load_authorization, verify_device
from core.validation import ContractError
from core.initialization import summarize_initialization
from core.accounting import summarize
from core.graphics_contract import reconcile
from core.wave_timing import stamp, mark, write_new, run_forwarded, observe_restoration, timing_summary


def claim_release(campaign, release):
    claims = Path(campaign).resolve() / 'results/A/P10_native_release_claims'
    claims.mkdir(parents=True, exist_ok=True)
    path = claims / (release['release_id'] + '.json')
    write_new(path, {'release_id': release['release_id'], 'release_sha256': release['_sha256'],
        'run_id': release['run_id'], 'claimed_at': stamp(), 'launcher_pid': os.getpid(),
        'consumed_on_success_or_failure': True, 'remaining_caps_reusable': False})
    return path


def child_environment(proposal, cache, parent=None):
    env = dict(os.environ if parent is None else parent)
    frozen = proposal['cuda_environment']
    if env.get('NVIDIA_VISIBLE_DEVICES') != frozen['NVIDIA_VISIBLE_DEVICES']:
        raise ContractError('Existing container NVIDIA visibility differs; do not rewrite metadata')
    env.update(frozen)
    root = Path(proposal['isolation_root'])
    env.update(PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        HF_HOME=proposal['hf_home'], MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl',
        OMP_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false', PYTORCH_NVML_BASED_CUDA_CHECK='0',
        LD_LIBRARY_PATH=':'.join([str(root/'isolation/lib'), proposal['python_library_directory'],
                                 '/usr/lib/x86_64-linux-gnu','/lib/x86_64-linux-gnu']),
        __EGL_VENDOR_LIBRARY_FILENAMES=str(root/'isolation/vendor/10_nvidia.json'),
        XDG_CACHE_HOME=str(cache/'xdg'), CUDA_CACHE_PATH=str(cache/'cuda'), TORCH_HOME=str(cache/'torch'))
    for key in ('LD_PRELOAD', '__EGL_VENDOR_LIBRARY_DIRS', 'MUJOCO_EGL_DEVICE_ID'):
        env.pop(key, None)
    return env


def main():
    start = stamp()
    parser = argparse.ArgumentParser()
    for key in ('campaign', 'release', 'proposal'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    # Metadata denial is CPU-only. A valid new release is consumed BEFORE full
    # hashing/identity checks, so input mismatch cannot enable another attempt.
    _, release, proposal = load_authorization(args.campaign, args.release, args.proposal, metadata_only=True)
    claim = claim_release(args.campaign, release)
    root = Path(__file__).resolve().parent
    directory = Path(args.campaign).resolve()/'results/A/P10_launcher_runs'/release['run_id']
    directory.mkdir(parents=True, exist_ok=False)
    write_new(directory/'launch_identity.json', dict(release=release, proposal_sha256=proposal['_sha256'],
              automatic_retry=False, release_claim=str(claim), started_at=start))
    with (directory/'wave_timing.jsonl').open('x') as stream:
        stream.write(json.dumps({'phase':'launcher_started', **start}) + '\n')
        stream.flush(); os.fsync(stream.fileno())
    result, error, restoration, lifecycle_entered = None, None, None, False
    resources = dict(status='not_entered', actual_counts=None, missing_reason='No diagnostic journal; no counts inferred')
    try:
        _, checked_release, proposal = load_authorization(args.campaign, args.release, args.proposal)
        if release['_sha256'] != checked_release['_sha256']:
            raise ContractError('Release changed after exclusive claim')
        verify_device(release, proposal)
        guard = Path(proposal['occupancy_lifecycle']).with_name('gpu_occupancy_guard.py')
        subprocess.run(['/usr/bin/python', str(guard), 'active'], check=True)
        cache = Path(args.campaign).resolve()/'work/A/P10_runtime_cache'/release['run_id']
        cache.mkdir(parents=True, exist_ok=False)
        env = child_environment(proposal, cache)
        command = [proposal['occupancy_lifecycle'], 'run', '--', proposal['python'], '-B', str(root/'run_reserved_diagnostic.py'),
            '--campaign', str(Path(args.campaign).resolve()), '--release', str(Path(args.release).resolve()),
            '--proposal', str(Path(args.proposal).resolve()), '--launch-directory', str(directory)]
        mark(directory, 'lifecycle_requested')
        lifecycle_entered = True
        try:
            result = run_forwarded(command, cwd=root, env=env, new_session=True)
        finally:
            ended = mark(directory, 'lifecycle_returned', returncode=result)
            restoration = observe_restoration(ended['unix_seconds'], proposal['restoration_observation_timeout_seconds'])
            mark(directory, 'restoration_observed', status=restoration['status'])
    except BaseException as failure:
        error = dict(type=type(failure).__name__, message=str(failure))
    finally:
        if not lifecycle_entered:
            restoration = dict(status='lifecycle_not_entered_holders_unchanged', GPU_inspection_not_repeated=True)
            mark(directory, 'preparation_failed', error=error)
        try:
            link = directory/'diagnostic_link.json'
            if link.exists():
                destination = Path(json.loads(link.read_text())['path'])
                resources = dict(status='reconciled_from_durable_journals', diagnostic_directory=str(destination))
                for filename, key, fn in (
                    ('events.jsonl', 'public_events', summarize),
                    ('initialization_events.jsonl', 'initialization', lambda rows: summarize_initialization(rows, proposal['initialization_caps']))):
                    path = destination/filename
                    resources[key] = fn([json.loads(x) for x in path.read_text().splitlines()]) if path.exists() else None
                path = destination/'graphics_events.jsonl'
                resources['graphics'] = reconcile(path) if path.exists() else None
                for filename, key in [('resource_receipt.json','diagnostic_receipt'), ('graphics_cleanup.json','graphics_cleanup')]:
                    path = destination/filename
                    resources[key] = json.loads(path.read_text()) if path.exists() else None
                resources['missing_reason'] = 'Missing journals/returns stay unresolved; entered attempts charged once, no refunds or retries'
        except (OSError, ValueError, KeyError) as failure:
            resources = dict(status='reconciliation_failed', error=str(failure), actual_counts=None)
        marks = [json.loads(x) for x in (directory/'wave_timing.jsonl').read_text().splitlines()]
        success = result == 0 and error is None and restoration['status'] == 'occupancy_resolved'
        write_new(directory/'LAUNCH_RESULT.json', dict(status='complete' if success else 'failed',
            diagnostic_returncode=result, launch_error=error, release_consumed=True, max_retries=0,
            remaining_caps_reusable=False, release_claim=str(claim), timing=timing_summary(marks),
            restoration=restoration, resources=resources, experimental_GPU_seconds=None,
            GPU_seconds_missing_reason='Wall time is separate; no device utilization integral'))
    return 0 if success else (result if result not in (None, 0) else 3)


if __name__ == '__main__':
    sys.exit(main())
