"""Actual BANK producer/loader and narrowly scoped shared-chunk authority.

Pure stdlib. The runtime Engine uses this exact load_bank method; fixtures do
not import Torch or replace the loader. No plan is sampled or copied here.
"""
import copy,hashlib,json,math,struct
from dataclasses import dataclass
from pathlib import Path
from core.contracts import ContractError
from pool_protocol import ARMS

SCHEMA='common_pool_bank_v2'
KEYS=('fresh0','fresh1','fresh2','a0','local_plus','local_minus')
FORMAT='float32_le_50x4'
MAX_BANK_BYTES=64*1024
def digest(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def bounded_bytes(path,limit):
    with Path(path).open('rb') as f:raw=f.read(limit+1)
    if len(raw)>limit:raise ContractError('shared-plan metadata byte limit')
    return raw
def ref3(ref):
    if type(ref) is not dict or set(ref)!={'path','sha256','format'}:raise ContractError('plan ref fields')
    if any(type(ref[k]) is not str for k in ref):raise ContractError('plan ref types')
    return copy.deepcopy(ref)
def root_for(engine):
    expected=engine.out.parent/'normal'
    if Path(engine.cfg['_normal_output'])!=expected or expected.resolve()!=expected:
        raise ContractError('normal directory is not this physical parent')
    return expected
def source_context(engine):
    source=engine.cfg['source']
    if source.get('cut')!=5 or getattr(engine,'cut',None)!=5:raise ContractError('BANK cut not frozen5')
    return dict(parent_source_id=source['parent_source_id'],source_id=source['source_id'],cut=5,
        source_signature=engine.source_signature,source_manifest_ref=ref3(engine.cfg['source_manifest_ref']),
        run_id=engine.identity['run_id'],synthetic=bool(engine.synthetic))
def verify_source_manifest(engine):
    r=ref3(engine.cfg['source_manifest_ref'])
    raw=bounded_bytes(r['path'],MAX_BANK_BYTES)
    if r['format']!='json' or digest(raw)!=r['sha256'] or json.loads(raw)!=engine.cfg['source']:
        raise ContractError('BANK source manifest SHA/content mismatch')
def raw_bytes(ref,root,realpath):
    r=ref3(ref);path=Path(r['path'])
    if not path.is_absolute() or str(path)!=realpath or str(path.resolve())!=realpath or not path.is_relative_to(root):
        raise ContractError('BANK plan path/realpath outside exact normal parent')
    if r['format']!=FORMAT:raise ContractError('BANK plan raw50 format')
    raw=bounded_bytes(path,800)
    if len(raw)!=800 or digest(raw)!=r['sha256']:raise ContractError('BANK plan SHA/size')
    if not all(math.isfinite(v) for v in struct.unpack('<200f',raw)):raise ContractError('BANK raw50 nonfinite')
    return raw
def make_bank_document(engine,plans):
    if engine.job[0]!='normal' or set(plans)!=set(KEYS):raise ContractError('normal BANK key set')
    root=root_for(engine);items={}
    for key in KEYS:
        raw=plans[key];r=ref3(engine.plan_refs[digest(raw)])
        items[key]=dict(plan_key=key,logical_alias_of='fresh0' if key=='a0' else None,
            raw50_ref=r,raw50_realpath=str(Path(r['path']).resolve()),shape=[50,4],dtype='<f4',size_bytes=800,
            noise_ref=ref3(engine.plan_noise[digest(raw)]))
    return dict(schema_version=SCHEMA,**source_context(engine),plans=items)
def saved_bank_ref(saved):
    return dict(path=saved['path'],realpath=str(Path(saved['path']).resolve()),sha256=saved['sha256'],format=SCHEMA)
def prepare_bank_reference(cfg,parent,*,synthetic=False):
    """Child uses completed normal RESULT as the anchor, before runtime import."""
    parent=Path(parent);normal=parent/'normal'
    if Path(cfg['_normal_output'])!=normal:raise ContractError('reference parent mismatch')
    result=json.loads(bounded_bytes(normal/'BRANCH_RESULT.json',MAX_BANK_BYTES))
    if result.get('role')!='normal' or result.get('status')!='complete' or not result.get('legal_cut_reached') or result.get('synthetic') is not synthetic:
        raise ContractError('normal reference result not qualified')
    ref=result.get('bank_manifest_ref')
    if type(ref) is not dict or set(ref)!={'path','realpath','sha256','format'} or ref['path']!=str(normal/'BANK.json') or ref['realpath']!=str((normal/'BANK.json').resolve()) or ref['format']!=SCHEMA:
        raise ContractError('normal RESULT BANK anchor mismatch')
    raw=bounded_bytes(ref['path'],MAX_BANK_BYTES)
    if digest(raw)!=ref['sha256']:raise ContractError('normal RESULT BANK SHA mismatch')
    cfg['_reference_bank_ref']=copy.deepcopy(ref);cfg['_reference_bank']=json.loads(raw)
    return ref
@dataclass(frozen=True)
class VerifiedBank:
    anchor_json: str
    document_json: str
    context_json: str
    def anchor(self):return json.loads(self.anchor_json)
    def document(self):return json.loads(self.document_json)
    def item(self,key):
        if key not in KEYS:raise ContractError('unknown BANK plan_key')
        return self.document()['plans'][key]
    def verify_anchor(self,engine):
        anchor=self.anchor();root=root_for(engine);path=root/'BANK.json'
        if anchor['path']!=str(path) or anchor['realpath']!=str(path.resolve()) or anchor['format']!=SCHEMA:
            raise ContractError('BANK frozen anchor path changed')
        if canonical(source_context(engine))!=self.context_json:raise ContractError('BANK source/parent/cut/run context changed')
        raw=bounded_bytes(path,MAX_BANK_BYTES)
        if digest(raw)!=anchor['sha256']:raise ContractError('BANK frozen manifest SHA changed')
def load_bank(self,reference):
    """Bound directly as Engine.load_bank; verify metadata and all six raw entries."""
    root=root_for(self);context=source_context(self);anchor=self.cfg.get('_reference_bank_ref')
    if type(anchor) is not dict or set(anchor)!={'path','realpath','sha256','format'} or anchor.get('path')!=str(root/'BANK.json') or anchor.get('realpath')!=str((root/'BANK.json').resolve()) or anchor.get('format')!=SCHEMA:
        raise ContractError('BANK reference identity')
    raw=bounded_bytes(anchor['path'],MAX_BANK_BYTES)
    if digest(raw)!=anchor['sha256']:raise ContractError('BANK manifest SHA mismatch')
    bank=json.loads(raw)
    if bank!=self.cfg.get('_reference_bank'):raise ContractError('BANK supplied content mismatch')
    if bank.get('schema_version')!=SCHEMA or canonical({k:bank.get(k) for k in context})!=canonical(context) or set(bank)!=set(context)|{'schema_version','plans'}:
        raise ContractError('BANK parent/cut/source/manifest/run identity')
    if reference.get('source_signature')!=self.source_signature:raise ContractError('cut reference source mismatch')
    verify_source_manifest(self)
    if type(bank['plans']) is not dict or set(bank['plans'])!=set(KEYS):raise ContractError('BANK exact plan_key set')
    plans={}
    for key in KEYS:
        item=bank['plans'][key]
        if set(item)!={'plan_key','logical_alias_of','raw50_ref','raw50_realpath','shape','dtype','size_bytes','noise_ref'} or item['plan_key']!=key or item['logical_alias_of']!=('fresh0' if key=='a0' else None):
            raise ContractError('BANK plan_key/alias mapping')
        if type(item['shape']) is not list or any(type(n) is not int for n in item['shape']) or item['shape']!=[50,4] or item['dtype']!='<f4' or type(item['size_bytes']) is not int or item['size_bytes']!=800:raise ContractError('BANK raw shape/dtype/size')
        payload=raw_bytes(item['raw50_ref'],root,item['raw50_realpath']);plans[key]=payload
        noise=ref3(item['noise_ref'])
        # Keep own prefix ref for G0_old even if content equals a BANK candidate.
        self.plan_refs.setdefault(digest(payload),copy.deepcopy(item['raw50_ref']))
        self.plan_noise.setdefault(digest(payload),noise)
    a,f=bank['plans']['a0'],bank['plans']['fresh0']
    if a['raw50_ref']!=f['raw50_ref'] or a['noise_ref']!=f['noise_ref']:raise ContractError('a0/fresh0 alias must be exact')
    self.shared_bank=VerifiedBank(canonical(anchor),canonical(bank),canonical(context));self.bank=plans
    verification=dict(schema_version='shared_plan_whitelist_v1',
        synthetic=self.synthetic,bank_manifest_ref=anchor,context=context,requested_plan_key=self.job[1],
        plans=bank['plans'],scope='only declared BANK entries; no extra plan copy; obs/next remain branch-local')
    if len(json.dumps(verification,sort_keys=True,allow_nan=False).encode())+1>2*MAX_BANK_BYTES:raise ContractError('whitelist audit byte limit')
    self.store.json('BANK_REFERENCE_VERIFICATION.json',verification)
    return plans
def active_key(engine,step):
    key=getattr(engine,'active_bank_plan_key',None)
    if key is None:return None
    if tuple(engine.job) not in ARMS or engine.job[1]=='old' or key!=engine.job[1]:raise ContractError('shared plan_key does not match branch request')
    count=10 if engine.job[0].startswith('Q_') else 5
    if not 5<=step<5+count:raise ContractError('shared plan outside its cut commitment')
    evidence=getattr(engine,'intervention_evidence',{})
    if evidence.get('commitment_entered') is not True or evidence.get('plan_key')!=key:raise ContractError('shared plan without actual commitment entry')
    if type(getattr(engine,'shared_bank',None)) is not VerifiedBank:raise ContractError('shared plan without verified BANK')
    return key
def transition_chunk_ref(engine,raw_plan,step):
    key=active_key(engine,step)
    if key is not None:
        item=engine.shared_bank.item(key)
        if digest(raw_plan)!=item['raw50_ref']['sha256']:raise ContractError('requested plan_key content mismatch')
        return item['raw50_ref']
    return copy.deepcopy(engine.plan_refs[digest(raw_plan)])
def validate_chunk_ref(engine,transition):
    ref=ref3(transition['generated_chunk_ref']);key=active_key(engine,transition['step'])
    if key is None:
        path=Path(ref['path'])
        if not path.resolve().is_relative_to(engine.out.resolve()) or digest(bounded_bytes(path,800))!=ref['sha256']:
            raise ContractError('unverified external or dangling branch-native chunk')
        return
    bank=engine.shared_bank;bank.verify_anchor(engine);item=bank.item(key)
    if ref!=item['raw50_ref'] or transition['candidate_family']!=key:raise ContractError('shared ref is not exact requested plan_key mapping')
    raw_bytes(ref,root_for(engine),item['raw50_realpath'])
