"""Publish immutable interface v1 for A10/B10 CPU preparation."""
from pathlib import Path
import hashlib
import json
import os
import platform
import uuid
from datetime import datetime, timezone
import jsonschema

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
OUT = BASE / 'results/A/A10/interface_v1'
VERSION = 'corrector-sim-interface/1'
S = {'type': 'string', 'minLength': 1}
N = {'type': 'number'}
I = {'type': 'integer', 'minimum': 0}
B = {'type': 'boolean'}
SHA = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}


def array(item, minimum=0):
    return {'type': 'array', 'items': item, 'minItems': minimum}


def obj(properties, required=None):
    return {'type': 'object', 'properties': properties,
            'required': list(properties) if required is None else required,
            'additionalProperties': False}


def enum(*values):
    return {'enum': list(values)}


def nullable(value):
    return {'anyOf': [value, {'type': 'null'}]}


def ref(name):
    return {'$ref': '#/$defs/' + name}


defs = {
    'ref': obj({'path': S, 'sha256': SHA, 'format': S}),
    'missing_reasons': {'type': 'object', 'additionalProperties': S},
    'identity': obj({k: S for k in ('campaign_id', 'task_id', 'run_id', 'node_role', 'hostname',
                                  'wave_id', 'shard_id', 'release_id', 'driver', 'runtime', 'gpu_model')} |
                    {k: SHA for k in ('code_sha256', 'config_sha256', 'data_manifest_sha256', 'model_sha256')}),
    'method': obj({'name': S, 'version': S, 'checkpoint': ref('ref'),
                   'training_lineage_ref': nullable(ref('ref'))}),
    'environment': obj({'name': S, 'version': S, 'task': S, 'instruction': S}),
    'source': obj({k: S for k in ('parent_episode_id', 'source_id', 'initial_state_id', 'branch_id', 'suffix_id')}),
    'hardware': obj({'gpu_index': nullable(I), 'gpu_uuid': nullable(S), 'worker_id': S,
                     'concurrency': {'type': 'integer', 'minimum': 1}, 'precision': S,
                     'batch_size': {'type': 'integer', 'minimum': 1}, 'warmup': B, 'clock_id': S}),
    'resources': obj({k: I for k in ('simulator_attempts', 'env_steps', 'vla_sampling_calls',
                                    'flow_forward_calls', 'vla_backward_calls', 'critic_forward_calls',
                                    'critic_backward_calls', 'monitor_calls', 'optimizer_updates')}),
}
common = {'interface_version': {'const': VERSION}, 'synthetic': B, 'missing_reasons': ref('missing_reasons')}


def record(kind, properties):
    return obj(common | {'record_type': {'const': kind}} | properties)


