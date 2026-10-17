"""CPU recovery policy. Never edits a live package, scientific claim or priority."""
import datetime as dt
import hashlib
import json
import socket
import time
from pathlib import Path
from qio import read, sha, new_json, atomic_json, same_process, process_identity, utc, ref

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT.parents[2]
WORKSPACE = CAMPAIGN.parents[2]
ORIGINAL = CAMPAIGN/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1'
PREVIOUS = CAMPAIGN/'results/A/A_D24_FULL_Q_AUTORUN_HANDOFF_V2'
LIVE = CAMPAIGN/'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1'
ISSUES = CAMPAIGN/'nodes/A/issues'
GRANT = CAMPAIGN/'deadline_20260924/AUTONOMOUS_RECOVERY_AND_SKIP_AUTHORIZATION_V1.json'
GRANT_SHA = '87878b0e2019048935904d639d1d15a1af9f0778047171a508054fecaadd4ab0'
POST_SHA = 'fa907477112320e7f8356282c5ba64742452172dee998e9efc20a82b92b9c4b1'
V2_SHA = 'fb15e23ad4ed75eaa1b9490784d58dc9dc925e440194e99cab066ae11af6414f'
THREAD = '01a0b91f-7443-71b1-915d-6cdb6d6a1a13'
ANALYSIS_THREAD = '01a0b91f-355f-7cd1-ae36-412500534ffb'
TASK = 'A_D24_AUTORECOVERY_QUEUE_RULE_V1'


def authority():
    if sha(GRANT) != GRANT_SHA:
        raise ValueError('recovery authority SHA mismatch')
    grant = read(GRANT)
    if grant['status'] != 'released' or grant['tasks']['A']['host'] != socket.gethostname():
        raise ValueError('recovery status/host mismatch')
    for key in ['rule', 'selection_rule', 'runtime_compatibility']:
        if sha(CAMPAIGN/grant[key]['path']) != grant[key]['sha256']:
            raise ValueError('operational rule changed: '+key)
    return grant


def timestamp(text):
    return dt.datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()


def iso(seconds):
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).isoformat()


def safe_id(value):
    if not value or len(value) > 200 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-' for c in value):
        raise ValueError('unsafe identity')
    return value


def new_issue(issue_id, *, task, units, error, attempted_fixes, decision_needed,
              blocked_tasks, runnable_tasks, evidence, now=None, directory=ISSUES):
    """First report fixes the deadline. Redelivery never resets it."""
    now = time.time() if now is None else now
    path = Path(directory)/(safe_id(issue_id)+'.json')
    if path.exists():
        return read(path)
    row = dict(issue_id=issue_id, owner='A', task=task, units=units,
               reported_at=iso(now), analysis_response_due_at=iso(now+1800),
               error=error, attempted_fixes=attempted_fixes,
               decision_needed=decision_needed, blocked_tasks=blocked_tasks,
               runnable_tasks=runnable_tasks, evidence=evidence,
               status='waiting_analysis', analysis_original_thread_id=ANALYSIS_THREAD)
    new_json(path, row)
    return row


def update_issue(row, decision, now):
    """An ACK is not a decision; a decision schedules only a gated boundary."""
    out = dict(row)
    actionable = bool(decision and decision.get('issue_id') == row['issue_id']
                      and decision.get('status') == 'actionable'
                      and decision.get('action') in ['resume_with_reference', 'defer', 'cancel']
                      and decision.get('rationale')
                      and (decision['action'] != 'resume_with_reference'
                           or decision.get('candidate_ref')))
    if actionable:
        if row.get('status') == 'decision_received_pending_safe_boundary' and row.get('decision') == decision:
            return out
        out.update(status='decision_received_pending_safe_boundary', decision=decision,
                   decision_received_at=iso(now), decision_does_not_bypass_scientific_gates=True)
    elif row['status'] == 'waiting_analysis' and now >= timestamp(row['analysis_response_due_at']):
        out.update(status='blocked_deferred', deferred_at=iso(now),
                   reason='1800s_without_actionable_decision')
    return out


