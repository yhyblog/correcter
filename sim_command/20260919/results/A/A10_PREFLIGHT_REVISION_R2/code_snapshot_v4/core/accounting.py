from copy import deepcopy
from pathlib import Path
import json
import os
import time
import uuid

from .validation import ContractError

RESOURCE_KEYS = ('simulator_attempts', 'env_steps', 'vla_sampling_calls', 'flow_forward_calls',
                 'vla_backward_calls', 'critic_forward_calls', 'critic_backward_calls',
                 'monitor_calls', 'optimizer_updates')


class ResourceBudget:
    def __init__(self, caps):
        if any(k not in RESOURCE_KEYS or not isinstance(v, int) or isinstance(v, bool) or v < 0 for k, v in caps.items()):
            raise ContractError('Invalid explicit resource limits')
        self.caps = {key: caps.get(key, 0) for key in RESOURCE_KEYS}
        self.used = dict.fromkeys(RESOURCE_KEYS, 0)

    def reserve(self, units):
        if any(k not in self.caps or not isinstance(v, int) or isinstance(v, bool) or v < 0 for k, v in units.items()):
            raise ContractError('Invalid resource units')
        if any(self.used[k] + v > self.caps[k] for k, v in units.items()):
            raise ContractError('Resource cap reached before operation entry')
        for key, value in units.items():
            self.used[key] += value


class EventJournal:
    """Durable enter-before-call accounting; no automatic retry or fallback."""
    def __init__(self, path, template, budget=None, clock=time.perf_counter):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise ContractError('Journal already exists; reconcile/resume through the run store')
        self.path.touch(exist_ok=False)
        self.template, self.budget, self.clock = deepcopy(template), budget, clock
        self.entered, self.finished = {}, set()

    def _append(self, row):
        encoded = json.dumps(row, allow_nan=False, separators=(',', ':')) + '\n'
        with self.path.open('a') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())

    def enter(self, event_type, *, methods, units=None, parent=None, research_only=False,
              environment_step=0, sampling_index=None, decision_index=0, scope='operation', count=1):
        units = dict(units or {})
        if scope == 'container' and any(units.values()):
            raise ContractError('Container resource duplication')
        if research_only and methods:
            raise ContractError('Research event cannot be deployment-required')
        if parent is not None and (parent not in self.entered or parent in self.finished):
            raise ContractError('Timing parent not active')
        if self.budget is not None:
            self.budget.reserve(units)
        row = deepcopy(self.template)
        event_id = uuid.uuid4().hex
        row.update(event_id=event_id, event_type=event_type, phase='entered',
                   wall_start=self.clock(), wall_end=None, device_elapsed=None, timing_parent_id=parent,
                   is_deployment_required_for_methods=list(methods), is_research_only=research_only,
                   environment_step=environment_step, sampling_index=sampling_index, decision_index=decision_index,
                   measurement_scope=scope, count=count, error=None,
                   resource_units=dict.fromkeys(RESOURCE_KEYS, 0))
        row['resource_units'].update(units)
        row['missing_reasons'] = {k: v for k, v in row.get('missing_reasons', {}).items() if k.startswith('hardware.')}
        row['missing_reasons'].update(wall_end='operation not complete', device_elapsed='not measured', error='no failure')
        if parent is None:
            row['missing_reasons']['timing_parent_id'] = 'root event'
        if sampling_index is None:
            row['missing_reasons']['sampling_index'] = 'not a VLA sampling event'
        self._append(row)
        self.entered[event_id] = row
        return event_id

    def finish(self, event_id, *, error=None, device_elapsed=None):
        if event_id not in self.entered or event_id in self.finished:
            raise ContractError('Unknown or already finished event')
        row = deepcopy(self.entered[event_id])
        row.update(phase='failed' if error is not None else 'returned', wall_end=self.clock(),
                   device_elapsed=device_elapsed, error=str(error) if error is not None else None)
        row['missing_reasons'].pop('wall_end', None)
        if error is not None:
            row['missing_reasons'].pop('error', None)
        if device_elapsed is not None:
            if device_elapsed < 0:
                raise ContractError('Negative device measurement')
            row['missing_reasons'].pop('device_elapsed', None)
        self._append(row)
        self.finished.add(event_id)
        return row

    def invoke(self, event_type, function, **kwargs):
        event_id = self.enter(event_type, **kwargs)
        try:
            value = function()
        except BaseException as error:
            self.finish(event_id, error=error)
            raise
        self.finish(event_id)
        return value


