"""Future separately released CPU install/rollback only; never invokes guard.

This file is prepared, not executed, by A10_PV_HANDOFF_CPU_REPAIR_V1.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import stat

PACKAGE=Path(__file__).resolve().parents[1]
CAMPAIGN=PACKAGE.parents[2]
TARGET=Path('/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py')

def digest(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def put(path,value):
    with path.open('x') as f:
        f.write(json.dumps(value,indent=2)+'\n');f.flush();os.fsync(f.fileno())

def validate(release,control,identity,operation,release_path,host):
    before='original' if operation=='install' else 'patched'
    after='patched' if operation=='install' else 'original'
    fixed=dict(status='released',issuer='analysis',kind='single_guard_file_transition_CPU_only',
        campaign_id='corrector-sim-20260919',owner_host=host,operation=operation,
        target_path=str(TARGET),expected_before_sha256=identity[before]['sha256'],
        expected_after_sha256=identity[after]['sha256'],shared_file_replacements=1,
        daemon_restarts=0,holder_queries_stops=0,GPU_model_or_hardware_calls=0,
        automatic_compute=False,automatic_rollback=False)
    if any(release.get(k)!=v for k,v in fixed.items()):raise ValueError('Exact independent file-transition release required')
    if host!='trial-303224955-trialrun-303224955-worker-0':raise ValueError('Wrong installation host')
    rid=release.get('release_id')
    if (not isinstance(rid,str) or not rid or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in rid)
            or release_path!=CAMPAIGN/'releases'/(rid+'.json')):raise ValueError('Invalid canonical independent release identity')
    if (control.get('mode')!='prepare' or control.get('formal_gpu_runs_enabled') is not False
            or control.get('active_compute_task_ids')!=[] or control.get('active_compute_release_id') is not None
            or control.get('stop_requested') is not False
            or not control.get('current_compute_limits') or any(control['current_compute_limits'].values())
            or control.get('active_guard_installation_release')!=str(release_path.relative_to(CAMPAIGN))):
        raise ValueError('Separate CPU installation window must be published in CONTROL')
    return before,after

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',required=True)
    parser.add_argument('--operation',choices=['install','rollback'],required=True)
    args=parser.parse_args()
    rp=Path(args.release).resolve()
    identity=read(PACKAGE/'guard_patch/PATCH_IDENTITY.json')
    release=read(rp);control=read(CAMPAIGN/'CONTROL.json')
    before,after=validate(release,control,identity,args.operation,rp,platform.node())
    if rp.with_name(release['release_id']+'_CLOSED.json').exists():raise ValueError('Installation release is closed')
    if TARGET.is_symlink() or not TARGET.is_file():raise ValueError('Shared target must be the existing regular file')
    meta=TARGET.stat();original=TARGET.read_bytes()
    replacement=Path(identity[after]['path']).read_bytes()
    if digest(original)!=identity[before]['sha256'] or digest(replacement)!=identity[after]['sha256']:
        raise ValueError('Exact before/after bytes required; do not overwrite drift')
    stage=CAMPAIGN/'work/A/guard_file_transitions'/release['release_id']
    stage.mkdir(parents=True,exist_ok=False)
    if stage.stat().st_dev!=TARGET.parent.stat().st_dev:raise ValueError('Same-filesystem atomic replacement required')
    put(stage/'STARTED.json',dict(release_path=str(rp),release_sha256=digest(rp.read_bytes()),operation=args.operation,
        target=str(TARGET),before_sha256=digest(original),after_sha256=digest(replacement),retries=0))
    with (stage/'before_bytes.py').open('xb') as f:f.write(original);f.flush();os.fsync(f.fileno())
    staged=stage/'replacement.py'
    with staged.open('xb') as f:
        f.write(replacement);os.fchmod(f.fileno(),stat.S_IMODE(meta.st_mode))
        os.fchown(f.fileno(),meta.st_uid,meta.st_gid);f.flush();os.fsync(f.fileno())
    if TARGET.stat().st_ino!=meta.st_ino or digest(TARGET.read_bytes())!=identity[before]['sha256']:
        raise ValueError('Target changed during preparation; no replacement performed')
    os.replace(staged,TARGET)
    actual=digest(TARGET.read_bytes())
    put(stage/'RESULT.json',dict(status='installed' if actual==identity[after]['sha256'] else 'verification_failed',operation=args.operation,
        target=str(TARGET),actual_sha256=actual,expected_sha256=identity[after]['sha256'],shared_file_replacements=1,
        daemon_restarts=0,holder_operations=0,GPU_calls=0,automatic_compute=False,automatic_rollback=False))
    if actual!=identity[after]['sha256']:raise ValueError('Installed bytes failed verification; stop for analysis')

if __name__=='__main__':main()
