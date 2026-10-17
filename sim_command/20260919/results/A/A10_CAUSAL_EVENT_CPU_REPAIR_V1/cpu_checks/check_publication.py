"""Synthetic V2 metadata-only fixtures; never load real authorization/claim."""
import copy,hashlib,importlib.abc,json,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];B=P.parents[2]
sys.path.insert(0,str(P/'code'))
FORBIDDEN={'torch','numpy','ctypes','mujoco','metaworld','gymnasium','pynvml','OpenGL','runtime_engine','numeric_setup','dg_models','launch','diagnostic','reserved'}
class BlockHeavy(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in FORBIDDEN:raise AssertionError('Forbidden publication fixture import: '+fullname)
sys.meta_path.insert(0,BlockHeavy())
from core.contracts import validate_metadata,ContractError,write_new,sha,read
from publication_check import check
WORK=Path(sys.argv[1]);WORK.mkdir(exist_ok=False)
p=read(P/'proposal/PROPOSAL.json');p['_sha256']=sha(P/'proposal/PROPOSAL.json')
control=read(P/'proposal/CONTROL_REQUIRED.json')['fields'];control['synthetic']=True
board=dict(tasks=[read(P/'proposal/BOARD_TASK_TEMPLATE.json')],synthetic=True)
template=read(P/'proposal/RELEASE_TEMPLATE.json');assert template['status']=='UNAUTHORIZED_TEMPLATE'
release=copy.deepcopy(template);release['status']='released';release['synthetic']=True
path=Path(p['required_release_path']);assert not path.exists()
checks=[]
def case(name,mutate,accepted):
    c,b,r=copy.deepcopy((control,board,release));host=p['owner_host']
    update=mutate(c,b,r)
    if update is not None:host=update
    error=None
    try:validate_metadata(c,b,r,p,path,host);passed=True
    except ContractError as e:passed=False;error=str(e)
    assert passed==accepted,(name,passed,error)
    checks.append(dict(name=name,status='PASS',synthetic=True,accepted=passed,refusal=error))
case('ready_released_same_source',lambda c,b,r:None,True)
case('running_released_same_source',lambda c,b,r:b['tasks'][0].update(status='running'),True)
case('board_released_rejected',lambda c,b,r:b['tasks'][0].update(status='released'),False)
case('template_not_authorization',lambda c,b,r:r.update(status='UNAUTHORIZED_TEMPLATE'),False)
case('old_release_rejected',lambda c,b,r:r.update(release_id='P10_A_CAUSAL_C10_PREFLIGHT_V1'),False)
case('closed_release_rejected',lambda c,b,r:c['closed_compute_releases'].append(dict(release_id=r['release_id'])),False)
case('wrong_task_rejected',lambda c,b,r:r.update(task_id='A10_CAUSAL_C10_PREFLIGHT_V1'),False)
case('wrong_revision_rejected',lambda c,b,r:r.update(task_revision=2),False)
case('wrong_host_rejected',lambda c,b,r:'synthetic-other-host',False)
case('wrong_run_rejected',lambda c,b,r:r.update(run_id='synthetic-wrong-run'),False)
case('wrong_wave_rejected',lambda c,b,r:r.update(wave_id='synthetic-wrong-wave'),False)
case('wrong_shard_rejected',lambda c,b,r:r.update(shard_id='synthetic-wrong-shard'),False)
case('changed_caps_rejected',lambda c,b,r:r['resource_caps'].update(vla_sampling_calls=8),False)
case('changed_proposal_SHA_rejected',lambda c,b,r:r.update(proposal_sha256='0'*64),False)
case('changed_handoff_rejected',lambda c,b,r:r['occupancy_handoff'].update(required_value='90'),False)
current=read(B/'CONTROL.json')
try:validate_metadata(current,board,release,p,path,p['owner_host'])
except ContractError as e:checks.append(dict(name='current_prepare_CONTROL_rejected',status='PASS',synthetic=True,accepted=False,refusal=str(e)))
else:raise AssertionError('Current CPU-only CONTROL accepted compute')
assert len(control['closed_compute_releases'])==9
assert control['current_compute_limits']==release['resource_caps']==p['resource_caps']
assert len(p['resource_caps'])==111
assert board['tasks'][0]['id']==release['task_id']==p['task_id']
for name,value in [('CONTROL.fixture.json',control),('BOARD.fixture.json',board),('RELEASE.fixture.json',release)]:write_new(WORK/name,value)
command=['/usr/bin/python3','-I','-S','-B',str(P/'code/publication_check.py'),
    '--control',str(WORK/'CONTROL.fixture.json'),'--board',str(WORK/'BOARD.fixture.json'),'--release',str(WORK/'RELEASE.fixture.json')]
run=subprocess.run(command,cwd=P,capture_output=True,text=True,timeout=30)
write_new(WORK/'CLI_RUN.json',dict(synthetic=True,command=command,cwd=str(P),returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,scope='metadata only; no load_authorization/full/claim'))
assert run.returncode==0 and json.loads(run.stdout)['status']=='PASS'
paths=read(P/'proposal/PATHS.json')['paths'];assert all(not Path(x).exists() for x in paths.values())
assert not any(k.split('.')[0] in FORBIDDEN for k in sys.modules)
write_new(WORK/'RESULT.json',dict(status='PASS',synthetic=True,checks=checks,check_count=len(checks),pure_JSON_CLI_passed=True,
    source_templates_unchanged=True,real_release_or_claim_created=False,real_launcher_invocations=0,hardware_imports=[],large_weights_hashed=0))
print(json.dumps(dict(status='PASS',checks=len(checks),CLI='PASS',result=str(WORK/'RESULT.json'))))
