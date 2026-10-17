"""Cross-node immutable CAS journal using atomic exclusive hard-link publication.

No distributed advisory-lock assumption, lease stealing, record deletion, or
lock held across model work. Loser proposals remain as bounded audit evidence.
"""
import copy
import hashlib
import os
import re
import uuid
from pathlib import Path
from qio import canonical, new_json, read, sync_dir, utc


class LedgerFault(RuntimeError):
    pass


class Ledger:
    def __init__(self, root, initial, max_generations=4096):
        self.root = Path(root)
        self.initial = initial
        self.max_generations = max_generations

    def latest(self):
        commits = self.root / 'commits'
        if not commits.exists():
            return -1, copy.deepcopy(self.initial), None
        files = sorted(commits.glob('g[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].json'))
        if not files:
            return -1, copy.deepcopy(self.initial), None
        if len(files) > self.max_generations:
            raise LedgerFault('control ledger generation cap')
        p = files[-1]
        row = read(p)
        n = int(p.stem[1:])
        if row['generation'] != n or len(files) != n + 1:
            raise LedgerFault('ledger generation gap or identity drift')
        if hashlib.sha256(canonical(row['state'])).hexdigest() != row['state_sha256']:
            raise LedgerFault('shared ledger corruption')
        return n, row['state'], row['state_sha256']

    def transact(self, mutation, *, node, operation):
        for _ in range(32):
            generation, old, previous = self.latest()
            if generation + 1 >= self.max_generations:
                raise LedgerFault('control ledger exhausted')
            new = mutation(copy.deepcopy(old))
            row = dict(generation=generation + 1, previous_state_sha256=previous,
                       node=node, operation=operation, created_utc=utc(), state=new,
                       state_sha256=hashlib.sha256(canonical(new)).hexdigest())
            stage = self.root / 'proposals' / (uuid.uuid4().hex + '.json')
            new_json(stage, row, limit=2*1024**2)
            target = self.root / 'commits' / ('g%08d.json' % (generation + 1))
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(stage, target)
            except FileExistsError:
                continue
            sync_dir(target.parent)
            return row
        raise LedgerFault('bounded shared transaction contention')


def empty_state(authorization_sha):
    return dict(schema='queue_shared_ledger_v1', authorization_sha256=authorization_sha,
                jobs={}, sources={}, storage={}, charged_caps={}, machine_validated=[],
                node_breakers={}, stage_blocked=None)


def reserve(state, job, *, source_rows, total_caps, available_bytes, available_inodes,
            storage_bytes, storage_inodes, free_floor, A_priority_floor=0):
    key = job['job_id']; node = job['node']
    if key in state['jobs']:
        raise LedgerFault('job already claimed; no retry')
    if state.get('stage_blocked'):
        raise LedgerFault('stage blocked: ' + str(state['stage_blocked']))
    if state['node_breakers'].get(node, {}).get('blocked'):
        raise LedgerFault('node breaker blocked')
    rows = {x['source_key']: x for x in source_rows}
    for source in job['source_keys']:
        row = rows.get(source)
        if row is None or row['initial_state'] != 'pending' or row['owner'] != node:
            raise LedgerFault('source/owner/split outside frozen pending plan: ' + source)
        if source in state['sources']:
            raise LedgerFault('source already claimed: ' + source)
    others = list(state['storage'].values())
    reserved_bytes = sum(x['bytes'] for x in others if x['active'])
    reserved_inodes = sum(x['inodes'] for x in others if x['active'])
    A_reserved = sum(x['bytes'] for x in others if x['active'] and x['node'] == 'A')
    priority = max(0, A_priority_floor - A_reserved) if node == 'B' else 0
    if available_bytes - reserved_bytes < storage_bytes + free_floor + priority:
        raise LedgerFault('shared capacity admission denied')
    if available_inodes - reserved_inodes < storage_inodes:
        raise LedgerFault('shared inode admission denied')
    if set(job['resource_caps']) != set(total_caps):
        raise LedgerFault('scientific resource vector dimensions drift')
    for name, amount in job['resource_caps'].items():
        if type(amount) is not int or amount < 0:
            raise LedgerFault('invalid budget amount')
        charged = state['charged_caps'].get(name, 0) + amount
        if charged > total_caps[name]:
            raise LedgerFault('stage budget exhausted: ' + name)
        state['charged_caps'][name] = charged
    state['jobs'][key] = dict(job, state='claimed', claimed_utc=utc(), entered=False,
                             unused_budget_reusable=False)
    for source in job['source_keys']:
        state['sources'][source] = dict(job_id=key, node=node, state='claimed')
    state['storage'][key] = dict(node=node, active=True, bytes=storage_bytes,
                                 inodes=storage_inodes, exclusive_filesystem_quota=False)
    return state


