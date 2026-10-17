"""Only new identity/admission metadata and changed environment/aggregate paths."""
import ast,copy,json,sys,types
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
import inheritance
from authorization import check_documents
from core.contracts import read,sha,ContractError
from storage import Store
from sidecar_output import aggregate
OUT=Path(sys.argv[1]);OUT.mkdir(parents=True,exist_ok=False)
checks=[]
def check(name,predicate):
    checks.append(dict(name=name,passed=bool(predicate)));assert predicate,name
def reject(name,fn):
    try:fn()
    except ContractError:check(name,True);return
    raise AssertionError(name+' accepted')
p=read(P/'proposal/PROPOSAL.json');p['_sha256']=sha(P/'proposal/PROPOSAL.json')
c=read(P/'proposal/CONTROL_TEMPLATE.json');b=read(P/'proposal/BOARD_TEMPLATE.json');r=read(P/'proposal/RELEASE_TEMPLATE.json')
host=p['owner_host']
reject('unauthorized_template_refused',lambda:check_documents(c,b,r,p,host))
r['status']='released'
for status in ('ready','running'):
    bb=copy.deepcopy(b);bb['tasks'][0]['status']=status
    check('staged_'+status+'_accepted',check_documents(c,bb,r,p,host)['status']=='PASS')
for name,doc in [('board_released',b),('closed',r),('wrong_host',r),('old_task',r),('wrong_caps',r),('missing_risk_admission',r)]:
    x=copy.deepcopy(doc)
    if name=='board_released':x['tasks'][0]['status']='released';reject(name,lambda:check_documents(c,x,r,p,host));continue
    if name=='closed':x['closed']=True
    if name=='wrong_host':x['owner_host']='wrong'
    if name=='old_task':x['task_ids']=['A11_COMMON_POOL_FIRST_PARENT_V1']
    if name=='wrong_caps':x['resource_caps']['vla_sampling_calls']+=1
    if name=='missing_risk_admission':x['storage_admission']['accepts_monitoring_gaps']=False
    reject(name,lambda:check_documents(c,b,x,p,host))
old=read(inheritance.BASE/'proposal/PROPOSAL.json')
check('all_116_caps_and_source_seeds_timeouts_unchanged',len(p['resource_caps'])==116 and p['resource_caps']==old['resource_caps'] and p['source']==old['source'] and p['timeouts']==old['timeouts'])
check('all_future_paths_independent_absent',all(v not in old['paths'].values() and not Path(v).exists() for v in p['paths'].values()))
check('metadata_no_AS_override_or_reserved_bytes','process_address_space_hard_bytes' in p['storage'] and p['storage']['process_address_space_hard_bytes'] is None and not any('reserved_bytes' in k for k in p['storage'] if k!='attempt_emergency_reserve_bytes'))

# Execute only child_environment function from revised launch AST with fake environment.
module=ast.parse((P/'code/launch.py').read_text());fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='child_environment')
cfg=read(P/'config/CONFIG.json');ns={'os':types.SimpleNamespace(environ={'NVIDIA_VISIBLE_DEVICES':cfg['cuda_environment']['NVIDIA_VISIBLE_DEVICES']}),
    'ContractError':ContractError,'require_handoff_environment':lambda *a:None}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'actual_child_environment_function','exec'),ns)
env=ns['child_environment'](cfg,Path('/SYNTHETIC_CACHE'))
check('actual_env_private_write_points',env['TMPDIR']=='/SYNTHETIC_CACHE/temporary' and env['XDG_CACHE_HOME']=='/SYNTHETIC_CACHE/cache'
    and env['TORCHINDUCTOR_CACHE_DIR']=='/SYNTHETIC_CACHE/cache/inductor' and env['TRITON_CACHE_DIR']=='/SYNTHETIC_CACHE/cache/triton'
    and env['CUDA_CACHE_PATH']=='/SYNTHETIC_CACHE/cache/cuda' and env['HF_HOME']==cfg['hf_home'] and env['PYTHONDONTWRITEBYTECODE']=='1')

# Actual aggregate producer receives a later repeat with explicit unknown state.
source=Path(sys.argv[2]);parent=OUT/'ineligible_aggregate';parent.mkdir()
from pool_protocol import ARMS
for name,_,_ in ARMS:
    x=read(source/name/'SIDECAR_V1.json')
    if name=='Q_local_minus_r1':x['restoration']['level']='unknown'
    child=parent/name;child.mkdir();(child/'SIDECAR_V1.json').write_text(json.dumps(x))
reserved=parent/'reserved';reserved.mkdir();store=Store(reserved,record_limit=1024**2)
labels=aggregate(parent,store)
check('actual_aggregate_does_not_borrow_first_member',not labels['pair']['target_mask'] and labels['gain_local_plus']['target_mask'])
a=read(reserved/'SIDECAR_AGGREGATE_pair.json')
check('aggregate_neutral_carrier_and_all_members',a['outcome']['success'] is None and a['plans']['physical_alias_of'] is None and len(a['repeats']['paired_members'])==4 and a['repeats']['valid_pair_repeat_ids']==[0])
for f in (P/'code').rglob('*.py'):ast.parse(f.read_text())
check('narrow_all_overlay_AST_passes',True)
(OUT/'CHECKS.json').write_text(json.dumps(dict(status='PASS',synthetic=True,checks=checks,real_calls=0),indent=2)+'\n')
# Staging only: no campaign release/CONTROL/BOARD, no real claim.
for name,value in [('CONTROL.json',c),('BOARD.json',b),('RELEASE.json',r)]:
    (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(dict(status='PASS',checks=len(checks),staging=str(OUT))))
