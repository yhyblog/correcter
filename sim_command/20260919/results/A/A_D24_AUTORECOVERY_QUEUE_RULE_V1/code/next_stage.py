"""Only registered, repaired, unit-filtered packages enter the existing lifecycle."""
import argparse
import fcntl
import json
import os
import subprocess
import time
from pathlib import Path
from policy import (ROOT,CAMPAIGN,ORIGINAL,PREVIOUS,LIVE,ISSUES,V2_SHA,POST_SHA,authority,
                    candidate_gate,collect_evidence,selection_ready,wave_state,safe_id)
from qio import read,sha,new_json,atomic_json,utc,ref


def local_path(text):
    p=Path(text).resolve()
    p.relative_to((CAMPAIGN/'results/A').resolve())
    return p


def checked_ref(row):
    p=local_path(row['path'])
    if p.stat().st_size>8*1024**2:
        raise ValueError('large-model hashing is not a recovery prerequisite')
    if sha(p)!=row['sha256']:
        raise ValueError('recovery reference changed: '+str(p))
    return p


def canonical_units():
    plan=read(CAMPAIGN/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json')
    units={}
    for r in plan['owners']['A']:
        job=read(r['path'])
        if job['stage']=='MAIN' and job['H']!=10:
            raise ValueError('A received foreign MAIN ownership')
        for source in job['sources']:
            uid=job['cell_id']+'__'+source['source_id']
            if uid in units:raise ValueError('duplicate canonical ownership')
            units[uid]=(job,source)
    if len(units)!=5600:raise ValueError('A original finite scope changed')
    return units


def live_admission(now):
    authority()
    root=read(CAMPAIGN/'CONTROL.json');queue=read(CAMPAIGN/'persistent_queue/CONTROL.json')
    node=queue['nodes']['A']
    if (root.get('stop_requested') or queue.get('global_stop') or node.get('enabled') is not True
        or root.get('active_full_Q_autorun_assignment',{}).get('sha256')!=V2_SHA
        or queue.get('active_full_Q_autorun_assignment',{}).get('sha256')!=V2_SHA
        or root.get('active_Post_selection_override',{}).get('sha256')!=POST_SHA
        or queue.get('active_Post_selection_override',{}).get('sha256')!=POST_SHA):
        raise ValueError('live scope revoked/disabled/selection changed')
    end=min(read(ORIGINAL/'RUN_TIME_BUDGET.json')['absolute_end_unix'],1790164800)
    if now>=end:raise ValueError('original finite deadline expired')
    # Global priority is intentionally neither modified nor required to be V2.
    return end


def validate(path, *, now=None):
    now=time.time() if now is None else now
    candidate_path=Path(path)
    end=live_admission(now);candidate=read(candidate_path);cid=safe_id(candidate['candidate_id'])
    if (ROOT/'launches'/cid/'LAUNCH_INTENT.json').exists():
        return dict(ready=False,reason='already_consumed_command_opportunity',candidate_id=cid)
    registry=read(ROOT/'REGISTRY.json')
    roots=[Path(x) for x in registry['evidence_roots']]
    states=[wave_state(r) for r in roots]
    canonical=canonical_units()
    # This bounded scan happens only on an actual prepared continuation, not
    # every healthy heartbeat. It never hashes weights or imports a model.
    evidence=collect_evidence(roots,canonical)
    if evidence['unknown_stage_attempts']:raise ValueError('unknown prior attempt stage; reconcile before launch')
    total=evidence['actual_attempts'];original_count=len(list((ORIGINAL/'unit_claims').glob('*.json')))
    followup_attempts=total-original_count
    selected=selection_ready()
    previous=[read(p) for p in (ROOT/'repairs').glob('*.json')]
    ok,reason=candidate_gate(candidate,now=now,
        alive_formal=any(not s['confirmed_formal_exit'] for s in states),
        exit_verified=all(s['confirmed_formal_exit'] for s in states),selection=selected,
        valid_units=evidence['valid'],allowed_units=canonical,
        attempts_remaining=min(4500-followup_attempts,27000-14896-total),prior_repairs=previous)
    if not ok:return dict(ready=False,reason=reason,candidate_id=cid)
    if not (states[-1].get('final') or {}).get('compute_complete') and not candidate.get('repair'):
        return dict(ready=False,reason='incomplete_chain_needs_documented_private_fix',candidate_id=cid)
    for issue_path in ISSUES.glob('*.json'):
        if issue_path.name.endswith('.decision.json'):continue
        issue=read(issue_path)
        affected=bool(set(candidate['units']) & set(issue.get('units',[])))
        dependency=issue.get('issue_id') in candidate.get('issue_dependencies',[])
        if not affected and not dependency:continue
        decision=issue.get('decision',{})
        if (issue.get('status')!='decision_received_pending_safe_boundary'
            or decision.get('action')!='resume_with_reference'
            or decision.get('candidate_ref',{}).get('sha256')!=sha(candidate_path)):
            return dict(ready=False,reason='unresolved_scientific_issue_even_after_timeout',candidate_id=cid)
    if candidate['absolute_end_unix']>end:raise ValueError('candidate extends original deadline')
    target=local_path(candidate['result_root'])
    if target in roots or any((target/n).exists() for n in ['CLAIM.json','CHAIN_COMMAND.json','QUEUE_COMMAND.json']):
        raise ValueError('cannot relaunch old package/claim')
    if candidate.get('lifecycle')!='existing_service_single_formal_lock_all8_off':
        raise ValueError('normal lifecycle declaration required')
    for item in candidate['required_refs']:checked_ref(item)
    entry=checked_ref(candidate['entry'])
    if entry.parent!=target or entry.suffix!='.sh':raise ValueError('entry must be isolated package shell')
    index=read(checked_ref(candidate['job_index']));actual=[];stages=set()
    for r in index['jobs']:
        job=read(checked_ref(r));stages.add(job['stage'])
        for source in job['sources']:
            uid=job['cell_id']+'__'+source['source_id']
            if uid not in canonical:raise ValueError('unit not A-owned')
            old,expected=canonical[uid]
            if source!=expected:raise ValueError('source/seed changed')
            for k in ['cell_id','stage','H','mode','method','loss','fit_seed','ensemble_key']:
                if old[k]!=job[k]:raise ValueError('scientific identity changed: '+k)
            actual.append(uid)
    if len(actual)!=len(set(actual)) or set(actual)!=set(candidate['units']):raise ValueError('candidate/index units disagree')
    previous_test_attempts=sum(n for stage,n in evidence['stage_attempts'].items() if stage!='DEV')
    new_test_attempts=sum(canonical[u][0]['stage']!='DEV' for u in actual)
    if previous_test_attempts+new_test_attempts>3500:raise ValueError('A post-selection attempt cap3500 exhausted')
    if stages!={'DEV'} and (not candidate.get('selection_required') or not selected):
        raise ValueError('all test stages require complete Post selection first')
    # Science code must retain exact current Post-led bytes. Repair control-plane
    # code privately; scientific changes need an explicit new scientific task.
    for name in ['controller.py','numeric_engine.py','resident_worker.py','selection.py']:
        if sha(target/'code'/name)!=sha(LIVE/'code'/name):raise ValueError('scientific/selection bytes changed: '+name)
    entered_needing_review=set(candidate['units']) & set(evidence['requires_terminal_log_review'])
    reviews={r['unit_id']:r for r in candidate.get('terminal_log_reviews',[])}
    for uid in entered_needing_review:
        r=reviews.get(uid,{})
        if r.get('conclusion')!='no_legal_terminal' or not r.get('evidence_ref'):
            raise ValueError('review unique terminal logs before retry: '+uid)
        checked_ref(r['evidence_ref'])
    repair=candidate.get('repair')
    if repair:
        old=checked_ref(repair['old_code_ref']);new=checked_ref(repair['new_code_ref'])
        check=read(checked_ref(repair['targeted_CPU_check_ref']))
        if sha(old)!=repair['old_code_sha256'] or sha(new)!=repair['new_code_sha256'] or check.get('status')!='PASS':
            raise ValueError('documented fix/check identity mismatch')
        if not set(candidate['units'])<=set(repair['affected_units']):raise ValueError('repair affected lineage missing')
    elif entered_needing_review:
        raise ValueError('entered technical retry requires documented fix')
    # The next package receives the original budget after all actual attempts,
    # not a fresh task cap. Both the prelaunch envelope and worker admission
    # consume the same bounded plan; a default full joblist is forbidden.
    envelope=read(checked_ref(candidate['budget_envelope']))
    if (envelope.get('prior_A_attempts')!=14896+total
        or envelope.get('new_first')!=len(actual)
        or envelope.get('new_attempt_cap')!=len(actual)
        or envelope.get('cumulative_cap')!=27000
        or envelope.get('original_stage_end_unix')!=end):
        raise ValueError('continuation budget envelope reset/mismatch')
    return dict(ready=True,candidate_id=cid,candidate=candidate,entry=str(entry),
        actual_attempts_before=total,followup_attempts_before=followup_attempts,
        preserved_valid=len(evidence['valid']),preserved_scientific_failures=evidence['preserved_scientific_failure_count'],
        units=len(actual),root=str(target),states=[dict(root=s['root'],confirmed_formal_exit=s['confirmed_formal_exit']) for s in states])


def consume(path):
    # Independent controller lock; never takes/releases/nests formal.lock.
    local=Path('/tmp/corrector_A_autorecovery_v1');local.mkdir(exist_ok=True)
    with (local/'launch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        checked=validate(path)
        if not checked['ready']:return checked
        candidate=checked.pop('candidate');cid=checked['candidate_id'];out=ROOT/'launches'/cid
        new_json(out/'LAUNCH_INTENT.json',dict(utc=utc(),candidate=ref(path),validation=checked,
            command=['bash',checked['entry']],no_outer_formal_lock=True))
        if candidate.get('repair'):
            new_json(ROOT/'repairs'/(cid+'.json'),dict(candidate['repair'],utc=utc(),candidate_id=cid,
                actual_attempts_before=checked['actual_attempts_before'],lineage_units=candidate['units']))
        registry=read(ROOT/'REGISTRY.json')
        registry['evidence_roots'].append(checked['root'])
        registry['wave_roots'].append(checked['root'])
        atomic_json(ROOT/'REGISTRY.json',registry)
        try:
            r=subprocess.run(['bash',checked['entry']],cwd=checked['root'],stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
            result=dict(utc=utc(),exit_code=r.returncode,stdout=r.stdout[-8192:],stderr=r.stderr[-8192:],
                        identity_not_model_readiness=True,no_command_retry=True)
        except Exception as e:
            result=dict(utc=utc(),error=dict(type=type(e).__name__,message=str(e)),no_command_retry=True)
        new_json(out/'LAUNCH_RESULT.json',result)
        return dict(ready=True,consumed=True,candidate_id=cid,result=result)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['check','consume']);parser.add_argument('candidate')
    args=parser.parse_args();print(json.dumps(consume(args.candidate) if args.action=='consume' else validate(args.candidate)))