defs['context'] = record('context', {
    'identity': ref('identity'), 'method': ref('method'), 'environment': ref('environment'),
    'source': ref('source'), 'episode_id': S, 'split': enum('train', 'development', 'calibration', 'test', 'historical'),
    'H': {'type': 'integer', 'minimum': 1}, 'C': {'type': 'integer', 'minimum': 1},
    'remaining_budget': I, 'environment_step': I, 'plan_age': I,
    'observation_history_ref': nullable(ref('ref')), 'proprioception': nullable(array(N)),
    'a0_ref': nullable(ref('ref')), 'noise_ref': nullable(ref('ref')), 'normalizer_ref': ref('ref'),
    'generated_length': {'type': 'integer', 'minimum': 1},
    'observation_max_step': I, 'historical_label_commitment': nullable(I),
})
defs['transition'] = record('transition', {
    'identity': ref('identity'), 'dataset_revision': S, 'split': enum('train', 'development', 'calibration', 'test', 'historical'),
    'environment': ref('environment'), 'source': ref('source'), 'collection_policy': ref('method'),
    'seed': I, 'step': I, 'H': {'type': 'integer', 'minimum': 1},
    'generated_length': {'type': 'integer', 'minimum': 1}, 'executed_prefix_length': {'type': 'integer', 'minimum': 1},
    'observation_ref': nullable(ref('ref')), 'proprioception': nullable(array(N)),
    'next_observation_ref': nullable(ref('ref')), 'next_step': I,
    'raw_actions': nullable(array(array(N, 1), 1)), 'normalized_actions': nullable(array(array(N, 1), 1)),
    'normalizer_ref': nullable(ref('ref')), 'generated_chunk_ref': nullable(ref('ref')),
    'executed_actions_ref': nullable(ref('ref')), 'rewards': nullable(array(N, 1)),
    'successes': nullable(array(B, 1)), 'first_success_step': nullable(I),
    'terminated': nullable(B), 'truncated': nullable(B), 'cut_reason': S,
    'anchor_id': nullable(S), 'a0_ref': nullable(ref('ref')), 'candidate_family': nullable(S),
    'raw_alias_group': nullable(S), 'suffix_seed': nullable(I), 'terminal_success': nullable(B),
    'data_origin': enum('new', 'historical_train', 'historical_development', 'historical_revealed_held'),
})
defs['episode'] = record('episode', {
    'identity': ref('identity'), 'episode_id': S, 'method': ref('method'), 'environment': ref('environment'),
    'source': ref('source'), 'train_seed': nullable(I), 'generation_seed': I, 'suffix_seed': I,
    'H': {'type': 'integer', 'minimum': 1}, 'C': {'type': 'integer', 'minimum': 1},
    'split': enum('train', 'development', 'calibration', 'test', 'historical'),
    'success': nullable(B), 'first_success_step': nullable(I), 'termination_reason': S,
    'technical_status': enum('complete', 'failed', 'incomplete'), 'executed_steps': I,
    'intervened': B, 'cut_step': nullable(I), 'prefix_id': S,
    'entry_generation_id': nullable(S), 'suffix_run_id': S, 'reused_from': array(ref('ref')),
    'cost_event_refs': array(S), 'deployment_time_is_reconstructed_estimate': B,
})
EVENTS = ('natural_plan', 'intervention_decision', 'anchor_sample', 'guided_sample',
          'flow_forward', 'vla_backward', 'critic_forward', 'critic_backward', 'monitor',
          'action_transform', 'env_step', 'restore', 'audit_io')
defs['event'] = record('event', {
    'identity': ref('identity'), 'episode_id': S, 'event_id': S, 'event_type': enum(*EVENTS),
    'decision_index': I, 'sampling_index': nullable(I), 'environment_step': I,
    'phase': enum('entered', 'returned', 'failed'), 'wall_start': N, 'wall_end': nullable(N),
    'device_elapsed': nullable({'type': 'number', 'minimum': 0}),
    'timing_parent_id': nullable(S), 'is_deployment_required_for_methods': array(S),
    'is_research_only': B, 'hardware': ref('hardware'), 'resource_units': ref('resources'),
    'measurement_scope': enum('operation', 'count_block', 'container'),
    'count': {'type': 'integer', 'minimum': 1}, 'error': nullable(S),
})
defs['chunk'] = record('chunk', {
    'identity': ref('identity'), 'episode_id': S, 'chunk_id': S, 'plan_H': {'type': 'integer', 'minimum': 1},
    'C': {'type': 'integer', 'minimum': 1}, 'generated_length': {'type': 'integer', 'minimum': 1},
    'actual_executed_length': I, 'start_step': I, 'end_step': I,
    'termination_reason': enum('natural_exhaustion', 'alarm', 'success', 'environment_terminated', 'environment_truncated', 'budget', 'technical_failure', 'intervention_complete'),
    'unguided_plan_ref': nullable(ref('ref')), 'final_raw_plan_ref': ref('ref'),
    'executed_actions_ref': ref('ref'), 'noise_ref': nullable(ref('ref')), 'normalizer_ref': ref('ref'),
})
defs['view_manifest'] = record('view_manifest', {
    'method': ref('method'), 'version': S, 'raw_data_manifest': ref('ref'), 'selection_rule': S,
    'parent_count': I, 'source_count': I, 'transition_count': I,
    'target': S, 'discount': nullable({'type': 'number', 'minimum': 0, 'maximum': 1}),
    'action_window': {'type': 'integer', 'minimum': 1}, 'actual_execution_length_semantics': S,
    'feature_version': S, 'normalizer_ref': ref('ref'), 'historical_initialization': nullable(ref('ref')),
    'training_lineage_ref': nullable(ref('ref')), 'split_unit': {'const': 'parent_episode'},
})
defs['shard_manifest'] = record('shard_manifest', {
    'identity': ref('identity'), 'global_manifest_sha256': SHA,
    'sources': array(obj({'parent_episode_id': S, 'source_id': S, 'initial_state_id': S,
                         'environment_task': S, 'seed': I, 'split': S, 'host': S, 'node_role': S,
                         'Hs': array({'type': 'integer', 'minimum': 1}, 1), 'methods': array(S, 1)})),
    'assignment_rule': {'const': 'explicit_analysis_manifest'},
})
schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
          '$id': 'urn:corrector-sim:interface:1', 'title': VERSION, '$defs': defs,
          'oneOf': [ref(name) for name in ('context', 'transition', 'episode', 'event', 'chunk', 'view_manifest', 'shard_manifest')]}


