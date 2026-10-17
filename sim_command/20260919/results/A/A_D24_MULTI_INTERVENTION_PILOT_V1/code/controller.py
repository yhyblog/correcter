"""Real raw H10 queue/controller, injected numerical engine/environment for CPU tests."""
from collections import deque
import time
import numpy as np
from experiments.native10_training_20260916.semantics import Native10Queue
from experiments.native10_training_20260916.protocol import source_seed, suffix_seed, candidate_seed

def run_episode(runtime,engine,source,arm,emit,stop=lambda:False):
    if arm not in ('R_once','R_multi','Post_once','Post_multi','Velocity_once','Velocity_multi'):
        raise ValueError('unregistered intervention method')
    method,mode=arm.rsplit('_',1);limit=1 if mode=='once' else None
    case=dict(task=source['task'],env_seed=source['env_seed'],episode_id=source['source_id'],case_id=source['source_id'])
    frames,props=deque(maxlen=5),deque(maxlen=5)
    actions=[];rewards=[];success_flags=[];events=[];plans=[]
    queue=Native10Queue(budget=300);locked_until=0;first_cut=None;count=0;natural_index=0;suffix_index=0
    begin=time.monotonic();language=engine.language()
    for t in range(300):
        if stop():raise RuntimeError('owned worker stop requested')
        if time.monotonic()-begin>1800:raise RuntimeError('pilot episode timeout')
        frames.append(runtime.frame().copy());props.append(runtime.proprio().copy())
        if queue.needs_plan(t):
            if first_cut is None:
                seed=source_seed(case,natural_index,namespace=engine.namespace);natural_index+=1
            else:
                seed=suffix_seed(case,first_cut,0,suffix_index,namespace=engine.namespace);suffix_index+=1
            raw,stats=engine.propose(seed)
            queue.replace(raw,t);plans.append(dict(step=t,kind='natural',seed=seed,stats=stats))
        # Commitment locks cover exactly the C10 actions, with no extra cooldown.
        # Monitoring resumes on the ordinary absolute 5-step clock after C10.
        if t>=locked_until and queue.monitor_ready(t):
            observed=engine.context(list(frames),list(props),actions[-4:],language,t)
            monitor=engine.monitor(observed,queue.peek_block(5,t))
            mature=len(frames)==5 and len(actions)>=4
            legal=mature and queue.alarm_eligible(t) and t+10<=300
            trigger=bool(legal and monitor['gate']>.05)
            allowed=limit is None or count<limit
            event=dict(step=t,queue_age=queue.age,history_mature=mature,legal_cut=bool(legal),
                gate_threshold=.05,true_G0_trigger=trigger,total_cap_allows=allowed,
                intervention_executed=False,forced_intervention=False,synthetic=False,**monitor)
            if trigger and allowed:
                seed=candidate_seed(case,t,namespace=engine.namespace)
                raw,stats=engine.intervene(method,observed,seed,t)
                count+=1
                if first_cut is None:first_cut=t
                queue=Native10Queue(start_step=t,budget=300);queue.replace(raw,t)
                locked_until=t+10
                event.update(intervention_executed=True,intervention_index=count,seed=seed,
                    commit_until=locked_until,old_tail_discarded=True,generation=stats)
                plans.append(dict(step=t,kind='intervention',seed=seed,stats=stats))
            events.append(event);emit('monitor',event)
        action=queue.pop(t);step=runtime.step(action,t)
        actions.append(np.asarray(action,np.float32));rewards.append(float(step['reward']));success_flags.append(bool(step['success']))
        emit('step',dict(step=t+1,success=bool(step['success']),interventions=count))
        if step['success'] or step['done'] or t==299:
            return dict(status='complete',success=bool(step['success']),steps=t+1,interventions=count,
                first_cut=first_cut,events=events,plans=plans,elapsed_control_seconds=time.monotonic()-begin,
                terminal_reason='success' if step['success'] else 'environment_done' if step['done'] else 's300',
                arrays=dict(actions=np.asarray(actions,np.float32),rewards=np.asarray(rewards),success_flags=np.asarray(success_flags)),
                sampling_calls=sum(x['stats']['policy_calls'] for x in plans),
                flow_calls=sum(x['stats']['policy_calls'] for x in plans)*10)
    raise RuntimeError('unreachable control termination')

