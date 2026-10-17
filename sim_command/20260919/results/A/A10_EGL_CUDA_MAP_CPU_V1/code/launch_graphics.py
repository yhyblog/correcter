"""One proposed graphics wave, all A holders paused until its process family exits."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from probe_contract import authorize, write_new, Refused, reconcile
from wave_timing import stamp, mark, run_forwarded, observe_restoration, timing_summary


def verify_device(proposal):
    d = proposal['device']
    r = subprocess.run(['nvidia-smi', '--id='+d['gpu_uuid'],
        '--query-gpu=index,uuid,name,driver_version,pci.bus_id', '--format=csv,noheader,nounits'],
        text=True, capture_output=True, check=True)
    rows = [line for line in r.stdout.splitlines() if line.strip()]
    if len(rows) != 1: raise Refused('Target GPU must resolve uniquely')
    fields = [x.strip() for x in rows[0].split(',')]
    index, uuid, name, driver, pci = fields
    pci = pci.lower(); pci = pci.split(':')[0][-4:]+':'+':'.join(pci.split(':')[1:])
    actual = dict(gpu_index=int(index), gpu_uuid=uuid, gpu_model=name, driver=driver, pci_bus_id=pci)
    if actual != d: raise Refused('Actual NVML GPU identity changed')
    return actual


def main():
    start = stamp()
    parser = argparse.ArgumentParser()
    for name in ('campaign','release','proposal'): parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    if Path(__file__).resolve().parent.parent != Path(args.proposal).resolve().parent.parent:
        raise Refused('Executable must belong to the proposed bundle')
    release, proposal = authorize(args.campaign, args.release, args.proposal)
    if os.environ.get('NVIDIA_VISIBLE_DEVICES') != proposal['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:
        raise Refused('Container NVIDIA visibility changed; do not rewrite mount identity')
    actual = verify_device(proposal)
    lifecycle = Path(proposal['occupancy_lifecycle'])
    subprocess.run(['/usr/bin/python', str(lifecycle.with_name('gpu_occupancy_guard.py')), 'active'], check=True)
    root = Path(args.proposal).resolve().parent.parent
    runs = Path(args.campaign).resolve()/'results/A/EGL_graphics_runs'
    claims = runs/'release_claims'; claims.mkdir(parents=True, exist_ok=True)
    write_new(claims/(release['release_id']+'.json'), dict(release_id=release['release_id'],
        release_sha256=release['_sha256'], run_id=release['run_id'], claimed_at=start, max_retries=0))
    out = runs/release['run_id']; out.mkdir(exist_ok=False)
    write_new(out/'launch_identity.json', dict(release=release, actual_gpu=actual, proposal_sha256=proposal['_sha256']))
    with (out/'wave_timing.jsonl').open('x') as f:
        f.write(json.dumps(dict(phase='launcher_started', **start))+'\n'); f.flush(); os.fsync(f.fileno())
    env = dict(os.environ)
    for key in ('LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID'): env.pop(key, None)
    env.update(MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl',
        PYTHONDONTWRITEBYTECODE='1', **proposal['cuda_environment'],
        __EGL_VENDOR_LIBRARY_FILENAMES=str(root/'isolation/vendor/10_nvidia.json'),
        LD_LIBRARY_PATH=':'.join([str(root/'isolation/lib'), proposal['python_library_directory'],
                                 '/usr/lib/x86_64-linux-gnu','/lib/x86_64-linux-gnu']),
        XDG_CACHE_HOME=str(out/'runtime_cache'), __GL_SHADER_DISK_CACHE='0', OMP_NUM_THREADS='1',
        OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    command = [str(lifecycle), 'run', '--', sys.executable, '-B', str(root/'code/run_reserved_graphics.py'),
        '--campaign',str(Path(args.campaign).resolve()),'--release',str(Path(args.release).resolve()),
        '--proposal',str(Path(args.proposal).resolve()),'--launch-directory',str(out)]
    rc = None; error = None
    mark(out, 'lifecycle_requested')
    try:
        rc = run_forwarded(command, cwd=root, env=env, new_session=True)
    except BaseException as e:
        error = dict(error_type=type(e).__name__, error=str(e))
    finally:
        ended = mark(out, 'lifecycle_returned', returncode=rc, error=error)
        restoration = observe_restoration(ended['unix_seconds'], 120)
        mark(out, 'restoration_observed', status=restoration['status'])
        events = out/'graphics/events.jsonl'
        resources = reconcile(events) if events.is_file() else None
        marks = [json.loads(line) for line in (out/'wave_timing.jsonl').read_text().splitlines()]
        write_new(out/'LAUNCH_RESULT.json', dict(status='complete' if rc==0 and restoration['status']=='occupancy_resolved' else 'failed',
            returncode=rc, launch_error=error, timing=timing_summary(marks), restoration=restoration,
            resources=resources, missing_counts_reason=None if resources else 'No graphics journal; outcome not invented',
            gpu_seconds=None, max_retries=0))
    return rc if rc not in (None,0) else (0 if error is None and restoration['status']=='occupancy_resolved' else 3)


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps(dict(status='denied', error_type=type(e).__name__, error=str(e)))); sys.exit(2)
