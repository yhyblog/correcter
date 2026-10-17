import hashlib,json,os,socket,time
from pathlib import Path
from paths import ROOT

def read(p):return json.loads(Path(p).read_text())
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    q=p.with_name(p.name+'.'+str(os.getpid())+'.tmp')
    q.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(q,p)
def seed(*args):return int.from_bytes(hashlib.sha256(('MECHANISM_20260924_V1|'+'|'.join(map(str,args))).encode()).digest()[:8],'big')%(2**63-1)
def uid(*args):return hashlib.sha256('|'.join(map(str,args)).encode()).hexdigest()[:24]
def identity():
    return dict(host=socket.gethostname(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),pid=os.getpid(),pgid=os.getpgid(0),thread=os.environ.get('CODEX_THREAD_ID'),time=time.time())
def check():
    cfg=read(ROOT/'CONFIG.json')
    if socket.gethostname()!=cfg['host']:raise RuntimeError('host mismatch')
    if time.time()>cfg['deadline_unix'] or (ROOT/'STOP').exists():raise RuntimeError('finite queue deadline/stop')
def terminal_path(job):return ROOT/'units'/job['id']/'RESULT.json'
def claim(job):
    check();p=ROOT/'claims'/(job['id']+'.json');p.parent.mkdir(exist_ok=True)
    with p.open('x') as f:json.dump(dict(job=job,owner=identity()),f)

