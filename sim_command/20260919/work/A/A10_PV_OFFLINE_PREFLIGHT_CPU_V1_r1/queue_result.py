"""Send only the authorized current-task receipt to the analysis session."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

root=Path(__file__).parent
message=(root/'QUEUE_MESSAGE.txt').read_text().strip()
result=subprocess.run(['codex','queue','--thread','01a0b91f-355f-7cd1-ae36-412500534ffb','--message',message],capture_output=True,text=True,timeout=45)
record=dict(thread='01a0b91f-355f-7cd1-ae36-412500534ffb',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
    sent_at_utc=datetime.now(timezone.utc).isoformat(),message_sha256=hashlib.sha256((root/'QUEUE_MESSAGE.txt').read_bytes()).hexdigest(),
    receipt_delivery_is_compute_authorization=False)
with (root/'QUEUE_DELIVERY.json').open('x') as f:f.write(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(record,indent=2,ensure_ascii=False))
raise SystemExit(result.returncode)
