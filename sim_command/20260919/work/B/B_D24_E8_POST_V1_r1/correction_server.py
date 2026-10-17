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
                        context, context_step = None, None
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
                    elif kind == 'post':
                        if request['source_id'] != source_id or request['step'] != context_step or context is None:
                            raise ValueError('Correction lacks current observed context')
                        raw = np.asarray(request['raw_plan'], np.float32)
                        if raw.shape != (cfg['H'],4) or cfg['H'] not in (30,50) or not np.isfinite(raw).all():
                            raise ValueError('Unexpected native physical action chunk')
                        # Q/projector use only first10. Inert padding accommodates the
                        # existing raw50 projector; it never reaches X's output/queue.
                        padded = np.empty((50,4), np.float32)
                        padded[:len(raw)] = raw
                        padded[len(raw):] = raw[-1]
                        base = np.clip(padded,-1,1).astype(np.float32)
                        observed = {k:v[0].detach().cpu().numpy() for k,v in context.items()}
                        objective = FrozenObjective(observed, base, selector=engine.selector)
                        gradient, grad_stats = objective.gradient()
                        slopes = ((engine.transform.q99-engine.transform.q01)/2).detach().cpu().numpy()
                        direction = gradient.numpy()*slopes[None]**2
                        plan, matching, arrays = project_solo(padded, direction, engine.cfg['matching'])
                        objective.verify(check_hashes=False)
                        stats = objective.stats()
                        engine.counts['action_gradients'] += stats['objective_backward_calls']
                        engine.counts['Q_ensemble_forward'] += stats['objective_forward_calls']
                        engine.counts['interventions'] += 1
                        if not np.array_equal(plan[10:len(raw)],raw[10:]):
                            raise ValueError('Post altered the unexecuted native tail')
                        np.savez_compressed(engine.episode_out/('post_%03d.npz'%context_step),
                            raw_base=raw, corrected=plan[:len(raw)], direction=direction,
                            actual_delta=arrays['actual_delta'])
                        result = dict(raw_plan=plan[:len(raw)].tolist(), matching=matching,
                            gradient=grad_stats, objective=stats, Q_acceptance_gate=False,
                            metric='frozen pi05 clean-coordinate metric S**2 times command gradient',
                            downstream='Post on fresh external-base plan; first10 commands only')
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
