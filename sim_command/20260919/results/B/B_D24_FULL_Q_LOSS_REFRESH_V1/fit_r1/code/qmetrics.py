"""Pure arithmetic over saved control-plane utilization samples."""
def accumulate(state,rows,unix_seconds):
    state=dict(state or {});previous=state.get('last_sample_unix');dt=None if previous is None else unix_seconds-previous
    gpus=state.setdefault('GPUs',{})
    for row in rows:
        key=row['uuid'];d=gpus.setdefault(key,dict(samples=0,valid_utilization_samples=0,zero_samples=0,
            utilization_percent_sum=0.,sampled_zero_interval_seconds_estimate=0.,unobserved_gap_seconds=0.,last_utilization=None))
        if dt is not None and dt>0:
            if dt<=30 and d['last_utilization'] is not None:
                if d['last_utilization']==0:d['sampled_zero_interval_seconds_estimate']+=dt
            else:d['unobserved_gap_seconds']+=dt
        try:
            value=float(row['utilization_gpu_percent'])
            if not 0<=value<=100:raise ValueError('range')
        except (ValueError,TypeError):value=None
        d['samples']+=1;d['last_utilization']=value
        if value is not None:
            d['valid_utilization_samples']+=1;d['utilization_percent_sum']+=value;d['zero_samples']+=value==0
            d['sample_mean_utilization_percent']=d['utilization_percent_sum']/d['valid_utilization_samples']
    state.update(last_sample_unix=unix_seconds,actual_GPU_kernel_idle_seconds=None,
        estimator='previous sample rectangular estimate only for gaps <=30s; not exact GPU busy/idle time',
        GPU_memory_is_not_utilization=True)
    return state
