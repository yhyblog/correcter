"""Small CPU-testable causal controller. No tensor or simulator imports.

Callbacks own real physics/numerics. This module owns order, queue lifetime,
causal visibility, legal cut and early-stop semantics. All events are private.
"""
from copy import deepcopy
from dataclasses import dataclass
import math
from core.contracts import ContractError

@dataclass(frozen=True)
class Flags:
    success: bool = False
    terminated: bool = False
    truncated: bool = False
    @property
    def stop(self): return self.success or self.terminated or self.truncated

class Queue:
    def __init__(self):
        self.rows=[]; self.raw=None; self.age=0; self.plan_id=None; self.horizon=0
    def replace(self, raw, horizon, plan_id):
        rows=deepcopy(raw.tolist() if hasattr(raw,'tolist') else raw)
        if len(rows)!=50 or any(len(x)!=4 or any(not math.isfinite(v) for v in x) for x in rows):
            raise ContractError('Plan must be finite raw50x4')
        if horizon not in (10,20):raise ContractError('Only C10/native H20 allowed')
        self.raw=rows; self.rows=deepcopy(rows[:horizon]); self.age=0
        self.plan_id=plan_id; self.horizon=horizon
    def peek(self,n):
        if len(self.rows)<n:raise ContractError('Insufficient queue')
        return [[min(1.,max(-1.,v)) for v in row] for row in self.rows[:n]]
    def pop(self):
        result=self.peek(1)[0];self.rows.pop(0);self.age+=1;return result
    def discard(self):
        evidence=dict(plan_id=self.plan_id,raw_unexecuted=50-self.age,committed_remaining=len(self.rows),age=self.age)
        self.rows=[];self.raw=None;self.plan_id=None;self.age=0;self.horizon=0
        return evidence

def legal_cut(step,queue,flags,interventions=0):
    if flags.stop:return False,'prior_success_or_native_termination'
    if not queue.rows:return False,'natural_refresh_boundary'
    if step!=5:return False,'not_prescribed_cut'
    if queue.age<=0:return False,'plan_age_not_positive'
    if len(queue.rows)<5:return False,'old_queue_below_five'
    if 300-step<10:return False,'insufficient_episode_budget'
    if interventions:return False,'intervention_limit'
    return True,'legal_non_natural_cut'

def validate_reference(reference,step,plan_id,executed):
    if reference['created_at']!=0 or reference['targets']!=[1,2,3,4,5] or step!=5:
        raise ContractError('Forecast time/target mismatch')
    if reference['plan_id']!=plan_id or reference['actions']!=executed:
        raise ContractError('Predicted commands were not the executed prefix')
    return True

def history_indices(step):
    if type(step) is not int or step<0:raise ContractError('Invalid causal step')
    return list(range(max(0,step-4),step+1)),list(range(max(0,step-4),step))

def run_branch(engine, branch, scheduled=True):
    if branch not in ('Post','Velocity'):raise ContractError('Unknown branch')
    queue=Queue();step=0;executed=[];flags=Flags()
    engine.emit('branch_start',state_restored=False,shared_prefix=False)
    obs,flags=engine.reset();engine.save_observation(obs,0)
    if flags.stop:return engine.finish('stopped_at_reset',step,queue)
    context0=engine.encode_context(obs,0,executed)
    raw=engine.sample(obs,'prefix',engine.seeds['generation_seed'])
    queue.replace(raw,20,'native_prefix_H20')
    reference=dict(created_at=0,targets=[1,2,3,4,5],plan_id=queue.plan_id,actions=queue.peek(5))
    reference['predictions']=engine.forecast(context0,reference['actions'],'t0_targets_1_to_5')
    engine.emit('forecast_created',created_at=0,target_steps=reference['targets'],available_observations=[0],planned_actions=reference['actions'])
    for _ in range(5):
        command=queue.pop();obs,flags=engine.step(command,step,queue.plan_id)
        executed.append(command);step+=1;engine.save_observation(obs,step)
        # Stop before feature/model calls after success/terminal output.
        if flags.stop:return engine.finish('early_prefix_stop',step,queue)
        context=engine.encode_context(obs,step,executed)
    valid,reason=legal_cut(step,queue,flags)
    engine.emit('cut_legality',step=step,legal=valid,reason=reason,age=queue.age,remaining=len(queue.rows))
    if not valid:return engine.finish(reason,step,queue)
    if not engine.check_prefix_at_cut():return engine.finish('independent_prefix_mismatch',step,queue)
    validate_reference(reference,step,queue.plan_id,executed)
    residual=engine.residual(reference['predictions'],context)
    future_actions=queue.peek(5)
    future=engine.forecast(context,future_actions,'t5_targets_6_to_10')
    score=engine.gate_score(context,future_actions,future)
    if not math.isfinite(score):raise ContractError('Nonfinite G0 output')
    alarm=score>engine.threshold
    forced=bool(scheduled and not alarm)
    engine.emit('trigger_decision',step=step,real_G0_score=score,threshold=engine.threshold,real_G0_trigger=alarm,
                scheduled_engineering_enabled=scheduled,forced_engineering_intervention=forced,
                execute_intervention=alarm or scheduled,residual=residual,residual_used_by_G0=False,
                G0_target='mean_fresh_minus_old_execute5_then_fixed10',Q_acceptance_gate=False)
    if not (alarm or scheduled):return engine.finish('G0_not_triggered',step,queue)
    old=queue.discard();engine.emit('old_H20_queue_discarded',**old)
    raw=engine.intervene(obs,context,branch,engine.seeds['suffix_seed'])
    queue.replace(raw,10,branch+'_C10')
    for _ in range(10):
        command=queue.pop();obs,flags=engine.step(command,step,queue.plan_id)
        executed.append(command);step+=1;engine.save_observation(obs,step)
        if flags.stop:return engine.finish('early_C10_stop',step,queue)
    if queue.rows or queue.age!=10:raise ContractError('C10 commitment did not end at ten')
    tail=queue.discard()
    if tail['raw_unexecuted']!=40:raise ContractError('C10 raw tail accounting changed')
    engine.clear_policy_queue()
    engine.emit('C10_tail_discarded',**tail,hidden_policy_queue_empty=True)
    raw=engine.sample(obs,'restore',engine.seeds['restore_seed'])
    queue.replace(raw,20,'restored_native_H20')
    command=queue.pop();obs,flags=engine.step(command,step,queue.plan_id)
    executed.append(command);step+=1;engine.save_observation(obs,step)
    if len(queue.rows)!=19 or queue.horizon!=20:raise ContractError('Restore must leave native H20 remainder 19')
    engine.emit('native_H20_restored',step=step,remaining=19,first_restore_action_executed=True,
                first_success=flags.success,native_terminated=flags.terminated,native_truncated=flags.truncated)
    return engine.finish('C10_and_H20_checked',step,queue)
