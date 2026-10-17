"""C-only full-Q authority, bounded stages and ordinary capacity admission."""
import os, socket, time
from pathlib import Path
from paths import ROOT,CAMPAIGN,AUTH_SHA,TASK,PREVIOUS
from paths import SCIENCE_ROOT
ROOT=SCIENCE_ROOT

from qio import read,sha,same_process
from process_family import group_members

class AdmissionStop(RuntimeError):pass
_last=0.

def authority():
    grant=CAMPAIGN/'deadline_20260924/FULL_Q_LOSS_SELECTION_AUTHORIZATION_V1.json'
    if sha(grant)!=AUTH_SHA:raise AdmissionStop('full Q authorization changed')
    a=read(grant);control=read(CAMPAIGN/'CONTROL.json');queue=read(CAMPAIGN/'persistent_queue/CONTROL.json');node=queue['nodes']['C']
    identity=read(CAMPAIGN/'nodes/C/identity.json')
    if a['status']!='released' or control.get('stop_requested') or queue.get('global_stop') or not node['enabled']:
        raise AdmissionStop('stop or disabled node')
    if socket.gethostname()!=node['owner_host'] or identity['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise AdmissionStop('C host/boot mismatch')
    follows=[x for x in node.get('authorized_followups',[]) if x['task_id']==TASK]
    if not follows or follows[0]['authorization']['sha256']!=AUTH_SHA:raise AdmissionStop('C task release absent')
    for key in ['protocol','concurrency_rule','admission_override']:
        if sha(CAMPAIGN/a[key]['path'])!=a[key]['sha256']:raise AdmissionStop('authorization input changed: '+key)
    cfg=read(ROOT/'config/CONFIG.json');limits=a['nodes']['C']
    if (cfg['stage_attempt_cap']!=limits['stage_attempt_cap'] or cfg['node_cumulative_attempt_cap']!=limits['cumulative_attempt_cap']
        or cfg['planned_prior_attempts']!=11943 or cfg['planned_prior_attempts']+cfg['stage_attempt_cap']>limits['cumulative_attempt_cap']
        or cfg['small_network_update_cap']!=64000 or cfg['workers']!=24):raise AdmissionStop('C budget or concurrency mismatch')
    for key in ['test_sources','source_index','frozen_D_G0_evidence']:
        if sha(cfg[key]['path'])!=cfg[key]['sha256']:raise AdmissionStop('frozen metadata changed: '+key)
    return a

def previous_exited():
    p=PREVIOUS/'concurrency24_r1';result=read(p/'RESULT.json');owner=read(p/'PROCESS.json')
    manager=read(p/'chain/MANAGER_STARTED.json')['process']
    if (not result['all_owned_descendants_exited'] or same_process(dict(owner,host=owner['hostname']))
        or same_process(manager) or group_members(manager['pgid'],manager['pid'])):raise AdmissionStop('old C formal family still active')
    if read(PREVIOUS/'FINAL_SUMMARY.json')['cumulative_C_attempts']!=11943:raise AdmissionStop('prior accounting changed')
    return result

def before_cutoff():
    end=read(ROOT/'config/CONFIG.json')['absolute_wall_deadline_unix']
    if (ROOT/'STAGE_DEADLINE.json').exists():end=min(end,read(ROOT/'STAGE_DEADLINE.json')['deadline_unix'])
    return time.time()<end and not (ROOT/'STOP.json').exists()

def boundary(admission=False):
    global _last
    now=time.monotonic()
    if admission or now-_last>=5:
        authority()
        if not before_cutoff():raise AdmissionStop('stage deadline or stop; missing success remains unknown')
        _last=now

def resource_admission(stage='evaluate'):
    info={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        fields=line.split()
        if fields[0] in ['MemTotal:','MemAvailable:']:info[fields[0][:-1]]=int(fields[1])*1024
    required=(640 if stage=='evaluate' else 32)*1024**3
    if info['MemAvailable']<required:raise AdmissionStop('insufficient ordinary host RAM for '+stage)
    st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
    if free<25*1024**3:raise AdmissionStop('insufficient filesystem space')
    return dict(host_memory=info,planning_RAM_bytes=required,filesystem_free_bytes=free,
        CPU_affinity_count=len(os.sched_getaffinity(0)),loadavg=os.getloadavg(),
        cgroup_limits='not visible in this container; not asserted unlimited',
        previous_24_worker_evidence=str(PREVIOUS/'concurrency24_r1/evidence/STABLE_HANDOFF_VERIFIED.json'),
        previous_per_GPU_used_MiB=42426,extra_GPU_probes=0)
