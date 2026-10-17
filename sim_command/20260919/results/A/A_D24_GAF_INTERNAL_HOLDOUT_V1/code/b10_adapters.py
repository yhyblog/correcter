from contextlib import contextmanager
class ContractError(ValueError):pass
def require(condition,message):
    if not condition:raise ContractError(message)

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

