from pathlib import Path
from datetime import datetime,timezone
import subprocess,os,json,sys,platform,shutil,re
import numpy,torch
from experiments.standalone_ablation_20260918 import storage
version=sys.argv[1]
if not re.fullmatch(r'cpu_v[0-9]+',version):raise ValueError('explicit CPU evidence version required')
code=storage.PACKAGE/'experiments/standalone_ablation_20260918';out=storage.ROOT/'preparation'/version;out.mkdir(parents=True,exist_ok=False)
files=sorted(p for p in code.rglob('*') if p.suffix in ('.py','.sh'))
before={str(p):storage.sha256(p) for p in files}
for p in files:
 target=out/'tested_code'/p.relative_to(code);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
shutil.copyfile(__file__,out/'cpu_evidence_runner.py')
selected_tests=[code/name for name in ('test_operations.py','test_protocol_storage_prepare.py','test_runner.py','test_audit.py')]
command=[sys.executable,'-m','pytest',*[str(p) for p in selected_tests],'-q','-p','no:cacheprovider','--junitxml='+str(out/'pytest.xml')]
started=datetime.now(timezone.utc).isoformat()
with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
 p=subprocess.run(command,stdout=stdout,stderr=stderr,env=os.environ.copy())
shell=subprocess.run(['bash','-n',str(code/'run_gpu.sh')],capture_output=True,text=True)
after={str(p):storage.sha256(p) for p in files}
result=dict(status='passed' if p.returncode==0 and shell.returncode==0 and before==after else 'failed',returncode=p.returncode,command=command,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),code_before=before,code_after=after,simulator_calls=0,model_calls=0,optimizer_updates=0,scope='bounded operational repair only: inherited operations provenance, actual old eight-slot scheduler with mocked child processes, empty slot guards, freeze authorization and audit metadata; no actual model/environment instantiated',reused_unchanged_scientific_cpu=dict(path=str(storage.ROOT/'preparation/cpu_v5'),seal_sha256=storage.sha256(storage.ROOT/'preparation/cpu_v5/complete.json')),runtime=dict(python=sys.version,executable=sys.executable,numpy=numpy.__version__,torch=torch.__version__,platform=platform.platform(),threads={k:os.environ[k] for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')}),shell_syntax=dict(returncode=shell.returncode,stdout=shell.stdout,stderr=shell.stderr))
storage.dump(out/'result.json',result);storage.seal(out,role='standalone_cpu_evidence')
print(json.dumps(dict(path=str(out),status=result['status'],seal_sha256=storage.sha256(out/'complete.json'))))
print((out/'stdout.log').read_text()[-15000:]);print((out/'stderr.log').read_text()[-1000:])
