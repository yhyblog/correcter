"""Finite first-parent admission. Capacity observation is never a reservation."""
import json,math,os,re,stat,time
from pathlib import Path
from core.contracts import ContractError
PRE_GATE_JSON_BYTES=4096
FIELDS={
 'command':{'started','release_sha256','command_opportunity_consumed'},
 'claim':{'time','release_sha256','run_id','consumed','remaining_caps_reusable'},
}
def metadata_bytes(value,kind):
    if kind not in FIELDS or type(value) is not dict or set(value)!=FIELDS[kind]:raise ContractError('pre-gate metadata fields')
    if type(value['release_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',value['release_sha256']):raise ContractError('metadata SHA')
    clock=value['started' if kind=='command' else 'time']
    if type(clock) not in (float,int) or not math.isfinite(clock) or clock<0:raise ContractError('metadata clock')
    if kind=='command':
        if value['command_opportunity_consumed'] is not True:raise ContractError('command opportunity must be consumed')
    else:
        if value['consumed'] is not True or value['remaining_caps_reusable'] is not False:raise ContractError('claim one-shot semantics')
        if type(value['run_id']) is not str or not re.fullmatch('[A-Za-z0-9_.:-]{1,160}',value['run_id']):raise ContractError('metadata run identity')
    raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
    if len(raw)>PRE_GATE_JSON_BYTES:raise ContractError('pre-gate metadata hard bytes')
    return raw
def exclusive_metadata(path,value,kind):
    raw=metadata_bytes(value,kind)  # validation precedes mkdir/open, no native call
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        view=memoryview(raw)
        while view:
            n=os.write(fd,view)
            if n<=0:raise OSError('metadata write made no progress')
            view=view[n:]
        os.fsync(fd)
    finally:os.close(fd)
    return str(path)
def check_admission_document(release,proposal):
    value=release.get('storage_admission')
    required=dict(mode='bounded_first_parent',run_id=release['identity']['run_id'],
        project_quota_known=False,exclusive_reservation=False,accepts_monitoring_gaps=True)
    if value!=required:raise ContractError('explicit bounded-first-parent risk admission missing or altered')
    if proposal['storage']['mode']!='bounded_first_parent':raise ContractError('wrong storage mode')
    return required
def nearest_existing(path):
    path=Path(path).resolve()
    while not path.exists():
        if path.parent==path:raise ContractError('no capacity root')
        path=path.parent
    return path
def capacity(path):
    root=nearest_existing(path);v=os.statvfs(root)
    return dict(requested_path=str(path),observed_path=str(root),device=os.stat(root).st_dev,
        available_bytes=v.f_bavail*v.f_frsize,available_inodes=v.f_favail,time=time.time(),
        scope='statvfs caller-available filesystem capacity; concurrent use and project quota unknown')
def gate(release,proposal,capacity_fn=capacity):
    check_admission_document(release,proposal)
    s=proposal['storage'];rows=[capacity_fn(proposal['paths'][k]) for k in ('output','cache')]
    if len({r['device'] for r in rows})!=1:raise ContractError('unquoted split filesystems')
    need=s['first_parent_admission_bytes']+s['minimum_remaining_space_bytes']
    if any(r['available_bytes']<need or r['available_inodes']<s['minimum_available_inodes'] for r in rows):
        raise ContractError('insufficient observed first-parent capacity')
    return dict(status='admitted_observation_only',mode=s['mode'],observations=rows,required_available_bytes=need,
        project_quota_known=False,exclusive_reservation=False,guaranteed_future_free_bytes=None,
        warning='no atomic quota; third-party/shared cache writes outside coverage remain unknown')
def scan_private(root,max_entries):
    root=Path(root);total=0;entries=0;stack=[root];seen=set()
    while stack:
        with os.scandir(stack.pop()) as children:
            for child in children:
                entries+=1
                if entries>max_entries:raise ContractError('private temp directory entry monitor cap')
                st=child.stat(follow_symlinks=False)
                if stat.S_ISLNK(st.st_mode):raise ContractError('private temp symlink outside monitored scope')
                if stat.S_ISDIR(st.st_mode):stack.append(Path(child.path))
                elif stat.S_ISREG(st.st_mode):
                    key=(st.st_dev,st.st_ino)
                    if key not in seen:total+=st.st_size;seen.add(key)
                else:raise ContractError('private temp unsupported file type')
    return dict(logical_file_bytes=total,entries=entries)
class PrivateMonitor:
    def __init__(self,root,storage,store,scan_fn=scan_private,capacity_fn=capacity):
        self.root=Path(root);self.s=storage;self.store=store;self.scan=scan_fn;self.capacity=capacity_fn
        self.polls=0;self.last=None;self.failure=None
    def check(self):
        try:
            if self.polls>=self.s['monitor_max_polls']:raise ContractError('finite storage monitor budget exhausted')
            self.polls+=1
            row=self.scan(self.root,self.s['private_temp_max_entries']);space=self.capacity(self.root)
            self.last=dict(poll=self.polls,**row,capacity=space)
            self.store.append('STORAGE_MONITOR.jsonl',(json.dumps(self.last,allow_nan=False)+'\n').encode())
            if row['logical_file_bytes']>self.s['private_temp_cache_budget_bytes']:raise ContractError('private temp monitoring threshold exceeded')
            if space['available_bytes']<self.s['minimum_remaining_space_bytes']:raise ContractError('observed remaining space below floor')
            return self.last
        except BaseException as e:
            self.failure=dict(type=type(e).__name__,message=str(e));raise
    def summary(self):
        return dict(polls=self.polls,last=self.last,failure=self.failure,hard_quota=False,
            maximum_overshoot_bytes=None,overshoot_reason='writes between/within scans and unlinked-open files are not bounded; drain may continue writing',
            shared_HF_and_native_outside_private_root_bytes=None,process_group_RSS_peak_bytes=None,
            coverage='private temp/cache linked regular files and statvfs; not shared caches, memory, or native outside paths')
