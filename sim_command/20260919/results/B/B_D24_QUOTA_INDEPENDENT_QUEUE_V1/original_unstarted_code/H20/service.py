"""Unstarted-stage wrapper; healthy process code is never changed in memory."""
import runpy
from pathlib import Path
import paths
from paths import ROOT
from qio import read
from recovery_policy import consume,issue
if __name__=='__main__':
 consume(ROOT,'service')
 try:runpy.run_path(str(ROOT/'code/service_impl.py'),run_name='__main__')
 except BaseException as exc:
  if not isinstance(exc,SystemExit) or exc.code not in (None,0):
   issue(ROOT,dict(type=type(exc).__name__,message=str(exc)),evidence=[str(ROOT/'daemon.stderr.log')],continuable=['next independent stage after verified own family exit'])
  raise
 finally:
  p=ROOT/'RESULT.json'
  if p.exists():
   r=read(p)
   if r.get('fatal') or r.get('publication_error') or r.get('status') in ['failed','partial','execution_unknown']:
    issue(ROOT,r.get('publication_error') or r.get('fatal') or dict(status=r.get('status'),detail='inspect missing/technical units; preserve all legal terminals'),evidence=[str(p)],continuable=['next authorized independent stage after own family exit'])
