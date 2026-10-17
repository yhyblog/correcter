"""Finite future admission metadata; no GPU query, benchmark or model import."""
import os
from pathlib import Path
from qio import utc


def memory_decision(observation, parents):
    if type(parents) is not int or not 1<=parents<=8:raise ValueError('finite parent count')
    per_parent=64*1024**3;other_reserve=16*1024**3
    known=[v for v in (observation['host_available_bytes'],observation['cgroup_available_bytes']) if v is not None]
    if not known:raise RuntimeError('no observable memory admission bound')
    available=min(known);required=parents*per_parent+other_reserve
    supported=max(0,min(8,(available-other_reserve)//per_parent))
    if available<required:
        raise RuntimeError('planning margin denied explicit8; not proof of a hardware maximum; no automatic fallback: '+str(dict(available=available,required=required,planning_supported=supported)))
    if observation['effective_CPU_count']<parents:raise RuntimeError('CPU affinity admission below one core per active parent')
    return dict(status='admitted_with_declared_unknowns',observed=observation,requested=parents,
                planning_per_parent_bytes=per_parent,other_workload_margin_bytes=other_reserve,
                planning_required_bytes=required,planning_margin_bytes=available-required,
                hardware_supported_max=None,planning_supported=supported,measured_per_parent_peak_bytes=None,
                true_container_peak_unknown=observation['cgroup_available_bytes'] is None,
                max_threads_per_numerical_library=1)


def observe():
    mem={x.split(':')[0]:int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.endswith('kB')}
    limits=[]
    for limit,usage in [('/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory.current'),
                         ('/sys/fs/cgroup/memory/memory.limit_in_bytes','/sys/fs/cgroup/memory/memory.usage_in_bytes')]:
        try:
            raw=Path(limit).read_text().strip();used=int(Path(usage).read_text())
            if raw!='max' and int(raw)<2**60:limits.append(max(0,int(raw)-used))
        except (OSError,ValueError):pass
    return dict(utc=utc(),host_available_bytes=mem.get('MemAvailable'),cgroup_available_bytes=min(limits) if limits else None,
                effective_CPU_count=len(os.sched_getaffinity(0)),GPU_queries=0,
                cgroup_note='visible controller roots only; hidden or unlimited controller is unknown')