def enter(state, job_id, identity):
    row = state['jobs'][job_id]
    if row['state'] != 'claimed' or row['entered']:
        raise LedgerFault('command opportunity already entered or unknown')
    row.update(state='running', entered=True, entered_utc=utc(), process=identity)
    return state


def finish(state, job_id, result):
    row = state['jobs'][job_id]
    if row['state'] not in ('claimed', 'running'):
        raise LedgerFault('duplicate terminal commit')
    if not result['process_exit_proven'] or not result['publication_complete']:
        row.update(state='execution_unknown', result=result)
        state['node_breakers'][row['node']] = dict(blocked=True, reason='exit/publication barrier unknown')
        return state
    row.update(state='terminal', result=result, terminal_utc=utc())
    state['storage'][job_id]['active'] = False
    for key in row['source_keys']:
        state['sources'][key].update(state='terminal', disposition=result['source_dispositions'].get(key, 'not_started_consumed'))
    if result.get('status')=='machine_validated':
        state['machine_validated'].append(dict(job_id=job_id, result=result['validation_ref']))
    # Reserved scientific caps are never returned for use by extra sources.
    return state


def technical_breaker(state, node, parent_results):
    record = state['node_breakers'].setdefault(node, dict(signature=None, consecutive=0, blocked=False))
    for parent in parent_results:
        signature = parent.get('technical_failure_signature')
        if signature:
            record['consecutive'] = record.get('consecutive',0) + 1 if record.get('signature') == signature else 1
            record['signature'] = signature
            if record['consecutive'] >= 3:
                record.update(blocked=True, reason='same technical signature for three consecutive parents')
        else:
            record.update(signature=None, consecutive=0)
    return state


def reserve_auxiliary_storage(state, key, *, node, grant_ref, available_bytes,
                              available_inodes, storage_bytes, storage_inodes,
                              free_floor=536870912, A_priority_floor=93952475136):
    """B independent stages share capacity only; their caller must verify its grant.

    This transaction creates no common-pool source claim, scientific budget or
    executable command. It is deliberately separate from the A source ledger.
    """
    if node!='B' or not key.startswith('B_') or key in state['storage']:
        raise LedgerFault('invalid/duplicate independent B storage identity')
    if not grant_ref.get('sha256') or not grant_ref.get('path'):
        raise LedgerFault('independent once-frozen stage grant reference required')
    if any(type(x) is not int or x<0 for x in (storage_bytes,storage_inodes)):
        raise LedgerFault('invalid auxiliary storage amount')
    active=[v for v in state['storage'].values() if v['active']]
    reserved=sum(v['bytes'] for v in active);inodes=sum(v['inodes'] for v in active)
    A=sum(v['bytes'] for v in active if v['node']=='A')
    extra=max(0,A_priority_floor-A)
    if available_bytes-reserved<storage_bytes+free_floor+extra or available_inodes-inodes<storage_inodes:
        raise LedgerFault('independent stage capacity conflicts with existing reservations/A next floor')
    state['storage'][key]=dict(node=node,active=True,bytes=storage_bytes,inodes=storage_inodes,
        stage_grant=grant_ref,scope='independent_stage_capacity_only',exclusive_filesystem_quota=False)
    return state
