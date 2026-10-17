"""Only strict metadata types and post-load BANK/raw mutation rejection."""
import copy,json,sys,types
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
import inheritance
from core.contracts import sha,ContractError
from shared_plans import prepare_bank_reference,load_bank
from public_records import publish_transition
from storage import Store
from pool_protocol import ARMS
OUT=Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=False)
BASE=Path(sys.argv[2]).resolve();checks=[]
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,sort_keys=True)+'\n')
def ref(p):return dict(path=str(p),sha256=sha(p),format='json')
def check(n,v):checks.append(dict(name=n,passed=bool(v)));assert v,n
def reject(n,fn):
    try:fn()
    except ContractError as e:check(n,True);return str(e)
    raise AssertionError(n+' accepted')
def fixture(name,change=None):
    root=OUT/name;normal=root/'normal';normal.mkdir(parents=True)
    bank=json.loads((BASE/'normal/BANK.json').read_text());paths={}
    for row in bank['plans'].values():
        for key in ('raw50_ref','noise_ref'):
            old=Path(row[key]['path']);new=normal/old.relative_to(BASE/'normal')
            if str(old) not in paths:new.parent.mkdir(parents=True,exist_ok=True);new.write_bytes(old.read_bytes());paths[str(old)]=new
            row[key]['path']=str(new)
        row['raw50_realpath']=str(Path(row['raw50_ref']['path']).resolve())
    if change:change(bank)
    write(normal/'BANK.json',bank)
    anchor=dict(path=str(normal/'BANK.json'),realpath=str(normal/'BANK.json'),sha256=sha(normal/'BANK.json'),format='common_pool_bank_v2')
    write(normal/'BRANCH_RESULT.json',dict(role='normal',status='complete',legal_cut_reached=True,synthetic=True,bank_manifest_ref=anchor))
    src=json.loads(Path(bank['source_manifest_ref']['path']).read_text())
    out=root/'Q_a0_r0';out.mkdir();e=types.SimpleNamespace(out=out,cut=5,synthetic=True,
        job=next(j for j in ARMS if j[0]=='Q_a0_r0'),source_signature=bank['source_signature'],
        identity=dict(run_id=bank['run_id']),plan_refs={},plan_noise={},store=Store(out),
        cfg=dict(source=src,source_manifest_ref=bank['source_manifest_ref'],_normal_output=str(normal)),
        active_bank_plan_key='a0',intervention_evidence=dict(commitment_entered=True,plan_key='a0'))
    prepare_bank_reference(e.cfg,root,synthetic=True)
    return e,normal,dict(source_signature=bank['source_signature'])
for name,mutation in [('float_shape',lambda d:d['plans']['a0'].update(shape=[50.,4.])),
    ('float_size',lambda d:d['plans']['a0'].update(size_bytes=800.)),('float_cut',lambda d:d.update(cut=5.))]:
    e,normal,reference=fixture(name,mutation);reject(name+'_rejected',lambda:load_bank(e,reference))
for name in ('late_BANK_change','late_raw_change'):
    e,normal,reference=fixture(name);load_bank(e,reference)
    t=json.loads((BASE/'Q_a0_r0/transitions/step005.json').read_text())
    for key in ('observation_ref','next_observation_ref'):
        p=e.out/(key+'.json');write(p,dict(synthetic=True));t[key]=ref(p)
    t['generated_chunk_ref']=e.shared_bank.item('a0')['raw50_ref']
    check(name+'_pre_mutation_real_publisher_passes',bool(publish_transition(e,copy.deepcopy(t),t['next_observation_ref'],6)))
    if name=='late_BANK_change':
        raw=(normal/'BANK.json').read_bytes();(normal/'ORIGINAL_BANK.json').write_bytes(raw);(normal/'BANK.json').write_bytes(raw+b' ')
    else:
        p=Path(t['generated_chunk_ref']['path']);raw=p.read_bytes();(normal/'ORIGINAL_PLAN.f32').write_bytes(raw);p.write_bytes(bytes([raw[0]^1])+raw[1:])
    error=reject(name+'_real_publisher_refuses',lambda:publish_transition(e,copy.deepcopy(t),t['next_observation_ref'],6))
    write(e.out/'EXPECTED_REJECTION.json',dict(synthetic=True,error=error,original_bytes_retained=True))
write(OUT/'CHECKS.json',dict(status='PASS',checks=checks,synthetic=True,real_operations=0,prior_suite_rerun=False))
print(json.dumps(dict(status='PASS',checks=len(checks))))
