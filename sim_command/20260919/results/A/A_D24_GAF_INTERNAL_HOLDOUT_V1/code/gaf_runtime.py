"""Small counters and frozen GAF ensemble; no public event bridge or G0 gate."""
from collections import Counter
from contextlib import contextmanager
import time
from qio import read
from paths import ROOT
from b10_adapters import GAFVelocityAdapter,pi05_denoiser_hook


class Counts:
    def __init__(self):self.entered=Counter();self.returned=Counter();self.seconds=Counter();self.failed=[]
    def call(self,name,fn,units=None,detail=None):
        units=units or {};self.entered.update(units);start=time.monotonic()
        try:
            value=fn();self.returned.update(units);return value
        except BaseException as e:
            self.failed.append(dict(name=name,type=type(e).__name__,message=str(e)));raise
        finally:self.seconds[name]+=time.monotonic()-start
    def snapshot(self):return dict(entered=dict(self.entered),returned=dict(self.returned),seconds=dict(self.seconds),failed=list(self.failed))


class Ledger:
    def __init__(self):self.entered=Counter();self.returned=Counter();self.failed=Counter();self.seconds=Counter()
    def emit(self,event,status,**kw):
        if status=='entered':self.entered[event]+=kw.get('count',1)
        elif status=='returned':self.returned[event]+=kw.get('count',1)
        elif status=='failed':self.failed[event]+=kw.get('count',1)
    @contextmanager
    def operation(self,event,count=1,**kw):
        self.emit(event,'entered',count=count);start=time.monotonic()
        try:yield
        except BaseException:
            self.emit(event,'failed',count=count);raise
        else:self.emit(event,'returned',count=count)
        finally:self.seconds[event]+=time.monotonic()-start
    def snapshot(self):return dict(entered=dict(self.entered),returned=dict(self.returned),failed=dict(self.failed),seconds=dict(self.seconds))


def load_critics(device):
    import torch
    from guided_action_flow.critics.action_chunk_critic import ActionChunkCritic,ActionChunkCriticConfig
    critics=[]
    for seed in read(ROOT/'config/CONFIG.json')['seeds']:
        result=read(ROOT/f'fits/{seed}/RESULT.json')
        if result['status']!='complete' or result['counts']['optimizer_updates']!=10000:raise ValueError('required GAF member fit incomplete')
        saved=torch.load(ROOT/f'fits/{seed}/selected.pt',map_location='cpu',weights_only=True)
        critic=ActionChunkCritic(ActionChunkCriticConfig(**saved['critic_config']))
        critic.load_state_dict(saved['model_state_dict']);critic.module.to(device).eval().requires_grad_(False)
        critics.append(critic)
    return critics


def make_adapter(critics,observed_state,language,device,ledger):
    import torch
    # These inputs are genuine current observation/language and are outside
    # inference_mode, allowing autograd through the clean action only.
    state=torch.as_tensor(observed_state,dtype=torch.float32,device=device).reshape(1,4)
    task=torch.as_tensor(language,dtype=torch.float32,device=device).reshape(1,2048)
    return GAFVelocityAdapter(critics,state=state,task_features=task,ledger=ledger,**read(ROOT/'config/CONFIG.json')['guidance'])
