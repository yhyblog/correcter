"""First unexpected engineering outcome closes new admissions, not active work."""
from paths import ROOT
from qio import new_json, utc

def pause(unit_id, result_path, detail):
    p=ROOT/'PAUSE_ADMISSIONS.json'
    try:
        new_json(p,dict(utc=utc(),reason='new_engineering_failure',unit_id=unit_id,
            result_path=str(result_path),detail=detail,existing_entered_work_drains=True,
            automatic_blind_retry=False,completed_source_replays=0))
    except FileExistsError:pass
