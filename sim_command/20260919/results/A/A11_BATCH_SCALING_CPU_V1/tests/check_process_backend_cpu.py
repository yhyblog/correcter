"""Actual release-only backend methods with fake process table/Popen/signals.
No real process is started/queried/signaled; no formal.lock or holder is touched.
"""
import ast,copy,json,sys,types,traceback
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'));import inheritance
def audit(event,args):
    if event=='import' and args[0].split('.')[0] in {'torch','mujoco','numpy','pynvml','metaworld','OpenGL'}:raise AssertionError(event)
    if event in ('ctypes.dlopen','subprocess.Popen','os.kill','os.killpg','os.system'):raise AssertionError('real operation forbidden '+event)
sys.addaudithook(audit)
import process_backend as m
import batch_publication
real_publish=batch_publication.publish_parent
def synthetic_publish(parent,store,cleanup,**kwargs):
    return real_publish(parent,store,cleanup,synthetic=True)
batch_publication.publish_parent=synthetic_publish
from batch_scheduler import GlobalFault
from core.contracts import sha
from pool_protocol import ARMS
from budget import scheduler_caps
OUT=Path(sys.argv[1]);OUT.mkdir(parents=True,exist_ok=False)
checks=[];trace=[];rows={};clock=[0.];nextpid=[900001]
def write(path,v):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(v)+'\n')
def check(name,value):checks.append(dict(name=name,passed=bool(value)));assert value,name
def reject(name,fn):
    try:fn()
    except GlobalFault:check(name,True);return
    raise AssertionError(name+' accepted')
class FakeProcess:
    def __init__(self,cmd,**kwargs):
        assert kwargs['start_new_session'] is False and kwargs['pass_fds']==(777,)
        self.pid=nextpid[0];nextpid[0]+=1;self.code=None
        rows[self.pid]=dict(pid=self.pid,ppid=900000,pgid=900000,state='R',start_ticks=self.pid+17)
        trace.append(dict(kind='Popen_FAKE',pid=self.pid,argv=cmd,pass_fds=list(kwargs['pass_fds']),new_session=kwargs['start_new_session']))
    def poll(self):return self.code
    def wait(self):return self.code
m.os=types.SimpleNamespace(getpid=lambda:900000,getpgrp=lambda:900000)
m.time=types.SimpleNamespace(monotonic=lambda:clock[0])
timer=[(1000.,0.)];timer_calls=[]
def set_timer(which,seconds,interval=0):timer_calls.append((seconds,interval));timer[0]=(seconds,interval)
m.signal=types.SimpleNamespace(ITIMER_REAL=0,getitimer=lambda which:timer[0],setitimer=set_timer)
m.subprocess=types.SimpleNamespace(Popen=FakeProcess)
import runtime_environment
runtime_environment.os=types.SimpleNamespace(environ={'CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS':'300'})
m.process_row=lambda pid:copy.deepcopy(rows.get(pid))
m.group_snapshot=lambda group,owner:[copy.deepcopy(r) for r in rows.values() if r['pgid']==group and r['pid']!=owner and r['state']!='Z']
def fake_drain(group,owner):
    assert group==owner==900000;trace.append(dict(kind='FAKE_DRAIN',owned=list(rows)));rows.clear()
    return dict(status='all_formal_group_members_exited',synthetic=True,actions=[],process_group=group)
m.drain_group=fake_drain
proposal=json.loads((P/'proposal/PROPOSAL.json').read_text());parent=copy.deepcopy(proposal['parents'][0])
parent['parent_key']='SYNTHETIC_PROCESS_PARENT';parent['paths']={k:str(OUT/k) for k in ('output','cache')}
parent['device']['gpu_uuid']='SYNTHETIC_GPU_UUID'
cfg=json.loads(Path(parent['config']['path']).read_text());cfg['source'].update(source_id='SYNTHETIC_SOURCE',parent_source_id='SYNTHETIC_PARENT')
runtime_environment.os.environ['NVIDIA_VISIBLE_DEVICES']=cfg['cuda_environment']['NVIDIA_VISIBLE_DEVICES']
path=OUT/'SYNTHETIC_CONFIG.json';write(path,cfg);parent['config']['path']=str(path)
proposal['scheduler_caps']=scheduler_caps(2)
def branch_files(name,*,primary=None,cleanup=None,ledger=True):
    out=Path(parent['paths']['output'])/name;out.mkdir(exist_ok=False)
    write(out/'BRANCH_RESULT.json',dict(status='complete',legal_cut_reached=True,restore_level='full_state_verified',synthetic=True))
    if ledger:write(out/'RESOURCE_LEDGER.json',dict(primary=primary,cleanup=cleanup or [],synthetic=True))
