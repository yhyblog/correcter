import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import inheritance
"""JSON-only planned-publication check; never launches or creates claims."""
import argparse,json,socket
from core.contracts import PACKAGE,read,sha
from authorization import check_documents,quota_gate,verify_ref
from observation_phase import validate_observation_config
def main():
    p=argparse.ArgumentParser()
    for n in ('control','board','release'):p.add_argument('--'+n,required=True)
    a=p.parse_args();proposal=read(PACKAGE/'proposal/PROPOSAL.json')
    proposal['_sha256']=sha(PACKAGE/'proposal/PROPOSAL.json')
    verify_ref(proposal['config'])
    phase_contract=validate_observation_config(read(proposal['config']['path']))
    release=read(a.release)
    result=check_documents(read(a.control),read(a.board),release,proposal,socket.gethostname())
    # Pure JSON check reports storage admission separately, without reading
    # hardware or following potentially large input references.
    result['observation_phase_contract']=phase_contract
    q=release.get('storage_admission')
    result['runtime_storage_admission_present']=isinstance(q,dict)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
