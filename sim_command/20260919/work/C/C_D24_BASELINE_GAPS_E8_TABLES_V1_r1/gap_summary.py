"""Small authoritative summary of the five finite corrected baseline attempts."""
from pathlib import Path
import d24_common as d


def summarize(path):
    cfg=d.load(path)
    records=[]
    for job in cfg['jobs']:
        jc=d.load(job['config'])
        source=jc['episodes'][0]
        rp=Path(job['output'])/'episodes'/source['source_id']/'RESULT.json'
        claim=d.R/'unit_claims'/(source['source_id']+'__N__corrected1.json')
        if rp.exists():
            row=d.load(rp)
            records.append(dict(source_id=source['source_id'],suite=jc['suite'],result_path=str(rp),
                                status=row['status'],success=row['success'],attempt=2,C_attempt=1))
        else:
            records.append(dict(source_id=source['source_id'],suite=jc['suite'],result_path=str(rp),
                                status='execution_unknown' if claim.exists() else 'unstarted',success=None))
    valid=sum(r['status']=='complete' and type(r['success']) is bool for r in records)
    attempts=len(list((d.R/'unit_claims').glob('*.json')))
    result=dict(task_id='C_D24_BASELINE_GAPS_E8_TABLES_V1',at_utc=d.utc(),
                status='complete' if valid==5 else 'partial',planned_eligible=5,valid=valid,
                successes=sum(r['success'] is True for r in records),
                technical_failures=sum(r['status']=='technical_failure' for r in records),
                current_C_attempts=attempts,cumulative_C_attempts=1008+attempts,
                historical_N_attempts_before_C=1401,combined_original_N_attempts=1401+attempts,
                unknown_original_slots_not_replayed=5,optimizer_updates=0,development_attempts=0,
                automatic_second_retry=False,records=records)
    d.atomic(d.R/cfg['batch_id']/'SUMMARY.json',result)
    d.atomic(d.C/'receipts/C/C_D24_BASELINE_GAPS_E8_TABLES_V1_RUNNING.json',result)
    return result
