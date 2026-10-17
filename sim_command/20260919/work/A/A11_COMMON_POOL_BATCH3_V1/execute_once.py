"""Record and invoke the authorized frozen bash exactly once; no probes or retry."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import time
import traceback

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W = B / 'work/A/A11_COMMON_POOL_BATCH3_V1'
P = B / 'results/A/A11_COMMON_POOL_BATCH3_V1'
ack = json.loads((B / 'receipts/A/A11_COMMON_POOL_BATCH3_V1_ACK.json').read_text())
release = Path(ack['command'][2])
assert hashlib.sha256(release.read_bytes()).hexdigest() == ack['release_sha256']
current = json.loads(release.read_text())
assert all(not Path(path).exists() for path in current['paths'].values())
assert not (P / 'OUTER_EXIT.json').exists()
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
tick = time.monotonic()
record = dict(command=ack['command'], cwd=ack['cwd'], started_at_utc=started,
              command_opportunity_consumed=True, automatic_retry=False,
              release_sha256=ack['release_sha256'])
with (P / 'OUTER_COMMAND_ENTERED.json').open('x') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
rc = None
error = None
print(json.dumps(dict(status='invoking_frozen_command_once', started_at_utc=started)), flush=True)
try:
    with (P / 'OUTER.stdout').open('xb') as out, (P / 'OUTER.stderr').open('xb') as err:
        result = subprocess.run(ack['command'], cwd=ack['cwd'], stdout=out, stderr=err, check=False)
        rc = result.returncode
except BaseException as exc:
    error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
finally:
    final = dict(**record, ended_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 elapsed_seconds=time.monotonic()-tick, returncode=rc, invocation_error=error,
                 retry_executed=False, command_invocations=1)
    with (P / 'OUTER_EXIT.json').open('x') as stream:
        json.dump(final, stream, indent=2)
        stream.write('\n')
    print(json.dumps(final), flush=True)
raise SystemExit(rc if rc is not None else 70)
