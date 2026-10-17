"""Detached finite task owner, notification side channel and terminal export."""
import argparse,fcntl,os,signal,subprocess,time,traceback
from pathlib import Path
import paths
from paths import ROOT,CAMPAIGN,TASK,JOB,AUTH_SHA,CONFIG
from qio import read,new_json,atomic_json,utc,ref,process_identity,same_process
from admission import authority
WAKE=CAMPAIGN/'work/C/C_TASK_DISCOVERY_SERVICE_V1_r1/wakeup.py'
def notify_identity(row):return dict(hostname=row['host'],boot_id=row['boot_id'],pid=row['pid'],start_ticks=row['start_ticks'],session_id=os.getsid(row['pid']))
def serve():
    authority();own=notify_identity(process_identity());local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    with (local/'owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        new_json(ROOT/'CLAIM.json',dict(task_id=TASK,run_id=JOB,revision=1,process=own,authorization_sha256=AUTH_SHA,utc=utc(),prior_attempts=19457,stage_attempt_cap=4400,node_attempt_cap=25150,planned_new_units=4000,reused_H10_units=2000,previous_valid_units_protected=True,CPU_exit_check_before_GPU=True,original_task_claim=str(ROOT.parent/'C_D24_L11_RENDER_RECOVERY_V1/CLAIM.json')))
        new_json(ROOT/'PROCESS.json',own)
        manifest=dict(job_id=JOB,task_id=TASK,revision=1,run_id=JOB,attempt=1,claim_identity=ref(ROOT/'CLAIM.json'),process_identity=own,result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'supervisor.log'))
        new_json(ROOT/'WAKEUP_REGISTRATION.json',manifest)
        try:
            n=subprocess.run(['/usr/bin/python','-B',str(WAKE),'register','--manifest',str(ROOT/'WAKEUP_REGISTRATION.json')],capture_output=True,text=True,timeout=30)
            notification=dict(exit_code=n.returncode,stdout=n.stdout[-2000:],stderr=n.stderr[-2000:],utc=utc(),blocks_science=False)
        except BaseException as exc:notification=dict(error=repr(exc),utc=utc(),blocks_science=False)
        new_json(ROOT/'NOTIFICATION_REGISTRATION_RESULT.json',notification)
        wave=None;fatal=None;summary=None;start=time.monotonic()
        try:
            from predecessor import wait_for_exit
            wait_for_exit()
            from wave import run_wave
            wave=run_wave('evaluate')
            from report import main
            summary=main()
        except BaseException as exc:fatal=dict(error=repr(exc),traceback=traceback.format_exc())
        status='authorized_H_sweep_complete' if summary and summary['valid']==4000 and summary['cut_protocol_errors']==0 and not fatal and wave and wave['exit_code']==0 else 'partial_or_technical_gap'
        result=dict(task_id=TASK,run_id=JOB,status=status,utc=utc(),fatal=fatal,wave=wave,summary_path=str(ROOT/'FINAL_SUMMARY.json'),elapsed_seconds=time.monotonic()-start,valid_terminal_replays=0,new_training_updates=0,new_collection=0,all_owned_descendants_exited=bool(wave and wave.get('cleanup',{}).get('status')=='all_formal_group_members_exited'),occupancy_handoff_complete=bool(wave and wave.get('restoration',{}).get('status')=='occupancy_resolved'))
        new_json(ROOT/'RESULT.json',result);atomic_json(ROOT/'HEARTBEAT.json',dict(status='terminal',process=own,result=str(ROOT/'RESULT.json'),utc=utc()))
        new_json(CAMPAIGN/'receipts/C/C_D24_CROSSBASE_H_SWEEP_V1_RESULT_r1.json',dict(task_id=TASK,status=status,utc=utc(),result=ref(ROOT/'RESULT.json'),summary=ref(ROOT/'FINAL_SUMMARY.json') if summary else None,claim=ref(ROOT/'CLAIM.json'),new_training_updates=0,valid_terminal_replays=0))
        return 0 if status=='authorized_H_sweep_complete' else 3
def start():
    authority()
    if (ROOT/'CLAIM.json').exists():print('EXISTING_CLAIM_NO_DUPLICATE');return
    with (ROOT/'supervisor.log').open('ab') as log:
        p=subprocess.Popen(['/usr/bin/python','-B',str(Path(__file__).resolve()),'serve'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    print('SPAWNED_NOT_YET_READY',p.pid)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args();raise SystemExit(serve() if a.action=='serve' else start())
