"""Targeted changed-path checks only. No legacy suite, hardware or model import."""
import sys
from pathlib import Path
PKG=Path(__file__).resolve().parents[1];sys.path[:0]=[str(PKG/'queue'),str(PKG/'code')]
import inheritance
import ast,copy,fcntl,hashlib,importlib.abc,json,os,socket,subprocess,time,uuid
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self,name,path,target=None):
        if name.split('.')[0] in {'torch','numpy','metaworld','mujoco','ctypes','pynvml'}:raise RuntimeError('forbidden CPU import '+name)
sys.meta_path.insert(0,Deny())
from qio import QUEUE,read,ref,new_json,process_identity,same_process
from qledger import Ledger,empty_state,reserve,enter,finish,technical_breaker,LedgerFault
from qplan import ordered_pending,build_metadata,auxiliary
from qauthority import validate_proposal,collection_gate,AuthorityFault,AwaitingRelease,AUTH_SHA,current
from qreservation import holder_exit_ack,send_existing_fd,receive_existing_fd
from qresources import memory_decision
from source_plan import check_source_seed
from qevents import deliver
from core.contracts import Meter
from audit_support import audit_journal

out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);checks=[]
def check(name,okay,detail=None):
    checks.append(dict(name=name,passed=bool(okay),detail=detail))
    if not okay:raise AssertionError(name)
def reject(name,fn):
    try:fn()
    except Exception as e:check(name,True,dict(type=type(e).__name__,message=str(e)));return
    raise AssertionError('accepted: '+name)
