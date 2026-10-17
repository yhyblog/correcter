"""Evaluation-only continuation. No training, old service launch or chat gate."""
import os, signal, sys, time, traceback
from pathlib import Path
import paths
from paths import ROOT, SCIENCE_ROOT, CAMPAIGN
from qio import read,new_json,atomic_json,utc,ref,process_identity
sys.path.append(str(CAMPAIGN/'work/C/C_D24_QUOTA_INDEPENDENT_QUEUE_V1_r1'))
import queue_common as qc
from admission import authority,resource_admission
from wave import run_wave,notify_identity

def main():
    qc.authority();authority()
    # The coordinator owns continuation admission. Both original supervisors and
    # any older continuation must be gone; a callback is never checked.
    for r in [qc.X,qc.P]+[Path(p) for p in read(ROOT/'CONTINUATION.json')['earlier_runs']]:
        if not qc.family(r)['exited']:raise RuntimeError('live original/continuation family; no overlap')
    own=notify_identity(process_identity())
    new_json(ROOT/'PROCESS.json',own)
    new_json(ROOT/'CLAIM.json',dict(task_id=SCIENCE_ROOT.name,continuation=True,original_claim=ref(SCIENCE_ROOT/'CLAIM.json'),manifest=ref(ROOT/'CONTINUATION.json'),process=own,utc=utc(),training_updates=0))
    manifest=dict(job_id=ROOT.name,task_id=SCIENCE_ROOT.name,revision=1,run_id=ROOT.name,attempt=1,claim_identity=ref(ROOT/'CLAIM.json'),process_identity=own,result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'stderr.log'))
    new_json(ROOT/'WAKEUP_REGISTRATION.json',manifest)
    qc.notify(ROOT/'WAKEUP_REGISTRATION.json')  # failure cannot abort this stage
    fatal=None;result=None;started=time.monotonic()
    try:
        new_json(ROOT/'RESOURCE_EVALUATE.json',resource_admission())
        result=run_wave('evaluate')
    except BaseException as exc:
        fatal=dict(error=repr(exc),traceback=traceback.format_exc())
    release=qc.snapshot(ROOT/'chains/evaluate/BEFORE_RESERVATION_RELEASE.json')
    clean=(release.get('cleanup') or {}).get('status') in ['all_formal_group_members_exited','no_formal_entry']
    if not (ROOT/'chains/evaluate').exists():clean=True
    restoration=qc.snapshot(ROOT/'chains/evaluate/RESTORATION.json')
    new_json(ROOT/'RESULT.json',dict(task_id=SCIENCE_ROOT.name,utc=utc(),status='continuation_terminal',fatal=fatal,wave=result,all_owned_descendants_exited=clean,occupancy_handoff_complete=restoration.get('status')=='occupancy_resolved',elapsed_seconds=time.monotonic()-started,original_claim_preserved=True,new_training_updates=0,completed_source_replays=0))
    return 3 if fatal or not clean else 0

if __name__=='__main__':sys.exit(main())

