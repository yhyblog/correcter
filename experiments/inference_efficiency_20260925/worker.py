"""Finite batch-one query profiling on real, predetermined MT50 cut contexts."""
import argparse
import json
import os
from pathlib import Path
import time
import traceback


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    tmp.replace(path)


def main(config_path):
    cfg = json.loads(Path(config_path).read_text())
    out = Path(cfg['output'])
    from adapter import NativeAdapter
    model = None
    completed, skipped, failures = [], [], []
    try:
        model = NativeAdapter(cfg)
        write(out / 'MODEL_READY.json', dict(time=time.time(), pid=os.getpid(), kind=cfg['kind']))
        if cfg.get('start_file'):
            ready_start = time.monotonic()
            while not Path(cfg['start_file']).exists():
                if time.monotonic() - ready_start > 1200:
                    raise TimeoutError('All-worker model loading barrier timed out')
                time.sleep(1)
        for si, source in enumerate(cfg['sources']):
            sid = source['source_id']
            target = out / 'sources' / sid
            if (target / 'RESULT.json').exists():
                continue
            target.mkdir(parents=True, exist_ok=True)
            try:
                context = model.prepare_source(source, H=10, cut=5)
                write(target / 'CONTEXT.json', context)
                if not context['eligible']:
                    skipped.append(sid)
                    write(target / 'RESULT.json', dict(status='ineligible_cut', source=sid, context=context))
                    continue
                rows = []
                for rep in range(-cfg.get('warmups', 1), cfg.get('repetitions', 5)):
                    monitor = model.monitor()
                    order = ['N', 'R', 'Post']
                    offset = (si + rep) % 3
                    order = order[offset:] + order[:offset]
                    for method in order:
                        seed = int(source['warmup_seed'] if rep < 0 else source['measurement_seeds'][rep])
                        start = time.perf_counter()
                        plan = model.generate(None if method == 'N' else seed)
                        post = model.post(plan['raw_plan']) if method == 'Post' else {}
                        wall_seconds = time.perf_counter() - start
                        components = {k: float(v) for k, v in post.items() if k.endswith('_seconds')}
                        query_seconds = float(plan['policy_seconds']) + sum(
                            components.get(k, 0.) for k in ('objective_seconds', 'gradient_seconds', 'projection_seconds'))
                        row = dict(kind=cfg['kind'], method=method, source_id=sid, task=source['task'],
                                   gpu_index=cfg['gpu_index'], repetition=rep, warmup=rep < 0,
                                   policy_seconds=float(plan['policy_seconds']), query_seconds=query_seconds,
                                   query_wall_seconds=wall_seconds, flow_calls=plan.get('flow_calls'),
                                   monitor=monitor, post=components)
                        rows.append(row)
                        with (target / 'timings.jsonl').open('a') as stream:
                            stream.write(json.dumps(row) + '\n')
                        write(out / 'PROGRESS.json', dict(time=time.time(), source=sid, repetition=rep,
                              method=method, measured_so_far=sum(not r['warmup'] for r in rows),
                              completed_sources=len(completed), skipped_sources=len(skipped)))
                completed.append(sid)
                write(target / 'RESULT.json', dict(status='complete', source=sid,
                      measured_queries=sum(not r['warmup'] for r in rows), warmup_queries=sum(r['warmup'] for r in rows)))
            except Exception as error:
                failures.append(sid)
                write(target / 'RESULT.json', dict(status='technical_failure', source=sid,
                      error=repr(error), traceback=traceback.format_exc()))
                # A broken shared model/connection cannot be repaired by replaying scientific samples.
                if isinstance(error, (BrokenPipeError, EOFError, ConnectionError)):
                    raise
        write(out / 'RESULT.json', dict(status='complete' if not failures else 'partial',
              completed=completed, skipped=skipped, failures=failures, time=time.time()))
    except BaseException as error:
        write(out / 'RESULT.json', dict(status='technical_failure', error=repr(error),
              traceback=traceback.format_exc(), completed=completed, skipped=skipped, failures=failures, time=time.time()))
        raise
    finally:
        if model is not None:
            model.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    main(parser.parse_args().config)