def fault_kind(message):
    message = str(message).lower()
    if any(s in message for s in ['model semantic', 'action unit', 'observation semantic', 'new source', 'label gap', 'incomplete development']):
        return 'scientific_decision'
    if any(s in message for s in ['cap exceeded', 'stage/node cap', 'cutoff', 'deadline expired', 'revoked']):
        return 'authorization_or_budget'
    if any(s in message for s in ['out of memory', 'cuda memory', 'insufficient ordinary storage', 'exceeds current ram']):
        return 'resource_engineering'
    return 'engineering_diagnosis'


def repair_gate(repair, previous):
    """Evidence for a change is required; no two identical blind restarts."""
    if repair.get('classification') not in ['engineering_diagnosis', 'resource_engineering']:
        return False, 'analysis_decision_required'
    if not repair.get('fault_signature') or not repair.get('diagnosis') or not repair.get('affected_units'):
        return False, 'missing_fault_or_unit_lineage'
    old, new = repair.get('old_code_sha256'), repair.get('new_code_sha256')
    if not old or not new or old == new or not repair.get('targeted_CPU_check_passed'):
        return False, 'no_documented_changed_fix'
    if repair.get('scientific_configuration_changed') is not False:
        return False, 'scientific_change_requires_decision'
    same = [x for x in previous if x.get('fault_signature') == repair['fault_signature']]
    if len(same) >= 2:
        return False, 'same_fault_two_repairs_consumed'
    if any(x.get('new_code_sha256') == new for x in same):
        return False, 'unchanged_retry_forbidden'
    return True, None


def partition_units(authorized_units, valid_rows, claims, log_candidates):
    """A legal unsuccessful terminal is complete too. Never skip a whole job."""
    allowed = set(authorized_units)
    valid, invalid = {}, []
    for row in valid_rows:
        uid = row.get('unit_id')
        if uid not in allowed:
            continue
        if row.get('status') == 'complete' and type(row.get('success')) is bool:
            if uid in valid:
                raise ValueError('multiple valid terminals: '+uid)
            valid[uid] = row
        else:
            invalid.append(uid)
    entered = set(claims) & allowed
    remaining = allowed-set(valid)
    recoverable = remaining & set(log_candidates)
    return dict(valid=valid, unentered=sorted(remaining-entered),
                technical_unfinished=sorted((remaining & entered)-recoverable),
                requires_terminal_log_review=sorted(recoverable),
                invalid_publication_rows=sorted(set(invalid)),
                preserved_scientific_failure_count=sum(not r['success'] for r in valid.values()))


def collect_evidence(roots, authorized):
    claims, rows, logs, attempts = [], [], set(), 0
    stage_attempts, unknown_stage_attempts = {}, 0
    for root in roots:
        root = Path(root)
        claim_paths = sorted((root/'unit_claims').glob('*.json'))
        attempts += len(claim_paths)
        claims.extend(p.stem for p in claim_paths)
        for cp in claim_paths:
            stage=read(cp).get('stage')
            if stage is None:unknown_stage_attempts+=1
            else:stage_attempts[stage]=stage_attempts.get(stage,0)+1
        for p in (root/'runs').glob('*/episodes/*/RESULT.json'):
            summary = p.with_name('SUMMARY_ROW.json')
            row = read(summary if summary.exists() else p)
            rows.append(row)
        # No speculative parsing of terminal logs: review before any replay.
        published = {r.get('unit_id') for r in rows if r.get('status') == 'complete' and type(r.get('success')) is bool}
        for cp in claim_paths:
            if cp.stem not in published:
                claim = read(cp)
                # A missing result can have a lawful terminal in the worker log.
                # Require a per-unit inspected-log conclusion in the repair package.
                logs.add(cp.stem)
    partition = partition_units(authorized, rows, claims, logs)
    partition.update(actual_attempts=attempts, entered_unique=len(set(claims)),
                     stage_attempts=stage_attempts,unknown_stage_attempts=unknown_stage_attempts)
    return partition


