"""Only V3 identity/static wiring and final whitelist JSON boundary."""
import ast,copy,json,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
import inheritance
from core.contracts import read,sha,ContractError
from authorization import check_documents
from shared_plans import load_bank,prepare_bank_reference,MAX_BANK_BYTES
from storage import Store
from pool_protocol import ARMS
OUT=Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=False)
checks=[]
def check(n,v):checks.append(dict(name=n,passed=bool(v)));assert v,n
def reject(n,fn):
    try:fn()
    except ContractError:check(n,True);return
    raise AssertionError(n+' accepted')
p=read(P/'proposal/PROPOSAL.json');p['_sha256']=sha(P/'proposal/PROPOSAL.json')
c=read(P/'proposal/CONTROL_TEMPLATE.json');b=read(P/'proposal/BOARD_TEMPLATE.json');r=read(P/'proposal/RELEASE_TEMPLATE.json')
reject('UNAUTHORIZED_template_refused',lambda:check_documents(c,b,r,p,p['owner_host']))
r['status']='released'
for status in ('ready','running'):
    bb=copy.deepcopy(b);bb['tasks'][0]['status']=status
    check(status+'_staged_PASS',check_documents(c,bb,r,p,p['owner_host'])['status']=='PASS')
bb=copy.deepcopy(b);bb['tasks'][0]['status']='released'
reject('board_released_refused',lambda:check_documents(c,bb,r,p,p['owner_host']))
old=copy.deepcopy(r);old['release_id']='P11_A_COMMON_POOL_FIRST_PARENT_V2'
reject('old_V2_identity_refused',lambda:check_documents(c,b,old,p,p['owner_host']))
reject('closed_refused',lambda:check_documents(c,b,{**r,'closed':True},p,p['owner_host']))
prior=read(inheritance.PREVIOUS/'proposal/PROPOSAL.json')
check('same_116_caps_source_timeout_storage',len(p['resource_caps'])==116 and all(p[k]==prior[k] for k in ('resource_caps','source','timeouts','storage')))
check('new_future_paths_absent_and_disjoint',all(not Path(v).exists() and v not in prior['paths'].values() for v in p['paths'].values()))
cfg=read(P/'config/CONFIG.json');src=cfg['source_manifest_ref']
check('actual_small_source_manifest_matches_exact_cfg',Path(src['path']).stat().st_size<=MAX_BANK_BYTES and sha(src['path'])==src['sha256'] and read(src['path'])==cfg['source'])

# Reuse only the tiny synthetic fixture constructor AST from this new task,
# without importing/executing its test suite. Call the real loader one final time.
import types
code=(P/'tests/check_binding_delta_cpu.py').read_text();tree=ast.parse(code)
functions=[copy.deepcopy(n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('write','ref','fixture')]
ns=dict(Path=Path,json=json,sha=sha,BASE=Path(sys.argv[2]).resolve(),OUT=OUT/'writer_final',Store=Store,
    types=types,ARMS=ARMS,prepare_bank_reference=prepare_bank_reference)
exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),'new_task_fixture_constructor_only','exec'),ns)
e,normal,reference=ns['fixture']('valid');load_bank(e,reference)
path=e.out/'BANK_REFERENCE_VERIFICATION.json'
check('final_actual_loader_audit_serialization_bound',path.stat().st_size<=2*MAX_BANK_BYTES)
check('loader_no_branch_raw_copies',not list(e.out.glob('*.f32')) and not (e.out/'bank').exists())
for f in (P/'code').rglob('*.py'):ast.parse(f.read_text())
check('changed_overlay_AST_PASS',True)
for name,value in [('CONTROL.json',c),('BOARD.json',b),('RELEASE.json',r)]:
    (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
(OUT/'CHECKS.json').write_text(json.dumps(dict(status='PASS',checks=checks,synthetic=True,real_calls=0,old_suites_run=False),indent=2)+'\n')
print(json.dumps(dict(status='PASS',checks=len(checks),staging=str(OUT))))
