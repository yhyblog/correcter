from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,time
import numpy as np
from experiments.native10_training_20260916 import heldout_collection_v1 as guard
root=guard.ROOT
out=root/'preparation/heldout_matching_dependency_probe_v1'
out.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
files=[Path(guard.__file__),Path(guard.__file__).with_name('test_heldout_collection_v1.py')]
code_before={str(p):sha(p) for p in files}
ledger=root/'budget/attempts.jsonl';ledger_before=sha(ledger)
bank=sorted((root/'banks/calibration_policy_v1').glob('*/cut*/plans.npz'))[0].parent
inputfiles=[bank/name for name in ('plans.npz','formal_directions.npz','directions.npz','generation.json','complete.json')]
config=root/'calibration_protocols/calibration_v1/config.json';inputfiles.append(config)
inputs={str(p):sha(p) for p in inputfiles}
sealed=json.loads((bank/'complete.json').read_text())
for p in inputfiles[:-2]:
 if sealed['files'][p.name]!=sha(p):raise ValueError('Input differs from calibration bank seal')
def arrays(p):
 with np.load(p,allow_pickle=False) as data:return {k:data[k].copy() for k in data.files}
start=time.perf_counter()
result=guard.audit_heldout_commands(arrays(bank/'plans.npz'),arrays(bank/'formal_directions.npz'),arrays(bank/'directions.npz'),
 json.loads((bank/'generation.json').read_text()),json.loads(config.read_text())['matching'])
code_after={str(p):sha(p) for p in files};ledger_after=sha(ledger)
assert code_before==code_after and ledger_before==ledger_after
assert inputs=={str(p):sha(p) for p in inputfiles}
dump('result.json',dict(status='passed',created_utc=datetime.now(timezone.utc).isoformat(),source_selection='Lexicographically first sealed calibration bank, independent of outcomes',
 bank=str(bank),inputs=inputs,code_sha256_before=code_before,code_sha256_after=code_after,ledger_sha256_before=ledger_before,ledger_sha256_after=ledger_after,
 audit=result,wall_seconds=time.perf_counter()-start,model_calls=0,simulator_calls=0,optimizer_updates=0,labels_read=False,
 operation='Pure NumPy validation of saved plans/directions/gradient metadata; no source, branch, outcome, model, scene, or environment access'))
dump('command.json',dict(argv=['/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python','/tmp/check_heldout_matching_dependency.py'],script_sha256=sha(__file__)))
(out/'execution_script.py').write_bytes(Path(__file__).read_bytes())
dump('complete.json',dict(status='complete',role='heldout_matching_dependency_pure_saved_bank_check',files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}))
print(json.dumps(dict(status='passed',path=str(out),seal_sha256=sha(out/'complete.json'),bank=str(bank),dependency_rms_spread=result['dependency_rms_spread'],ledger_unchanged=True),indent=2))
