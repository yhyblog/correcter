"""Targeted control tests; never imports model/hardware or touches live locks."""
import ast
import builtins
import copy
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
CAMPAIGN=ROOT.parents[3]
PACKAGE=CAMPAIGN/'persistent_queue/package/versions/queue_v1'
sys.path.insert(0,str(PACKAGE/'queue'))
original_import=builtins.__import__
def guarded_import(name,*args,**kwargs):
    if name.split('.')[0] in {'torch','ctypes','pynvml','mujoco','metaworld','pycuda','OpenGL'}:
        raise AssertionError('forbidden import: '+name)
    return original_import(name,*args,**kwargs)
builtins.__import__=guarded_import
import qoccupancy as qo
import qauthority as qa
from qio import new_json,read,utc

rows=[]
def check(name,fn):
    try:fn();rows.append(dict(name=name,status='PASS'))
    except BaseException as error:
        rows.append(dict(name=name,status='FAIL',error=repr(error)));raise
def reject(fn):
    try:fn()
    except (RuntimeError,ValueError):return
    raise AssertionError('did not reject')

run_suffix=sys.argv[1] if len(sys.argv)>1 else ''
root=ROOT/('fixtures'+run_suffix);root.mkdir(exist_ok=False)
ack={'status':'all8_holder_processes_exited_before_formal_child'}
devices=[dict(gpu_uuid='synthetic_GPU_'+str(i),gpu_index=i) for i in range(2)]
g0,g1=[d['gpu_uuid'] for d in devices]
cache=lambda:dict(updated=time.time(),gpus={'0':dict(state='reserved',pids=[]),'1':dict(state='reserved',pids=[])})
trace=[]
def factory(gpu,folder):trace.append(('holder_start',gpu))
def stopper(folder,reason):
    trace.extend([('stop_request',str(folder)),('manager_exit',str(folder)),('descendants_exit_ACK',str(folder))])
    return {'status':'all_owned_holder_session_processes_exited','synthetic':True}
def fresh(name,**kwargs):return qo.PerGPU(root/name,devices,ack,holder_factory=factory,holder_stopper=stopper,**kwargs)

def actual_policy():
    p=qo.policy();assert p['sha256']==qo.OVERRIDE_SHA
    new_json(ROOT/('EFFECTIVE_POLICY_CHECK'+run_suffix+'.json'),dict(policy=p,control=read(qo.QUEUE/'CONTROL.json'),utc=utc(),synthetic=False,CPU_metadata_only=True))
check('actual_SHA_bound_override_and_unchanged_base_authority',actual_policy)
ctl=read(qo.QUEUE/'CONTROL.json')
check('missing_override_rejected',lambda:reject(lambda:qo.policy(dict(ctl,operational_overrides=[]))))
check('wrong_base_authority_rejected',lambda:reject(lambda:qo.policy(dict(ctl,authorization=dict(path='wrong',sha256='0'*64)))))
check('disabled_legacy475_stays_blocked',lambda:reject(lambda:qa.collection_gate(sequence=1,admission=False)))

def no_loading_fill():
    p=fresh('pending',pending_gpus=[g0]);assert not p.fill_idle(g0,cache())
    p.before_formal(g0,'p0');assert not p.fill_idle(g0,cache())
    p.before_formal(g0,'p0');assert not p.fill_idle(g0,cache())
    reject(lambda:p.before_formal(g0,'p_other'))
check('pending_loading_and_cold_branch_gap_never_idle',no_loading_fill)

# Compile the exact QueueBackend class; fake only its external formal backend.
# Its real override method must ACK before it can delegate to formal start.
tree=ast.parse((PACKAGE/'queue/qbatch.py').read_text())
klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='QueueBackend')
class FormalBackend:
    def start(self,parent,job):trace.append(('formal_Popen',parent['parent_key']));return 'synthetic_formal_handle'
