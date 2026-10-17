"""Check release first, then hold one complete A-only formal wave in the lifecycle wrapper."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
from core.release import load_authorization


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--campaign', required=True)
    p.add_argument('--release', required=True)
    p.add_argument('--proposal', required=True)
    args = p.parse_args()
    control, release, proposal = load_authorization(args.campaign, args.release, args.proposal)
    root = Path(__file__).resolve().parent
    cache = Path(args.campaign).resolve() / 'work/A/P10_runtime_cache' / release['run_id']
    cache.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               HF_HOME=proposal['hf_home'], MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl',
               CUDA_VISIBLE_DEVICES=release['gpu_uuid'], OMP_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false',
               XDG_CACHE_HOME=str(cache / 'xdg'), CUDA_CACHE_PATH=str(cache / 'cuda'), TORCH_HOME=str(cache / 'torch'))
    command = [proposal['occupancy_lifecycle'], 'run', '--', 'timeout', '--signal=TERM', '--kill-after=30s',
        str(proposal['timeout_seconds']) + 's', proposal['python'], '-B', str(root / 'preflight_pi05.py'),
        '--campaign', str(Path(args.campaign).resolve()), '--release', str(Path(args.release).resolve()),
        '--proposal', str(Path(args.proposal).resolve())]
    result = subprocess.run(command, cwd=root, env=env, check=False)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
