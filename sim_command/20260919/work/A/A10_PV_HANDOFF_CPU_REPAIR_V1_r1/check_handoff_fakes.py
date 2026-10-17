"""Extract changed functions into fake-only namespaces. No real guard import."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1'
W=B/'work/A/A10_PV_HANDOFF_CPU_REPAIR_V1_r1'
F=W/'targeted_fixtures'
F.mkdir(exist_ok=False)
blocked=[]

def audit(event,args):
    if event=='import' and args[0].split('.')[0] in {'torch','numpy','ctypes','pynvml','OpenGL','mujoco','metaworld','lerobot','fcntl'}:
        blocked.append([event,args[0]]);raise AssertionError('Forbidden import in pure CPU fixtures')
    if event.startswith('ctypes.') or event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.kill','os.killpg'}:
        blocked.append([event]);raise AssertionError('Forbidden real process/driver operation')
    if event=='open' and isinstance(args[0],str) and (args[0].startswith('/tmp/gpu_occupancy_guard') or Path(args[0]).suffix in {'.safetensors','.pt','.pth','.npy','.npz','.so'}):
        blocked.append([event,args[0]]);raise AssertionError('Forbidden real lock/cache/model/library read')

sys.addaudithook(audit)

def put(path,obj):
    with path.open('x') as f:f.write(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

def extracted(path,names,scope):
    tree=ast.parse(path.read_text());body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in body}==set(names)
    exec(compile(ast.Module(body=body,type_ignores=[]),str(path)+'::fake_only','exec'),scope)
    return scope

class Fake:
    def __init__(self,env=None,clear_at=0,error_at=None,query_latency=0,malformed=False,rows=1,returncode=0,forward_signal=False,drain_seconds=1):
        self.now=0.;self.env={} if env is None else dict(env);self.clear_at=clear_at;self.error_at=error_at
        self.query_latency=query_latency;self.malformed=malformed;self.rows=rows;self.returncode=returncode
        self.forward_signal=forward_signal;self.drain_seconds=drain_seconds
        self.calls=0;self.starts=0;self.spawns=0;self.lock_opens=0;self.acquires=0
        self.parent_lock=False;self.child_fd=False;self.proc_done=False;self.handlers={};self.signals=[];self.logs=[];self.trace=[]
        self.restore_times=[];self.launch_times=[];self.drain=None
    def held(self):return self.parent_lock or self.child_fd
    def monotonic(self):return self.now
    def sleep(self,dt):
        assert self.held() and dt>0
        self.now+=dt
    def start(self):self.starts+=1;self.trace.append(['fake_guard_active',self.now])
    def query(self,fields,kind):
        assert (fields,kind)==('pid','compute-apps') and self.held()
        self.calls+=1;self.now+=self.query_latency
        if self.error_at is not None and self.now>=self.error_at:raise RuntimeError('synthetic driver query failure')
        if self.malformed:return None
        return [] if self.now>=self.clear_at else [[str(900000+i)] for i in range(self.rows)]
    def __truediv__(self,name):
        assert name=='formal.lock';return self
    def open(self,mode):
        assert mode=='a';self.lock_opens+=1;return self
    def __enter__(self):return self
    def fileno(self):return 321
    def __exit__(self,*args):
        self.parent_lock=False
        if not self.held():self.restore_times.append(self.now)
        self.trace.append(['reservation_client_closed',self.now,self.held()])
    def flock(self,handle,flag):
        assert handle is self and flag==2 and not self.parent_lock
        self.parent_lock=True;self.acquires+=1;self.trace.append(['all8_reserved',self.now])
    def popen(self,command,**kw):
        assert command==['fake_reserved_wrapper'] and kw==dict(start_new_session=True,pass_fds=(321,)) and self.held()
        assert self.now>=self.clear_at
        self.spawns+=1;self.child_fd=True;self.launch_times.append(self.now);self.trace.append(['formal_spawn',self.now])
        return self
    @property
    def pid(self):return 7001
    def poll(self):return self.returncode if self.proc_done else None
    def signal(self,sig,fn):
        previous=self.handlers.get(sig,'old_handler');self.handlers[sig]=fn;return previous
    def killpg(self,pid,sig):
        assert pid==7001 and self.held();self.signals.append(['group',pid,sig])
    def send_member(self,pid,sig):
        assert pid==7002 and self.held();self.signals.append(['member',pid,sig])
    def wait(self):
        assert self.held()
        if self.forward_signal:self.handlers[15](15,None)
        begun=self.now
        def reader(pgid,owner):
            assert pgid==owner==7001 and self.held()
            return [{'pid':7002,'start_ticks':111}] if self.now-begun<self.drain_seconds else []
        self.drain=self.drain_fn(7001,7001,reader=reader,send=self.send_member,clock=self.monotonic,pause=self.sleep)
        assert self.drain['status']=='all_formal_group_members_exited' and self.held()
        self.trace.append(['entire_formal_group_exited',self.now])
        self.proc_done=True;self.child_fd=False
        return self.returncode
    def scope(self):
        signals=SimpleNamespace(SIGINT=2,SIGTERM=15,SIGHUP=1,SIGKILL=9,signal=self.signal)
        os=SimpleNamespace(environ=self.env,killpg=self.killpg,kill=self.send_member)
        timing=SimpleNamespace(monotonic=self.monotonic,sleep=self.sleep)
        drain_scope=dict(os=os,signal=signals,time=timing,group_members=lambda *a:None)
        extracted(P/'code/core/process_family.py',['drain_group'],drain_scope)
        self.drain_fn=drain_scope['drain_group']
        return dict(os=os,time=timing,STATE=self,fcntl=SimpleNamespace(flock=self.flock,LOCK_EX=2),start=self.start,query=self.query,subprocess=SimpleNamespace(Popen=self.popen),signal=signals,log=self.logs.append,json=json)

results=[]
def run_case(name,patched=True,expected_error=None,**kw):
    fake=Fake(**kw);scope=fake.scope()
    source=P/'guard_patch'/('gpu_occupancy_guard.patched.py' if patched else 'gpu_occupancy_guard.original.py')
    names=['handoff_timeout_seconds','run_formal'] if patched else ['run_formal']
    extracted(source,names,scope)
    error=None;result=None
    try:result=scope['run_formal'](['--','fake_reserved_wrapper'])
    except (ValueError,RuntimeError) as e:error=dict(type=type(e).__name__,message=str(e))
    if expected_error:
        assert error is not None and error['type']==expected_error,(name,error)
        assert fake.spawns==0
    else:
        assert error is None and fake.spawns==1 and result==fake.returncode,(name,error)
        assert fake.trace.index(next(x for x in fake.trace if x[0]=='entire_formal_group_exited')) < fake.trace.index(next(x for x in fake.trace if x[0]=='reservation_client_closed'))
    assert not fake.held() and fake.lock_opens==fake.acquires and fake.acquires<=1
    assert all(s[1] in [7001,7002] for s in fake.signals)
    for log in fake.logs:
        info=json.loads(log.removeprefix('HANDOFF_FAILURE_JSON '))
        assert info['poll_attempts']==fake.calls and info['extra_hardware_queries']==0
        if info['last_observation'] is not None:assert len(info['last_observation']['rows'])<=64
    row=dict(case=name,status='passed',patched=patched,elapsed_fake_seconds=fake.now,error=error,returncode=result,
        start_calls=fake.starts,poll_calls=fake.calls,formal_spawns=fake.spawns,lock_opens=fake.lock_opens,lock_acquires=fake.acquires,
        launch_times=fake.launch_times,restoration_times=fake.restore_times,signals=fake.signals,failure_logs=fake.logs,trace=fake.trace,
        real_queries_locks_processes_signals=0)
    put(F/(name+'.json'),row);results.append(row);return fake

run_case('old90_rejects_holder_clear_at120',patched=False,clear_at=120,expected_error='RuntimeError')
new=run_case('new300_accepts_holder_clear_at120',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'300'},clear_at=120)
assert new.launch_times==[120] and new.calls==121
run_case('new_default90_rejects_holder_clear_at120',clear_at=120,expected_error='RuntimeError')
run_case('new_default90_accepts_clear_at20',clear_at=20)
run_case('persistent_external_apps_timeout_no_kill',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'300'},clear_at=1000,expected_error='RuntimeError')
no_obs=run_case('query_error_first_poll_not_empty',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'300'},error_at=0,clear_at=120,expected_error='RuntimeError')
assert json.loads(no_obs.logs[0].removeprefix('HANDOFF_FAILURE_JSON '))['last_observation'] is None
run_case('query_error_preserves_prior_observation',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'300'},error_at=2,clear_at=120,expected_error='RuntimeError')
run_case('malformed_query_is_rejected',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'300'},malformed=True,expected_error='RuntimeError')
run_case('late_empty_query_after_deadline_rejected',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'300'},clear_at=0,query_latency=301,expected_error='RuntimeError')
bounded=run_case('failure_record_truncates_100_rows',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'1'},clear_at=1000,rows=100,expected_error='RuntimeError')
obs=json.loads(bounded.logs[0].removeprefix('HANDOFF_FAILURE_JSON '))['last_observation'];assert obs['truncated'] and obs['total_rows']==100 and len(obs['rows'])==64
run_case('child_failure_keeps_reservation_until_group_exit',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'300'},clear_at=1,returncode=3)
sig=run_case('signal_forwarding_and_KILL_drain_barrier',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'300'},clear_at=1,returncode=143,forward_signal=True,drain_seconds=31)
assert ['group',7001,15] in sig.signals and ['member',7002,9] in sig.signals
for index,value in enumerate(['','0','-1','+300','301','9999','nan','inf','1e3','300.0',' 300','300 ','٣٠٠','090']):
    invalid=run_case(f'invalid_value_{index:02d}',env={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':value},expected_error='ValueError')
    assert invalid.starts==invalid.calls==invalid.acquires==0 and not invalid.logs

sys.path.insert(0,str(P/'code'))
from core import contracts as C
from core.handoff import HANDOFF_SPEC,require_handoff_environment
cfg=json.loads((P/'config/CONFIG.json').read_text())
assert require_handoff_environment(cfg,{HANDOFF_SPEC['environment_variable']:'300'})['actual_value']=='300'
for env in [{},{HANDOFF_SPEC['environment_variable']:'90'},{HANDOFF_SPEC['environment_variable']:'301'}]:
    try:require_handoff_environment(cfg,env);raise AssertionError('Actual V3 parameter drift not rejected')
    except ValueError:pass
# Test the real manifest verifier against retained tiny fixtures only.
for label,source,success in [('uninstalled_old',P/'guard_patch/gpu_occupancy_guard.original.py',False),('installed_expected',P/'guard_patch/gpu_occupancy_guard.patched.py',True)]:
    target=F/(label+'.txt')
    with target.open('xb') as f:f.write(source.read_bytes())
    row=dict(path=str(target),sha256=HANDOFF_SPEC['guard_expected_sha256'],size_bytes=HANDOFF_SPEC['guard_expected_size_bytes'])
    try:C.verify_ref(row);accepted=True
    except C.ContractError:accepted=False
    assert accepted==success
try:C.verify_ref(dict(path=str(F/'missing_guard.txt'),sha256=HANDOFF_SPEC['guard_expected_sha256']));raise AssertionError('Missing guard accepted')
except FileNotFoundError:pass

p=json.loads((P/'proposal/PROPOSAL.json').read_text());p['_sha256']=hashlib.sha256((P/'proposal/PROPOSAL.json').read_bytes()).hexdigest()
required=json.loads((P/'proposal/CONTROL_REQUIRED.json').read_text())
c=json.loads((W/'ack_snapshots/CONTROL.json').read_text())
for key in ['mode','formal_gpu_runs_enabled','stop_requested','active_compute_release_id','active_compute_release','active_compute_task_ids','current_compute_limits','per_task_compute_limits','active_occupancy_handoff']:c[key]=required[key]
c['allowed_task_ids'].append(C.TASK);c['fixture_only_not_authorization']=True
board=dict(tasks=[required['board_task']],fixture_only_not_authorization=True)
r=json.loads((P/'proposal/RELEASE_TEMPLATE.json').read_text());r['status']='released';r['fixture_only_not_authorization']=True
base=dict(control=c,board=board,release=r,proposal=p,release_path=p['required_release_path'],hostname=p['owner_host'])
metadata=[]
def meta_case(name,change=None,success=False):
    item=copy.deepcopy(base)
    if change:change(item)
    error=None
    try:C.validate_metadata(**item);accepted=True
    except C.ContractError as e:accepted=False;error=str(e)
    assert accepted==success,(name,error)
    metadata.append(dict(case=name,accepted=accepted,expected=success,error=error))
meta_case('V3_ready_passes',success=True)
meta_case('V3_running_passes',lambda x:x['board']['tasks'][0].update(status='running'),success=True)
meta_case('board_released_rejects',lambda x:x['board']['tasks'][0].update(status='released'))
meta_case('old_V2_identity_rejects',lambda x:x['release'].update(task_id='A10_PV_OFFLINE_PREFLIGHT_V2',release_id='P10_A_PV_OFFLINE_PREFLIGHT_V2'))
meta_case('closed_V3_rejects',lambda x:x['control']['closed_compute_releases'].append(dict(release_id=C.RELEASE)))
meta_case('release_handoff_90_rejects',lambda x:x['release']['occupancy_handoff'].update(timeout_seconds=90))
meta_case('control_handoff_missing_rejects',lambda x:x['control'].pop('active_occupancy_handoff'))
meta_case('proposal_handoff_wrong_rejects',lambda x:x['proposal']['occupancy_handoff'].update(required_value='90'))
meta_case('external_manifest_SHA_wrong_rejects',lambda x:x['release'].update(external_source_manifest_sha256='0'*64))
meta_case('unreleased_template_rejects',lambda x:x['release'].update(status='UNAUTHORIZED_TEMPLATE'))
for name,obj in [('CONTROL_CANDIDATE.json',c),('TASK_BOARD_CANDIDATE.json',board),('RELEASE_CANDIDATE.json',r)]:put(F/name,obj)
spec=importlib.util.spec_from_file_location('publication_checker',P/'commands/check_publication_metadata_cpu.py');checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
published=checker.check(F/'CONTROL_CANDIDATE.json',F/'TASK_BOARD_CANDIDATE.json',F/'RELEASE_CANDIDATE.json',p['required_release_path'],p['owner_host'])
assert published['status']=='PASS_METADATA_ONLY_NOT_AUTHORIZATION'
assert not blocked
result=dict(status='passed',scope='Only handoff run-client changes, actual metadata/environment/manifest guards and inherited group exit barrier; no old numeric suite',guard_cases=len(results),guard_results=[dict(case=x['case'],status=x['status']) for x in results],metadata_cases=metadata,actual_environment_checks=4,actual_guard_manifest_fixture_checks=3,pure_publication_result=published,blocked_real_operations=blocked,live_guard_imports=0,real_locks_processes_queries_signals=0,real_launcher_invocations=0,compute_release_claims=0,holder_queries_stops=0,shared_installations=0,daemon_restarts=0,large_model_hashes=0,whole_algorithm_suite_runs=0,deletions=0)
put(W/'TARGETED_FAKE_RESULT.json',result)
print(json.dumps(dict(status='passed',guard_cases=len(results),metadata_cases=len(metadata),actual_environment_checks=4,guard_manifest_fixture_checks=3,pure_publication_checks=1,real_operations=0),indent=2))
