"""Future released one-snapshot PV diagnostic. Importing this file is CPU only."""
import argparse
import hashlib
import importlib.abc
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time

from core.contracts import CAMPAIGN, PACKAGE, RELEASE, ContractError, Meter, gate, load_authorization, read, reconcile, sha, write_new
from core.identity import check_policy_uuid, verify_device
from core.wave_timing import held_reservation_fds

class NoEnvironment(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'mujoco','metaworld','OpenGL','pynvml'} or fullname=='lerobot.envs.metaworld':
            raise ImportError('Offline PV forbids environment/graphics imports: '+fullname)

class CountedCallable:
    def __init__(self,fn,meter,name,units):self.fn,self.meter,self.name,self.units=fn,meter,name,units
    def __call__(self,*a,**kw):return self.meter.call(self.name,lambda:self.fn(*a,**kw),self.units)
    def __getattr__(self,k):return getattr(self.fn,k)

def run(cfg,out,meter):
    # No driver or tensor library is imported before authorization, complete
    # SHA verification, exclusive claim, and inherited all-holder reservation.
    sys.meta_path.insert(0,NoEnvironment())
    sys.path.insert(0,str(PACKAGE/'code/vendor_vla/src'))
    import numpy as np
    import torch
    for name,expected in cfg['runtime_packages'].items():
        if version(name)!=expected:raise ContractError('Runtime package changed: '+name)
    if torch.version.git_version!='e2d141dbde55c2a4370fac5165b0561b6af4798b':raise ContractError('Torch source commit changed')
    if dict((k,os.environ.get(k)) for k in cfg['cuda_environment'])!=cfg['cuda_environment']:
        raise ContractError('CUDA visibility/order differs from frozen V3')
    device='cuda:0'
    meter.call('select_fixed_policy_device',lambda:torch.cuda.set_device(0),{'policy_device_selections':1})
    props=meter.call('policy_device_properties',lambda:torch.cuda.get_device_properties(0),{'policy_device_property_queries':1})
    identity=check_policy_uuid(props.uuid,cfg['device']['gpu_uuid'],getattr(torch._C,'_CUuuid',None),
        before_conversion=lambda e:write_new(out/'policy_device_type.json',e))
    write_new(out/'policy_device.json',dict(identity,device=device,name=props.name,total_memory=props.total_memory,
        torch_version=torch.__version__,torch_cuda=torch.version.cuda,torch_git_version=torch.version.git_version,
        torch_file=torch.__file__,cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES']))
    if not identity['accepted'] or props.name!=cfg['device']['gpu_model']:raise ContractError('Physical policy device mismatch')
    from lerobot.configs.policies import PreTrainedConfig
    from lerobot.policies.pi05.modeling_pi05 import PI05Policy
    from lerobot.policies.pi05 import processor_pi05  # register saved PI05 preprocessing step only
    from lerobot.processor import PolicyProcessorPipeline
    from lerobot.processor.converters import batch_to_transition, transition_to_batch, policy_action_to_transition, transition_to_policy_action
    from transformers import AutoTokenizer
    from feature_path import OfflineFeatures, preprocess_observation, canonical_decode, spatial_tokens, cpu_batch
    from corrector.critic import FrozenSelector
    from corrector.guidance import FrozenObjective, FlowHook, post_direction
    from corrector.actions import ActionTransform
    from corrector.solo import array_sha
    from corrector import solo, critic as critic_module
    solo.project_solo=CountedCallable(solo.project_solo,meter,'own_direction_projection',{'own_projection_calls':1})
    project_solo=solo.project_solo
    audit_solo=CountedCallable(solo.audit_solo,meter,'raw_constraint_audit',{'raw_constraint_audits':1})

    ckpt=Path(cfg['checkpoint'])
    pc=PreTrainedConfig.from_pretrained(ckpt,local_files_only=True)
    pc.device=device;pc.n_action_steps=10;pc.chunk_size=50;pc.compile_model=False;pc.pretrained_path=ckpt
    if pc.num_inference_steps!=10 or pc.max_action_dim!=32 or pc.rtc_config is not None:raise ContractError('Frozen flow configuration changed')
    # The inherited PI05 loader catches load errors and can return a random
    # model. Observe its existing load once and fail closed before any forward;
    # this adds no second checkpoint load, tensor comparison, or model call.
    import safetensors.torch as st
    original_file_load=st.load_file
    original_state_load=PI05Policy.load_state_dict
    loader={'file_calls':[],'state_calls':[],'errors':[]}
    def file_load(filename,*a,**kw):
        record={'path':str(Path(filename).resolve()),'returned':False};loader['file_calls'].append(record)
        try:
            if Path(filename).resolve()!=(ckpt/'model.safetensors').resolve():raise ContractError('Unexpected policy state file')
            value=meter.call('policy_safetensors_load',lambda:original_file_load(filename,*a,**kw),{'policy_state_file_loads':1})
            record.update(returned=True,tensor_count=len(value));return value
        except BaseException as e:loader['errors'].append({'type':type(e).__name__,'message':str(e)});raise
    def state_load(self,state,*a,**kw):
        record={'model_id':id(self),'strict':kw.get('strict',True),'returned':False};loader['state_calls'].append(record)
        try:
            if record['strict'] is not True:raise ContractError('Non-strict policy loading forbidden')
            value=meter.call('policy_load_state_dict',lambda:original_state_load(self,state,*a,**kw),{'policy_state_dict_loads':1})
            record.update(returned=True,missing_keys=list(value.missing_keys),unexpected_keys=list(value.unexpected_keys));return value
        except BaseException as e:loader['errors'].append({'type':type(e).__name__,'message':str(e)});raise
    st.load_file=file_load;PI05Policy.load_state_dict=state_load
    try:
        policy=meter.call('load_PI05_SFT030000',lambda:PI05Policy.from_pretrained(ckpt,config=pc,local_files_only=True,strict=True),
            {'model_initializations':1,'policy_model_loads':1})
    finally:
        st.load_file=original_file_load;PI05Policy.load_state_dict=original_state_load
        write_new(out/'policy_loader.json',loader)
    if (loader['errors'] or len(loader['file_calls'])!=1 or len(loader['state_calls'])!=1
        or not loader['file_calls'][0]['returned'] or not loader['state_calls'][0]['returned']
        or loader['state_calls'][0]['model_id']!=id(policy) or loader['state_calls'][0].get('missing_keys')
        or loader['state_calls'][0].get('unexpected_keys')):
        raise ContractError('Actual policy loader did not prove one complete strict checkpoint load')
    policy.eval().requires_grad_(False)
    versions=[(p,p._version) for p in policy.parameters()]
    tokenizer=meter.call('load_pinned_tokenizer',lambda:AutoTokenizer.from_pretrained(cfg['tokenizer_name'],revision=cfg['tokenizer_revision'],local_files_only=True,padding_side='right'),{'tokenizer_loads':1})
    tokenizer.padding_side='right'
    tokenizer=CountedCallable(tokenizer,meter,'tokenize',{'tokenizer_calls':1})
    pre=meter.call('load_saved_preprocessor',lambda:PolicyProcessorPipeline.from_pretrained(
        pretrained_model_name_or_path=str(ckpt),config_filename='policy_preprocessor.json',
        overrides={'device_processor':{'device':device},'rename_observations_processor':{'rename_map':{'observation.image':'observation.images.base_0_rgb'}},'tokenizer_processor':{'tokenizer':tokenizer}},
        to_transition=batch_to_transition,to_output=transition_to_batch),{'preprocessor_loads':1})
    post=meter.call('load_saved_postprocessor',lambda:PolicyProcessorPipeline.from_pretrained(
        pretrained_model_name_or_path=str(ckpt),config_filename='policy_postprocessor.json',
        to_transition=policy_action_to_transition,to_output=transition_to_policy_action),{'postprocessor_loads':1})
    features=OfflineFeatures()
    features.device=torch.device(device);features.policy=policy;features.policy_config=pc;features.tokenizer=tokenizer
    features._instruction=cfg['source']['instruction'];features._visual_encoder_calls=0;features._visual_observations_encoded=0
    features._preprocess_observation=preprocess_observation
    features.preprocessor=CountedCallable(pre,meter,'preprocess_saved_observation',{'preprocessor_calls':1})
    model=policy.model
    # These are the original methods with entered/returned accounting only.
    model.paligemma_with_expert.embed_image=CountedCallable(model.paligemma_with_expert.embed_image,meter,'vision_tower_and_projector',{'visual_encoder_forwards':1,'encoder_forward_calls':1})
    model.paligemma_with_expert.embed_language_tokens=CountedCallable(model.paligemma_with_expert.embed_language_tokens,meter,'language_token_embedding',{'language_embedding_forwards':1,'encoder_forward_calls':1})
    policy._preprocess_images=CountedCallable(policy._preprocess_images,meter,'policy_image_preprocessing',{'image_preprocessing_calls':1})
    original_combined=model.paligemma_with_expert.forward
    def combined(*a,**kw):
        kind='prefix_transformer_forwards' if kw['inputs_embeds'][1] is None else 'action_expert_forwards'
        return meter.call(kind,lambda:original_combined(*a,**kw),{kind:1})
    model.paligemma_with_expert.forward=combined
    model.denoise_step=CountedCallable(model.denoise_step,meter,'denoise_step',{'flow_forward_calls':1})
    model.sample_noise=CountedCallable(model.sample_noise,meter,'rebuild_frozen_noise',{'noise_draws':1})

    with np.load(cfg['source']['observation_path'],allow_pickle=False) as saved:
        obs={'pixels':saved['pixels'].copy(),'agent_pos':saved['proprioception'].copy()}
    if obs['pixels'].shape!=(480,480,3) or obs['pixels'].dtype!=np.uint8 or obs['agent_pos'].shape!=(4,):raise ContractError('Saved step0 input shape changed')
    raw=np.load(cfg['source']['raw_plans_path'],allow_pickle=False)[0].copy()
    if raw.shape!=(50,4) or raw.dtype!=np.float32 or array_sha(raw)!=cfg['source']['raw50_sha256']:raise ContractError('Cached raw50 identity changed')
    base=np.clip(raw,-1,1).astype(np.float32)
    np.save(out/'cached_raw_a0.npy',raw,allow_pickle=False)
    np.save(out/'bounded_anchor.npy',base,allow_pickle=False)
    transform=meter.call('load_same_action_transform',lambda:ActionTransform.from_checkpoint(ckpt,device=device),{'normalizer_transform_loads':1})
    projection=meter.call('load_frozen_spatial_projection',lambda:torch.from_numpy(np.load(cfg['projection'],allow_pickle=False)).to(device),{'projection_loads':1})
    with torch.no_grad():
        vision=features.encode_visual_batch([obs],batch_size=1)
        if vision.shape!=(1,1,256,2048):raise ContractError('Q vision shape changed')
        rawvision=torch.as_tensor(vision,device=device).float()
        spatial=meter.call('canonical_singleton_spatial_projection',lambda:spatial_tokens(canonical_decode(rawvision),projection).flatten(1).half().float().cpu().numpy(),{'spatial_projection_calls':1})
        language=features.encode_instruction(cfg['source']['instruction'])
        if spatial.shape!=(1,4096) or language.shape!=(2048,):raise ContractError('Q encoder dimensions changed')
        context=meter.call('single_valid_frame_context',lambda:cpu_batch(spatial,[obs['agent_pos']],[],language,0,device='cpu'),{'context_builds':1})
    observed={k:v[0].numpy().copy() for k,v in context.items()}
    if observed['history_mask'].tolist()!=[False,False,False,False,True] or observed['proprio_mask'].tolist()!=[False,False,False,False,True] or observed['past_actions'].any() or observed['history'][:4].any() or observed['proprio'][:4].any() or float(observed['remaining'])!=1:
        raise ContractError('Single-frame causal mask contract failed')
    np.savez_compressed(out/'Q_observed_context.npz',**observed)
    np.savez_compressed(out/'same_source_encoder_outputs.npz',visual_patch_tokens=vision,spatial=spatial,language=language)
    write_new(out/'context_provenance.json',dict(source=cfg['source'],step1_used=False,past_actions_from_execution=0,
        zero_padding_is_masked=True,projection=cfg['projection'],checkpoint=cfg['checkpoint'],Q_features_require_D=False))
    original_load=torch.load
    def counted_load(*a,**kw):
        path=Path(a[0]).resolve()
        valid={Path(cfg['Q_assets']).resolve()/f'models/refit/member_{i}/selected.pt' for i in range(4)}
        if path not in valid:raise ContractError('Unexpected Q checkpoint load')
        return meter.call('load_Q_member',lambda:original_load(*a,**kw),{'critic_model_loads':1},{'path':str(path)})
    torch.load=counted_load
    original_from_state=critic_module.from_state
    critic_module.from_state=CountedCallable(original_from_state,meter,'construct_frozen_Q_member',{'model_initializations':1})
    try:selector=FrozenSelector(cfg['Q_assets'])
    finally:
        torch.load=original_load
        critic_module.from_state=original_from_state
    for i,q in enumerate(selector.models):
        q.features=CountedCallable(q.features,meter,'Q_member_features',{'critic_feature_transforms':1})
        q.forward=CountedCallable(q.forward,meter,'Q_member_forward_two_slots',{'critic_forward_calls':1})
    stage='objective_setup'
    class MeteredObjective(FrozenObjective):
        def __call__(self,commands):
            return meter.call('ensemble_objective_two_slots',lambda:super(MeteredObjective,self).__call__(commands),{'objective_forward_calls':1},
                {'stage':stage,'gradient_enabled':torch.is_grad_enabled(),'Q_acceptance_gate':False})
    objective=MeteredObjective(observed,base,selector=selector)
    original_grad=torch.autograd.grad
    gradients=[]
    def action_grad(*a,**kw):
        if any(p.requires_grad or p.grad is not None for p,_ in versions):raise ContractError('VLA parameter gradient enabled')
        kind='post_action_gradient_calls' if stage=='post_gradient' else 'velocity_action_gradient_calls'
        result=meter.call('action_only_gradient',lambda:original_grad(*a,**kw),{'action_gradient_calls':1,'critic_backward_calls':1,kind:1})
        for g in result:
            gradients.append(g.detach().float().cpu().numpy().copy())
        return result
    torch.autograd.grad=action_grad
    hook=None
    try:
        stage='anchor_score';anchor=objective.evaluate(base[:10])
        if anchor['mean_gain']!=0:raise ContractError('J(b;b) must be exactly zero')
        stage='post_gradient';direction,post_stats=post_direction(objective,transform)
        if post_stats['value']!=0:raise ContractError('Post gradient anchor changed')
        post_raw,post_matching,post_arrays=project_solo(raw,direction,cfg['matching'])
        post_audit=audit_solo(raw,post_raw,direction,cfg['matching'])
        stage='post_final_score';post_score=objective.evaluate(np.clip(post_raw[:10],-1,1))
        np.savez_compressed(out/'Post_arrays.npz',**post_arrays,command_gradient=gradients[0])
        write_new(out/'Post_result.json',dict(gradient=post_stats,matching=post_matching,audit=post_audit,score=post_score,Q_acceptance_gate=False))

        # CPU seed and current CUDA generator match V3. Noise is drawn exactly
        # once, checked before sampling, then explicitly passed into sample_actions.
        with torch.random.fork_rng(devices=[0]):
            torch.random.default_generator.manual_seed(cfg['source']['generation_seed'])
            torch.cuda.manual_seed(cfg['source']['generation_seed'])
            noise=model.sample_noise((1,50,32),torch.device(device))
        noise_sha=hashlib.sha256(noise.detach().float().cpu().numpy().tobytes()).hexdigest()
        write_new(out/'noise_reconstruction.json',dict(expected_sha256=cfg['source']['noise_sha256'],actual_sha256=noise_sha,
            shape=list(noise.shape),dtype=str(noise.dtype),seed=cfg['source']['generation_seed'],draws=1,matching=noise_sha==cfg['source']['noise_sha256'],retry=False))
        np.save(out/'reconstructed_noise.npy',noise.detach().float().cpu().numpy(),allow_pickle=False)
        if noise_sha!=cfg['source']['noise_sha256']:raise ContractError('Noise SHA mismatch; no baseline resampling or second draw allowed')
        with torch.no_grad():
            batch=features._policy_batch(obs,cfg['source']['instruction'])
            images,masks=policy._preprocess_images(batch)
        if len(images)!=3 or [bool(x[0]) for x in masks]!=[True,False,False]:raise ContractError('Frozen one-real/two-padded camera path changed')
        stage='velocity_flow';hook=FlowHook(model,transform,cfg['guidance']);hook.begin(objective)
        with torch.no_grad():
            native=meter.call('guided_sampling_cached_anchor',lambda:model.sample_actions(images,masks,batch['observation.language.tokens'],batch['observation.language.attention_mask'],noise=noise,num_steps=10),{'vla_sampling_calls':1,'model_gpu_inference_calls':1})
            internal=native[:,:,:4].detach().clone()
            commands=meter.call('postprocess_guided_raw50',lambda:post(internal.reshape(-1,4)).reshape(internal.shape),{'postprocessor_calls':1})
            guided=commands.float().cpu().numpy()[0].copy()
        if len(hook.times)!=10 or not np.allclose(hook.times,np.arange(10,0,-1)/10,atol=1e-6) or len(hook.logs)!=3 or not np.allclose([x['tau'] for x in hook.logs],[.3,.2,.1],atol=1e-6):raise ContractError('Unexpected ten-flow/last-three-gradient schedule')
        if hook.last_noise_sha!=noise_sha:raise ContractError('Actual guided x_t differs from reconstructed noise')
        if guided.shape!=(50,4) or not np.isfinite(guided).all():raise ContractError('Invalid guided raw50')
        vdirection=np.clip(guided,-1,1)[:10].astype(float)-base[:10].astype(float)
        velocity_raw,velocity_matching,velocity_arrays=project_solo(raw,vdirection,cfg['matching'])
        velocity_audit=audit_solo(raw,velocity_raw,vdirection,cfg['matching'])
        stage='velocity_final_score';velocity_score=objective.evaluate(np.clip(velocity_raw[:10],-1,1))
        np.savez_compressed(out/'Velocity_arrays.npz',**velocity_arrays,own_native_raw=guided,own_internal_guided=native.detach().float().cpu().numpy(),**{f'action_gradient_tau_{k}':g for k,g in enumerate(gradients[1:])})
        write_new(out/'Velocity_result.json',dict(updates=hook.logs,times=hook.times,matching=velocity_matching,audit=velocity_audit,score=velocity_score,
            gradient_quantity='dJ/dv=-tau*g_u; update v+10*dJ/dv; negative Euler dt=-.1',noise_sha256=hook.last_noise_sha,Q_acceptance_gate=False))
        if objective.stats()['objective_forward_calls']!=10 or objective.stats()['critic_member_forward_calls']!=40 or objective.stats()['objective_backward_calls']!=4:raise ContractError('Q arithmetic count mismatch')
        objective.verify();selector.verify(check_files=True)
        if any(p.requires_grad or p.grad is not None or p._version!=v for p,v in versions):raise ContractError('Frozen VLA parameter invariant changed')
        write_new(out/'numeric_checks.json',dict(status='passed',anchor_score=anchor,objective_stats=objective.stats(),
            critic_member_backward_paths=16,critic_member_backward_paths_scope='derived from four frozen members per four successful action-gradient calls; not hardware API calls',
            frozen_models=True,Q_member_feature_hashes=objective.feature_hashes,finite_action_gradients=all(np.isfinite(g).all() for g in gradients),
            input_raw_sha_unchanged=array_sha(raw)==cfg['source']['raw50_sha256'],own_radius_independent=True,shared_radius=False,
            VLA_parameter_backward=0,Q_parameter_updates=0,D_G0_calls=0,environment_instances=0,
            deployment_sampling_calls=cfg['deployment_sampling_calls'],cost_scope='cached single-snapshot numerical diagnostic only',
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved()))
    finally:
        torch.autograd.grad=original_grad
        if hook is not None:hook.close()
        torch.cuda.synchronize()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);parser.add_argument('--launch-directory',required=True)
    a=parser.parse_args();out=Path(a.launch_directory).resolve()/'diagnostic'
    r,p=load_authorization(a.release,full=True)
    if not held_reservation_fds():raise ContractError('Missing inherited whole-host occupancy reservation')
    claim=read(CAMPAIGN/'results/A/P10_PV_release_claims'/ (RELEASE+'.json'))
    if claim['release_sha256']!=r['_sha256'] or claim['run_id']!=r['run_id']:raise ContractError('Missing matching exclusive claim')
    if out.parent!=CAMPAIGN/'results/A/P10_PV_launcher_runs'/r['run_id']:raise ContractError('Output destination mismatch')
    out.mkdir(exist_ok=False)
    meter=Meter(out/'events.jsonl',p['diagnostic_caps'],lambda:gate(a.release,r['_sha256']))
    cfg=read(p['config']['path']);failure=None;start=time.monotonic()
    try:
        meter.call('offline_snapshot_attempt',lambda:None,{'offline_attempts':1})
        rows=meter.call('in_reservation_NVML_identity',lambda:verify_device({**r,**cfg['device']},cfg),{'native_nvml_identity_queries':1})
        write_new(out/'nvml_identity.json',dict(rows=rows,target=cfg['device']))
        run(cfg,out,meter)
        if meter.used!=p['diagnostic_caps']:raise ContractError('Successful path does not equal frozen explicit operation counts')
    except BaseException as e:
        failure=dict(type=type(e).__name__,message=str(e));write_new(out/'failure.json',failure)
    finally:
        ledger=reconcile(out/'events.jsonl',p['diagnostic_caps'])
        write_new(out/'RESOURCE_LEDGER.json',dict(ledger,status='failed' if failure else 'complete',failure=failure,
            elapsed_seconds=time.monotonic()-start,remaining_caps_reusable=False,automatic_retry=False,
            compute_scope='explicit Python/model entry calls; CUDA/framework internal APIs are not guessed as zero'))
        write_new(out/'ARTIFACT_MANIFEST.json',dict(files=[dict(path=str(x),size_bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(out.iterdir()) if x.is_file()]))
    return 3 if failure else 0

if __name__=='__main__':sys.exit(main())
