"""Check release first, then hold one complete A-only formal wave in the lifecycle wrapper."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
from core.release import load_authorization, verify_device
from core.initialization import summarize_initialization
from core.accounting import summarize
from core.wave_timing import stamp, mark, write_new, run_forwarded, observe_restoration, timing_summary
import json


def main():
    launch_start = stamp()
    p = argparse.ArgumentParser()
    p.add_argument('--campaign', required=True)
    p.add_argument('--release', required=True)
    p.add_argument('--proposal', required=True)
    args = p.parse_args()
    control, release, proposal = load_authorization(args.campaign, args.release, args.proposal)
    verify_device(release)
    root = Path(__file__).resolve().parent
    guard = Path(proposal['occupancy_lifecycle']).with_name('gpu_occupancy_guard.py')
    subprocess.run(['/usr/bin/python', str(guard), 'active'], check=True)
    directory = Path(args.campaign).resolve() / 'results/A/P10_launcher_runs' / release['run_id']
    directory.mkdir(parents=True, exist_ok=False)  # no second physical attempt
    write_new(directory / 'launch_identity.json', {'release': release, 'proposal_sha256': proposal['_sha256'],
              'automatic_retry': False, 'started_at': launch_start})
    with (directory / 'wave_timing.jsonl').open('x') as stream:
        stream.write(json.dumps({'phase': 'launcher_started', **launch_start}) + '\n')
        stream.flush(); os.fsync(stream.fileno())
    cache = Path(args.campaign).resolve() / 'work/A/P10_runtime_cache' / release['run_id']
    cache.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               HF_HOME=proposal['hf_home'], MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl',
               CUDA_VISIBLE_DEVICES=release['gpu_uuid'], OMP_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false',
               XDG_CACHE_HOME=str(cache / 'xdg'), CUDA_CACHE_PATH=str(cache / 'cuda'), TORCH_HOME=str(cache / 'torch'))
    command = [proposal['occupancy_lifecycle'], 'run', '--', sys.executable, '-B', str(root / 'run_reserved_diagnostic.py'),
        '--campaign', str(Path(args.campaign).resolve()), '--release', str(Path(args.release).resolve()),
        '--proposal', str(Path(args.proposal).resolve()), '--launch-directory', str(directory)]
    result, error, restoration = None, None, None
    mark(directory, 'lifecycle_requested')
    try:
        result = run_forwarded(command, cwd=root, env=env, new_session=True)
    except BaseException as failure:
        error = {'type': type(failure).__name__, 'message': str(failure)}
    finally:
        ended = mark(directory, 'lifecycle_returned', returncode=result, error=error)
        restoration = observe_restoration(ended['unix_seconds'], proposal['restoration_observation_timeout_seconds'])
        mark(directory, 'restoration_observed', status=restoration['status'])
        resources = {'status': 'no_reconciled_diagnostic_artifact', 'actual_counts': None,
                     'missing_reason': 'See diagnostic link and durable journals; no result is fabricated after a crash'}
        link = directory / 'diagnostic_link.json'
        try:
            if link.exists():
                destination = Path(json.loads(link.read_text())['path'])
                resources = {'status': 'reconciled_from_durable_journals', 'diagnostic_directory': str(destination)}
                for filename, key, summarize_fn in (
                        ('events.jsonl', 'public_events', summarize),
                        ('initialization_events.jsonl', 'initialization',
                         lambda rows: summarize_initialization(rows, proposal['initialization_caps']))):
                    path = destination / filename
                    resources[key] = (summarize_fn([json.loads(line) for line in path.read_text().splitlines()])
                                      if path.exists() else None)
                resources['missing_reason'] = 'Missing journals/terminal events remain unknown; entered charges retained, no automatic retry'
        except (OSError, ValueError, KeyError) as failure:
            resources = {'status': 'reconciliation_failed', 'actual_counts': None, 'error': str(failure)}
        marks = [json.loads(line) for line in (directory / 'wave_timing.jsonl').read_text().splitlines()]
        write_new(directory / 'LAUNCH_RESULT.json', {
            'status': 'complete' if result == 0 and restoration['status'] == 'occupancy_resolved' else 'failed',
            'diagnostic_returncode': result, 'launch_error': error, 'max_retries': 0,
            'timing': timing_summary(marks), 'restoration': restoration, 'resources': resources,
            'experimental_GPU_seconds': None,
            'GPU_seconds_missing_reason': 'Process wall time is measured separately; it is not device utilization integral'})
    raise SystemExit(result if result not in (None, 0) else (0 if error is None and restoration['status'] == 'occupancy_resolved' else 3))


if __name__ == '__main__':
    main()
