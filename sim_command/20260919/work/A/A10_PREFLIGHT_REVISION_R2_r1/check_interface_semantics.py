"""Narrow CPU check of published v1 semantics; no runtime or schema mutation."""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
OLD = BASE / 'results/A/A10'
sys.path.insert(0, str(OLD / 'code_snapshot_v3'))
from core.accounting import summarize
from core.validation import ContractError, validate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    assert not path.exists(), str(path)
    pending = path.with_suffix(path.suffix + '.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(pending, path)


schema = json.loads((OLD / 'interface_v1/interface.schema.json').read_text())
registry = json.loads((BASE / 'manifests/PUBLIC_INTERFACE_V1.json').read_text())
identities = [registry['publication'], *registry['files'].values()]
for ref in identities:
    assert sha(ref['path']) == ref['sha256']
checks = ['published_ready_and_three_file_sha_unchanged']
expected = {'successful_return': (2, 0, 0), 'partial_failure': (0, 2, 0),
            'missing_terminal': (0, 0, 2)}
cases = []
for example in json.loads((OLD / 'accounting_examples_v1/SUMMARY.json').read_text())['examples']:
    assert sha(example['path']) == example['sha256']
    rows = [json.loads(line) for line in Path(example['path']).read_text().splitlines()]
    for row in rows:
        validate(row, schema)
    result = summarize(rows)
    assert result == example['summary']
    assert (result['returned_events'], result['failed_events'], len(result['incomplete_events'])) == expected[example['case']]
    assert result['counts']['vla_sampling_calls'] == result['counts']['flow_forward_calls'] == 1
    if example['case'] == 'missing_terminal':
        assert result['wall_union_by_clock'] == {}
    if example['case'] == 'successful_return':
        successful = rows
    cases.append({'case': example['case'], 'path': example['path'], 'sha256': example['sha256'],
                  'vla_entered_calls': 1, 'flow_entered_calls': 1,
                  'returned_events': result['returned_events'], 'failed_events': result['failed_events'],
                  'incomplete_event_count': len(result['incomplete_events'])})
    checks.append(example['case'] + '_schema_and_entered_only_charge')

refs = [r['event_id'] for r in successful if r['phase'] == 'entered']
assert summarize(successful, event_refs=refs * 3)['counts'] == summarize(successful)['counts']
checks.append('reused_cost_references_charge_once')

def rejects(rows):
    try:
        summarize(rows)
    except ContractError:
        return
    raise AssertionError('Expected conflicting event identity to be rejected')

rejects(successful + successful)
checks.append('duplicate_entered_rows_rejected_instead_of_double_charged')
changed = copy.deepcopy(successful)
for row in changed:
    row['identity']['run_id'] = 'different-run-with-colliding-ids'
rejects(successful + changed)
checks.append('cross_run_event_id_collision_rejected_not_silently_merged')
changed = copy.deepcopy(successful)
changed[-1]['identity']['run_id'] = 'changed-terminal-origin'
rejects(changed)
checks.append('terminal_origin_identity_mismatch_rejected')
changed = copy.deepcopy(successful)
changed[-1]['resource_units']['vla_sampling_calls'] += 1
rejects(changed)
checks.append('terminal_units_cannot_be_cumulative_or_incremental_update')

examples = {r['record_type']: r for r in map(json.loads, (OLD / 'interface_v1/examples.jsonl').read_text().splitlines())}
episode = copy.deepcopy(examples['episode'])
episode['method'].update(name='GAF-v1 adapted', version='synthetic-native-frequency')
for field in ('cut_step', 'entry_generation_id'):
    episode[field] = None
    episode['missing_reasons'][field] = 'Multiple native decisions; read the complete event stream, not this single summary field'
events = []
for index in range(3):
    row = copy.deepcopy(examples['event'])
    row.update(event_id=f'synthetic-integration-E3-{index}', decision_index=index,
               sampling_index=index, environment_step=index * 10,
               is_deployment_required_for_methods=['GAF-v1 adapted'])
    events.append(row)
episode['cost_event_refs'] = [r['event_id'] for r in events]
validate(episode, schema)
for row in events:
    validate(row, schema)
assert summarize(events)['counts']['vla_sampling_calls'] == 3
checks.append('E3_null_single_cut_summary_allows_three_native_decisions')

destination = BASE / 'results/A/A10/interface_semantics_r1'
destination.mkdir()
write_new(destination / 'E3_multiple_decisions_synthetic.json', {'synthetic': True, 'episode': episode, 'events': events})
write_new(destination / 'CPU_CHECK.json', {
    'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'status': 'passed', 'checks': checks, 'check_count': len(checks), 'cases': cases,
    'published_interface': identities,
    'accounting_code': {'path': str(OLD / 'code_snapshot_v3/core/accounting.py'),
                        'sha256': sha(OLD / 'code_snapshot_v3/core/accounting.py')},
    'integration_notes': {'path': str(BASE / 'contracts/INTERFACE_V1_INTEGRATION_NOTES.md'),
                          'sha256': sha(BASE / 'contracts/INTERFACE_V1_INTEGRATION_NOTES.md')},
    'B_consumption_feedback': {'path': str(BASE / 'receipts/B/A10_INTERFACE_FEEDBACK.md'),
                               'sha256': sha(BASE / 'receipts/B/A10_INTERFACE_FEEDBACK.md')},
    'resource_counts': {'simulator_attempts': 0, 'completed_rollouts': 0, 'vla_sampling_calls': 0,
                        'environment_reset_calls': 0, 'optimizer_updates': 0, 'gpu_seconds': 0},
    'counts_in_examples_are_synthetic': True,
})
print(json.dumps({'status': 'passed', 'checks': len(checks), 'evidence': str(destination / 'CPU_CHECK.json')}))
