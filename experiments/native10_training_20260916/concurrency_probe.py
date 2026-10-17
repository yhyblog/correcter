"""P0-only 32-worker reproducibility probe: 64 counted attempts, no new sources.

Uses the first eight registered P0 cases, four replicas each, independently of
their outcomes. Original P0 code/config/artifacts remain read-only. Full candidate
and trajectory arrays are compared to the already sealed one-worker/GPU run.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from .storage import ROOT, PACKAGE, AttemptLedger, arrays, dump, seal, sha256
from .runner import verify_frozen, save_error

OUT = ROOT/'p0/concurrency32'


def prepare():
    cfg=verify_frozen()
    audit=ROOT/'p0/audit_native20.json'
    if json.loads(audit.read_text())['status']!='passed':
        raise ValueError('Native20 audit must pass first')
    ledger=[json.loads(x) for x in (ROOT/'budget/attempts.jsonl').read_text().splitlines()]
    used=sum(x['amount'] for x in ledger if x['resource']=='simulator_attempts')
    if used+64>600:raise ValueError('Insufficient P0 budget')
    references={}
    for case in cfg['episode_manifest'][:8]:
        source=ROOT/'sources'/case['case_id']
        cut=json.loads((source/'summary.json').read_text())['cuts'][0]
        bank=ROOT/'candidates'/case['case_id']/f'cut{cut:03d}'
        branch=ROOT/'rollouts/p0'/case['case_id']/f'cut{cut:03d}'/'alarm_replan10/repeat_0'
        for folder in (source,bank,branch):
            references[str(folder/'complete.json')]=sha256(folder/'complete.json')
    dump(OUT/'registration.json',dict(workers=32,workers_per_gpu=4,attempts=64,
        budget_before=used,budget_after_max=used+64,case_ids=[x['case_id'] for x in cfg['episode_manifest'][:8]],
        selection='first eight manifest rows, each four copies; no outcome filter',
        exact_keys='candidate commands, generated plans, executed commands, seeds, outcome flags',
        physics_atol=1e-10,physics_rtol=0.,diagnostic_only=True,changes_to_algorithm=False,
        baseline_audit_sha256=sha256(audit),references=references,
        files={str(p.resolve()):sha256(p) for p in (Path(__file__),Path(__file__).with_name('run_concurrency.sh'))},
        analysis_authority_sha256=sha256(PACKAGE/'coordination/NATIVE10_ANALYSIS_LEAD.md')))
    dump(OUT/'wave.json',dict(hold_idle=False,log_root=str(OUT/'logs'),jobs=[
        dict(devices=[gpu],command=['bash',str(Path(__file__).with_name('run_concurrency.sh')),'supervisor','--rank',str(gpu)])
        for gpu in range(8)]))
    print(OUT/'wave.json')


def verified_registration():
    r=json.loads((OUT/'registration.json').read_text())
    for name,digest in {**r['references'],**r['files']}.items():
        if sha256(name)!=digest:raise ValueError('Probe dependency changed: '+name)
    return r


def worker(rank):
    verified_registration();cfg=verify_frozen()
    case=cfg['episode_manifest'][rank%8]
    dest=OUT/f'worker_{rank:02d}'
    dest.mkdir(parents=True,exist_ok=False)
    engine=None
    begin=time.perf_counter()
    try:
        import torch
        torch.set_num_threads(cfg['cpu']['worker_threads']);torch.cuda.set_device(0)
        from .engine import create_engine
        from .adapter import Native10Collector,digest
        from corrector.critic import STATE_KEYS
        from .semantics import Native10Queue,make_branch_prefix,execute_prefix
        from .protocol import suffix_seed
        engine=create_engine(cfg,'p0')
        loading=time.perf_counter()-begin
        dump(OUT/'ready'/f'{rank:02d}.json',dict(rank=rank,unix=time.time(),loading_seconds=loading))
        deadline=time.monotonic()+900
        while len(list((OUT/'ready').glob('*.json')))<32:
            if time.monotonic()>deadline:raise TimeoutError('32-worker model-load barrier timed out')
            time.sleep(.5)
        work_started_unix=time.time()
        collector=Native10Collector(engine,cfg,AttemptLedger(cfg),'p0')
        source=ROOT/'sources'/case['case_id']
        cut=json.loads((source/'summary.json').read_text())['cuts'][0]
        baseline_bank=ROOT/'candidates'/case['case_id']/f'cut{cut:03d}'
        baseline_branch=ROOT/'rollouts/p0'/case['case_id']/f'cut{cut:03d}'/'alarm_replan10/repeat_0'
        tick=time.perf_counter()
        bank_attempt=collector.ledger.reserve('p0','concurrency_candidate_restore',str(dest))
        dump(dest/'bank_attempt.json',bank_attempt)
        collector.restore(case,source,cut)
        with np.load(source/f'cut{cut:03d}'/'context.npz') as archive:
            observed={name:archive[name].copy() for name in STATE_KEYS}
        plans,metadata,details=engine.make_bank(observed,case,cut)
        bank_seconds=time.perf_counter()-tick
        # Adapter names the raw replan plan alarm_replan10 when persisting banks.
        aliases={'replan':'alarm_replan10','velocity_matched':'velocity',
                 'direct_matched':'direct','post_matched':'post'}
        plans={aliases.get(name,name):plan for name,plan in plans.items()}
        arrays(dest/'plans.npz',**plans)
        dump(dest/'generation.json',metadata)
        with np.load(baseline_bank/'plans.npz') as ref:
            for key in ref.files:np.testing.assert_array_equal(plans[key],ref[key])
        tick=time.perf_counter()
        attempt=collector.ledger.reserve('p0','concurrency_branch_including_restore',str(dest))
        dump(dest/'branch_attempt.json',attempt)
        trace,snapshot,_=collector.restore(case,source,cut)
        restore_seconds=time.perf_counter()-tick
        prefix=make_branch_prefix(snapshot,'alarm_replan10',plans['alarm_replan10'])
        execute_prefix(prefix,lambda command:trace.execute(engine.runtime,command),lambda:trace.terminal,lambda:trace.step)
        endpoint=digest(engine.runtime.frame());suffix=[]
        queue=Native10Queue(start_step=trace.step,budget=300)
        while not trace.terminal and trace.step<300:
            t=trace.step
            if queue.needs_plan(t):
                index=len(suffix);seed=suffix_seed(case,cut,0,index,namespace=cfg['seed_namespace'])
                raw,stats=engine.propose(seed);queue.replace(raw,t)
                collector._record_plan(trace,raw,seed,stats)
                suffix.append(dict(step=t,decision_index=index,seed=seed,noise_sha256=stats.get('noise_sha256')))
            trace.execute(engine.runtime,queue.pop(t))
        branch_seconds=time.perf_counter()-tick
        values=trace.arrays();arrays(dest/'trajectory.npz',**values)
        errors=[]
        with np.load(baseline_branch/'trajectory.npz') as ref:
            for key in ref.files:
                try:
                    if key in ('physics_states','rewards'):
                        np.testing.assert_allclose(values[key],ref[key],rtol=0,atol=1e-10 if key=='physics_states' else 1e-8)
                    else:np.testing.assert_array_equal(values[key],ref[key])
                except AssertionError:errors.append(key)
        reference=json.loads((baseline_branch/'summary.json').read_text())
        if suffix!=reference['suffix_seeds']:errors.append('suffix_seed_and_noise_hash')
        if endpoint!=reference['endpoint_image_sha256']:errors.append('prefix_endpoint_image')
        engine.verify()
        dump(dest/'result.json',dict(status='passed' if not errors else 'failed',errors=errors,
            case_id=case['case_id'],rank=rank,loading_seconds=loading,candidate_restore_and_bank_seconds=bank_seconds,
            work_started_unix=work_started_unix,work_finished_unix=time.time(),
            branch_wall_seconds=branch_seconds,branch_restore_seconds=restore_seconds,
            wall_seconds=time.perf_counter()-begin,branch_steps=trace.step,bank_attempt=bank_attempt['number'],
            branch_attempt=attempt['number'],policy_calls=trace.policy_calls,policy_seconds=trace.policy_seconds,
            peak_allocated_mib=torch.cuda.max_memory_allocated()/2**20,
            peak_reserved_mib=torch.cuda.max_memory_reserved()/2**20))
        seal(dest)
        if errors:raise ValueError('Concurrent trajectory mismatch: '+repr(errors))
    except Exception as error:
        save_error(OUT/'errors'/f'worker_{rank}_{time.time_ns()}',error,case)
        raise
    finally:
        if engine is not None:engine.close()


def supervisor(gpu):
    verified_registration()
    children=[];streams=[]
    try:
        for copy in range(4):
            rank=gpu+8*copy
            stream=(OUT/'logs'/f'worker_{rank:02d}.log').open('x');streams.append(stream)
            children.append(subprocess.Popen([sys.executable,'-u','-m',__package__+'.concurrency_probe','worker','--rank',str(rank)],stdout=stream,stderr=subprocess.STDOUT))
        while any(p.poll() is None for p in children):
            for p in children:
                if p.poll() not in (None,0):raise RuntimeError(f'Owned worker failed: {p.returncode}')
            time.sleep(1)
        if any(p.returncode for p in children):raise RuntimeError('Probe worker failed')
    finally:
        for p in children:
            if p.poll() is None:p.terminate()
        for p in children:
            try:p.wait(timeout=20)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for stream in streams:stream.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','supervisor','worker'));p.add_argument('--rank',type=int)
    args=p.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='supervisor':supervisor(args.rank)
    else:worker(args.rank)


if __name__=='__main__':main()
