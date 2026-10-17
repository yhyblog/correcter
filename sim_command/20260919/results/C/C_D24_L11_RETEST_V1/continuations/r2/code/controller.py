"""Frozen main scientific functions with randomized-once or uncapped G0 timing."""
from collections import deque
import time
import hashlib
import numpy as np
from experiments.native10_training_20260916.protocol import seed_for


def random_coin(source_id,H,step):
    key=f'corrector_random_multi_v1|2026092203|{source_id}|H={H}|cut={step}'
    digest=hashlib.sha256(key.encode('utf-8')).digest()
    u=int.from_bytes(digest[:8],'big',signed=False)
    return dict(key=key,u64=u,trigger=u<2**63,p=.5)


def run_episode(runtime,engine,source,method,H,emit,stop=lambda:False,*,mode,random_cut=None):
    if method not in ('R','Post','Velocity') or H not in (10,20,30,40,50):raise ValueError('unregistered A unit')
    if mode not in ('G0-once','G0-multi'):raise ValueError('unregistered trigger mode')
    frames,props=deque(maxlen=5),deque(maxlen=5)
    actions=[];rewards=[];success_flags=[];events=[];plans=[];cuts=[]
    raw=None;age=0;active_horizon=H;locked_until=0;first_cut=None;last_cut=None;count=0;natural_index=0
    commitment=None;random_reached=False;random_reason=None;shadow_contexts=0
    begin=time.monotonic();language=engine.language()
    engine.start_natural_stream(source['policy_seed'])
    for t in range(300):
        if stop() or time.monotonic()-begin>1800:raise RuntimeError('episode stop/deadline')
        frames.append(runtime.frame().copy());props.append(runtime.proprio().copy())
        # Preserve main order: refill first, then examine the current queue/cut.
        if raw is None or age==active_horizon:
            restoring=commitment is not None and commitment['C10_complete'] and not commitment['native_H_restored']
            raw,stats=engine.propose_natural();age=0;active_horizon=H
            plans.append(dict(step=t,kind='natural',natural_index=natural_index,H=H,policy_seed=source['policy_seed'],stats=stats));natural_index+=1
            if restoring:
                commitment.update(native_H_restored=True,native_restore_step=t,new_plan_tail_discarded=True)
                emit('native_H_restored',dict(step=t,intervention_index=commitment['intervention_index'],native_H=H))
                commitment=None
        at_random=False
        if at_random:random_reached=True
        monitored=False
        if t>=locked_until and t%5==0 and min(active_horizon-age,300-t)>=5:
            monitored=True
            observed=engine.context(list(frames),list(props),actions[-4:],language,t)
            monitor=engine.monitor(observed,raw[age:age+5].copy())
            mature=len(frames)==5 and len(actions)>=4
            legal=mature and age>0 and t+10<=300
            true_trigger=bool(legal and monitor['gate']>.05)
            is_shadow=mode=='Random-multi'
            if is_shadow:shadow_contexts+=1
            allows=mode!='G0-once' or count<1
            coin=random_coin(source['source_id'],H,t) if mode=='Random-multi' and legal else None
            chosen=true_trigger
            event=dict(step=t,queue_age=age,native_H=H,active_horizon=active_horizon,history_mature=mature,
                legal_cut=bool(legal),gate_threshold=.05,true_G0_trigger=true_trigger,G0_shadow_only=is_shadow,
                mode=mode,planned_random_cut=None,random_coin=coin,random_schedule_trigger=bool(coin and coin['trigger']),
                total_cap_allows=mode!='G0-once' or count<1,total_intervention_cap=None,
                intervention_executed=False,forced_intervention=False,synthetic=False,**monitor)
            if at_random and not legal:
                random_reason='selected_cut_ineligible:' + ('history_immature' if not mature else 'queue_age_zero' if age==0 else 'insufficient_commit_budget')
            if chosen and allows:
                # Exact main domain: mode/branch/intervention index never enter this seed.
                seed=seed_for('D24_designated_a0',source['source_id'],source['policy_seed'],t,namespace=engine.namespace)
                raw,stats=engine.intervene(method,observed,seed,t);count+=1
                if first_cut is None:first_cut=t
                last_cut=t;cuts.append(t);age=0;active_horizon=10;locked_until=t+10
                event.update(intervention_executed=True,intervention_index=count,seed=seed,commit_until=locked_until,
                    old_tail_discarded=True,restore_native_H=H,generation=stats,C10_steps_executed=0,C10_complete=False,
                    native_H_restored=False,native_restore_step=None,new_plan_tail_discarded=False)
                commitment=event
                plans.append(dict(step=t,kind='intervention',seed=seed,H=10,stats=stats))
                if is_shadow:random_reason='executed_at_legal_coin'
            events.append(event);emit('monitor',event)
        if at_random and not monitored:random_reason='selected_cut_ineligible:commit_lock_or_insufficient_queue'
        action=raw[age].copy();age+=1;step=runtime.step(action,t)
        actions.append(np.asarray(action,np.float32));rewards.append(float(step['reward']));success_flags.append(bool(step['success']))
        if commitment is not None and t<locked_until:
            commitment['C10_steps_executed']+=1
            if t+1==locked_until:
                commitment['C10_complete']=True
                emit('C10_complete',dict(step=t+1,intervention_index=commitment['intervention_index'],C10_steps=10))
        emit('step',dict(step=t+1,success=bool(step['success']),interventions=count))
        yield dict(step=t+1,source_id=source['source_id'])
        if step['success'] or step['done'] or t==299:
            terminal_reason='success' if step['success'] else 'environment_done' if step['done'] else 's300'
            if mode=='Random-multi' and random_reason is None:
                random_reason='no_successful_legal_coin' if not count else 'executed_at_legal_coin'
            if commitment is not None and not commitment['native_H_restored']:
                commitment['restore_not_executed_reason']='episode_terminal:'+terminal_reason
                commitment['new_plan_tail_discarded']=True
            return dict(status='complete',success=bool(step['success']),steps=t+1,interventions=count,first_cut=first_cut,last_cut=last_cut,
                intervention_cuts=cuts,mode=mode,branch=method,planned_random_cut=None,
                random_slot_reached=None,
                no_intervention_reason=(random_reason if mode=='Random-multi' else 'no_legal_G0_above_threshold') if not count else None,
                random_schedule_disposition=random_reason if mode=='Random-multi' else None,random_legal_coin_count=sum(e.get('random_coin') is not None for e in events),
                shadow_DG0_contexts=shadow_contexts,shadow_D_member_calls=2*shadow_contexts,shadow_G0_member_calls=2*shadow_contexts,
                shadow_cost_in_actual_elapsed=True,events=events,plans=plans,elapsed_control_seconds=time.monotonic()-begin,
                terminal_reason=terminal_reason,
                arrays=dict(actions=np.asarray(actions,np.float32),rewards=np.asarray(rewards),success_flags=np.asarray(success_flags)),
                sampling_calls=sum(x['stats']['policy_calls'] for x in plans),flow_calls=sum(x['stats']['policy_calls'] for x in plans)*10)
    raise RuntimeError('unreachable terminal')
