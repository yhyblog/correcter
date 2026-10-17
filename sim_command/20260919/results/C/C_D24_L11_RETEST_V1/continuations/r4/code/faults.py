"""First unexpected engineering outcome closes new admissions, not active work."""
from paths import ROOT
from qio import new_json, utc

def pause(unit_id, result_path, detail):
    model=unit_id.split('|',1)[0]
    if model not in ('X-VLA','pi05'):raise ValueError('fault model scope')
    p=ROOT/('PAUSE_ADMISSIONS_'+model+'.json')
    try:
        new_json(p,dict(utc=utc(),reason='new_engineering_failure',model=model,unit_id=unit_id,
            result_path=str(result_path),detail=detail,existing_entered_work_drains=True,
            automatic_blind_retry=False,completed_source_replays=0))
    except FileExistsError:pass
