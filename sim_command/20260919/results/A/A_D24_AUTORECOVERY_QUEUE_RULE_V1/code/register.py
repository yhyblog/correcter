"""Register an issue or an already prepared private continuation, CPU only."""
import argparse
import json
from pathlib import Path
from policy import ROOT,ISSUES,authority,new_issue,safe_id,TASK
from qio import read,new_json,ref
from transport import emit


def register_issue(path):
    authority();request=read(path)
    row=new_issue(**request)
    target=ISSUES/(row['issue_id']+'.json')
    emit(TASK+'_'+row['issue_id']+'_analysis','analysis_issue',dict(issue=str(target)),analysis=True)
    return dict(issue=ref(target),status=row['status'],analysis_response_due_at=row['analysis_response_due_at'])


def register_candidate(path):
    authority();candidate=read(path)
    cid=safe_id(candidate['candidate_id'])
    if candidate.get('owner')!='A' or candidate.get('task_id')!='A_D24_FULL_Q_AUTORUN_HANDOFF_V2':
        raise ValueError('candidate outside registered finite A scope')
    target=ROOT/'candidates'/(cid+'.json')
    if target.exists():
        if read(target)!=candidate:raise ValueError('candidate identity collision')
    else:new_json(target,candidate)
    return dict(candidate=ref(target),registration_only=True,not_claim_or_execution=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['issue','candidate']);p.add_argument('json_file');a=p.parse_args()
    print(json.dumps(register_issue(a.json_file) if a.action=='issue' else register_candidate(a.json_file)))
