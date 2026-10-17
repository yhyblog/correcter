from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json,time
root=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector');old=root/'outputs/native10_training_20260916/heldout_protocols/heldout_v1/freeze.json';f=json.loads(old.read_text());out=root/'outputs/standalone_ablation_20260918/preparation/operational_repair_v1';out.mkdir(parents=True,exist_ok=False)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def check(item):
 path,expected=item;p=Path(path)
 try:
  stat=p.stat();actual=sha(p);return dict(path=path,expected_sha256=expected,actual_sha256=actual,bytes=stat.st_size,status='matched' if actual==expected else 'drift')
 except Exception as error:return dict(path=path,expected_sha256=expected,status='unreadable',error=repr(error))
start=datetime.now(timezone.utc).isoformat();items=list(f['files'].items());print(json.dumps(dict(event='full_inherited_scan_start',files=len(items),large_assets=len(f.get('large_files_verified_once_then_stat',{})))),flush=True)
with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(check,items))
large=[]
for name,spec in f.get('large_files_verified_once_then_stat',{}).items():
 p=Path(name)
 try:
  st=p.stat();actual=dict(bytes=st.st_size,mtime_ns=st.st_mtime_ns,inode=st.st_ino,device=st.st_dev);checks={k:actual[k]==v for k,v in spec.items() if k in actual};digest=sha(p);sha_fields={k:v for k,v in spec.items() if 'sha' in k};match=all(checks.values()) and all(digest==v for v in sha_fields.values());large.append(dict(path=name,expected=spec,actual=actual,actual_sha256=digest,status='matched' if match else 'drift',sha_checked=bool(sha_fields)))
 except Exception as error:large.append(dict(path=name,status='unreadable',error=repr(error),expected=spec))
report=dict(status='complete',started_utc=start,finished_utc=datetime.now(timezone.utc).isoformat(),old_freeze_path=str(old),old_freeze_sha256=sha(old),files=rows,large_assets=large,drift=[r for r in rows+large if r['status']!='matched'],model_calls=0,simulator_attempts=0,optimizer_updates=0)
p=out/'inherited_dependency_audit.json';p.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(path=str(p),sha256=sha(p),files=len(rows),large_assets=len(large),drift=report['drift'])),flush=True)
