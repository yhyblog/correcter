"""CPU-only copy of accepted small code/metadata; never traverse model inputs."""
import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
CPU_TASK = 'A10_PV_AUTH_METADATA_CPU_V1'
OLD = B/'results/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1'
NEW = B/'results/A'/CPU_TASK
WORK = B/'work/A'/f'{CPU_TASK}_r1'
TASK = 'A10_PV_OFFLINE_PREFLIGHT_V2'
RELEASE = 'P10_A_PV_OFFLINE_PREFLIGHT_V2'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw)

def put(path, value):
    write(path, (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode())

def ref(path):
    raw = path.read_bytes()
    return dict(path=str(path), sha256=digest(raw), size_bytes=len(raw))

replacements = {
    'A10_PV_OFFLINE_PREFLIGHT_V1': TASK,
    'P10_A_PV_OFFLINE_PREFLIGHT_V1': RELEASE,
    'results/A/P10_PV_release_claims': 'results/A/P10_PV_V2_release_claims',
    'results/A/P10_PV_launcher_runs': 'results/A/P10_PV_V2_launcher_runs',
    'work/A/P10_PV_runtime_cache': 'work/A/P10_PV_V2_runtime_cache',
}
allowed_changed = {'core/contracts.py', 'launch.py', 'diagnostic.py'}
old_manifest = json.loads((OLD/'code/CODE_MANIFEST.json').read_text())
assert digest((OLD/'code/CODE_MANIFEST.json').read_bytes()) == '4e790e12efdcb133e5ae9aca2b797aa35455409d052aa3067a15be2b8fbc1ada'
diffs = []
patches = []
ast_checks = []
new_rows = []
for row in old_manifest['files']:
    rel = row['path']
    source = OLD/'code'/rel
    raw = source.read_bytes()
    assert len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], rel
    changed = raw
    if rel in allowed_changed:
        for a, b in replacements.items():
            changed = changed.replace(a.encode(), b.encode())
        old_ast, new_ast = ast.parse(raw), ast.parse(changed)
        class MapStrings(ast.NodeTransformer):
            def visit_Constant(self, node):
                if isinstance(node.value, str):
                    for a, b in replacements.items():
                        node.value = node.value.replace(a, b)
                return node
        assert ast.dump(MapStrings().visit(old_ast)) == ast.dump(new_ast), rel
        ast_checks.append(dict(path=rel, parsed=True, only_declared_string_substitutions=True))
        patches.extend(difflib.unified_diff(raw.decode().splitlines(True), changed.decode().splitlines(True), fromfile='old/code/'+rel, tofile='new/code/'+rel))
    assert (changed != raw) == (rel in allowed_changed), rel
    write(NEW/'code'/rel, changed)
    new_rows.append(dict(path=rel, sha256=digest(changed), size_bytes=len(changed)))
    diffs.append(dict(path='code/'+rel, old_sha256=digest(raw), new_sha256=digest(changed), old_size_bytes=len(raw), new_size_bytes=len(changed), byte_identical=raw==changed, classification='identity_path_literals_only' if raw!=changed else 'unchanged_source_bytes'))
new_manifest = copy.deepcopy(old_manifest)
new_manifest['root'] = str(NEW/'code')
new_manifest['files'] = new_rows
put(NEW/'code/CODE_MANIFEST.json', new_manifest)

for rel, expected in {
    'config/CONFIG.json': '109bfe6482e7491cb8ad6ef4821bf55b536f4d8f9a734fd0100e71ee516cd48b',
    'INPUT_MANIFEST.json': '706b2e94b543e404c7a3ce6baee88d1736c61cf2ea4e9e491643af95e1fc1fb0',
    'EXTERNAL_SOURCE_MANIFEST.json': '088c97a731211ccb51f989fe024fe608c1d005838c505d8335768788a75b768c',
}.items():
    raw = (OLD/rel).read_bytes()
    assert digest(raw) == expected
    write(NEW/rel, raw)
    diffs.append(dict(path=rel, old_sha256=expected, new_sha256=expected, old_size_bytes=len(raw), new_size_bytes=len(raw), byte_identical=True, classification='unchanged_config_or_manifest_bytes_no_referenced_input_read'))

