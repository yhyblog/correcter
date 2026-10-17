"""Static diagnostics, only after a complete wave and sealed primary audit."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time,traceback
from datetime import datetime,timezone

PACKAGE=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
ROOT=PACKAGE/'outputs/native10_training_20260916'
CONTROL=ROOT/'execution_control/round2_policy_v1'
STAGE='round2_development_policy';BANK='round2_policy_v1';WAVE='round2_policy_v1_01'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def write(p,d):
 with Path(p).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')

def run():
 result=read(CONTROL/'result.json')
 if result['status']!='wave_and_primary_audit_complete' or (CONTROL/'failure.json').exists():
  raise RuntimeError('Wait for successful complete wave and primary audit')
 write(CONTROL/'postprocess_started.json',dict(pid=os.getpid(),utc=datetime.now(timezone.utc).isoformat()))
 from experiments.native10_training_20260916 import policy5_round2_independent_audit_v1 as independent
 from experiments.native10_training_20260916 import policy5_round2_cost_diagnostic_v1 as cost
 from experiments.native10_training_20260916 import policy5_round2_delivery_report_v1 as delivery
 modules={str(Path(m.__file__).resolve()):sha(m.__file__) for m in (independent,cost,delivery)}
 write(CONTROL/'postprocess_code.json',modules)
 ledger=ROOT/'budget/attempts.jsonl';before=sha(ledger)
 config=Path(result['frozen']['config']);freeze=Path(result['frozen']['freeze'])
 audit=Path(result['primary_audit']['path'])
 if sha(audit/'complete.json')!=result['primary_audit']['seal_sha256']:
  raise ValueError('Primary audit seal differs from execution receipt')
 begin=time.perf_counter();costs={}
 start=time.perf_counter()
 i=independent.audit(config,BANK,'round2_policy_v1_independent',audit/'result.json')
 costs['independent_seconds']=time.perf_counter()-start
 idir=Path(i['path'])
 start=time.perf_counter();c=cost.run(config,audit,freeze_path=freeze)
 cdir=ROOT/'policy5_cost_diagnostics/round2_policy_v1'
 cost.write_outputs(c,cdir);costs['cost_diagnostic_seconds']=time.perf_counter()-start
 start=time.perf_counter()
 wave=ROOT/'policy5_execution'/STAGE/BANK/WAVE
 report=ROOT/'policy_reports/round2_policy_v1'
 delivery.run(audit_path=audit,independent_path=idir,cost_path=cdir,wave_path=wave,output_path=report)
 costs['delivery_seconds']=time.perf_counter()-start
 if sha(ledger)!=before:raise RuntimeError('Read-only diagnostic changed formal ledger')
 for path,digest in modules.items():
  if sha(path)!=digest:raise RuntimeError('Diagnostic implementation changed during execution')
 out=dict(status='complete',utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-begin,
    independent=dict(path=str(idir),seal_sha256=sha(idir/'complete.json')),
    cost=dict(path=str(cdir),seal_sha256=sha(cdir/'complete.json')),
    report=dict(path=str(report),seal_sha256=sha(report/'complete.json')),costs=costs,
    ledger_sha256=before,model_calls=0,simulator_calls=0,optimizer_updates=0,code_sha256=modules)
 write(CONTROL/'postprocess_result.json',out)
 print(json.dumps(out,ensure_ascii=False),flush=True)

if __name__=='__main__':
 try:run()
 except BaseException as error:
  write(CONTROL/'postprocess_failure.json',dict(error=repr(error),traceback=traceback.format_exc(),
       utc=datetime.now(timezone.utc).isoformat(),model_calls=0,simulator_calls=0,optimizer_updates=0))
  raise
