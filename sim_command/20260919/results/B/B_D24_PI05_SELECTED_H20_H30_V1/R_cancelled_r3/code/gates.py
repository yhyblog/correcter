"""Live authority and scientific dependencies; CPU only, no launch side effects."""
import socket,time
from fractions import Fraction
from pathlib import Path
from qio import read,sha,same_process
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=C/'results/B/B_D24_PI05_SELECTED_H20_H30_V1'
A=C/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1'
AH=C/'results/A/A_D24_FULL_Q_AUTORUN_HANDOFF_V2'
TASK=P.name
AUTH='fb15e23ad4ed75eaa1b9490784d58dc9dc925e440194e99cab066ae11af6414f'
POST_AUTH='fa907477112320e7f8356282c5ba64742452172dee998e9efc20a82b92b9c4b1'
LOSSES=['L00','L10','L01','L11']

def authority():
 g=C/'deadline_20260924/FULL_Q_AUTORUN_AUTHORIZATION_V2.json'
 if sha(g)!=AUTH:raise ValueError('autorun authorization changed')
 a=read(g);control=read(C/'CONTROL.json');q=read(C/'persistent_queue/CONTROL.json')
 if a['status']!='released' or a['nodes']['B']['task_id']!=TASK:raise ValueError('task grant mismatch')
 if control.get('stop_requested') or q.get('global_stop') or not q['nodes']['B']['enabled']:raise ValueError('live stop/disabled')
 if TASK not in control['allowed_task_ids'] or not any(v.get('sha256')==AUTH for v in q['stage_authorizations']):raise ValueError('task not currently registered')
 if socket.gethostname()!=control['roles']['B']['hostname']:raise ValueError('host mismatch')
 if sha(C/'deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json')!=POST_AUTH:raise ValueError('Post-only directive changed')
 return a

def validate_post_choice(row):
 if row.get('status')!='selected_locked' or row.get('chosen_loss') not in LOSSES or row.get('fixed_fit_seed')!=9101 or row.get('test_used') is not False:
  raise ValueError('incomplete/unlocked/nonfixed scientific choice')
 # The published rule must explicitly identify Post-only selection.
 rule=str(row.get('selection_rule','')).lower().replace('_',' ').replace('-',' ')
 explicit=(row.get('Post_only') is True or row.get('post_only') is True or row.get('selection_branch')=='Post'
  or ('post' in rule and ('only' in rule or '仅' in rule)))
 if not explicit:raise ValueError('selection does not declare current Post-only rule')
 scores=[s for s in row.get('scores',[]) if s.get('method',s.get('branch'))=='Post']
 expected=read(A/'SOURCE_INDEX.json')['source_sets']['DEV'];tasks=sorted({r['task'] for r in expected})
 if len(expected)!=100 or len(tasks)!=5:raise ValueError('development source set')
 keys=[(s['loss'],s['fit_seed'],s['task']) for s in scores]
 required={(loss,fit,task) for loss in LOSSES for fit in [9101,9102,9103] for task in tasks}
 if len(keys)!=60 or set(keys)!=required:raise ValueError('complete 4x3x5 Post development cells required')
 totals={loss:Fraction(0) for loss in LOSSES}
 for s in scores:
  if s['valid']!=20 or type(s['successes']) is not int or not 0<=s['successes']<=20:raise ValueError('unequal/incomplete dev denominator')
  totals[s['loss']]+=Fraction(s['successes'],300)
 aux={'L00':0,'L10':1,'L01':1,'L11':2}
 winner=min(LOSSES,key=lambda k:(-totals[k],aux[k],LOSSES.index(k)))
 if row['chosen_loss']!=winner:raise ValueError('published choice disagrees with fixed Post-only development rule')
 if any(row.get(k,0) for k in ['Post_development_missing','post_development_missing','Post_development_unresolved']):
  raise ValueError('published Post development unresolved')
 return row

def selection():
 source=A/'SELECTION.json';lock=A/'SELECTION_LOCK.json'
 if not source.is_file() or not lock.is_file():raise FileNotFoundError('A Post-only selection/lock pending')
 s=read(source);l=read(lock)
 if l['selection']['sha256']!=sha(source):raise ValueError('selection lock hash mismatch')
 validate_post_choice(s)
 e=s['ensemble']
 if e['loss']!=s['chosen_loss'] or e['fit_seed']!=9101 or len(e['member_hashes'])!=4:raise ValueError('pi05 selected four-member ensemble')
 if Path(e['assets']).resolve()!= (A/'ensembles'/f"{s['chosen_loss']}_s9101").resolve():raise ValueError('pi05 assets must come from A, never Smol/X')
 return s

def transfer():
 s=selection();path=AH/'TRANSFER_READY.json'
 if not path.is_file():raise FileNotFoundError('A source-exact TRANSFER_READY pending')
 t=read(path)
 if t.get('status')!='TRANSFER_READY' or t.get('old_manager_cannot_dispatch') is not True or t.get('A_new_manager_contains_remote_jobs') is not False:
  raise ValueError('transfer lacks dispatch exclusion')
 if t['selection']['sha256']!=sha(A/'SELECTION.json') or t['chosen_loss']!=s['chosen_loss'] or t['fixed_fit_seed']!=9101:raise ValueError('transfer selection mismatch')
 n=t['nodes']['B'];units=n['units']
 if n['task_id']!=TASK or n['Hs']!=[20,30] or len(units)!=n['first_count'] or len(units)>2000:raise ValueError('B ownership scope')
 uids=[v['unit_id'] for v in units]
 if len(uids)!=len(set(uids)) or set(uids)&{v['unit_id'] for v in t['nodes'].get('C',{}).get('units',[])}:raise ValueError('cross-node ownership collision')
 if set(uids)&{v['unit_id'] for v in t.get('excluded_A_units',[])}:raise ValueError('excluded A unit included')
 plan={x['job_id']:x for x in read(P/'PLANNED_OWNERSHIP.json')['jobs']}
 jobs={x['job_id']:x for x in n['jobs']}
 if len(jobs)!=len(n['jobs']) or not set(jobs)<=set(plan):raise ValueError('transferred job outside frozen B plan')
 seen=set()
 for jid,j in jobs.items():
  original=read(plan[jid]['path'])
  if j['sha256']!=plan[jid]['sha256'] or sha(plan[jid]['path'])!=j['sha256']:raise ValueError('original job changed')
  for source in j['sources']:
   uid=original['cell_id']+'__'+source['source_id']
   if source not in original['sources'] or uid in seen:raise ValueError('source changed/duplicate')
   seen.add(uid)
   if any((ar/'unit_claims'/(uid+'.json')).exists() or (ar/'claims'/(jid+'.json')).exists() for ar in (A,AH)):
    raise ValueError('A already owns transferred unit '+uid)
 if seen!=set(uids):raise ValueError('job/unit transfer mismatch')
 return t

def family_exited(root):
 root=Path(root)
 if not (root/'RESULT.json').is_file():return False
 t=read(root/'RESULT.json')
 if not t.get('all_owned_descendants_exited') or not t.get('occupancy_handoff_complete'):return False
 for name in ['CLAIM.json','QUEUE_CLAIM.json','DAEMON_READY.json']:
  if not (root/name).is_file():continue
  process=read(root/name)['process'];process=dict(process,host=process.get('host',process.get('hostname')))
  if same_process(process):return False
 return True
