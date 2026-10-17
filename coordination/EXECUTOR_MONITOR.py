"""Read-only batch progress: never reads per-branch outcomes."""
from pathlib import Path
import json
from collections import Counter
from datetime import datetime, timezone
root=Path(__file__).resolve().parents[1]
out=root/'outputs/metaworld_small_20260916'
ledger=out/'budget/attempts.jsonl'
rows=[json.loads(line) for line in ledger.read_text().splitlines() if line] if ledger.exists() else []
counts={}
for stage in ('preflight','development'):
    folder=out/'rollouts'/stage
    counts[stage]={'complete_sources':len(list(folder.glob('*/complete.json'))),'complete_branches':len(list(folder.glob('*/cut*/*/replicate_*/complete.json')))}
errors=[]
for path in sorted((out/'logs').glob('*/workers/*.log')):
    text=path.read_text(errors='replace')[-6000:]
    if 'Traceback (most recent call last)' in text or 'AssertionError' in text:
        errors.append({'path':str(path),'tail':text[-2000:]})
ready=root/'coordination/ANALYSIS_READY.json'
print(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'analysis_ready_exists':ready.exists(),'attempts':len(rows),'by_kind':dict(Counter(row['kind'] for row in rows)),'remaining_to_hard700':700-len(rows),'completed':counts,'concurrency_checks_passed':len(list((out/'checks').glob('*/worker_*/passed.json'))),'worker_errors':errors},ensure_ascii=False,indent=2))
