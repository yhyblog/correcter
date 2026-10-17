"""CPU-only execution receipt for the separately authorized final A/B protocol.

Preparation or a high READY version never releases this entrypoint. Exact
config/freeze/scope verification precedes importing the model pipeline. The
current collection release cannot run it. No experiment is started on import.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import time
import traceback

from . import storage


def utc():
    return datetime.now(timezone.utc).isoformat()


def ledger_snapshot():
    """Take an immutable resource view without reserving any dummy attempt."""
    with storage.LOCK_PATH.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        raw=(storage.ROOT/'budget/attempts.jsonl').read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Partial budget record')
    rows=[json.loads(line) for line in raw.splitlines()]
    totals=Counter();stages=defaultdict(Counter)
    for number,row in enumerate(rows,1):
        if (row.get('number')!=number or type(row.get('amount')) is not int or row['amount']<1
                or row.get('resource') not in ('simulator_attempts','training_updates')):
            raise ValueError('Invalid ordered resource ledger')
        totals[row['resource']]+=row['amount'];stages[row['stage']][row['resource']]+=row['amount']
    if totals['simulator_attempts']>50000 or totals['training_updates']>51200:
        raise ValueError('Global hard resource limit exceeded')
    return dict(raw=raw,rows=rows,sha256=hashlib.sha256(raw).hexdigest(),
        totals=dict(totals),stages={stage:dict(counts) for stage,counts in stages.items()})


def resource_delta(before,after,mode,protocol_sha256):
    if mode not in ('preflight','fit'):
        raise ValueError('Unsupported final execution mode')
    if not after['raw'].startswith(before['raw']) or after['rows'][:len(before['rows'])]!=before['rows']:
        raise ValueError('Existing budget history was changed or removed')
    added=after['rows'][len(before['rows']):]
    if mode=='preflight' and added:
        raise ValueError('Zero-update preflight changed the formal resource ledger')
    if any(row['resource']!='training_updates' or row['stage']!='training_final'
           or row.get('kind')!='critic_optimizer_update' or row['amount']!=1
           or row.get('protocol_sha256')!=protocol_sha256 for row in added):
        raise ValueError('Final execution contains an unauthorized simulator/stage/update attempt')
    if (len(added)>32000 or after['stages'].get('training_final',{}).get('training_updates',0)>32000
            or after['totals'].get('training_updates',0)>51200):
        raise ValueError('Final or workflow optimizer budget exceeded')
    return dict(simulator_attempts=0,optimizer_updates=len(added),attempt_numbers=[r['number'] for r in added],
        prior_attempts_preserved=True,preflight_ledger_unchanged=before['raw']==after['raw'])


def _verify(config_path,freeze_path,mode):
    from .final_fit_protocol_v1 import verify_frozen
    return verify_frozen(config_path,freeze_path,mode)


def _pipeline():
    from . import final_training_pipeline_v1
    return final_training_pipeline_v1


def _metadata(snapshot):
    return {key:value for key,value in snapshot.items() if key not in ('raw','rows')}


def execute(mode,*,config_path,freeze_path,version):
    if mode not in ('preflight','fit') or not isinstance(version,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',version):
        raise ValueError('Use an explicit supported mode and safe new output version')
    start,started=time.perf_counter(),utc()
    # CPU formal work retains the GPU holders. This entrypoint never reserves GPUs.
    os.environ['CUDA_VISIBLE_DEVICES']=''
    os.environ['OMP_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
    config=_verify(config_path,freeze_path,mode)
    verified=time.perf_counter()
    before=ledger_snapshot()
    directory=storage.ROOT/'final_fit_execution'/mode/version
    directory.mkdir(parents=True,exist_ok=False)
    storage.dump(directory/'registration.json',dict(mode=mode,version=version,started_utc=started,
        config_path=str(Path(config_path).resolve()),config_sha256=storage.sha256(config_path),
        freeze_path=str(Path(freeze_path).resolve()),freeze_sha256=storage.sha256(freeze_path),
        protocol_sha256=config['analysis_approval']['protocol_sha256'],cpu_only=True,
        gpu_holders_yielded=False,resource_before=_metadata(before),next_stage_automatically_started=False))
    with (directory/'budget_before.jsonl').open('xb') as stream:stream.write(before['raw'])
    try:
        pipeline=_pipeline()
        if mode=='preflight':
            result=pipeline.preflight(config,version=version)
        else:
            result=pipeline.run(config,storage.AttemptLedger(config),version=version)
        after=ledger_snapshot()
        delta=resource_delta(before,after,mode,config['analysis_approval']['protocol_sha256'])
        status=result.get('status')
        allowed=('passed','pending_numerical_review') if mode=='preflight' else ('complete',)
        if status not in allowed:
            raise ValueError('Final pipeline returned an unsupported/incomplete execution status')
        if mode=='fit' and result.get('optimizer_updates')!=delta['optimizer_updates']:
            raise ValueError('Reported optimizer updates disagree with the immutable ledger')
        with (directory/'budget_after.jsonl').open('xb') as stream:stream.write(after['raw'])
        receipt=dict(status=status,mode=mode,version=version,started_utc=started,finished_utc=utc(),
            wall_seconds=time.perf_counter()-start,verification_seconds=verified-start,
            max_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            resources=delta,resource_after=_metadata(after),pipeline_result=result,
            cpu_only=True,next_stage_automatically_started=False,
            next_stage_authorized=False,training_success_claim=False)
        storage.dump(directory/'result.json',receipt)
        storage.seal(directory,role='native10_final_cpu_execution_receipt',mode=mode,
            scientific_status=status,next_stage_automatically_started=False)
        return dict(path=str(directory),seal_sha256=storage.sha256(directory/'complete.json'),**receipt)
    except BaseException as error:
        failure=dict(status='failed',mode=mode,version=version,error_type=type(error).__name__,error=str(error),
            traceback=traceback.format_exc(),started_utc=started,finished_utc=utc(),
            wall_seconds=time.perf_counter()-start,counted_attempts_preserved=True,
            automatic_retry=False,next_stage_automatically_started=False)
        try:
            after=ledger_snapshot()
            with (directory/'budget_after_failure.jsonl').open('xb') as stream:stream.write(after['raw'])
            failure['resource_after_failure']=_metadata(after)
        except Exception as snapshot_error:
            failure['resource_snapshot_error']=repr(snapshot_error)
        storage.dump(directory/'failure.json',failure)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('preflight','fit'))
    parser.add_argument('--config-path',type=Path,required=True)
    parser.add_argument('--freeze-path',type=Path,required=True)
    parser.add_argument('--version',required=True)
    result=execute(**vars(parser.parse_args()))
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()