command_rel = 'commands/run_proposed_pv_offline.sh'
old_command = (OLD/command_rel).read_bytes()
new_command = old_command.replace(str(OLD).encode(), str(NEW).encode())
assert new_command != old_command
write(NEW/command_rel, new_command)
(NEW/command_rel).chmod(0o555)
patches.extend(difflib.unified_diff(old_command.decode().splitlines(True), new_command.decode().splitlines(True), fromfile='old/'+command_rel, tofile='new/'+command_rel))
diffs.append(dict(path=command_rel, old_sha256=digest(old_command), new_sha256=digest(new_command), old_size_bytes=len(old_command), new_size_bytes=len(new_command), byte_identical=False, classification='package_root_only'))

identity = dict(
    campaign_id='corrector-sim-20260919', preparation_task_id=CPU_TASK,
    task_id=TASK, task_revision=1, node_role='A', release_id=RELEASE,
    owner_host='trial-303224955-trialrun-303224955-worker-0',
    wave_id='corrector-sim-20260919-A-PV-offline-V2-wave07',
    run_id='A10_PV_OFFLINE_PREFLIGHT_V2_r1_A_wave07',
    shard_id='A-PV-offline-V2-shelf-place-step0-cached-once',
    board_status='ready', released_status='released', template_status='UNAUTHORIZED_TEMPLATE',
    release_relative_path='releases/'+RELEASE+'.json', release_path=str(B/'releases'/(RELEASE+'.json')),
    package_directory=str(NEW), command_path=str(NEW/command_rel),
    claim_path=str(B/'results/A/P10_PV_V2_release_claims'/(RELEASE+'.json')),
    output_root=str(B/'results/A/P10_PV_V2_launcher_runs'),
    cache_root=str(B/'work/A/P10_PV_V2_runtime_cache'),
    task_brief='tasks/'+TASK+'.md',
    acknowledgement='receipts/A/'+TASK+'_ACK.json', result='receipts/A/'+TASK+'_RESULT.json',
    publication_is_authorization=False)
put(NEW/'proposal/IDENTITY.json', identity)
old_proposal = json.loads((OLD/'proposal/PROPOSAL.json').read_text())
p = copy.deepcopy(old_proposal)
p.update(proposal_id=TASK+'_proposal_r1', task_id=TASK, task_revision=identity['task_revision'], required_release_path=identity['release_path'])
for key, rel in {'config':'config/CONFIG.json','input_manifest':'INPUT_MANIFEST.json','external_sources':'EXTERNAL_SOURCE_MANIFEST.json','code_manifest':'code/CODE_MANIFEST.json','command':command_rel}.items():
    p[key] = ref(NEW/rel)
p['real_command'] = [identity['command_path'], 'NEW_RELEASE_JSON']
p['authorization_identity'] = ref(NEW/'proposal/IDENTITY.json')
put(NEW/'proposal/PROPOSAL.json', p)

release = copy.deepcopy(json.loads((OLD/'proposal/RELEASE_TEMPLATE.json').read_text()))
for key in ['campaign_id','task_id','task_revision','node_role','owner_host','release_id','wave_id','run_id','shard_id']:
    release[key] = identity[key]
release['status'] = identity['template_status']
release['proposal_sha256'] = ref(NEW/'proposal/PROPOSAL.json')['sha256']
for rk, pk in {'code_manifest_sha256':'code_manifest','input_manifest_sha256':'input_manifest','config_sha256':'config','external_source_manifest_sha256':'external_sources'}.items():
    release[rk] = p[pk]['sha256']
release['real_command'] = [identity['command_path'], identity['release_path']]
put(NEW/'proposal/RELEASE_TEMPLATE.json', release)