def href(label):
    return {'path': 'synthetic://' + label, 'sha256': hashlib.sha256(label.encode()).hexdigest(), 'format': 'synthetic-json'}


ident = {k: 'synthetic-' + k for k in defs['identity']['properties']}
ident.update(campaign_id='corrector-sim-20260919', task_id='A10', node_role='A', hostname='synthetic-A')
for k in ('code_sha256', 'config_sha256', 'data_manifest_sha256', 'model_sha256'):
    ident[k] = hashlib.sha256(k.encode()).hexdigest()
method = {'name': 'Post', 'version': 'standalone-own-radius-v1', 'checkpoint': href('model'), 'training_lineage_ref': href('training-lineage')}
env = {'name': 'metaworld', 'version': 'synthetic', 'task': 'synthetic-task', 'instruction': 'Synthetic CPU contract example'}
source = {k: 'synthetic-' + k for k in defs['source']['properties']}
base = {'interface_version': VERSION, 'synthetic': True, 'missing_reasons': {}}
context = base | {'record_type': 'context', 'identity': ident, 'method': method, 'environment': env,
                  'source': source, 'episode_id': 'example', 'split': 'development', 'H': 20, 'C': 10,
                  'remaining_budget': 295, 'environment_step': 5, 'plan_age': 5,
                  'observation_history_ref': href('history-through-step5'), 'proprioception': [0.] * 4,
                  'a0_ref': href('own-raw-a0'), 'noise_ref': href('own-initial-noise'),
                  'normalizer_ref': href('normalizer'), 'generated_length': 50,
                  'observation_max_step': 5, 'historical_label_commitment': 5}
transition = base | {'record_type': 'transition', 'identity': ident, 'dataset_revision': 'synthetic-v1',
    'split': 'development', 'environment': env, 'source': source, 'collection_policy': method,
    'seed': 1, 'step': 5, 'H': 20, 'generated_length': 50, 'executed_prefix_length': 2,
    'observation_ref': href('step5'), 'proprioception': [0.] * 4, 'next_observation_ref': href('step7'),
    'next_step': 7, 'raw_actions': [[0.] * 4] * 2, 'normalized_actions': [[0.] * 4] * 2,
    'normalizer_ref': href('normalizer'), 'generated_chunk_ref': href('50-step-plan'),
    'executed_actions_ref': href('actual2-actions'), 'rewards': [0., 1.], 'successes': [False, True],
    'first_success_step': 7, 'terminated': True, 'truncated': False, 'cut_reason': 'success',
    'anchor_id': 'a0', 'a0_ref': href('own-raw-a0'), 'candidate_family': 'Post',
    'raw_alias_group': 'group0', 'suffix_seed': 1, 'terminal_success': True, 'data_origin': 'new'}
