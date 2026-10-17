"""Pure-JSON fixture checks; no release publication, launcher or claim."""
import copy,hashlib,importlib.abc,json,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'torch','numpy','ctypes','mujoco','metaworld','gymnasium','pynvml','OpenGL'}:raise AssertionError('Forbidden CPU import '+fullname)
sys.meta_path.insert(0,Block())
from publication_check import check
from core.contracts import read,ContractError,TASK,RELEASE,CAMPAIGN
W=Path(sys.argv[1]);W.mkdir(exist_ok=False)
p=read(P/'proposal/PROPOSAL.json');p['_sha256']=hashlib.sha256((P/'proposal/PROPOSAL.json').read_bytes()).hexdigest()
c=read(P/'proposal/CONTROL_REQUIRED.json')['fields'];c['closed_compute_releases']=[]
b=dict(tasks=[read(P/'proposal/BOARD_TASK_TEMPLATE.json')]);r=read(P/'proposal/RELEASE_TEMPLATE.json');r['status']='released'
rows=[]
def test(name,change,want):
 cc,bb,rr=copy.deepcopy(c),copy.deepcopy(b),copy.deepcopy(r);change(cc,bb,rr)
 try:check(cc,bb,rr,p);accepted=True;error=None
 except ContractError as e:accepted=False;error=str(e)
 assert accepted==want,(name,accepted,want,error)
 rows.append(dict(name=name,status='PASS',accepted=accepted,error=error))
test('ready_accepted',lambda c,b,r:None,True)
test('running_accepted',lambda c,b,r:b['tasks'][0].update(status='running'),True)
test('board_released_rejected',lambda c,b,r:b['tasks'][0].update(status='released'),False)
test('unauthorized_template_rejected',lambda c,b,r:r.update(status='unauthorized_template'),False)
test('old_release_rejected',lambda c,b,r:r.update(release_id='P10_A_PV_OFFLINE_PREFLIGHT_V3'),False)
test('wrong_task_rejected',lambda c,b,r:r.update(task_id='A10_PV_OFFLINE_PREFLIGHT_V3'),False)
test('wrong_run_rejected',lambda c,b,r:r.update(run_id='some_other_run'),False)
test('wrong_revision_rejected',lambda c,b,r:r.update(task_revision=2),False)
test('closed_list_rejected',lambda c,b,r:c['closed_compute_releases'].append(dict(release_id=RELEASE)),False)
test('closed_status_rejected',lambda c,b,r:r.update(status='closed'),False)
test('wrong_host_rejected',lambda c,b,r:r.update(owner_host='B'),False)
test('wrong_wave_rejected',lambda c,b,r:r.update(wave_participants=['A','B']),False)
test('changed_cap_rejected',lambda c,b,r:r['resource_caps'].update(env_steps=33),False)
test('changed_device_rejected',lambda c,b,r:r['device'].update(gpu_index=1),False)
test('wrong_identity_metadata_rejected',lambda c,b,r:r['authorization_identity'].update(shard_id='stale'),False)
test('wrong_handoff_rejected',lambda c,b,r:c['active_occupancy_handoff'].update(required_value='90'),False)
test('stopped_control_rejected',lambda c,b,r:c.update(stop_requested=True),False)
test('duplicate_board_rejected',lambda c,b,r:b['tasks'].append(copy.deepcopy(b['tasks'][0])),False)
test('current_prepare_control_rejected',lambda c,b,r:c.update(read(CAMPAIGN/'CONTROL.json')),False)
for name,value in [('CONTROL.json',c),('TASK_BOARD.json',b),('RELEASE.json',r)]:
 (W/name).write_text(json.dumps(value,indent=2)+'\n')
(W/'RESULT.json').write_text(json.dumps(dict(status='PASS',checks=rows,hardware_imports=0,launches=0,claims=0,only_fixtures_written=True),indent=2)+'\n')
print(json.dumps(dict(status='PASS',checks=len(rows),result=str(W/'RESULT.json'))))
