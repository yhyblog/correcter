"""Bounded tests of new recovery invariants. Never imports a model or probes GPUs."""
import argparse, ast, importlib, json, shutil, subprocess, sys, tempfile, types
from unittest.mock import patch
from queue_common import *
from inventory import allowed_units

def main():
    checks=[]
    for label,original in [('X',X),('P',P)]:
        # Each template is loaded in its own fresh Python process; imported
        # scientific modules perform no computation in this entry check.
        cmd=['/usr/bin/python','-B',str(WORK/'targeted_cpu_check.py'),'--entry',label]
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        checks.append(json.loads(r.stdout))
    inv=dict(remaining=[dict(unit_id='tail',prior_attempts=0),dict(unit_id='unknown',prior_attempts=1),dict(unit_id='io',prior_attempts=1),dict(unit_id='already_retried',prior_attempts=2)],states={'io':{'error':'OSError [Errno 5]','traceback':'qio.py new_json'},'already_retried':{'error':'OSError [Errno 5]','traceback':'qio.py new_json'}})
    yes,no=allowed_units(inv,True,True)
    assert {r['unit_id'] for r in yes}=={'tail','io'} and {r['unit_id'] for r in no}=={'unknown','already_retried'}
    checks.append(dict(check='unentered tail retained, unknown excluded, failed retry capped',passed=True))
    with tempfile.TemporaryDirectory(prefix='C_quota_CPU_',dir='/tmp') as tmp:
        p=Path(tmp)/'notify.json';new_json(p,{'fixture':True})
        with patch('subprocess.run',side_effect=TimeoutError('fixture notifier unavailable')):
            row=notify(p)
        assert row['blocks_science'] is False and 'error' in row
    checks.append(dict(check='notification timeout returns evidence without blocking next stage',passed=True))
    result=dict(status='passed',utc=utc(),checks=checks,new_GPU_calls=0,new_scientific_attempts=0,actual_GPU_failure_recovery_tested=False)
    atomic_json(ROOT/'CPU_CHECK.json',result);print(json.dumps(result))

def entry(label):
    original=X if label=='X' else P
    with tempfile.TemporaryDirectory(prefix='C_quota_entry_',dir='/tmp') as temp:
        run=Path(temp)/'run';run.mkdir();shutil.copytree(WORK/('template_'+label),run/'code');shutil.copytree(original/'config',run/'config')
        # Test-only paths are explicit; production template uses sibling C root.
        path=run/'code/paths.py';path.write_text(path.read_text().replace('CAMPAIGN=ROOT.parents[2]',f'CAMPAIGN=Path({str(C)!r})'))
        for name in ['SELECTION_CONSUMED.json','SOURCE_INDEX.json','TRANSFER_CONSUMED.json','PREDECESSOR_EXIT.json']:
            if (original/name).exists():shutil.copyfile(original/name,run/name)
        shutil.copyfile(original/'CLAIM.json',run/'ORIGINAL_CLAIM.json')
        new_json(run/'CONTINUATION.json',dict(units=[],earlier_runs=[],config=ref(original/'config/CONFIG.json')))
        new_json(run/'STAGE_DEADLINE.json',dict(deadline_unix=CUTOFF))
        sys.path.insert(0,str(run/'code'))
        import admission,manager,continuation_adapter as adapter
        import qio
        qio.verify.__defaults__=(C,)
        admission.authority()
        if label=='P':
            j=read(read(P/'JOB_INDEX.json')['jobs'][0]['path']);admission.validate_job(j)
            from selection import engine_config
            assert engine_config(j)['fit_seed']==9101
            import resident_worker
        else:
            from selection import consumed_selection
            assert consumed_selection()['own_assets']==read(X/'SELECTION_CONSUMED.json')['own_assets']
            import native_client,gpu_job
        assert not {'torch','mujoco','numpy'} & set(sys.modules)
        # Real admission implementation exercised only against disposable local
        # roots. Counter/claim corruption, duplicate entry and legal failure replay
        # all fail before any model code can run.
        fake=Path(temp)/'science';fake.mkdir();out=Path(temp)/'attempt';out.mkdir()
        adapter.SCIENCE_ROOT=fake;adapter.ROOT=out;adapter.IS_X=True
        adapter.authority=lambda:True;adapter.admissions_allowed=lambda:True
        adapter.MANIFEST={'earlier_runs':[]};uid='Post/source';source={'source_id':'source'}
        adapter.UNITS={uid:dict(unit_id=uid,source=source,method='Post',prior_attempts=0,correction='filtered_partial_job_continuation')}
        new_json(out/'CONTINUATION.json',{'fixture':True})
        qc=importlib.import_module('queue_common');oldlocal=qc.LOCAL;qc.LOCAL=Path(temp)/'locks'
        try:
            with patch.object(qc,'counts',return_value=(0,0,11943)):
                first=adapter.admit(uid);assert read(first)['attempt']==0
                assert read(fake/'ATTEMPT_COUNTER.json')['reserved_attempts']==1
                try:adapter.admit(uid)
                except RuntimeError:pass
                else:raise AssertionError('duplicate entry allowed')
            uid2='Post/valid_false';adapter.UNITS[uid2]=dict(unit_id=uid2,source={'source_id':'valid_false'},method='Post',prior_attempts=0,correction='filtered_partial_job_continuation')
            new_json(fake/'evaluation'/uid2/'RESULT.json',dict(status='complete',success=False))
            try:adapter.admit(uid2)
            except RuntimeError:pass
            else:raise AssertionError('legal failure replay allowed')
            uid3='Post/no_budget';adapter.UNITS[uid3]=dict(unit_id=uid3,source={'source_id':'no_budget'},method='Post',prior_attempts=0,correction='filtered_partial_job_continuation')
            with patch.object(qc,'counts',return_value=(1100,0,13043)):
                try:adapter.admit(uid3)
                except RuntimeError:pass
                else:raise AssertionError('stage cap bypassed')
        finally:qc.LOCAL=oldlocal
    print(json.dumps(dict(check=label+' actual private entry imports, frozen source/selection validation, durable admission invariants',passed=True)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--entry',choices=['X','P']);a=p.parse_args();entry(a.entry) if a.entry else main()
