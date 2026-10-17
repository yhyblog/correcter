"""Two tiny CPU jobs on this host; no formal paths, GPU or holder operations."""
import sys,os,json,time,subprocess,uuid
from pathlib import Path
from qio import PACKAGE,new_json,read,process_identity,ref
from service_primitives import acquire_singleton,detached

def worker(root):
    root=Path(root);lock=acquire_singleton(root/'singleton.lock')
    if lock is None:return 0
    if (root/'COMPLETED.json').exists():return 0
    new_json(root/'READY.json',dict(process=process_identity(),session=os.getsid(0)))
    time.sleep(1)
    for n in (1,2):
        new_json(root/('CPU_JOB_%d.json'%n),dict(synthetic=True,ordinal=n,value=sum(i*i for i in range(100)),process=process_identity()))
        time.sleep(.2)
    new_json(root/'COMPLETED.json',dict(status='PASS',synthetic_only=True,jobs=2,formal_compute=0))
    return 0

def check(destination):
    destination=Path(destination)
    root=Path('/tmp')/('corrector_local_control_'+uuid.uuid4().hex);root.mkdir()
    wrapper='import sys,os,json;sys.path.insert(0,sys.argv[1]);from service_primitives import detached;p=detached([sys.executable,"-B",sys.argv[1]+"/local_control_check.py","worker",sys.argv[2]],cwd=sys.argv[1],log=sys.argv[2]+"/daemon.log",env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1"));print(json.dumps({"parent_pid":os.getpid(),"child_pid":p.pid}))'
    command=[sys.executable,'-B','-c',wrapper,str(PACKAGE/'queue'),str(root)]
    parent=subprocess.run(command,text=True,capture_output=True,check=True);launch=json.loads(parent.stdout)
    deadline=time.monotonic()+12
    while not (root/'READY.json').exists():
        if time.monotonic()>deadline:raise RuntimeError('local detached CPU check did not start')
        time.sleep(.05)
    again=subprocess.run(command,text=True,capture_output=True,check=True)
    while not (root/'COMPLETED.json').exists():
        if time.monotonic()>deadline:raise RuntimeError('local detached CPU jobs did not complete')
        time.sleep(.05)
    identity=read(root/'READY.json')['process']
    result=dict(status='PASS',synthetic_only=True,launch_parent_exit=parent.returncode,
        detached_session=(read(root/'READY.json')['session']==identity['pid']),node_local_host=identity['host'],
        original_parent_exited=not Path('/proc',str(launch['parent_pid'])).exists(),
        idempotent_start=len(list(root.glob('CPU_JOB_*.json')))==2,actual_jobs=2,
        checks=dict(detached_two_jobs=True,idempotent_start=True),
        files=[ref(p) for p in sorted(root.glob('*.json'))],formal_compute=0,real_reservation_operations=0)
    if not all(result[k] for k in ('detached_session','original_parent_exited','idempotent_start')):raise RuntimeError('local detach/singleton proof failed')
    new_json(destination,result);return result

if __name__=='__main__':
    if sys.argv[1]=='worker':raise SystemExit(worker(sys.argv[2]))
    print(json.dumps(check(sys.argv[2])))
