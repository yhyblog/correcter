"""One metadata-only preparation run; cannot launch real policy work."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
from datetime import datetime,timezone

PACKAGE=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
ROOT=PACKAGE/'outputs/native10_training_20260916'
CODE=PACKAGE/'experiments/native10_training_20260916'
CONTROL=ROOT/'execution_control/round2_policy_preparation_v1'
CPU=ROOT/'preparation/round2_policy_cpu_20260917_v1'

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def dump(path,data):
 with Path(path).open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
def seal(folder,**meta):
 dump(folder/'complete.json',dict(status='complete',files={str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file()},**meta))

if __name__=='__main__':
 with (CONTROL/'started.json').open('x') as f:json.dump(dict(pid=os.getpid(),utc=datetime.now(timezone.utc).isoformat()),f)
 CPU.mkdir(parents=True,exist_ok=False)
 names=['policy5_round2_prepare_v1.py','policy5_round2_runner_v1.py','run_policy5_round2_gpu_v1.sh',
        'policy_deployment_round2_v1.py','policy5_round2_audit_v1.py','policy5_audit_v1.py',
        'policy5_round2_pending_v1.py','test_policy5_round2_entrypoints_v1.py',
        'test_policy_deployment_round2_v1.py','test_policy5_round2_pending_v1.py']
 dependencies={str(CODE/name):sha(CODE/name) for name in names}
 dependencies[str(CONTROL/'runner.py')]=sha(CONTROL/'runner.py')
 # Record inherited final-fit dependencies; no repair/write of an old artifact.
 old_freeze=ROOT/'final_fit_protocols/final_fit_v1/freeze.json'
 frozen=read(old_freeze)
 old_files={p:d for p,d in frozen['files'].items() if Path(p).suffix in ('.py','.sh')}
 old_files[str(old_freeze)]=sha(old_freeze)
 old_files[str(old_freeze.with_name('config.json'))]=sha(old_freeze.with_name('config.json'))
 old_files[str(CODE/'policy_deployment_v1.py')]=sha(CODE/'policy_deployment_v1.py')
 old_files[str(CODE/'policy5_prepare_v1.py')]=sha(CODE/'policy5_prepare_v1.py')
 old_files[str(CODE/'policy5_runner_v1.py')]=sha(CODE/'policy5_runner_v1.py')
 if any(sha(p)!=d for p,d in old_files.items()):raise RuntimeError('Old frozen implementation identity mismatch')
 ledger=ROOT/'budget/attempts.jsonl';ledger_before=sha(ledger)
 dump(CPU/'code_before.json',dependencies)
 dump(CPU/'old_dependencies_before.json',old_files)
 dump(CPU/'gpu_holder_before.json',read('/tmp/gpu_occupancy_guard/status.json'))
 env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONPATH=str(PACKAGE)+':'+str(PACKAGE/'src')+':'+str(PACKAGE.parent/'ACT-RECAP/src'))
 command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',str(CODE/'test_policy_deployment_round2_v1.py'),str(CODE/'test_policy5_round2_entrypoints_v1.py'),str(CODE/'test_policy5_round2_pending_v1.py')]
 begin=time.perf_counter()
 with (CPU/'pytest.log').open('x') as log:
  proc=subprocess.run(command,cwd=PACKAGE,env=env,stdout=log,stderr=subprocess.STDOUT)
 after={p:sha(p) for p in dependencies};old_after={p:sha(p) for p in old_files}
 result=dict(status='passed' if proc.returncode==0 and after==dependencies and old_after==old_files and sha(ledger)==ledger_before else 'failed',returncode=proc.returncode,command=command,wall_seconds=time.perf_counter()-begin,code_sha256_before=dependencies,code_sha256_after=after,old_frozen_files_unchanged=old_after==old_files,old_frozen_file_count=len(old_files),ledger_sha256_before=ledger_before,ledger_sha256_after=sha(ledger),model_calls=0,simulator_calls=0,optimizer_updates=0,scope='Synthetic CPU only; no actual model instantiation/inference/environment',runtime=dict(python=sys.version,executable=sys.executable))
 dump(CPU/'result.json',result);dump(CPU/'gpu_holder_after.json',read('/tmp/gpu_occupancy_guard/status.json'));seal(CPU,role='round2_policy_entrypoints_cpu')
 print(json.dumps(dict(cpu_status=result['status'],cpu_path=str(CPU),cpu_seal_sha256=sha(CPU/'complete.json'))),flush=True)
 if result['status']!='passed':raise SystemExit(1)
 # Metadata-only pending builder has no execute/freeze/model factory path.
 from experiments.native10_training_20260916.policy5_round2_pending_v1 import pending
 pending_result=pending(version='round2_policy_pending_v1')
 if sha(ledger)!=ledger_before:raise RuntimeError('Preparation changed formal resource ledger')
 dump(CONTROL/'result.json',dict(status='prepared_not_released',cpu_path=str(CPU),cpu_seal_sha256=sha(CPU/'complete.json'),pending=pending_result,ledger_sha256=ledger_before,model_calls=0,simulator_calls=0,optimizer_updates=0,old_freeze_unchanged=sha(old_freeze)==old_files[str(old_freeze)]))
 print(json.dumps(read(CONTROL/'result.json'),ensure_ascii=False),flush=True)
