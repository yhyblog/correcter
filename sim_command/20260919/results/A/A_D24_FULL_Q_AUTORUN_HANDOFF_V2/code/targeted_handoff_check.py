"""Only new continuation, selection-publication and ownership CPU boundaries."""
import ast,copy,json,tempfile
from pathlib import Path
import paths,admission,selection,publication_data,transfer
from paths import ROOT,ORIGINAL,CAMPAIGN
from qio import read,new_json,sha,utc
from prepare_handoff import remaining_sources

checks=[]
for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
checks.append('private_changed_AST')
index=read(ROOT/'JOB_INDEX.json');jobs=[read(j['path']) for j in index['jobs']]
old_claims={p.stem for p in (ORIGINAL/'unit_claims').glob('*.json')}
units=[(j['cell_id']+'__'+s['source_id'],j['stage']) for j in jobs for s in j['sources']]
assert len(units)==len(set(u for u,_ in units))==4054
assert not old_claims.intersection(u for u,_ in units)
assert sum(s=='DEV' for _,s in units)==854
assert all(j['H']==10 for j in jobs if j['stage']=='MAIN')
for job in jobs:admission.validate_job(job,stage_gate=False)
checks.append('real_original_refs_822_jobs_4054_unentered_units_remote_H_absent')
test_job=next(j for j in jobs if j['stage']=='MAIN')
try:admission.validate_job(test_job)
except FileNotFoundError:pass
else:raise AssertionError('test admitted before immutable selection')
assert not (ORIGINAL/'SELECTION.json').exists()
checks.append('real_admission_rejects_test_before_selection_without_claim')
_,attempts,claims,_=publication_data.load_evidence()
assert len(attempts)==len(claims)==1546 and all(x['status']=='complete' for x in attempts)
checks.append('real_combined_reader_preserves1546_and_no_duplicate_claim')
assert transfer.original_exit_verified()['no_signal_sent']
checks.append('actual_original_normal_family_exit_evidence_readonly')

# Use actual selection/publisher functions, writing only synthetic /tmp roots.
with tempfile.TemporaryDirectory(prefix='corrector_handoff_cpu_') as temp:
 t=Path(temp);o=t/'old';n=t/'new';b=t/'campaign';o.mkdir();n.mkdir();b.mkdir()
 for p in ['ENSEMBLES.json','TRAINING_COMPLETE.json','SOURCE_INDEX.json']:
  (n/p).write_bytes((ROOT/p).read_bytes());(o/p).write_bytes((ORIGINAL/p).read_bytes())
 sources=read(ROOT/'SOURCE_INDEX.json')['source_sets']['DEV'];rows=[]
 for loss in selection.LOSSES:
  for fit in [9101,9102,9103]:
   for method in ['Post','Velocity']:
    for source in sources:rows.append(dict(source,stage='DEV',cell_id=f'DEV_{loss}_s{fit}_{method}_H10',status='complete',success=source['ordinal']%2==0))
 assert selection.choose_development(rows,sources)['chosen_loss']=='L00'
 try:selection.choose_development(rows[:-1],sources)
 except ValueError:pass
 else:raise AssertionError('missing dev allowed')
 selection.ROOT=n;selection.ORIGINAL=o;selection.SELECTION_ROOT=o;selection.EVIDENCE_ROOTS=(o,n)
 publication_data.load_evidence=lambda *a,**kw:([],[],[],rows)
 chosen=selection.make_selection();assert chosen['fixed_fit_seed']==9101 and chosen['test_used'] is False
 for name in ['SELECTION.json','SELECTION_LOCK.json']:(n/name).symlink_to(o/name)
 before=sha(o/'SELECTION.json');assert selection.make_selection()['chosen_loss']=='L00' and sha(o/'SELECTION.json')==before
 checks.append('real_dev_selector_complete_only_common_loss9101_immutable_synthetic')
 transfer.ROOT=n;transfer.ORIGINAL=o;transfer.CAMPAIGN=b;transfer.original_exit_verified=lambda:dict(synthetic=True,normal_exit=True)
 (b/'deadline_20260924').mkdir()
 name='deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json'
 (b/name).write_bytes((CAMPAIGN/name).read_bytes());(n/'JOB_INDEX.json').write_bytes((ROOT/'JOB_INDEX.json').read_bytes())
 proof=transfer.publish_transfer()
 assert proof['source_units_total']==4000 and len(proof['nodes']['B']['units'])==len(proof['nodes']['C']['units'])==2000
 assert {j['H'] for j in proof['owners']['B']}=={20,30} and {j['H'] for j in proof['owners']['C']}=={40,50}
 assert transfer.publish_transfer()==proof
 checks.append('real_transfer_publisher_4000_disjoint_units_dedup_synthetic')

manager=ast.parse((ROOT/'code/manager.py').read_text())
calls=[n for n in ast.walk(manager) if isinstance(n,ast.Call)]
assert not any(isinstance(n.func,ast.Name) and n.func.id=='publish_ensembles' for n in calls)
assert 'train_pair.py' not in (ROOT/'code/manager.py').read_text()
assert (ROOT/'code/controller.py').read_bytes()==(ORIGINAL/'code/controller.py').read_bytes()
assert (ROOT/'code/numeric_engine.py').read_bytes()==(ORIGINAL/'code/numeric_engine.py').read_bytes()
assert (ROOT/'code/resident_worker.py').read_bytes()==(ORIGINAL/'code/resident_worker.py').read_bytes()
checks.append('no_training_entry_and_actual_science_worker_controller_engine_unchanged')
assert not list((ROOT/'unit_claims').glob('*.json'))
new_json(ROOT/'TARGETED_CPU_CHECK.json',dict(status='PASS',utc=utc(),checks=checks,count=len(checks),synthetic_model_environment_hardware_calls=0,actual_scientific_compute=0,real_claims_created=0,large_weight_hashes=0))
print(json.dumps(dict(status='PASS',checks=checks)))
