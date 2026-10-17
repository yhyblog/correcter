"""Pure JSON authority and release-only filesystem gates. No native imports."""
import json,os,socket,time
from pathlib import Path
from core.contracts import CAMPAIGN,PACKAGE,ContractError,read,sha
from observation_phase import validate_observation_config
TASK='A11_COMMON_POOL_FIRST_PARENT_V4'
RELEASE='P11_A_COMMON_POOL_FIRST_PARENT_V4'
def check_documents(control,board,release,proposal,host):
    identity=proposal['authorization_identity']
    if release.get('status')!='released' or release.get('closed') or release.get('consumed'):raise ContractError('release not open/released')
    if release.get('task_ids')!=[TASK] or release.get('task_revision')!=1 or release.get('release_id')!=RELEASE:raise ContractError('wrong release identity')
    if release.get('owner_host')!=host or proposal['owner_host']!=host:raise ContractError('host mismatch')
    if release.get('proposal_sha256')!=proposal['_sha256']:raise ContractError('proposal SHA mismatch')
    if release.get('identity')!=identity or release.get('resource_caps')!=proposal['resource_caps']:raise ContractError('identity/caps mismatch')
    if release.get('device')!=proposal['device'] or release.get('source')!=proposal['source']:raise ContractError('UUID/source mismatch')
    if release.get('paths')!=proposal['paths'] or release.get('timeouts')!=proposal['timeouts'] or release.get('storage')!=proposal['storage']:raise ContractError('path/timeout/storage drift')
    if control.get('stop_requested') or control.get('formal_gpu_runs_enabled') is not True or control.get('mode')!='run':raise ContractError('CONTROL not computing')
    if control.get('active_compute_release_id')!=RELEASE or control.get('active_compute_task_ids')!=[TASK] or control.get('active_compute_release')!='releases/'+RELEASE+'.json':raise ContractError('CONTROL release mismatch')
    if control.get('current_compute_limits')!=proposal['resource_caps']:raise ContractError('CONTROL caps mismatch')
    if TASK not in control.get('allowed_task_ids',[]) or control.get('per_task_compute_limits',{}).get(TASK)!=proposal['resource_caps']:raise ContractError('CONTROL allowed task/per-task caps mismatch')
    rows=[x for x in board.get('tasks',[]) if x.get('id')==TASK]
    if len(rows)!=1:raise ContractError('unique board entry required')
    row=rows[0]
    if row.get('status') not in ('ready','running') or row.get('revision')!=1 or row.get('owner')!='A' or row.get('release')!='releases/'+RELEASE+'.json':raise ContractError('board status/identity mismatch')
    for key in ('run_id','wave_id','shard_id'):
        if row.get(key)!=identity[key]:raise ContractError('board '+key+' mismatch')
    if release.get('wave_participants')!=['A'] or release.get('max_commands')!=1 or release.get('max_claims')!=1 or release.get('max_retries')!=0:raise ContractError('wave scope mismatch')
    check_admission_document(release,proposal)
    return {'status':'PASS','board_status':row['status'],'release_status':release['status'],'grants_authorization':False}
def verify_ref(row):
    p=Path(row['path'])
    if 'realpath' in row and str(p.resolve())!=row['realpath']:raise ContractError('realpath mismatch '+str(p))
    if 'size_bytes' in row and p.stat().st_size!=row['size_bytes']:raise ContractError('size mismatch '+str(p))
    if sha(p)!=row['sha256']:raise ContractError('SHA mismatch '+str(p))
def load_authorization(path,full=False):
    path=Path(path).resolve()
    if path!=CAMPAIGN/'releases'/(RELEASE+'.json'):raise ContractError('wrong release path')
    r=read(path);p=read(PACKAGE/'proposal/PROPOSAL.json');p['_sha256']=sha(PACKAGE/'proposal/PROPOSAL.json')
    check_documents(read(CAMPAIGN/'CONTROL.json'),read(CAMPAIGN/'TASK_BOARD.json'),r,p,socket.gethostname())
    if path.with_name(RELEASE+'_CLOSED.json').exists():raise ContractError('closed release record exists')
    for name in ('config','budget','code_manifest','input_manifest','external_manifest','closure','sidecar_ready','command_ref','preparation_manifest'):
        verify_ref(p[name])
    validate_observation_config(read(p['config']['path']))
    if full:
        for name in ('code_manifest','input_manifest','external_manifest','preparation_manifest'):
            manifest=read(p[name]['path'])
            for row in manifest['files']:verify_ref(row)
            for base in manifest.get('inherited_manifests',[]):
                verify_ref(base)
                for row in read(base['path'])['files']:verify_ref(row)
    r['_sha256']=sha(path)
    return r,p
def gate(path,expected,proposal):
    if sha(path)!=expected:raise ContractError('release changed')
    if Path(path).with_name(RELEASE+'_CLOSED.json').exists():raise ContractError('release closed')
    check_documents(read(CAMPAIGN/'CONTROL.json'),read(CAMPAIGN/'TASK_BOARD.json'),read(path),proposal,socket.gethostname())
from storage_admission import exclusive_metadata,gate as quota_gate,check_admission_document
def exclusive_record(path,value,kind='command'):
    return exclusive_metadata(path,value,kind)
def claim(r,p):
    return exclusive_record(p['paths']['claim'],dict(release_sha256=r['_sha256'],run_id=r['identity']['run_id'],
        consumed=True,remaining_caps_reusable=False,time=time.time()),'claim')
