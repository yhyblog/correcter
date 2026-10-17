"""C multi release, immutable final heads, finite budget and ordinary resources."""
import os, socket, time
from pathlib import Path
from paths import ROOT,RUNROOT,CAMPAIGN,AUTH_SHA,TASK,HEADS
from qio import read,sha,same_process
class AdmissionStop(RuntimeError):pass
_last=0.
def authority():
    grant=CAMPAIGN/'deadline_20260924/MULTI_PRIMARY_VALIDATION_AUTHORIZATION_V1.json'
    if sha(grant)!=AUTH_SHA:raise AdmissionStop('multi authorization changed')
    a=read(grant);control=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json');node=q['nodes']['C']
    identity=read(CAMPAIGN/'nodes/C/identity.json')
    if a['status']!='released' or control.get('stop_requested') or q.get('global_stop') or not node['enabled']:
        raise AdmissionStop('stop or disabled node')
    if socket.gethostname()!=node['owner_host'] or identity['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise AdmissionStop('C host/boot mismatch')
    follows=[x for x in node.get('authorized_followups',[]) if x['task_id']==TASK]
    if not follows or follows[0]['authorization']['sha256']!=AUTH_SHA:raise AdmissionStop('followup release absent')
    if sha(CAMPAIGN/a['protocol']['path'])!=a['protocol']['sha256']:raise AdmissionStop('protocol changed')
    terminal=read(HEADS/'RESULT.json');claimed=read(HEADS/'PROCESS.json');summary=read(HEADS/'FINAL_SUMMARY.json')
    if terminal['status']!='complete' or not terminal['all_owned_descendants_exited'] or same_process(dict(claimed,host=claimed['hostname'])):
        raise AdmissionStop('own predecessor not complete or exited')
    cfg=read(ROOT/'config/CONFIG.json');limits=a['nodes']['C']
    if (cfg['planned_prior_attempts']!=summary['cumulative_C_attempts'] or cfg['planned_prior_attempts']!=10443
        or cfg['stage_attempt_cap']!=limits['stage_attempt_cap'] or cfg['node_cumulative_attempt_cap']!=limits['cumulative_attempt_cap']
        or cfg['planned_prior_attempts']+cfg['stage_attempt_cap']>limits['cumulative_attempt_cap'] or cfg['small_network_update_cap']!=0):
        raise AdmissionStop('C cumulative budget mismatch')
    for k in ['test_sources','source_index','method_frozen','frozen_heads']:
        row=cfg[k]
        if sha(row['path'])!=row['sha256']:raise AdmissionStop('sealed input changed: '+k)
    heads=read(ROOT/'FROZEN_HEADS.json')
    for k in ['fit_summary','normalization','Q_ranking']:
        row=heads[k]
        if sha(row['path'])!=row['sha256']:raise AdmissionStop('fixed head metadata changed: '+k)
    return a

def before_cutoff():
    return time.time()<read(ROOT/'config/CONFIG.json')['absolute_wall_deadline_unix'] and not (ROOT/'STOP.json').exists() and not (RUNROOT/'STOP.json').exists()

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
        parts=line.split()
        if parts[0] in ['MemTotal:','MemAvailable:']:info[parts[0][:-1]]=int(parts[1])*1024
    required=640*1024**3
    if info['MemAvailable']<required:raise AdmissionStop('insufficient RAM for24 resident pairs')
    st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
    if free<25*1024**3:raise AdmissionStop('insufficient filesystem space')
    return dict(host_memory=info,planning_RAM_bytes=required,filesystem_free_bytes=free,
                cgroup='evidence/CLAIM_RESOURCE_CHECK.json',extra_GPU_probes=0)
