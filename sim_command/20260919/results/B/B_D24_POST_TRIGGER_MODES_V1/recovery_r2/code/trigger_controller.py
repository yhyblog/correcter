"""Frozen main controller with only random-once / uncapped-G0 trigger routing."""
from collections import deque
import time
import numpy as np
from experiments.native10_training_20260916.protocol import seed_for


def run_episode(runtime, engine, source, method, H, emit, stop=lambda: False,
                *, mode, random_cut=None):
    if method != 'Post' or H not in (10, 20, 30, 40, 50):
        raise ValueError('unregistered B branch/H')
    if mode not in ('Random-once', 'G0-multi'):
        raise ValueError('unregistered trigger mode')
    if mode == 'Random-once' and (type(random_cut) is not int or random_cut not in range(5, 291, 5)):
        raise ValueError('missing frozen random cut')
    if mode == 'G0-multi' and random_cut is not None:
        raise ValueError('multi does not consume random timing')
    frames, props = deque(maxlen=5), deque(maxlen=5)
    actions, rewards, success_flags, events, plans, cuts, commitments = [], [], [], [], [], [], []
    raw = None; age = 0; active_horizon = H; locked_until = 0
    first_cut = None; count = 0; natural_index = 0; committed_cut = None
    random_reason = None; random_evaluated = False
    monitor_seconds = 0.; context_seconds = 0.
    begin = time.monotonic(); language = engine.language()
    engine.start_natural_stream(source['policy_seed'])
    for t in range(300):
        if stop() or time.monotonic() - begin > 1800:
            raise RuntimeError('episode stop/deadline')
        frames.append(runtime.frame().copy()); props.append(runtime.proprio().copy())
        # Preserve refill-before-monitor and the same independent natural stream.
        if raw is None or age == active_horizon:
            raw, stats = engine.propose_natural(); age = 0; active_horizon = H
            plans.append(dict(step=t, kind='natural', natural_index=natural_index,
                              H=H, policy_seed=source['policy_seed'], stats=stats))
            natural_index += 1
            if committed_cut is not None:
                commitments[-1]['restored_at'] = t
                commitments[-1]['restore_queue_age'] = 0
                commitments[-1]['restored_H'] = H
                committed_cut = None
        if t >= locked_until and t % 5 == 0 and min(active_horizon-age, 300-t) >= 5:
            started = time.monotonic()
            observed = engine.context(list(frames), list(props), actions[-4:], language, t)
            context_seconds += time.monotonic() - started
            started = time.monotonic()
            monitor = engine.monitor(observed, raw[age:age+5].copy())
            monitor_seconds += time.monotonic() - started
            mature = len(frames) == 5 and len(actions) >= 4
            legal = mature and age > 0 and t+10 <= 300
            true_trigger = bool(legal and monitor['gate'] > .05)
            cap_allows = mode == 'G0-multi' or count < 1
            selected = t == random_cut if mode == 'Random-once' else monitor['gate'] > .05
            trigger = bool(legal and selected and cap_allows)
            event = dict(step=t, queue_age=age, native_H=H, active_horizon=active_horizon,
                         mode=mode, history_mature=mature, legal_cut=bool(legal), gate_threshold=.05,
                         true_G0_trigger=true_trigger, total_cap_allows=cap_allows,
                         trigger_selected=bool(selected), planned_random_cut=random_cut,
                         shadow_G0=mode == 'Random-once', intervention_executed=False,
                         forced_intervention=False, synthetic=False, **monitor)
            if mode == 'Random-once' and t == random_cut:
                random_evaluated = True
                random_reason = 'executed' if trigger else 'scheduled_cut_ineligible'
            if trigger:
                seed = seed_for('D24_designated_a0', source['source_id'], source['policy_seed'],
                                t, namespace=engine.namespace)
                raw, stats = engine.intervene(method, observed, seed, t)
                count += 1; cuts.append(t)
                if first_cut is None:
                    first_cut = t
                age = 0; active_horizon = 10; locked_until = t+10; committed_cut = t
                commitments.append(dict(cut=t, commit_until=t+10, committed_steps=None,
                                        old_tail_discarded=True, restored_at=None, restored_H=None))
                event.update(intervention_executed=True, intervention_index=count, seed=seed,
                             commit_until=locked_until, old_tail_discarded=True,
                             restore_native_H=H, generation=stats)
                plans.append(dict(step=t, kind='intervention', seed=seed, H=10, stats=stats))
            events.append(event); emit('monitor', event)
        if mode == 'Random-once' and t == random_cut and not random_evaluated:
            random_evaluated = True
            random_reason = 'scheduled_cut_ineligible'
            event = dict(step=t, mode=mode, planned_random_cut=random_cut,
                         intervention_executed=False, legal_cut=False, queue_age=age,
                         active_horizon=active_horizon, locked_until=locked_until,
                         reason=random_reason, shadow_G0=True, synthetic=False)
            events.append(event); emit('monitor', event)
        action = raw[age].copy(); age += 1; step = runtime.step(action, t)
        actions.append(np.asarray(action, np.float32)); rewards.append(float(step['reward']))
        success_flags.append(bool(step['success']))
        emit('step', dict(step=t+1, success=bool(step['success']), interventions=count))
        if step['success'] or step['done'] or t == 299:
            if mode == 'Random-once' and not random_evaluated:
                random_reason = 'terminal_before_scheduled_decision'
            for commitment in commitments:
                commitment['committed_steps'] = min(10, t+1-commitment['cut'])
            reason = None if count else (random_reason if mode == 'Random-once'
                                        else 'no_legal_G0_above_threshold')
            return dict(status='complete', success=bool(step['success']), steps=t+1, mode=mode,
                        interventions=count, first_cut=first_cut, last_cut=cuts[-1] if cuts else None,
                        intervention_cuts=cuts, commitments=commitments,
                        planned_random_cut=random_cut, random_schedule_evaluated=random_evaluated,
                        random_schedule_outcome=random_reason, no_intervention_reason=reason,
                        G0_is_shadow=mode == 'Random-once', events=events, plans=plans,
                        context_seconds=context_seconds, monitor_seconds=monitor_seconds,
                        elapsed_control_seconds=time.monotonic()-begin,
                        terminal_reason='success' if step['success'] else 'environment_done' if step['done'] else 's300',
                        arrays=dict(actions=np.asarray(actions, np.float32), rewards=np.asarray(rewards),
                                    success_flags=np.asarray(success_flags)),
                        sampling_calls=sum(x['stats']['policy_calls'] for x in plans),
                        flow_calls=sum(x['stats']['policy_calls'] for x in plans)*10)
    raise RuntimeError('unreachable terminal')
