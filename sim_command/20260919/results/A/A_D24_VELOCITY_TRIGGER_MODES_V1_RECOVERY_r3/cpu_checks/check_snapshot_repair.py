"""Narrow CPU checks for the actual immutable writer and evidence reader."""
import ast
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
import qio
import publication_data as evidence
import admission
from paths import HISTORY_ROOTS

FIX=ROOT/'cpu_checks'/'fixtures'
FIX.mkdir(exist_ok=False)
checks=[]
def passed(name,**fields):
    checks.append(dict(name=name,passed=True,**fields))

def paths(root,number=0,attempt=0):
    source=dict(source_id=f'synthetic_{number}',task='synthetic-v3',ordinal=number,env_seed=100+number,policy_seed=200+number)
    uid=f"Random-once_H30_{source['source_id']}"
    claim=dict(unit_id=uid,mode='Random-once',H=30,attempt=attempt,source=source)
    result=dict(source,mode='Random-once',H=30,attempt_index=attempt,status='complete',success=False)
    return root/'unit_claims'/(uid+'.json'),root/'runs/job/episodes'/source['source_id']/'RESULT.json',claim,result

def commit(root,number=0,attempt=0):
    cp,rp,c,r=paths(root,number,attempt)
    qio.new_json(cp,c);qio.new_json(rp,r)
    return cp,rp

def expect_conflict(name,root,contains):
    try:evidence.load_evidence(roots=root if isinstance(root,tuple) else (root,))
    except evidence.EvidenceConflict as e:
        assert contains in str(e),(contains,str(e))
        passed(name,error=str(e))
    else:raise AssertionError('conflict accepted: '+name)

# Inspect the final-name boundary in the real writer, including exclusive refusal.
target=FIX/'atomic.json';link=qio.os.link
seen=[]
def checked_link(temp,dest):
    if Path(dest)==target:
        assert json.loads(Path(temp).read_text())=={'synthetic':True,'payload':'x'*10000}
        assert not target.exists()
        seen.append('complete_temp_before_visibility')
    return link(temp,dest)
with patch.object(qio.os,'link',checked_link):
    qio.new_json(target,dict(synthetic=True,payload='x'*10000))
before=target.read_bytes()
try:qio.new_json(target,dict(overwrite=True))
except FileExistsError:pass
else:raise AssertionError('exclusive write overwrote old final')
assert target.read_bytes()==before and len(seen)==1
assert not list(FIX.glob('.*.tmp'))
passed('atomic_complete_visibility_and_exclusive_final')

# Reproduce the old failing sequence using its actual reader: a commit occurs
# after the old claim directory snapshot and before the result directory read.
old_spec=importlib.util.spec_from_file_location('old_publication_data',HISTORY_ROOTS[-1]/'code/publication_data.py')
old=importlib.util.module_from_spec(old_spec);old_spec.loader.exec_module(old)
old.OLD_ROOT=FIX/'old_race';old.ROOT=FIX/'old_empty'
glob=Path.glob;injected=[]
def stale_claim_listing(path,pattern):
    if path==old.OLD_ROOT/'unit_claims' and pattern=='*.json' and not injected:
        captured=list(glob(path,pattern))
        def it():
            yield from captured
            commit(old.OLD_ROOT);injected.append(True)
        return it()
    return glob(path,pattern)
with patch.object(Path,'glob',stale_claim_listing):
    try:old.load_evidence()
    except old.EvidenceConflict as e:assert 'without same source attempt claim' in str(e)
    else:raise AssertionError('old race was not reproduced')
assert len(evidence.load_evidence(roots=(old.OLD_ROOT,))[1])==1
passed('old_reader_real_interleaving_reproduced_and_fixed')

# Even a stale/empty claims listing cannot invalidate an exact committed result.
def hidden_listing(path,pattern):
    if path==old.OLD_ROOT/'unit_claims' and pattern=='*.json':return iter(())
    return glob(path,pattern)
with patch.object(Path,'glob',hidden_listing):
    _,attempts,claims,selected=evidence.load_evidence(roots=(old.OLD_ROOT,))
assert len(attempts)==len(claims)==len(selected)==1
passed('exact_claim_join_independent_of_listing')

# A commit after the result snapshot is in-flight in that partial snapshot;
# the next snapshot contains it, with no orphan diagnosis.
late=FIX/'late_result';late_once=[]
def late_commit(path,pattern):
    if path==late/'runs' and pattern=='*/episodes/*/RESULT.json' and not late_once:
        captured=list(glob(path,pattern))
        def it():
            yield from captured
            commit(late);late_once.append(True)
        return it()
    return glob(path,pattern)
