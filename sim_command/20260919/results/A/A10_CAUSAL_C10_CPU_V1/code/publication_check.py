"""Pure JSON publication check. No actual launcher, claim or hardware import."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core.contracts import PACKAGE,CAMPAIGN,RELEASE,read,sha,validate_metadata

def check(control,board,release,proposal):
    return validate_metadata(control,board,release,proposal,CAMPAIGN/'releases'/(RELEASE+'.json'),proposal['owner_host'])

def main():
    p=argparse.ArgumentParser()
    for key in ['control','board','release']:p.add_argument('--'+key,required=True)
    a=p.parse_args();proposal=read(PACKAGE/'proposal/PROPOSAL.json');proposal['_sha256']=sha(PACKAGE/'proposal/PROPOSAL.json')
    check(read(a.control),read(a.board),read(a.release),proposal)
    print(json.dumps(dict(status='PASS',scope='JSON metadata only',hardware_imports=0,launches=0,claims=0)))
if __name__=='__main__':main()
