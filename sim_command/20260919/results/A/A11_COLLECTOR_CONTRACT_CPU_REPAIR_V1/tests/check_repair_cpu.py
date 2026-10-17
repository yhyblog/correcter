"""Only this repair: real serializers/recorder/controller/publishers, fake boundaries."""
import ast,copy,hashlib,importlib.util,json,os,sys,types
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'));sys.path.insert(0,str(P/'tests'))
import inheritance
import numpy as np
FORBIDDEN=('torch','mujoco','gymnasium','metaworld','pynvml','OpenGL')
def audit(event,args):
    if event=='import' and args[0].split('.')[0] in FORBIDDEN:raise AssertionError('forbidden runtime import '+args[0])
    if event in ('ctypes.dlopen','ctypes.dlsym','subprocess.Popen','os.system'):raise AssertionError('forbidden runtime action '+event)
sys.addaudithook(audit)
from core.contracts import ContractError,sha
from core.event_recorder import EventRecorder,EventIdentityConflict
from full_state import typed,snapshot,compare,REQUIRED
from state_attrs import capture_attrs,BoxBound
from controller import run_attempt
from pool_protocol import ARMS,digest
from storage import Store,StorageDenied
from storage_admission import metadata_bytes,exclusive_metadata,gate,PrivateMonitor,scan_private
from budget import STORAGE
from public_records import validate_public,make_transition,publish_transition,null_paths
from sidecar_output import aggregate
from audit_indices import validate_aggregate_index,private_cost_index,verify_member
from episode_identity import episode_id
import synthetic_adapter as fake
OUT=Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=False)
checks=[]
def check(name,predicate,detail=None):
    checks.append(dict(name=name,passed=bool(predicate),detail=detail))
    if not predicate:raise AssertionError(name)
def rejects(name,fn,kind=Exception):
    try:fn()
    except kind as e:check(name,True,dict(type=type(e).__name__,message=str(e)));return
    raise AssertionError(name+' accepted')
def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')

# Execute only the installed pure low/high construction AST with explicit fake Box.
source=Path('/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/lib/python3.12/site-packages/metaworld/sawyer_xyz_env.py')
tree=ast.parse(source.read_text());fn=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='sawyer_observation_space'][-1]
fn=copy.deepcopy(fn);fn.decorator_list=[];fn.returns=None
class FakeBox:
    def __init__(self,low,high,**kwargs):self.low=low;self.high=high;self.dtype=low.dtype;self.shape=low.shape
class FakeDict:
    def __init__(self,spaces):self.spaces=spaces