try:
    for file in [*(PKG/'queue').glob('*.py'),*(PKG/'code').rglob('*.py')]:ast.parse(file.read_text())
    check('new_package_AST',True)
    plan=read(QUEUE/'plan/SOURCES_V2.json');rows=ordered_pending(plan['sources']);expected=read(QUEUE/'plan/NEXT8_FORMAL_CONCURRENCY_V1.json')
    check('frozen475_and_first8_order',len(rows)==475 and [r['source_key'] for r in rows[:8]]==[p['source_key'] for p in expected['parents']])
    check('no_terminal_reserved_reintroduced',all(r['initial_state']=='pending' for r in rows))
    sample=out/'SMALL_MANIFEST.json';new_json(sample,dict(files=[]))
    p=build_metadata(rows[:8],out/'first8',job_id='A_pool_v2_b001',sequence=1,package_manifest_ref=ref(sample),
        code_manifest_ref=ref(sample),authorization_ref=ref(QUEUE/'AUTHORIZATION_V2.json'))
    validate_proposal(p,full=False)
    check('real_factory_real_CPU_authority_validates_first8',p['resource_caps']==expected['resource_caps_total'])
    check('eight_distinct_UUIDs_sources_private_directories',len({x['device']['gpu_uuid'] for x in p['parents']})==8 and len({x['paths']['output'] for x in p['parents']})==8)
    check('no_runtime_directories_created',not any(Path(v).exists() for v in p['paths'].values()))
    for source in [rows[0]['source'],next(x['source'] for x in rows if x['source']['split']=='development')]:check_source_seed(source)
    check('real_source_seed_train_and_ASCII_development',True)
    bad=copy.deepcopy(rows[0]['source']);bad['env_seed']+=1;reject('wrong_seed_refused',lambda:check_source_seed(bad))
    bad=copy.deepcopy(p);bad['synthetic']=True;reject('production_rejects_synthetic',lambda:validate_proposal(bad))
    bad=copy.deepcopy(p);bad['parents'][1]['device']=bad['parents'][0]['device'];reject('duplicate_UUID_refused',lambda:validate_proposal(bad))
    bad=copy.deepcopy(p);bad['paths']['output']=str(out/'forbidden_real_path');reject('path_escape_refused',lambda:validate_proposal(bad))
    bad=copy.deepcopy(p);cfg=read(bad['parents'][0]['config']['path']);cfg['matching']['xyz_rms']=.1
    new_json(out/'CHANGED_SCIENCE.json',cfg);bad['parents'][0]['config']=ref(out/'CHANGED_SCIENCE.json')
    reject('model_or_radius_drift_refused_before_large_hash',lambda:validate_proposal(bad))
    reject('wrong_node_host_refused',lambda:current('B'))
    try:collection_gate(sequence=1)
    except AwaitingRelease:check('first8_gate_closed_without_compute_or_claim',True)
    else:check('first8_gate_now_released_recheck_required',True)
    s=empty_state('SYNTHETIC');sources=[dict(source_key='a',owner='A',initial_state='pending'),dict(source_key='b',owner='B',initial_state='pending')]
    job=dict(job_id='a',node='A',source_keys=['a'],resource_caps={'test':1})
    kwargs=dict(source_rows=sources,total_caps={'test':2},available_bytes=300,available_inodes=100,storage_bytes=100,storage_inodes=5,free_floor=10)
    reserve(s,job,**kwargs)
    reject('duplicate_command_source_refused',lambda:reserve(s,job,**kwargs))
    reject('wrong_owner_refused',lambda:reserve(copy.deepcopy(s),dict(job_id='x',node='B',source_keys=['a'],resource_caps={'test':1}),**kwargs))
    bjob=dict(job_id='b',node='B',source_keys=['b'],resource_caps={'test':1})
    k=dict(kwargs,available_bytes=220,A_priority_floor=100)
    reserve(copy.deepcopy(s),bjob,**k);check('shared_A_priority_not_double_deducted',True)
    reject('cross_node_same_capacity_denied',lambda:reserve(copy.deepcopy(s),bjob,**dict(k,available_bytes=209)))
    enter(s,'a',dict(synthetic=True));reject('entered_job_not_restarted',lambda:enter(s,'a',{}))
    finish(s,'a',dict(process_exit_proven=False,publication_complete=False))
    check('unknown_exit_blocks_without_lease_reclaim',s['jobs']['a']['state']=='execution_unknown' and s['storage']['a']['active'])
    technical_breaker(s,'A',[dict(technical_failure_signature='same')]*3)
    check('three_identical_technical_failures_block_node',s['node_breakers']['A']['blocked'])
    l=Ledger(out/'CAS',dict(value=0));l.transact(lambda s:dict(value=s['value']+1),node='A',operation='synthetic')
    check('real_filesystem_exclusive_hardlink_publication',l.latest()[1]['value']==1)
    code='import sys;sys.path.insert(0,sys.argv[1]);from qledger import Ledger;l=Ledger(sys.argv[2],dict(value=0));l.transact(lambda s:dict(value=s["value"]+1),node=sys.argv[3],operation="synthetic_concurrent")'
    ps=[subprocess.Popen([sys.executable,'-B','-c',code,str(PKG/'queue'),str(out/'CAS'),node]) for node in ['A','B','A','B']]
    check('concurrent_CAS_no_lost_updates',all(p.wait()==0 for p in ps) and l.latest()[1]['value']==5)
    obs=dict(host_available_bytes=2*1024**4,cgroup_available_bytes=None,effective_CPU_count=224)
    d=memory_decision(obs,8);check('unknown_cgroup_not_invented_hardmax2',d['planning_supported']==8 and d['hardware_supported_max'] is None)
    reject('finite_memory_planning_denial_no_fallback',lambda:memory_decision(dict(obs,host_available_bytes=128*1024**3),8))
    check('tail_batch_not_padded',auxiliary(3,8,read(PKG/'config/LEGACY_PROPOSAL.json')['storage'])[1]['branch_process_starts']==45)
    t=[0.];statuses=[dict(updated=2,gpus={str(i):dict(state='holder') for i in range(8)}),dict(updated=3,gpus={str(i):dict(state='reserved') for i in range(8)})]
    order=[]
    ack=holder_exit_ack(dict(request_unix=1,holder_processes=[dict(pid=1)]),status_reader=lambda:statuses[min(int(t[0]),1)],
        alive=lambda p:t[0]<1,clock=lambda:t[0],pause=lambda _:t.__setitem__(0,t[0]+1),seconds=3)
    order.append('ACK');order.append('formal_Popen_allowed');check('holder_exit_ACK_precedes_any_formal_Popen',ack['extra_GPU_queries']==0 and order==['ACK','formal_Popen_allowed'])
    lockfile=Path('/tmp')/('corrector_synthetic_fd_'+uuid.uuid4().hex+'.lock');handle=lockfile.open('a');fcntl.flock(handle,fcntl.LOCK_EX)
    sockpath='/tmp/corrector_cpu_fd_'+uuid.uuid4().hex+'.sock';server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(sockpath);server.listen(1)
    cmd='import sys;sys.path.insert(0,sys.argv[1]);from qreservation import send_existing_fd;send_existing_fd(sys.argv[2],int(sys.argv[3]))'
    child=subprocess.Popen([sys.executable,'-B','-c',cmd,str(PKG/'queue'),sockpath,str(handle.fileno())],pass_fds=(handle.fileno(),),start_new_session=True)
    duplicate,peer=receive_existing_fd(server,lockfile,lambda row:row['pid']==child.pid);child.wait();handle.close()
    contender=lockfile.open('a');busy=False
    try:fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:busy=True
    check('same_FD_retains_lock_after_sender_exit_no_nested_acquire',busy and child.returncode==0)
    os.close(duplicate);fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB);contender.close();server.close()
    check('lock_released_only_after_outer_publication_barrier',True)
    m=Meter(out/'missing_terminal.jsonl',{'test':1});m.enter('synthetic',{'test':1})
    j=audit_journal(out/'missing_terminal.jsonl','numeric',{'test':1})
    check('missing_terminal_charged_and_blocks_validation',j['entered']['test']==1 and bool(j['incomplete_ids']))
    new_json(out/'CPU_CHECKS.json',dict(status='PASS',checks=checks,formal_compute=0,hardware_imports=0,real_claims=0))
    print(json.dumps(dict(status='PASS',checks=len(checks),result=str(out/'CPU_CHECKS.json'))))
except BaseException as e:
    import traceback
    new_json(out/'FAILED.json',dict(checks=checks,error=str(e),traceback=traceback.format_exc()));raise
