"""Read-only host/GPU status snapshot. Does not load models or instantiate environments."""
from audit_support import *
import shutil
import subprocess

progress('Snapshotting local host, GPU ownership and shared mount')
commands = {
    'gpu_inventory': ['nvidia-smi', '--query-gpu=index,name,uuid,driver_version,memory.total,memory.used,utilization.gpu', '--format=csv,noheader'],
    'compute_processes': ['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory', '--format=csv,noheader'],
    'mount': ['findmnt', '-T', str(ROOT), '-J', '-o', 'TARGET,SOURCE,FSTYPE,OPTIONS'],
}
result = {'hostname': platform.node(), 'kernel': platform.release(),
          'os_release': Path('/etc/os-release').read_text(),
          'cpu_logical_host': os.cpu_count(),
          'cpu_affinity': len(os.sched_getaffinity(0)),
          'tmp_disk': dict(zip(('total', 'used', 'free'), shutil.disk_usage('/tmp'))),
          'commands': {}, 'project_compute_processes': []}
for name, command in commands.items():
    run = subprocess.run(command, text=True, capture_output=True, timeout=15)
    result['commands'][name] = {'command': command, 'returncode': run.returncode,
                                'stdout': run.stdout, 'stderr': run.stderr}
for path in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        argv = [x.decode(errors='replace') for x in path.read_bytes().split(b'\0') if x]
        if not argv or not any(tag in Path(argv[0]).name for tag in ('python', 'torchrun', 'accelerate')):
            continue
        # Match actual module/script arguments, excluding source text supplied via -c.
        args = argv[1:argv.index('-c')] if '-c' in argv else argv[1:]
        relevant = [x for x in args if any(tag in x for tag in
                    ('Corrector/', 'ac_tmil', 'future_aware', 'experiments.',
                     'eval_metaworld', 'train_metaworld', 'serve_pi05', 'eval_libero'))]
        if relevant:
            result['project_compute_processes'].append({'pid': int(path.parent.name),
                                                        'program': argv[0],
                                                        'relevant_arguments': relevant})
    except (OSError, ValueError):
        continue
guard = Path('/tmp/gpu_occupancy_guard/status.json')
result['guard_status'] = json.loads(guard.read_text()) if guard.exists() else None
result['guard_state_source'] = str(guard)
save('node_probe.json', result)
print(json.dumps(result, ensure_ascii=False, indent=2))
