"""Queue authority adapter for the unchanged cold child entry."""
from pathlib import Path
from core.contracts import read,sha
from batch_scheduler import GlobalFault
from qio import QUEUE,under,verify
from qauthority import validate_proposal,collection_gate

def load_authorization(path,full=False):
    path=under(path,QUEUE/'jobs/A')
    r=read(path)
    if r.get('schema')!='queue_derived_release_v1' or r.get('status')!='released':raise GlobalFault('not a queue-derived released command')
    p=read(r['proposal']['path'])
    if sha(r['proposal']['path'])!=r['proposal']['sha256']:raise GlobalFault('queue proposal SHA mismatch')
    if r.get('authorization_identity')!=p['authorization_identity'] or r.get('owner_host')!=p['owner_host']:raise GlobalFault('queue run/host mismatch')
    actual_grant=collection_gate(sequence=p['sequence'],admission=False)
    if r.get('grant')!=actual_grant:raise GlobalFault('derived release grant mismatch')
    verify(r['grant'])
    if r.get('resource_caps')!=p['resource_caps'] or r.get('command_opportunities')!=1 or r.get('retries')!=0:raise GlobalFault('derived release caps/one-shot mismatch')
    validate_proposal(p,full=full)
    p['_sha256']=sha(r['proposal']['path']);r['_sha256']=sha(path)
    return r,p

def select_parent(proposal,key):
    rows=[x for x in proposal['parents'] if x['parent_key']==key]
    if len(rows)!=1:raise GlobalFault('parent outside immutable job')
    return rows[0]

def gate(path,expected,proposal):
    if sha(path)!=expected:raise GlobalFault('derived release changed')
    collection_gate(sequence=proposal['sequence'],admission=False)
