"""Installed only in a new, explicitly linked continuation, never in live code."""
import fcntl, hashlib, os, sys, time
from pathlib import Path
from paths import ROOT, SCIENCE_ROOT, CAMPAIGN
from qio import read, new_json, atomic_json, ref, utc, process_identity
sys.path.append(str(CAMPAIGN/'work/C/C_D24_QUOTA_INDEPENDENT_QUEUE_V1_r1'))
import queue_common as qc
MANIFEST=read(ROOT/'CONTINUATION.json')
UNITS={r['unit_id']:r for r in MANIFEST['units']}
IS_X=SCIENCE_ROOT==qc.X

def allowed(uid): return uid in UNITS

def before_cutoff():
    end=min(qc.CUTOFF,read(ROOT/'STAGE_DEADLINE.json')['deadline_unix'])
    return time.time()<end and not any((r/n).exists() for r in [ROOT,SCIENCE_ROOT] for n in ['STOP.json','DRAIN.json'])

def authority():
    import base_admission
    base_admission.authority();qc.authority()
    if read(SCIENCE_ROOT/'CLAIM.json')!=read(ROOT/'ORIGINAL_CLAIM.json'):raise RuntimeError('original scientific claim changed')
    if qc.sha(SCIENCE_ROOT/'config/CONFIG.json')!=MANIFEST['config']['sha256']:raise RuntimeError('original configuration changed')
    return True

def admissions_allowed():
    if not before_cutoff():return False
    q=read(CAMPAIGN/'persistent_queue/CONTROL.json');c=read(CAMPAIGN/'CONTROL.json')
    return not q.get('global_stop') and not c.get('stop_requested') and q['nodes']['C']['enabled']

_last=0.
def boundary(admission=False):
    global _last
    if admission or time.monotonic()-_last>=5:
        authority()
        if not admissions_allowed():
            import base_admission
            error=base_admission.AdmissionStop if IS_X else base_admission.AdmissionClosed
            raise error('continuation original deadline/stop/grant boundary')
        _last=time.monotonic()

def result_paths(uid,item):
    for root in [SCIENCE_ROOT]+[Path(p) for p in MANIFEST['earlier_runs']]+[ROOT]:
        yield root/'evaluation'/uid/'RESULT.json' if IS_X else root/'runs'/item['job_id']/'episodes'/item['source']['source_id']/'RESULT.json'

def admit(uid,job=None):
    authority()
    if uid not in UNITS:raise RuntimeError('unit outside exact continuation manifest')
    item=UNITS[uid];qc.LOCAL.mkdir(exist_ok=True)
    with (qc.LOCAL/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not admissions_allowed():raise RuntimeError('admission closed')
        for p in result_paths(uid,item):
            if p.exists():
                r=read(p)
                if qc.policy.legal_terminal(r) or r.get('status') in ['user_cancelled','cancelled']:raise RuntimeError('legal/cancelled terminal cannot replay')
        if job is not None:
            import base_admission
            base_admission.validate_job(job)
            from transfer import assert_not_A_owned
            assert_not_A_owned(job['job_id'],uid)
            if item['source'] not in job['sources'] or job['job_id']!=item['job_id']:raise ValueError('exact transferred source changed')
            if job['H']==50 and not (ROOT/'H40_DISPATCH_COMPLETE.json').exists():raise RuntimeError('H40 dispatch barrier')
        digest=hashlib.sha256(uid.encode()).hexdigest()
        old=SCIENCE_ROOT/'claims/attempts'/(digest+'.json') if IS_X else SCIENCE_ROOT/'unit_claims'/(uid+'.json')
        old_exists=old.exists();attempt=int(old_exists)
        if attempt!=item['prior_attempts'] or attempt>1:raise RuntimeError('attempt lineage changed')
        if attempt and item['correction']!='atomic_exclusive_JSON_commit_with_bounded_transient_IO_retry':raise RuntimeError('failed source lacks encoded correction')
        ledger=SCIENCE_ROOT/'quota_attempt_lineage'/(digest+f'_a{attempt}.json')
        if ledger.exists():raise RuntimeError('source continuation already reserved; no duplicate')
        nx,np,total=qc.counts();used=nx if IS_X else np;cap=1100 if IS_X else 2200;nodecap=14000 if IS_X else 16000
        if used>=cap or total>=nodecap:raise RuntimeError('unchanged stage/node budget exhausted')
        number=used+1;counter=SCIENCE_ROOT/'ATTEMPT_COUNTER.json'
        # Persist the charge before launch. A crash can conservatively lose a
        # reservation, but can never produce an uncounted scientific attempt.
        new_json(ledger,dict(unit_id=uid,attempt=attempt,stage_ordinal=number,node_cumulative_ordinal=total+1,manifest=ref(ROOT/'CONTINUATION.json'),process=process_identity(),utc=utc(),original_claim=ref(old) if old_exists else None))
        if IS_X:
            atomic_json(counter,dict(reserved_attempts=number,prior_C_attempts=11943,cumulative_C_reserved=total+1,at_utc=utc(),continuation_lineage=str(ledger)))
            row=dict(identity=uid,number=number,process=process_identity(),at_utc=utc(),phase='evaluate',method=item['method'],source_id=item['source']['source_id'],attempt=attempt,corrected_retry=bool(attempt),lineage=str(ledger))
            target=ROOT/'claims/attempts'/(digest+'.json')
        else:
            prior=read(SCIENCE_ROOT/'PREDECESSOR_EXIT.json')['prior_C_attempts']
            atomic_json(counter,dict(count=number,prior_D24_attempts=prior,node_cumulative=total+1,stage_cap=2200,node_cap=16000,first_evaluation_cap=read(SCIENCE_ROOT/'TRANSFER_CONSUMED.json')['first_count'],utc=utc(),continuation_lineage=str(ledger)))
            row=dict(unit_id=uid,task_id=SCIENCE_ROOT.name,cell_id=job['cell_id'],source=item['source'],H=job['H'],mode=job['mode'],branch=job['method'],stage=job['stage'],loss=job['loss'],fit_seed=job['fit_seed'],attempt=attempt,stage_ordinal=number,node_cumulative_ordinal=total+1,utc=utc(),retry=bool(attempt),lineage=str(ledger))
            target=ROOT/'unit_claims'/(uid+'.json')
        if not old_exists:new_json(old,row)
        new_json(target,row)
        return str(target) if IS_X else row

def claim_attempt(identity,**extra):return admit(identity)
def admit_episode(source,job):
    uid=job['cell_id']+'__'+source['source_id']
    if UNITS.get(uid,{}).get('source')!=source:raise ValueError('source changed')
    return admit(uid,job)
