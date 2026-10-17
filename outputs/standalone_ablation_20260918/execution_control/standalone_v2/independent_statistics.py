"""Independent post-seal label reaggregation; never launch models or simulators.

Prepared during the wave. Run only after audits/standalone_v2/complete.json
exists. No frozen aggregation function is imported or called.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OLD_ROOT = ROOT.parent/'native10_training_20260916'
TASKS = ('disassemble-v3', 'pick-place-wall-v3', 'shelf-place-v3', 'stick-pull-v3', 'stick-push-v3')
IDS = [f'{TASKS[i % 5]}__{start+i}' for start in (2026111750, 2026111850) for i in range(50)]
IDS_SHA = 'f05bbfeb92da78d8fb9242bd28b116cf6f5a4cff252b5ad0487506e0bd108afc'
COMMON = {'pick-place-wall-v3__2026111866', 'pick-place-wall-v3__2026111881'}
OLD = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
SOLO = ('solo_velocity', 'solo_direct', 'solo_post')
METHODS = OLD+SOLO
PRIMARY = ((7, 1), (6, 1), (5, 1))
SECONDARY = ((7, 4), (6, 3), (5, 2), (7, 0), (6, 0), (5, 0))
REFERENCE = ((1, 0),)
PAIRS = PRIMARY+SECONDARY+REFERENCE
SEED, DRAWS = 2026091801, 10000
BONFERRONI = [.05/6, 1-.05/6]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def verify_audit_seal(folder, expected=None):
    """First gate: never inspect source or branch labels before this passes."""
    seal_path = folder/'complete.json'
    require(seal_path.is_file(), 'Wait for the complete formal audit seal')
    if expected is not None:
        require(sha(seal_path) == expected, 'Formal audit seal SHA differs')
    seal = read(seal_path)
    require(seal.get('status') == 'complete' and seal.get('role') == 'standalone_ablation_full_static_audit_v1',
            'A complete formal audit is required, not preflight')
    files = seal.get('files', {})
    actual = {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p != seal_path}
    require(set(files) == actual and {'result.json', 'source_records.json'} <= set(files), 'Audit seal inventory differs')
    for name, digest in files.items():
        path = (folder/name).resolve()
        require(path.is_relative_to(folder) and sha(path) == digest, 'Audit sealed file differs: '+name)
    return seal


class Evidence:
    def __init__(self, artifacts):
        self.refs = {str(Path(r['path']).resolve()):r['sha256'] for r in artifacts}
        require(len(self.refs) == len(artifacts), 'Duplicate primary-audit artifact paths')
        self.used = {}

    def load(self, path):
        path = Path(path).resolve(); key = str(path)
        require(path.is_relative_to(ROOT) or path.is_relative_to(OLD_ROOT), 'Evidence path escapes explicit roots')
        require(key in self.refs and sha(path) == self.refs[key], 'Raw label/path SHA absent or changed: '+key)
        self.used[key] = self.refs[key]
        return read(path)

    def sealed_summary(self, folder, expected_seal, expected_protocol):
        folder = Path(folder).resolve(); seal = self.load(folder/'complete.json')
        require(self.refs[str(folder/'complete.json')] == expected_seal and seal.get('status') == 'complete'
                and seal.get('protocol_sha256') == expected_protocol, 'Source/branch original seal identity differs')
        require(seal['files'].get('summary.json') == self.refs.get(str(folder/'summary.json')), 'Summary SHA differs from its original seal')
        return self.load(folder/'summary.json')


def reconstruct(audited, config, stored_rows, evidence):
    require([r.get('planned_slot_id') for r in stored_rows] == IDS and len(stored_rows) == 100,
            'Full original source_records order is required')
    bounds = config['inputs']['sources']
    require(list(bounds) == IDS and config['tasks'] == list(TASKS), 'Config original source or task order differs')
    rows, scenes, labels, counts = [], set(), [], Counter()
    for row in stored_rows:
        identity = row['planned_slot_id']; b = bounds[identity]; no_cut = identity in COMMON
        require(row['status'] == 'complete' and row['artifact_audit_status'] == row['pairing_audit_status'] == 'passed',
                'Incomplete source audit')
        require(row['resolved_episode_id'] == b['resolved_episode_id'] == identity and row['task'] == b['task'] == identity.rsplit('__', 1)[0]
                and row['no_cut'] is no_cut and b['no_cut'] is no_cut and row['actual_cut'] == b['actual_cut'],
                'Source identity or original no-cut status differs')
        scene = (row['task'], row['scene_fingerprint'])
        require(scene not in scenes and row['scene_fingerprint'] == b['scene_fingerprint'], 'Repeated or changed physical scene')
        scenes.add(scene)
        old_collection = evidence.sealed_summary(b['collection_path'], b['collection_seal_sha256'], b['source_protocol_sha256'])
        new_path = ROOT/'collections/standalone_formal'/identity
        new_seal_sha = evidence.refs.get(str(new_path/'complete.json'))
        new_collection = evidence.sealed_summary(new_path, new_seal_sha, audited['protocol_sha256'])
        require(old_collection['case'] == new_collection['case'] == b['case']
                and old_collection['no_cut'] is no_cut and new_collection['no_cut'] is no_cut,
                'Collection source mapping differs')
        y = np.empty((8, 4), dtype=bool)
        if no_cut:
            original = evidence.sealed_summary(b['source_path'], b['source_seal_sha256'], b['source_protocol_sha256'])
            value = original['success']
            require(type(value) is bool and original['full_episode_outcome_available'] is True
                    and original['no_cut'] is True and original['actual_cut'] is None
                    and row['common_outcome'] == b['common_outcome'] == old_collection['common_outcome'] == new_collection['common_outcome'] == value
                    and old_collection['branch_records'] == new_collection['branch_records'] == [],
                    'Original no-alarm common terminal outcome differs')
            y[:] = value; counts['common_sources'] += 1
        else:
            require(row['common_outcome'] is None, 'Cut source cannot have an imputed common outcome')
            for collection, methods, old in ((old_collection, OLD, True), (new_collection, SOLO, False)):
                records = collection['branch_records']; keyed = {(r['method'], r['repeat']):r for r in records}
                require(len(keyed) == len(records) == len(methods)*4
                        and set(keyed) == {(m,r) for m in methods for r in range(4)}, 'Incomplete/duplicate physical label set')
                for method in methods:
                    for repeat in range(4):
                        ref = keyed[(method,repeat)]
                        base = OLD_ROOT/'rollouts/heldout/heldout_policy_v1' if old else ROOT/'rollouts/standalone_formal'
                        folder = base/identity/f"cut{b['actual_cut']:03d}"/method/f'repeat_{repeat}'
                        require(Path(ref['summary_path']).resolve() == folder/'summary.json', 'Wrong source/method/repeat summary path')
                        value = evidence.sealed_summary(folder, ref['seal_sha256'], b['source_protocol_sha256'] if old else audited['protocol_sha256'])
                        require(value['method'] == method and value['repeat'] == repeat and type(value['success']) is bool
                                and value['source_seal_sha256'] == b['source_seal_sha256']
                                and all(value[k] == ref[k] for k in ('success', 'budget_attempt', 'command_sha256')),
                                'Raw branch label or source identity differs from collection')
                        y[METHODS.index(method), repeat] = value['success']
                        counts['old_branch_summaries' if old else 'new_branch_summaries'] += 1
        require(set(row['outcomes']) == set(METHODS), 'Exactly eight arms required')
        for index, method in enumerate(METHODS):
            saved = np.asarray(row['outcomes'][method])
            require(saved.shape == (4,) and saved.dtype == np.dtype('bool') and np.array_equal(saved, y[index]),
                    'Audited label differs from independently reread raw source/branch outcome')
        rows.append(deepcopy(row)); labels.append(y)
    require(Counter(r['task'] for r in rows) == Counter({t:20 for t in TASKS})
            and counts == Counter(common_sources=2, old_branch_summaries=1960, new_branch_summaries=1176),
            'Full 100-source / 98-cut raw-label coverage required')
    return rows, np.stack(labels), dict(counts)


def compute(rows, labels):
    """Independent arithmetic, sharing the preregistered random-draw definition."""
    task = np.asarray([r['task'] for r in rows]); rng = np.random.default_rng(SEED)
    indices = np.concatenate([rng.choice(np.flatnonzero(task == t), (DRAWS,20), replace=True) for t in TASKS], axis=1)
    def group(selected, intervals=False):
        values = labels[selected]; n = len(values); counts = values.sum(axis=(0,2), dtype=np.int64)
        result = dict(sources=n, logical_outcomes_per_arm=n*4,
            success_counts={m:int(counts[j]) for j,m in enumerate(METHODS)},
            success_rates={m:float(counts[j]/(n*4)) for j,m in enumerate(METHODS)}, comparisons={})
        for candidate, baseline in PAIRS:
            a, b = values[:,candidate], values[:,baseline]
            deltas = (a.astype(np.int8)-b.astype(np.int8)).mean(axis=1)
            rescue, harm = int((a & ~b).sum()), int((~a & b).sum())
            c = dict(gain=(rescue-harm)/(n*4), paired_success_difference=rescue-harm, rescues=rescue, harms=harm,
                positive_sources=int((deltas>0).sum()), negative_sources=int((deltas<0).sum()), zero_sources=int((deltas==0).sum()))
            if intervals:
                means = deltas[indices].mean(axis=1)
                c['source_95ci'] = np.quantile(means, [.025,.975], method='linear').tolist()
                if (candidate,baseline) in PRIMARY:
                    c['source_bonferroni_98_333333ci'] = np.quantile(means, BONFERRONI, method='linear').tolist()
                    c['bonferroni_quantiles'] = BONFERRONI
                    c['adjusted_interval_supports_positive_gain'] = c['source_bonferroni_98_333333ci'][0] > 0
            result['comparisons'][METHODS[candidate]+'_minus_'+METHODS[baseline]] = c
        return result
    for index, row in enumerate(rows):
        row['paired_source_gains'] = {METHODS[a]+'_minus_'+METHODS[b]:
            float((labels[index,a].astype(np.int8)-labels[index,b].astype(np.int8)).mean()) for a,b in PAIRS}
    common = np.asarray([r['no_cut'] for r in rows])
    return dict(overall=group(np.ones(100,bool), True), per_task={t:group(task==t) for t in TASKS},
                alarm_conditioned=group(~common), no_cut_common_outcomes=group(common), per_source=rows)


def exact(first, second, path='statistics'):
    if isinstance(first, dict):
        require(isinstance(second,dict) and set(first)==set(second), 'Comparison key mismatch: '+path)
        return 1+sum(exact(v,second[k],path+'.'+k) for k,v in first.items())
    if isinstance(first, list):
        require(isinstance(second,list) and len(first)==len(second), 'Comparison length mismatch: '+path)
        return 1+sum(exact(a,b,f'{path}[{i}]') for i,(a,b) in enumerate(zip(first,second)))
    require(type(first) == type(second) and first == second, 'Exact comparison mismatch: '+path)
    return 1


def run(audit_path, output_path, expected_audit_seal=None):
    audit_path, output_path = Path(audit_path).resolve(), Path(output_path).resolve()
    require(audit_path == ROOT/'audits/standalone_v2', 'Only the fixed standalone_v2 formal audit is accepted')
    require(output_path.is_relative_to(ROOT/'independent_audits') and not output_path.exists(), 'New independent output directory required')
    code_sha = sha(__file__); sealed = verify_audit_seal(audit_path, expected_audit_seal)
    audited = read(audit_path/'result.json'); gate = audited.get('wave_gate', {})
    require(audited.get('status') == 'passed' and audited.get('role') == sealed['role']
            and audited.get('stage') == 'standalone_formal' and audited.get('primary_ids') == IDS
            and audited.get('completed_sources') == 100 and audited.get('reached_sources') == 98
            and audited.get('no_cut_sources') == 2 and audited.get('loaded_workers') == 32
            and gate.get('all_slots_complete') is True and gate.get('lifecycle_returncode') == 0
            and audited.get('expected_attempts') == 1274, 'Full formal audit/wave gate is not passed')
    require(canonical(IDS) == IDS_SHA, 'Independent registered IDs checksum differs')
    evidence = Evidence(audited['artifacts']); config_refs = [r for r in audited['artifacts'] if r['role']=='config']
    require(len(config_refs)==1 and config_refs[0]['sha256']==audited['config_sha256'], 'Unique original frozen config required')
    config = evidence.load(config_refs[0]['path'])
    require(config['analysis_approval']['protocol_sha256'] == audited['protocol_sha256'] == sealed['protocol_sha256'],
            'Audit/config protocol identity differs')
    rows, labels, coverage = reconstruct(audited, config, read(audit_path/'source_records.json'), evidence)
    calculated = compute(rows, labels); primary = audited['statistics']
    require(primary['methods'] == list(METHODS) and primary['primary_ids'] == IDS and primary['primary_ids_sha256'] == IDS_SHA
            and primary['source_denominator'] == 100 and primary['replicates'] == 4 and primary['logical_outcomes_per_arm'] == 400,
            'Frozen denominator/method order differs')
    for name,pairs in [('common_primary_comparisons',PRIMARY), ('secondary_comparisons',SECONDARY), ('reference_comparisons',REFERENCE)]:
        require(primary[name] == [METHODS[a]+'_minus_'+METHODS[b] for a,b in pairs], 'Frozen comparison family differs')
    bootstrap = primary['bootstrap']
    expected_bootstrap = dict(draws=DRAWS,seed=SEED,task_order=list(TASKS),source_order=IDS,quantile_method='linear',
        ordinary_quantiles=[.025,.975],primary_family_size=3,bonferroni_quantiles=BONFERRONI,adjusted_confidence=1-.05/3)
    require(all(bootstrap[k]==v for k,v in expected_bootstrap.items()), 'Frozen bootstrap rule differs')
    nodes = sum(exact(value,primary[key],key) for key,value in calculated.items())
    for path,digest in evidence.used.items():
        require(sha(path)==digest, 'Evidence changed during independent read')
    require(sha(__file__)==code_sha, 'Independent script changed during execution')
    result = dict(role='standalone_independent_raw_label_reaggregation_v1',status='passed',
        comparison=dict(exact=True,compared_nodes=nodes,float_tolerance=0,
            primary_audit_path=str(audit_path),primary_audit_seal_sha256=sha(audit_path/'complete.json'),
            primary_result_sha256=sha(audit_path/'result.json')),
        methods=list(METHODS),source_denominator=100,replicates=4,logical_outcomes_per_arm=400,
        coverage=coverage,bootstrap=expected_bootstrap,statistics=calculated,
        raw_evidence_sha256=evidence.used,code=dict(path=str(Path(__file__).resolve()),sha256=code_sha),
        runtime=dict(numpy=np.__version__,python=sys.version,executable=sys.executable),
        no_existing_summarize_imported=True,model_calls=0,simulator_calls=0,optimizer_updates=0,
        selection_seals_written=0,winner_selected=False,new_independent_heldout=False,
        limitations=['Previously revealed fixed cohort structure ablation; no new independent heldout or post-hoc winner selection.',
            'Raw binary labels and their audited paths/SHA are reread; full physical trajectories are not redundantly re-audited.',
            'Whole-source bootstrap jointly resamples all arms/repeats within task; primary Bonferroni intervals are approximate family control.'])
    output_path.mkdir(parents=True,exist_ok=False)
    for name,value in [('result.json',result)]:
        with (output_path/name).open('x') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    seal = dict(status='complete',role=result['role'],protocol_sha256=audited['protocol_sha256'],
        files={'result.json':sha(output_path/'result.json')},model_calls=0,simulator_calls=0,optimizer_updates=0)
    with (output_path/'complete.json').open('x') as stream:
        json.dump(seal,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    return dict(status='passed',path=str(output_path),seal_sha256=sha(output_path/'complete.json'),
                result_sha256=sha(output_path/'result.json'),exact=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',default=str(ROOT/'audits/standalone_v2'))
    parser.add_argument('--output',default=str(ROOT/'independent_audits/standalone_v2'))
    parser.add_argument('--audit-seal')
    args = parser.parse_args()
    print(json.dumps(run(args.audit,args.output,args.audit_seal),ensure_ascii=False))
