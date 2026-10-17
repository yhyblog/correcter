"""CPU-prepared adapters for P00. No model loading, training, or simulation on import."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import uuid
from typing import Any

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE / 'upstream/guided-action-flow'

class ContractError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise ContractError(message)

def content_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def check_parent_splits(trajectories):
    splits={}
    identities=set()
    for trajectory in trajectories:
        parent=trajectory['parent_episode_id']; split=trajectory['split']
        require(parent not in splits or splits[parent]==split, 'Parent episode crosses splits')
        splits[parent]=split
        identity=tuple(trajectory[k] for k in ('parent_episode_id','source_id','branch_id','suffix_id'))
        require(identity not in identities,'Duplicate physical trajectory identity')
        identities.add(identity)
    return splits

def validate_trajectory(t, *, training=True):
    import numpy as np
    fields=['dataset_revision','split','task','instruction','parent_episode_id','source_id','branch_id','suffix_id','collection_policy_sha256','seed','H','generated_length','executed_prefix_length','normalizer_sha256','state_feature_sha256','language_feature_sha256','steps','observation_refs','policy_state','task_features','action_policy','raw_actions','rewards','successes','first_success_step','terminated','truncated','cut_reason','generated_chunk_ref','outcome_complete']
    for name in fields:require(name in t, 'Missing trajectory field: '+name)
    if training:require(t['split'] in ('train','development'),'Test/held data cannot enter learning views')
    steps=t['steps'];n=len(steps)
    require(n>0 and all(type(x) is int for x in steps),'Nonempty integer control-step indices required')
    require(steps==list(range(steps[0],steps[0]+n)),'Gaps or reordered transitions cannot be joined')
    require(len(t['observation_refs'])==n+1,'Require true current and next observation references')
    for reference in t['observation_refs']:
        require(isinstance(reference,dict) and reference.get('path') and reference.get('sha256'),'Unversioned or missing observation reference')
    for name in ('normalizer_sha256','state_feature_sha256','language_feature_sha256','collection_policy_sha256'):
        require(isinstance(t[name],str) and len(t[name])==64,'Missing feature/model identity: '+name)
    for name in ('policy_state','action_policy','raw_actions','rewards','successes','terminated','truncated'):
        require(len(t[name])==n,'Length mismatch: '+name)
    state=np.asarray(t['policy_state'],dtype=np.float32)
    actions=np.asarray(t['action_policy'],dtype=np.float32)
    raw=np.asarray(t['raw_actions'],dtype=np.float32)
    require(state.shape==(n,4),'GAF-v1 MW adapter accepts only four policy-side state coordinates')
    require(actions.shape==raw.shape==(n,4),'Actual MW actions must be four-dimensional')
    for x in (state,actions,raw,np.asarray(t['task_features']),np.asarray(t['rewards'])):
        require(np.isfinite(x).all(),'Nonfinite trajectory content')
    for name in ('successes','terminated','truncated'):
        require(all(type(v) is bool for v in t[name]),'Unknown/nonboolean '+name+' cannot be fabricated')
    require(not any(t['terminated'][:-1]) and not any(t['truncated'][:-1]),'Trajectory crosses an environment boundary')
    observed=next((step+1 for step,success in zip(steps,t['successes']) if success),None)
    require(t['first_success_step']==observed,'First-success time disagrees with per-step observations')
    require(type(t['executed_prefix_length']) is int and 0<t['executed_prefix_length']<=t['generated_length'],'Invalid actual execution prefix')
    require(t['H']>0 and t['generated_length']>0,'Invalid plan length')
    return n

def gaf_view(trajectories, *, split, horizon=10, gamma=0.99):
    """Keep upstream success-to-go/MSE data semantics; parent split is externally fixed."""
    import torch
    require(split in ('train','development'),'Learning view must be train/development')
    check_parent_splits(trajectories)
    sys.path.insert(0,str(UPSTREAM/'src')) if str(UPSTREAM/'src') not in sys.path else None
    from guided_action_flow.training.critic_dataset import build_action_chunk_dataset
    selected=[];ids=[];identities=set()
    for t in trajectories:
        validate_trajectory(t)
        if t['split']!=split:continue
        require(t['outcome_complete'] is True,'Censored/incomplete suffix cannot receive fabricated failure targets')
        identities.add((t['normalizer_sha256'],t['state_feature_sha256'],t['language_feature_sha256']))
        selected.append({'state':t['policy_state'],'action_policy':t['action_policy'],'success':t['successes'],'task_features':t['task_features']})
        ids.append({k:t[k] for k in ('parent_episode_id','source_id','branch_id','suffix_id','steps')})
    require(bool(selected),'No trajectories for requested split')
    require(len(identities)==1,'Feature/normalizer versions cannot be mixed')
    view=build_action_chunk_dataset(selected,action_horizon=horizon,gamma=gamma,task_feature_source='episode')
    view['provenance']=[dict(ids[int(e)],start_step=ids[int(e)]['steps'][int(f)]) for e,f in zip(view['episode_indices'],view['frame_indices'])]
    view['split']=split
    view['parent_ids']=sorted({item['parent_episode_id'] for item in ids})
    view['synthetic_only']=any(t.get('synthetic_only',False) for t in trajectories if t['split']==split)
    view['feature_identities']=list(next(iter(identities)))
    require(view['action_chunks'].device.type=='cpu','View preparation must remain on CPU')
    return view

def lvm_pair_indices(trajectory, *, k=10, normal_demo=False):
    """Pair only within a declared normal demonstration; token extraction remains separate."""
    validate_trajectory(trajectory)
    require(normal_demo,'VLA-Corrector normal-dynamics view requires explicit demonstration selection')
    require(k>0,'Prediction offset must be positive')
    n=len(trajectory['steps'])
    return [{'parent_episode_id':trajectory['parent_episode_id'],'source_id':trajectory['source_id'],'branch_id':trajectory['branch_id'],'suffix_id':trajectory['suffix_id'],'step':trajectory['steps'][i],'target_step':trajectory['steps'][i]+k,'observation_ref':trajectory['observation_refs'][i],'next_k_observation_ref':trajectory['observation_refs'][i+k],'normalized_action':trajectory['action_policy'][i],'token_shape':[256,2048],'k':k} for i in range(n-k+1)]

@dataclass
class EventLedger:
    ledger_id: str = field(default_factory=lambda:uuid.uuid4().hex)
    on_event: Any = None
    events: list[dict[str,Any]] = field(default_factory=list)
    pending: dict = field(default_factory=dict)
    next_id: int = 0
    def emit(self,event_type,**kwargs):
        status=kwargs['status']
        if status=='entered':
            event_id=self.next_id;self.next_id+=1;start=time.monotonic()
            self.pending.setdefault(event_type,[]).append((event_id,start))
        else:
            require(bool(self.pending.get(event_type)),'Returned/failed event lacks entered event')
            event_id,start=self.pending[event_type].pop()
        self.events.append({'event_id':event_id,'event_type':event_type,'wall_start':start,'wall_end':None if status=='entered' else time.monotonic(),**kwargs})
        if self.on_event is not None:self.on_event(self.events[-1])
    @contextmanager
    def operation(self,event_type,**kwargs):
        self.emit(event_type,status='entered',**kwargs)
        try:yield
        except Exception as exc:
            self.emit(event_type,status='failed',error=type(exc).__name__,**kwargs);raise
        else:self.emit(event_type,status='returned',**kwargs)

class GAFVelocityAdapter:
    """Guide each native pi05 sample, first 10 real action coordinates; no G0 gate."""
    def __init__(self,critics,*,state,task_features,beta=2.,clip=1.,uncertainty_scale=10.,min_gate=.1,ledger=None):
        require(len(critics)>0,'Need a frozen critic ensemble')
        self.critics=critics;self.state=state;self.task_features=task_features
        self.parameters=(beta,clip,uncertainty_scale,min_gate)
        self.ledger=ledger if ledger is not None else EventLedger()
    def __call__(self,action_t,velocity_t,time_t):
        import torch
        require(action_t.ndim==3 and action_t.shape==velocity_t.shape,'Expected equal [batch,time,action] tensors')
        require(action_t.shape[1]>=10 and action_t.shape[2]>=4,'Missing executed ten-step physical action prefix')
        require(bool(torch.isfinite(action_t).all()) and bool(torch.isfinite(velocity_t).all()),'Nonfinite flow inputs')
        beta,clip,scale,minimum=self.parameters
        require(beta>0 and scale>=0 and 0<=minimum<=1 and (clip is None or clip>0),'Invalid GAF guidance parameters')
        # Equivalent to pinned GAF qgf.py; split operations solely for actual-call logging.
        with torch.inference_mode(False),torch.enable_grad():
            x=action_t[:,:10,:4].detach().clone();v=velocity_t[:,:10,:4].detach().clone()
            t=torch.as_tensor(time_t,dtype=x.dtype,device=x.device)
            if t.ndim==1:t=t.reshape(-1,1,1)
            clean=(x-t*v).detach().clone().requires_grad_(True)
            values=[]
            for index,critic in enumerate(self.critics):
                with self.ledger.operation('critic_forward',count=1,member=index):
                    values.append(critic(obs_features=self.state,action_chunk=clean,proprio=None,task_features=self.task_features))
            qs=torch.stack(values);q=qs.mean(0)
            std=qs.std(0,unbiased=False) if len(values)>1 else torch.zeros_like(q)
            with self.ledger.operation('critic_backward',count=1):
                gradient=torch.autograd.grad(q.sum(),clean,create_graph=False)[0]
            raw_norm=gradient.reshape(len(x),-1).norm(dim=-1)
            if clip is not None:gradient=gradient*(float(clip)/(raw_norm+1e-6)).clamp(max=1).reshape(-1,1,1)
            norm=gradient.reshape(len(x),-1).norm(dim=-1)
            gate=torch.exp(-scale*std).clamp(min=minimum,max=1) if scale>0 else torch.ones_like(q)
            guided=v-gradient*gate.reshape(-1,1,1)/beta
            diagnostics={'q_value_mean':q.detach().mean(),'q_value_std_mean':std.detach().mean(),'q_gate_mean':gate.detach().mean(),'q_grad_norm_raw_mean':raw_norm.detach().mean(),'q_grad_norm_mean':norm.detach().mean()}
            require(bool(torch.isfinite(guided).all()),'Nonfinite guided velocity')
        result=velocity_t.detach().clone();result[:,:10,:4]=guided.detach()
        return result,diagnostics

@contextmanager
def pi05_denoiser_hook(model,adapter):
    """Bind an owned model instance only; restores its method even on failed sampling."""
    require(not getattr(model,'_b10_guidance_active',False),'Concurrent guidance on one model is not supported')
    original=model.denoise_step
    had_instance_override='denoise_step' in model.__dict__
    previous_instance_value=model.__dict__.get('denoise_step')
    def wrapped(*args,**kwargs):
        require(not args and 'x_t' in kwargs and 'timestep' in kwargs,'Pinned pi05 denoise_step keyword API required')
        adapter.ledger.emit('flow_forward',status='entered')
        try:
            velocity=original(**kwargs)
        except Exception as exc:
            adapter.ledger.emit('flow_forward',status='failed',error=type(exc).__name__);raise
        adapter.ledger.emit('flow_forward',status='returned')
        return adapter(kwargs['x_t'],velocity,kwargs['timestep'])[0]
    model._b10_guidance_active=True;model.denoise_step=wrapped
    try:yield
    finally:
        if had_instance_override:model.denoise_step=previous_instance_value
        else:del model.denoise_step
        del model._b10_guidance_active

def legal_e6_cut(*,step,plan_age,remaining_queue,terminated=False,success=False,intervened=False,budget=300):
    return (not terminated and not success and step%5==0 and plan_age>0 and remaining_queue>=5 and budget-step>=10)

@dataclass
class CausalD5Monitor:
    """episode_id is a unique physical rollout identity, including branch/suffix/reset."""
    threshold: float
    feature_scale: Any
    episode_id: str
    pending: dict = field(default_factory=dict)
    intervened: bool = False
    def observe_or_skip(self, **kwargs):
        """Unavailable/misaligned observations are missing diagnostics, never alarms."""
        try:
            return self.observe(**kwargs)
        except ContractError as exc:
            issued=kwargs.get('issued_step')
            if isinstance(issued,int) and kwargs.get('observed_step',-1)>=issued+5:
                self.pending.pop(issued,None)
            return {'score':None,'triggered':False,'eligible':False,'missing_reason':str(exc),'downstream':'R'}
    def register(self,*,issued_step,predicted_features,conditioned_raw_actions):
        import numpy as np
        predicted=np.asarray(predicted_features,dtype=float);actions=np.asarray(conditioned_raw_actions,dtype=float)
        require(predicted.ndim in (2,3) and predicted.shape[-2]==5 and actions.shape==(5,4),'D5 prediction/action window must be five actual steps')
        require(np.isfinite(predicted).all() and np.isfinite(actions).all(),'Nonfinite D5 prediction')
        require(issued_step not in self.pending,'Duplicate pending prediction')
        self.pending[issued_step]=(predicted.copy(),actions.copy())
    def observe(self,*,issued_step,observed_step,actual_features,executed_raw_actions,episode_id,plan_age,remaining_queue,success=False,terminated=False):
        import numpy as np
        require(episode_id==self.episode_id,'Prediction crossed reset/episode identity')
        require(observed_step==issued_step+5,'Prediction must mature at the real five-step arrival')
        require(issued_step in self.pending,'No prior prediction for this observation')
        predicted,actions=self.pending[issued_step]
        actual=np.asarray(actual_features,dtype=float);executed=np.asarray(executed_raw_actions,dtype=float);scale=np.asarray(self.feature_scale,dtype=float)
        require(actual.shape==predicted.shape[-2:],'Actual observations do not match the prediction window')
        require(executed.shape==actions.shape and np.array_equal(actions,executed),'Conditioned actions were not actually executed')
        require(np.isfinite(actual).all() and np.isfinite(scale).all() and (scale>0).all(),'Invalid observed features or fixed train-only scale')
        if predicted.ndim==3 and scale.ndim==2:scale=scale[:,None,:]
        score=float(np.mean(((predicted-actual)/scale)**2))
        eligible=legal_e6_cut(step=observed_step,plan_age=plan_age,remaining_queue=remaining_queue,terminated=terminated,success=success,intervened=self.intervened)
        triggered=eligible and score>self.threshold
        del self.pending[issued_step]
        # Multi protocol: no episode-wide suppression after a triggered local window.
        return {'score':score,'triggered':triggered,'eligible':eligible,'decision_step':observed_step,'prediction_step':issued_step,'downstream':'R','max_interventions':None}

def select_development_threshold(episodes):
    """Closest intervention frequency to G0; no success labels used, ties favor fewer."""
    require(bool(episodes),'Need development episodes including no-alarm cases')
    require(all(e['split']=='development' for e in episodes),'Threshold calibration is development-only')
    require(len({e['parent_episode_id'] for e in episodes})==len(episodes),'Threshold calibration requires one row per parent')
    values=[float(s) for e in episodes for s in e['eligible_scores']]
    require(all(math.isfinite(s) for s in values),'Nonfinite development score')
    target=sum(bool(e['g0_intervened']) for e in episodes)
    candidates=sorted(set(values))
    if candidates:candidates=[math.nextafter(candidates[0],-math.inf)]+candidates
    else:candidates=[0.]
    counts=[sum(any(float(s)>threshold for s in e['eligible_scores']) for e in episodes) for threshold in candidates]
    best=min(range(len(candidates)),key=lambda i:(abs(counts[i]-target),counts[i],-candidates[i]))
    return {'threshold':candidates[best],'strict_comparison':'>','development_episodes':len(episodes),'target_g0_interventions':target,'achieved_anomaly_interventions':counts[best],'selection_uses_success':False,'tie_rule':'closest count; fewer interventions; larger threshold','parent_ids':sorted(e['parent_episode_id'] for e in episodes)}

def e1_loss(logits,outcomes,*,candidate_weights,gain_weights,pair_weights,gain_enabled,pair_enabled):
    """Same source means/alias weights and probability differences as the frozen core."""
    import torch
    from torch.nn import functional as F
    require(logits.ndim==2 and logits.shape[1]==13 and outcomes.shape==(*logits.shape,4),'Expected source/13 candidates/4 outcomes')
    cw=torch.as_tensor(candidate_weights,device=logits.device,dtype=logits.dtype)
    gw=torch.as_tensor(gain_weights,device=logits.device,dtype=logits.dtype)
    pw=torch.as_tensor(pair_weights,device=logits.device,dtype=logits.dtype)
    require(cw.shape==gw.shape==logits.shape and pw.shape==(len(logits),5),'Invalid alias weights')
    require(bool(torch.isfinite(logits).all()),'Nonfinite logits')
    require(bool(((outcomes==0)|(outcomes==1)).all()),'E1 requires all four real binary outcomes')
    for weight in (cw,gw,pw):require(bool(torch.isfinite(weight).all()) and bool(((weight>=0)&(weight<=1)).all()),'Invalid weights')
    require(bool((cw[:,0]>0).all()) and bool((gw[:,0]==0).all()),'a0 must be included in BCE and excluded from gain')
    y=outcomes.to(logits.dtype).mean(-1);p=logits.sigmoid()
    def average(value,weight):
        denominator=weight.sum(-1)
        return ((value*weight).sum(-1)/torch.where(denominator>0,denominator,torch.ones_like(denominator))).mean()
    bce=average(F.binary_cross_entropy_with_logits(logits,y,reduction='none'),cw)
    gain=average(((p-p[:,:1])-(y-y[:,:1])).square(),gw)
    pairs=((1,2),(3,4),(5,6),(7,8),(11,12))
    difference=torch.stack([(p[:,a]-p[:,b])-(y[:,a]-y[:,b]) for a,b in pairs],-1)
    pair=average(difference.square(),pw)
    return {'loss':bce+int(gain_enabled)*gain+.5*int(pair_enabled)*pair,'bce':bce,'gain_mse':gain,'pair_mse':pair}
