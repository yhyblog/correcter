"""Registration, provenance and hard simulator budget for the small comparison."""
from __future__ import annotations

import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

from ac_tmil.ogg_research_v3.common import REPO, BASE, ROOT as V3, OGG, RG
from ac_tmil.ogg_research_v2.common import freeze, read, dump, save_arrays, seed_for, file_sha256

PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE / 'outputs/metaworld_small_20260916'
DOC = ROOT / 'report'
TEMPLATE = PACKAGE / 'configs/metaworld_small_20260916.json'
METHODS = ['replan', 'velocity_matched', 'direct_matched', 'post_matched', 'continue_old']
GENERATED_METHODS = METHODS[:4] + ['reverse_matched', 'random_matched', 'velocity_native', 'direct_native']
MATCHED = ['velocity_matched', 'direct_matched', 'post_matched', 'reverse_matched', 'random_matched']
REFERENCE = PACKAGE / 'results/reference_flow_20260916'
HARD_MAXIMUM = 700


def reserve_branch(kind, identity):
    """Count before simulation, including failed/repeated work and captures."""
    folder = ROOT / 'budget'
    folder.mkdir(parents=True, exist_ok=True)
    with Path('/tmp/corrector_metaworld_small_20260916_budget.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = folder / 'attempts.jsonl'
        count = sum(1 for _ in path.open()) if path.exists() else 0
        if count >= HARD_MAXIMUM:
            raise RuntimeError('Hard 700 simulator-attempt budget reached; do not extend this batch')
        row = dict(number=count+1, kind=kind, identity=str(identity), unix=time.time())
        with path.open('a') as stream:
            stream.write(json.dumps(row)+'\n')
        return row


def implementation_hashes():
    paths = (sorted((PACKAGE/'src/corrector').glob('*.py')) +
             sorted((PACKAGE/'experiments/metaworld_small').glob('*.py')) +
             sorted((PACKAGE/'tests').glob('test*.py')) +
             [PACKAGE/'scripts/run_metaworld_small.sh', TEMPLATE,
              PACKAGE/'experiments/metaworld_small/PROTOCOL.md',
              REPO/'scripts/run_recap_gpu_wave.py'])
    # The runtime adapter deliberately reuses the original environment stack.
    # Freeze that source as well, so it cannot silently change between stages.
    paths += sorted((REPO/'src/ac_tmil').rglob('*.py'))
    return {str(path): file_sha256(path) for path in paths}


def verify_code(hashes):
    for name, expected in hashes.items():
        assert file_sha256(Path(name)) == expected, name


def prepare():
    if (ROOT/'config.json').exists():
        return read(ROOT/'config.json')
    cfg = json.loads(TEMPLATE.read_text())
    assert cfg['methods'] == METHODS and cfg['budget']['hard_maximum'] == HARD_MAXIMUM
    counts = Counter(case['split'] for case in cfg['cases'])
    assert counts == {'preflight': 5, 'development': 15}
    assert cfg['replicates'] == 8 and cfg['preflight_replicates'] == 1
    seeds = [case['env_seed'] for case in cfg['cases']]
    assert len(set(seeds)) == 20 and not any(2026105000 <= seed < 2026105100 for seed in seeds)
    pattern = r'(?:__|"(?:env_seed|seed)"\s*:\s*)(?:' + '|'.join(map(str, seeds)) + r')(?:[^0-9]|$)'
    scan = subprocess.run([RG, '-l', '--glob', '*.json', pattern, str(REPO/'outputs')], capture_output=True, text=True)
    assert scan.returncode in (0, 1) and not scan.stdout, (scan.stdout+scan.stderr)[:1500]
    previous = json.loads((REFERENCE/'provenance/previous.json').read_text())
    for name, expected in previous['dependencies'].items():
        assert file_sha256(Path(name)) == expected, name
    cfg['created_unix'] = time.time()
    cfg['sources_collision_checked'] = True
    cfg['source_collision_audit'] = dict(command=scan.args, matches=[], seeds=seeds)
    cfg['reference_config_sha256'] = file_sha256(REFERENCE/'config.json')
    cfg['critic_ranking_sha256'] = file_sha256(PACKAGE/'assets/critic/ranking.json')
    freeze(ROOT/'config.json', cfg)
    freeze(ROOT/'provenance/previous.json', dict(dependencies=previous['dependencies'],
        reference=str(REFERENCE), reference_config_sha256=cfg['reference_config_sha256']))
    print(json.dumps(dict(status='prepared', root=str(ROOT), budget=cfg['budget'])), flush=True)
    return cfg


def cpu_check():
    """Run extracted-core tests and bitwise rebuild all reference candidate banks."""
    import numpy as np
    from corrector.candidates import construct
    read(ROOT/'config.json')
    process = subprocess.run([sys.executable, '-m', 'pytest', '-q', str(PACKAGE/'tests'),
                              str(PACKAGE/'experiments/metaworld_small/test_runner.py')],
                             cwd=PACKAGE, capture_output=True, text=True)
    (ROOT/'audits').mkdir(parents=True, exist_ok=True)
    (ROOT/'audits/cpu_pytest.log').write_text(process.stdout+process.stderr)
    if process.returncode:
        raise RuntimeError('CPU core tests failed: '+process.stdout[-3000:]+process.stderr[-1000:])
    cfg = json.loads((REFERENCE/'config.json').read_text())
    checked = []
    for packet in sorted((REFERENCE/'rollouts/development').glob('*/cut*/candidates')):
        generation = json.loads((packet/'generation.json').read_text())
        case = next(case for case in cfg['cases'] if case['case_id'] == generation['case_id'])
        with np.load(packet/'plans.npz') as archive:
            plans = {key: archive[key].copy() for key in archive.files}
        with np.load(packet/'directions.npz') as archive:
            direction = archive['post_internal_metric_direction'].copy()
        rebuilt, _ = construct(plans['replan'], plans['velocity_native'], plans['direct_native'], direction,
            seed_for(cfg['random_seed_namespace'], case['env_seed'], generation['step']), cfg['matching'])
        for method in GENERATED_METHODS:
            np.testing.assert_array_equal(plans[method], rebuilt[method])
        checked.append(generation['case_id'])
    assert len(checked) == 30
    dump(ROOT/'audits/cpu_checks.json', dict(status='passed', tests_exit_code=0,
        reference_candidate_banks_bit_identical=checked, code_hashes=implementation_hashes(),
        log_sha256=file_sha256(ROOT/'audits/cpu_pytest.log'), unix=time.time()))
    print(json.dumps(dict(status='passed', reference_banks=30, tests=process.stdout.strip())), flush=True)


def formal_freeze():
    cfg = read(ROOT/'config.json')
    assert not (ROOT/'rollouts/development').exists()
    cpu = json.loads((ROOT/'audits/cpu_checks.json').read_text())
    assert cpu['status'] == 'passed'
    verify_code(cpu['code_hashes'])
    preflight = json.loads((ROOT/'audits/preflight.json').read_text())
    assert preflight['status'] == 'passed'
    absent = not any((ROOT/'sources/single'/case['case_id']).exists()
                     for case in cfg['cases'] if case['split'] == 'development')
    assert absent
    freeze(ROOT/'formal_freeze.json', dict(unix=time.time(), config_sha256=file_sha256(ROOT/'config.json'),
        code_hashes=implementation_hashes(), preflight_audit_sha256=file_sha256(ROOT/'audits/preflight.json'),
        cpu_checks_sha256=file_sha256(ROOT/'audits/cpu_checks.json'),
        development_sources_absent=absent, preflight_outcomes_used_for_settings=False,
        settings_unchanged_from_preflight=True))
    print(json.dumps(dict(status='frozen', root=str(ROOT))), flush=True)


def launch(stage):
    read(ROOT/'config.json')
    cpu = json.loads((ROOT/'audits/cpu_checks.json').read_text())
    assert cpu['status'] == 'passed'
    verify_code(cpu['code_hashes'])
    if stage == 'development':
        frozen = read(ROOT/'formal_freeze.json')
        verify_code(frozen['code_hashes'])
    attempt = f'{stage}_{time.time_ns()}'
    execution = ROOT/'waves'/f'{attempt}_execution.json'
    freeze(execution, dict(stage=stage, workers_per_gpu=1, total_workers=8,
        config_sha256=file_sha256(ROOT/'config.json'), code_hashes=implementation_hashes(),
        worker_logs=str(ROOT/'logs'/attempt/'workers'), checks=str(ROOT/'checks'/attempt)))
    spec = ROOT/'waves'/f'{attempt}.json'
    jobs = [dict(devices=[rank], command=['bash', str(PACKAGE/'scripts/run_metaworld_small.sh'),
        'collection', '--rank', str(rank), '--execution', str(execution)]) for rank in range(8)]
    dump(spec, dict(jobs=jobs, hold_idle=False, log_root=str(ROOT/'logs'/attempt)))
    print(spec, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'cpu-check', 'freeze', 'launch'])
    parser.add_argument('--stage', choices=['preflight', 'development'], default='preflight')
    args = parser.parse_args()
    {'prepare': prepare, 'cpu-check': cpu_check, 'freeze': formal_freeze,
     'launch': lambda: launch(args.stage)}[args.action]()
