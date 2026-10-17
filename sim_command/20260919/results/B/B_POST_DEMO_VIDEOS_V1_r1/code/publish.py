from paths import ROOT,CONFIG,CAMPAIGN
from qio import read,atomic_json,utc
from demo_publication import publish_incremental
s=publish_incremental(final=True)
chain=read(ROOT/'chain/CHAIN_RESULT.json') if (ROOT/'chain/CHAIN_RESULT.json').exists() else None
s.update(chain=chain,A_waits_for_B=False,formal_family_exit=chain.get('cleanup') if chain else None,holder_restoration=chain.get('restoration') if chain else None)
atomic_json(ROOT/'FINAL_SUMMARY.json',s)
atomic_json(CAMPAIGN/CONFIG['result_receipt'],s)
# Analysis consumes the shared B receipt/outbox; this is persistence, not a claim of transport delivery.
atomic_json(ROOT/'ANALYSIS_TERMINAL_NOTICE.json',dict(utc=utc(),task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],status=s['status'],receipt=str(CAMPAIGN/CONFIG['result_receipt']),delivery='B-owned shared receipt published for analysis; transport acceptance not asserted'))
print(s['status'],s['qualified_pairs'],s['recording_attempts'])
