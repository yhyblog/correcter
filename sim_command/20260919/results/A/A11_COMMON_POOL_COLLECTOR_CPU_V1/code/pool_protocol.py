"""Production pure-CPU candidate/label functions, also used by synthetic tests."""
import hashlib,math,random,struct,sys
from core.contracts import ContractError
VERSION='pool_H10_C5_C10_s300_v1'
ARMS=[('normal',None,None)]+[(f'Q_{family}_r{r}',family,r)
    for family in ('a0','local_plus','local_minus') for r in (0,1)]+[
    (f'G0_{family}_r{r}',family,r) for family in ('old','fresh0','fresh1','fresh2') for r in (0,1)]
def digest(raw):return hashlib.sha256(raw).hexdigest()
def f32(v):return struct.unpack('<f',struct.pack('<f',v))[0]
def unpack(raw):
    if not isinstance(raw,bytes) or len(raw)!=800:raise ContractError('raw50 must be float32 little-endian800 bytes')
    values=struct.unpack('<200f',raw)
    if not all(math.isfinite(x) for x in values):raise ContractError('nonfinite raw50')
    return values
def raw_group(raw,commitment=10):
    unpack(raw)
    if commitment not in (5,10):raise ContractError('invalid raw commitment')
    return digest(raw[:commitment*16])
def command(raw,index):
    values=unpack(raw)
    return [max(-1.,min(1.,x)) for x in values[index*4:index*4+4]]
def local_pair(raw,seed):
    values=unpack(raw);rng=random.Random(seed)
    nodes=[[rng.gauss(0.,1.) for _ in range(3)] for _ in range(4)]
    d=[]
    for t in range(10):
        lo=0 if t<=4.5 else 1;fraction=(t-4.5*lo)/4.5
        d.extend(nodes[j][lo]*(1-fraction)+nodes[j][lo+1]*fraction for j in range(4))
    return project_direction(raw,d,dict(nodes=nodes,times=[0,4.5,9],rng='stdlib.random.Random.gauss',
        python_version=sys.version,seed=seed))
def project_direction(raw,direction,evidence=None):
    values=unpack(raw)
    if len(direction)!=40 or not all(math.isfinite(x) for x in direction):raise ContractError('direction shape/finite')
    b=[max(-1.,min(1.,x)) for x in values[:40]]
    mask=[1-abs(x)>=.05 for x in b];delta=[0.]*40;radii={}
    for name,indices,target,linf in [
        ('XYZ',[i for i in range(40) if i%4!=3],.05,.15),
        ('gripper',[i for i in range(40) if i%4==3],.10,.40)]:
        d=[direction[i] if mask[i] else 0. for i in indices]
        n=math.sqrt(sum(x*x for x in d)/len(indices))
        if n<=1e-10:r=0.;e=[0.]*len(d)
        else:
            e=[x/n for x in d]
            capacity=min(min(1-abs(b[i]),linf)/abs(x) for i,x in zip(indices,e) if abs(x)>1e-10)
            r=(1-1e-6)*max(0.,min(target,capacity))
        radii[name]=dict(norm=n,radius=r,RMS_target=target,Linf=linf)
        for i,x in zip(indices,e):delta[i]=r*x
    result={}
    for name,sign in [('local_plus',1),('local_minus',-1)]:
        out=bytearray(raw)
        for i,x in enumerate(delta):
            if x!=0. and mask[i]:struct.pack_into('<f',out,4*i,values[i]+sign*x)
        out=bytes(out);after=unpack(out)
        if out[160:]!=raw[160:]:raise ContractError('raw tail changed')
        actual=[after[i]-values[i] for i in range(40)]
        bounded=[max(-1.,min(1.,after[i]))-b[i] for i in range(40)]
        for i in range(40):
            if delta[i]==0. or not mask[i]:
                if out[4*i:4*i+4]!=raw[4*i:4*i+4]:raise ContractError('inactive raw bits changed')
            if abs(actual[i]-bounded[i])>1e-6:raise ContractError('raw/bounded delta mismatch')
        for key,idx,target,linf in [('XYZ',[i for i in range(40) if i%4!=3],.05,.15),('gripper',list(range(3,40,4)),.10,.4)]:
            if math.sqrt(sum(actual[i]**2 for i in idx)/len(idx))>target+1e-6 or max(abs(actual[i]) for i in idx)>linf+1e-6:
                raise ContractError('own symmetric constraint failed')
        result[name]=dict(raw=out,raw_C10_sha256=raw_group(out),actual_raw_delta=actual,actual_execution_delta=bounded)
    return dict(plans=result,evidence=dict(evidence or {},direction=list(direction),mask=mask,
        radii=radii,mathematical_delta=delta,no_resample=True,bitwise_antisymmetry_claim=False))
