"""CPU checks for this override only, no model/environment/hardware calls."""
import ast,copy,json,tempfile
from pathlib import Path
import admission,selection,publication_data,transfer
from paths import ROOT,ORIGINAL,PREVIOUS,PRIOR_EVIDENCE_ROOTS,POST_OVERRIDE_SHA
from qio import read,new_json,sha,utc

checks=[]
for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
plan=read(ROOT/'RESUME_PLAN.json');jobs=[read(x['path']) for x in read(ROOT/'JOB_INDEX.json')['jobs']]
old={p.stem for root in PRIOR_EVIDENCE_ROOTS for p in (root/'unit_claims').glob('*.json')}
units={j['cell_id']+'__'+s['source_id'] for j in jobs for s in j['sources']}
assert len(old)==1880 and len(units)==plan['new_first']==3720 and not units.intersection(old)
assert plan['remaining_DEV_first']==520 and plan['new_attempt_cap']==4166 and plan['prior_A_attempts']==16776
assert {j['H'] for j in jobs if j['stage']=='MAIN'}=={10}
for j in jobs:admission.validate_job(j,stage_gate=False)
checks.append('real_frozen_metadata_520_unentered_DEV_3200_tests_no1880_replay')
_,rows,claims,_=publication_data.load_evidence();assert len(rows)==len(claims)==1880
assert all(x['status']=='complete' for x in rows)
checks.append('real_three_root_reader_preserves1880_valid_DEV')
assert len(transfer.original_exit_verified()['prior_families'])==2
checks.append('both_actual_prior_formal_families_exited_no_joint_lock')
sources=read(ROOT/'SOURCE_INDEX.json')['source_sets']['DEV'];rows=[]
for loss,n in [('L00',6),('L10',14),('L01',8),('L11',13)]:
 for fit in [9101,9102,9103]:
  for method in ['Post','Velocity']:
   for source in sources:
    rows.append(dict(source,stage='DEV',cell_id=f'DEV_{loss}_s{fit}_{method}_H10',method=method,status='complete',success=source['ordinal']<n if method=='Post' else loss=='L00'))
choice=selection.choose_development(rows,sources)
assert choice['chosen_loss']=='L10' and choice['selection_valid']==1200 and choice['loss_scores']['L10']['equal_weight_score']==.7
assert choice['Post_only'] and choice['Velocity_selection_weight']==0 and choice['fixed_fit_seed']==9101
changed=copy.deepcopy(rows)
for row in changed:
 if row['method']=='Velocity':row['success']=not row['success']
assert selection.choose_development(changed,sources)['chosen_loss']=='L10'
assert selection.choose_development([r for r in rows if r['method']=='Post'],sources)['chosen_loss']=='L10'
try:selection.choose_development(rows[1:],sources)
except ValueError:pass
else:raise AssertionError('incomplete Post development selected')
ties=copy.deepcopy(rows)
for row in ties:
 if row['method']=='Post':row['success']=row['ordinal']<10
assert selection.choose_development(ties,sources)['chosen_loss']=='L00'
checks.append('real_Post_only_score_V_flips_no_effect_missing_Post_rejected_fixed_tie_fit')
try:admission.validate_job(next(j for j in jobs if j['stage']=='MAIN'))
except FileNotFoundError:pass
else:raise AssertionError('test admitted before selection')
checks.append('actual_test_gate_rejects_absent_selection')

with tempfile.TemporaryDirectory(prefix='corrector_post_selection_') as temp:
 t=Path(temp);o=t/'old';n=t/'new';o.mkdir();n.mkdir()
 for name in ['ENSEMBLES.json','TRAINING_COMPLETE.json','SOURCE_INDEX.json','RESUME_PLAN.json']:(n/name).write_bytes((ROOT/name).read_bytes())
 (o/'TRAINING_COMPLETE.json').write_bytes((ORIGINAL/'TRAINING_COMPLETE.json').read_bytes())
 selection.ROOT=n;selection.ORIGINAL=o;selection.SELECTION_ROOT=o
 publication_data.load_evidence=lambda *args,**kwargs:([],[],[],rows)
 selected=selection.make_selection()
 for name in ['SELECTION.json','SELECTION_LOCK.json']:(n/name).symlink_to(o/name)
 assert selection.locked_selection()['chosen_loss']=='L10'
 digest=sha(o/'SELECTION.json');assert selection.make_selection()['chosen_loss']=='L10' and sha(o/'SELECTION.json')==digest
 bad=t/'joint';bad.mkdir();joint=dict(selected,Post_only=False,Velocity_selection_weight=1)
 new_json(bad/'SELECTION.json',joint);new_json(bad/'SELECTION_LOCK.json',dict(selection=dict(sha256=sha(bad/'SELECTION.json'))))
 selection.ROOT=bad
 try:selection.locked_selection()
 except ValueError:pass
 else:raise AssertionError('old joint lock accepted')
 checks.append('real_publisher_immutable_Post_choice_and_valid_SHA_joint_lock_rejected_synthetic')

report=ast.parse((ROOT/'code/report.py').read_text())
for filename,var in [('FINAL_CELLS.csv','cells'),('FINAL_EPISODES.csv','rows')]:
 call=next(n for n in ast.walk(report) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='write_csv' and isinstance(n.args[0],ast.BinOp) and isinstance(n.args[0].right,ast.Constant) and n.args[0].right.value==filename)
 result=eval(compile(ast.Expression(call.args[1]),'actual_paper_filter','eval'),{var:[dict(method='Velocity'),dict(method='Post')]})
 assert result==[dict(method='Post')]
checks.append('actual_FINAL_table_AST_filters_Velocity_to_other_work')
for name in ['controller.py','numeric_engine.py','resident_worker.py']:
 assert (ROOT/'code'/name).read_bytes()==(PREVIOUS/'code'/name).read_bytes()
assert 'train_pair.py' not in (ROOT/'code/manager.py').read_text()
checks.append('scientific_worker_controller_engine_unchanged_no_training_entry')
new_json(ROOT/'TARGETED_CPU_CHECK.json',dict(status='PASS',utc=utc(),override_sha256=POST_OVERRIDE_SHA,checks=checks,count=len(checks),scientific_compute=0,new_claims=0,new_training=0,large_weight_hashes=0))
print(json.dumps(dict(status='PASS',checks=checks)))