resources = {k: 0 for k in defs['resources']['properties']}
resources['vla_sampling_calls'] = 1
event = base | {'record_type': 'event', 'identity': ident, 'episode_id': 'example', 'event_id': 'sample1',
    'event_type': 'anchor_sample', 'decision_index': 0, 'sampling_index': 0, 'environment_step': 5,
    'phase': 'entered', 'wall_start': 1., 'wall_end': None, 'device_elapsed': None,
    'timing_parent_id': None, 'is_deployment_required_for_methods': ['Post'], 'is_research_only': False,
    'hardware': {'gpu_index': None, 'gpu_uuid': None, 'worker_id': 'cpu', 'concurrency': 1,
                 'precision': 'float32', 'batch_size': 1, 'warmup': False, 'clock_id': 'synthetic-clock'},
    'resource_units': resources, 'measurement_scope': 'operation', 'count': 1, 'error': None,
    'missing_reasons': {'wall_end': 'operation not complete', 'device_elapsed': 'CPU synthetic example',
                        'timing_parent_id': 'root event', 'error': 'no failure',
                        'hardware.gpu_index': 'CPU only', 'hardware.gpu_uuid': 'CPU only'}}
episode = base | {'record_type': 'episode', 'identity': ident, 'episode_id': 'example', 'method': method,
    'environment': env, 'source': source, 'train_seed': 42, 'generation_seed': 1, 'suffix_seed': 1,
    'H': 20, 'C': 10, 'split': 'development', 'success': True, 'first_success_step': 7,
    'termination_reason': 'success', 'technical_status': 'complete', 'executed_steps': 7,
    'intervened': True, 'cut_step': 5, 'prefix_id': 'prefix5', 'entry_generation_id': 'entry1',
    'suffix_run_id': 'suffix1', 'reused_from': [], 'cost_event_refs': ['sample1'],
    'deployment_time_is_reconstructed_estimate': True}
chunk = base | {'record_type': 'chunk', 'identity': ident, 'episode_id': 'example', 'chunk_id': 'chunk1',
    'plan_H': 20, 'C': 10, 'generated_length': 50, 'actual_executed_length': 2,
    'start_step': 5, 'end_step': 7, 'termination_reason': 'success',
    'unguided_plan_ref': href('own-raw-a0'), 'final_raw_plan_ref': href('post-plan'),
    'executed_actions_ref': href('actual2-actions'), 'noise_ref': href('own-initial-noise'), 'normalizer_ref': href('normalizer')}
view = base | {'record_type': 'view_manifest', 'method': method, 'version': 'synthetic-v1',
    'raw_data_manifest': href('shared-raw-manifest'), 'selection_rule': 'parent_episode development only',
    'parent_count': 1, 'source_count': 1, 'transition_count': 1, 'target': 'terminal success; gain/pair by source',
    'discount': None, 'action_window': 10, 'actual_execution_length_semantics': '2 actual steps, no invented50-step next observation',
    'feature_version': 'synthetic', 'normalizer_ref': href('normalizer'),
    'historical_initialization': href('initialization'), 'training_lineage_ref': href('training-lineage'),
    'split_unit': 'parent_episode', 'missing_reasons': {'discount': 'terminal success regression, no TD target'}}
shard = base | {'record_type': 'shard_manifest', 'identity': ident,
    'global_manifest_sha256': hashlib.sha256(b'synthetic-global').hexdigest(),
    'sources': [{'parent_episode_id': source['parent_episode_id'], 'source_id': source['source_id'],
                 'initial_state_id': source['initial_state_id'], 'environment_task': env['task'], 'seed': 1,
                 'split': 'development', 'host': 'synthetic-A', 'node_role': 'A',
                 'Hs': [10, 20, 30, 40, 50], 'methods': ['N', 'R', 'Post', 'Velocity']}],
    'assignment_rule': 'explicit_analysis_manifest'}
