import copy
from types import SimpleNamespace
import numpy as np
import pytest
from .scene_identity import canonical_scene,exact_arrays_hash,read_initial_scene
from .protocol import canonical_hash


def scene():
    return dict(qpos=np.array([.1,.2,.3,1,0,0,0,.2,.4]),qvel=np.zeros(8),
        joint_type=np.array([0,2,3]),joint_qpos_address=np.array([0,7,8]),joint_dof_address=np.array([0,6,7]),
        target_pos=np.array([.1,.8,.2]),act=np.zeros(0),mocap_pos=np.zeros((1,3)),mocap_quat=np.array([[1,0,0,0]]),
        **{f'model_{k}_pos':np.zeros((2,3)) for k in ('body','site','geom')},
        **{f'model_{k}_quat':np.array([[1,0,0,0],[1,0,0,0]]) for k in ('body','site','geom')})


def test_identity_excludes_seed_clock_solver_and_unused_random_vector():
    a=scene();b=copy.deepcopy(a);b.update(seed=19,time=np.array([3.]),randomization_vector=np.ones(10),qacc_warmstart=np.ones(8))
    assert canonical_hash(canonical_scene(a))==canonical_hash(canonical_scene(b))
    assert exact_arrays_hash(a)!=exact_arrays_hash(b)


def test_quaternion_sign_scale_and_position_quantization():
    a=scene();b=copy.deepcopy(a);b['qpos'][3:7]*=-2;b['mocap_quat']*=-1;b['qpos'][0]+=.1e-6
    assert canonical_scene(a)==canonical_scene(b)
    b['qpos'][0]+=2e-6
    assert canonical_scene(a)!=canonical_scene(b)


@pytest.mark.parametrize('key',['target_pos','model_body_pos','model_site_pos','model_geom_pos','qvel'])
def test_actual_physical_changes_are_detected(key):
    a=scene();b=copy.deepcopy(a);b[key].flat[0]+=.01
    assert canonical_scene(a)!=canonical_scene(b)


def test_angular_and_translation_rules_are_separate():
    q=canonical_scene(scene());assert q['joints'][1]['state']['position_m']==[200000]
    assert q['joints'][2]['state']['angle_rad']==[400000]
    assert 'quaternion' in q['joints'][0]['state']


def test_uncovered_joint_and_invalid_quaternion_fail():
    x=scene();x['qpos']=x['qpos'][:-1]
    with pytest.raises(ValueError):canonical_scene(x)
    x=scene();x['qpos'][3:7]=0
    with pytest.raises(ValueError):canonical_scene(x)


def test_read_requires_before_first_action():
    with pytest.raises(ValueError,match='first policy action'):
        read_initial_scene(SimpleNamespace(backend=SimpleNamespace(_control_step_index=1)))


def test_registry_rejects_same_physical_scene_across_splits(tmp_path,monkeypatch):
    from . import scene_identity,storage
    from .protocol import episode_key
    monkeypatch.setattr(scene_identity,'ROOT',tmp_path)
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    monkeypatch.setattr(scene_identity,'LOCK',tmp_path/'lock')
    monkeypatch.setattr(scene_identity,'read_initial_scene',lambda runtime:(scene(),{'randomization_vector':[runtime]}))
    cfg={'scene_identity':{'schema':scene_identity.SCHEMA},'analysis_approval':{'protocol_sha256':'a'*64}}
    def capture(seed,split):
        case={'task':'stick-pull-v3','env_seed':seed,'episode_id':episode_key('stick-pull-v3',seed),'split':split}
        return scene_identity.capture_scene_identity(seed,case,{'number':seed},cfg,tmp_path/str(seed))
    a=capture(1,'train');b=capture(2,'heldout')
    assert a['status']=='accepted' and b['status']=='duplicate'
    assert b['duplicate_of']['episode_id']==a['episode_id']
    assert b['duplicate_of']['split']=='train'
    assert a['scene_fingerprint']==b['scene_fingerprint']
    assert (tmp_path/'1/complete.json').exists() and (tmp_path/'2/complete.json').exists()