try:
    backend=m.ProcessBackend('SYNTHETIC_RELEASE_NOT_EXECUTED',proposal,(777,))
    h=backend.start(parent,ARMS[0]);backend.refresh()
    check('actual_backend_one_cold_child_same_group_lock',len(trace)==1 and h['parent']['device']['gpu_uuid']=='SYNTHETIC_GPU_UUID')
    child=h['process'];desc=900101;rows[desc]=dict(pid=desc,ppid=child.pid,pgid=900000,state='R',start_ticks=17)
    backend.refresh();check('actual_descendant_ownership_inherited',backend.owners[desc]['root']==child.pid)
    child.code=0;rows.pop(child.pid);branch_files('normal')
    check('leader_exit_does_not_release_slot_with_live_descendant',backend.poll(h) is None)
    rows.pop(desc);result=backend.poll(h);check('slot_released_only_after_descendants_exit',result['cleanup_complete'] and not backend.handles)
    backend.record_exit(parent,ARMS[0],result)
    # Ordinary model errors remain local; identity, cleanup and absent ledger stop wave.
    cases=[('Q_a0_r0',dict(failure_scope='parent'),[],True,'parent'),
           ('Q_a0_r1',dict(failure_scope='wave'),[],True,'wave'),
           ('Q_local_plus_r0',None,[dict(failure_scope='wave')],True,'wave'),
           ('Q_local_plus_r1',None,[],False,'wave')]
    for name,primary,cleanup,ledger,expected in cases:
        job=next(j for j in ARMS if j[0]==name);h=backend.start(parent,job)
        branch_files(name,primary=primary,cleanup=cleanup,ledger=ledger)
        h['process'].code=3;rows.pop(h['process'].pid)
        r=backend.poll(h);check(name+'_actual_failure_scope',r['failure_scope']==expected)
        backend.record_exit(parent,job,r)
    # Unattributed process: no parent-local completion; no killing outside group.
    rows[999999]=dict(pid=999999,ppid=1,pgid=900000,state='R',start_ticks=4)
    reject('unknown_member_refuses_parent_local_exit',backend.refresh);rows.clear()
    cleanup=backend.drain();check('actual_backend_drain_retains_group_barrier',cleanup['status']=='all_formal_group_members_exited' and backend.cleanup==cleanup)
    # Real publication entry includes group-exit and private-cost evidence even if partial.
    published=backend.publish(parent)
    check('actual_backend_partial_publication_after_exit',published['analysis_acceptance_pending'] and (Path(parent['paths']['output'])/'reserved/PROCESS_GROUP_EXIT.json').exists())
    index=json.loads((Path(parent['paths']['output'])/'reserved/PRIVATE_COST_INDEX.json').read_text())
    check('missing_child_ledgers_not_inferred_zero',any(x['missing'] for x in index['attempts']) and index['public_UUID_bridge'] is False)
    reject('real_backend_requires_inherited_lock',lambda:m.ProcessBackend('synthetic',proposal,()))
    # Real entry wiring, no importing/executing launch/reserved/child main.
    trees={n:ast.parse((P/'code'/n).read_text()) for n in ('launch.py','reserved.py','child.py','authorization.py','execution.py')}
    literal_calls=lambda t,s:[n for n in ast.walk(t) if isinstance(n,ast.Constant) and n.value==s]
    check('only_outer_entry_contains_lifecycle_command',len(literal_calls(trees['launch.py'],'occupancy_lifecycle'))==1 and not literal_calls(trees['child.py'],'occupancy_lifecycle') and not literal_calls(trees['reserved.py'],'occupancy_lifecycle'))
    check('reserved_calls_actual_batch_scheduler',any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='run_schedule' for n in ast.walk(trees['reserved.py'])))
    check('config_manifest_in_full_authorization',len(literal_calls(trees['authorization.py'],'config_manifest'))==2)
    check('no_new_address_space_limit','RLIMIT_AS' not in (P/'code/execution.py').read_text())
    timer[0]=(1000.,0.);clock[0]=0.
    with m.publication_deadline(300.):clock[0]=20.
    check('publication_timer_does_not_extend_wave',timer_calls[-2:]==[(300.,0),(980.,0.)])
    reject('publication_deadline_expired',lambda:m.publication_deadline(10.).__enter__())
    status='PASS';failure=None
except BaseException:status='FAIL';failure=traceback.format_exc()
value=dict(status=status,synthetic=True,checks=checks,trace=trace,failure=failure,
    real_process_queries_or_launches=0,real_lock_accesses=0,real_signals=0,hardware_or_holder_operations=0,
    actual_backend_module=dict(path=m.__file__,sha256=sha(m.__file__)))
write(OUT/'CHECK_RESULT.json',value);print(json.dumps(dict(status=status,checks=len(checks),failure=failure)))
sys.exit(0 if status=='PASS' else 1)
