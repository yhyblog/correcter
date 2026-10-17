import ast
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
N=C/'results/B/B_D24_POST_TRIGGER_MODES_V1/recovery_r3'
sys.path.insert(0,str(N/'code'))
import qio, admission

checks=[]
for p in (N/'code').glob('*.py'): ast.parse(p.read_text())
with tempfile.TemporaryDirectory(prefix='B_recovery_r3_') as tmp:
    p=Path(tmp)/'sample.json'; p.write_text('{"current": true}')
    original=Path.open; calls=[]
    def transient(self,*args,**kw):
        if self==p:
            calls.append(1)
            if len(calls)==1: raise FileNotFoundError(2,'atomic replace window')
        return original(self,*args,**kw)
    with patch.object(Path,'open',transient): assert qio.read(p)=={'current':True}
    assert len(calls)==2;checks.append('transient_ENOENT_retries_fresh_contents')
    p.write_text('{')
    with patch.object(qio.time,'sleep',lambda _:p.write_text('{"fresh": 1}')): assert qio.read(p)=={'fresh':1}
    checks.append('partial_JSON_retries_fresh_contents')
    unavailable=qio.optional_snapshot(Path(tmp)/'not_yet_present.json')
    assert unavailable['status']=='snapshot_temporarily_unavailable'
    checks.append('missing_optional_telemetry_reported_without_fatal')
    with patch.object(Path,'open',side_effect=PermissionError(13,'not transient')):
        try: qio.read(p)
        except PermissionError: pass
        else: raise AssertionError('permission error swallowed')
    checks.append('nontransient_errors_not_swallowed')

original_read=admission.read_control
def stopped(p):
    d=original_read(p)
    if str(p).endswith('/persistent_queue/CONTROL.json'):d['global_stop']=True
    return d
with patch.object(admission,'read_control',stopped):
    try: admission.authority()
    except RuntimeError as e: assert 'not currently authorized' in str(e)
    else: raise AssertionError('real stop ignored')
checks.append('real_control_stop_still_rejected')
cfg=qio.read(N/'config/CONFIG.json');plan=qio.read(N/'config/RECOVERY_PLAN.json')
units=set()
for p in (N/'jobs').glob('*.json'):
    j=qio.read(p);admission.validate_job(j)
    for s in j['sources']:
        k=(j['mode'],j['H'],s['source_id']);assert k not in units;units.add(k)
assert len(units)==4504 and not (units & {tuple(x) for x in plan['retained_valid_units']})
assert len(plan['corrected_retry_units'])==2 and plan['prior_physical_attempts']==505
assert cfg['absolute_wall_deadline_unix']==1790102926.704207
checks.append('496_valid_excluded_4502_unstarted_2_one_time_retries_original_deadline')
import publish_trigger
result=publish_trigger.publish('Post_Random-once_H10')
assert result['attempts']==505 and result['valid']==496
summary=qio.read(N/'cell_publications/Post_Random-once_H10/FINAL_SUMMARY.json')
assert summary['historical_technical_attempts']==9 and summary['cells'][0]['execution_unknown']==0
checks.append('three_root_publication_preserves_prior_retries_costs_and_denominators')
for name in ['numeric_engine.py','resident_egl.py','trigger_controller.py']:
    assert (N/'code'/name).read_bytes()==(N.parent/'recovery_r2/code'/name).read_bytes()
checks.append('scientific_engine_renderer_controller_unchanged')
qio.new_json(N/'evidence/RECOVERY_CPU_CHECKS.json',dict(status='PASS',checks=checks,at_utc=qio.utc(),GPU_calls=0))
manifest=qio.read(N/'CODE_MANIFEST.json')
manifest['files']={str(p.relative_to(N)):qio.sha(p) for p in sorted((N/'code').glob('*.py'))}
qio.atomic_json(N/'CODE_MANIFEST.json',manifest)
print(json.dumps(dict(status='PASS',checks=checks)))