def reconcile(rows):
    entered, ends = {}, {}
    for row in rows:
        key = row['event_id']
        if row['phase'] == 'entered':
            if key in entered:
                raise ContractError('Duplicate event entry')
            parent = row['timing_parent_id']
            if parent is not None and (parent not in entered or parent in ends):
                raise ContractError('Timing parent absent or no longer active')
            entered[key] = row
        else:
            if key not in entered or key in ends:
                raise ContractError('Unmatched or repeated terminal event')
            for field in ('resource_units', 'event_type', 'episode_id', 'identity', 'timing_parent_id',
                          'is_deployment_required_for_methods', 'is_research_only', 'wall_start', 'hardware'):
                if row[field] != entered[key][field]:
                    raise ContractError(f'Event identity changed: {field}')
            if row['wall_end'] < row['wall_start']:
                raise ContractError('Negative time interval')
            ends[key] = row
    return entered, ends


def interval_union(intervals):
    total, start, end = 0., None, None
    for left, right in sorted(intervals):
        if start is None:
            start, end = left, right
        elif left <= end:
            end = max(end, right)
        else:
            total += end - start
            start, end = left, right
    return total + (0 if start is None else end - start)


def summarize(rows, *, method=None, event_refs=None):
    entered, ends = reconcile(rows)
    keys = set(entered) if event_refs is None else set(event_refs)
    if not keys <= entered.keys():
        raise ContractError('Missing referenced actual event')
    if method is not None:
        keys = {key for key in keys if method in entered[key]['is_deployment_required_for_methods']
                and not entered[key]['is_research_only']}
    counts = {resource: sum(entered[key]['resource_units'][resource] for key in keys) for resource in RESOURCE_KEYS}
    intervals = {}
    for key in keys & ends.keys():
        row = ends[key]
        intervals.setdefault(row['hardware']['clock_id'], []).append((row['wall_start'], row['wall_end']))
    device = {}
    for key in keys & ends.keys():
        row = ends[key]
        if row['device_elapsed'] is None:
            continue
        parent = row['timing_parent_id']
        covered = False
        while parent is not None:
            if parent in keys and parent in ends and ends[parent]['device_elapsed'] is not None:
                covered = True
                break
            parent = entered[parent]['timing_parent_id']
        if not covered:
            clock = row['hardware']['clock_id']
            device[clock] = device.get(clock, 0.) + row['device_elapsed']
    return {'ledger': 'experiment_actual' if method is None else 'deployment_reconstructed',
            'counts': counts, 'counted_event_ids': sorted(keys),
            'returned_events': sum(key in ends and ends[key]['phase'] == 'returned' for key in keys),
            'failed_events': sum(key in ends and ends[key]['phase'] == 'failed' for key in keys),
            'incomplete_events': sorted(keys - ends.keys()),
            'wall_union_by_clock': {key: interval_union(value) for key, value in intervals.items()},
            'outermost_measured_device_seconds_by_clock': device,
            'device_scope': 'parent/child overlap excluded; sums measured intervals only, not total device utilization; compare only fixed single-worker timing subsets',
            'time_scope': ('observed event interval union, not measured full episode or wave time' if method is None else
                           'deployment reconstruction estimate from referenced actual intervals; never an independently measured episode time'),
            'missing_device_measurements': sum(key not in ends or ends[key]['device_elapsed'] is None for key in keys)}


def costs_per_success(episode_costs):
    tasks = {}
    for row in episode_costs:
        task = tasks.setdefault(row['task'], {'episodes': 0, 'successes': 0, 'calls': 0, 'technical_failures': 0})
        task['calls'] += row['calls']  # Failed calls remain in the numerator.
        task['episodes'] += 1
        task['successes'] += row['success'] is True
        task['technical_failures'] += row.get('technical_status') != 'complete'
    if not tasks:
        return {'calls_per_success': None, 'missing_reason': 'no episodes', 'tasks': tasks}
    if any(task['technical_failures'] for task in tasks.values()):
        return {'calls_per_success': None, 'missing_reason': 'unresolved technical outcomes; keep costs without inventing binary labels', 'tasks': tasks}
    mean_calls = sum(task['calls'] / task['episodes'] for task in tasks.values()) / len(tasks)
    mean_success = sum(task['successes'] / task['episodes'] for task in tasks.values()) / len(tasks)
    return {'task_macro_calls_per_episode': mean_calls, 'task_macro_success_rate': mean_success,
            'calls_per_success': mean_calls / mean_success if mean_success else None,
            'missing_reason': None if mean_success else 'zero success', 'tasks': tasks,
            'weighting': 'ratio of equally task-weighted mean episode calls and success rate'}
