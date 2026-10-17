"""Bounded CPU publication; ordinary exporter faults do not kill science."""
import subprocess
import time
from paths import ROOT
from qio import read,new_json,atomic_json,utc


class PublicationSafetyFailure(RuntimeError):
    pass


def publish(cell=None,*,terminal=False,root=ROOT,run=subprocess.run,clock=time.time,force=False):
    key='terminal' if terminal else cell
    folder=root/'publication_attempts'/key;folder.mkdir(parents=True,exist_ok=True)
    state_path=folder/'STATE.json'
    state=read(state_path) if state_path.exists() else dict(attempts=0,status='pending',next_utc_seconds=0)
    if state['status']=='published':return state
    if state['attempts']>=3 or (not force and clock()<state['next_utc_seconds']):return state
    n=state['attempts']+1;error_path=folder/f'error_{n:02d}.json'
    base=read(root/'config/BASE.json')
    command=[base['python'],'-B',str(root/'code/report.py'),'--error-json',str(error_path)]
    command+=['--terminal'] if terminal else ['--cell',cell]
    state.update(attempts=n,status='publication_running',utc=utc(),next_utc_seconds=clock()+60)
    atomic_json(state_path,state)
    try:
        result=run(command,cwd=root,check=False,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=300 if terminal else 180)
        code=result.returncode;stdout=result.stdout;stderr=result.stderr
    except subprocess.TimeoutExpired as error:
        code=1;stdout='';stderr='bounded CPU publication timeout: '+str(error)
    except OSError:
        # Inability to start/write/read is an actual storage/execution failure.
        raise
    record=dict(utc=utc(),command=command,exit_code=code,stdout=stdout[-8192:],stderr=stderr[-16384:],
        scientific_compute=0,cell=cell,terminal=terminal,attempt=n,
        error=read(error_path) if error_path.exists() else None)
    new_json(folder/f'attempt_{n:02d}.json',record)
    if code==0:
        marker=root/'PUBLICATION.json' if terminal else root/'cells'/cell/'PUBLICATION.json'
        if not marker.exists():raise PublicationSafetyFailure('publisher returned success without committed publication')
        state.update(status='published',publication=str(marker),utc=utc())
        atomic_json(state_path,state);return state
    state.update(status='publication_error',last_error=record,utc=utc())
    atomic_json(state_path,state)
    if code in (2,3):raise PublicationSafetyFailure('evidence/IO publication failure: '+str(record))
    # Pure table serialization/statistical bugs are recorded; finite retry later.
    return state
