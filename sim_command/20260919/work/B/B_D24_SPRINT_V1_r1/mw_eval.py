"""Resident Smol baseline, adapted from the existing project evaluator."""
import argparse
import collections
import json
from pathlib import Path
import random
import time
import traceback
import d24_common as d

def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    output = Path(cfg['output'])
    output.mkdir(parents=True, exist_ok=True)
    status = dict(status='loading', job_id=cfg['job_id'], config=str(config_path),
                  checkpoint=cfg['checkpoint'], H=cfg['H'], K=cfg['K'], method='N',
                  planned_episodes=len(cfg['episodes']), completed_episodes=0, technical_failures=0)
    d.atomic(output / 'status.json', status)
    start = time.monotonic()
    rows = []
    try:
        import numpy as np
        import torch
        from lerobot.envs.metaworld import MetaworldEnv
        from lerobot.policies.factory import get_policy_class, make_pre_post_processors
        torch.set_num_threads(4)
        torch.backends.cuda.matmul.allow_tf32 = True
        policy = get_policy_class('smolvla').from_pretrained(Path(cfg['checkpoint']), local_files_only=True, strict=True)
        policy.config.n_action_steps = cfg['K']
        policy.config.num_steps = cfg['NFE']
        assert policy.config.chunk_size == cfg['H']
        assert tuple(policy.config.output_features['action'].shape) == (4,)
        assert tuple(policy.config.input_features['observation.state'].shape) == (4,)
        policy.to('cuda').eval()
        pre, post = make_pre_post_processors(policy.config, pretrained_path=Path(cfg['checkpoint']))
        torch.cuda.synchronize()
        status.update(status='running', load_seconds=time.monotonic() - start)
        d.atomic(output / 'status.json', status)
        groups = collections.OrderedDict()
        for source in cfg['episodes']:
            groups.setdefault(source['task'], []).append(source)
        failure_count = 0
        for task, sources in groups.items():
            d.authorize(admission=True)
            np.random.seed(sources[0]['reset_seed'])
            random.seed(sources[0]['reset_seed'])
            env = MetaworldEnv(task=task, obs_type='pixels_agent_pos')
            try:
                for source in sources:
                    d.episode_claim(output, source)
                    begun = time.monotonic()
                    row = dict(source, method='N', checkpoint=cfg['checkpoint'], H=cfg['H'], K=cfg['K'],
                               status='running', success=None, steps=0, queries=0, inference_seconds=0.0,
                               environment_seconds=0.0, preprocessing_seconds=0.0)
                    try:
                        with d.episode_deadline():
                            np.random.seed(source['reset_seed'])
                            random.seed(source['reset_seed'])
                            env._env.seed(source['reset_seed'])
                            obs, _ = env.reset(seed=source['reset_seed'])
                            initial = np.asarray(env._env._last_rand_vec).tolist()
                            d.exclusive(output / 'sources' / (source['source_id'] + '.json'),
                                        dict(source, initial_randomization_vector=initial))
                            policy.reset()
                            torch.manual_seed(source['policy_seed'])
                            row['initial_randomization_vector'] = initial
                            success = False
                            terminated = truncated = False
                            for step in range(cfg['max_steps']):
                                d.authorize()
                                t = time.monotonic()
                                sample = {'observation.image': torch.from_numpy(np.ascontiguousarray(obs['pixels'])).permute(2, 0, 1).float() / 255,
                                          'observation.state': torch.as_tensor(obs['agent_pos'], dtype=torch.float32), 'task': env.task_description}
                                row['preprocessing_seconds'] += time.monotonic() - t
                                if step % cfg['K'] == 0:
                                    row['queries'] += 1
                                t = time.monotonic()
                                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                                    action = post(policy.select_action(pre(sample))).reshape(-1).cpu().float().numpy()
                                row['inference_seconds'] += time.monotonic() - t
                                if action.shape != (4,) or not np.isfinite(action).all():
                                    raise RuntimeError('Invalid physical MetaWorld action')
                                t = time.monotonic()
                                obs, _, terminated, truncated, info = env.step(action)
                                row['environment_seconds'] += time.monotonic() - t
                                row['steps'] = step + 1
                                success = success or bool(info.get('success', info.get('is_success', False)))
                                if success or terminated or truncated:
                                    break
                            row.update(status='complete', success=success, terminated=bool(terminated), truncated=bool(truncated),
                                       terminal_reason='success' if success else 'environment_terminal' if terminated or truncated else 'step_cap')
                    except Exception as exc:
                        failure_count += 1
                        row.update(status='technical_failure', success=None, error=repr(exc))
                        traceback.print_exc()
                    row['elapsed_seconds'] = time.monotonic() - begun
                    row['at_utc'] = d.utc()
                    d.append(output / 'episodes.jsonl', row)
                    rows.append(row)
                    status.update(completed_episodes=sum(r['status'] == 'complete' for r in rows),
                                  technical_failures=failure_count, latest_source=source['source_id'], at_utc=d.utc())
                    d.atomic(output / 'status.json', status)
                    print(json.dumps(row), flush=True)
                    if failure_count >= 3:
                        raise RuntimeError('Three technical episode failures; pause this shard for diagnosis')
            finally:
                env.close()
        status['status'] = 'complete' if not failure_count else 'partial'
    except BaseException as exc:
        status.update(status='failed', error=repr(exc))
        raise
    finally:
        status.update(elapsed_seconds=time.monotonic() - start, at_utc=d.utc())
        d.atomic(output / 'status.json', status)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    main(p.parse_args().config)
