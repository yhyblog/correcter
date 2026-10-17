"""P0 only. Every GPU wave must be launched through the occupancy lifecycle."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import traceback
import numpy as np
from .storage import ROOT, PACKAGE, AttemptLedger, arrays, dump, seal, sha256
from .protocol import require_stage_budget, seed_for


def verify_frozen():
    frozen=json.loads((ROOT/'p0/freeze.json').read_text())
    for name,expected in frozen['files'].items():
        if sha256(name)!=expected:raise ValueError('Frozen dependency changed: '+name)
    for name,identity in frozen.get('large_files_verified_once_then_stat',{}).items():
        stat=Path(name).stat()
        if any([stat.st_size!=identity['bytes'],stat.st_mtime_ns!=identity['mtime_ns'],
                stat.st_ino!=identity['inode'],stat.st_dev!=identity['device']]):
            raise ValueError('Byte-verified large checkpoint cache changed: '+name)
    config=json.loads((ROOT/'p0/config.json').read_text())
    require_stage_budget(config,'p0')
    return config


def save_diagnostic(folder,metadata,values):
    folder.mkdir(parents=True,exist_ok=False)
    arrays(folder/'arrays.npz',**values)
    dump(folder/'summary.json',metadata)
    seal(folder)


def save_error(folder,error,case=None):
    folder.mkdir(parents=True,exist_ok=True)
    row=dict(status='failed',utc=datetime.now(timezone.utc).isoformat(),error_type=type(error).__name__,
             error=str(error),traceback=traceback.format_exc(),outcome_filter=False)
    if case:
        row.update(episode_id=case['episode_id'],task=case['task'],env_seed=case['env_seed'],split=case['split'])
    if hasattr(error,'metadata'):row['diagnostic']=error.metadata
    if hasattr(error,'arrays'):arrays(folder/'failure_arrays.npz',**error.arrays)
    dump(folder/'failure.json',row)


def load_plans(case,cut):
    bank=ROOT/'candidates'/case['case_id']/f'cut{cut:03d}'
    with np.load(bank/'plans.npz') as archive:plans={name:archive[name].copy() for name in archive.files}
    return plans,bank


def run_case(collector,case,*,single_replan=False):
    source=ROOT/'sources'/case['case_id']
    if not (source/'complete.json').exists():collector.capture(case)
    meta=json.loads((source/'summary.json').read_text())
    if not meta['cuts']:
        return source,meta
    cut=meta['cuts'][0]
    bank=ROOT/'candidates'/case['case_id']/f'cut{cut:03d}'
    if not (bank/'complete.json').exists():collector.prepare_bank(case,source,cut)
    plans,_=load_plans(case,cut)
    if single_replan:
        collector.branch(case,source,cut,'alarm_replan10',plans['alarm_replan10'],0)
        return source,meta
    order=np.random.default_rng(seed_for('branch_order',case['episode_id'],cut,namespace=collector.namespace))
    for repeat in range(collector.config['replicates']):
        for method in order.permutation(collector.config['methods']):
            method=str(method)
            dest=ROOT/'rollouts/p0'/case['case_id']/f'cut{cut:03d}'/method/f'repeat_{repeat}'
            if (dest/'complete.json').exists():continue
            collector.branch(case,source,cut,method,None if method=='continue_native10' else plans[method],repeat)
    return source,meta


def worker(mode,rank):
    config=verify_frozen()
    ledger=AttemptLedger(config)
    begin=time.perf_counter()
    case=None
    engine=None
    try:
        import torch
        torch.set_num_threads(config['cpu']['worker_threads'])
        torch.cuda.set_device(0)
        if mode=='technical' and rank>=5:
            from .legacy_diagnostic import run as legacy_run
            legacy_run(config,ledger,case_indices=[rank-5])
        else:
            from .engine import create_engine
            from .adapter import Native10Collector
            engine=create_engine(config,'p0')
            collector=Native10Collector(engine,config,ledger,'p0')
            cases=config['episode_manifest']
            if mode=='technical':
                case=cases[rank]
                from .diagnostics import run_native10_equivalence
                metadata,values=run_native10_equivalence(engine,case,config,ledger,max_steps=30)
                save_diagnostic(ROOT/'diagnostics/native10_queue'/case['case_id'],metadata,values)
                source,meta=run_case(collector,case,single_replan=True)
                if meta['cuts']:
                    from .probes import run_raw_clipped_probe
                    metadata,values=run_raw_clipped_probe(engine,case,source,meta['cuts'][0],collector.restore,ledger)
                    save_diagnostic(ROOT/'diagnostics/raw_clipped'/case['case_id'],metadata,values)
                else:
                    dump(ROOT/'diagnostics/raw_clipped'/case['case_id']/'skipped.json',
                         dict(status='unavailable_no_cut',episode_id=case['episode_id'],planned_source_retained=True))
            elif mode=='native20':
                for case in cases[rank::8]:
                    run_case(collector,case)
                    print(json.dumps(dict(event='episode_complete',case=case['case_id'])),flush=True)
            else:
                raise ValueError('Unknown P0 mode')
        dump(ROOT/'p0/wave_status'/mode/f'worker_{rank}.json',dict(status='complete',mode=mode,rank=rank,
            utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-begin))
    except Exception as error:
        save_error(ROOT/'p0/errors'/f'{mode}_{rank}_{time.time_ns()}',error,case)
        raise
    finally:
        if engine is not None:engine.close()


def launch_spec(mode):
    verify_frozen()
    wave=f'{mode}_{time.time_ns()}'
    spec=ROOT/'p0/waves'/f'{wave}.json'
    dump(spec,dict(hold_idle=False,log_root=str(ROOT/'p0/logs'/wave),jobs=[
        dict(devices=[rank],command=['bash',str(Path(__file__).with_name('run_gpu.sh')),'worker',
                                    '--mode',mode,'--rank',str(rank)]) for rank in range(8)]))
    print(spec)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['worker','launch-spec'])
    parser.add_argument('--mode',choices=['technical','native20'],required=True)
    parser.add_argument('--rank',type=int)
    args=parser.parse_args()
    worker(args.mode,args.rank) if args.action=='worker' else launch_spec(args.mode)
