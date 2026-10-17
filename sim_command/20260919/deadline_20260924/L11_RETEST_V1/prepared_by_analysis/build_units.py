"""CPU-only L11 unit inventory from saved terminal tables; never launches work."""
from pathlib import Path
import collections
import csv
import hashlib
import json

P = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
OUT = Path(__file__).resolve().parent
INPUTS = {}


def load_json(path):
    path = Path(path)
    data = path.read_bytes()
    INPUTS[str(path)] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return json.loads(data)


def rows(rel):
    path = P / rel
    data = path.read_bytes()
    INPUTS[str(path)] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return [(d, {'table': str(path), 'csv_data_row': i, 'result_path': d.get('result_path')})
            for i, d in enumerate(csv.DictReader(data.decode().splitlines()), 1)]


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def key(u):
    return (u['model'], u['source_id'], u['method'], u['mode'], u['H'], u['Q_loss'], u['Q_fit_seed'])


def unit(model, row, ref, H, mode, owner, native_source=None):
    source = native_source or row
    env_field = 'reset_seed' if native_source is not None else 'env_seed'
    for name in ('source_id', 'task', env_field, 'policy_seed'):
        assert source.get(name) not in (None, ''), (model, name, ref)
    assert row['status'] == 'complete' and row['success'] in ('True', 'False'), ref
    assert row['source_id'] == source['source_id'] and row['task'] == source['task']
    assert int(row['policy_seed']) == int(source['policy_seed'])
    if native_source is not None:
        assert int(row['reset_seed']) == int(source['reset_seed'])
    else:
        assert int(row['H']) == H and row['mode'] == mode
    ordinal = int(source['episode'] if native_source is not None else row['ordinal'])
    repeat = None if native_source is not None else int(row['repeat'])
    u = {
        'model': model, 'source_id': source['source_id'], 'task': source['task'],
        'env_seed': int(source[env_field]), 'env_seed_original_field': env_field,
        'policy_seed': int(source['policy_seed']), 'ordinal': ordinal, 'repeat': repeat,
        'split': source.get('split', 'test'), 'method': row['method'], 'mode': mode,
        'H': H, 'H_meaning': 'native execution queue length, not raw plan length',
        'raw_plan_length': 30 if model == 'X-VLA' else 50,
        'Q_loss': 'L11', 'Q_fit_seed': 9101, 'Q_members': [1041, 1042, 1043, 1044],
        'owner': owner, 'current_paper': row['method'] == 'Post',
        'method_priority': 0 if row['method'] == 'Post' else 1,
        'original_source': ref, 'Q_asset_key': model,
        'status': 'new_unit_not_launched_by_analysis',
        'provenance': 'user_requested_L11_revision_on_existing_revealed_sources',
    }
    if native_source is not None:
        u['native_source_record'] = native_source
        u['missing_reasons'] = {'repeat': 'Original native source manifest has episode ordinal but no explicit repeat field; no new repeated trial is added.'}
    else:
        u['original_unit_id'] = row['unit_id']
    u['unit_id'] = '|'.join(str(x) for x in key(u))
    return u


a_path = 'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/TECHNICAL_EPISODES_ALL_METHODS.csv'
a = rows(a_path)
ensemble_path = P / 'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/ENSEMBLES.json'
ensembles = load_json(ensemble_path)
a_asset = ensembles['ensembles']['L11_s9101']
b_ready_path = P / 'results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/CANDIDATES_READY.json'
b_ready = load_json(b_ready_path)
b_asset = b_ready['candidate_assets']['L11']
b_ranking = load_json(b_asset['ranking']['path'])
b_members = []
for i, member in enumerate([1041, 1042, 1043, 1044]):
    fit = next(d for d in b_ready['fit_results'] if d['loss'] == 'L11' and d['member'] == member)
    assert fit['fit_seed'] == 9101 and fit['status'] == 'complete'
    b_members.append({'member': member, 'checkpoint': fit['checkpoint'],
                      'sha256_previously_recorded': b_ranking['model_hashes'][str(i)],
                      'sha256_source': b_asset['ranking']['path']})
