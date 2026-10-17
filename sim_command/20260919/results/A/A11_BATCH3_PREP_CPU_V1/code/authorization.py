"""Batch-only identity/config authority. CPU fixtures use pure JSON entry points."""
import hashlib,json,socket,time
from pathlib import Path
from core.contracts import CAMPAIGN,PACKAGE,ContractError,read,sha
from batch_scheduler import GlobalFault,validate_schedule
from task_profiles import FIXED_SLOTS,validate_config
from budget import parent_caps,batch_caps,batch_storage,batch_timeouts,scheduler_caps
from observation_phase import validate_observation_config
from batch_storage import check_admission_document,gate as quota_gate
from storage_admission import exclusive_metadata
from source_plan import select_next_slots,processed_keys,check_source_seed
from task_profiles import PROFILES

TASK='A11_COMMON_POOL_BATCH3_V1'
RELEASE='P11_A_COMMON_POOL_BATCH3_V1'
BOUND=('authorization_identity','parents','concurrency','resource_caps','scheduler_caps','paths','timeouts','storage')

def verify_ref(row):
    p=Path(row['path'])
    if 'realpath' in row and str(p.resolve())!=row['realpath']:raise GlobalFault('realpath mismatch '+str(p))
    if 'size_bytes' in row and p.stat().st_size!=row['size_bytes']:raise GlobalFault('size mismatch '+str(p))
    if sha(p)!=row['sha256']:raise GlobalFault('SHA mismatch '+str(p))