ns={'ProcessBackend':FormalBackend}
exec(compile(ast.Module(body=[klass],type_ignores=[]),str(PACKAGE/'queue/qbatch.py'),'exec'),ns)
def handoff_order():
    p=fresh('handoff');assert p.fill_idle(g0,cache())
    backend=object.__new__(ns['QueueBackend']);backend.occupancy=p
    trace.clear();backend.start(dict(parent_key='p0',device=devices[0]),('normal','normal',0))
    assert [r[0] for r in trace]==['stop_request','manager_exit','descendants_exit_ACK','formal_Popen']
    assert p.states[g0]=='formal' and not p.fill_idle(g0,cache())
    new_json(ROOT/('HANDOFF_ORDER_SYNTHETIC'+run_suffix+'.json'),dict(events=trace,synthetic=True,actual_QueueBackend_start_method=True))
check('real_entry_wrapper_exit_ACK_precedes_formal_start',handoff_order)

def no_entry_on_missing_exit():
    p=fresh('no_entry');p.fill_idle(g0,cache())
    p.stopper=lambda *a:{'status':'not_started'}
    backend=object.__new__(ns['QueueBackend']);backend.occupancy=p
    trace.clear();reject(lambda:backend.start(dict(parent_key='p0',device=devices[0]),('normal','normal',0)))
    assert not trace and p.states[g0]=='handoff' and not p.fill_idle(g0,cache())
check('missing_exit_ACK_blocks_formal_start_and_fill',no_entry_on_missing_exit)

def exit_eligibility():
    p=fresh('exit');p.before_formal(g0,'p0');p.before_formal(g1,'p1')
    reject(lambda:p.formal_exited(g0,'p0',dict(cleanup_complete=False,remaining_group=[9])))
    assert not p.fill_idle(g0,cache())
    p.formal_exited(g0,'p0',dict(cleanup_complete=True,remaining_group=[]))
    assert p.fill_idle(g0,cache()) and not p.fill_idle(g1,cache())
check('completed_descendant_free_card_fills_while_other_formal_active',exit_eligibility)

def stale_or_busy():
    p=fresh('cache')
    stale=cache();stale['updated']-=20;assert not p.fill_idle(g0,stale)
    busy=cache();busy['gpus']['0']['pids']=[987];assert not p.fill_idle(g0,busy)
    missing=cache();missing['gpus']['0']={'state':'holder'};assert not p.fill_idle(g0,missing)
    absent=cache();absent['gpus']['0']={'state':'reserved'};assert not p.fill_idle(g0,absent)
check('stale_or_busy_or_nonreserved_cache_blocks_fill',stale_or_busy)

def exact_own_signal_scope():
    folder=root/'session';folder.mkdir()
    manager=dict(pid=90000001,start_ticks=50,host='fake',boot_id='fake')
    child=dict(pid=90000002,start_ticks=51,host='fake',boot_id='fake')
    new_json(folder/'STARTED.json',dict(process=manager))
    new_json(folder/'GO_RECORDED.json',dict(monotonic=time.monotonic()-1,GPU_uuid=g0,duty=.95))
    snapshots=iter([[manager,child],[child],[child],[]])
    signals=[]
    with patch.object(qo,'session_members',side_effect=lambda saved:next(snapshots)),patch.object(qo,'same_process',return_value=False),patch.object(qo,'signal_owned',side_effect=lambda row,sig:signals.append(row['pid'])),patch.object(qo.time,'sleep',return_value=None):
        out=qo.stop_session(folder,'synthetic')
    assert set(signals)=={manager['pid'],child['pid']}
    assert out['manager_exit'] and out['descendants'][0]['exit'] and out['extra_GPU_queries']==0
    assert (folder/'STOP_REQUEST.json').exists() and (folder/'EXIT_ACK.json').exists()
    assert out['holder_manager_interval_seconds']>=1 and out['measured_utilization'] is None
check('real_session_stop_waits_late_child_records_request_manager_and_descendant_exit',exact_own_signal_scope)

def timeout_blocks_ack():
    folder=root/'timeout';folder.mkdir();manager={'pid':999,'start_ticks':1}
    new_json(folder/'STARTED.json',dict(process=manager))
    with patch.object(qo,'session_members',return_value=[manager]),patch.object(qo,'same_process',return_value=True),patch.object(qo,'signal_owned'):
        reject(lambda:qo.stop_session(folder,'synthetic',timeout=0))
    assert not (folder/'EXIT_ACK.json').exists()
