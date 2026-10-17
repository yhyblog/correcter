"""Pure control-plane planning helper, not a daemon or capacity measurement.

The public queue must supply current B-local measurements and hold its short
storage-ledger transaction when reserving the returned allocations. Unknown
capacity is not infinity. Existing active-job reservations are already charged.
"""
from copy import deepcopy

A_FLOOR = 93952475136


def choose(jobs, capacity):
    cap=deepcopy(capacity); selected=[]; rejected=[]
    required=('host_available_bytes','cgroup_remaining_bytes','cpu_threads',
              'tmp_free_bytes','shared_free_bytes','shared_reserved_bytes',
              'A_reserved_bytes','active_jobs','gpu_free_bytes')
    if any(cap.get(k) is None for k in required):
        return [], [{'job_id':j['job_id'],'reason':'unknown resource capacity'} for j in jobs]
    cap['ram']=min(cap['host_available_bytes'],cap['cgroup_remaining_bytes'])
    # If A already owns part/all of its next batch reservation, preserve only
    # the remainder in addition to the total ledger, not the same bytes twice.
    extra_A=max(0,A_FLOOR-cap['A_reserved_bytes']) if cap.get('A_pending') else 0
    cap['shared']=cap['shared_free_bytes']-cap['shared_reserved_bytes']-extra_A
    cap['gpus']={str(k):v for k,v in cap['gpu_free_bytes'].items() if v is not None}
    for job in jobs:
        r=job['resources'];reason=None
        if not job.get('authorized') or not job.get('dependencies_ready'):reason='stage authorization or dependencies missing'
        elif cap['active_jobs']>=8:reason='node parallel limit 8'
        elif any(r[k]>cap[c] for k,c in [('ram_bytes','ram'),('cpu_threads','cpu_threads'),('tmp_bytes','tmp_free_bytes'),('shared_bytes','shared')]):reason='CPU/RAM/tmp/shared storage admission'
        eligible=sorted(k for k,v in cap['gpus'].items() if v>=r['vram_bytes_per_gpu'])
        if reason is None and len(eligible)<r['gpus']:reason='local free GPU/VRAM capacity'
        if reason:
            rejected.append({'job_id':job['job_id'],'reason':reason});continue
        devices=eligible[:r['gpus']]
        for k in devices:del cap['gpus'][k]
        for k,c in [('ram_bytes','ram'),('cpu_threads','cpu_threads'),('tmp_bytes','tmp_free_bytes'),('shared_bytes','shared')]:cap[c]-=r[k]
        cap['active_jobs']+=1
        selected.append({'job_id':job['job_id'],'gpu_ids':devices})
    return selected,rejected
