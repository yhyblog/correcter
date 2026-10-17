"""Queue-aware entry authorization; importing this module is stdlib CPU only.

No legacy CONTROL/release and no lifecycle nesting. Analysis must publish one
finite stage and register its path/SHA in current queue CONTROL.stage_authorizations.
Current V2 contains no such stage, so every model/optimizer entry is denied.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import time

C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
Q = C/'persistent_queue'
HOST = 'trial-303225685-trialrun-303225685-worker-0'
PREP = C/'work/B/B_INDEPENDENT_PIPELINE_PREP_V1_r1'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(value,message):
    if not value:raise PermissionError(message)


def registered_stage(path, *, control=None, hostname=None):
    path=Path(path).resolve()
    require(path.is_relative_to((Q/'stages').resolve()),'stage must be under analysis-owned persistent_queue/stages')
    control=load(Q/'CONTROL.json') if control is None else control
    hostname=socket.gethostname() if hostname is None else hostname
    require(hostname==HOST,'B host identity mismatch')
    require(not control.get('global_stop') and control['nodes']['B']['enabled'],'B admission stopped')
    refs=control.get('stage_authorizations',[])
    if isinstance(refs,dict):refs=list(refs.values())
    matches=[r for r in refs if str((C/Path(r['path'])).resolve())==str(path)]
    require(len(matches)==1,'no once-frozen B stage registered in current queue authority')
    require(path.is_file() and sha(path)==matches[0]['sha256'],'stage missing or SHA changed')
    stage=load(path)
    require(stage.get('owner')=='B' and stage.get('hostname')==HOST and stage.get('authorized') is True,'stage owner/authorization mismatch')
    require(stage.get('kind') in ('frozen_training_stage','frozen_evaluation_stage'),'not a scientific stage authorization')
    require(stage.get('basis_authorization_sha256')==control['authorization']['sha256'],'stage/current authority mismatch')
    auth_path=C/control['authorization']['path']
    require(sha(auth_path)==control['authorization']['sha256'],'current authorization SHA')
    overrides={r['path']:r['sha256'] for r in control.get('operational_overrides',[])}
    require(stage.get('operational_overrides_sha256',{})==overrides,'stage operational overrides differ from current CONTROL')
    for name,digest in overrides.items():
        require(sha(C/name)==digest,'operational override SHA changed')
        item=load(C/name);contract=item['contract']
        require(sha(C/contract['path'])==contract['sha256'],'operational override contract SHA changed')
    require(stage.get('automatic_retry') is False,'unexpected automatic retries')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',stage.get('stage_id','')),'invalid stage identifier')
    stage['_verified_path']=str(path);stage['_verified_sha256']=matches[0]['sha256']
    return stage


def authorize(config_path, stage_path):
    stage=registered_stage(stage_path)
    config=load(config_path);job=stage['jobs'].get(config['job_id'])
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',config['job_id']),'invalid job identifier')
    require(job is not None and job['config_sha256']==sha(config_path),'job/config not frozen')
    require(config['kind'] in ('e1_fit','gaf_fit'),'only implemented fit workers are admitted')
    require(job['limits']==config['limits'],'finite operation caps differ')
    require(all(type(v) is int and v>=0 for v in config['limits'].values()),'unbounded operation count')
    require(0<config['updates']<=config['limits']['optimizer_attempts'],'optimizer cap')
    require(config['retry_cap']==0 and config['timeout_seconds']>0,'finite timeout/retry scope')
    require(sha(PREP/'CODE_SNAPSHOT.json')==stage['code_manifest_sha256'],'worker snapshot identity')
    for entry in load(PREP/'CODE_SNAPSHOT.json')['files']:
        require(sha(entry['path'])==entry['sha256'],'worker/dependency bytes changed')
    # A stage can bind an as-yet absent immutable data view, but cannot silently
    # replace an input that was already fixed in the proposed job.
    for key, binding in job.get('input_bindings',{}).items():
        require(key in config['inputs'],'unknown input binding')
        require(config['inputs'][key] is None or config['inputs'][key]==binding,'fixed input replaced')
        config['inputs'][key]=binding
    for key, value in config['inputs'].items():
        require(value and value.get('path') and value.get('sha256'),'blocked_input: '+key)
        require(Path(value['path']).is_file() and sha(value['path'])==value['sha256'],'input identity: '+key)
    if config['kind']=='gaf_fit':
        require(stage.get('same_final_common_pool_sha_as_A')==config['inputs']['common_data_manifest']['sha256'],
                'E3 must bind A final common train pool, not 16-parent development snapshot')
        require(stage.get('local_GPU_admission_verified') is True,'queue must verify B-local GPU/environment admission')
    # CPU model fitting is also a formal experiment; metadata preparation is
    # the only holder-exempt work in this proposal.
    fds=[]
    for p in Path('/proc/self/fd').iterdir():
        try:
            if p.readlink()==Path('/tmp/gpu_occupancy_guard/formal.lock'):fds.append(int(p.name))
        except OSError:pass
    require(len(fds)==1,'formal fit must inherit exactly one queue reservation; it never acquires a second one')
    stage['task_id']=stage.get('task_id','B13' if config['kind']=='e1_fit' else 'B12')
    stage['release_id']=stage['stage_id']
    return config,stage


def boundary(release):
    stage=registered_stage(release['_verified_path'])
    require(stage['_verified_sha256']==release['_verified_sha256'],'stage changed during execution')


def claim(config,release,output):
    output=Path(output).resolve();require(output.is_relative_to(C/'results/B'),'B output only')
    directory=C/'results/B/stage_compute_claims';directory.mkdir(exist_ok=True)
    claim_path=directory/(release['stage_id']+'__'+config['job_id']+'.json')
    # Exclusive persistent entry. Lease expiry and a new output directory do
    # not authorize repeating an already consumed optimizer command.
    with claim_path.open('x') as f:
        json.dump(dict(hostname=HOST,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                       pid=os.getpid(),at_unix=time.time(),output=str(output),stage_sha256=release['_verified_sha256']),f)
        f.flush();os.fsync(f.fileno())
    output.mkdir(parents=True,exist_ok=False)


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--stage',required=True);p.add_argument('--output',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:
        cfg=load(a.config)
        print(json.dumps(dict(job_id=cfg['job_id'],execution_authorized=False,
              missing_inputs=[k for k,v in cfg['inputs'].items() if v is None],limits_proposal=cfg['limits'])))
        return
    config,stage=authorize(a.config,a.stage)
    claim(config,stage,a.output)
    from fit_worker import execute
    execute(config,stage,a.output)


if __name__=='__main__':main()