def selected_rule(selection, lock_sha, actual_sha):
    return bool(selection and lock_sha == actual_sha
                and selection.get('status') == 'selected_locked'
                and selection.get('Post_only') is True
                and selection.get('Post_development_valid') == 1200
                and selection.get('Velocity_selection_weight') == 0
                and selection.get('fixed_fit_seed') == 9101
                and selection.get('Post_selection_override_sha256') == POST_SHA
                and selection.get('test_used') is False)


def selection_ready():
    p, l = ORIGINAL/'SELECTION.json', ORIGINAL/'SELECTION_LOCK.json'
    if not p.is_file() or not l.is_file():
        return False
    return selected_rule(read(p), read(l)['selection']['sha256'], sha(p))


def group_live(pgid):
    found = []
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            row = process_identity(int(p.name))
            if row and row['pgid'] == pgid and row['state'] != 'Z':
                found.append(row)
    return found


def wave_state(root):
    """Missing metadata is unknown, not exit proof. Never sends a signal."""
    root = Path(root)
    final_path = root/'RESULT.json'
    heartbeat_path = root/'HEARTBEAT.json'
    h = read(heartbeat_path) if heartbeat_path.exists() else {}
    final = read(final_path) if final_path.exists() else None
    ready = root/'DAEMON_READY.json'
    daemon = read(ready).get('process') if ready.exists() else None
    alive = bool(daemon and same_process(daemon))
    chain = root/'chain/MANAGER_EXIT.json'
    manager_exit = read(chain) if chain.exists() else None
    # Process-group check is only performed at a terminal transition, not polling
    # all OS processes on every healthy heartbeat.
    family = None
    if final and final.get('all_owned_descendants_exited') is True:
        manager = h.get('progress', {}).get('manager')
        if not manager:
            mh = root/'chain/HEARTBEAT.json'
            manager = read(mh).get('manager') if mh.exists() else None
        if manager:
            family = group_live(manager['pgid'])
    drained = bool(final and final.get('all_owned_descendants_exited') is True
                   and manager_exit and manager_exit.get('all_owned_processes_exited') is True
                   and family == [])
    return dict(root=str(root), daemon_alive=alive, daemon=daemon,
                heartbeat_utc=h.get('utc'), progress=h.get('progress', {}),
                final=final, manager_exit=manager_exit, confirmed_formal_exit=drained,
                formal_members=family, state='terminal' if drained else 'running' if alive else 'unknown_or_failed')


def candidate_gate(candidate, *, now, alive_formal, exit_verified, selection,
                   valid_units, allowed_units, attempts_remaining, prior_repairs):
    if candidate.get('owner') != 'A' or candidate.get('task_id') != 'A_D24_FULL_Q_AUTORUN_HANDOFF_V2':
        return False, 'foreign_or_unregistered_scope'
    if candidate.get('status') != 'ready' or candidate.get('cancelled'):
        return False, 'not_ready_or_cancelled'
    if now >= candidate['absolute_end_unix']:
        return False, 'cutoff_or_original_stage_deadline'
    if alive_formal or not exit_verified:
        return False, 'healthy_or_unconfirmed_formal_family'
    units = candidate.get('units', [])
    if not units or len(units) != len(set(units)) or not set(units) <= set(allowed_units):
        return False, 'new_or_duplicate_or_foreign_units'
    if set(units) & set(valid_units):
        return False, 'legal_terminal_must_not_replay'
    if candidate.get('selection_required') and not selection:
        return False, 'complete_Post_selection_required'
    if len(units) > attempts_remaining or candidate.get('attempt_limit') != len(units):
        return False, 'attempt_budget_exhausted_or_unbounded_launch'
    if candidate.get('repair'):
        return repair_gate(candidate['repair'], prior_repairs)
    if candidate.get('unentered_only') is not True:
        return False, 'technical_retry_requires_fix_evidence'
    return True, None
