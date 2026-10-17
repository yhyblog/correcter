"""Real numeric setup extracted from accepted PV V3; imported only below gate.
Private integration changes: H10 policy config, no Q/D/G0/guidance loads.
Strict loader is inherited; the new collector obtains explicit fresh raw plans.
"""
import hashlib,json,os
from pathlib import Path
from importlib.metadata import version
import numpy as np
import torch
from core.contracts import ContractError,write_new
class CountedCallable:
    def __init__(self,fn,meter,name,units):self.fn,self.meter,self.name,self.units=fn,meter,name,units
    def __call__(self,*a,**kw):return self.meter.call(self.name,lambda:self.fn(*a,**kw),self.units)
    def __getattr__(self,k):return getattr(self.fn,k)
def initialize(cfg,out,meter,device):
    for name,expected in cfg['runtime_packages'].items():
        if version(name)!=expected:raise ContractError('Runtime package changed: '+name)
    if torch.version.git_version!='e2d141dbde55c2a4370fac5165b0561b6af4798b':raise ContractError('Torch commit changed')
    from lerobot.configs.policies import PreTrainedConfig
    from lerobot.policies.pi05.modeling_pi05 import PI05Policy
    from lerobot.policies.pi05 import processor_pi05  # register saved PI05 preprocessing step only
    from lerobot.processor import PolicyProcessorPipeline
    from lerobot.processor.converters import batch_to_transition, transition_to_batch, policy_action_to_transition, transition_to_policy_action
    from transformers import AutoTokenizer
    from feature_path import OfflineFeatures, preprocess_observation, canonical_decode, spatial_tokens, cpu_batch
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

    projection=meter.call('load_spatial_projection',lambda:torch.from_numpy(np.load(cfg['projection'],allow_pickle=False)).to(device),{'projection_loads':1})
    versions=[(p,p._version) for p in list(policy.parameters())+list(policy.buffers())]
    return locals()
