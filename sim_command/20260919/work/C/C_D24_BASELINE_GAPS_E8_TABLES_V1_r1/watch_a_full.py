"""One bounded CPU file dependency event; never launches scientific work."""
import argparse
import datetime
import fcntl
import hashlib
from pathlib import Path
import subprocess
import time
import d24_common as d
import wakeup

OUT=d.R/'A_FULL_DEPENDENCY'
FINAL=d.C/'results/A/A_D24_LIBERO_FULL_NATIVE_V1/FINAL_SUMMARY.json'


def run():
    wakeup.check_identity()
    with (OUT/'watch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        claim=OUT/'CLAIM.json'
        d.exclusive(claim,dict(at_utc=d.utc(),process=d.identity(),dependency=str(FINAL),
                    scientific_launches=0,maximum_registrations=1,scope='append A native Full in a separate E8 table'))
        d.atomic(OUT/'PROCESS.json',d.identity())
        manifest=dict(job_id='C_E8_A_FULL_APPEND_V1',task_id='C_D24_BASELINE_GAPS_E8_TABLES_V1',revision=1,
                run_id='C_E8_A_FULL_APPEND_V1',attempt=1,claim_identity=dict(path=str(claim),sha256=hashlib.sha256(claim.read_bytes()).hexdigest()),
                process_identity=d.identity(),result_path=str(OUT/'RESULT.json'),error_summary_path=str(OUT/'watch.log'),
                purpose='CPU-only append of A native Full publication; do not repeat baseline, Post, Velocity or any GPU work')
        mp=OUT/'WAKEUP_REGISTRATION.json';d.atomic(mp,manifest);wakeup.register(mp)
        deadline=datetime.datetime(2026,9,23,15,tzinfo=datetime.timezone.utc).timestamp()
        while time.time()<deadline:
            wakeup.check_identity()
            data=d.load(FINAL) if FINAL.exists() else None
            # A writes provisional FINAL_SUMMARY snapshots during setup too.
            # Only actual Full claims/results or a concrete scientific gap count.
            full_complete=bool(data and data.get('Full_claimed') and all(
                data.get('phases',{}).get(method,{}).get('valid')==400 for method in ('Full-Post','Full-Velocity')))
            accepted=bool(data and (full_complete or data.get('scientific_gap')))
            if accepted:
                d.atomic(OUT/'RESULT.json',dict(status='dependency_published',at_utc=d.utc(),dependency=str(FINAL),
                    source_status=data.get('status'),Full_claimed=data.get('Full_claimed'),scientific_gap=data.get('scientific_gap'),
                    snapshot=data,scientific_launches=0,
                    action='Update only E8_FULL_NATIVE_TABLE and report from this A publication, preserving B operator table; no new GPU admission.'))
                return
            d.atomic(OUT/'HEARTBEAT.json',dict(at_utc=d.utc(),process=d.identity(),status='waiting_for_actual_A_Full_publication',
                       dependency=str(FINAL),observed_status=(data or {}).get('status'),observed_Full_claimed=(data or {}).get('Full_claimed'),
                       new_scientific_launches=0,deadline_utc='2026-09-23T15:00:00Z'))
            time.sleep(30)
        d.atomic(OUT/'RESULT.json',dict(status='dependency_unavailable_at_tables_deadline',at_utc=d.utc(),dependency=str(FINAL),
                   scientific_launches=0,action='Keep A Full cells explicitly pending/unavailable; current B/C tables remain usable.'))


def start():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'CLAIM.json').exists():
        return dict(status='existing_registration_no_duplicate',claim=str(OUT/'CLAIM.json'))
    with (OUT/'watch.log').open('a') as log:
        p=subprocess.Popen(['/usr/bin/python','-B',str(Path(__file__).resolve()),'run'],cwd=d.W,
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    return dict(status='started_one_CPU_dependency_watch',process=d.identity(p.pid),output=str(OUT))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['start','run'])
    print(globals()[parser.parse_args().command]())
