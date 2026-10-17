"""Identity-only selection and proposal seed arithmetic. No RNG or runtime claims."""
import hashlib
from core.contracts import ContractError

def source_identity(task,split,ordinal,cut):
    if type(task) is not str or not task.endswith('-v3') or split not in ('train','development'):
        raise ContractError('unquoted source identity')
    if type(ordinal) is not int or ordinal<0 or type(cut) is not int or cut!=(5,55)[ordinal%2]:
        raise ContractError('source ordinal/cut rule changed')
    slug='shelf' if task=='shelf-place-v3' else task.removesuffix('-v3').replace('-','_')
    sid=f'PROPOSED_MT50_{slug}_{split}_{ordinal:04d}'
    rule=f'common_pool_batch_source_v1|{task}|{split}|{ordinal}|cut{cut}'
    return dict(source_id=sid,parent_source_id=sid+'_parent',proposal_seed_rule=rule,
        env_seed=int.from_bytes(hashlib.sha256((rule+'|env').encode('ascii')).digest()[:4],'little')%(2**31-1),
        master_seed=int.from_bytes(hashlib.sha256((rule+'|master').encode('ascii')).digest()[:8],'little')%(2**63-1))

def processed_keys(dispositions):
    keys=set();ids=set()
    for row in dispositions['parents']:
        s=row['source'];ordinal=s.get('ordinal')
        if ordinal is None:
            # The already consumed first shelf0 record predates the ordinal field.
            if s['source_id']!='PROPOSED_MT50_shelf_train_0000' or s['task']!='shelf-place-v3' or s['cut']!=5:
                raise ContractError('missing processed ordinal outside frozen shelf0 legacy identity')
            ordinal=0
        key=(s['task'],s['split'],ordinal,s['cut'])
        if key in keys or s['source_id'] in ids:raise ContractError('duplicate processed source')
        keys.add(key);ids.add(s['source_id'])
    if len(keys)!=dispositions['processed_planned_parent_slots']:raise ContractError('processed identity count mismatch')
    return keys

def select_next_slots(names,dispositions):
    if len(names)!=50 or len(set(names))!=50 or any(type(n) is not str or not n.isascii() for n in names):
        raise ContractError('requires exact 50 ASCII task identities')
    done=processed_keys(dispositions)
    slots=[(task,0,5) for task in sorted(names) if (task,'train',0,5) not in done]
    if len(slots)<8:raise ContractError('fewer than8 remaining A train0/cut5 sources; no fill')
    return slots[:8]

def check_source_seed(source):
    expected=source_identity(source['task'],source['split'],source['ordinal'],source['cut'])
    if any(source.get(k)!=v for k,v in expected.items()):raise ContractError('source ID or deterministic seed rule differs')
    if source['ordinal']//2%2!=0 or source['split']!='train':raise ContractError('source not assigned to A train')
    return expected
