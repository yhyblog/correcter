"""C-only scientific authorization, finite deadline, immutable input checks."""
import os, socket, time
from pathlib import Path
from paths import ROOT,CAMPAIGN,AUTH_SHA,TASK
from qio import read,sha,same_process
class AdmissionStop(RuntimeError):pass
_last=0.
def authority():
    grant=CAMPAIGN/'deadline_20260924/PER_BASE_AUXILIARY_TRAINING_AUTHORIZATION_V1.json'
    if sha(grant)!=AUTH_SHA:raise AdmissionStop('auxiliary authorization changed')
    a=read(grant);c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json');node=q['nodes']['C']
    identity=read(CAMPAIGN/'nodes/C/identity.json')
    if a['status']!='released' or c.get('stop_requested') or q.get('global_stop') or not node['enabled']:
        raise AdmissionStop('stop or disabled node')
    if socket.gethostname()!=node['owner_host'] or identity['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise AdmissionStop('C host/boot mismatch')
    follows=[x for x in node.get('authorized_followups',[]) if x['task_id']==TASK]
    if not follows or follows[0]['authorization']['sha256']!=AUTH_SHA:raise AdmissionStop('followup release absent')
    prior=CAMPAIGN/'results/C/C_D24_R_TRIGGER_MODES_V1'
    terminal=read(prior/'RESULT.json');claimed=read(prior/'PROCESS.json')
    if not terminal['all_owned_descendants_exited'] or same_process(dict(claimed,host=claimed['hostname'])):
        raise AdmissionStop('predecessor formal family has not exited')
    cfg=read(ROOT/'config/CONFIG.json')
    if cfg['planned_prior_attempts']!=7013 or cfg['planned_prior_attempts']+cfg['stage_attempt_cap']>a['nodes']['C']['cumulative_attempt_cap']:
        raise AdmissionStop('C cumulative budget mismatch')
    for k in ['source_manifest','test_sources','method_frozen']:
        r=cfg[k]
        if sha(r['path'])!=r['sha256']:raise AdmissionStop('sealed input changed: '+k)
    return a
def before_cutoff():
    return time.time()<read(ROOT/'config/CONFIG.json')['absolute_wall_deadline_unix'] and not (ROOT/'STOP.json').exists()
def boundary(admission=False):
    global _last
    now=time.monotonic()
    if admission or now-_last>=5:
        authority()
        if not before_cutoff():raise AdmissionStop('stage deadline or stop, success unknown')
        _last=now
def resource_admission():
    info={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        s=line.split()
        if s[0] in ['MemTotal:','MemAvailable:']:info[s[0][:-1]]=int(s[1])*1024
    required=(8*64+16)*1024**3
    if info['MemAvailable']<required:raise RuntimeError('insufficient RAM for eight resident pairs')
    st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
    if free<25*1024**3:raise RuntimeError('insufficient filesystem space')
    return dict(host_memory=info,planning_RAM_bytes=required,filesystem_free_bytes=free,cgroup='see evidence/CLAIM_RESOURCE_CHECK.json',extra_GPU_probes=0)
