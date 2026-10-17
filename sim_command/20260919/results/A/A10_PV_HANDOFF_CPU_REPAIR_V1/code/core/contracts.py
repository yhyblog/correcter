"""Standard-library authorization and durable, entered-first accounting."""
import hashlib
import json
import os
import platform
from pathlib import Path
import time
from .handoff import HANDOFF_SPEC

TASK='A10_PV_OFFLINE_PREFLIGHT_V3'
RELEASE='P10_A_PV_OFFLINE_PREFLIGHT_V3'
CAMPAIGN=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
PACKAGE=Path(__file__).resolve().parents[2]

class ContractError(ValueError):pass

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def read(path):return json.loads(Path(path).read_text())
def write_new(path,value):
    with Path(path).open('x') as f:
        f.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

def verify_ref(row):
    p=Path(row['path'])
    if ('realpath' in row and str(p.resolve())!=row['realpath']) or sha(p)!=row['sha256']:
        raise ContractError('Frozen input identity changed: '+str(p))
    if 'size_bytes' in row and p.stat().st_size!=row['size_bytes']:raise ContractError('Input size changed: '+str(p))

def validate_metadata(control,board,release,proposal,release_path,hostname):
    if (control.get('campaign_id')!='corrector-sim-20260919' or control.get('mode')!='preflight'
        or control.get('formal_gpu_runs_enabled') is not True or control.get('stop_requested') is not False
        or control.get('active_compute_release_id')!=RELEASE or control.get('active_compute_task_ids')!=[TASK]
        or TASK not in control.get('allowed_task_ids',[])):
        raise ContractError('No current unique offline PV compute authorization')
    if (CAMPAIGN/control.get('active_compute_release','')).resolve()!=Path(release_path).resolve():
        raise ContractError('Active release path mismatch')
    if any(x.get('release_id')==RELEASE for x in control.get('closed_compute_releases',[])):
        raise ContractError('Release is closed')
    tasks=[t for t in board.get('tasks',[]) if t.get('id')==TASK]
    if len(tasks)!=1 or tasks[0].get('owner')!='A' or tasks[0].get('revision')!=1 or tasks[0].get('status') not in ['ready','running']:
        raise ContractError('Task board mismatch')
    if (CAMPAIGN/tasks[0].get('release','')).resolve()!=Path(release_path).resolve():raise ContractError('Task release mismatch')
    fixed=dict(status='released',issuer='analysis',campaign_id='corrector-sim-20260919',task_id=TASK,
        task_revision=1,node_role='A',release_id=RELEASE,owner_host=proposal['owner_host'],wave_participants=['A'],
        max_retries=0,timeout_seconds=1800,kill_grace_seconds=30,resource_caps=proposal['resource_caps'],
        device=proposal['device'],cuda_environment=proposal['cuda_environment'],
        occupancy_handoff=proposal['occupancy_handoff'],
        proposal_sha256=proposal['_sha256'],code_manifest_sha256=proposal['code_manifest']['sha256'],
        input_manifest_sha256=proposal['input_manifest']['sha256'],config_sha256=proposal['config']['sha256'],
        external_source_manifest_sha256=proposal['external_sources']['sha256'])
    if any(release.get(k)!=v for k,v in fixed.items()):raise ContractError('Release identity/caps differ from frozen proposal')
    if proposal.get('occupancy_handoff')!=HANDOFF_SPEC or control.get('active_occupancy_handoff')!=HANDOFF_SPEC:
        raise ContractError('Frozen V3 handoff metadata mismatch')
    if hostname!=proposal['owner_host']:raise ContractError('Wrong physical host')
    for k in ('run_id','wave_id','shard_id'):
        x=release.get(k)
        if not isinstance(x,str) or not x or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in x):
            raise ContractError('Invalid unique '+k)
    if control.get('current_compute_limits')!=proposal['resource_caps'] or control.get('per_task_compute_limits',{}).get(TASK)!=proposal['resource_caps']:
        raise ContractError('CONTROL must expose exactly this finite PV budget')
    return True

