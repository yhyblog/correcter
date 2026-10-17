"""Frozen pi05 features and MW D/G0/Q, isolated from each base's runtime."""
import argparse
from multiprocessing.connection import Listener
from pathlib import Path
import time
import traceback
import paths
import d24_common as d


def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    out = Path(cfg['output'])/'corrector'
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    import numpy as np
    import torch
    from numeric_setup import initialize
    from numeric_engine import Engine
    from episode_runtime import Counts
    from corrector.guidance import FrozenObjective
    from experiments.standalone_ablation_20260918.candidates import project_solo
    torch.set_num_threads(4)
    state = initialize(d.load(cfg['base_config']), out, Counts(), 'cuda:0')
    engine = Engine(state, d.load(cfg['engine_config']), out)
    # No pi05 policy sampling here. The external base supplies every action.
    context, language, source_id, context_step, counts_before = None, None, None, None, None
    objective, gradient_calls = None, 0
    listener = Listener(cfg['socket_path'], family='AF_UNIX', authkey=bytes.fromhex(cfg['ipc_auth']))
    d.atomic(out/'READY.json', dict(at_utc=d.utc(), status='ready', process=d.identity(),
        load_seconds=time.monotonic()-started, frozen_feature_policy='pi05_MT50_SFT030000',
        model_sampling=False, transfer='frozen five-task D/G0/Q applied to other MW base commands'))
    try:
        with listener.accept() as connection:
            while True:
                request = connection.recv()
                d.authorize()
                begin = time.monotonic()
                try:
                    kind = request['kind']
                    if kind == 'close':
                        connection.send(dict(ok=True))
                        break
                    if kind == 'episode':
                        source_id = request['source_id']
                        engine.instruction = request['instruction']
                        engine.features._instruction = request['instruction']
                        engine.episode_out = Path(request['episode_output'])
                        context, context_step, objective = None, None, None
                        counts_before = dict(engine.counts)
                        language = engine.language()
                        result = dict(source_id=source_id)
                    elif kind == 'monitor':
                        if request['source_id'] != source_id or language is None:
                            raise ValueError('Context crossed episode boundary')
                        frames = [np.frombuffer(row['data'], dtype=np.uint8).reshape(row['shape'])
                                  for row in request['frames']]
                        if not 1 <= len(frames) <= 5 or any(f.ndim != 3 or f.shape[-1] != 3 or not f.any() for f in frames):
                            raise ValueError('Invalid actual RGB observation')
                        context_step = int(request['step'])
                        context = engine.context(frames, np.asarray(request['props'], np.float32),
                            np.asarray(request['past_actions'], np.float32), language, context_step)
                        next_five = np.asarray(request['next_five'], np.float32)
                        if next_five.shape != (5,4) or not np.isfinite(next_five).all():
                            raise ValueError('Invalid base five-command window')
                        result = engine.monitor(context, next_five)
                    elif kind == 'velocity_begin':
                        if request['source_id'] != source_id or request['step'] != context_step or context is None:
                            raise ValueError('Correction lacks current causal context')
                        raw = np.asarray(request['raw_plan'], np.float32)
                        if raw.shape != (cfg['H'],4) or not np.isfinite(raw).all():
                            raise ValueError('Invalid native anchor')
                        padded = np.empty((50,4), np.float32)
                        padded[:len(raw)] = raw
                        padded[len(raw):] = raw[-1]
                        base = np.clip(padded, -1, 1).astype(np.float32)
                        observed = {k:v[0].detach().cpu().numpy() for k,v in context.items()}
                        objective = FrozenObjective(observed, base, selector=engine.selector)
                        gradient_calls = 0
                        result = dict(anchor_fixed=True)
                    elif kind == 'velocity_gradient':
                        if request['source_id'] != source_id or request['step'] != context_step or objective is None:
                            raise ValueError('Gradient crossed intervention context')
                        commands = np.asarray(request['commands'], np.float32)
                        gradient, stats = objective.gradient(commands)
                        gradient_calls += 1
                        if gradient_calls > 3:
                            raise ValueError('More than three Velocity updates')
                        engine.counts['action_gradients'] += 1
                        engine.counts['Q_ensemble_forward'] += 1
                        result = dict(gradient=gradient.numpy().tolist(), value=stats['value'])
                    elif kind == 'velocity_project':
                        if request['source_id'] != source_id or request['step'] != context_step or gradient_calls != 3:
                            raise ValueError('Incomplete Velocity native guidance')
                        native = np.asarray(request['guided_plan'], np.float32)
                        if native.shape != raw.shape or not np.isfinite(native).all():
                            raise ValueError('Invalid guided native chunk')
                        direction = np.clip(native[:10],-1,1).astype(float)-base[:10].astype(float)
                        plan, matching, arrays = project_solo(padded, direction, engine.cfg['matching'])
                        objective.verify(check_hashes=False)
                        if not np.array_equal(plan[10:len(raw)], raw[10:]):
                            raise ValueError('Velocity projector changed unexecuted tail')
                        engine.counts['interventions'] += 1
                        np.savez_compressed(engine.episode_out/('velocity_%03d.npz'%context_step),
                            raw_base=raw, native_guided=native, corrected=plan[:len(raw)],
                            direction=direction, actual_delta=arrays['actual_delta'])
                        result = dict(raw_plan=plan[:len(raw)].tolist(), matching=matching,
                            objective=objective.stats(), Q_acceptance_gate=False,
                            metric='native base inverse-normalization and true-clamp Jacobian',
                            other_direction_calls=0, own_radius_only=True)
                        objective = None
                    elif kind == 'verify':
                        engine.verify()
                        if engine.counts['sampling'] or engine.counts['flow']:
                            raise ValueError('External feature server sampled pi05 actions')
                        result = dict(counters={k:v-counts_before.get(k,0) for k,v in engine.counts.items()})
                    else:
                        raise ValueError('Unknown correction request')
                    connection.send(dict(ok=True, seconds=time.monotonic()-begin, **result))
                except BaseException as exc:
                    connection.send(dict(ok=False, error=repr(exc), traceback=traceback.format_exc()))
                    raise
    finally:
        listener.close()
        engine.hook.close()
        d.atomic(out/'TERMINAL.json', dict(at_utc=d.utc(), counts=engine.counts,
            elapsed_seconds=time.monotonic()-started, process=d.identity()))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    main(p.parse_args().config)
