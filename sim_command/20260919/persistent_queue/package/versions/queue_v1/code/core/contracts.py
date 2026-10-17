import hashlib,json,os,time
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[2]
CAMPAIGN=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
class ContractError(ValueError):pass
STORE=None
def configure_store(store):
    global STORE
    STORE=store
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write_new(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    if STORE is not None:return STORE.write(path,raw)
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def append_json(path,value):
    raw=(json.dumps(value,allow_nan=False)+'\n').encode()
    if STORE is not None:return STORE.append(path,raw)
    with Path(path).open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
class Meter:
    def __init__(self,path,caps,gate_fn=lambda:None):
        self.path=Path(path);self.path.touch(exist_ok=False);self.caps=dict(caps);self.used=dict.fromkeys(caps,0)
        self.gate=gate_fn;self.next=0
    def append(self,row):
        append_json(self.path,row)
    def enter(self,name,units=None,detail=None):
        self.gate();units=units or {}
        for k,v in units.items():
            if k not in self.caps or type(v) is not int or v<0 or self.used[k]+v>self.caps[k]:raise ContractError('Budget denied before entry: '+k)
        self.next+=1
        row=dict(event_id=self.next,phase='entered',name=name,units=units,detail=detail,monotonic=time.monotonic())
        self.append(row)
        for k,v in units.items():self.used[k]+=v
        return self.next
    def finish(self,i,error=None):self.append(dict(event_id=i,phase='raised' if error else 'returned',error=None if error is None else dict(type=type(error).__name__,message=str(error)),monotonic=time.monotonic()))
    def call(self,name,fn,units=None,detail=None):
        i=self.enter(name,units,detail)
        try:x=fn()
        except BaseException as e:self.finish(i,e);raise
        self.finish(i);return x

def reconcile(path,caps):
    if not Path(path).exists():return dict(status='not_entered',entered=dict.fromkeys(caps,0),returned=dict.fromkeys(caps,0),unresolved=[],counts_complete=True,corrupt_records=[])
    starts={};ends={};entered=dict.fromkeys(caps,0);returned=dict.fromkeys(caps,0);bad=[]
    for lineno,line in enumerate(Path(path).read_text().splitlines(),1):
        try:
            r=json.loads(line);i=r['event_id']
            if type(i) is not int or r['phase'] not in ['entered','returned','raised']:raise ValueError('Invalid event identity/phase')
            if r['phase']=='entered' and (i in starts or any(k not in caps or type(v) is not int or v<0 for k,v in r['units'].items())):raise ValueError('Duplicate or invalid entry')
            if r['phase']!='entered' and (i not in starts or i in ends):raise ValueError('Orphan/duplicate terminal record')
        except (ValueError,KeyError,TypeError,AttributeError) as error:
            bad.append(dict(line=lineno,error=str(error),raw=line));continue
        if r['phase']=='entered':
            starts[i]=r
            for k,v in r['units'].items():entered[k]+=v
        else:
            ends[i]=r
            if r['phase']=='returned':
                for k,v in starts[i]['units'].items():returned[k]+=v
    return dict(status='incomplete_or_corrupt_journal' if bad else 'reconciled',entered=entered,returned=returned,entered_events=len(starts),terminal_events=len(ends),
        failed=[i for i,r in ends.items() if r['phase']=='raised'],unresolved=sorted(set(starts)-set(ends)),
        counts_complete=not bad,corrupt_records=bad,
        charge_rule='entered units charged once; raised or missing terminal record never refunds entry; if corrupt records exist, counts are known lower bounds only and release remains consumed',units_are_incremental=True)
