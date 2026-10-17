"""Four-suite N evaluation; fresh frozen reset seeds, action7/state8/K5."""
import argparse
import collections
import json
from pathlib import Path
import random
import sys
import time
import traceback
import d24_common as d

def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    output = Path(cfg['output'])
    status = dict(status='initializing_simulator', job_id=cfg['job_id'], checkpoint=cfg['checkpoint'], suite=cfg['suite'],
                  H=10, K=5, method='N', source_policy=cfg['initial_source_policy'], planned_episodes=len(cfg['episodes']),
                  completed_episodes=0, technical_failures=0)
    d.atomic(output / 'status.json', status)
    start = time.monotonic()
    rows = []
    try:
        import numpy as np
        from libero.libero import benchmark
        from openpi_client import image_tools
        from openpi_client.websocket_client_policy import WebsocketClientPolicy
        sys.path.insert(0, str(d.ROOT / 'embodied-ai-workspace/projects/upstream/openpi-215abfb'))
        from examples.libero.main import _get_libero_env, _quat2axisangle, LIBERO_DUMMY_ACTION
        suite = benchmark.get_benchmark_dict()[cfg['suite']]()
        assert suite.n_tasks == 10
        client = WebsocketClientPolicy('127.0.0.1', cfg['port'])
        meta = client.get_server_metadata()
        assert meta['checkpoint'] == cfg['checkpoint'] and meta['H'] == 10 and meta['NFE'] == 10
        status.update(server=meta, status='running')
        d.atomic(output / 'status.json', status)
        groups = collections.OrderedDict()
        for source in cfg['episodes']:
            groups.setdefault(source['task_id'], []).append(source)
        failures = 0
        for task_id, sources in groups.items():
            d.authorize(admission=True)
            task = suite.get_task(task_id)
            np.random.seed(sources[0]['reset_seed'])
            random.seed(sources[0]['reset_seed'])
            env, instruction = _get_libero_env(task, 256, sources[0]['reset_seed'])
            try:
                for source in sources:
                    d.episode_claim(output, source)
                    begun = time.monotonic()
                    row = dict(source, task=instruction, suite=cfg['suite'], method='N', checkpoint=cfg['checkpoint'],
                               H=10, K=5, status='running', success=None, steps=0, queries=0,
                               inference_seconds=0.0, environment_seconds=0.0, preprocessing_seconds=0.0)
                    try:
                        with d.episode_deadline():
                            np.random.seed(source['reset_seed'])
                            random.seed(source['reset_seed'])
                            env.seed(source['reset_seed'])
                            obs = env.reset()
                            initial = np.asarray(env.get_sim_state())
                            d.exclusive(output / 'sources' / (source['source_id'] + '.json'),
                                        dict(source, task=instruction, initial_sim_state=initial.tolist(),
                                             source_policy=cfg['initial_source_policy']))
                            for _ in range(cfg['settle_steps']):
                                obs, _, _, _ = env.step(LIBERO_DUMMY_ACTION)
                            pending = collections.deque()
                            done = False
                            for step in range(cfg['max_steps']):
                                d.authorize()
                                if not pending:
                                    t = time.monotonic()
                                    img, wrist = [image_tools.convert_to_uint8(image_tools.resize_with_pad(
                                        np.ascontiguousarray(obs[key][::-1, ::-1]), 224, 224))
                                        for key in ('agentview_image', 'robot0_eye_in_hand_image')]
                                    request = {'observation/image': img, 'observation/wrist_image': wrist,
                                               'observation/state': np.concatenate((obs['robot0_eef_pos'],
                                                   _quat2axisangle(obs['robot0_eef_quat'].copy()), obs['robot0_gripper_qpos'])),
                                               'prompt': str(instruction)}
                                    if request['observation/state'].shape != (8,):
                                        raise RuntimeError('LIBERO state must have eight coordinates')
                                    if row['queries'] == 0:
                                        request['d24_policy_seed'] = source['policy_seed']
                                    row['preprocessing_seconds'] += time.monotonic() - t
                                    row['queries'] += 1
                                    t = time.monotonic()
                                    actions = np.asarray(client.infer(request)['actions'])
                                    row['inference_seconds'] += time.monotonic() - t
                                    if actions.shape != (10, 7) or not np.isfinite(actions).all():
                                        raise RuntimeError('LIBERO physical action chunk must be finite 10x7')
                                    pending.extend(actions[:5])
                                t = time.monotonic()
                                obs, _, done, _ = env.step(pending.popleft().tolist())
                                row['environment_seconds'] += time.monotonic() - t
                                row['steps'] = step + 1
                                if done:
                                    break
                            row.update(status='complete', success=bool(done), terminal_reason='success' if done else 'step_cap')
                    except Exception as exc:
                        failures += 1
                        row.update(status='technical_failure', success=None, error=repr(exc))
                        traceback.print_exc()
                    row.update(elapsed_seconds=time.monotonic() - begun, at_utc=d.utc())
                    d.append(output / 'episodes.jsonl', row)
                    rows.append(row)
                    status.update(completed_episodes=sum(r['status'] == 'complete' for r in rows),
                                  technical_failures=failures, latest_source=source['source_id'], at_utc=d.utc())
                    d.atomic(output / 'status.json', status)
                    print(json.dumps(row), flush=True)
                    if failures >= 3:
                        raise RuntimeError('Three technical failures; pause suite for diagnosis')
            finally:
                env.close()
        status['status'] = 'complete' if not failures else 'partial'
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
