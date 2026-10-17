"""Only new V4 identity/config publication checks; never run the real launcher."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

P = Path(__file__).resolve().parents[1]
B = P.parents[2]
W = B / 'work/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1_r1'
D = W / 'publication_fixture_v1'
D.mkdir(exist_ok=False)
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / 'code'))
import inheritance
from authorization import check_documents

def read(p):
    return json.loads(Path(p).read_text())

def write(p, value):
    with Path(p).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')

proposal = read(P / 'proposal/PROPOSAL.json')
proposal['_sha256'] = hashlib.sha256((P / 'proposal/PROPOSAL.json').read_bytes()).hexdigest()
control = read(P / 'proposal/CONTROL_TEMPLATE.json')
board = read(P / 'proposal/BOARD_TEMPLATE.json')
template = read(P / 'proposal/RELEASE_TEMPLATE.json')
assert template['status'] == 'UNAUTHORIZED_TEMPLATE'
release = copy.deepcopy(template)
release.update(status='released', synthetic=True, CPU_fixture_only=True, actual_authorization=False)
checks = []
for state in ['ready', 'running']:
    b = copy.deepcopy(board)
    b['tasks'][0]['status'] = state
    result = check_documents(control, b, release, proposal, proposal['owner_host'])
    assert result['status'] == 'PASS' and not result['grants_authorization']
    checks.append({'case': 'V4_' + state, 'status': 'PASS', 'result': result})

negative = []
wrong_board = copy.deepcopy(board)
wrong_board['tasks'][0]['status'] = 'released'
negative.append(('board_released_rejected', control, wrong_board, release))
negative.append(('unauthorized_template_rejected', control, board, template))
closed = copy.deepcopy(release)
closed['closed'] = True
negative.append(('closed_rejected', control, board, closed))
old_release = copy.deepcopy(release)
old_release['release_id'] = 'P11_A_COMMON_POOL_FIRST_PARENT_V3'
negative.append(('consumed_V3_identity_rejected', control, board, old_release))
old_path = copy.deepcopy(release)
old_path['paths']['claim'] = old_path['paths']['claim'].replace('_V4', '_V3')
negative.append(('old_claim_path_rejected', control, board, old_path))
for name, c, b, r in negative:
    try:
        check_documents(c, b, r, proposal, proposal['owner_host'])
    except ValueError as e:
        checks.append({'case': name, 'status': 'PASS', 'rejection': str(e)})
    else:
        raise AssertionError(name)

for name, doc in [('CONTROL_SYNTHETIC.json', control), ('BOARD_SYNTHETIC.json', board), ('RELEASE_SYNTHETIC_NOT_AUTHORIZATION.json', release)]:
    write(D / name, doc)
argv = ['bash', str(P / 'commands/check_publication_metadata.sh'), str(D / 'CONTROL_SYNTHETIC.json'),
        str(D / 'BOARD_SYNTHETIC.json'), str(D / 'RELEASE_SYNTHETIC_NOT_AUTHORIZATION.json')]
proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
(D / 'checker.stdout').write_text(proc.stdout)
(D / 'checker.stderr').write_text(proc.stderr)
assert proc.returncode == 0, proc.stderr
checker = json.loads(proc.stdout)
assert checker['status'] == 'PASS' and checker['observation_phase_contract']['observation_phases'] == 301
assert not checker['grants_authorization']
checks.append({'case': 'actual_JSON_publication_entry_with_real_CONFIG', 'status': 'PASS', 'argv': argv,
               'exit_code': proc.returncode, 'result': checker})

changed = ['authorization.py', 'runtime_engine.py', 'publication_check.py', 'observation_phase.py']
for name in changed:
    ast.parse((P / 'code' / name).read_text(), filename=name)
checks.append({'case': 'only_four_changed_python_AST_parse', 'status': 'PASS', 'files': changed})
for name in ['run_proposed_first_parent.sh', 'check_publication_metadata.sh']:
    r = subprocess.run(['bash', '-n', str(P / 'commands' / name)], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    checks.append({'case': 'shell_syntax_only_' + name, 'status': 'PASS', 'exit_code': 0})
paths = {k: dict(path=v, absent=not Path(v).exists() and not Path(v).is_symlink()) for k, v in proposal['paths'].items()}
assert all(v['absent'] for v in paths.values())
real_control = read(B / 'CONTROL.json')
assert real_control['revision'] == 43 and real_control['mode'] == 'prepare'
assert not real_control['formal_gpu_runs_enabled'] and not any(real_control['current_compute_limits'].values())
assert not (B / 'releases/P11_A_COMMON_POOL_FIRST_PARENT_V4.json').exists()
checks.append({'case': 'future_paths_and_release_absent_real_CONTROL_still_CPU_only', 'status': 'PASS', 'paths': paths})
write(P / 'CPU_METADATA_CHECKS.json', dict(status='PASS', synthetic=True, checks=checks, check_groups=len(checks),
    real_launcher_invocations=0, claims_created=0, holder_queries=0, large_weight_hashes=0,
    only_metadata_JSON_check_and_shell_syntax_executed=True))
print(json.dumps({'status': 'PASS', 'check_groups': len(checks), 'future_paths_absent': True,
                  'checker_output': checker, 'real_operations': 0}, ensure_ascii=False))