def load_authorization(release_path,full=False):
    release_path=Path(release_path).resolve()
    if release_path.parent!=CAMPAIGN/'releases' or release_path.name!=RELEASE+'.json':
        raise ContractError('Only the designated new analysis release is accepted')
    if (release_path.parent/(RELEASE+'_CLOSED.json')).exists():raise ContractError('Release closure exists')
    p=read(PACKAGE/'proposal/PROPOSAL.json');p['_sha256']=sha(PACKAGE/'proposal/PROPOSAL.json')
    r=read(release_path);r['_sha256']=sha(release_path)
    validate_metadata(read(CAMPAIGN/'CONTROL.json'),read(CAMPAIGN/'TASK_BOARD.json'),r,p,release_path,platform.node())
    if full:
        for key in ['config','input_manifest','external_sources','code_manifest','command']:
            verify_ref(p[key])
        for row in read(p['code_manifest']['path'])['files']:
            verify_ref(dict(row,path=str(PACKAGE/'code'/row['path'])))
        for row in read(p['input_manifest']['path'])['files']:verify_ref(row)
        for row in read(p['external_sources']['path'])['files']:verify_ref(row)
    return r,p

def gate(release_path,expected_sha):
    r,p=load_authorization(release_path,full=False)
    if r['_sha256']!=expected_sha:raise ContractError('Release changed after claim')

def claim(release):
    root=CAMPAIGN/'results/A/P10_PV_V3_release_claims';root.mkdir(parents=True,exist_ok=True)
    p=root/(RELEASE+'.json')
    write_new(p,dict(release_id=RELEASE,release_sha256=release['_sha256'],run_id=release['run_id'],
        launcher_pid=os.getpid(),unix_seconds=time.time(),consumed_on_any_outcome=True,unused_caps_reusable=False))
    return p

class Meter:
    def __init__(self,path,caps,gate_fn=lambda:None):
        self.path=Path(path);self.path.touch(exist_ok=False);self.caps=dict(caps);self.used=dict.fromkeys(caps,0)
        self.gate=gate_fn;self.next=0
    def append(self,row):
        with self.path.open('a') as f:
            f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def enter(self,name,units=None,detail=None):
        self.gate();units=units or {}
        for k,v in units.items():
            if k not in self.caps or type(v) is not int or v<0 or self.used[k]+v>self.caps[k]:raise ContractError('Budget denied before entry: '+k)
        self.next+=1
        row=dict(event_id=self.next,phase='entered',name=name,units=units,detail=detail,monotonic=time.monotonic())
        self.append(row)
        for k,v in units.items():self.used[k]+=v
        return self.next
    def finish(self,i,error=None):self.append(dict(event_id=i,phase='raised' if error else 'returned',error=None if error is None else dict(type=type(error).__name__,message=str(error)),monotonic=time.monotonic()))
    def call(self,name,fn,units=None,detail=None):
        i=self.enter(name,units,detail)
        try:x=fn()
        except BaseException as e:self.finish(i,e);raise
        self.finish(i);return x

def reconcile(path,caps):
    if not Path(path).exists():return dict(status='not_entered',entered=dict.fromkeys(caps,0),returned=dict.fromkeys(caps,0),unresolved=[],counts_complete=True,corrupt_records=[])
    starts={};ends={};entered=dict.fromkeys(caps,0);returned=dict.fromkeys(caps,0);bad=[]
    for lineno,line in enumerate(Path(path).read_text().splitlines(),1):
        try:
            r=json.loads(line);i=r['event_id']
            if type(i) is not int or r['phase'] not in ['entered','returned','raised']:raise ValueError('Invalid event identity/phase')
            if r['phase']=='entered' and (i in starts or any(k not in caps or type(v) is not int or v<0 for k,v in r['units'].items())):raise ValueError('Duplicate or invalid entry')
            if r['phase']!='entered' and (i not in starts or i in ends):raise ValueError('Orphan/duplicate terminal record')
        except (ValueError,KeyError,TypeError,AttributeError) as error:
            bad.append(dict(line=lineno,error=str(error),raw=line));continue
        if r['phase']=='entered':
            starts[i]=r
            for k,v in r['units'].items():entered[k]+=v
        else:
            ends[i]=r
            if r['phase']=='returned':
                for k,v in starts[i]['units'].items():returned[k]+=v
    return dict(status='incomplete_or_corrupt_journal' if bad else 'reconciled',entered=entered,returned=returned,entered_events=len(starts),terminal_events=len(ends),
        failed=[i for i,r in ends.items() if r['phase']=='raised'],unresolved=sorted(set(starts)-set(ends)),
        counts_complete=not bad,corrupt_records=bad,
        charge_rule='entered units charged once; raised or missing terminal record never refunds entry; if corrupt records exist, counts are known lower bounds only and release remains consumed',units_are_incremental=True)
