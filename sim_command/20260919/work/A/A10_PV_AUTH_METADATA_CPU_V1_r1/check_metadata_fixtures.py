"""Targeted authorization metadata checks only; never call claim or launcher."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
NEW = B/'results/A/A10_PV_AUTH_METADATA_CPU_V1'
WORK = B/'work/A/A10_PV_AUTH_METADATA_CPU_V1_r1'
FIX = WORK/'metadata_fixtures'
FIX.mkdir(exist_ok=False)
forbidden_events = []

def audit(event, args):
    if event == 'import' and args[0].split('.')[0] in {'torch','numpy','ctypes','pynvml','OpenGL','mujoco','metaworld','lerobot'}:
        forbidden_events.append(dict(event=event, name=args[0]))
        raise AssertionError('Forbidden model/hardware import')
    if event.startswith('ctypes.') or event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork'}:
        forbidden_events.append(dict(event=event))
        raise AssertionError('Forbidden process or driver operation in metadata check')
    if event == 'open' and isinstance(args[0],str) and Path(args[0]).suffix in {'.safetensors','.pt','.pth','.npy','.npz','.so'}:
        forbidden_events.append(dict(event=event, path=args[0]))
        raise AssertionError('Model/binary/array file read outside metadata scope')

sys.addaudithook(audit)
sys.path.insert(0,str(NEW/'code'))
from core import contracts as C

def no_call(*args, **kwargs):
    raise AssertionError('Claim/full verifier forbidden in CPU task')

C.claim = no_call
C.verify_ref = no_call

def put(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:
        f.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

def get(path):
    return json.loads(path.read_text())

p = get(NEW/'proposal/PROPOSAL.json')
p['_sha256'] = hashlib.sha256((NEW/'proposal/PROPOSAL.json').read_bytes()).hexdigest()
identity = get(NEW/'proposal/IDENTITY.json')
requirements = get(NEW/'proposal/CONTROL_REQUIRED.json')
template = get(NEW/'proposal/RELEASE_TEMPLATE.json')
board_entry = get(NEW/'proposal/BOARD_TASK_TEMPLATE.json')
assert board_entry == requirements['board_task']
control = get(WORK/'ack_snapshots/CONTROL.json')
for key in ['mode','formal_gpu_runs_enabled','stop_requested','active_compute_release_id','active_compute_release','active_compute_task_ids','current_compute_limits','per_task_compute_limits']:
    control[key] = copy.deepcopy(requirements[key])
control['allowed_task_ids'].append(C.TASK)
control['fixture_only_not_authorization'] = True
board = get(WORK/'ack_snapshots/TASK_BOARD.json')
board['tasks'].append(board_entry)
board['fixture_only_not_authorization'] = True
release = copy.deepcopy(template)
release['status'] = 'released'
release['fixture_only_not_authorization'] = True
host = p['owner_host']
release_path = Path(identity['release_path'])
base = dict(control=control,board=board,release=release,proposal=p,release_path=str(release_path),hostname=host)
put(FIX/'CONTROL_CANDIDATE.json',control)
put(FIX/'TASK_BOARD_CANDIDATE.json',board)
put(FIX/'RELEASE_CANDIDATE.json',release)
case_results = []

def case(name, edit=None, accepted=False):
    item = copy.deepcopy(base)
    if edit:
        edit(item)
    expected = 'accepted' if accepted else 'rejected'
    try:
        assert C.validate_metadata(**item) is True
        actual, error = 'accepted', None
    except C.ContractError as e:
        actual, error = 'rejected', str(e)
    assert actual == expected, (name,actual,expected)
    record = dict(case=name,expected=expected,actual=actual,error=error)
    put(FIX/'cases'/(name+'.json'),dict(fixture_only_not_authorization=True,inputs=item,result=record))
    case_results.append(record)

def board_task(x):
    return next(t for t in x['board']['tasks'] if t.get('id') == C.TASK)

case('V2_board_ready',accepted=True)
case('V2_board_running',lambda x:board_task(x).update(status='running'),accepted=True)
case('board_released_rejected',lambda x:board_task(x).update(status='released'))
case('board_owner_wrong',lambda x:board_task(x).update(owner='B'))
case('board_revision_wrong',lambda x:board_task(x).update(revision=2))
case('board_release_wrong',lambda x:board_task(x).update(release='releases/P10_A_PV_OFFLINE_PREFLIGHT_V1.json'))
case('board_duplicate_task',lambda x:x['board']['tasks'].append(copy.deepcopy(board_task(x))))
case('board_missing_task',lambda x:board_task(x).update(id='wrong'))
case('control_campaign_wrong',lambda x:x['control'].update(campaign_id='wrong'))
case('control_mode_prepare',lambda x:x['control'].update(mode='prepare'))
case('control_compute_disabled',lambda x:x['control'].update(formal_gpu_runs_enabled=False))
case('control_stop_requested',lambda x:x['control'].update(stop_requested=True))
case('control_active_release_wrong',lambda x:x['control'].update(active_compute_release_id='P10_A_PV_OFFLINE_PREFLIGHT_V1'))
case('control_active_task_wrong',lambda x:x['control'].update(active_compute_task_ids=['A10_PV_OFFLINE_PREFLIGHT_V1']))
case('control_active_task_not_unique',lambda x:x['control'].update(active_compute_task_ids=[C.TASK,'B10']))
case('control_release_path_wrong',lambda x:x['control'].update(active_compute_release='releases/P10_A_PV_OFFLINE_PREFLIGHT_V1.json'))
case('control_task_not_allowed',lambda x:x['control']['allowed_task_ids'].remove(C.TASK))
case('control_global_caps_wrong',lambda x:x['control']['current_compute_limits'].update(flow_forward_calls=11))
case('control_task_caps_wrong',lambda x:x['control']['per_task_compute_limits'][C.TASK].update(flow_forward_calls=11))
case('control_task_caps_missing',lambda x:x['control'].update(per_task_compute_limits={}))
case('closed_release_in_control',lambda x:x['control']['closed_compute_releases'].append(dict(release_id=C.RELEASE,closure='fixture_only')))
case('release_template_is_not_authorized',lambda x:x['release'].update(status='UNAUTHORIZED_TEMPLATE'))
case('release_old_V1_identity',lambda x:x['release'].update(task_id='A10_PV_OFFLINE_PREFLIGHT_V1',release_id='P10_A_PV_OFFLINE_PREFLIGHT_V1'))
case('release_revision_wrong',lambda x:x['release'].update(task_revision=2))
case('release_caps_wrong',lambda x:x['release']['resource_caps'].update(critic_forward_calls=41))
case('release_host_wrong',lambda x:x['release'].update(owner_host='wrong-host'))
case('actual_host_wrong',lambda x:x.update(hostname='wrong-host'))
case('release_device_wrong',lambda x:x['release']['device'].update(gpu_index=1))
case('release_cuda_environment_wrong',lambda x:x['release']['cuda_environment'].update(CUDA_VISIBLE_DEVICES='0'))
case('release_timeout_wrong',lambda x:x['release'].update(timeout_seconds=1801))
case('release_grace_wrong',lambda x:x['release'].update(kill_grace_seconds=31))
case('release_extra_wave_participant',lambda x:x['release'].update(wave_participants=['A','B']))
case('release_retry_wrong',lambda x:x['release'].update(max_retries=1))
for key in ['proposal_sha256','code_manifest_sha256','input_manifest_sha256','config_sha256','external_source_manifest_sha256']:
    case(key+'_wrong',lambda x,k=key:x['release'].update({k:'0'*64}))
for key in ['run_id','wave_id','shard_id']:
    case(key+'_invalid',lambda x,k=key:x['release'].update({k:'../invalid'}))

# Actual early authorization guards with a synthetic campaign root only.
# No launcher, full verifier, real release or claim function is called.
original_campaign = C.CAMPAIGN
fake_campaign = FIX/'closed_path_fixture'
(fake_campaign/'releases').mkdir(parents=True)
put(fake_campaign/'releases'/(C.RELEASE+'_CLOSED.json'),dict(fixture_only_not_authorization=True,status='closed'))
guard_results = []
try:
    C.CAMPAIGN = fake_campaign
    for name,path,expected_message in [
        ('old_V1_path_rejected',fake_campaign/'releases/P10_A_PV_OFFLINE_PREFLIGHT_V1.json','Only the designated new analysis release is accepted'),
        ('closure_file_rejected',fake_campaign/'releases'/(C.RELEASE+'.json'),'Release closure exists'),
    ]:
        try:
            C.load_authorization(path,full=False)
            raise AssertionError('Authorization guard did not reject')
        except C.ContractError as error:
            assert str(error)==expected_message
            guard_results.append(dict(case=name,actual='rejected',error=str(error),synthetic_campaign_root=str(fake_campaign)))
finally:
    C.CAMPAIGN = original_campaign

# Repeated-claim protection uses the unchanged actual write_new exclusive mode.
# Exercise only write_new against a pre-existing synthetic marker, NOT claim().
marker = FIX/'existing_exclusive_write_marker.json'
put(marker,dict(fixture_only=True,marker='must remain unchanged'))
before = marker.read_bytes()
try:
    C.write_new(marker,dict(forbidden_replacement=True))
    raise AssertionError('Exclusive write accepted existing file')
except FileExistsError:
    pass
assert marker.read_bytes()==before
tree = ast.parse((NEW/'code/core/contracts.py').read_text())
claim_node = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='claim')
writer_node = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='write_new')
assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='write_new' for n in ast.walk(claim_node))
assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='open' and len(n.args)==1 and isinstance(n.args[0],ast.Constant) and n.args[0].value=='x' for n in ast.walk(writer_node))
guard_results.append(dict(case='duplicate_claim_exclusive_writer_semantics',actual='rejected_FileExistsError',marker_unchanged=True,claim_function_invocations=0,proof='actual unchanged write_new plus claim AST call-site, synthetic marker only'))

spec = importlib.util.spec_from_file_location('publication_checker',NEW/'commands/check_publication_metadata_cpu.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
entry_result = checker.check(FIX/'CONTROL_CANDIDATE.json',FIX/'TASK_BOARD_CANDIDATE.json',FIX/'RELEASE_CANDIDATE.json',release_path,host)
assert entry_result['status']=='PASS_METADATA_ONLY_NOT_AUTHORIZATION'
bad_board = copy.deepcopy(board)
next(t for t in bad_board['tasks'] if t.get('id')==C.TASK)['status']='released'
put(FIX/'TASK_BOARD_RELEASED_INVALID.json',bad_board)
try:
    checker.check(FIX/'CONTROL_CANDIDATE.json',FIX/'TASK_BOARD_RELEASED_INVALID.json',FIX/'RELEASE_CANDIDATE.json',release_path,host)
    raise AssertionError('Publication entry accepted released board status')
except C.ContractError as error:
    assert str(error)=='Task board mismatch'
    entry_rejection=dict(status='rejected',error=str(error))
assert not forbidden_events
result = dict(status='passed',scope='V2 identity/state/path metadata only; no numeric or whole-suite tests',pure_validator_cases=case_results,authorization_guard_checks=guard_results,publication_entry_pass=entry_result,publication_entry_rejection=entry_rejection,fixture_root=str(FIX),forbidden_audit_events=forbidden_events,real_launcher_invocations=0,claim_function_invocations=0,compute_release_claims=0,holder_queries=0,holder_stops=0,large_weight_hashes=0,model_array_binary_reads=0,torch_imports=0,dlopen_calls=0,algorithm_fake_suite_runs=0,deletions=0)
put(WORK/'METADATA_FIXTURE_RESULT.json',result)
print(json.dumps(dict(status='passed',validator_cases=len(case_results),guard_checks=len(guard_results),publication_entry_checks=2,real_launcher_invocations=0,compute_release_claims=0),indent=2))