def stream_seed(master,parent,namespace,repeat,decision):
    if namespace not in ('prefix','normal','fresh','local','Q_C10','G0_C5'):raise ContractError('unknown RNG namespace')
    if namespace=='prefix':repeat=None
    raw=f'{VERSION}|{master}|{parent}|cut5|{namespace}|{repeat}|{decision}'.encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8],'little')%(2**63-1)
def classify_outcome(step,success,terminated,truncated,technical_reason=None):
    if technical_reason:return dict(success=None,outcome_complete=False,reason=technical_reason)
    if success:return dict(success=1,outcome_complete=True,reason='success')
    if step==300:return dict(success=0,outcome_complete=True,reason='absolute_s300_complete')
    if terminated or truncated:return dict(success=None,outcome_complete=False,reason='unknown_timelimit')
    return dict(success=None,outcome_complete=False,reason='short_stage_only')
def paired_label(records,arms,kind):
    if kind not in ('gain','pair','G0'):raise ContractError('label kind')
    expected=['old','fresh0','fresh1','fresh2'] if kind=='G0' else ['local_plus','local_minus'] if kind=='pair' else None
    if expected is not None and arms!=expected:raise ContractError('unfrozen comparison arms')
    if kind=='gain' and (len(arms)!=2 or arms[0] not in ('local_plus','local_minus') or arms[1]!='a0'):raise ContractError('unfrozen gain arms')
    records=[x for x in records if x['arm'] in arms]
    if len(set((x['arm'],x['repeat']) for x in records))!=len(records):raise ContractError('duplicate logical repeat')
    if any(type(x['repeat']) is not int or x['repeat'] not in (0,1) for x in records):raise ContractError('unplanned repeat')
    by={(x['arm'],x['repeat']):x for x in records};valid=[]
    cross_keys=('parent','cut','target','source_signature','context_signature')
    cross_ok=all(len({json_key(x.get(k)) for x in records})==1 and all(x.get(k) is not None for x in records) for k in cross_keys)
    namespace='G0_C5' if kind=='G0' else 'Q_C10'
    cross_ok=cross_ok and all(x['target']==namespace and x['cut']==5 for x in records)
    raw_stable=all(len({x.get('raw_group') for x in records if x['arm']==arm})==1 and all(x.get('raw_group') for x in records if x['arm']==arm) for arm in arms)
    for r in (0,1):
        rows=[by.get((a,r)) for a in arms]
        if any(x is None or not x['outcome_complete'] or x['success'] not in (0,1) or
               x['restore_level']!='full_state_verified' for x in rows):continue
        keys=('parent','cut','target','source_signature','context_signature','suffix_stream')
        if not cross_ok or not raw_stable or any(len({json_key(x[k]) for x in rows})!=1 or rows[0][k] is None for k in keys):continue
        valid.append(r)
    alias=kind in ('gain','pair') and all(by.get((arms[0],r),{}).get('raw_group') is not None and by.get((arms[0],r),{}).get('raw_group')==
        by.get((arms[1],r),{}).get('raw_group') for r in (0,1))
    streams_distinct=all(by.get((a,0),{}).get('suffix_stream')!=by.get((a,1),{}).get('suffix_stream') for a in arms)
    eligible=valid==[0,1] and not alias and streams_distinct
    target=None
    if eligible:
        mean=lambda a:sum(by[(a,r)]['success'] for r in (0,1))/2
        target=(sum(mean(a) for a in arms[1:])/3-mean(arms[0])) if kind=='G0' else mean(arms[0])-mean(arms[1])
    return dict(valid_pair_repeat_ids=valid,target_mask=eligible,target=target,raw_alias_masked=alias)
def json_key(x):
    import json
    return json.dumps(x,sort_keys=True)
