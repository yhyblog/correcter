"""Eight resident workers evaluate the fixed E1 loss-by-operator matrix."""
import argparse
import collections
import hashlib
import signal
import sys
import time
import traceback
from pathlib import Path
import paths
import d24_common as d


def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    out = Path(cfg['output'])
    out.mkdir(parents=True, exist_ok=True)
    status = dict(status='loading', job_id=cfg['job_id'], planned_episodes=cfg['planned_episodes'],
                  completed_episodes=0, technical_failures=0, completed_cells=0)
    d.atomic(out/'status.json', status)
    engine = None
    stopping = False
    started = time.monotonic()
    def stop(*_):
        nonlocal stopping
        stopping = True
    def boundary():
        d.authorize()
        return stopping
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)
    try:
        import numpy as np
        import torch
        from numeric_setup import initialize
        from numeric_engine import Engine
        from corrector.critic import FrozenSelector
        from episode_runtime import Counts, execute_episode
        from renderer_cleanup import install
        install()
        from lerobot.envs.metaworld import MetaworldEnv
        torch.set_num_threads(4)
        base = d.load(cfg['base_config'])
        checkpoint = Path(base['checkpoint'])
        if hashlib.sha256((checkpoint/'config.json').read_bytes()).hexdigest() != cfg['checkpoint_config_sha256']:
            raise ValueError('pi05 checkpoint config identity changed')
        if (checkpoint/'model.safetensors').stat().st_size != cfg['checkpoint_weight_bytes']:
            raise ValueError('pi05 checkpoint weight size changed')
        state = initialize(base, out, Counts(), 'cuda:0')
        first = d.load(cfg['cells'][0]['config'])
        engine = Engine(state, first, out)
        status.update(status='running', load_seconds=time.monotonic()-started, model_resident=True)
        d.atomic(out/'status.json', status)
        for cell in cfg['cells']:
            d.authorize(admission=True)
            if stopping:
                raise RuntimeError('Worker stopped before next cell')
            cell_cfg = d.load(cell['config'])
            dest = out/'cells'/cell['cell_id']
            dest.mkdir(parents=True, exist_ok=False)
            engine.selector = FrozenSelector(cell_cfg['critic_assets'])
            if engine.selector.ranking['model_hashes'] != cell_cfg['selected_model']['member_hashes']:
                raise ValueError('Frozen E1 ensemble identity changed')
            engine.cfg = cell_cfg
            d.exclusive(dest/'CELL_IDENTITY.json', cell_cfg)
            grouped = collections.OrderedDict()
            for source in cell_cfg['sources']:
                grouped.setdefault(source['task'], []).append(source)
            rows = []
            for task, sources in grouped.items():
                d.authorize(admission=True)
                env = None
                try:
                    import random
                    random.seed(sources[0]['env_seed'])
                    np.random.seed(sources[0]['env_seed'])
                    env = MetaworldEnv(task=task, camera_name='corner2', obs_type='pixels_agent_pos',
                        render_mode='rgb_array', observation_width=480, observation_height=480,
                        max_path_length=300)
                    if float(env._env.model.opt.timestep) != 1/400:
                        raise ValueError('Unexpected physics timestep')
                    for source in sources:
                        d.authorize(admission=True)
                        if stopping:
                            raise RuntimeError('Worker stopped before episode')
                        d.episode_claim(dest, source)
                        ep = dest/'episodes'/source['source_id']
                        ep.mkdir(parents=True, exist_ok=False)
                        with d.episode_deadline():
                            row = execute_episode(state, engine, env, source, 10, cell_cfg['method'], ep, boundary)
                        row.update(cell_id=cell['cell_id'], loss=cell_cfg['loss'],
                                   complete_training_seed=cell_cfg['complete_training_seed'],
                                   renderer='Mesa llvmpipe; corrected GL resource lifetime', result_path=str(ep/'RESULT.json'),
                                   repair_of=cell_cfg['repair_of'][source['source_id']])
                        compact = {k:v for k,v in row.items() if k not in ('events','plans')}
                        d.append(out/'episodes.jsonl', compact)
                        rows.append(compact)
                        status['completed_episodes'] += int(row['status']=='complete')
                        status['technical_failures'] += int(row['status']!='complete')
                        status.update(cell_id=cell['cell_id'], latest_source=source['source_id'], at_utc=d.utc())
                        d.atomic(out/'status.json', status)
                        if row['status'] != 'complete':
                            raise RuntimeError('Recorded technical episode failure; no automatic retry')
                finally:
                    if env is not None:
                        env.close()
            d.exclusive(dest/'RESULT.json', dict(status='complete', cell_id=cell['cell_id'],
                episodes=len(rows), successes=sum(r['success'] is True for r in rows), at_utc=d.utc()))
            status['completed_cells'] += 1
        status['status'] = 'complete'
    except BaseException as exc:
        status.update(status='failed', error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        if engine is not None:
            engine.hook.close()
        status.update(at_utc=d.utc(), elapsed_seconds=time.monotonic()-started)
        d.atomic(out/'status.json', status)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    main(parser.parse_args().config)
