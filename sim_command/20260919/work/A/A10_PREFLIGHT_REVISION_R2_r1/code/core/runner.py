"""Model-agnostic core scheduler. Backends must log their real low-level work."""
from .scheduling import CoreQueue, paired_seed
from .validation import ContractError


def run_core(*, backend, entry, journal, protocol, method, source, seed_namespace, shadow_N=False):
    queue = CoreQueue(protocol, method)
    chunks, observations, actions = [], [], []
    decision = 0
    current_chunk = None

    def close_chunk(reason):
        nonlocal current_chunk
        if current_chunk is not None:
            current_chunk.update(end_step=queue.step, actual_executed_length=queue.step-current_chunk['start_step'],
                                 termination_reason=reason)
            chunks.append(current_chunk)
            current_chunk = None

    def install(plan, phase):
        nonlocal current_chunk, decision
        plan_id = f"{source['source_id']}:{protocol.H}:{method}:{decision}"
        decision += 1
        if phase == 'normal':
            queue.install_natural(plan, plan_id)
        current_chunk = {'chunk_id': plan_id, 'start_step': queue.step, 'H': protocol.H,
                         'commitment': protocol.H if phase == 'normal' else protocol.C,
                         'generated_length': protocol.generated_length, 'phase': phase}
        return plan_id

    try:
        observation = journal.invoke('restore', lambda: backend.reset(source), methods=[method],
                                     units={'simulator_attempts': 1})
        while True:
            for key in ('success', 'terminated', 'truncated'):
                if type(observation[key]) is not bool:
                    raise ContractError('Fresh runtime must provide separate actual terminal flags')
            observations.append(observation)
            queue.observe_terminal(success=observation['success'], terminated=observation['terminated'],
                                   truncated=observation['truncated'])
            if queue.terminal:
                close_chunk(queue.termination_reason)
                break
            if queue.needs_plan:
                seed = paired_seed(seed_namespace, source['source_id'], protocol.H, queue.step,
                                   source['repeat'], decision, 'natural')
                plan = journal.invoke('natural_plan', lambda: backend.sample_natural(observation, seed, journal),
                    methods=[method], units={'vla_sampling_calls': 1}, environment_step=queue.step,
                    sampling_index=decision, decision_index=decision)
                install(plan, 'normal')
            # Natural exhaustion is handled before this check; new plans have age zero.
            if queue.monitor_eligible() and (method != 'N' or shadow_N):
                research = method == 'N'
                score = journal.invoke('monitor', lambda: backend.monitor(observations, actions, queue, journal),
                    methods=[] if research else [method], research_only=research,
                    units={'monitor_calls': 1}, environment_step=queue.step, decision_index=decision)
                if queue.alarm(score):
                    close_chunk('alarm')
                    seed = paired_seed(seed_namespace, source['source_id'], protocol.H, queue.step,
                                       source['repeat'], decision, 'intervention')
                    plan, metadata, arrays = entry.generate(method, backend.context(observations, actions, queue),
                                                            seed, queue.step)
                    plan_id = install(plan, 'intervention')
                    queue.install_intervention(plan, plan_id, score)
            action = queue.command()
            observation = journal.invoke('env_step', lambda: backend.step(action), methods=[method],
                units={'env_steps': 1}, environment_step=queue.step, decision_index=decision)
            actions.append(action)
            reason = queue.advance(success=observation['success'], terminated=observation['terminated'],
                                   truncated=observation['truncated'])
            if reason:
                close_chunk(reason)
        return {'technical_status': 'complete', 'success': queue.termination_reason == 'success',
                'executed_steps': queue.step, 'intervened': bool(queue.interventions), 'cut_step': queue.cut_step,
                'termination_reason': queue.termination_reason, 'chunks': chunks, 'observations': observations,
                'actions': actions, 'H': protocol.H, 'C': protocol.C}
    except BaseException:
        close_chunk('technical_failure')
        raise  # Durable event entries preserve failed costs; never replace source or synthesize a task label.
    finally:
        backend.close()
