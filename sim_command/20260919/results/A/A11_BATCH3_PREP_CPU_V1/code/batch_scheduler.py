"""Actual bounded state machine. Backend supplies processes or explicit CPU fakes."""
import time
from controller import branch_allows_next
from pool_protocol import ARMS
from core.contracts import ContractError
from core.failure_evidence import record_failure
from task_profiles import profile

class GlobalFault(ContractError):
    pass

def validate_schedule(parents, concurrency):
    if type(concurrency) is not int or concurrency not in (1,2,4,8):
        raise ContractError('unquoted concurrent parent count')
    if not 1 <= len(parents) <= 8:
        raise ContractError('finite one-to-eight parent plan required')
    for field in ('parent_key',):
        if len({p[field] for p in parents}) != len(parents):raise ContractError('duplicate parent identity')
    for field in ('source_id','parent_source_id'):
        if len({p['source'][field] for p in parents}) != len(parents):raise ContractError('duplicate source')
    if len({p['device']['gpu_uuid'] for p in parents}) != len(parents):
        raise ContractError('one fixed UUID per proposed parent; no assignment reuse')
    for p in parents:
        profile(p['source']['task'],p['source']['cut'])
    return True

def run_schedule(parents, concurrency, backend, *, gate, emit, limits, timeouts,
                 clock=time.monotonic, pause=time.sleep):
    """No threads, GPUs, locks or holders here. All launch operations go via backend.

    A process is one cold branch; a worker slot retains the entire parent until
    its sequential branches finish. Publication follows the whole-wave exit
    barrier. The runtime and CPU integration fixtures call this same function.
    """
    validate_schedule(parents,concurrency)
    started=clock(); pending=list(parents); active={}; finished=[]; polls=0; admissions=0; starts=0
    primary=None; cleanup=None; publications=[]; publication_failures=[]
    try:
        while pending or active:
            gate()
            if clock()-started>timeouts['reserved_wave_seconds']:raise GlobalFault('wave admission timeout')
            polls+=1
            if polls>limits['poll_iterations']:raise GlobalFault('scheduler polling cap')
            backend.refresh()
            while pending and len(active)<concurrency:
                parent=pending.pop(0);key=parent['parent_key'];admissions+=1
                if admissions>limits['parent_admissions']:raise GlobalFault('parent admission cap')
                active[key]=dict(parent=parent,index=0,handle=None,rows=[],started=clock())
                emit('parent_admitted',parent_key=key,gpu_uuid=parent['device']['gpu_uuid'])
            for key in list(active):
                state=active[key];parent=state['parent']
                if clock()-state['started']>timeouts['parent_seconds']:raise GlobalFault('parent process deadline requires wave drain')
                job=ARMS[state['index']]
                if state['handle'] is None:
                    starts+=1
                    if starts>limits['branch_process_starts']:raise GlobalFault('branch start cap')
                    state['handle']=backend.start(parent,job)
                    emit('branch_started',parent_key=key,attempt_role=job[0],gpu_uuid=parent['device']['gpu_uuid'])
                result=backend.poll(state['handle'])
                if result is None:continue
                state['rows'].append(result);backend.record_exit(parent,job,result)
                if result.get('failure_scope')=='wave':raise GlobalFault('child reports system fault: '+key)
                emit('branch_compute_exited',parent_key=key,attempt_role=job[0],returncode=result['returncode'])
                eligible=branch_allows_next(job,result)
                state['index']+=1;state['handle']=None
                if not eligible or state['index']==len(ARMS):
                    finished.append(dict(parent_key=key,rows=state['rows'],branches_started=state['index'],
                        status='complete' if eligible and state['index']==15 else 'parent_stopped',
                        unstarted_branches=[j[0] for j in ARMS[state['index']:]],elapsed_seconds=clock()-state['started']))
                    del active[key]
                # No more than one new branch per parent in one poll iteration.
            if pending or active:pause(timeouts['scheduler_poll_seconds'])
    except BaseException as error:
        primary=record_failure(error,branch=None,stage='batch_scheduler',category='primary',
            synthetic=getattr(backend,'synthetic',False))
        primary['scope']='wave'
        emit('wave_stopped',error=primary)
    finally:
        # This backend owns the one isolated formal process group, never other jobs.
        cleanup=backend.drain()
        emit('whole_wave_compute_exit',cleanup=cleanup)
    if cleanup.get('status')!='all_formal_group_members_exited':
        raise GlobalFault('publication forbidden before whole group exit')
    publish_started=clock()
    for parent in parents:
        if not backend.was_started(parent):continue
        if clock()-publish_started>timeouts['publication_seconds']:
            primary=primary or dict(type='TimeoutError',message='publication deadline',scope='wave');break
        try:
            publications.append(backend.publish(parent))
            emit('parent_data_published',parent_key=parent['parent_key'])
        except BaseException as error:
            failure=record_failure(error,branch=None,stage='batch_publication',category='primary',
                synthetic=getattr(backend,'synthetic',False))
            failure['scope']='wave_publication';publication_failures.append(failure);primary=primary or failure
            break
    return dict(status='complete' if primary is None and len(finished)==len(parents) and all(x['status']=='complete' for x in finished) else 'partial_or_failed',
        primary=primary,cleanup=cleanup,parents=finished,publications=publications,publication_failures=publication_failures,
        admission_count=admissions,branch_starts=starts,polls=polls,
        maximum_concurrent_parents=concurrency,unadmitted=[p['parent_key'] for p in pending],
        interrupted_active=[dict(parent_key=k,rows=s['rows'],branch_index=s['index']) for k,s in active.items()],
        no_retry=True,publication_is_not_analysis_acceptance=True)

def lifecycle_driver(command, exit_reader, restore_observer):
    """The real launcher delegates reservation/release to its single lifecycle run."""
    code=command()
    exited=exit_reader()
    if exited is None or exited.get('status')!='all_formal_group_members_exited':
        raise GlobalFault('missing owned wave exit barrier; never claim restoration')
    restored=restore_observer()
    return dict(returncode=code,process_group_exit=exited,restoration=restored)

class OnceObservation:
    """An exception must not cause a second restoration observation/probe."""
    def __init__(self,fn):self.fn=fn;self.called=False;self.value=None
    def __call__(self):
        if not self.called:
            self.called=True
            try:self.value=self.fn()
            except BaseException as error:
                self.value=dict(status='observation_failed',type=type(error).__name__,error=str(error))
        return self.value
