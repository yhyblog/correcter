"""Native H queue, one true-G0 C10 intervention, then restore native H."""
from collections import deque
import time
import numpy as np
from experiments.native10_training_20260916.protocol import seed_for

def run_episode(runtime,engine,source,method,H,emit,stop=lambda:False):
    if method not in ('R','Post','Velocity') or H not in (10,20,30,40,50):raise ValueError('unregistered main cell')
    frames,props=deque(maxlen=5),deque(maxlen=5)
    actions=[];rewards=[];success_flags=[];events=[];plans=[]
    raw=None;age=0;active_horizon=H;locked_until=0;first_cut=None;count=0;natural_index=0
    begin=time.monotonic();language=engine.language()
    engine.start_natural_stream(source['policy_seed'])
    for t in range(300):
        if stop() or time.monotonic()-begin>1800:raise RuntimeError('episode stop/deadline')
        frames.append(runtime.frame().copy());props.append(runtime.proprio().copy())
        if raw is None or age==active_horizon:
            raw,stats=engine.propose_natural();age=0;active_horizon=H
            plans.append(dict(step=t,kind='natural',natural_index=natural_index,H=H,policy_seed=source['policy_seed'],stats=stats));natural_index+=1
        if t>=locked_until and t%5==0 and min(active_horizon-age,300-t)>=5:
            observed=engine.context(list(frames),list(props),actions[-4:],language,t)
            monitor=engine.monitor(observed,raw[age:age+5].copy())
            mature=len(frames)==5 and len(actions)>=4
            legal=mature and age>0 and t+10<=300
            trigger=bool(legal and monitor['gate']>.05)
            event=dict(step=t,queue_age=age,native_H=H,active_horizon=active_horizon,history_mature=mature,
                legal_cut=bool(legal),gate_threshold=.05,true_G0_trigger=trigger,total_cap_allows=count<1,
                intervention_executed=False,forced_intervention=False,synthetic=False,**monitor)
            if trigger and count<1:
                seed=seed_for('D24_designated_a0',source['source_id'],source['policy_seed'],t,namespace=engine.namespace)
                raw,stats=engine.intervene(method,observed,seed,t);count+=1;first_cut=t
                age=0;active_horizon=10;locked_until=t+10
                event.update(intervention_executed=True,intervention_index=count,seed=seed,commit_until=locked_until,
                    old_tail_discarded=True,restore_native_H=H,generation=stats)
                plans.append(dict(step=t,kind='intervention',seed=seed,H=10,stats=stats))
            events.append(event);emit('monitor',event)
        action=raw[age].copy();age+=1;step=runtime.step(action,t)
        actions.append(np.asarray(action,np.float32));rewards.append(float(step['reward']));success_flags.append(bool(step['success']))
        emit('step',dict(step=t+1,success=bool(step['success']),interventions=count))
        if step['success'] or step['done'] or t==299:
            return dict(status='complete',success=bool(step['success']),steps=t+1,interventions=count,first_cut=first_cut,
                events=events,plans=plans,elapsed_control_seconds=time.monotonic()-begin,
                terminal_reason='success' if step['success'] else 'environment_done' if step['done'] else 's300',
                arrays=dict(actions=np.asarray(actions,np.float32),rewards=np.asarray(rewards),success_flags=np.asarray(success_flags)),
                sampling_calls=sum(x['stats']['policy_calls'] for x in plans),flow_calls=sum(x['stats']['policy_calls'] for x in plans)*10)
    raise RuntimeError('unreachable terminal')