check('live_holder_timeout_cannot_produce_exit_ACK',timeout_blocks_ack)

def reused_pid():
    saved=dict(pid=100,host='fake',boot_id='fake',start_ticks=1)
    with patch.object(qo,'process_identity',side_effect=[saved,dict(saved,start_ticks=2)]):
        reject(lambda:qo.session_members(saved))
check('PID_start_identity_mismatch_rejected_before_signals',reused_pid)

def unknown_spawn():
    f=root/'unknown_spawn';f.mkdir();new_json(f/'SPAWN_INTENT.json',{'synthetic':True})
    reject(lambda:qo.stop_tree(f,'synthetic'))
check('unknown_spawn_retains_exit_barrier',unknown_spawn)

def cached_foreign_context():
    p=fresh('foreign');p.fill_idle(g0,cache())
    folder=p.holders[g0];new_json(folder/'STARTED.json',dict(process={'pid':123}))
    snapshot=cache();snapshot['gpus']['0']['pids']=[123,987]
    with patch.object(qo,'session_members',return_value=[{'pid':123}]):p.monitor_cached(snapshot)
    assert g0 not in p.holders and p.states[g0]=='idle'
    assert not p.fill_idle(g0,snapshot)
check('cached_unrelated_context_yields_only_own_holder_no_GPU_query',cached_foreign_context)

def final_barrier():
    t=ast.parse((PACKAGE/'queue/qservice.py').read_text())
    fn=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='run_chain')
    outer=next(n for n in fn.body if isinstance(n,ast.Try))
    loop=next(n for n in outer.finalbody if isinstance(n,ast.While) and 'stop_tree' in ast.unparse(n))
    fdclose=next(n for n in outer.finalbody if isinstance(n,ast.If) and 'os.close(fd)' in ast.unparse(n))
    assert outer.finalbody.index(loop)<outer.finalbody.index(fdclose)
    close=ast.parse('release()').body[0]
    code=compile(ast.Module(body=[loop,close],type_ignores=[]),'real_outer_release_barrier','exec')
    events=[]
    class Halt(Exception):pass
    def unresolved(*a):raise RuntimeError('synthetic holder descendants live')
    def pause(_):events.append('retained_reservation');raise Halt()
    env=dict(chain=root,node='A',stop_tree=unresolved,new_json=lambda *a:None,utc=utc,
        heartbeat=lambda *a,**k:events.append('blocked_heartbeat'),time=SimpleNamespace(sleep=pause),release=lambda:events.append('release'))
    try:exec(code,env)
    except Halt:pass
    assert events==['blocked_heartbeat','retained_reservation']
    env['stop_tree']=lambda *a:events.append('all_auxiliary_exit_ACK') or []
    exec(code,env);assert events[-2:]==['all_auxiliary_exit_ACK','release']
check('real_outer_finally_retains_FD_on_unproven_auxiliary_exit',final_barrier)

def static_entry_checks():
    text=(PACKAGE/'queue/qholder_entry.py').read_text()
    assert text.index("new_json(root/'STARTED.json'")<text.index('os.read(a.go_fd,3)')<text.index('os.execv(')
    text=(PACKAGE/'queue/qoccupancy.py').read_text()
    assert text.index("new_json(folder/'GO_RECORDED.json'")<text.index('os.write(write_fd')
    for rel in ['queue/qoccupancy.py','queue/qholder_entry.py','queue/qauthority.py','queue/qbatch.py','queue/qdrain.py','queue/qservice.py']:
        ast.parse((PACKAGE/rel).read_text())
check('CPU_wrapper_has_durable_identity_and_GO_before_GPU_exec_changed_AST_valid',static_entry_checks)

new_json(ROOT/('CPU_CHECKS'+run_suffix+'.json'),dict(status='PASS',checks=rows,number=len(rows),utc=utc(),synthetic=True,
    scope='per_GPU_control_handoff_only; real occupancy methods and actual entry/outer-loop AST with fake process and hardware boundaries',
    real_GPU_calls=0,model_imports=0,real_formal_commands=0,real_holder_start_stop=0,real_claims=0,real_lock_operations=0))
print(json.dumps({'status':'PASS','checks':len(rows)}))
