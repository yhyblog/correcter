"""Exercise the real scheduler with fake subprocesses and isolated CPU files."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import batch
import d24_common as d

real = d.load(d.W / 'BATCH.json')
assert real['run_id'] and len(real['jobs']) == real['max_workers'] == 8
checks = []
for job in real['jobs']:
    cfg = d.load(job['config'])
    assert Path(job['output']).is_relative_to(d.R)
    assert Path(job['argv'][1]).is_relative_to(d.W)
    assert job['argv'][-1] == job['config']
    for filename in ('libero_job.py', 'libero_server.py', 'libero_eval.py', 'train_full.py'):
        keys = set()
        for node in ast.walk(ast.parse((d.W / filename).read_text())):
            if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                    and node.value.id == 'cfg' and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)):
                keys.add(node.slice.value)
        assert not keys - cfg.keys(), (filename, keys - cfg.keys())
    assert cfg['H'] == 10 and cfg['K'] == 5 and cfg['NFE'] == 10
    checks.append(dict(job=job['job_id'], config_literal_fields_present=True))

target = d.R / 'cpu_launch_fixture'
assert not target.exists()
target.mkdir()
fake_cfg = json.loads(json.dumps(real))
for i, job in enumerate(fake_cfg['jobs']):
    job['output'] = str(target / 'workers' / str(i))
d.atomic(target / 'batch.json', fake_cfg)
d.atomic(target / 'HOLDER_HANDOFF_REQUEST.json', dict(utc=d.utc(), owned_processes=[]))
spawned = []

def fake_popen(argv, **kwargs):
    job = fake_cfg['jobs'][len(spawned)]
    assert tuple(kwargs['pass_fds']) == (991,)
    assert (target / 'HOLDER_EXIT_ACK.json').exists()
    spawned.append(list(argv))
    d.atomic(Path(job['output']) / 'status.json', dict(status='complete', synthetic=True))
    return SimpleNamespace(pid=9000000 + len(spawned), poll=lambda: 0)

with patch.object(d, 'R', target), patch.object(d, 'authorize', lambda **kw: None), \
        patch.object(d, 'identity', lambda pid=None: dict(pid=pid or 9999999, synthetic=True)), \
        patch.object(batch, 'reservation_fds', lambda: (991,)), \
        patch.object(batch, 'group_members', lambda pid: []), \
        patch.object(batch.signal, 'signal', lambda *args: None), \
        patch.object(batch.time, 'sleep', lambda *args: None), \
        patch.object(batch.subprocess, 'Popen', fake_popen), \
        patch.object(batch.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='synthetic', returncode=0)):
    rc = batch.run(target / 'batch.json')
assert rc == 0 and len(spawned) == 8
result = dict(utc=d.utc(), synthetic=True, real_scheduler=True, fake_subprocesses=8,
              complete=8, config_checks=checks, hardware_calls=0, model_calls=0,
              environment_calls=0, actual_scientific_claims=0,
              fixture=str(target), status='PASS')
d.atomic(d.R / 'LAUNCH_METADATA_CPU_CHECK.json', result)
print(json.dumps(result, indent=2))
