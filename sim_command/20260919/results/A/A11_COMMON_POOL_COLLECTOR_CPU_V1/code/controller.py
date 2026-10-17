"""Actual H10/cut5 collector controller. Fixtures call this same function."""
from pool_protocol import command,classify_outcome
from full_state import compare
from core.contracts import ContractError
def run_attempt(engine,job,recorder,reference=None):
    if engine.task!='shelf-place-v3':raise ContractError('task not in first collector allowlist')
    if engine.H!=10 or engine.cut!=5 or engine.target!=300:raise ContractError('unfrozen temporal config')
    name,family,repeat=job;normal=name=='normal';step=0;plan=None;age=0
    success=terminated=truncated=False;first_success=None;captured=None;bank=None;restore=None
    obs=engine.reset();engine.observe(obs,0)
    recorder.emit('attempt_started',attempt_role=name,absolute_target=300,cut=5,H=10)
    while step<300:
        if step==5:
            if age!=5 or plan is None:raise ContractError('illegal cut queue age')
            captured=engine.capture(step,plan,age)
            recorder.emit('cut_captured',absolute_step=step,queue_age=age)
            if normal:
                engine.save_reference(captured)
                bank=engine.generate_bank(obs)
                recorder.emit('bank_created',fresh_plans=3,local_plans=2)
            else:
                engine.verify_prefix(reference)
                restore=engine.compare_state(reference['state'],captured)
                engine.save_verification(restore)
                if restore['level']!='full_state_verified':raise ContractError('full-state mismatch before intervention')
                bank=engine.load_bank(reference)
                selected=bank[family] if family!='old' else plan
                commitment=10 if name.startswith('Q_') else 5
                start=age if family=='old' else 0
                recorder.emit('intervention_entered',target_namespace='Q_C10' if commitment==10 else 'G0_C5',
                    absolute_step=5,commitment=commitment,restore_level=restore['level'],repeat_id=repeat)
                for index in range(commitment):
                    obs,info=engine.step(command(selected,start+index),step,raw_plan=selected,raw_index=start+index)
                    step+=1;engine.observe(obs,step)
                    success=bool(info['success']);terminated=bool(info['terminated']);truncated=bool(info['truncated'])
                    if info.get('technical_failure'):raise ContractError('native technical failure')
                    if success:first_success=step
                    if success or terminated or truncated:break
                recorder.emit('commitment_finished',actual_steps=index+1,absolute_step=step,
                    discarded_raw_tail=50-(start+index+1),early_terminal=bool(success or terminated or truncated))
                plan=None;age=0;engine.clear_policy_queue()
                if success or terminated or truncated:break
        if plan is None or age==10:
            namespace='prefix' if step<5 else 'normal' if normal else 'Q_C10' if name.startswith('Q_') else 'G0_C5'
            plan=engine.sample(obs,namespace,repeat,step);age=0
            recorder.emit('H10_plan_installed',absolute_step=step,horizon=10)
        obs,info=engine.step(command(plan,age),step,raw_plan=plan,raw_index=age);age+=1;step+=1;engine.observe(obs,step)
        success=bool(info['success']);terminated=bool(info['terminated']);truncated=bool(info['truncated'])
        if info.get('technical_failure'):raise ContractError('native technical failure')
        if success:first_success=step
        if success or terminated or truncated:break
    outcome=classify_outcome(step,success,terminated,truncated)
    result=dict(status='complete' if outcome['outcome_complete'] else 'incomplete',
        role=name,controls=step,legal_cut_reached=captured is not None,
        outcome=outcome,first_success_step=first_success,
        terminated=terminated,truncated=truncated,
        restore_level='reference_capture' if normal else None if restore is None else restore['level'],
        full_target_is_parent_absolute=True,synthetic=engine.synthetic)
    recorder.emit('attempt_finished',**{k:v for k,v in result.items() if k!='synthetic'})
    engine.finish(result)
    return result
def sequential_jobs(jobs,run_one):
    """Same scheduler used by reserved launcher; no retries and no fake emitter."""
    rows=[]
    for job in jobs:
        result=run_one(job);rows.append(result)
        if result.get('returncode')!=0 or result.get('remaining_group') or result.get('cleanup_complete') is not True:break
        branch=result.get('result',{})
        if branch.get('status')!='complete' or not branch.get('legal_cut_reached'):break
        if job[0]!='normal' and branch.get('restore_level')!='full_state_verified':break
    return rows