ns={'np':np,'Box':FakeBox}
exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(source),'exec'),ns)
finite=FakeBox(np.array([-1.,-2.,-3.]),np.array([1.,2.,3.]))
box=ns['sawyer_observation_space'](types.SimpleNamespace(_partially_observable=False,goal_space=finite,_HAND_SPACE=finite))
spec=importlib.util.spec_from_file_location('old_full_state',inheritance.BASE_CODE/'full_state.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
rejects('old_serializer_rejects_installed_structure_low',lambda:old.typed(box.low),ContractError)
rejects('old_serializer_rejects_installed_structure_high',lambda:old.typed(box.high),ContractError)
check('synthetic_static_observation_shape_39_and_28_infinities',box.low.shape==(39,) and np.isneginf(box.low).sum()==28 and np.isposinf(box.high).sum()==28)
attrs=capture_attrs(FakeDict({'observation':box}),box_type=FakeBox,numpy=np,read_rng=lambda r:None,container_space_types=(FakeDict,))
groups={k:{} for k in REQUIRED};groups['task_python']=attrs
state=snapshot(groups);rows={r['name']:r['value'] for r in state['fields']}
low=rows['task_python.spaces.observation.low'];high=rows['task_python.spaces.observation.high']
check('Box_metadata_dtype_shape_raw_bytes',low['bytes']==box.low.tobytes().hex() and high['bytes']==box.high.tobytes().hex() and low['dtype']=='<f8' and low['shape']==[39])
check('Box_bitwise_full_compare_keeps_zero_tolerance',compare(state,state)['level']=='full_state_verified')
for name,value,field in [('NaN',np.array([np.nan]),'low'),('object',np.array([object()]),'low'),('complex',np.array([1j]),'low'),('wrong_field',np.array([np.inf]),'position')]:
    rejects('Box_reject_'+name,lambda value=value,field=field:typed(BoxBound('low',value),box_field=field),ContractError)
rejects('physical_array_infinity_rejected',lambda:typed(box.low),ContractError)
rejects('physical_scalar_infinity_rejected',lambda:typed(float('inf')),ContractError)
rejects('Box_wrong_field_in_physical_category',lambda:snapshot({**groups,'task_python':{},'integration':{'low':BoxBound('low',box.low)}}),ContractError)
rejects('unmarked_named_low_rejected',lambda:snapshot({**groups,'task_python':{'low':box.low}}),ContractError)
rejects('unknown_object_rejected',lambda:typed(object()),ContractError)
save('BOX_STATIC_SOURCE.json',dict(synthetic=True,source_path=str(source),source_sha256=sha(source),line=fn.lineno,
    constructed_only_pure_low_high=True,finite_hand_goal_are_synthetic=True,low=low,high=high,native_environment_calls=0))

# New modified production recorder + unchanged real controller + new publisher.
parent=OUT/'publisher';shared={};engines=[]
for job in ARMS:
    e=fake.FakeEngine(job,parent,shared)
    recorder=EventRecorder(e.out/'events.jsonl',branch=job[0],source_id=e.cfg['source']['source_id'],
        parent_source_id=e.cfg['source']['parent_source_id'],split='train',synthetic=True,writer=e.store)
    result=run_attempt(e,job,recorder,shared.get('reference'));engines.append(e)
    public=json.loads((e.out/'EPISODE_PUBLIC_V1.json').read_text());side=json.loads((e.out/'SIDECAR_V1.json').read_text())
    events=[json.loads(l) for l in (e.out/'events.jsonl').read_text().splitlines()]
    expected=episode_id(e.cfg['source']['parent_source_id'],job[0])
    check(job[0]+'_real_publisher_identity_nulls_and_private_cost_separation',
        public['episode_id']==side['identity']['episode_id']==expected and all(x['episode_id']==expected for x in events)
        and public['cost_event_refs']==[] and all(public['missing_reasons'].get(k) for k in null_paths(public))
        and public['source']['source_id']!=public['source']['parent_episode_id'] and result['controls']==300)
    verify_member(side)
    rejects(job[0]+'_reserved_identity_conflict',lambda:recorder.emit('conflict',episode_id='cross'),EventIdentityConflict)
e=engines[0];pub=json.loads((e.out/'EPISODE_PUBLIC_V1.json').read_text())
bad=copy.deepcopy(pub);bad['missing_reasons'].pop('train_seed')
rejects('real_publisher_missing_null_reason_refused',lambda:validate_public(bad),ContractError)
bad=copy.deepcopy(pub);bad['cost_event_refs']=['numeric_events.jsonl']
rejects('private_filename_not_public_UUID',lambda:validate_public(bad),ContractError)
bad=copy.deepcopy(pub);bad['episode_id']='cross_episode'
rejects('cross_episode_public_record_rejected',lambda:validate_public(bad),ContractError)

# Actual pure transition builder/publisher extracted from Engine.step; no runtime import.
raw=e.sample(0,'normal',None,0);key=digest(raw)
e.last_observation=fake.rr(Path(e.store.json('obs0.json',{'synthetic':True})['path']))
e.last_proprio=[0.,0.,0.,0.]
nextref=fake.rr(Path(e.store.json('obs1.json',{'synthetic':True})['path']))
t=make_transition(e,raw,0,[0.,0.,0.,0.],0.,False,False,False,0,key)
publish_transition(e,t,nextref,1)
check('actual_transition_all_nulls_explained',validate_public(t) and all(t['missing_reasons'].get(k) for k in null_paths(t)))
cross=copy.deepcopy(t);cross['observation_ref']=fake.rr(engines[1].out/'BRANCH_RESULT.json')
rejects('cross_episode_observation_ref_rejected',lambda:publish_transition(e,cross,nextref,1),ContractError)

reserved=parent/'reserved';reserved.mkdir();store=Store(reserved,record_limit=1024**2)
labels=aggregate(parent,store)
for key,label in labels.items():
    index=json.loads((reserved/('AGGREGATE_INDEX_'+key+'.json')).read_text());validate_aggregate_index(index)
    carrier=json.loads((reserved/('SIDECAR_AGGREGATE_'+key+'.json')).read_text())
    check('aggregate_'+key+'_all_member_index',carrier['plans']['physical_alias_of'] is None and carrier['repeats']['repeat_id'] is None
        and carrier['outcome']['reason']=='not_applicable' and carrier['restoration']['level']=='not_applicable' and label['target_mask'])
# Ineligible second repeat must not borrow the first member's qualification.
from pool_protocol import paired_label
records=json.loads((reserved/'PAIRED_LABELS.json').read_text())['records'];broken=copy.deepcopy(records)
next(r for r in broken if r['arm']=='local_minus' and r['repeat']==1)['restore_level']='unknown'
check('second_repeat_ineligible_masks_pair',not paired_label([r for r in broken if r['target']=='Q_C10'],['local_plus','local_minus'],'pair')['target_mask'])
bad=copy.deepcopy(index);bad['label_key']='pair' if key!='pair' else 'G0'
rejects('aggregate_label_key_mismatch_rejected',lambda:validate_aggregate_index(bad),ContractError)

early=fake.FakeEngine(ARMS[1],OUT/'early',shared,success_at=2)
r=EventRecorder(early.out/'events.jsonl',branch=early.job[0],source_id=early.cfg['source']['source_id'],parent_source_id=early.cfg['source']['parent_source_id'],synthetic=True,writer=early.store)
run_attempt(early,early.job,r,shared['reference'])
check('precut_branch_result_retained_with_explicit_sidecar_absence',(early.out/'BRANCH_RESULT.json').exists() and (early.out/'SIDECAR_MISSING.json').exists() and not (early.out/'SIDECAR_V1.json').exists())
store.json('PROCESS_GROUP_EXIT.json',dict(status='all_formal_group_members_exited',synthetic=True))
for e in engines:e.store.json('RESOURCE_LEDGER.json',dict(synthetic=True,note='fake no real compute; no fabricated native event series'))
private_cost_index(parent,store,synthetic=True)
cost=json.loads((reserved/'PRIVATE_COST_INDEX.json').read_text())
check('post_exit_private_cost_index_SHA_only',cost['public_cost_event_refs']==[] and not cost['public_UUID_bridge'] and all(r['resource_ledger_completed'] for r in cost['attempts']))

# Actual bounded metadata and store; only tiny synthetic files, never real paths.
command=dict(started=1.,release_sha256='a'*64,command_opportunity_consumed=True)
claim=dict(time=1.,release_sha256='a'*64,run_id='SYNTHETIC_V2',consumed=True,remaining_caps_reusable=False)
check('both_gate_JSON_serializations_below_4096',len(metadata_bytes(command,'command'))<=4096 and len(metadata_bytes(claim,'claim'))<=4096)
for kind,v in [('command',command),('claim',claim)]:
    path=OUT/(kind+'_SYNTHETIC_ONLY.json');exclusive_metadata(path,v,kind)
    rejects(kind+'_exclusive_duplicate_denied',lambda path=path,v=v,kind=kind:exclusive_metadata(path,v,kind),FileExistsError)
    rejects(kind+'_extra_field_denied',lambda v=v,kind=kind:metadata_bytes({**v,'payload':'x'*5000},kind),ContractError)
rejects('unbounded_claim_identity_refused',lambda:metadata_bytes({**claim,'run_id':'x'*5000},'claim'),ContractError)
rejects('NaN_metadata_clock_refused',lambda:metadata_bytes({**command,'started':float('nan')},'command'),ContractError)
s=dict(STORAGE);proposal=dict(storage=s,paths=dict(output='/SYNTHETIC/output',cache='/SYNTHETIC/cache'))
release=dict(identity=dict(run_id='SYNTHETIC_V2'),storage_admission=dict(mode='bounded_first_parent',run_id='SYNTHETIC_V2',project_quota_known=False,exclusive_reservation=False,accepts_monitoring_gaps=True))
capacity=lambda p:dict(device=1,available_bytes=10**12,available_inodes=100000)
check('first_parent_accepts_unknown_quota_without_reservation',gate(release,proposal,capacity)['exclusive_reservation'] is False)
rejects('low_space_before_any_hardware',lambda:gate(release,proposal,lambda p:dict(device=1,available_bytes=0,available_inodes=100000)),ContractError)
rejects('fake_exclusive_reservation_rejected',lambda:gate({**release,'storage_admission':{**release['storage_admission'],'reserved_bytes':10**12}},proposal,capacity),ContractError)
tiny=OUT/'tiny_temp';tiny.mkdir();(tiny/'payload').write_bytes(b'x'*17)
check('bounded_private_scan_actual_tiny_file',scan_private(tiny,2)['logical_file_bytes']==17)
monstore=Store(OUT/'monitor',byte_limit=128*1024,record_limit=4096,reserve_bytes=0);monstore.root.mkdir()
mon=PrivateMonitor(tiny,s,monstore,capacity_fn=capacity);mon.check();check('monitor_admits_17_bytes_reports_unknown_overshoot',mon.summary()['maximum_overshoot_bytes'] is None)
limited={**s,'private_temp_cache_budget_bytes':16}
rejects('temp_threshold_failure',lambda:PrivateMonitor(tiny,limited,monstore,capacity_fn=capacity).check(),ContractError)
rejects('temp_entry_scan_bound',lambda:scan_private(tiny,0),ContractError)
rejects('capacity_query_exception_fails_closed',lambda:gate(release,proposal,lambda p:(_ for _ in ()).throw(OSError('synthetic statvfs error'))),OSError)
writer=Store(OUT/'writer',byte_limit=20,record_limit=10,reserve_bytes=0)
writer.write('kept.bin',b'12345678')
rejects('controlled_record_bytes_hard_bound',lambda:writer.write('oversize.bin',b'x'*11),StorageDenied)
rejects('controlled_wave_bytes_hard_bound',lambda:(writer.write('second.bin',b'12345678'),writer.write('third.bin',b'12345678')),StorageDenied)
failed=Store(OUT/'write_error',byte_limit=20,record_limit=10,reserve_bytes=0,write_fn=lambda *a:(_ for _ in ()).throw(OSError('synthetic write failure')))
rejects('write_failure_stops_without_delete',lambda:failed.write('failure.bin',b'123'),OSError)
check('failed_partial_retained',(failed.root/'failure.bin.partial_1').exists())

# Narrow changed-source AST. No launch/limits/signal calls in this fixture.
for f in (P/'code').rglob('*.py'):ast.parse(f.read_text())
execution=(P/'code/execution.py').read_text();tree=ast.parse(execution)
check('no_RLIMIT_AS_call',not any(isinstance(n,ast.Attribute) and n.attr=='RLIMIT_AS' for n in ast.walk(tree)))
check('monitor_exception_retains_final_wait_barrier','child.wait()' in execution and 'finally:' in execution and 'os.killpg(child.pid,signal.SIGTERM)' in execution)
launch=(P/'code/launch.py').read_text()
check('capacity_gate_before_NVML_and_lifecycle',launch.index('quota_gate(r,p)')<launch.index("phase='NVML'")<launch.index("phase='lifecycle'"))
check('new_runtime_uses_pure_transition_publisher','publish_transition(self,transition,obref,step)' in (P/'code/runtime_engine.py').read_text())
check('forbidden_modules_never_imported',not any(name.split('.')[0] in FORBIDDEN for name in sys.modules))
save('CHECKS.json',dict(status='PASS',synthetic=True,checks=checks,count=len(checks),old_133_suite_run=False,
    real_model_environment_hardware_holder_launcher_claim_calls=0,deletions=0,synthetic_adapter_counts=fake.OPS))
print(json.dumps(dict(status='PASS',checks=len(checks),output=str(OUT))))
