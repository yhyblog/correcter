"""Exercise real qdrain.main with CPU execution/authority boundaries only."""
import sys
from pathlib import Path
PKG=Path(__file__).resolve().parents[1];sys.path[:0]=[str(PKG/'queue'),str(PKG/'code')]
import inheritance
import os,fcntl,json,time
import qdrain,qbatch,qevents
from qio import new_json,read,ref
root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=False)
if os.getpid()!=os.getpgrp():os.setsid()
checks=[]
for fail in (False,True):
    case=root/('success' if not fail else 'failed_first');case.mkdir();chain=case/'chain';chain.mkdir()
    lock=(case/'synthetic.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    runtime=case/'RUNTIME_MANIFEST.json';new_json(runtime,dict(synthetic=True))
    release=case/'FIRST_GRANT.json';new_json(release,dict(synthetic=True))
    proposals=[];releases=[]
    for i in (1,2):
        p=dict(job_id='SYNTHETIC_CPU_'+str(i),sequence=i,task_id='SYNTHETIC_CPU',
            authorization_identity=dict(run_id='SYNTHETIC_'+str(i)),parents=[dict(synthetic=True)],
            source_keys=['SYNTHETIC_'+str(i)],paths=dict(output=str(case/('out%d'%i)),claim='SYNTHETIC_NOT_CREATED'))
        pp=case/('P%d.json'%i);new_json(pp,p);rp=case/('R%d.json'%i);new_json(rp,dict(proposal=ref(pp)));proposals.append(p);releases.append(rp)
    new_json(chain/'REQUEST.json',dict(socket='SYNTHETIC_NO_SOCKET',request_unix=0,holder_processes=[]))
    trace=[]
    qdrain.PACKAGE=case;qdrain.QUEUE=case/'queue';qdrain.held_reservation_fds=lambda:(lock.fileno(),)
    qdrain.send_existing_fd=lambda address,fd:trace.append(('same_FD_transfer',fd))
    from qreservation import holder_exit_ack
    qdrain.holder_exit_ack=lambda ctx:holder_exit_ack(ctx,status_reader=lambda:dict(updated=1,gpus={str(i):dict(state='reserved') for i in range(8)}))
    def execute(path,p,fds,ack):
        assert fds==(lock.fileno(),) and ack['status']=='all8_holder_processes_exited_before_formal_child'
        trace.append(('batch_compute',p['sequence']));out=Path(p['paths']['output']);(out/'launcher').mkdir(parents=True)
        v=out/'VALIDATION.json';new_json(v,dict(status='machine_validated',synthetic=True))
        result=dict(status='failed' if fail and p['sequence']==1 else 'complete',primary='synthetic failure' if fail else None,
            validation_ref=ref(v),process_exit_proven=True,publication_complete=True,restoration='deferred_to_queue')
        new_json(out/'launcher/LAUNCH_RESULT.json',result);new_json(out/'TERMINAL_MANIFEST.json',dict(synthetic=True))
        trace.append(('group_exit_then_publication',p['sequence']))
        return result,dict(source_dispositions={p['source_keys'][0]:'synthetic'},completion_order_failure_signatures=[])
    qbatch.execute=execute
    qdrain.terminal=lambda p,result:trace.append(('terminal_commit',p['sequence']))
    qevents.enqueue=lambda *a,**kw:trace.append(('outbox',a[1]))
    qdrain.first_grant=lambda:(dict(automatic_continuation_after_machine_pass=True),ref(release))
    pending=[(releases[1],proposals[1]),None]
    qdrain.prepare_next=lambda:pending.pop(0)
    sys.argv=['qdrain','--first-release',str(releases[0]),'--chain',str(chain)]
    rc=qdrain.main()
    batches=[x for x in trace if x[0]=='batch_compute']
    assert len(batches)==(1 if fail else 2) and rc==(3 if fail else 0)
    assert sum(x[0]=='same_FD_transfer' for x in trace)==1
    contender=(case/'synthetic.lock').open('a');held=False
    try:fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:held=True
    assert held;contender.close();lock.close()
    if not fail:assert (case/'queue/nodes/A/CONTINUATION_GRANT.json').exists()
    checks.append(dict(name='failure_does_not_admit_second' if fail else 'real_drain_two_batches_single_reservation',passed=True,trace=trace,
        exit=ref(chain/'DRAIN_EXIT.json'),synthetic_only=True))
new_json(root/'CHECKS.json',dict(status='PASS',checks=checks,formal_compute=0,holder_operations=0))
print(json.dumps(dict(status='PASS',checks=len(checks))))
