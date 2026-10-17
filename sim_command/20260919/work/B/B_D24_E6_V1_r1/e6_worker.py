"""Eight resident workers: development traces, frozen threshold, paired test."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import signal
import time
import traceback
import paths
import d24_common as d


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wait_for(paths_to_wait, phase, shared, boundary, timeout=7200):
    deadline = time.monotonic() + timeout
    while not all(p.exists() for p in paths_to_wait):
        if boundary():
            raise RuntimeError('Worker stopped while waiting for '+phase)
        failures = sorted(shared.glob('FAILURE_*.json'))
        if failures:
            raise RuntimeError('Another worker failed; no partial-development calibration: '+str(failures[0]))
        if time.monotonic() >= deadline:
            raise TimeoutError('Bounded phase wait expired: '+phase)
        time.sleep(2)


def freeze_threshold(cfg, engine, shared):
    from calibrate_e6 import calibrate
    sources = d.load(cfg['source_table'])
    expected = {row['parent_episode_id'] for row in sources['development']}
    episodes, refs = [], []
    for jid in cfg['all_jobs']:
        mark = d.load(shared/('DEV_DONE_'+jid+'.json'))
        trace = Path(mark['trace_path'])
        if digest(trace) != mark['trace_sha256'] or mark['D_identity'] != cfg['DG0_identity']:
            raise ValueError('Development identity changed')
        episodes.extend(d.load(trace))
        refs.append(mark)
    actual = [row['parent_episode_id'] for row in episodes]
    if len(actual) != 100 or len(set(actual)) != 100 or set(actual) != expected:
        raise ValueError('All 100 development parents including no alarms are required')
    allowed = {'parent_episode_id', 'source_id', 'split', 'eligible_scores', 'g0_intervened',
               'causal_D5_action_alignment_verified', 'compared_windows'}
    if any(set(row) != allowed for row in episodes):
        raise ValueError('Threshold inputs must be trace-only; outcome labels are excluded')
    episodes.sort(key=lambda row: row['parent_episode_id'])
    trace_path = shared/'DEVELOPMENT_TRACES.json'
    d.exclusive(trace_path, episodes)
    manifest = shared/'DEVELOPMENT_MANIFEST.json'
    d.exclusive(manifest, dict(synthetic=False, split='development',
        episodes=dict(path=str(trace_path), sha256=digest(trace_path)),
        frozen_D_identity=cfg['DG0_identity'], downstream='R', horizon=5,
        source_table_sha256=cfg['source_table_sha256'], worker_traces=refs,
        note='Old independent dev100; N execution with shadow G0 and causal D5 scores; no success labels'))
    threshold_path = shared/'THRESHOLD.json'
    result = calibrate(manifest, threshold_path)
    if result['development_episodes'] != 100 or result['selection_uses_success']:
        raise ValueError('Invalid development-only threshold publication')
    d.exclusive(shared/'THRESHOLD_READY.json', dict(at_utc=d.utc(), threshold_path=str(threshold_path),
        threshold_sha256=digest(threshold_path), manifest_path=str(manifest),
        source_table_sha256=cfg['source_table_sha256'], test_admitted_before_freeze=False))


def publish_test_summary(cfg, shared):
    rows = []
    for jid in cfg['all_jobs']:
        marker = d.load(shared/('TEST_DONE_'+jid+'.json'))
        p = Path(marker['rows_path'])
        if digest(p) != marker['rows_sha256']:
            raise ValueError('Completed test rows changed')
        rows.extend(d.load(p))
    expected = {(method, source['source_id']) for method in ('G0', 'D5')
                for source in d.load(cfg['source_table'])['test']}
    actual = [(row['method'], row['source_id']) for row in rows]
    if len(actual) != 100 or len(set(actual)) != 100 or set(actual) != expected:
        raise ValueError('Incomplete or duplicate paired E6 matrix')
    if any(row['status'] != 'complete' or row['success'] not in (True, False) for row in rows):
        raise ValueError('Technical failures cannot be scientific failures')
    cells = []
    for task in sorted({row['task'] for row in rows}):
        for method in ('G0', 'D5'):
            selected = [row for row in rows if row['task'] == task and row['method'] == method]
            cells.append(dict(task=task, method=method, n=len(selected),
                successes=sum(row['success'] is True for row in selected),
                interventions=sum(row['interventions'] for row in selected)))
    paired = collections.defaultdict(dict)
    for row in rows:
        paired[row['source_id']][row['method']] = row['success']
    counts = collections.Counter(('both_success' if v['G0'] and v['D5'] else
        'G0_only' if v['G0'] else 'D5_only' if v['D5'] else 'both_failure') for v in paired.values())
    summary = dict(status='complete', run_id=cfg['run_id'], at_utc=d.utc(),
        development_episodes=100, test_episodes=100, paired_test_sources=50,
        source_table_sha256=cfg['source_table_sha256'],
        threshold=d.load(shared/'THRESHOLD.json'), per_task=cells, paired_outcomes=dict(counts),
        successes={method:sum(row['success'] is True for row in rows if row['method'] == method) for method in ('G0','D5')},
        scientific_retries=0, technical_failures=0, optimizer_updates=0,
        renderer='B Mesa llvmpipe with corrected GL resource lifetime',
        protocol='H10 C10 once; 30Hz/400Hz/action_scale .015; same frozen pi05/D/G0; old dev threshold then new test',
        comparisons='Both arms run on B; do not merge with A NVIDIA-EGL runs as identical renderer outcomes',
        holder_policy='All holder computation disabled until whole formal wave drains')
    out = Path(cfg['batch_output'])
    d.exclusive(out/'E6_COMPLETE_SUMMARY.json', summary)
    d.exclusive(out/'E6_VALID_EPISODES.json', rows)
    with (out/'E6_COMPLETE_CELLS.csv').open('x') as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=['task','method','n','successes','interventions'])
        writer.writeheader()
        writer.writerows(cells)
    with (out/'E6_COMPLETE_SUMMARY.md').open('x') as f:
        f.write('# E6 causal D5 versus G0, both followed by R\n\n')
        f.write('All 100 old independent development parents calibrated the fixed threshold before any test entry. '
                'Each method used the same 50 new sources (10 per historical task), with no test-guided selection.\n\n')
        f.write('| Method | Successes | Episodes |\n|---|---:|---:|\n')
        for method in ('G0','D5'):
            f.write('| %s | %d | 50 |\n' % (method, summary['successes'][method]))
        f.write('\nB Mesa renderer; same frozen pi05/D/G0, H10/C10/max1, control30Hz/physics400Hz. '
                'Detailed threshold, paired counts, per-task counts and source identities are in the JSON/CSV.\n')


def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    out, shared = Path(cfg['output']), Path(cfg['shared_phase'])
    out.mkdir(parents=True, exist_ok=True)
    shared.mkdir(parents=True, exist_ok=True)
    status = dict(status='loading', job_id=cfg['job_id'], planned_episodes=cfg['planned_episodes'],
                  completed_episodes=0, technical_failures=0, phase='loading')
    d.atomic(out/'status.json', status)
    started, engine, stopping = time.monotonic(), None, False
    def stop(*_):
        nonlocal stopping
        stopping = True
    def boundary():
        d.authorize()
        return stopping
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)
    try:
        if digest(cfg['source_table']) != cfg['source_table_sha256']:
            raise ValueError('Source table changed')
        for ref in cfg['sealed_files']:
            if digest(ref['path']) != ref['sha256']:
                raise ValueError('Prepared implementation/config changed: '+ref['path'])
        import numpy as np
        import torch
        from numeric_setup import initialize
        from numeric_engine import Engine
        from episode_runtime import Counts, execute_episode
        from renderer_cleanup import install
        install()
        from lerobot.envs.metaworld import MetaworldEnv
        torch.set_num_threads(4)
        base = d.load(cfg['base_config'])
        checkpoint = Path(base['checkpoint'])
        if digest(checkpoint/'config.json') != cfg['checkpoint_config_sha256'] or (
                checkpoint/'model.safetensors').stat().st_size != cfg['checkpoint_weight_bytes']:
            raise ValueError('Frozen pi05 checkpoint identity changed')
        state = initialize(base, out, Counts(), 'cuda:0')
        engine = Engine(state, d.load(cfg['engine_config']), out)
        if d.load(out/'AUXILIARY_IDENTITY.json')['DG0'] != cfg['DG0_identity']:
            raise ValueError('Frozen D/G0 changed')
        status.update(status='running', load_seconds=time.monotonic()-started, model_resident=True)

        def run_sources(sources, methods, phase):
            status['phase'] = phase
            d.atomic(out/'status.json', status)
            grouped, rows = collections.OrderedDict(), []
            for source in sources:
                grouped.setdefault(source['task'], []).append(source)
            for task, group in grouped.items():
                d.authorize(admission=True)
                env = None
                try:
                    import random
                    random.seed(group[0]['env_seed'])
                    np.random.seed(group[0]['env_seed'])
                    env = MetaworldEnv(task=task, camera_name='corner2', obs_type='pixels_agent_pos',
                        render_mode='rgb_array', observation_width=480, observation_height=480, max_path_length=300)
                    if float(env._env.model.opt.timestep) != 1/400:
                        raise ValueError('Unexpected physics timestep')
                    for source in group:
                        for method in methods:
                            d.authorize(admission=True)
                            if stopping:
                                raise RuntimeError('Worker stopped before episode')
                            dest = out/phase/method
                            d.episode_claim(dest, source)
                            ep = dest/'episodes'/source['source_id']
                            ep.mkdir(parents=True, exist_ok=False)
                            with d.episode_deadline():
                                row = execute_episode(state, engine, env, source, 10, method, ep, boundary)
                            compact = {k:v for k,v in row.items() if k not in ('events','plans')}
                            compact.update(result_path=str(ep/'RESULT.json'), phase=phase,
                                parent_episode_id=source.get('parent_episode_id', source['source_id']))
                            d.append(out/'episodes.jsonl', compact)
                            rows.append(compact)
                            status['completed_episodes'] += int(row['status'] == 'complete')
                            status['technical_failures'] += int(row['status'] != 'complete')
                            status.update(latest_source=source['source_id'], method=method, at_utc=d.utc())
                            d.atomic(out/'status.json', status)
                            if row['status'] != 'complete':
                                raise RuntimeError('Recorded technical episode failure; no automatic retry')
                finally:
                    if env is not None:
                        env.close()
            return rows

        dev_rows = run_sources(cfg['development_sources'], ['DEV'], 'development')
        keys = ('parent_episode_id','source_id','split','eligible_scores','g0_intervened',
                'causal_D5_action_alignment_verified','compared_windows')
        trace_path = out/'DEVELOPMENT_TRACE_ONLY.json'
        d.exclusive(trace_path, [{k:row[k] for k in keys} for row in dev_rows])
        d.exclusive(shared/('DEV_DONE_'+cfg['job_id']+'.json'), dict(at_utc=d.utc(),
            trace_path=str(trace_path), trace_sha256=digest(trace_path), D_identity=cfg['DG0_identity']))
        status.update(phase='threshold_barrier')
        d.atomic(out/'status.json', status)
        if cfg['worker_index'] == 0:
            wait_for([shared/('DEV_DONE_'+jid+'.json') for jid in cfg['all_jobs']], 'development', shared, boundary)
            freeze_threshold(cfg, engine, shared)
        wait_for([shared/'THRESHOLD_READY.json'], 'frozen threshold', shared, boundary)
        ready = d.load(shared/'THRESHOLD_READY.json')
        if digest(ready['threshold_path']) != ready['threshold_sha256']:
            raise ValueError('Frozen threshold changed')
        threshold = d.load(ready['threshold_path'])
        if threshold['D_identity'] != cfg['DG0_identity'] or threshold['selection_uses_success']:
            raise ValueError('Threshold/D identity or selection violation')
        engine.cfg['e6_threshold'] = threshold['threshold']
        d.exclusive(out/'TEST_ENTRY.json', dict(at_utc=d.utc(), threshold=ready,
            source_table_sha256=cfg['source_table_sha256'], test_sources=len(cfg['test_sources'])))
        test_rows = run_sources(cfg['test_sources'], ['G0','D5'], 'test')
        if engine.counts['Q_ensemble_forward'] or engine.counts['action_gradients']:
            raise ValueError('E6 downstream R must not use Q/action gradients')
        p = out/'TEST_ROWS.json'
        d.exclusive(p, test_rows)
        d.exclusive(shared/('TEST_DONE_'+cfg['job_id']+'.json'), dict(at_utc=d.utc(),
            rows_path=str(p), rows_sha256=digest(p)))
        if cfg['worker_index'] == 0:
            status['phase'] = 'summary_barrier'
            d.atomic(out/'status.json', status)
            wait_for([shared/('TEST_DONE_'+jid+'.json') for jid in cfg['all_jobs']], 'test summary', shared, boundary)
            publish_test_summary(cfg, shared)
        status.update(status='complete', phase='complete')
    except BaseException as exc:
        status.update(status='failed', error=repr(exc), traceback=traceback.format_exc())
        d.atomic(shared/('FAILURE_'+cfg['job_id']+'.json'), dict(status, at_utc=d.utc()))
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
