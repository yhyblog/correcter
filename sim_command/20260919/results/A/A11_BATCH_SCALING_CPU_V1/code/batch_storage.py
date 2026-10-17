"""New batch admission; old single-parent risk acceptance grants no authority."""
from pathlib import Path
import json
from core.contracts import ContractError
from storage_admission import capacity,scan_private,exclusive_metadata

def check_admission_document(release,proposal):
    expected=dict(mode='bounded_batch1',run_id=proposal['authorization_identity']['run_id'],
        parent_keys=[p['parent_key'] for p in proposal['parents']],
        project_quota_known=False,exclusive_reservation=False,accepts_monitoring_gaps=True,
        acceptance_scope='this_eight_parent_batch_only_not_500_parent_quota')
    if release.get('storage_admission')!=expected:raise ContractError('new explicit batch storage risk admission required')
    return expected

def gate(release,proposal,capacity_fn=capacity):
    check_admission_document(release,proposal)
    s=proposal['storage'];rows=[capacity_fn(proposal['paths'][k]) for k in ('output','cache')]
    need=s['admission_bytes']+s['minimum_remaining_space_bytes']
    if len({r['device'] for r in rows})!=1:raise ContractError('unquoted multi-filesystem batch')
    if any(r['available_bytes']<need or r['available_inodes']<s['minimum_available_inodes'] for r in rows):
        raise ContractError('insufficient current batch capacity')
    return dict(status='admitted_observation_only',mode='bounded_batch1',required_bytes=need,
        observations=rows,exclusive_reservation=False,project_quota_known=False,
        future_space_guaranteed=False,monitoring_gaps_accepted=release['storage_admission'])

class BatchMonitor:
    def __init__(self,proposal,store,scan_fn=scan_private,capacity_fn=capacity):
        self.p=proposal;self.s=proposal['storage'];self.store=store
        self.scan,self.capacity=scan_fn,capacity_fn;self.polls=0;self.last=None;self.failure=None
    def check(self):
        try:
            if self.polls>=self.s['monitor_max_polls']:raise ContractError('batch monitor polling cap')
            rows=[];s=self.s['per_parent']
            for parent in self.p['parents']:
                row=dict(parent_key=parent['parent_key'],**self.scan(parent['paths']['cache'],s['private_temp_max_entries']))
                if row['logical_file_bytes']>s['private_temp_cache_budget_bytes']:raise ContractError('parent private temp threshold')
                rows.append(row)
            space=self.capacity(self.p['paths']['cache'])
            if space['available_bytes']<self.s['minimum_remaining_space_bytes']:raise ContractError('batch remaining space floor')
            self.polls+=1;self.last=dict(poll=self.polls,parents=rows,capacity=space)
            self.store.append('STORAGE_MONITOR.jsonl',(json.dumps(self.last,allow_nan=False)+'\n').encode())
            return self.last
        except BaseException as e:
            self.failure=dict(type=type(e).__name__,message=str(e));raise
    def summary(self):
        return dict(polls=self.polls,last=self.last,failure=self.failure,hard_quota=False,
            maximum_overshoot_bytes=None,process_group_RSS_peak_bytes=None,
            shared_HF_native_outside_private_root_and_unlinked_bytes=None,
            coverage='eight per-parent private linked-file caches plus filesystem floor; 5s sampling, no quota/reservation guarantee')
