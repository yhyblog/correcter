"""New Smol/X same-device feedback plus full Q correction; no prior cases repeated."""
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
        raw = planned.result()
        feedback = monitored.result()
    q_start = time.perf_counter()
    raw = model.correct(ctx, raw, feedback['observed'])
    q_seconds = time.perf_counter() - q_start
    wall = time.perf_counter() - origin
    policy, monitor = spans.get('policy', {}), spans.get('feedback', {})
    return dict(case=case, gpu_index=gpu, wall_seconds=wall,
        policy_seconds=policy.get('seconds'), feedback_seconds=monitor.get('seconds'),
        policy_start_s=policy.get('start'), policy_end_s=policy.get('end'),
        feedback_start_s=monitor.get('start'), feedback_end_s=monitor.get('end'),
        gate=feedback['gate'] if feedback is not None else None,
        gate_is_untrained=True, Q_included=True, q_seconds=q_seconds)



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
        cases = ['parallel_feedback_with_Q']
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
