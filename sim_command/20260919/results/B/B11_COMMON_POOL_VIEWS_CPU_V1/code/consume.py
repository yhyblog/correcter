#!/usr/bin/python
"""Build B-owned reference indices from the 17 already accepted dispositions.

All numerical model, encoder, simulator, driver and training operations are 0.
Large tensors/RGB/MJB/weights are not loaded or rehashed. Frozen runtime file
manifests bind these references; actual reads are JSON and bounded small arrays.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import time
from datetime import datetime, timezone
import views

sys.dont_write_bytecode = True
C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
HERE = Path(__file__).resolve().parent
INDEX = {'path': 'manifests/COMMON_POOL_ACCEPTED_PARENTS_V3.json', 'sha256': '62fdb2d17a7b43be4ab5861671b80557ce7213a65326102689ac821d97fc37ad'}
DISPOSITIONS = {'path': 'manifests/COMMON_POOL_SOURCE_DISPOSITIONS_V2.json', 'sha256': 'a9507f9d917a071d1865e70bed537c97c46f61c08ee87433f6f99d6bcfd43007'}
SIDECAR = C / 'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/sidecar_v1'
SIDE_READY_SHA = '56adfa1657553af79e0b740c643ddcc0616520c62c50983594e0cfa72e9650d9'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def path_of(value):
    p = Path(value)
    return p if p.is_absolute() else C / p


def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    if path.exists():
        require(path.read_bytes() == raw, 'immutable output exists with different content: ' + str(path))
        return
    tmp = path.with_name(path.name + '.tmp.' + str(os.getpid()))
    with tmp.open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    os.link(tmp, path); tmp.unlink()


def shape(value, schema, root):
    """Targeted stdlib validation of the already frozen public schema."""
    if '$ref' in schema:
        return shape(value, root['$defs'][schema['$ref'].split('/')[-1]], root)
    if 'anyOf' in schema:
        for s in schema['anyOf']:
            try:
                shape(value, s, root); return
            except ValueError:
                pass
        raise ValueError('public schema union')
    if 'const' in schema:
        require(value == schema['const'], 'public schema const')
    if 'enum' in schema:
        require(value in schema['enum'], 'public schema enum')
    kind = schema.get('type')
    types = {'object': type(value) is dict, 'array': type(value) is list, 'string': type(value) is str,
             'integer': type(value) is int, 'number': type(value) in (int, float) and math.isfinite(value),
             'boolean': type(value) is bool, 'null': value is None}
    if kind:
        require(types[kind], 'public schema type: ' + kind)
    if kind == 'object':
        props = schema.get('properties', {}); extra = schema.get('additionalProperties', True)
        require(not set(schema.get('required', [])) - value.keys(), 'public missing keys')
        require(extra is not False or not value.keys() - props.keys(), 'public unknown keys')
        for key, child in value.items():
            if key in props:
                shape(child, props[key], root)
            elif isinstance(extra, dict):
                shape(child, extra, root)
    if kind == 'array':
        require(schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', 10**9), 'public array size')
        for child in value:
            shape(child, schema.get('items', {}), root)
    if kind == 'string':
        require(len(value) >= schema.get('minLength', 0), 'public short string')
        if 'pattern' in schema:
            require(re.fullmatch(schema['pattern'], value) is not None, 'public string pattern')
    if kind in ('number', 'integer'):
        require(schema.get('minimum', value) <= value <= schema.get('maximum', value), 'public numeric bound')


def null_paths(value, prefix=''):
    if value is None:
        yield prefix
    elif isinstance(value, dict):
        for k, v in value.items():
            if k != 'missing_reasons':
                yield from null_paths(v, (prefix + '.' if prefix else '') + k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from null_paths(v, prefix + '.' + str(i))


class Reader:
    def __init__(self):
        self.rows = {}; self.manifests = []; self.inputs = []; self.reads = Counter()
        self.byte_counts = Counter(); self.checked_digest = hashlib.sha256()

    def external(self, reference):
        p = path_of(reference['path'])
        data = p.read_bytes(); require(sha(data) == reference['sha256'], 'input SHA mismatch: ' + str(p))
        self.inputs.append(dict(path=str(p), sha256=reference['sha256'], size_bytes=len(data)))
        return json.loads(data) if p.suffix in ('.json', '.jsonl') else data

    def load_manifest(self, reference, roots):
        p = path_of(reference['path']); h = hashlib.sha256(); count = 0
        prefixes = tuple(str(r) + '/' for r in roots)
        def keep(row):
            nonlocal count
            name = row['path']
            if name.startswith(prefixes) and '.partial_' not in name:
                require(name not in self.rows or self.rows[name]['sha256'] == row['sha256'], 'manifest collision')
                self.rows[name] = row; count += 1
        if p.suffix == '.jsonl':
            with p.open('rb') as f:
                for line in f:
                    h.update(line); keep(json.loads(line))
        else:
            raw = p.read_bytes(); h.update(raw)
            for row in json.loads(raw)['files']:
                keep(row)
        require(h.hexdigest() == reference['sha256'], 'runtime manifest SHA mismatch')
        self.manifests.append(dict(path=str(p), sha256=h.hexdigest(), canonical_records_selected=count,
                                   payload_tree_rehashed=False))

    def binding(self, p, expected=None, size=None):
        p = path_of(p)
        require('.partial_' not in str(p), 'partial hardlink alias is not a sample')
        row = self.rows.get(str(p))
        require(row is not None, 'path not bound by accepted runtime manifest: ' + str(p))
        if expected:
            require(row['sha256'] == expected, 'reference disagrees with runtime manifest: ' + str(p))
        if size is not None:
            require(row['size_bytes'] == size, 'array metadata size mismatch: ' + str(p))
        return row

    def data(self, p, expected=None, limit=2*1024*1024):
        p = path_of(p); row = self.binding(p, expected)
        require(row['size_bytes'] <= limit, 'CPU metadata read budget exceeded: ' + str(p))
        raw = p.read_bytes(); require(sha(raw) == row['sha256'], 'runtime bytes changed: ' + str(p))
        self.reads[p.suffix] += 1; self.byte_counts[p.suffix] += len(raw)
        self.checked_digest.update((str(p) + '\0' + row['sha256'] + '\n').encode())
        return raw

    def obj(self, p, expected=None):
        return json.loads(self.data(p, expected))

    def referenced(self, reference):
        return self.obj(reference['path'], reference['sha256'])


def public_check(record, schema):
    shape(record, schema['$defs'][record['record_type']], schema)
    require(record['interface_version'] == 'corrector-sim-interface/1' and record['synthetic'] is False,
            'real public identity')
    require(all(record['missing_reasons'].get(p) for p in null_paths(record)), 'public null reason missing')
    if record['record_type'] == 'episode':
        require(record['cost_event_refs'] == [] and record['missing_reasons'].get('cost_event_refs'),
                'private cost cannot be fabricated as public UUID cost')


def branch_view(reader, root, role, parent, validator, schema, bank):
    branch = root / role; s = reader.obj(branch / 'SIDECAR_V1.json')
    validator.validate(s, SIDECAR / 'schema.json')
    require(not s['synthetic'], 'synthetic sidecar mixed with real pool')
    ident, proto, sig = s['identity'], s['protocol'], s['input_signatures']
    source = parent['source']; expected_episode = source['parent_source_id'] + '__' + role
    require((ident['parent_id'], ident['source_id'], ident['episode_id'], ident['physical_attempt_id'], ident['branch_id'], ident['split']) ==
            (source['parent_source_id'], source['source_id'], expected_episode, expected_episode, role, source['split']), 'sidecar physical identity')
    source_document = reader.external(ident['source_manifest_ref'])
    require(source_document['parent_source_id'] == source['parent_source_id'] and source_document['env_seed'] == source['env_seed'], 'source manifest binding')
    ep = reader.referenced(s['record_ref']); result = reader.obj(branch / 'BRANCH_RESULT.json')
    public_check(ep, schema)
    require(ep['episode_id'] == expected_episode and ep['source']['branch_id'] == role, 'episode cross binding')
    require(ep['source']['parent_episode_id'] == ident['parent_id'] and ep['split'] == source['split'], 'episode split/parent')
    require(ep['identity']['model_sha256'] == sig['policy_sha256'], 'model signature')
    n = result['controls']; require(type(n) is int and 0 < n <= 300, 'invalid actual controls')
    require(n == ep['executed_steps'] == s['outcome']['last_observed_parent_state'], 'control count mismatch')
    value, why = views.outcome(s['outcome'], proto)
    require(result['outcome']['success'] == value and (ep['success'] is None if value is None else int(ep['success']) == value), 'outcome mismatch')
    require(result['first_success_step'] == ep['first_success_step'] == s['outcome']['first_success_step'], 'first success timing')
    member_row = None
    if role != 'normal':
        state = s['restoration']; evidence = reader.referenced(state['verification_ref'])
        require(evidence['fields'] == state['fields'] and evidence['level'] == 'full_state_verified'
                and evidence['bitwise_equal'] and not evidence['unknown_fields'], 'closure evidence mismatch')
        for k in ('reference_state_ref', 'observed_state_ref'):
            reader.binding(state[k]['path'], state[k]['sha256'])
        events = [json.loads(l) for l in reader.data(branch / 'events.jsonl').splitlines()]
        entered = [e for e in events if e['event'] == 'intervention_entered']
        done = [e for e in events if e['event'] == 'attempt_finished']
        require(len(entered) == len(done) == 1 and entered[0]['event_id'] < done[0]['event_id']
                and entered[0]['restore_level'] == 'full_state_verified', 'full-state proof must precede outcome')
        require(entered[0]['absolute_step'] == source['cut'] == proto['cut_step'], 'cut binding')
        require(entered[0]['repeat_id'] == s['repeats']['repeat_id'], 'repeat binding')
        if role.startswith('G0_old'):
            iv = result['intervention_evidence']
            require(iv['kind'] == 'old_queue_control' and iv['plan_replaced'] is False and ep['intervened'] is False
                    and iv['online_G0_triggered'] is False, 'old control is not an online intervention')
        member_row = views.member(s)
        if role.startswith('Q_'):
            raw = reader.data(s['plans']['raw50_ref']['path'], s['plans']['raw50_ref']['sha256'], 800)
            require(views.raw_c10_group(raw) == s['plans']['raw_C10_sha256'] == s['plans']['raw_alias_group'], 'Q raw C10 digest')

    language = reader.data(branch / 'language.f32', limit=8192)
    require(len(language) == 8192 and all(math.isfinite(v) for v in struct.unpack('<2048f', language)), 'language2048 finite')
    observations = []; observation_shas = []; feature_shas = []; transition_shas = []
    for step in range(n + 1):
        p = branch / f'observations/step{step:03d}.json'; ob = reader.obj(p)
        require(ob['step'] == step and ob['feature_signature'] == sig['preprocessing_sha256'], 'feature time/signature')
        require(len(ob['proprio']) == 4 and all(math.isfinite(v) for v in ob['proprio']), 'public policy-state4')
        require(Path(ob['features']['path']) == branch / f'features/step{step:03d}.f32', 'feature branch binding')
        reader.binding(ob['features']['path'], ob['features']['sha256'], 16384)
        require(Path(ob['RGB']['path']) == branch / f'observations/step{step:03d}.ppm', 'RGB branch binding')
        reader.binding(ob['RGB']['path'], ob['RGB']['sha256'])
        observations.append(ob); observation_shas.append(reader.binding(p)['sha256']); feature_shas.append(ob['features']['sha256'])
    # Two small payload checks per branch; all other features remain bound
    # references, not a full feature-store rehash or newly materialized cache.
    for step in sorted({0, n}):
        ob = observations[step]; raw = reader.data(ob['features']['path'], ob['features']['sha256'], 16384)
        require(all(math.isfinite(v) for v in struct.unpack('<4096f', raw)), 'sampled stored feature nonfinite')
    whitelist = None; plan_cache = {}; successes = []
    if role != 'normal':
        whitelist = reader.obj(branch / 'BANK_REFERENCE_VERIFICATION.json')
        require(bank is not None and whitelist['plans'] == bank['plans'], 'shared bank whitelist plans')
        require(whitelist['context']['parent_source_id'] == source['parent_source_id']
                and whitelist['context']['cut'] == source['cut'] and whitelist['context']['source_signature'] == ident['source_signature'], 'shared bank context')
        reader.referenced(whitelist['bank_manifest_ref'])
    for step in range(n):
        p = branch / f'transitions/step{step:03d}.json'; t = reader.obj(p)
        public_check(t, schema)
        require(t['source'] == ep['source'] and t['split'] == source['split'], 'transition physical source')
        require(t['seed'] == source['env_seed'] and t['environment']['task'] == source['task']
                and t['H'] == 10 and t['generated_length'] == 50, 'transition seed/task/temporal identity')
        require(t['step'] == step and t['next_step'] == step + 1 and t['executed_prefix_length'] == 1, 'real contiguous control')
        for field, next_step in [('observation_ref', step), ('next_observation_ref', step + 1)]:
            require(t[field]['path'] == str(branch / f'observations/step{next_step:03d}.json')
                    and t[field]['sha256'] == observation_shas[next_step], 'observation crossed branch or hash')
        require(t['proprioception'] == observations[step]['proprio'], 'state4 representation binding')
        require(t['normalizer_ref']['sha256'] == sig['normalizer_sha256'] and
                t['collection_policy']['checkpoint']['sha256'] == sig['policy_sha256'], 'action/model signature')
        raw, bounded = t['raw_actions'], t['normalized_actions']
        require(len(raw) == len(bounded) == 1 and len(raw[0]) == len(bounded[0]) == 4, 'actual four commands')
        require(all(math.isfinite(v) for v in raw[0] + bounded[0]), 'nonfinite action')
        require(bounded[0] == [min(1., max(-1., v)) for v in raw[0]], 'actual bounded command mapping')
        pref = t['generated_chunk_ref']; planpath = Path(pref['path']); cut = source['cut']
        commitment = 10 if role.startswith('Q_') else 5
        shared = role != 'normal' and not role.startswith('G0_old') and cut <= step < cut + commitment
        if shared:
            family = s['plans']['candidate_family']
            require(whitelist['requested_plan_key'] == family and pref == bank['plans'][family]['raw50_ref'], 'shared plan wrong requested key/phase')
            raw_index = step - cut
        else:
            require(planpath.parent == branch / 'plans', 'non-commitment plan is not branch local')
            raw_index = step % 10 if role == 'normal' or step < cut else (5 + step - cut if step < cut + commitment else (step - cut - commitment) % 10)
        if str(planpath) not in plan_cache:
            plan_cache[str(planpath)] = reader.data(planpath, pref['sha256'], 800)
        plan = plan_cache[str(planpath)]
        require(len(plan) == 800 and sha(plan) == pref['sha256'], 'raw50 reference identity')
        require(t['raw_alias_group'] == views.raw_c10_group(plan), 'transition raw C10 grouping')
        require(struct.pack('<4f', *raw[0]) == plan[raw_index*16:(raw_index+1)*16], 'raw plan to actual action index')
        require(type(t['terminated']) is bool and type(t['truncated']) is bool and len(t['successes']) == 1, 'terminal metadata')
        require(step == n - 1 or not (t['terminated'] or t['truncated'] or t['successes'][0]), 'transition crosses terminal boundary')
        if t['successes'][0]:
            successes.append(step + 1)
        transition_shas.append(reader.binding(p)['sha256'])
    observed_first = successes[0] if successes else None
    require(observed_first == s['outcome']['first_success_step'], 'result success state vs actual transitions')
    windows = views.window_indices(n=n, outcome_value=value, first_success_state=observed_first)
    lvm = views.lvm(s)
    return dict(synthetic=False, parent=ident['parent_id'], source=ident['source_id'], split=source['split'],
                task=ident['task'], episode_id=expected_episode, physical_attempt_id=ident['physical_attempt_id'], role=role,
                root=str(branch), controls=n, source_signature=ident['source_signature'], planned_cut=source['cut'],
                sidecar_sha256=reader.binding(branch/'SIDECAR_V1.json')['sha256'], input_signatures=sig,
                outcome=value, outcome_reason=why, first_success_state=observed_first, target_namespace=proto['target_namespace'],
                sequence_bindings=dict(transition_template='transitions/step{step:03d}.json', transition_sha256=transition_shas,
                                       observation_template='observations/step{step:03d}.json', observation_sha256=observation_shas,
                                       feature_template='features/step{step:03d}.f32', feature_sha256=feature_shas,
                                       feature_shape=[4096], feature_payload_validation='two endpoints per branch; other bytes bound by accepted runtime manifest',
                                       state4_field='observation_bundle.proprio == transition.proprioception',
                                       action_field='transition.normalized_actions[0]; already executed bounded command; no new transform',
                                       action_normalizer_sha256=sig['normalizer_sha256'],
                                       language_ref=dict(path=str(branch/'language.f32'), sha256=sha(language), shape=[2048])),
                windows=windows, LVM=lvm, member=member_row,
                complete_Q_success_during_commitment=bool(role.startswith('Q_') and value == 1 and n < source['cut'] + 10),
                GAF_at_cut_eligible=source['cut'] in windows['GAF'],
                privileged_fields_in_model_inputs=[], public_cost_missing=True)


def integrate(out):
    reader = Reader(); accepted = reader.external(INDEX); disposed = reader.external(DISPOSITIONS)
    locked = json.loads((HERE/'CPU_INPUT_LOCK.json').read_text())
    for r in locked['inputs'].values():
        reader.external(r)
    parents = disposed['parents']; require(len(parents) == 17 and accepted['accepted_parent_count'] == 16, 'fixed handoff set')
    require(len({p['source']['parent_source_id'] for p in parents}) == len(parents), 'duplicate parent')
    by_parent = {p['source']['parent_source_id']: p for p in accepted['parents']}
    roots = [Path(p['run_root']) for p in parents]
    manifests = {p['runtime_manifest']['path']: p['runtime_manifest'] for p in accepted['parents']}
    # First-parent index v3 uses the same runtime JSON manifest as v1.
    for r in manifests.values():
        print('binding runtime manifest', r['path'], flush=True); reader.load_manifest(r, roots)
    side = reader.external(dict(path=str(SIDECAR/'READY.json'), sha256=SIDE_READY_SHA))
    for r in side['files']:
        reader.external(r)
    spec = importlib.util.spec_from_file_location('b11_A_sidecar_validator', SIDECAR/'validator.py')
    validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
    pub = reader.external(locked['inputs']['public_interface_registration'])
    schema = reader.external(pub['files']['interface.schema.json'])
    for key in ('supplement_v2', 'supplement_v1', 'supplement_batch_v1'):
        ready = reader.external(locked['inputs'][key])
        for f in ready.get('files', []):
            reader.external(f)
        for k in ('original_sidecar_ready_ref', 'predecessor_ready_ref', 'old_sidecar_ready_ref', 'public_sidecar_unchanged', 'notes'):
            if k in ready:
                reader.external(ready[k])
    summaries = []; branches = []; all_physical = set(); aggregate_count = 0; inputs_per_source = {}
    for ordinal, parent in enumerate(parents):
        root = Path(parent['run_root']); pid = parent['source']['parent_source_id']; paired_entry = by_parent.get(pid)
        print('parent', ordinal+1, '/17', pid, flush=True)
        coverage = reader.obj(root/'reserved/ATTEMPT_COVERAGE.json'); labels = reader.obj(root/'reserved/PAIRED_LABELS.json')
        bank = reader.obj(root/'normal/BANK.json') if paired_entry else None
        if bank:
            require(bank['parent_source_id'] == pid and bank['cut'] == parent['source']['cut'], 'BANK parent cut')
            for key, plan in bank['plans'].items():
                require(plan['plan_key'] == key and plan['shape'] == [50,4] and plan['dtype'] == '<f4' and plan['size_bytes'] == 800, 'BANK plan metadata')
                reader.data(plan['raw50_ref']['path'], plan['raw50_ref']['sha256'], 800)
            require(bank['plans']['a0']['raw50_ref'] == bank['plans']['fresh0']['raw50_ref'] and bank['plans']['a0']['logical_alias_of'] == 'fresh0', 'a0/fresh0 plan sharing')
        local = []
        for plan in coverage['planned']:
            if not plan['started']:
                require(not plan['result_present'] and not plan['sidecar_present'], 'unstarted attempt contains fabricated result')
                continue
            require(plan['sidecar_present'], 'started branch without usable sidecar')
            item = branch_view(reader, root, plan['role'], parent, validator, schema, bank)
            require(item['physical_attempt_id'] not in all_physical, 'duplicate physical attempt')
            all_physical.add(item['physical_attempt_id']); local.append(item)
            write(out/'indices'/pid/(plan['role']+'.json'), item)
        rows = [r['member'] for r in local if r['member'] is not None]
        fresh_labels = {key: views.paired(rows, key) for key in views.COMPARISONS}
        for key, value in fresh_labels.items():
            old = labels['labels'][key]
            require(all(value[k] == old[k] for k in ('target','target_mask','valid_pair_repeat_ids','raw_alias_masked')), 'recomputed paired label differs: '+pid+' '+key)
            if paired_entry:
                index = reader.obj(root/'reserved'/('AGGREGATE_INDEX_'+key+'.json'))
                require(index['label_key'] == key and index['represents_new_physical_attempt'] is False and index['carrier_fields_are_physical_summary'] is False, 'aggregate carrier')
                require(reader.referenced(index['paired_labels_ref']) == labels, 'aggregate labels ref')
                carrier = reader.referenced(index['aggregate_sidecar_ref']); validator.validate(carrier, SIDECAR/'schema.json')
                require(carrier['identity']['physical_attempt_id'] == 'not_applicable:logical_aggregate' and carrier['outcome']['success'] is None, 'aggregate is not physical')
                expected = {(r['arm'],r['repeat']) for r in rows if r['target'] == value['target_namespace'] and r['arm'] in value['arms']}
                require({(m['arm'],m['repeat_id']) for m in index['members']} == expected, 'aggregate members mismatch')
                for m in index['members']:
                    child = reader.referenced(m['sidecar_ref'])
                    require(child['repeats']['repeat_id'] == m['repeat_id'] and child['plans']['candidate_family'] == m['arm'], 'aggregate selected wrong repeat/arm')
                    original = next(r for r in local if r['member'] and r['member']['target'] == value['target_namespace']
                                    and r['member']['arm'] == m['arm'] and r['member']['repeat'] == m['repeat_id'])
                    require(m['sidecar_ref']['path'] == original['root'] + '/SIDECAR_V1.json'
                            and m['sidecar_ref']['sha256'] == original['sidecar_sha256']
                            and child['identity']['physical_attempt_id'] == original['physical_attempt_id'], 'aggregate cross-parent physical reference')
                require(carrier['repeats']['valid_pair_repeat_ids'] == value['valid_pair_repeat_ids'], 'carrier repeat assertion')
                aggregate_count += 1
        stats = dict(parent=pid, source=parent['source']['source_id'], task=parent['source']['task'], split=parent['source']['split'],
                     cut=parent['source']['cut'], disposition=parent['status'], physical_attempts=len(local),
                     unstarted_attempts=sum(not x['started'] for x in coverage['planned']),
                     labels=fresh_labels, Q_BCE=views.bce_groups(rows),
                     D5_eligible_windows=sum(len(r['windows']['D5']) for r in local),
                     GAF_eligible_windows=sum(len(r['windows']['GAF']) for r in local), LVM_eligible_windows=0,
                     G0_old_online_interventions=0,
                     index_directory=str(out/'indices'/pid))
        if parent['source']['task'] == 'box-close-v3':
            ledger = reader.obj(root/'normal/RESOURCE_LEDGER.json')
            stats['existing_box_close_initialization_evidence'] = dict(
                path=str(root/'normal/RESOURCE_LEDGER.json'), sha256=reader.binding(root/'normal/RESOURCE_LEDGER.json')['sha256'],
                entered=ledger['initialization']['entered_budget_usage'],
                B_initialization_calls=0, interpretation='read-only actual A initialization accounting; no new initialization')
        summaries.append(stats); branches.extend(local)
        inputs_per_source[pid] = sorted({r['sequence_bindings']['language_ref']['sha256'] for r in local})
        require(len(inputs_per_source[pid]) == 1, 'language identity changed inside parent')
        progress=dict(task_id='B11_COMMON_POOL_VIEWS_CPU_V1', status='running', parents_checked=ordinal+1, physical_attempts=len(branches), at_utc=datetime.now(timezone.utc).isoformat())
        p=HERE/'PROGRESS.json'; t=p.with_suffix('.tmp');t.write_text(json.dumps(progress));os.replace(t,p)
    totals = dict(parents=17, paired_parents=16, normal_only_parents=1, train_parents=17, development_parents=0,
                  physical_attempts=len(branches), logical_aggregates=aggregate_count,
                  raw_controls=sum(r['controls'] for r in branches),
                  D5_eligible_windows=sum(len(r['windows']['D5']) for r in branches),
                  GAF_eligible_windows=sum(len(r['windows']['GAF']) for r in branches),
                  LVM_eligible_windows=0, LVM_rejected_physical_records=len(branches),
                  LVM_rejected_contiguous_11frame_windows=sum(max(0,r['controls']-9) for r in branches),
                  Q_BCE_groups=sum(len(r['Q_BCE']) for r in summaries),
                  Q_gain_targets=sum(p['labels'][k]['target_mask'] for p in summaries for k in ('gain_local_plus','gain_local_minus')),
                  Q_pair_targets=sum(p['labels']['pair']['target_mask'] for p in summaries),
                  G0_targets=sum(p['labels']['G0']['target_mask'] for p in summaries),
                  D5_rejected_windows=sum(r['controls']-len(r['windows']['D5']) for r in branches),
                  GAF_rejected_windows=sum(r['controls']-len(r['windows']['GAF']) for r in branches))
    rejected = {method: dict(sum((Counter(r['windows'][method+'_rejected']) for r in branches), Counter())) for method in ('D5','GAF')}
    result=dict(status='PASS', synthetic=False, qualification='CPU reference indices; not materialized training tensors or scientific acceptance',
                totals=totals, by_parent=summaries, rejected_window_reasons=rejected,
                Q_complete_short_commitment_cases=[dict(parent=r['parent'],role=r['role'],controls=r['controls'],cut=r['planned_cut'],Q_outcome=r['outcome'],GAF_at_cut_eligible=r['GAF_at_cut_eligible']) for r in branches if r['complete_Q_success_during_commitment']],
                all_model_input_keys=['observed causal features/proprio references','actual executed commands','frozen language reference'],
                privileged_fields_in_model_inputs=[], language_SHA_by_parent=inputs_per_source,
                new_model_encoder_simulation_training_calls=0, public_cost_view='missing; preserved as [] plus reason',
                full_state_scope='existing SHA-bound captured-field/MJB closure and pre-intervention evidence; no new physical-equivalence proof')
    write(out/'REAL_VIEW_SUMMARY.json',result)
    write(out/'INPUT_CHECK_MANIFEST.json', dict(static_inputs=reader.inputs, accepted_runtime_manifests=reader.manifests,
        actual_reads_by_extension=dict(reader.reads), actual_bytes_by_extension=dict(reader.byte_counts),
        checked_read_sequence_sha256=reader.checked_digest.hexdigest(),
        large_weight_RGB_MJB_rehashes=0, complete_feature_store_rehash=False,
        per_branch_sequence_bindings='indices/<parent>/<branch>.json', records_from_partial_aliases=0))
    print(json.dumps(totals,indent=2),flush=True)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    require(args.out.resolve().is_relative_to(C/'work/B/B11_COMMON_POOL_VIEWS_CPU_V1_r1'), 'isolated B output required')
    integrate(args.out.resolve())
