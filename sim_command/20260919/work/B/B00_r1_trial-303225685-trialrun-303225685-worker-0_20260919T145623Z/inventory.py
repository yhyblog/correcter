"""B00 read-only CPU inventory; writes only this node's campaign directories."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
BASE = ROOT / 'Corrector/sim_command/20260919'
WORK = Path(__file__).resolve().parent
WS = ROOT / 'embodied-ai-workspace'

def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def atomic(path, value):
    temp = path.with_name('.' + path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)

def beat(progress):
    path = BASE / 'receipts/B/B00_HEARTBEAT.json'
    value = json.loads(path.read_text())
    value.update(updated_at_utc=now(), progress=progress)
    atomic(path, value)

def command(argv, env=None):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=45, env=env)
        return dict(command=argv, exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
    except Exception as exc:
        return dict(command=argv, error=str(exc))

def record(path):
    path = Path(path)
    out = dict(path=str(path), exists=path.exists(), symlink=path.is_symlink(), resolved=str(path.resolve()))
    if path.is_file():
        out['bytes'] = path.stat().st_size
        with path.open('rb') as handle:
            handle.read(1)
        out['readable'] = True
        if out['bytes'] <= 2 * 1024 * 1024:
            out['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            out['sha256'] = None
            out['hash_note'] = 'Large payload not rehashed during inventory; size/readability only.'
    elif path.is_dir():
        out['entries'] = sorted(p.name for p in path.iterdir())
    return out

ENV_CODE = r'''
import importlib.metadata as m, importlib.util, json, os, platform, sys
packages = ['torch','torchvision','numpy','safetensors','transformers','lerobot','metaworld','mujoco','jax','jaxlib','flax','optax','orbax-checkpoint','tensorstore','robosuite','libero','datasets','pyarrow','accelerate','pytest']
versions={}
for name in packages:
 try: versions[name]=m.version(name)
 except m.PackageNotFoundError: versions[name]=None
specs={}
for name in ['torch','lerobot','metaworld','mujoco','jax','openpi','libero','robosuite','guided_action_flow','ogbench']:
 try:
  spec=importlib.util.find_spec(name)
  specs[name]=None if spec is None else {'origin':spec.origin,'search_locations':list(spec.submodule_search_locations or [])}
 except Exception as exc: specs[name]={'error':str(exc)}
print(json.dumps({'python':platform.python_version(),'executable':sys.executable,'base_prefix':sys.base_prefix,'prefix':sys.prefix,'versions':versions,'module_locations':specs,'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'check_type':'metadata/spec only; no model, CUDA initialization, or simulator'}))
'''

def env_check(name):
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES='', JAX_PLATFORMS='cpu', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
    runtime = WS / 'projects/vla-baselines/launchers/runtime.sh'
    result = command(['bash', str(runtime), name, 'python', '-c', ENV_CODE], env=env)
    if result.get('exit_code') == 0:
        result['details'] = json.loads(result.pop('stdout'))
    return name, result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', action='store_true')
    args = parser.parse_args()
    beat('host inventory' if args.host else 'CPU environment and physical asset inventory')
    if args.host:
        data = {'hostname': socket.gethostname(), 'observed_at_utc': now(), 'pid': os.getpid(), 'pid_note': 'Transient inventory process, not persistent executor', 'queries': []}
        for argv in [
            ['nvidia-smi','--query-gpu=index,uuid,name,memory.total,driver_version,utilization.gpu,memory.used','--format=csv,noheader,nounits'],
            ['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_memory','--format=csv,noheader'],
            [str(ROOT/'gpu_occupancy_lifecycle.sh'),'status'],
            ['findmnt','--json','--target',str(ROOT),'--output','TARGET,SOURCE,FSTYPE'],
            ['findmnt','--json','--target','/tmp','--output','TARGET,SOURCE,FSTYPE'],
            ['lscpu','--json'],
        ]:
            data['queries'].append(command(argv))
        data['memory'] = {line.split(':')[0]:line.split(':')[1].strip() for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
        data['filesystems'] = {}
        for p in [ROOT, Path('/tmp')]:
            stat = os.statvfs(p)
            data['filesystems'][str(p)] = {'total_bytes':stat.f_blocks*stat.f_frsize,'available_bytes':stat.f_bavail*stat.f_frsize,'note':'Shared FUSE capacity can be nominal; local /tmp capacity is distinct.'}
        data['local_tmp_candidates'] = [record(p) for p in Path('/tmp').iterdir() if any(x in p.name.lower() for x in ['checkpoint','vla-openpi','native10','pi05','standalone','corrector'])]
        atomic(WORK/'host_inventory.json',data)
        print(json.dumps({'artifact':str(WORK/'host_inventory.json'),'queries':[{k:v for k,v in q.items() if k!='stdout'} for q in data['queries']], 'local_tmp_candidates':data['local_tmp_candidates'], 'filesystems':data['filesystems']}))
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        environments = dict(pool.map(env_check, ['mw-pi05-legacy','mw-smolvla-lr044','mw-xvla-lr044','pi05-openpi-jax','libero-sim-openpi']))
    atomic(WORK/'environments.json', environments)
    paths = [
        WS/'models/vla-sft-030000', WS/'models/vla-corrector-h1-k10', WS/'datasets/metaworld-mt50',
        ROOT/'vla-corrector/outputs/metaworld_very_hard/latents_pi05_mt50',
        WS/'models/base/xvla-cdb7964', WS/'models/initializations/xvla-mt50-s42',
        WS/'models/initializations/smolvla-mt50-s42', WS/'models/reference/pi05-libero-official',
        WS/'artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/050000/pretrained_model',
        WS/'artifacts/vla-baselines/runs/metaworld/xvla',
        WS/'artifacts/vla-baselines/runs/libero/pi05/pi05_libero/libero-pi05-s42-ma-20260912-v1/29999',
        WS/'datasets/libero/physical-intelligence-v2/a4336d589d589045d1c56423ffdf3b88a0e19b1f',
        ROOT/'Corrector/outputs/standalone_ablation_20260918/banks',
        ROOT/'Corrector/outputs/native10_training_20260916/banks',
    ]
    assets = []
    for path in paths:
        item = record(path)
        if path.is_dir():
            item['immediate_files'] = [record(p) for p in path.iterdir() if p.is_file()]
        assets.append(item)
    atomic(WORK/'physical_paths.json',assets)
    print(json.dumps({'artifact':str(WORK/'environments.json'),'environments':{k: {'exit_code':v.get('exit_code'),'python':v.get('details',{}).get('python'),'versions':v.get('details',{}).get('versions'),'stderr':v.get('stderr')} for k,v in environments.items()},'assets':[{k:v for k,v in a.items() if k!='immediate_files'} for a in assets]},indent=2))
    beat('CPU environments checked; reviewing checkpoint payloads and data schemas')

if __name__ == '__main__':
    main()
