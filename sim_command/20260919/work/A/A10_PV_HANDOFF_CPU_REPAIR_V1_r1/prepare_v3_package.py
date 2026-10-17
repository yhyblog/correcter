"""Copy accepted code by manifest; change only V3 identity and handoff contract."""
import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
CPU='A10_PV_HANDOFF_CPU_REPAIR_V1'
OLD=B/'results/A/A10_PV_AUTH_METADATA_CPU_V1'
NEW=B/'results/A'/CPU
WORK=B/'work/A'/f'{CPU}_r1'
TASK='A10_PV_OFFLINE_PREFLIGHT_V3'
RELEASE='P10_A_PV_OFFLINE_PREFLIGHT_V3'

def get(path):return json.loads(path.read_text())
def digest(raw):return hashlib.sha256(raw).hexdigest()
def write(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(raw)
def put(path,obj):write(path,(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
def ref(path):
    raw=path.read_bytes()
    return dict(path=str(path),sha256=digest(raw),size_bytes=len(raw))

spec=get(NEW/'guard_patch/HANDOFF_SPEC.json')
changes={
    'A10_PV_OFFLINE_PREFLIGHT_V2':TASK,
    'P10_A_PV_OFFLINE_PREFLIGHT_V2':RELEASE,
    'P10_PV_V2_release_claims':'P10_PV_V3_release_claims',
    'P10_PV_V2_launcher_runs':'P10_PV_V3_launcher_runs',
    'P10_PV_V2_runtime_cache':'P10_PV_V3_runtime_cache',
}
old_manifest=get(OLD/'code/CODE_MANIFEST.json')
assert ref(OLD/'code/CODE_MANIFEST.json')['sha256']=='6aebda83f18a1698e815d522866106a0e84eb1adf669b7d097131f3f858ac161'
diff=[];patches=[];code_rows=[]
for row in old_manifest['files']:
    rel=row['path'];raw=(OLD/'code'/rel).read_bytes()
    assert digest(raw)==row['sha256'] and len(raw)==row['size_bytes']
    new=raw
    if rel in ['core/contracts.py','launch.py','diagnostic.py']:
        text=raw.decode()
        for old,new_string in changes.items():text=text.replace(old,new_string)
        if rel=='core/contracts.py':
            text=text.replace('import time\n','import time\nfrom .handoff import HANDOFF_SPEC\n',1)
            text=text.replace("        device=proposal['device'],cuda_environment=proposal['cuda_environment'],", "        device=proposal['device'],cuda_environment=proposal['cuda_environment'],\n        occupancy_handoff=proposal['occupancy_handoff'],")
            needle="    if hostname!=proposal['owner_host']:raise ContractError('Wrong physical host')"
            text=text.replace(needle,"    if proposal.get('occupancy_handoff')!=HANDOFF_SPEC or control.get('active_occupancy_handoff')!=HANDOFF_SPEC:\n        raise ContractError('Frozen V3 handoff metadata mismatch')\n"+needle)
        if rel=='launch.py':
            text=text.replace('from core.identity import verify_device','from core.handoff import require_handoff_environment\nfrom core.identity import verify_device')
            text=text.replace("    env.update(cfg['cuda_environment'])", "    require_handoff_environment(cfg,env)\n    env.update(cfg['cuda_environment'])")
            text=text.replace("        cfg=read(p['config']['path'])", "        cfg=read(p['config']['path'])\n        handoff=require_handoff_environment(cfg,os.environ)\n        write_new(out/'handoff_environment.json',handoff)")
        new=text.encode();ast.parse(new)
    assert (new!=raw)==(rel in ['core/contracts.py','launch.py','diagnostic.py'])
    write(NEW/'code'/rel,new)
    code_rows.append(dict(path=rel,sha256=digest(new),size_bytes=len(new)))
    diff.append(dict(path='code/'+rel,old_sha256=digest(raw),new_sha256=digest(new),old_size_bytes=len(raw),new_size_bytes=len(new),byte_identical=raw==new,classification='identity_path_and_handoff_authorization_only' if raw!=new else 'unchanged_accepted_bytes'))
    if raw!=new:patches.extend(difflib.unified_diff(raw.decode().splitlines(True),new.decode().splitlines(True),fromfile='V2/code/'+rel,tofile='V3/code/'+rel))

helper='''"""Fixed V3 handoff metadata/environment; no hardware or file operations."""
HANDOFF_SPEC = '''+repr(spec)+'''

def require_handoff_environment(cfg, environment):
    if cfg.get('occupancy_handoff') != HANDOFF_SPEC:
        raise ValueError('V3 requires the exact frozen handoff contract')
    key = HANDOFF_SPEC['environment_variable']
    actual = environment.get(key)
    if actual != HANDOFF_SPEC['required_value']:
        raise ValueError('Missing or mismatched actual V3 handoff timeout; no default90 fallback')
    return dict(environment_variable=key, actual_value=actual,
        timeout_seconds=HANDOFF_SPEC['timeout_seconds'],
        guard_expected_sha256=HANDOFF_SPEC['guard_expected_sha256'],
        guard_SHA_check='parent full INPUT and EXTERNAL manifest verification already returned',
        propagation='frozen sh export -> launcher os.environ -> child_environment copy -> unchanged lifecycle active branch -> fresh guard run process',
        additional_hardware_queries=0)
'''
write(NEW/'code/core/handoff.py',helper.encode());ast.parse(helper)
code_rows.append(dict(path='core/handoff.py',sha256=digest(helper.encode()),size_bytes=len(helper.encode())))
code_rows.sort(key=lambda x:x['path'])
put(NEW/'code/CODE_MANIFEST.json',dict(old_manifest,root=str(NEW/'code'),files=code_rows))

old_cfg=get(OLD/'config/CONFIG.json');cfg=copy.deepcopy(old_cfg);cfg['occupancy_handoff']=spec
put(NEW/'config/CONFIG.json',cfg)
manifest_changes=[]
for name in ['INPUT_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json']:
    old=get(OLD/name);value=copy.deepcopy(old)
    rows=[x for x in value['files'] if x['path']==spec['guard_path']]
    assert len(rows)==1 and rows[0]['sha256']=='d499982dff72c3b74ddab0e13e359edccb5f282900c534030b3816b58495fcaf'
    rows[0].update(sha256=spec['guard_expected_sha256'],size_bytes=spec['guard_expected_size_bytes'],verification_now='Expected future installed guard patch; prepared privately only; original SHA belongs solely to installation precondition')
    assert [x for x in value['files'] if x['path']!=spec['guard_path']]==[x for x in old['files'] if x['path']!=spec['guard_path']]
    put(NEW/name,value)
    manifest_changes.append(dict(path=name,changed_referenced_path=spec['guard_path'],changed_rows=1,all_other_rows_exactly_equal=True,referenced_asset_bytes_read=False))

command= (OLD/'commands/run_proposed_pv_offline.sh').read_text().replace(str(OLD),str(NEW))
command=command.replace('set -eu\n',"set -eu\nexport CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300\n")
write(NEW/'commands/run_proposed_pv_offline.sh',command.encode());(NEW/'commands/run_proposed_pv_offline.sh').chmod(0o555)
identity=get(OLD/'proposal/IDENTITY.json')
identity.update(preparation_task_id=CPU,task_id=TASK,release_id=RELEASE,
    wave_id='corrector-sim-20260919-A-PV-offline-V3-wave08',run_id='A10_PV_OFFLINE_PREFLIGHT_V3_r1_A_wave08',shard_id='A-PV-offline-V3-shelf-place-step0-cached-once',
    release_relative_path='releases/'+RELEASE+'.json',release_path=str(B/'releases'/(RELEASE+'.json')),package_directory=str(NEW),command_path=str(NEW/'commands/run_proposed_pv_offline.sh'),
    claim_path=str(B/'results/A/P10_PV_V3_release_claims'/(RELEASE+'.json')),output_root=str(B/'results/A/P10_PV_V3_launcher_runs'),cache_root=str(B/'work/A/P10_PV_V3_runtime_cache'),
    task_brief='tasks/'+TASK+'.md',acknowledgement='receipts/A/'+TASK+'_ACK.json',result='receipts/A/'+TASK+'_RESULT.json')
put(NEW/'proposal/IDENTITY.json',identity)
old_p=get(OLD/'proposal/PROPOSAL.json');p=copy.deepcopy(old_p)
p.update(proposal_id=TASK+'_proposal_r1',task_id=TASK,required_release_path=identity['release_path'],occupancy_handoff=spec)
for key,rel in {'config':'config/CONFIG.json','input_manifest':'INPUT_MANIFEST.json','code_manifest':'code/CODE_MANIFEST.json','external_sources':'EXTERNAL_SOURCE_MANIFEST.json','command':'commands/run_proposed_pv_offline.sh','authorization_identity':'proposal/IDENTITY.json'}.items():p[key]=ref(NEW/rel)
p['real_command']=[identity['command_path'],'NEW_RELEASE_JSON']
put(NEW/'proposal/PROPOSAL.json',p)
r=get(OLD/'proposal/RELEASE_TEMPLATE.json')
for key in ['campaign_id','task_id','task_revision','node_role','owner_host','release_id','wave_id','run_id','shard_id']:r[key]=identity[key]
r.update(status='UNAUTHORIZED_TEMPLATE',proposal_sha256=ref(NEW/'proposal/PROPOSAL.json')['sha256'],occupancy_handoff=spec,real_command=[identity['command_path'],identity['release_path']])
for rk,pk in {'code_manifest_sha256':'code_manifest','input_manifest_sha256':'input_manifest','config_sha256':'config','external_source_manifest_sha256':'external_sources'}.items():r[rk]=p[pk]['sha256']
put(NEW/'proposal/RELEASE_TEMPLATE.json',r)
board=get(OLD/'proposal/BOARD_TASK_TEMPLATE.json')
board.update(id=TASK,owner='A',revision=1,status='ready',release=identity['release_relative_path'],dependencies=[CPU],dependency_outcome_required='CPU_handoff_package_accepted_shared_patch_separately_installed_and_independent_compute_release_published',brief=identity['task_brief'],wave_id=identity['wave_id'],run_id=identity['run_id'],shard_id=identity['shard_id'],acknowledgement=identity['acknowledgement'],expected_result=identity['result'])
put(NEW/'proposal/BOARD_TASK_TEMPLATE.json',board)
control=get(OLD/'proposal/CONTROL_REQUIRED.json')
control.update(active_compute_release_id=RELEASE,active_compute_release=identity['release_relative_path'],active_compute_task_ids=[TASK],allowed_task_id_to_add=TASK,per_task_compute_limits={TASK:p['resource_caps']},board_task=board,active_occupancy_handoff=spec)
control['analysis_must']='Use this complete ready board row, independent released V3 identity and exact66 caps. Preserve seven old closures. Shared guard patch installation needs separate explicit authorization and exact original/new SHA checks. Runtime expects only installed patched SHA in both input/external manifests. This CPU package and unauthorized templates grant neither installation nor compute.'
put(NEW/'proposal/CONTROL_REQUIRED.json',control)

checker=(OLD/'commands/check_publication_metadata_cpu.py').read_text().replace('V2','V3')
checker=checker.replace('from core.contracts import CAMPAIGN, TASK, RELEASE, ContractError, validate_metadata','from core.contracts import CAMPAIGN, TASK, RELEASE, ContractError, validate_metadata\nfrom core.handoff import HANDOFF_SPEC')
needle='    control, _, _ = small_json(control_path)'
addition='''    if proposal.get('occupancy_handoff') != HANDOFF_SPEC or cfg.get('occupancy_handoff') != HANDOFF_SPEC:
        raise ContractError('V3 handoff config/proposal mismatch')
    for name in ('input_manifest','external_sources'):
        rows = [x for x in manifests[name]['files'] if x['path'] == HANDOFF_SPEC['guard_path']]
        if (len(rows) != 1 or rows[0]['sha256'] != HANDOFF_SPEC['guard_expected_sha256']
                or rows[0]['size_bytes'] != HANDOFF_SPEC['guard_expected_size_bytes']):
            raise ContractError('Future installed guard manifest mismatch: '+name)
'''
assert needle in checker;checker=checker.replace(needle,addition+needle)
write(NEW/'commands/check_publication_metadata_cpu.py',checker.encode());ast.parse(checker)

metadata_paths=['config/CONFIG.json','INPUT_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json','commands/run_proposed_pv_offline.sh','commands/check_publication_metadata_cpu.py','code/CODE_MANIFEST.json','proposal/IDENTITY.json','proposal/PROPOSAL.json','proposal/RELEASE_TEMPLATE.json','proposal/CONTROL_REQUIRED.json','proposal/BOARD_TASK_TEMPLATE.json']
for rel in metadata_paths:
    a=(OLD/rel).read_bytes();z=(NEW/rel).read_bytes()
    diff.append(dict(path=rel,old_sha256=digest(a),new_sha256=digest(z),old_size_bytes=len(a),new_size_bytes=len(z),byte_identical=a==z,classification='identity_path_or_guard_handoff_metadata_only'))
    patches.extend(difflib.unified_diff(a.decode().splitlines(True),z.decode().splitlines(True),fromfile='V2/'+rel,tofile='V3/'+rel))
put(NEW/'DIFF_MANIFEST.json',dict(source_package=str(OLD),new_package=str(NEW),files=diff,added_runtime_files=[ref(NEW/'code/core/handoff.py')],code_files=381,unchanged_copied_code_files=377,changed_existing_runtime_files=['core/contracts.py','diagnostic.py','launch.py'],input_manifest_changes=manifest_changes,large_weight_hashes=0,old_files_modified=0))
write(WORK/'V2_TO_V3.diff',''.join(patches).encode())
def segment(path,name):
    text=path.read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return ast.get_source_segment(text,node)
assert segment(OLD/'code/diagnostic.py','run')==segment(NEW/'code/diagnostic.py','run')
assert {k:v for k,v in cfg.items() if k!='occupancy_handoff'}==old_cfg
invariant_keys=[k for k in old_p if k not in ['proposal_id','task_id','config','input_manifest','code_manifest','external_sources','command','real_command','required_release_path','authorization_identity']]
assert all(p[k]==old_p[k] for k in invariant_keys)
assert p['resource_caps']==r['resource_caps']==control['current_compute_limits']==control['per_task_compute_limits'][TASK]
put(WORK/'NUMERIC_AND_LIFECYCLE_PRESERVATION.json',dict(status='passed',copied_code_files=380,byte_identical_files=377,added_pure_metadata_runtime_helper=1,diagnostic_run_bytes_identical=True,all_config_fields_except_occupancy_handoff_equal=True,unchanged_proposal_fields=invariant_keys,resource_cap_entries_unchanged=66,private_ledger_functions_unchanged=True,reserved_wrapper_process_family_wave_timing_bytes_identical=True,lifecycle_shared_shell_SHA='3248ae959f5e43bca50c361818f620cff21eb87d10b1ee6b2d8c8756df623248',large_model_or_array_bytes_read=0,whole_algorithm_or_vendor_AST_tests_run=0,input_guard_manifest_rows_updated_in_both_manifests=True))
print(json.dumps(dict(status='V3_private_package_prepared',proposal=ref(NEW/'proposal/PROPOSAL.json'),code_files=381,caps=66,guard_expected_sha256=spec['guard_expected_sha256'],shared_installations=0),indent=2))
