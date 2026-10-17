from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time,os
from experiments.native10_training_20260916 import storage
base=storage.PACKAGE;root=storage.ROOT;code=base/'experiments/native10_training_20260916'
out=root/'preparation/heldout_postprocess_cpu_20260917_v1';out.mkdir(exist_ok=False)
paths=[code/name for name in ['heldout_audit_v1.py','test_heldout_audit_v1.py','heldout_diagnostics_v1.py','test_heldout_diagnostics_v1.py']]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
before={str(p):sha(p) for p in paths};started=datetime.now(timezone.utc).isoformat();t=time.perf_counter()
command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',str(paths[1]),str(paths[3])]
result=subprocess.run(command,cwd=base,capture_output=True,text=True)
(out/'stdout.log').write_text(result.stdout);(out/'stderr.log').write_text(result.stderr)
after={str(p):sha(p) for p in paths}
payload=dict(status='passed' if result.returncode==0 and before==after else 'failed',started_utc=started,completed_utc=datetime.now(timezone.utc).isoformat(),command=command,returncode=result.returncode,wall_seconds=time.perf_counter()-t,code_before=before,code_after=after,active_protocol_freeze_sha256=sha(root/'heldout_protocols/heldout_v1/freeze.json'),checks_did_not_pause_or_change_wave=True,simulator_calls=0,model_calls=0,optimizer_updates=0,notes='Only new synthetic postprocessing tests; no heldout outcomes read and no old CPU suite repeated.')
storage.dump(out/'result.json',payload)
if payload['status']=='passed':storage.seal(out,role='native10_heldout_postprocessing_cpu',simulator_calls=0,optimizer_updates=0,model_calls=0)
print(json.dumps(payload,indent=2));print(result.stdout);print(result.stderr)
raise SystemExit(0 if payload['status']=='passed' else 1)
