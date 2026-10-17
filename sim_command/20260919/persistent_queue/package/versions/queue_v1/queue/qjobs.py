"""One-shot metadata, command and shared source/storage transactions."""
import os
from pathlib import Path
from qio import PACKAGE, QUEUE, CAMPAIGN, read, ref, verify, new_json, process_identity, utc
from qauthority import AUTH_SHA, collection_gate, current, validate_proposal, AuthorityFault, package_ready
from qplan import ordered_pending, build_metadata
from qledger import Ledger, empty_state, reserve, enter, finish, technical_breaker, LedgerFault


def ledger():
    return Ledger(QUEUE/'ledger',empty_state(AUTH_SHA))


def snapshot():
    _,state,_=ledger().latest()
    if state['authorization_sha256']!=AUTH_SHA:
        raise LedgerFault('shared ledger stage identity')
    return state


def next_rows():
    if (QUEUE/'nodes/A/BLOCKED.json').exists():
        raise LedgerFault('persistent node block requires explicit reconciliation')
    state=snapshot()
    if any(j['node']=='A' and j['state']!='terminal' for j in state['jobs'].values()):
        raise LedgerFault('unresolved existing command: no re-admission/retry')
    if state.get('stage_blocked') or state['node_breakers'].get('A',{}).get('blocked'):
        raise LedgerFault('persistent stage/node fault gate')
    return ordered_pending(read(QUEUE/'plan/SOURCES_V2.json')['sources'],state['sources'])[:8],len(state['jobs'])+1


def capacity(path):
    p=Path(path)
    while not p.exists():p=p.parent
    st=os.statvfs(p)
    return dict(path=str(path),observed_ancestor=str(p),device=p.stat().st_dev,
                available_bytes=st.f_bavail*st.f_frsize,available_inodes=st.f_favail,utc=utc(),
                project_quota=None,exclusive_filesystem_reservation=False)


def prepare_next():
    rows,sequence=next_rows()
    if not rows:return None
    grant=collection_gate(sequence=sequence,admission=True)
    ready=package_ready()
    if ref(QUEUE/'package/READY.json')['sha256']!=read(QUEUE/'nodes/A/DAEMON_READY.json')['package_sha256']:
        raise LedgerFault('running service package READY changed; no hot deployment')
    job_id='A_pool_v2_b%03d'%sequence
    root=QUEUE/'jobs/A'/job_id
    if root.exists():raise LedgerFault('job metadata already exists; consumed/unknown, do not rebuild')
    if sequence==1:
        proposal_path=PACKAGE/'proposal/first8/PROPOSAL.json';p=read(proposal_path)
        if p['source_keys']!=[r['source_key'] for r in rows]:raise LedgerFault('first8 source order conflict')
        root.mkdir(parents=True,exist_ok=False)
    else:
        p=build_metadata(rows,root,job_id=job_id,sequence=sequence,
            package_manifest_ref=ref(PACKAGE/'RUNTIME_MANIFEST.json'),code_manifest_ref=ref(PACKAGE/'code/CODE_MANIFEST.json'),
            authorization_ref=ref(QUEUE/'AUTHORIZATION_V2.json'))
        proposal_path=root/'PROPOSAL.json'
    validate_proposal(p,full=False)
    for path in p['paths'].values():
        if Path(path).exists():raise LedgerFault('command/claim/output/cache already exists')
    observations=[capacity(p['paths'][k]) for k in ('output','cache')]
    from qresources import observe,memory_decision
    memory=memory_decision(observe(),len(p['parents']))
    if len({r['device'] for r in observations})!=1:raise LedgerFault('unquoted different output/cache filesystems')
    r=dict(schema='queue_derived_release_v1',status='released',node='A',owner_host=p['owner_host'],
           campaign_id=p['campaign_id'],release_id=p['release_id'],task_id=p['task_id'],task_revision=1,
           authorization_identity=p['authorization_identity'],proposal=ref(proposal_path),grant=grant,
           authorization_sha256=AUTH_SHA,resource_caps=p['resource_caps'],command_opportunities=1,retries=0)
    rpath=root/'DERIVED_RELEASE.json';new_json(rpath,r)
    new_json(p['paths']['command_record'],dict(job_id=job_id,release=ref(rpath),source_keys=p['source_keys'],
        utc=utc(),command_opportunity_consumed=True,process=process_identity(),formal_entered=False,no_retry=True))
    job=dict(job_id=job_id,node='A',source_keys=p['source_keys'],resource_caps=p['resource_caps'],release=ref(rpath))
    totals=read(QUEUE/'plan/AGGREGATE_LIMITS_V2.json')['resource_caps_total'];s=p['storage']
    committed=ledger().transact(lambda state:reserve(state,job,source_rows=read(QUEUE/'plan/SOURCES_V2.json')['sources'],
        total_caps=totals,available_bytes=min(x['available_bytes'] for x in observations),
        available_inodes=min(x['available_inodes'] for x in observations),storage_bytes=s['admission_bytes'],
        storage_inodes=s['minimum_available_inodes'],free_floor=s['minimum_remaining_space_bytes']),node='A',operation='reserve_batch')
    new_json(p['paths']['claim'],dict(run_id=p['authorization_identity']['run_id'],job_id=job_id,
        release_sha256=ref(rpath)['sha256'],authorization_sha256=AUTH_SHA,process=process_identity(),
        shared_generation=committed['generation'],source_keys=p['source_keys'],no_retry=True))
    new_json(root/'STORAGE_ADMISSION.json',dict(observations=observations,logical_reservation=committed['state']['storage'][job_id],
        mode='bounded_queue_stage_v2',accepts_monitoring_gaps=True,shared_ledger_generation=committed['generation']))
    new_json(root/'MEMORY_ADMISSION.json',memory)
    return rpath,p


def mark_entered(p):
    return ledger().transact(lambda s:enter(s,p['job_id'],process_identity()),node='A',operation='enter_batch')


def terminal(p,result):
    def apply(state):
        state=finish(state,p['job_id'],result)
        state=technical_breaker(state,'A',result.get('parents',[]))
        if result.get('status')!='machine_validated':
            state['node_breakers']['A']=dict(blocked=True,reason=result.get('reason','technical acceptance failed'))
        return state
    return ledger().transact(apply,node='A',operation='terminal_batch')
