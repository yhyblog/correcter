"""Confirm audited predecessor family exit before the new formal reservation."""
from pathlib import Path
from paths import ROOT,CONFIG
from qio import read,new_json,utc,same_process,ref
from admission import authority
from process_family import group_members

def wait_for_exit():
    authority();s=read(ROOT/'INITIAL_IDENTITY_RESOURCE_AND_EXIT.json');m=s['previous_manager']
    if same_process(s['previous_process']) or same_process(m) or group_members(m['pgid'],m['pid']):raise RuntimeError('prior formal family still alive')
    p=Path(s['previous_terminal']['path']);r=read(p)
    if not r.get('all_owned_descendants_exited') or not r.get('occupancy_handoff_complete'):raise RuntimeError('unresolved prior cleanup')
    old=p.parent;counter=read(old/'ATTEMPT_COUNTER.json')
    prior=counter['prior_C_attempts']+counter['count']
    if prior!=CONFIG['planned_prior_attempts'] or prior!=19457:raise RuntimeError('cumulative prior counter changed')
    value=dict(utc=utc(),all_previous_formal_exited=True,previous_manager=m,previous_terminal=ref(p),prior_C_attempts=prior,previous_counter=ref(old/'ATTEMPT_COUNTER.json'),planned_new_units=4000,H10_replays=0,new_GPU_calls=0)
    new_json(ROOT/'DEPENDENCY_EXIT.json',value);return value
