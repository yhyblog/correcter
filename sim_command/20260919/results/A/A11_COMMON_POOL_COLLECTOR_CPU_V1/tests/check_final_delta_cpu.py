"""Only post-fixture changes and static entry boundaries; no runtime imports."""
import ast,copy,json,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
from full_state import typed,snapshot,compare,REQUIRED,MAX_FIELDS
from core.contracts import ContractError
from pool_protocol import paired_label
from storage import Store,StorageDenied
from budget import TOTAL,numeric_caps
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);checks=[]
def check(name,value):
    if not value:raise AssertionError(name)
    checks.append(dict(name=name,passed=True))
def refused(name,fn,error):
    try:fn()
    except error:check(name,True);return
    raise AssertionError(name)
for v,n in [(float('nan'),'nan'),(float('inf'),'inf'),(-float('inf'),'negative_inf')]:refused('state_'+n,lambda:typed(v),ContractError)
s=snapshot({k:0 for k in REQUIRED});check('finite_state_still_compares',compare(s,copy.deepcopy(s))['level']=='full_state_verified')
large={k:0 for k in REQUIRED};large['identity']={str(i):0 for i in range(MAX_FIELDS)}
refused('state_field_count_hard_bound',lambda:snapshot(large),ContractError)
check('absent_repeats_are_not_raw_aliases',paired_label([],['local_plus','local_minus'],'pair')['raw_alias_masked'] is False)
check('state_JSON_and_hash_caps',TOTAL['state_document_writes']==16 and TOTAL['state_field_digest_calls']==14*4096)
w=Store(out/'reserve',byte_limit=16,record_limit=8,reserve_bytes=8);w.write('normal',b'12345678')
refused('reserve_stops_noncleanup',lambda:w.write('denied',b'1'),StorageDenied)
w.emergency_mode=True;w.write('cleanup',b'1234');check('cleanup_can_use_reserved_bytes',w.used==12)
refused('JSON_limit_before_write',lambda:w.json('large',{'a':'x'*30}),StorageDenied)
# Call the actual nested-space attr walker extracted without its Torch imports.
tree=ast.parse((P/'code/runtime_state.py').read_text());fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='python_attrs')
class RngA:pass
class RngB:pass
class Random:Generator=RngA;RandomState=RngB
class NP:random=Random
Box=type('Box',(),{'__module__':'gymnasium.spaces.box'});box=Box();box.low=[-1.];box.high=[1.]
Outer=type('Dict',(),{'__module__':'gymnasium.spaces.dict'});outer=Outer();outer.spaces={'box':box};outer._np_random=None
ns=dict(np=NP,read_rng=lambda r,m:'synthetic_rng');exec(compile(ast.Module(body=[fn],type_ignores=[]),'actual_runtime_state_python_attrs','exec'),ns)
check('actual_recursive_space_walker',ns['python_attrs'](outer,None,{})['spaces']['box']['low']==[-1.])
# Assert the new runtime boundary fields are captured, not merely documented.
runtime=(P/'code/runtime_engine.py').read_text();state=(P/'code/runtime_state.py').read_text()
check('prefix_noise_checked',"reference['prefix_noise_SHAs']!=self.prefix_noise_shas" in runtime and 'prefix_noise_SHAs=engine.prefix_noise_shas' in state)
check('sampling_decisions_and_language_captured','sampling_decisions=' in state and 'language=engine.language' in state)
check('zero_native_restore_or_extra_obs',all(x not in state for x in ['mujoco.mj_setState(','._get_obs(','mujoco.mj_forward(']))
asts=[]
for p in sorted((P/'code').glob('*.py')):
    ast.parse(p.read_text());asts.append(p.name)
check('all_changed_top_level_AST',bool(asts))
child=(P/'code/child.py').read_text();check('actual_runtime_import_after_auth_and_EGL',child.index('load_authorization(a.release,True)')<child.index('egl.prepare()')<child.index('from runtime_engine import Engine'))
reserved=(P/'code/reserved.py').read_text();check('same_group_no_new_session_children','pass_fds=fds' in reserved and 'new_session=True' not in reserved and 'drain_group(os.getpgrp(),os.getpid())' in reserved)
check('no_lock_open_in_new_entries',all('flock(' not in (P/'code'/f).read_text() for f in ('launch.py','reserved.py','child.py','execution.py')))
check('partial_wave_coverage_and_masks','ATTEMPT_COVERAGE.json' in reserved and 'aggregate(parent,store)' in reserved)
check('public_schema_unchanged',__import__('hashlib').sha256((P.parents[2]/'results/A/A10/interface_v1/interface.schema.json').read_bytes()).hexdigest()=='7d52f22e9d2e622a18a9a71fdac822ed50413aa3838aa3ad40d98e0bee10500f')
check('no_forbidden_imports',not any(x.split('.')[0] in ('torch','mujoco','OpenGL','ctypes','numpy','pynvml','runtime_engine','runtime_state','execution') for x in sys.modules))
result=dict(status='PASS',synthetic=True,checks=checks,passed=len(checks),real_operations=0,large_weight_hashes=0)
(out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
