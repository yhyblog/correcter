"""C ordinary CPU queue. Notifications are a side channel, never a gate."""
import json, os, socket, sys, time
from pathlib import Path
WORK = Path(__file__).resolve().parent
C = WORK.parents[2]
OPS = C/'work/C/C_D24_AUTORECOVERY_QUEUE_RULE_V1_r1'
sys.path.insert(0, str(OPS))
from ops_io import read, new_json, atomic_json, utc, ref, sha, verify, process_identity, same_process
import c_recovery_policy as policy
TASK = 'C_D24_QUOTA_INDEPENDENT_QUEUE_V1'
ROOT = C/'results/C'/TASK
X, P = policy.X, policy.P
AUTH = C/'deadline_20260924/QUOTA_INDEPENDENT_AUTORUN_AUTHORIZATION_V1.json'
AUTH_SHA = '651a1b85faf16e3d13e0a722f1253fc465f5fcbeeab99b692f51f674de30af98'
DISC = C/'work/C/C_TASK_DISCOVERY_SERVICE_V1_r1'
CUTOFF = 1790164800.0
TABLES_DUE = 1790175600.0
LOCAL = Path('/tmp/corrector_C_quota_independent_r1')

def snapshot(p):
    return read(p) if Path(p).is_file() else {}

def authority():
    a=read(AUTH); q=read(C/'persistent_queue/CONTROL.json'); i=read(C/'nodes/C/identity.json')
    if sha(AUTH)!=AUTH_SHA or a['status']!='released': raise ValueError('quota grant changed')
    if socket.gethostname()!=a['nodes']['C']['host'] or i['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip(): raise ValueError('C host/boot mismatch; no automatic reboot recovery')
    if not any(r.get('task_id')==TASK and r['authorization']['sha256']==AUTH_SHA for r in q['nodes']['C'].get('control_plane_followups',[])): raise ValueError('quota followup absent')
    verify(a['rule'],base=C); policy.authority()
    return a

def live(row):
    return bool(row and same_process(dict(row,host=row.get('host',row.get('hostname')))))

def family(root):
    """Read actual host /proc; no GPU queries and no signals."""
    root=Path(root); owner=snapshot(root/'PROCESS.json'); records=[]
    if live(owner): return dict(exited=False,reason='original owner alive',owner=owner)
    for chain in (root/'chains').glob('*'):
        for name in ['MANAGER_STARTED.json','LIFECYCLE_STARTED.json']:
            row=snapshot(chain/name).get('process')
            if row: records.append(row)
    groups={r['pgid'] for r in records if 'pgid' in r}; found=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit(): continue
        actual=process_identity(int(entry.name))
        if not actual or actual['state']=='Z': continue
        try: cmd=(entry/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        except OSError: continue
        if actual['pgid'] in groups or str(root/'code')+'/' in cmd:
            found.append(dict(actual,cmdline=cmd))
    return dict(exited=not found,owner=owner,recorded_families=records,remaining=found,utc=utc(),host=socket.gethostname())

def runs(root):
    rows=[]
    for p in sorted((ROOT/'continuations').glob('*.json')):
        row=read(p)
        if row['science_root']==str(root): rows.append(Path(row['run_root']))
    return [Path(root)]+rows

def all_original_owners_exited():
    return all(family(r)['exited'] for r in [X,P])

def notify(manifest):
    """Finite best effort; no exception is allowed to block science."""
    import subprocess
    try:
        r=subprocess.run(['/usr/bin/python','-B',str(DISC/'wakeup.py'),'register','--manifest',str(manifest)],capture_output=True,text=True,timeout=30)
        row=dict(utc=utc(),exit_code=r.returncode,stdout=r.stdout[-2000:],stderr=r.stderr[-2000:],blocks_science=False)
    except Exception as exc: row=dict(utc=utc(),error=repr(exc),blocks_science=False)
    atomic_json(Path(manifest).with_name('NOTIFICATION_REGISTRATION_ATTEMPT.json'),row)
    return row

def counts():
    nx=snapshot(X/'ATTEMPT_COUNTER.json').get('reserved_attempts',0)
    np=snapshot(P/'ATTEMPT_COUNTER.json').get('count',0)
    return nx,np,11943+nx+np

def issue(root,error,signature,evidence=None):
    return policy.record_fault(root,error,signature=signature,evidence=evidence or [],continuable=['independent authorized C stages; no callback/ACK gate'])

def recover_missing_terminal(root):
    """A dead CPU parent is not a scientific failure; retain its old claim."""
    root=Path(root)
    if (root/'RESULT.json').exists() or not (root/'CLAIM.json').exists(): return
    proof=family(root)
    if not proof['exited']: return
    # A family ending after its parent may still have live descendants; proof above
    # includes both recorded process groups and all commands under this run's code.
    guard=snapshot('/tmp/gpu_occupancy_guard/status.json')
    restored=len(guard.get('gpus',{}))==8 and all(v.get('state')=='holder' for v in guard['gpus'].values())
    if not restored: return
    for ch in (root/'chains').glob('*'):
        if not (ch/'BEFORE_RESERVATION_RELEASE.json').exists():
            new_json(ch/'BEFORE_RESERVATION_RELEASE.json',dict(utc=utc(),log_derived=True,CPU_reconciled=True,cleanup={'status':'all_formal_group_members_exited'},evidence=proof,original_parent_terminal_missing=True))
    record=root/'QUOTA_RECOVERED_OWNER_EXIT.json'
    if not record.exists(): new_json(record,dict(utc=utc(),actual_family_exit=proof,cached_guard=guard,scientific_success_inferred=False,claim_preserved=ref(root/'CLAIM.json')))
    new_json(root/'RESULT.json',dict(task_id=root.name,status='engineering_parent_exit_without_terminal',stage='unknown',fatal={'error':'Original CPU owner exited without terminal; source outcomes retained separately'},all_owned_descendants_exited=True,occupancy_handoff_complete=True,CPU_reconciled=True,exit_evidence=ref(record),utc=utc(),report_exit_code=None,completed_source_replays=0))