c_ready_path = P / 'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/CANDIDATES_READY.json'
c_ready = load_json(c_ready_path)
c_asset = c_ready['ensembles']['L11']
assets = {
    'pi05': {'source': str(ensemble_path), **a_asset},
    'SmolVLA': {'source': str(b_ready_path), **b_asset, 'fit_seed': 9101, 'loss': 'L11', 'members': b_members},
    'X-VLA': {'source': str(c_ready_path), **c_asset},
}
for model, asset in assets.items():
    assert asset['fit_seed'] == 9101 and asset['loss'] == 'L11'
    assert {m['member'] for m in asset['members']} == {1041, 1042, 1043, 1044}
    for member in asset['members']:
        member['exists_metadata_only'] = Path(member['checkpoint']).is_file()
        assert member['exists_metadata_only'], member
    asset['weights_rehashed_by_this_task'] = False
    asset['previous_method_reference'] = str(P / {
        'pi05': 'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/METHOD_FROZEN.json',
        'SmolVLA': 'results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/METHOD_FROZEN.json',
        'X-VLA': 'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/METHOD_FROZEN.json',
    }[model])

all_units = []
for d, ref in a:
    if d['stage'] in ('MAIN', 'ONCE'):
        all_units.append(unit('pi05', d, ref, 10, d['mode'], 'A'))
for rel in [
    'results/B/B_D24_PI05_SELECTED_H20_H30_V1/H20_r1/FINAL_EPISODES.csv',
    'results/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1/waves/H20_01/FINAL_EPISODES.csv',
    'results/B/B_D24_PI05_SELECTED_H20_H30_V1/H30_r1/FINAL_EPISODES.csv',
    'results/C/C_D24_PI05_SELECTED_H40_H50_V1/FINAL_EPISODES.csv',
]:
    for d, ref in rows(rel):
        if d['status'] != 'complete':
            continue
        H = int(d['H'])
        owner = {20: 'B', 30: 'A', 40: 'C'}.get(H)
        if H == 50:
            owner = 'B' if d['method'] == 'Post' else 'C'
        all_units.append(unit('pi05', d, ref, H, 'G0-multi', owner))

b_source_path = P / 'work/B/B_D24_E8_POST_V1_r1/POST_SOURCES.json'
c_source_path = P / 'results/C/C_D24_XVLA_MULTI_EVAL_V1/config/TEST_SOURCES.json'
for model, owner, source_path, csv_path in [
    ('SmolVLA', 'B', b_source_path, 'results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/evaluation_r1/FINAL_EPISODES.csv'),
    ('X-VLA', 'C', c_source_path, 'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/FINAL_EPISODES.csv'),
]:
    source_payload = load_json(source_path)
    sources = source_payload['sources'] if isinstance(source_payload, dict) else source_payload
    source_map = {s['source_id']: s for s in sources}
    assert len(source_map) == 500
    for d, ref in rows(csv_path):
        ref['native_source_manifest'] = str(source_path)
        all_units.append(unit(model, d, ref, 10, 'G0-multi', owner, source_map[d['source_id']]))

all_map = {key(u): u for u in all_units}
assert len(all_map) == len(all_units) == 8000
reused = []
for d, ref in a:
    if d['stage'] == 'ABLATION' and d['loss'] == 'L11' and d['fit_seed'] == '9101':
        u = unit('pi05', d, ref, 10, 'G0-multi', 'A')
        old = all_map[key(u)]
        for field in ('source_id', 'task', 'env_seed', 'policy_seed', 'ordinal', 'repeat'):
            assert u[field] == old[field], (field, u, old)
        u['status'] = 'reused_completed_L11_result_do_not_rerun'
        u['success'] = d['success'] == 'True'
        u['main_source_reference'] = old['original_source']
        u['reuse_reason'] = 'Exact L11 fit9101 method/H/mode/source/task/environment_seed/policy_seed match from completed full-Q ablation.'
        reused.append(u)
