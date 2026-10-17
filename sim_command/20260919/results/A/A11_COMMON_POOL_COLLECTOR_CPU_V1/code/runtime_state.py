"""Actual snapshot reader, imported only inside authorized runtime.
No mj_setState, reset, render or _get_obs is used here."""
import random
import numpy as np
import torch
from full_state import snapshot
from core.contracts import ContractError
CALLBACKS=['act_dyn','act_gain','act_bias','control','passive','sensor','contactfilter','time']
def read_rng(rng,meter):
    if rng is None:return None
    if isinstance(rng,np.random.Generator):
        return meter.call('numpy_generator_state',lambda:dict(engine=type(rng.bit_generator).__name__,
            state=rng.bit_generator.state),{'numpy_rng_state_reads':1})
    if isinstance(rng,np.random.RandomState):
        return meter.call('numpy_randomstate',rng.get_state,{'numpy_rng_state_reads':1})
    raise ContractError('unknown RNG engine')
def python_attrs(obj,meter,exclude):
    """Enumerate actual instance attrs; unknown types fail serialization, no omission."""
    def descend(value):
        if isinstance(value,(np.random.Generator,np.random.RandomState)):return read_rng(value,meter)
        if type(value).__module__.startswith('gymnasium.spaces'):return python_attrs(value,meter,{})
        if type(value) is dict:return {k:descend(v) for k,v in value.items()}
        if type(value) in (list,tuple):return type(value)(descend(v) for v in value)
        return value
    result={}
    for key,value in vars(obj).items():
        if key in exclude:
            result[key]={'classification':'irrelevant','basis':exclude[key],
                'class':type(value).__module__+':'+type(value).__qualname__}
        else:result[key]=descend(value)
    return result
def capture(engine,step,raw,age):
    import mujoco
    e=engine.env._env;m=e.model;d=e.data;meter=engine.meter
    if type(e).__module__!='metaworld.envs.sawyer_shelf_place_v3' or type(e).__name__!='SawyerShelfPlaceEnvV3':
        raise ContractError('actual environment class not allowlisted')
    plugin=meter.call('plugin_fields',lambda:(int(m.nplugin),int(m.npluginstate)),{'plugin_field_reads':2})
    if plugin!=(0,0):raise ContractError('unknown native plugin state')
    callbacks={}
    for key in CALLBACKS:
        value=meter.call('callback_'+key,lambda key=key:getattr(mujoco,'get_mjcb_'+key)(),{'callback_read_calls':1})
        if value is not None:raise ContractError('callback must be absent: '+key)
        callbacks[key]=None
    sig=int(mujoco.mjtState.mjSTATE_INTEGRATION)
    count=meter.call('mj_stateSize',lambda:mujoco.mj_stateSize(m,sig),{'mj_stateSize_calls':1})
    if count<0 or count>1024*1024:raise ContractError('state buffer bound')
    state=np.empty(count,dtype=np.float64)
    meter.call('mj_getState',lambda:mujoco.mj_getState(m,d,state,sig),{'mj_getState_calls':1})
    size=meter.call('mj_sizeModel',lambda:mujoco.mj_sizeModel(m),{'mj_sizeModel_calls':1})
    if not 0<size<=32*1024**2:raise ContractError('MJB model byte bound')
    model=np.zeros(size,dtype=np.uint8)
    meter.call('mj_saveModel',lambda:mujoco.mj_saveModel(m,None,model),{'mj_saveModel_calls':1})
    model_bytes=model.tobytes();engine.store.write('cut_model.mjb',model_bytes)
    native_exclusions={
        'model':'all compiled mutable model fields captured as MJB; plugins/callbacks refused',
        'data':'mjSTATE_INTEGRATION plus task observation cache; derived physics recomputed by frozen step',
        'mujoco_renderer':'native GL handles affect no physics; frozen camera/config and actual prefix image/feature bytes verified'}
    wrapper_exclusions={'_env':'captured separately as native task/model/data',
        'expert_policy':'unused by this pi05 controller; frozen class code identity, never called'}
    rng=dict(python=meter.call('python_rng_state',random.getstate,{'python_rng_state_reads':1}),
        numpy=meter.call('numpy_global_state',np.random.get_state,{'numpy_rng_state_reads':1}),
        torch_cpu=meter.call('torch_CPU_rng',lambda:torch.get_rng_state().cpu().numpy(),{'torch_rng_state_reads':1}),
        torch_target=meter.call('torch_target_rng',lambda:torch.cuda.get_rng_state(0).cpu().numpy(),{'torch_rng_state_reads':1}))
    groups=dict(identity=dict(source=engine.source_signature,policy=engine.cfg['model_sha256'],
        task=engine.task,versions=engine.cfg['runtime_packages'],state_precision='float64',
        prefix_plan_SHAs=engine.prefix_plan_shas,prefix_noise_SHAs=engine.prefix_noise_shas,feature_signature=engine.cfg['feature_signature']),
        integration=dict(signature=sig,state=state),
        mutable_model=model_bytes,
        task_python=python_attrs(e,meter,native_exclusions),
        wrapper_python=python_attrs(engine.env,meter,wrapper_exclusions),
        rng=rng,clocks=dict(absolute_step=step,frame_skip=int(e.frame_skip),physics_time=float(d.time),
            scheduler_phase=(step*400)%30,action_scale=float(e.action_scale),target=300,H=10),
        queue_history=dict(raw50=raw,age=age,remaining=10-age,
            policy_action_queue=list(engine.policy._action_queue),
            policy_queues={str(k):list(v) for k,v in engine.policy._queues.items()},
            features=engine.history[-5:],proprio=engine.props[-5:],actions=engine.actions[-4:],
            language=engine.language,
            sampling_decisions=[dict(namespace=ns,repeat=r,next_index=i) for (ns,r),i in engine.decisions.items()],
            parameter_buffer_versions=[int(p._version) for p,_ in engine.versions]),
        callbacks_plugins=dict(callbacks=callbacks,plugins=plugin))
    return meter.call('typed_full_snapshot',lambda:snapshot(groups),{'state_serialization_calls':1})
