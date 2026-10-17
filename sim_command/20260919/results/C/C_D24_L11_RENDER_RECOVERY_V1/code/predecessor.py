"""Reconfirm local predecessor identities and family exit before GPU entry."""
from pathlib import Path
from paths import ROOT,CONFIG
from qio import read,new_json,utc,same_process,ref
from admission import authority
from process_family import group_members
def wait_for_exit():
    authority();snapshot=read(ROOT/'INITIAL_RESOURCE_AND_EXIT.json');proof=[]
    for f in snapshot['prior_families']:
        m=f['manager'];alive=same_process(f['supervisor']) or same_process(m) or bool(group_members(m['pgid'],m['pid']))
        if alive:raise RuntimeError('prior local formal family still alive: '+f['root'])
        terminal=read(Path(f['root'])/'RESULT.json')
        if not terminal.get('all_owned_descendants_exited') or not terminal.get('occupancy_handoff_complete'):raise RuntimeError('unresolved prior cleanup')
        proof.append(dict(root=f['root'],manager=m,all_exited=True,terminal=ref(Path(f['root'])/'RESULT.json')))
    attempts=sum(len(list((Path(f['root'])/'claims/units').glob('*.json'))) for f in snapshot['prior_families'])
    if attempts!=2750:raise RuntimeError('historical claim count changed')
    value=dict(utc=utc(),all_previous_formal_exited=True,prior_task_attempts=attempts,prior_C_attempts=14943+attempts,remaining_units=1764,protected_valid=736,prior_families=proof,new_GPU_calls=0)
    if value['prior_C_attempts']!=CONFIG['planned_prior_attempts']:raise RuntimeError('historical counter disagreement')
    new_json(ROOT/'DEPENDENCY_EXIT.json',value);return value
