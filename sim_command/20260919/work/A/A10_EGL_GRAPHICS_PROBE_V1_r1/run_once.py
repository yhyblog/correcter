"""Execute the exact newly released command once; observe without changing its lifecycle."""
import datetime
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORK = Path(__file__).resolve().parent
TASK = 'A10_EGL_GRAPHICS_PROBE_V1'
RELEASE = BASE / 'releases/P10_A_EGL_GRAPHICS_PROBE_V1.json'
PUB = BASE / 'results/A/A10_EGL_CPU_REPAIR_V1'
COMMAND = ['bash', str(PUB / 'commands/run_proposed_graphics_probe.sh'), str(RELEASE)]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path, value):
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(pending, path)


with (WORK / 'EXECUTION_STARTED.json').open('x') as stream:
    stream.write(json.dumps({'task_id': TASK, 'command': COMMAND, 'started_at_utc': now(),
                             'planned_launcher_invocations': 1, 'max_retries': 0}) + '\n')
status = subprocess.run(['/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh', 'status'],
                        text=True, capture_output=True, timeout=25)
atomic(WORK / 'OCCUPANCY_BEFORE.json', {'returncode': status.returncode, 'stdout': status.stdout,
       'stderr': status.stderr, 'checked_at_utc': now()})
if status.returncode:
    raise RuntimeError('Guard status check failed; command was not launched')
start = time.monotonic()
samples, max_rss_kib, error = 0, None, None
with (WORK / 'command.log').open('x') as output:
    process = subprocess.Popen(COMMAND, cwd=PUB, stdout=output, stderr=subprocess.STDOUT,
                               start_new_session=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    atomic(WORK / 'PROCESS.json', {'pid': process.pid, 'started_at_utc': now(), 'command': COMMAND, 'launcher_invocations': 1,
           'process_start_ticks': Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]})

    def forward(sig, _):
        if process.poll() is None:
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
    prior = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    next_heartbeat = 0.
    try:
        while process.poll() is None:
            current = time.monotonic()
            sample = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.used,utilization.gpu',
                                     '--format=csv,noheader,nounits'], text=True, capture_output=True, timeout=10)
            with (WORK / 'GPU_OBSERVATIONS.jsonl').open('a') as stream:
                stream.write(json.dumps({'utc': now(), 'monotonic_seconds': time.monotonic(),
                    'query_started_monotonic_seconds': current, 'query_returncode': sample.returncode, 'stdout': sample.stdout, 'stderr': sample.stderr}) + '\n')
            samples += 1
            if current >= next_heartbeat:
                atomic(BASE / f'receipts/A/{TASK}_HEARTBEAT.json', {'task_id': TASK, 'status': 'running',
                    'updated_at_utc': now(), 'pid': process.pid, 'elapsed_wall_seconds': current - start,
                    'progress_source': str(WORK / 'command.log'), 'launcher_invocations': 1,
                    'actual_resource_counts': None, 'missing_reason': 'Use durable event journals; no inferred progress or retry'})
                next_heartbeat = current + 15
            time.sleep(.25)
        result = process.wait()
        max_rss_kib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    finally:
        for sig, handler in prior.items():
            signal.signal(sig, handler)
elapsed = time.monotonic() - start
atomic(WORK / 'COMMAND_EXIT.json', {'task_id': TASK, 'command': COMMAND, 'returncode': result,
    'finished_at_utc': now(), 'observed_command_wall_seconds': elapsed, 'launcher_invocations': 1,
    'max_retries': 0, 'child_rusage_maxrss_KiB': max_rss_kib,
    'RAM_measurement_scope': 'OS child-family ru_maxrss maximum, not sum of simultaneous process RSS or machine used RAM',
    'gpu_observation_count': samples, 'GPU_peak_scope': 'NVML samples only; partition by wave timing before reporting, not allocator-exact peak'})
atomic(BASE / f'receipts/A/{TASK}_HEARTBEAT.json', {'task_id': TASK, 'status': 'command_exited_audit_pending',
    'updated_at_utc': now(), 'returncode': result, 'launcher_invocations': 1})
print(json.dumps({'command_returncode': result, 'command_wall_seconds': elapsed,
                  'evidence': str(WORK / 'COMMAND_EXIT.json')}), flush=True)
# A nonzero scientific command remains a completed orchestration, never a retry.
