"""Per-environment model state; real dispatcher is also exercised by CPU fakes."""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import hashlib
import numpy as np

def validate_observation(obs):
    frame=np.asarray(obs['pixels']);prop=np.asarray(obs['agent_pos'])
    if frame.shape!=(480,480,3) or frame.dtype!=np.uint8 or prop.shape!=(4,) or not np.isfinite(prop).all():raise ValueError('invalid native observation shape/units')
    return frame

class EngineSessions:
    fields=('runtime','instruction','episode_out','natural_seed','natural_generator','counts')
    def __init__(self,engine,counts,units,root,audit):
        self.engine=engine;self.counts=counts;self.units=units;self.root=Path(root);self.audit=audit;self.contexts={}
    def handle(self,req):
        key=req['branch_id'];kind=req['kind'];uid=req['unit_id'];unit=self.units[uid]
        if kind=='begin':
            out=self.root/'episodes'/unit['uid_hash']
            if Path(req['episode_out'])!=out or req['instruction']!=unit['source']['instruction']:raise ValueError('RPC source/output mismatch')
            validate_observation(req['observation'])
            self.contexts[key]=dict(unit_id=uid,client_pid=req['client_pid'],counts={k:0 for k in self.engine.counts},numeric=Counter(),instruction=req['instruction'],episode_out=out,runtime=SimpleNamespace(observation=req['observation']),observed=None,observed_step=None,natural_seed=None,natural_generator=None,stream_started=False)
        ctx=self.contexts[key]
        if uid!=ctx['unit_id'] or req['client_pid']!=ctx['client_pid'] or req['source_id']!=unit['source_id']:raise ValueError('cross-environment RPC identity')
        engine=self.engine
        for name in self.fields:setattr(engine,name,ctx[name])
        engine.features._instruction=ctx['instruction']
        if 'observation' in req:
            validate_observation(req['observation']);engine.runtime.observation=req['observation']
        before=dict(self.counts.entered)
        if kind=='begin':reply={}
        elif kind=='language':reply=dict(value=engine.language())
        elif kind=='start_natural_stream':
            if req['seed']!=unit['policy_seed']:raise ValueError('natural seed changed')
            engine.start_natural_stream(req['seed']);ctx['stream_started']=True;reply={}
        elif kind=='propose_natural':
            if not ctx['stream_started']:raise ValueError('natural stream not initialized')
            plan,stats=engine.propose_natural();reply=dict(plan=plan,stats=stats)
        elif kind=='context':
            step=req['step']
            if step!=req['observation_step'] or len(req['frames'])!=len(req['props']) or len(req['frames'])!=min(5,step+1):raise ValueError('history/step ownership mismatch')
            for frame,prop in zip(req['frames'],req['props']):validate_observation(dict(pixels=frame,agent_pos=prop))
            if req.get('rgb_sha256') and hashlib.sha256(np.asarray(req['frames'][-1]).tobytes()).hexdigest()!=req['rgb_sha256']:raise ValueError('RPC frame provenance mismatch')
            ctx['observed']=engine.context(req['frames'],req['props'],req['past'],req['language'],step);ctx['observed_step']=step;reply=dict(context_id=step)
        elif kind in ('monitor','intervene'):
            if req['context_id']!=ctx['observed_step'] or req['observation_step']!=ctx['observed_step']:raise ValueError('stale/cross-branch model context')
            if kind=='monitor':reply=dict(value=engine.monitor(ctx['observed'],req['next_five']))
            else:
                if req['method']!=unit['method'] or req['step']!=ctx['observed_step']:raise ValueError('intervention identity mismatch')
                plan,stats=engine.intervene(req['method'],ctx['observed'],req['seed'],req['step']);reply=dict(plan=plan,stats=stats)
        elif kind=='snapshot':engine.verify();reply={}
        else:raise ValueError(kind)
        for name in self.fields:ctx[name]=getattr(engine,name)
        ctx['numeric'].update({k:v-before.get(k,0) for k,v in self.counts.entered.items()})
        if kind=='snapshot':reply.update(counts=dict(ctx['counts']),numeric=dict(ctx['numeric']))
        if req.get('rgb_sha256') and kind in ('begin','context'):
            self.audit(dict(kind=kind,unit_id=uid,source_id=unit['source_id'],branch_id=key,client_pid=ctx['client_pid'],step=req['observation_step'],rgb_sha256=req['rgb_sha256'],real_model_context=True,extra_render_calls=0))
        return reply