board = dict(id=identity['task_id'], owner=identity['node_role'], revision=identity['task_revision'], status=identity['board_status'], release=identity['release_relative_path'], dependencies=[CPU_TASK], dependency_outcome_required='CPU_metadata_package_accepted_and_independent_compute_release_published', brief=identity['task_brief'], wave_id=identity['wave_id'], run_id=identity['run_id'], shard_id=identity['shard_id'], acknowledgement=identity['acknowledgement'], expected_result=identity['result'])
put(NEW/'proposal/BOARD_TASK_TEMPLATE.json', board)
control = copy.deepcopy(json.loads((OLD/'proposal/CONTROL_REQUIRED.json').read_text()))
control.update(active_compute_release_id=identity['release_id'], active_compute_release=identity['release_relative_path'], active_compute_task_ids=[identity['task_id']], allowed_task_id_to_add=identity['task_id'], per_task_compute_limits={identity['task_id']:copy.deepcopy(p['resource_caps'])}, board_task=copy.deepcopy(board))
control['analysis_must'] = 'Publish this complete board_task with status ready (running accepted after ACK); release status released. Preserve all old closures. This requirements file and UNAUTHORIZED_TEMPLATE do not grant compute. Replace global and task caps exactly; do not inherit CPU zero Torch/model limits. Run the pure JSON publication checker before dispatch. Use the prepared V2 run/wave/shard identity consistently.'
put(NEW/'proposal/CONTROL_REQUIRED.json', control)

metadata_diff = []
for rel in ['code/CODE_MANIFEST.json','proposal/PROPOSAL.json','proposal/RELEASE_TEMPLATE.json','proposal/CONTROL_REQUIRED.json']:
    before, after = (OLD/rel).read_bytes(), (NEW/rel).read_bytes()
    diffs.append(dict(path=rel, old_sha256=digest(before), new_sha256=digest(after), old_size_bytes=len(before), new_size_bytes=len(after), byte_identical=before==after, classification='authorization_identity_path_manifest_metadata_only'))
    metadata_diff.extend(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True), fromfile='old/'+rel, tofile='new/'+rel))
allowed_proposal_changes = {'proposal_id','task_id','config','input_manifest','code_manifest','external_sources','command','real_command','required_release_path','authorization_identity'}
assert {k for k in set(p)|set(old_proposal) if p.get(k)!=old_proposal.get(k)} <= allowed_proposal_changes
invariants = {k:old_proposal[k]==p[k] for k in old_proposal if k not in allowed_proposal_changes}
assert all(invariants.values())
assert p['resource_caps']==release['resource_caps']==control['current_compute_limits']==control['per_task_compute_limits'][TASK]
assert board==control['board_task']
write(WORK/'RUNTIME_IDENTITY_PATH.diff', ''.join(patches).encode())
write(WORK/'AUTHORIZATION_METADATA.diff', ''.join(metadata_diff).encode())
put(NEW/'DIFF_MANIFEST.json', dict(source_package=str(OLD), new_package=str(NEW), files=diffs, code_file_count=len(new_rows), changed_runtime_files=sorted(allowed_changed), unchanged_code_files=sum(x['path'].startswith('code/') and x['path']!='code/CODE_MANIFEST.json' and x['byte_identical'] for x in diffs), added_authorization_files=['proposal/IDENTITY.json','proposal/BOARD_TASK_TEMPLATE.json','commands/check_publication_metadata_cpu.py'], copied_input_and_external_manifest_entries_not_read=True, old_package_mutations=0, large_weight_hashes=0))
put(WORK/'IDENTITY_CHANGE_STATIC_CHECKS.json', dict(status='passed', changed_runtime_AST=ast_checks, normalized_AST_equal=True, diagnostic_run_function_byte_identical=ast.get_source_segment((OLD/'code/diagnostic.py').read_text(),next(n for n in ast.parse((OLD/'code/diagnostic.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run'))==ast.get_source_segment((NEW/'code/diagnostic.py').read_text(),next(n for n in ast.parse((NEW/'code/diagnostic.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run')), unchanged_proposal_fields=invariants, caps_entries=len(p['resource_caps']), same_source_board_release_control=True, current_state_and_old_receipts_mutations=0, whole_algorithm_tests_run=0))
print(json.dumps(dict(status='prepared', package=str(NEW), code_files=len(new_rows), changed_runtime_files=sorted(allowed_changed), caps_entries=len(p['resource_caps']), proposal=ref(NEW/'proposal/PROPOSAL.json')),indent=2))
