from pathlib import Path
import json, hashlib, traceback
from experiments.native10_training_20260916 import heldout_prepare_v1 as prepare
root=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916')
control=root/'execution_control/heldout_v1'
ready=root.parent.parent/'coordination/NATIVE10_ANALYSIS_READY.json'
expected='b4241436b80706e2edc3ed9f5c16ef3dca02dab029732776c7411f73779f5d3d'
try:
 assert hashlib.sha256(ready.read_bytes()).hexdigest()==expected
 result=prepare.freeze(root/'heldout_preparations/heldout_pending_v2',ready,[root/'preparation/final_selection_heldout_cpu_20260917_v1',root/'preparation/heldout_statistics_cpu_20260917_v1'],version='heldout_v1')
 result.update(status='passed',ready_sha256=expected)
 with (control/'freeze_result.json').open('x') as stream:json.dump(result,stream,indent=2)
 print(json.dumps(result),flush=True)
except BaseException as error:
 with (control/'freeze_failure.json').open('x') as stream:json.dump(dict(error=repr(error),traceback=traceback.format_exc(),simulator_calls=0,optimizer_updates=0),stream,indent=2)
 raise
