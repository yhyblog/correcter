from pathlib import Path
import json
import math
import jsonschema

VERSION = 'corrector-sim-interface/1'


class ContractError(ValueError):
    pass


def null_paths(value, prefix=''):
    if value is None:
        yield prefix
    elif isinstance(value, dict):
        for key, child in value.items():
            if key != 'missing_reasons':
                yield from null_paths(child, f'{prefix}.{key}' if prefix else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from null_paths(child, f'{prefix}.{index}')


def references(value):
    if isinstance(value, dict):
        if {'path', 'sha256', 'format'} <= value.keys():
            yield value
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def validate(record, schema):
    jsonschema.Draft202012Validator(schema).validate(record)
    # JSON permits NaN in Python's parser unless explicitly rejected.
    json.dumps(record, allow_nan=False)
    for path in null_paths(record):
        if not record['missing_reasons'].get(path):
            raise ContractError(f'null lacks missing_reason: {path}')
    if not record['synthetic'] and any(r['path'].startswith('synthetic:') for r in references(record)):
        raise ContractError('Synthetic reference in real data')
    kind = record['record_type']
    if kind == 'context':
        if record['observation_max_step'] > record['environment_step']:
            raise ContractError('Observation from the future')
        if record['generated_length'] < max(record['H'], record['C']):
            raise ContractError('Plan shorter than commitment')
    elif kind == 'transition':
        n = record['executed_prefix_length']
        if record['next_step'] != record['step'] + n or n > record['generated_length']:
            raise ContractError('Next state does not follow the actual executed prefix')
        for key in ('raw_actions', 'normalized_actions', 'rewards', 'successes'):
            if record[key] is not None and len(record[key]) != n:
                raise ContractError(f'{key} length differs from actual execution')
        if record['normalized_actions'] is None and record['normalizer_ref'] is None:
            raise ContractError('Neither normalized action nor reconstructible normalizer provided')
        if record['raw_actions'] is None and record['executed_actions_ref'] is None:
            raise ContractError('No executed actions or immutable action reference')
        if record['data_origin'] == 'historical_revealed_held' and record['split'] not in ('historical', 'development'):
            raise ContractError('Revealed held data cannot become new train/test data')
        if record['successes'] is not None:
            first = next((record['step'] + i + 1 for i, success in enumerate(record['successes']) if success), None)
            if first != record['first_success_step']:
                raise ContractError('First success step disagrees with executed success sequence')
    elif kind == 'episode':
        if record['technical_status'] != 'complete' and record['success'] is not None:
            raise ContractError('Technical failure/incompletion is not a binary task outcome')
        if record['technical_status'] == 'complete' and record['success'] is None:
            raise ContractError('Completed episode missing actual outcome')
        if record['intervened'] != (record['cut_step'] is not None):
            raise ContractError('Intervention identity mismatch')
        if record['first_success_step'] is not None and record['first_success_step'] > record['executed_steps']:
            raise ContractError('Success beyond executed trajectory')
    elif kind == 'event':
        if record['is_research_only'] and record['is_deployment_required_for_methods']:
            raise ContractError('Research-only event attributed to deployment')
        if record['phase'] == 'entered' and record['wall_end'] is not None:
            raise ContractError('Entered event already has end time')
        if record['phase'] != 'entered' and (record['wall_end'] is None or record['wall_end'] < record['wall_start']):
            raise ContractError('Invalid finished-event interval')
        if record['measurement_scope'] == 'container' and any(record['resource_units'].values()):
            raise ContractError('Container may not duplicate operation resource counts')
        if record['phase'] == 'failed' and record['error'] is None:
            raise ContractError('Failure lacks error')
    elif kind == 'chunk':
        if record['end_step'] - record['start_step'] != record['actual_executed_length']:
            raise ContractError('Chunk interval disagrees with executed length')
        if record['actual_executed_length'] > record['generated_length']:
            raise ContractError('Executed more than generated')
    return record


def validate_parent_splits(records):
    parent_splits = {}
    for record in records:
        parent = record['source']['parent_episode_id']
        split = record['split']
        if parent in parent_splits and parent_splits[parent] != split:
            raise ContractError(f'Parent episode split leakage: {parent}')
        parent_splits[parent] = split
    return parent_splits


def build_transition_view(records, required_fields, method, target, action_window):
    """Selection only; never invent images, terminal flags or next states."""
    validate_parent_splits(records)
    accepted, excluded = [], []
    for record in records:
        missing = [key for key in required_fields if record.get(key) is None]
        if record['executed_prefix_length'] < action_window:
            missing.append('insufficient_actual_execution_length')
        if missing:
            excluded.append({'source': record['source'], 'step': record['step'], 'missing': missing})
        else:
            accepted.append(record)
    return {'method': method, 'target': target, 'action_window': action_window,
            'accepted': accepted, 'excluded': excluded,
            'parent_count': len({x['source']['parent_episode_id'] for x in accepted}),
            'source_count': len({x['source']['source_id'] for x in accepted}),
            'transition_count': len(accepted)}


def chain_transitions(records):
    """Check one real contiguous branch/suffix stream, not concatenated candidates."""
    if not records:
        return []
    identity = records[0]['source']
    split = records[0]['split']
    for i, record in enumerate(records):
        if record['source'] != identity or record['split'] != split:
            raise ContractError('Cannot splice across parent/source/branch/suffix/split')
        if i and records[i - 1]['next_step'] != record['step']:
            raise ContractError('Noncontiguous transition chain')
        if i and (records[i - 1]['terminated'] or records[i - 1]['truncated']):
            raise ContractError('Transition after terminal/truncated state')
    return records
