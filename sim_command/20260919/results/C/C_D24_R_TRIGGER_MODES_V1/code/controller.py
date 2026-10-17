"""Frozen native-H/C10 mechanics with authorized Random-once and G0-multi routing."""
from collections import deque
import time
import numpy as np
from experiments.native10_training_20260916.protocol import seed_for

def run_episode(runtime,engine,source,method,H,emit,stop=lambda:False,*,mode,random_cut=None):
    if method != 'R' or H not in (10,20,30,40,50) or mode not in ('Random-once','G0-multi'):
        raise ValueError('unregistered C trigger cell')
    if (mode == 'Random-once') != (random_cut is not None):
        raise ValueError('random cut presence must match mode')
    frames,props=deque(maxlen=5),deque(maxlen=5)
    actions=[];rewards=[];success_flags=[];events=[];plans=[];cuts=[];restorations=[]
    raw=None;age=0;active_horizon=H;locked_until=0;first_cut=None;count=0;natural_index=0
    monitor_seconds=0.;random_visited=False;random_reason=None
    begin=time.monotonic();language=engine.language()
    engine.start_natural_stream(source['policy_seed'])
    for t in range(300):
        if stop() or time.monotonic()-begin>1800:raise RuntimeError('episode stop/deadline')
        frames.append(runtime.frame().copy());props.append(runtime.proprio().copy())
        if raw is None or age==active_horizon:
            if raw is not None and count and t == locked_until:
                restorations.append(dict(step=t,from_commitment=10,native_H=H,old_tail_discarded=True))
            raw,stats=engine.propose_natural();age=0;active_horizon=H
            plans.append(dict(step=t,kind='natural',natural_index=natural_index,H=H,policy_seed=source['policy_seed'],stats=stats));natural_index+=1
        if mode=='Random-once' and t==random_cut:
            random_visited=True;random_reason='scheduled_cut_ineligible'
        if t>=locked_until and t%5==0 and min(active_horizon-age,300-t)>=5:
            monitor_start=time.monotonic()
            observed=engine.context(list(frames),list(props),actions[-4:],language,t)
            monitor=engine.monitor(observed,raw[age:age+5].copy())
            monitor_seconds+=time.monotonic()-monitor_start
            mature=len(frames)==5 and len(actions)>=4
            legal=mature and age>0 and t+10<=300
            trigger=bool(legal and monitor['gate']>.05)
            timing_selected=(t==random_cut) if mode=='Random-once' else trigger
            cap_allows=(mode=='G0-multi' or count<1)
            event=dict(step=t,queue_age=age,native_H=H,active_horizon=active_horizon,history_mature=mature,
                legal_cut=bool(legal),gate_threshold=.05,true_G0_trigger=trigger,total_cap_allows=cap_allows,
                mode=mode,random_scheduled_cut=random_cut,timing_selected=bool(timing_selected),shadow_G0=mode=='Random-once',
                intervention_executed=False,forced_intervention=False,synthetic=False,**monitor)
            if legal and timing_selected and cap_allows:
                seed=seed_for('D24_designated_a0',source['source_id'],source['policy_seed'],t,namespace=engine.namespace)
                raw,stats=engine.intervene(method,observed,seed,t);count+=1;cuts.append(t)
                if first_cut is None:first_cut=t
                age=0;active_horizon=10;locked_until=t+10
                event.update(intervention_executed=True,intervention_index=count,seed=seed,commit_until=locked_until,
                    old_tail_discarded=True,restore_native_H=H,generation=stats)
                plans.append(dict(step=t,kind='intervention',seed=seed,H=10,stats=stats))
                if mode=='Random-once':random_reason='executed_at_frozen_cut'
            events.append(event);emit('monitor',event)
        action=raw[age].copy();age+=1;step=runtime.step(action,t)
        actions.append(np.asarray(action,np.float32));rewards.append(float(step['reward']));success_flags.append(bool(step['success']))
        emit('step',dict(step=t+1,success=bool(step['success']),interventions=count))
        if step['success'] or step['done'] or t==299:
            if mode=='Random-once' and not random_visited:random_reason='terminal_before_scheduled_cut'
            no_intervention_reason=None if count else (random_reason if mode=='Random-once' else 'no_legal_G0_trigger_before_terminal')
            return dict(status='complete',success=bool(step['success']),steps=t+1,interventions=count,first_cut=first_cut,
                last_cut=cuts[-1] if cuts else None,intervention_cuts=cuts,restorations=restorations,mode=mode,branch=method,
                random_scheduled_cut=random_cut,random_cut_visited=random_visited if mode=='Random-once' else None,
                random_schedule_outcome=random_reason,no_intervention_reason=no_intervention_reason,
                monitor_seconds=monitor_seconds,shadow_context_DG0_seconds=monitor_seconds if mode=='Random-once' else 0.,
                shadow_G0=mode=='Random-once',events=events,plans=plans,elapsed_control_seconds=time.monotonic()-begin,
                terminal_reason='success' if step['success'] else 'environment_done' if step['done'] else 's300',
                arrays=dict(actions=np.asarray(actions,np.float32),rewards=np.asarray(rewards),success_flags=np.asarray(success_flags)),
                sampling_calls=sum(x['stats']['policy_calls'] for x in plans),flow_calls=sum(x['stats']['policy_calls'] for x in plans)*10)
    raise RuntimeError('unreachable terminal')