def check_parent_documents(proposal,configs,accepted,processed=None):
    parents=proposal['parents'];validate_schedule(parents,proposal['concurrency'])
    if type(proposal['concurrency']) is not int or proposal['concurrency']!=2:
        raise GlobalFault('Batch3 freezes measured concurrency2; no fallback')
    if processed is None:processed=read(proposal['processed_source_dispositions']['path'])
    selected=select_next_slots(list(PROFILES),processed)
    if selected!=FIXED_SLOTS:raise GlobalFault('processed identity selection changed')
    if [(p['source']['task'],p['source']['ordinal'],p['source']['cut']) for p in parents]!=FIXED_SLOTS:
        raise GlobalFault('eight fixed coverage slots changed')
    old={x['source']['source_id'] for x in processed['parents']}
    if any(p['source']['source_id'] in old for p in parents):raise GlobalFault('processed source cannot be resampled, including normal-only')
    if not {x['source']['source_id'] for x in accepted['parents']}<=old:raise GlobalFault('accepted index missing from dispositions')
    for field in ('parent_source_id','env_seed','master_seed'):
        prior={x['source'][field] for x in processed['parents']}
        if any(p['source'][field] in prior for p in parents):raise GlobalFault('accepted source/seed overlap '+field)
    if len({p['source']['env_seed'] for p in parents})!=8 or len({p['source']['master_seed'] for p in parents})!=8:
        raise GlobalFault('proposed source seeds overlap')
    seen=set()
    for parent,cfg in zip(parents,configs,strict=True):
        check_source_seed(parent['source'])
        validate_config(cfg);validate_observation_config(cfg)
        if cfg['source']!=parent['source'] or cfg['device']!=parent['device'] or cfg['native']['device']!=parent['device']:
            raise GlobalFault('parent config source/device mismatch')
        signature=hashlib.sha256(json.dumps(cfg['source'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        expected_ref={k:parent['source_ref'][k] for k in ('path','sha256')}|{'format':'json'}
        if cfg['source_signature']!=signature or cfg['source_manifest_ref']!=expected_ref:
            raise GlobalFault('source signature/manifest binding mismatch')
        if cfg['source']['ordinal']//2%2!=0:raise GlobalFault('parent does not belong to A')
        if parent['resource_caps']!=parent_caps(cfg['source']['task'],cfg['source']['cut']):raise GlobalFault('parent caps mismatch')
        for key in ('output','cache'):
            expected=Path(proposal['paths'][key])/parent['parent_key']
            if Path(parent['paths'][key])!=expected or str(expected) in seen:raise GlobalFault('parent path collision')
            seen.add(str(expected))
        if parent['identity']['run_id']!=proposal['authorization_identity']['run_id']+':'+parent['parent_key']:
            raise GlobalFault('parent run identity mismatch')
    if proposal['resource_caps']!=batch_caps(parents):raise GlobalFault('batch total caps mismatch')
    c=proposal['concurrency']
    if proposal['timeouts']!=batch_timeouts(c) or proposal['storage']!=batch_storage(c) or proposal['scheduler_caps']!=scheduler_caps(c):
        raise GlobalFault('batch auxiliary bounds drift')
    return dict(status='PASS',parents=8,configs_301_phase_count=len(configs),old_sources_reused=0)

def check_documents(control,board,release,proposal,host):
    if release.get('status')!='released' or release.get('closed') or release.get('consumed'):raise GlobalFault('release not open/released')
    if release.get('release_id')!=RELEASE or release.get('task_ids')!=[TASK] or release.get('task_revision')!=1:raise GlobalFault('release identity')
    if release.get('owner_host')!=host or proposal['owner_host']!=host:raise GlobalFault('host mismatch')
    if release.get('proposal_sha256')!=proposal['_sha256']:raise GlobalFault('proposal SHA mismatch')
    if any(release.get(k)!=proposal[k] for k in BOUND):raise GlobalFault('release differs from frozen batch proposal')
    if release.get('wave_participants')!=['A'] or release.get('max_commands')!=1 or release.get('max_claims')!=1 or release.get('max_retries')!=0:raise GlobalFault('one-shot A-only wave')
    if control.get('stop_requested') or control.get('formal_gpu_runs_enabled') is not True or control.get('mode')!='run':raise GlobalFault('CONTROL not computing')
    if control.get('active_compute_release_id')!=RELEASE or control.get('active_compute_release')!='releases/'+RELEASE+'.json' or control.get('active_compute_task_ids')!=[TASK]:raise GlobalFault('CONTROL identity')
    if control.get('current_compute_limits')!=proposal['resource_caps'] or control.get('per_task_compute_limits',{}).get(TASK)!=proposal['resource_caps'] or TASK not in control.get('allowed_task_ids',[]):raise GlobalFault('CONTROL task/caps')
    rows=[x for x in board['tasks'] if x.get('id')==TASK]
    if len(rows)!=1:raise GlobalFault('unique task-board row')
    row=rows[0]
    if row.get('status') not in ('ready','running') or row.get('revision')!=1 or row.get('owner')!='A' or row.get('release')!='releases/'+RELEASE+'.json':raise GlobalFault('board metadata')
    if any(row.get(k)!=proposal['authorization_identity'][k] for k in ('run_id','wave_id','shard_id')):raise GlobalFault('board run/wave/shard')
    check_admission_document(release,proposal)
    return dict(status='PASS',board_status=row['status'],release_status=release['status'],grants_authorization=False)

def load_authorization(path,full=False):
    path=Path(path).resolve()
    if path!=CAMPAIGN/'releases'/(RELEASE+'.json'):raise GlobalFault('wrong Batch3 release path')
    r=read(path);p=read(PACKAGE/'proposal/PROPOSAL.json');p['_sha256']=sha(PACKAGE/'proposal/PROPOSAL.json')
    check_documents(read(CAMPAIGN/'CONTROL.json'),read(CAMPAIGN/'TASK_BOARD.json'),r,p,socket.gethostname())
    if path.with_name(RELEASE+'_CLOSED.json').exists():raise GlobalFault('closed release record')
    refs=['code_manifest','input_manifest','external_manifest','inherited_package_manifest',
          'source_evidence','closure','sidecar_ready','command_ref','accepted_parent_index','processed_source_dispositions','config_manifest']
    for key in refs:verify_ref(p[key])
    configs=[]
    for parent in p['parents']:
        verify_ref(parent['config']);verify_ref(parent['source_ref'])
        cfg=read(parent['config']['path'])
        if read(parent['source_ref']['path'])!=parent['source']:raise GlobalFault('source JSON differs from proposed identity')
        configs.append(cfg)
    check_parent_documents(p,configs,read(p['accepted_parent_index']['path']))
    if full:
        seen=set()
        def check_manifest(row):
            verify_ref(row)
            if row['path'] in seen:return
            seen.add(row['path']);m=read(row['path'])
            for f in m['files']:verify_ref(f)
            for old in m.get('inherited_manifests',[]):check_manifest(old)
        for key in ('code_manifest','input_manifest','external_manifest','inherited_package_manifest','config_manifest'):
            check_manifest(p[key])
    r['_sha256']=sha(path)
    return r,p

def select_parent(proposal,key):
    rows=[p for p in proposal['parents'] if p['parent_key']==key]
    if len(rows)!=1:raise GlobalFault('parent outside frozen eight-source plan')
    return rows[0]

def gate(path,expected,proposal):
    if sha(path)!=expected:raise GlobalFault('release changed')
    if Path(path).with_name(RELEASE+'_CLOSED.json').exists():raise GlobalFault('release closed')
    check_documents(read(CAMPAIGN/'CONTROL.json'),read(CAMPAIGN/'TASK_BOARD.json'),read(path),proposal,socket.gethostname())

def exclusive_record(path,value,kind='command'):
    return exclusive_metadata(path,value,kind)

def claim(release,proposal):
    return exclusive_record(proposal['paths']['claim'],dict(release_sha256=release['_sha256'],
        run_id=proposal['authorization_identity']['run_id'],consumed=True,remaining_caps_reusable=False,time=time.time()),'claim')
