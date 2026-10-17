"""Same native H10/C10 replan; G0 versus a strictly retrospective D5 alarm."""
from collections import deque
import math
import time
import numpy as np
from b10_adapters import CausalD5Monitor, legal_e6_cut
from experiments.native10_training_20260916.protocol import seed_for


def run_episode(runtime, engine, source, method, H, emit, stop=lambda: False):
    if method not in ('DEV', 'G0', 'D5') or H != 10:
        raise ValueError('E6 supports frozen H10 DEV/G0/D5 only')
    threshold = float(engine.cfg['e6_threshold']) if method == 'D5' else math.inf
    if method == 'D5' and not math.isfinite(threshold):
        raise ValueError('D5 test needs a finite frozen development threshold')
    physical_id = source['source_id'] + ':' + method
    monitor = CausalD5Monitor(threshold, engine.feature_scale, physical_id)
    frames, props = deque(maxlen=5), deque(maxlen=5)
    actions, rewards, successes, events, plans, eligible_scores = [], [], [], [], [], []
    raw, age, active_horizon, locked_until = None, 0, H, 0
    first_cut, count, natural_index, compared_windows = None, 0, 0, 0
    g0_any = False
    begin = time.monotonic()
    language = engine.language()
    engine.start_natural_stream(source['policy_seed'])
    for t in range(300):
        if stop() or time.monotonic() - begin > 1800:
            raise RuntimeError('Episode stop/deadline')
        frames.append(runtime.frame().copy())
        props.append(runtime.proprio().copy())
        if raw is None or age == active_horizon:
            raw, stats = engine.propose_natural()
            age, active_horizon = 0, H
            plans.append(dict(step=t, kind='natural', natural_index=natural_index, H=H,
                              policy_seed=source['policy_seed'], stats=stats))
            natural_index += 1
        if t >= locked_until and t % 5 == 0 and min(active_horizon - age, 300 - t) >= 5:
            observed = engine.context(list(frames), list(props), actions[-4:], language, t)
            mature = len(frames) == 5 and len(actions) >= 5
            legal = mature and legal_e6_cut(step=t, plan_age=age,
                                           remaining_queue=active_horizon-age, intervened=count > 0)
            retrospective = None
            if t-5 in monitor.pending:
                retrospective = monitor.observe(
                    issued_step=t-5, observed_step=t,
                    actual_features=engine.actual_features(observed),
                    executed_raw_actions=np.asarray(actions[-5:], dtype=np.float32),
                    episode_id=physical_id, plan_age=age, remaining_queue=active_horizon-age)
                if not math.isfinite(retrospective['score']):
                    raise ValueError('Nonfinite causal D5 score')
                compared_windows += 1
                if retrospective['eligible']:
                    eligible_scores.append(retrospective['score'])
            elif legal:
                raise ValueError('Eligible E6 cut lacks an aligned prior D5 prediction')
            if monitor.pending:
                raise ValueError('Expired or future D5 prediction leaked across monitor boundaries')
            next_five = raw[age:age+5].copy()
            forecast = engine.forecast(observed, next_five)
            g0_trigger = bool(legal and forecast['gate'] > .05)
            g0_any = g0_any or g0_trigger
            chosen = (method == 'G0' and g0_trigger) or (
                method == 'D5' and retrospective is not None and retrospective['triggered'])
            event = dict(step=t, queue_age=age, native_H=H, active_horizon=active_horizon,
                         history_mature=mature, legal_cut=bool(legal), method=method,
                         gate=forecast['gate'], member_benefits=forecast['member_benefits'],
                         gate_threshold=.05, true_G0_trigger=g0_trigger,
                         causal_D5=retrospective, selected_trigger=bool(chosen),
                         intervention_executed=False, forced_intervention=False, synthetic=False)
            if chosen:
                if not legal or count:
                    raise ValueError('Illegal/repeated E6 intervention')
                seed = seed_for('D24_designated_a0', source['source_id'], source['policy_seed'],
                                t, namespace=engine.namespace)
                raw, stats = engine.intervene('R', observed, seed, t)
                count += 1
                monitor.intervened = True
                first_cut, age, active_horizon, locked_until = t, 0, 10, t+10
                # The old predicted action window was replaced. Do not register it:
                # its arrival would be inside the mandatory C10 lock anyway.
                event.update(intervention_executed=True, intervention_index=count, seed=seed,
                             commit_until=locked_until, old_tail_discarded=True, restore_native_H=H,
                             prediction_registered=False, generation=stats)
                plans.append(dict(step=t, kind='intervention', seed=seed, H=10, stats=stats))
            else:
                monitor.register(issued_step=t, predicted_features=forecast['prediction'],
                                 conditioned_raw_actions=next_five)
                event['prediction_registered'] = True
            events.append(event)
            emit('monitor', event)
        action = raw[age].copy()
        age += 1
        step = runtime.step(action, t)
        actions.append(np.asarray(action, dtype=np.float32))
        rewards.append(float(step['reward']))
        successes.append(bool(step['success']))
        emit('step', dict(step=t+1, success=bool(step['success']), interventions=count))
        if step['success'] or step['done'] or t == 299:
            return dict(status='complete', success=bool(step['success']), steps=t+1,
                        interventions=count, first_cut=first_cut, events=events, plans=plans,
                        elapsed_control_seconds=time.monotonic()-begin,
                        terminal_reason='success' if step['success'] else 'environment_done' if step['done'] else 's300',
                        eligible_scores=eligible_scores, g0_intervened=g0_any,
                        compared_windows=compared_windows,
                        causal_D5_action_alignment_verified=True,
                        immature_terminal_predictions=len(monitor.pending),
                        arrays=dict(actions=np.asarray(actions, dtype=np.float32),
                                    rewards=np.asarray(rewards), success_flags=np.asarray(successes)),
                        sampling_calls=sum(x['stats']['policy_calls'] for x in plans),
                        flow_calls=10*sum(x['stats']['policy_calls'] for x in plans))
    raise RuntimeError('Unreachable terminal')
