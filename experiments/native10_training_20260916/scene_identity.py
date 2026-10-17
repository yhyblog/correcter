"""Pre-action physical scene identity; never supplies extra critic inputs.

Quantized scene identity excludes episode/seed/RNG/time/counters. An independent
exact array digest retains the complete initial simulation state for audit.
No environment creation/reset happens in this module.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
from pathlib import Path
import numpy as np
from .protocol import canonical_hash, episode_key
from .storage import ROOT, arrays, dump, seal, sha256

SCHEMA='metaworld_physical_initial_scene_v1'
PRECISION={'position_m':1e-6,'angle_rad':1e-6,'linear_velocity_m_per_s':1e-6,
           'angular_velocity_rad_per_s':1e-6,'unit_quaternion':1e-8,'activation':1e-8}
LOCK=Path('/tmp/corrector_native10_scene_registry.lock')


def exact_arrays_hash(values):
    h=hashlib.sha256()
    for key in sorted(values):
        v=np.ascontiguousarray(values[key])
        h.update(json.dumps([key,str(v.dtype),list(v.shape)],separators=(',',':')).encode())
        h.update(v.tobytes())
    return h.hexdigest()


def _quantize(value,precision):
    x=np.asarray(value,dtype=np.float64)
    if not np.isfinite(x).all():raise ValueError('Nonfinite scene state')
    if x.size and np.max(np.abs(x/precision))>9e18:raise ValueError('Scene quantization overflow')
    return np.rint(x/precision).astype(np.int64).tolist()


def _quaternion(values):
    values=np.asarray(values,dtype=np.float64)
    if values.size==0:return values.reshape(-1,4)
    if values.shape[-1]!=4:raise ValueError('Quaternion width must be four')
    q=values.reshape(-1,4).copy()
    norm=np.linalg.norm(q,axis=1)
    if not np.isfinite(norm).all() or np.any(norm<1e-12):raise ValueError('Invalid unit quaternion')
    q/=norm[:,None]
    # q and -q describe the same rotation. Canonical sign ignores numerical zero.
    for row in q:
        nonzero=np.flatnonzero(np.abs(row)>1e-12)
        if row[nonzero[0]]<0:row*=-1
    return q.reshape(values.shape)


def canonical_scene(raw):
    """MuJoCo free/ball/slide/hinge coordinates receive explicit unit rules."""
    qpos=np.asarray(raw['qpos'],dtype=float);qvel=np.asarray(raw['qvel'],dtype=float)
    types=np.asarray(raw['joint_type'],dtype=int)
    qadr=np.asarray(raw['joint_qpos_address'],dtype=int);vadr=np.asarray(raw['joint_dof_address'],dtype=int)
    if not (len(types)==len(qadr)==len(vadr)):raise ValueError('Invalid joint metadata')
    joints=[];covered_q=[];covered_v=[]
    for t,qa,va in zip(types,qadr,vadr):
        if t==0:
            widths=(7,6)
            state={'position_m':_quantize(qpos[qa:qa+3],1e-6),
                   'quaternion':_quantize(_quaternion(qpos[qa+3:qa+7]),1e-8),
                   'linear_velocity':_quantize(qvel[va:va+3],1e-6),
                   'angular_velocity':_quantize(qvel[va+3:va+6],1e-6)}
        elif t==1:
            widths=(4,3)
            state={'quaternion':_quantize(_quaternion(qpos[qa:qa+4]),1e-8),
                   'angular_velocity':_quantize(qvel[va:va+3],1e-6)}
        elif t in (2,3):
            widths=(1,1)
            unit='position_m' if t==2 else 'angle_rad'
            # Keep hinge winding: joint limits may distinguish a full turn.
            state={unit:_quantize(qpos[qa:qa+1],1e-6),'velocity':_quantize(qvel[va:va+1],1e-6)}
        else:raise ValueError('Unsupported MuJoCo joint type')
        covered_q.extend(range(qa,qa+widths[0]));covered_v.extend(range(va,va+widths[1]))
        joints.append({'type':int(t),'state':state})
    if sorted(covered_q)!=list(range(len(qpos))) or sorted(covered_v)!=list(range(len(qvel))):
        raise ValueError('Joint units do not cover qpos/qvel exactly once')
    result={'schema':SCHEMA,'precision':PRECISION,'joints':joints}
    for key in ('target_pos','mocap_pos','model_body_pos','model_site_pos','model_geom_pos'):
        result[key]=_quantize(raw[key],1e-6)
    for key in ('mocap_quat','model_body_quat','model_site_quat','model_geom_quat'):
        result[key]=_quantize(_quaternion(raw[key]),1e-8)
    result['act']=_quantize(raw['act'],1e-8)
    return result


def read_initial_scene(runtime):
    backend=runtime.backend
    if backend._control_step_index!=0:raise ValueError('Scene identity must precede first policy action')
    env=backend._env._env;data=env.data;model=env.model
    raw={name:np.asarray(getattr(data,name)).copy() for name in
         ('qpos','qvel','act','ctrl','qacc_warmstart','mocap_pos','mocap_quat','userdata')}
    raw['time']=np.asarray([data.time],dtype=np.float64)
    raw['target_pos']=np.asarray(env._target_pos,dtype=np.float64).copy()
    if raw['target_pos'].shape!=(3,):raise ValueError('Expected physical target position')
    for group in ('body','site','geom'):
        for attr in ('pos','quat'):
            raw[f'model_{group}_{attr}']=np.asarray(getattr(model,f'{group}_{attr}')).copy()
    for dst,src in (('joint_type','jnt_type'),('joint_qpos_address','jnt_qposadr'),('joint_dof_address','jnt_dofadr')):
        raw[dst]=np.asarray(getattr(model,src)).copy()
    # Full exact identity keeps replay state; scene identity deliberately does
    # not count solver history, clocks, IDs, or unused randomization vectors.
    raw['runtime_physics_state']=np.asarray(runtime.physics_state()).copy()
    random_vector=getattr(env,'_last_rand_vec',None)
    diagnostics={'randomization_vector':None if random_vector is None else np.asarray(random_vector).tolist(),
        'randomization_vector_used_in_scene_hash':False,'native_path_length':int(env.curr_path_length),
        'control_steps':int(backend._control_step_index)}
    return raw,diagnostics


def capture_scene_identity(runtime,case,attempt,config,destination):
    identity=episode_key(case['task'],case['env_seed'])
    if identity!=case['episode_id']:raise ValueError('Invalid scene episode identity')
    if config.get('scene_identity',{}).get('schema')!=SCHEMA:
        raise ValueError('Scene schema must be preregistered in main configuration')
    raw,diagnostics=read_initial_scene(runtime)
    canonical=canonical_scene(raw);fingerprint=canonical_hash(canonical)
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    arrays(destination/'state.npz',**raw)
    exact=exact_arrays_hash(raw)
    base=dict(schema=SCHEMA,precision=PRECISION,episode_id=identity,task=case['task'],
        env_seed=case['env_seed'],split=case['split'],round=case.get('round'),
        replacement_of=case.get('replacement_of'),budget_attempt=attempt['number'],
        protocol_sha256=config['analysis_approval']['protocol_sha256'],
        scene_fingerprint=fingerprint,exact_state_sha256=exact,
        state_file_sha256=sha256(destination/'state.npz'),scene_fields=canonical,
        before_first_policy_action=True,privileged_critic_input=False,**diagnostics)
    registry=ROOT/'scene_registry/entries.jsonl';registry.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        entries=[json.loads(line) for line in registry.read_text().splitlines()] if registry.exists() else []
        if any(row['episode_id']==identity for row in entries):
            raise ValueError('An episode scene was already registered; preserve previous attempt and use explicit retry version')
        duplicate=next((row for row in entries if row['task']==case['task'] and
                        row['scene_fingerprint']==fingerprint and row['status']=='accepted'),None)
        base.update(status='duplicate' if duplicate else 'accepted',
            duplicate_of=None if duplicate is None else {key:duplicate[key] for key in
                ('episode_id','split','task','budget_attempt','scene_fingerprint')})
        dump(destination/'identity.json',base)
        seal(destination,protocol_sha256=base['protocol_sha256'])
        entry={key:base[key] for key in ('episode_id','task','split','scene_fingerprint','exact_state_sha256',
            'status','duplicate_of','budget_attempt','protocol_sha256','replacement_of')}
        entry.update(path=str(destination),seal_sha256=sha256(destination/'complete.json'))
        import os
        with registry.open('a') as stream:
            stream.write(json.dumps(entry,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
    return base
