import datetime
import os
import socket
import time
from paths import ROOT,CAMPAIGN,AUTH_SHA
from qio import read,sha,same_process

class AdmissionStop(RuntimeError):pass

def authority():
    grant=CAMPAIGN/'deadline_20260924/PER_BASE_AUXILIARY_TRAINING_AUTHORIZATION_V1.json'
    if sha(grant)!=AUTH_SHA:raise AdmissionStop('auxiliary authorization changed')
    a=read(grant);c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json')
    node=q['nodes']['B'];task='B_D24_SMOL_AUX_RETRAIN_V1'
    if a['status']!='released' or c.get('stop_requested') or q.get('global_stop') or not node['enabled']:
        raise AdmissionStop('current stop or disabled node')
    if socket.gethostname()!=c['roles']['B']['hostname'] or task not in c['allowed_task_ids']:
        raise AdmissionStop('wrong host or task')
    follows=[x for x in node.get('authorized_followups',[]) if x['task_id']==task]
    if not follows or follows[0]['authorization']['sha256']!=AUTH_SHA:raise AdmissionStop('followup release absent')
    prior=CAMPAIGN/'results/B/B_D24_POST_TRIGGER_MODES_V1/recovery_r3'
    terminal=read(prior/'RESULT.json');claimed=read(prior/'CLAIM.json')['process']
    if not terminal['all_owned_descendants_exited'] or same_process(dict(claimed,host=claimed['hostname'])):
        raise AdmissionStop('predecessor family still running')
    cfg=read(ROOT/'config/CONFIG.json')
    if cfg['planned_prior_attempts']!=read(prior/'FINAL_SUMMARY.json')['cumulative_B_attempts']:
        raise AdmissionStop('prior attempt history differs')
    if cfg['planned_prior_attempts']+cfg['stage_attempt_cap']>a['nodes']['B']['cumulative_attempt_cap']:
        raise AdmissionStop('node budget exhausted')
    return a

def before_cutoff():
    cfg=read(ROOT/'config/CONFIG.json')
    return time.time()<cfg['absolute_wall_deadline_unix'] and not (ROOT/'STOP.json').exists()

_last=0.
def boundary(admission=False):
    global _last
    now=time.monotonic()
    if admission or now-_last>=5:
        authority()
        if not before_cutoff():raise AdmissionStop('stage deadline or stop; do not label as task failure')
        _last=now

def resource_admission():
    info={}
    for line in open('/proc/meminfo'):
        s=line.split()
        if s[0] in ['MemTotal:','MemAvailable:']:info[s[0][:-1]]=int(s[1])*1024
    required=(8*64+16)*1024**3
    if info['MemAvailable']<required:raise RuntimeError('insufficient ordinary host RAM')
    st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
    if free<25*1024**3:raise RuntimeError('insufficient filesystem space')
    return dict(host_memory=info,planned_RAM_bytes=required,filesystem_free_bytes=free,extra_GPU_probes=0)
