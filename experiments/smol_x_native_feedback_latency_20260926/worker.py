"""Native Smol/X baseline and same-device full-feedback timing; no training."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import threading
import time
import traceback


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2))
    tmp.replace(path)


def append(path, row):
    with Path(path).open('a') as stream:
        stream.write(json.dumps(row) + '\n')


def latency(model, ctx, case, seed, pool, gpu):
    origin = time.perf_counter()
    spans = {}
    def call(name, fn, barrier=None):
        if barrier is not None:
            barrier.wait()
        start = time.perf_counter()
        value = fn()
        end = time.perf_counter()
        spans[name] = dict(start=start-origin, end=end-origin, seconds=end-start)
        return value
    feedback = None
    if case == 'N':
        pool.submit(call, 'policy', lambda: model.plan(ctx, seed)).result()
    elif case == 'monitor':
        feedback = pool.submit(call, 'feedback', lambda: model.monitor(ctx)).result()
    else:
        barrier = threading.Barrier(3)
        planned = pool.submit(call, 'policy', lambda: model.plan(ctx, seed), barrier)
        monitored = pool.submit(call, 'feedback', lambda: model.monitor(ctx), barrier)
        barrier.wait()
        planned.result()
        feedback = monitored.result()
    wall = time.perf_counter() - origin
    policy, monitor = spans.get('policy', {}), spans.get('feedback', {})
    return dict(case=case, gpu_index=gpu, wall_seconds=wall,
        policy_seconds=policy.get('seconds'), feedback_seconds=monitor.get('seconds'),
        policy_start_s=policy.get('start'), policy_end_s=policy.get('end'),
        feedback_start_s=monitor.get('start'), feedback_end_s=monitor.get('end'),
        gate=feedback['gate'] if feedback is not None else None,
        gate_is_untrained=True, Q_included=False)


def frequency(model, ctx, mode, duration, pool, gpu):
    policy_rate = None if mode == 'feedback_alone_max' else 3.
    feedback_rate = {'policy_only_3Hz': None, 'feedback_6Hz': 6., 'feedback_30Hz': 30.,
                     'feedback_alone_max': 0., 'feedback_saturated_with_policy': 0.}[mode]
    channels = []
    if policy_rate is not None:
        channels.append(('policy', policy_rate))
    if mode != 'policy_only_3Hz':
        channels.append(('feedback', feedback_rate))
    barrier = threading.Barrier(len(channels) + 1)
    origin = [None]
    def loop(name, rate):
        barrier.wait()
        rows, index, skipped = [], 0, 0
        while True:
            now = time.perf_counter() - origin[0]
            if now >= duration:
                break
            if rate:
                # Only the newest due input is processed; stale frame arrivals do not queue indefinitely.
                latest = max(index, math.floor(now * rate))
                skipped += latest - index
                index = latest
                release = index / rate
                if release >= duration:
                    break
                delay = origin[0] + release - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
            else:
                release = now
            start = time.perf_counter()
            if start - origin[0] >= duration:
                break
            if name == 'policy':
                model.plan(ctx, 202609260000 + len(rows))
            else:
                model.monitor(ctx)
            end = time.perf_counter()
            rows.append(dict(release_s=release, start_s=start-origin[0], end_s=end-origin[0],
                             service_seconds=end-start))
            index += 1
        return rows, skipped
    futures = {name: pool.submit(loop, name, rate) for name, rate in channels}
    origin[0] = time.perf_counter()
    barrier.wait()
    outputs = {name: future.result() for name, future in futures.items()}
    return dict(mode=mode, gpu_index=gpu, duration_seconds=duration,
        drained_wall_seconds=time.perf_counter()-origin[0], planned_policy_hz=policy_rate,
        planned_feedback_hz=feedback_rate if feedback_rate else None, control_hz=30,
        policy=outputs.get('policy', ([], 0))[0], feedback=outputs.get('feedback', ([], 0))[0],
        policy_skipped_releases=outputs.get('policy', ([], 0))[1],
        feedback_skipped_releases=outputs.get('feedback', ([], 0))[1],
        policy_scheduled_count=math.ceil(duration*policy_rate) if policy_rate else 0,
        feedback_scheduled_count=math.ceil(duration*feedback_rate) if feedback_rate else None,
        arrival_semantics='fixed recorded real input replay; latest-due scheduling; no environment stepping')



def main(cfg_path):
    cfg = json.loads(Path(cfg_path).read_text())
    out = Path(cfg['output'])
    from model import ParallelModel
    model = ParallelModel(cfg)
    records = json.loads(Path(cfg['contexts_path']).read_text())['contexts']
    contexts = [(records[i], model.prepare(records[i])) for i in cfg['context_indices']]
    write(out / 'WORKER_READY.json', dict(time=time.time(), pid=os.getpid(), kind=cfg['kind']))
    ready_time = time.monotonic()
    while not Path(cfg['start_file']).exists():
        if time.monotonic() - ready_time > 900:
            raise TimeoutError('Finite model-loading barrier')
        time.sleep(1)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='native_feedback') as pool:
        cases = ['N', 'monitor', 'parallel_feedback_no_intervention']
        for index, (record, ctx) in enumerate(contexts):
            for repetition in range(-1, 5):
                offset = (index+repetition) % len(cases)
                for case in cases[offset:] + cases[:offset]:
                    seed = 202609260000 + record['context_index'] * 100 + repetition + 1
                    row = latency(model, ctx, case, seed, pool, cfg['gpu_index'])
                    row.update(kind=cfg['kind'], context_id=record['source_id'], task=record['task'],
                               repetition=repetition, warmup=repetition < 0)
                    append(out / 'latency.jsonl', row)
            write(out / 'PROGRESS.json', dict(time=time.time(), completed_contexts=index+1, stage='latency'))
        record, ctx = contexts[0]
        modes = ['policy_only_3Hz', 'feedback_alone_max', 'feedback_6Hz', 'feedback_30Hz', 'feedback_saturated_with_policy']
        offset = (cfg['gpu_index'] % 4) % len(modes)
        for mode in modes[offset:] + modes[:offset]:
            row = frequency(model, ctx, mode, 5. if mode == 'feedback_alone_max' else 10., pool, cfg['gpu_index'])
            row.update(kind=cfg['kind'], context_id=record['source_id'], task=record['task'])
            append(out / 'frequency.jsonl', row)
            write(out / 'PROGRESS.json', dict(time=time.time(), completed_mode=mode, stage='frequency'))
    write(out / 'RESULT.json', dict(status='complete', time=time.time(), kind=cfg['kind'],
          gpu_index=cfg['gpu_index'], contexts=len(contexts), training_updates=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    try:
        main(args.config)
    except BaseException as error:
        write(Path(cfg['output']) / 'RESULT.json', dict(status='technical_failure', time=time.time(),
              error=repr(error), traceback=traceback.format_exc()))
        raise
