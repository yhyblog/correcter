"""Replace only the verified C idle guard under its existing reservation lock."""
import fcntl,json,os,signal,socket,subprocess,sys,time
from pathlib import Path

W=Path(__file__).resolve().parent
C=W.parents[2]
STATE=Path('/tmp/gpu_occupancy_guard')
sys.path.insert(0,str(C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/code'))
from qio import read,new_json,atomic_json,utc,process_identity,same_process
from process_family import group_members

def main():
    cfg=read(W/'CONFIG.json');assert socket.gethostname()==cfg['hostname']
    with (STATE/'configure.lock').open('a') as configlock:
        fcntl.flock(configlock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (STATE/'formal.lock').open('a') as reservation:
            # No active formal group can be interrupted by this reconfiguration.
            fcntl.flock(reservation,fcntl.LOCK_EX|fcntl.LOCK_NB)
            status=read(STATE/'status.json');old=process_identity(status['pid'])
            assert old['pid']==31625 and old['start_ticks']==1060544194
            assert old['boot_id']=='215be39c-da79-4f3e-ae0e-c08d40fad8f1'
            assert same_process(old) and (Path('/proc')/str(old['pid'])/'cmdline').read_bytes().split(b'\0')[1].decode()==cfg['original_guard']
            holders=[process_identity(x['manager_pid']) for x in status['gpus'].values() if x.get('manager_pid')]
            assert len(holders)==8 and all(x for x in holders)
            new_json(W/'BEFORE.json',dict(utc=utc(),observer=process_identity(),guard=old,holders=holders,status=status,
                reservation_exclusive=True,formal_processes_signaled=0))
            started=time.monotonic();os.kill(old['pid'],signal.SIGTERM)
            while same_process(old) or any(same_process(x) or group_members(x['pid'],x['pid']) for x in holders):
                if time.monotonic()-started>180:raise RuntimeError('own old guard/holder graceful exit timeout; do not duplicate')
                time.sleep(.2)
            new_json(W/'OLD_EXIT.json',dict(utc=utc(),guard_exited=True,all_holder_groups_empty=True,seconds=time.monotonic()-started))
            with (W/'guard.log').open('ab') as log:
                proc=subprocess.Popen(['/usr/bin/python','-B',str(W/'guard.py'),'daemon'],cwd=W,
                    stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            identity=process_identity(proc.pid);new_json(W/'PROCESS.json',identity)
            end=time.monotonic()+20
            while time.monotonic()<end:
                if proc.poll() is not None:raise RuntimeError('C private guard exited during startup')
                current=read(STATE/'status.json')
                if current['pid']==proc.pid and all(x['state']=='reserved' for x in current['gpus'].values()):break
                time.sleep(.2)
            else:raise RuntimeError('new guard startup identity/status not confirmed')
            new_json(W/'NEW_GUARD_STARTED.json',dict(utc=utc(),process=identity,status=current,existing_formal_lock=True,
                holder_compute_during_reconfiguration=False))
        # Normal guard ownership resumes after releasing this short reservation.
        atomic_json(C/'nodes/C/IDLE_OCCUPANCY_POLICY.json',dict(cfg,utc=utc(),process=identity,status='active',
            recovery_entry=str(W/'guard.py'),startup_evidence=str(W/'NEW_GUARD_STARTED.json')))
        print(json.dumps(dict(status='C_guard90_started',pid=proc.pid,measured_SM_pending=True)))

if __name__=='__main__':main()
