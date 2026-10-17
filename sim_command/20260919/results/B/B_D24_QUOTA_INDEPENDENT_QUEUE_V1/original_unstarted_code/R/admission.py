import os
import socket
import time
from pathlib import Path
from paths import ROOT,CAMPAIGN,AUTH_SHA,CONFIG
from qio import read,sha,same_process

class AdmissionStop(RuntimeError):pass

def release_valid(control,queue,grant,task,expected_sha):
    node=queue['nodes']['B']
    if grant['status']!='released' or control.get('stop_requested') or queue.get('global_stop') or not node['enabled']:
        return False
    if task not in control['allowed_task_ids'] or grant['nodes']['B']['task_id']!=CONFIG['grant_task_id']:return False
    # A promotion from followup to current work does not revoke its released grant.
    return any(x.get('sha256')==expected_sha for x in queue.get('stage_authorizations',[]))

def authority():
    if not CONFIG.get('activation_finalized'):raise AdmissionStop('CPU queue not yet formally activated')
    grant=CAMPAIGN/CONFIG['grant']
    if sha(grant)!=AUTH_SHA:raise AdmissionStop('scientific authorization changed')
    a=read(grant);c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json')
    if not release_valid(c,q,a,CONFIG['task_id'],AUTH_SHA):raise AdmissionStop('stop, disabled node, or released task authorization absent')
    if socket.gethostname()!=c['roles']['B']['hostname']:raise AdmissionStop('wrong host')
    prior=Path(CONFIG['predecessor_root']);terminal=read(prior/'RESULT.json');claimed=read(prior/('CLAIM.json' if (prior/'CLAIM.json').exists() else 'QUEUE_CLAIM.json'))['process']
    if not terminal['all_owned_descendants_exited'] or same_process(dict(claimed,host=claimed.get('hostname',claimed.get('host')))):
        raise AdmissionStop('predecessor family still running')
    if CONFIG.get('predecessor_required_complete') and terminal['status']!='complete':raise AdmissionStop('once chain not complete')
    if CONFIG['planned_prior_attempts']+CONFIG['stage_attempt_cap']>a['nodes']['B']['cumulative_attempt_cap']:
        raise AdmissionStop('cumulative attempt budget unavailable')
    import gates
    gates.selection()
    return a

def before_cutoff():return time.time()<CONFIG['absolute_wall_deadline_unix'] and not (ROOT/'STOP.json').exists()

_last=0.
def boundary(admission=False):
    global _last
    now=time.monotonic()
    if admission or now-_last>=5:
        authority()
        if not before_cutoff():raise AdmissionStop('stage deadline or explicit stop')
        _last=now

def resource_admission():
    info={}
    for line in open('/proc/meminfo'):
        values=line.split()
        if values[0] in ['MemTotal:','MemAvailable:']:info[values[0][:-1]]=int(values[1])*1024
    required=(CONFIG.get('target_workers',8)*64+16)*1024**3
    if info['MemAvailable']<required:raise RuntimeError('insufficient ordinary host RAM')
    st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
    if free<25*1024**3:raise RuntimeError('insufficient filesystem space')
    return dict(host_memory=info,planned_RAM_bytes=required,filesystem_free_bytes=free,extra_GPU_probes=0)
