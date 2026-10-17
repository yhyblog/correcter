"""Pure JSON candidate-publication check. Creates no claim/run/cache."""
import inheritance
import argparse,json,socket
from pathlib import Path
from authorization import check_documents,check_parent_documents
from core.contracts import PACKAGE,read,sha

def main():
    p=argparse.ArgumentParser()
    for key in ('control','board','release'):p.add_argument('--'+key,required=True)
    p.add_argument('--proposal',default=str(PACKAGE/'proposal/PROPOSAL.json'))
    a=p.parse_args();proposal=read(a.proposal);proposal['_sha256']=sha(a.proposal)
    c=check_documents(read(a.control),read(a.board),read(a.release),proposal,socket.gethostname())
    configs=[read(row['config']['path']) for row in proposal['parents']]
    s=check_parent_documents(proposal,configs,read(proposal['accepted_parent_index']['path']))
    print(json.dumps(dict(status='PASS',authority=c,parent_metadata=s,real_operations=0)))
if __name__=='__main__':main()