assert len(reused) == 100
reuse_keys = {key(u) for u in reused}
new_units = [u for u in all_units if key(u) not in reuse_keys]
assert len(new_units) == 7900
assert not ({key(u) for u in new_units} & reuse_keys)
priority_H = {10: 0, 20: 1, 30: 2, 40: 3, 50: 4}
new_units.sort(key=lambda u: (u['owner'], u['method_priority'], 1 if u['mode'] == 'G0-once' else 0,
                              priority_H[u['H']], u['model'], u['task'], u['ordinal']))
reused.sort(key=lambda u: (u['method_priority'], u['task'], u['ordinal']))

def jsonl(name, units):
    (OUT / name).write_text(''.join(json.dumps(u, ensure_ascii=False, separators=(',', ':')) + '\n' for u in units))

jsonl('NEW_UNITS.jsonl', new_units)
jsonl('REUSED_UNITS.jsonl', reused)
for owner in 'ABC':
    owned = [u for u in new_units if u['owner'] == owner]
    assert len(owned) == {'A': 2900, 'B': 2500, 'C': 2500}[owner]
    jsonl(f'NEW_UNITS_{owner}.jsonl', owned)
cells = []
for cellkey, count in sorted(collections.Counter((u['owner'], u['model'], u['method'], u['mode'], u['H']) for u in all_units).items()):
    rr = [u for u in reused if (u['owner'], u['model'], u['method'], u['mode'], u['H']) == cellkey]
    cells.append(dict(zip(('owner', 'model', 'method', 'mode', 'H'), cellkey)) |
                 {'planned_total': count, 'reuse': len(rr), 'new': count - len(rr),
                  'reused_successes': sum(u['success'] for u in rr) if rr else None})
assert all(c['planned_total'] == 500 for c in cells)
dump('ASSET_REFERENCES.json', {'Q_loss': 'L11', 'Q_fit_seed': 9101, 'coefficients': {'BCE': 1, 'gain': 1, 'pair': 0.5}, 'assets': assets,
    'changes': 'Only selected Q loss changes L01 to already-trained L11; retain frozen base/D/G0, source/policy/candidate streams, action units, trigger, commitment and per-model protocol.',
    'weight_file_reads_or_hashes': 0})
dump('INPUT_REFERENCES.json', {'small_saved_metadata_only': True, 'sources': INPUTS})
summary = {'status': 'CPU_UNIT_INVENTORY_READY', 'new_scientific_launches': 0,
    'model': 'per-unit model domain retained; native Smol/X are not pi05 source domain',
    'planned_total': 8000, 'new_units': len(new_units), 'reused_units': len(reused),
    'by_owner_new': dict(collections.Counter(u['owner'] for u in new_units)),
    'Post_new': sum(u['method'] == 'Post' for u in new_units),
    'Velocity_new': sum(u['method'] == 'Velocity' for u in new_units),
    'duplicate_unit_keys': 0, 'reuse_new_overlap': 0, 'missing_required_launch_source_fields': [],
    'native_repeat_field': 'not present in original manifest; retain null with reason, use existing episode ordinal/source only',
    'cells': cells, 'data_role': 'L11 revision after prior results were revealed; not new unseen benchmark data',
    'not_a_compute_release': True}
dump('SUMMARY.json', summary)
output_files = ['NEW_UNITS.jsonl', 'REUSED_UNITS.jsonl', 'NEW_UNITS_A.jsonl', 'NEW_UNITS_B.jsonl', 'NEW_UNITS_C.jsonl', 'ASSET_REFERENCES.json', 'INPUT_REFERENCES.json', 'SUMMARY.json', 'build_units.py']
dump('MANIFEST.json', {'files': [{'path': str(OUT / n), 'bytes': (OUT / n).stat().st_size,
    'sha256': hashlib.sha256((OUT / n).read_bytes()).hexdigest()} for n in output_files], 'CPU_only': True})
print(json.dumps(summary, ensure_ascii=False, indent=2))