examples = [context, transition, episode, event, chunk, view, shard]
jsonschema.Draft202012Validator.check_schema(schema)
validator = jsonschema.Draft202012Validator(schema)
for example in examples:
    validator.validate(example)

README = '''# Public interface v1

Owner A; immutable publication for P00_PREP_V1 and B10. No experiment is released by this interface.
`interface.schema.json` validates one record. `examples.jsonl` contains seven explicitly synthetic CPU examples.
Record kinds: context, transition, episode, event, chunk, view_manifest, shard_manifest.

All real references require a path plus SHA256 and format; a path's presence alone is not identity verification.
Every null must have a nonempty `missing_reasons` entry using the dotted field path. Missing observations/next observations are not fabricated.
`synthetic://` references are allowed only in records marked synthetic. No synthetic examples may enter a real dataset manifest.
`transition.step` is pre-action state time; `next_step=step+executed_prefix_length`; reward/success sequences and executed actions have that actual length. Success at an action's result state uses step+1 indexing.
Parent episode determines split. Never splice across branch/suffix. Historical revealed-held data may only be historical/development, not new train/test.
Core MW H is10/20/30/40/50, C10, generated50, monitor5, at most one intervention, budget300. E8 may describe different dimensions/lengths only under a separate method contract.
Every complete VLA call emits an entered event before execution and one returned/failed event with the same event_id. Count the entered event once even if the call fails.
`resource_units` gives observed counts; do not infer flow_forward counts from method names. Container events have zero resource units.
Failed/incomplete episode success is null, never a fabricated false label. No-alarm/early-success completed episodes remain in denominators.
`is_deployment_required_for_methods` contains exact method names. A shadow monitor is not attributed to N. `is_research_only=true` requires an empty deployment-method list.
Costs: experiment_actual counts unique executed event IDs; each deployment reconstruction references prefix/own entry/own suffix and counts its referenced events without sharing/dividing a0 cost. Reused output does not execute or charge again.
Entered events use null wall_end/device_elapsed with reasons. Wall timestamps are monotonic seconds in hardware.clock_id. Device elapsed is explicit synchronized/device-event measurement, never assumed equal to host submission time.
Parent/child wall intervals must not be added; report union/root intervals as reconstructed estimates, separate from actual episode/wave wall clocks. Concurrent hardware clocks are separate.
Sampling seeds exclude method and host for same-H paired comparisons; source IDs and H distinguish cross-H trajectories. Explicit analysis shards assign all methods for one source to one host.
No stale heartbeat authorizes takeover. An existing matching completion is reused only after identity/file-SHA validation; incomplete claims require an explicit recovery decision.
B adapters consume this published directory and return records under the same schema. New interface revisions use a new directory and READY; never edit v1 in place.
'''
OUT.mkdir(parents=True, exist_ok=True)
assert not (OUT / 'INTERFACE_READY.json').exists(), 'Interface already published; make v2 for changes.'


def write(name, text):
    target = OUT / name
    temporary = target.with_name(target.name + '.tmp.' + uuid.uuid4().hex)
    temporary.write_text(text)
    os.replace(temporary, target)


write('interface.schema.json', json.dumps(schema, ensure_ascii=False, indent=2) + '\n')
write('examples.jsonl', ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in examples))
write('README.md', README)
ready = {'campaign_id': 'corrector-sim-20260919', 'task_id': 'A10', 'task_revision': 1,
         'interface_version': VERSION, 'status': 'ready_for_cpu_adapter_work',
         'hostname': platform.node(), 'published_at_utc': datetime.now(timezone.utc).isoformat(),
         'formal_compute_authorized': False, 'schema_examples_validated': 7,
         'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file()}}
write('INTERFACE_READY.json', json.dumps(ready, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'interface_ready': str(OUT / 'INTERFACE_READY.json'), 'files': ready['files']}))