with patch.object(Path,'glob',late_commit):
    _,attempts,claims,_=evidence.load_evidence(roots=(late,))
assert not attempts and len(claims)==1
assert len(evidence.load_evidence(roots=(late,))[1])==1
passed('later_result_is_next_snapshot_not_corruption')

orphan=FIX/'orphan';cp,rp,c,r=paths(orphan);qio.new_json(rp,r)
expect_conflict('true_orphan_rejected',orphan,'missing immutable claim')
wrong=FIX/'wrong';cp,rp,c,r=paths(wrong);r['env_seed']+=1
qio.new_json(cp,c);qio.new_json(rp,r)
expect_conflict('seed_mismatch_rejected',wrong,'env_seed conflict')
wrong_attempt=FIX/'wrong_attempt';cp,rp,c,r=paths(wrong_attempt);r['attempt_index']=1
qio.new_json(cp,c);qio.new_json(rp,r)
expect_conflict('attempt_mismatch_rejected',wrong_attempt,'attempt conflict')
dup1=FIX/'dup1';dup2=FIX/'dup2';commit(dup1);commit(dup2)
expect_conflict('duplicate_physical_claim_rejected',(dup1,dup2),'duplicate or changed')
replayed=FIX/'replayed';commit(replayed,attempt=1)
expect_conflict('completed_terminal_replay_rejected',(dup1,replayed),'completed unit replay')

# Real eight concurrent CPU writers; reads overlap both claim/result commit.
parallel=FIX/'parallel';errors=[]
def writer(slot):
    try:
        for k in range(12):
            cp,rp,c,r=paths(parallel,slot*12+k)
            qio.new_json(cp,c);time.sleep(.001);qio.new_json(rp,r)
    except BaseException as e:errors.append(repr(e))
threads=[threading.Thread(target=writer,args=(slot,)) for slot in range(8)]
for t in threads:t.start()
snapshots=0
while any(t.is_alive() for t in threads):
    _,attempts,claims,selected=evidence.load_evidence(roots=(parallel,));snapshots+=1
    assert len(attempts)==len(selected)<=len(claims)
for t in threads:t.join()
assert not errors,errors
assert len(evidence.load_evidence(roots=(parallel,))[1])==96
passed('eight_concurrent_actual_CPU_writers_and_reader',physical_fixture_records=96,snapshots=snapshots)

# Real historical evidence and real admission validators, without any admission.
jobs,attempts,claims,selected=evidence.load_evidence()
assert len(claims)==len(attempts)==1232
assert sum(x['status']=='complete' for x in selected)==1216
assert sum(x['status']!='complete' for x in selected)==8
plan,eligible=admission.recovery_plan()
checked=0
for p in (ROOT/'jobs').glob('*.json'):
    admission.validate_job(qio.read(p));checked+=1
completed_job=qio.read(next((HISTORY_ROOTS[0]/'jobs').glob('Velocity_Random-once_H10_*.json')))
try:admission.validate_job(completed_job)
except ValueError:pass
else:raise AssertionError('old completed job accepted')
assert checked==383 and len(eligible)==3784
assert plan['old_attempts']+len(eligible)==5016 and 9360+5016==14376
passed('real_1232_attempts_1216_valid_and_3784_exact_remainder',eligible_jobs=checked,no_claim_created=not(ROOT/'CLAIM.json').exists())

# Config and the actual scientific controller/engine remain byte-identical.
for name in ('controller.py','numeric_engine.py','resident_egl.py','reservation.py','process_family.py','wave_timing.py'):
    assert (ROOT/'code'/name).read_bytes()==(HISTORY_ROOTS[-1]/'code'/name).read_bytes()
for p in (ROOT/'config').iterdir():assert p.read_bytes()==(HISTORY_ROOTS[-1]/'config'/p.name).read_bytes()
assert (ROOT/'RUN_TIME_BUDGET.json').read_bytes()==(HISTORY_ROOTS[0]/'RUN_TIME_BUDGET.json').read_bytes()
for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text())
passed('science_config_deadline_and_lifecycle_unchanged_AST_valid')
assert 'torch' not in sys.modules
qio.new_json(ROOT/'CPU_SNAPSHOT_REPAIR_CHECKS.json',dict(utc=qio.utc(),checks=checks,passed=len(checks),scientific_compute=0,hardware_queries=0,formal_claims=0))
print(json.dumps(dict(passed=len(checks),checks=[x['name'] for x in checks],scientific_compute=0)))
