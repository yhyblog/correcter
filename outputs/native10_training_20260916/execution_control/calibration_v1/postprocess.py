"""Read-only full calibration audit, diagnostics and proposal; no next stage."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, time, traceback

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
ROOT = BASE/'outputs/native10_training_20260916'
CONTROL = ROOT/'execution_control/calibration_v1'
OUTPUT = ROOT/'execution_control/calibration_postprocess_v1'

def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')

def run():
    # Outcome-bearing files must remain unopened until the entire wave exits.
    finished = read(CONTROL/'result.json')
    if finished['status'] != 'wave_complete_pending_full_audit' or finished['completed_primary_slots'] != 100:
        raise ValueError('The authorized calibration wave must finish before audit')
    evidence = ROOT/'preparation/calibration_postprocess_cpu_20260917_v1'
    cpu = read(evidence/'result.json')
    if cpu['status'] != 'passed' or cpu['returncode'] != 0:
        raise ValueError('Synthetic postprocessing CPU evidence must pass')
    for path, expected in cpu['code_after'].items():
        if sha(path) != expected:
            raise ValueError('New postprocessing code differs from tested version')
    frozen = finished['frozen']
    if sha(frozen['freeze']) != cpu['active_protocol_freeze_sha256']:
        raise ValueError('Collection freeze identity differs')
    OUTPUT.mkdir(exist_ok=False)
    started = time.monotonic()
    ledger = ROOT/'budget/attempts.jsonl'
    before = sha(ledger)
    write(OUTPUT/'started.json', dict(utc=utc(), pid=os.getpid(), controller_sha256=sha(__file__),
        cpu_seal_sha256=sha(evidence/'complete.json'), resources_before=finished['resources'],
        ledger_sha256=before, simulator_calls=0, optimizer_updates=0, model_calls=0))
    try:
        from experiments.native10_training_20260916.calibration_audit_v1 import run_audit
        wave = ROOT/'calibration_execution/calibration/calibration_policy_v1/calibration_v1_01'
        begin = time.monotonic()
        audit = run_audit(frozen['config'], frozen['freeze'], wave, version='calibration_v1')
        write(OUTPUT/'audit_receipt.json', dict(audit, wall_seconds=time.monotonic()-begin))
        from experiments.native10_training_20260916.calibration_diagnostics_v1 import run as diagnose
        begin = time.monotonic()
        diagnostic = diagnose(frozen['config'], audit['path'], wave,
            output_path=ROOT/'calibration_diagnostics/calibration_v1', freeze_path=frozen['freeze'])
        write(OUTPUT/'diagnostic_receipt.json', dict(diagnostic, wall_seconds=time.monotonic()-begin))
        after = sha(ledger)
        if after != before:
            raise ValueError('The read-only postprocessing ledger changed')
        write(OUTPUT/'result.json', dict(status='complete_audit_diagnostics_proposal_only',
            finished_utc=utc(), wall_seconds=time.monotonic()-started, audit=audit, diagnostics=diagnostic,
            ledger_sha256_before=before, ledger_sha256_after=after,
            simulator_calls=0, optimizer_updates=0, model_calls=0, heldout_reads=0,
            selection_seal_created=False, next_stage_automatically_started=False))
    except BaseException as error:
        write(OUTPUT/'failure.json', dict(status='failed_no_automatic_retry', utc=utc(),
            error=repr(error), traceback=traceback.format_exc(), wall_seconds=time.monotonic()-started,
            ledger_sha256_before=before, ledger_sha256_after=sha(ledger),
            simulator_calls=0, optimizer_updates=0, model_calls=0))
        raise

if __name__ == '__main__':
    run()
