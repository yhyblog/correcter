"""CPU-only snapshot diff, small-source hashes, and UNAUTHORIZED V2 metadata."""
from pathlib import Path
import ast,copy,difflib,hashlib,json,subprocess
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
O=B/'results/A/A10_CAUSAL_C10_CPU_V1';P=B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1'
W=B/'work/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1_r1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),realpath=str(p.resolve()),sha256=sha(p),size_bytes=p.stat().st_size)
def put(p,v):
    with p.open('x') as f:f.write(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def read(p):return json.loads(p.read_text())
def astmap(p,cls=None):
    body=ast.parse(p.read_text()).body
    if cls:body=next(n.body for n in body if isinstance(n,ast.ClassDef) and n.name==cls)
    return {n.name:ast.dump(n,include_attributes=False) for n in body if isinstance(n,ast.FunctionDef)}
old_manifest=read(O/'code/CODE_MANIFEST.json');old_index={r['path']:r for r in old_manifest['files']}
newfiles=sorted(p for p in (P/'code').rglob('*') if p.is_file())
assert all(p.suffix not in {'.pyc','.pt','.safetensors','.bin','.npy','.npz'} and p.stat().st_size<4*1024*1024 for p in newfiles)
rows=[dict(path=str(p.relative_to(P/'code')),sha256=sha(p),size_bytes=p.stat().st_size) for p in newfiles]
assert set(old_index).issubset({r['path'] for r in rows})
changed=[];same=[];lineage=[];patch=[]
reasons={
 'causal_contract.py':'Remove only duplicate branch payload on branch_start; unchanged controller algorithm.',
 'runtime_engine.py':'Construct shared recorder and delegate emit; all numeric/environment methods unchanged.',
 'core/event_recorder.py':'New stdlib production recorder; protected identities; serialization before write and ID commit.',
 'core/failure_evidence.py':'New stdlib live traceback and stage evidence helpers; exclusive files, no historical reconstruction.',
 'diagnostic.py':'New V2 output identity; capture primary/cleanup/validation exceptions with branch and known stage.',
 'launch.py':'New V2 output/cache identity; live exception capture, with restoration failure separate from primary lifecycle failure.',
 'native/native_egl.py':'Only capture original live cleanup exception traceback; preserve existing error aliases and all graphics calls.',
 'core/contracts.py':'Only V2 task/release/claim identity substitutions.'}
for row in rows:
    rel=row['path'];n=P/'code'/rel;o=O/'code'/rel
    origin=ref(o) if rel in old_index else None
    if origin:assert origin['sha256']==old_index[rel]['sha256']
    relation='byte_identical' if origin and row['sha256']==origin['sha256'] else 'new' if not origin else 'modified'
    lineage.append(dict(new=ref(n),origin=origin,relationship=relation))
    if relation=='byte_identical':same.append(rel)
    else:
        assert rel in reasons,rel
        changed.append(dict(relative_path='code/'+rel,old=origin,new=ref(n),reason=reasons[rel]))
        patch.extend(difflib.unified_diff(o.read_text().splitlines(True) if origin else [],n.read_text().splitlines(True),fromfile=str(o) if origin else '/dev/null',tofile=str(n)))
assert set(reasons)=={x['relative_path'][5:] for x in changed}
copied=['config/CONFIG.json','INPUT_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json','proposal/RESOURCE_BUDGET.json']
for name in copied:assert (P/name).read_bytes()==(O/name).read_bytes()
numeric=['corrector/'+x+'.py' for x in ['actions','critic','guidance','radii','raw_commands','solo']]
frozen=numeric+['numeric_setup.py','budget.py','feature_path.py','dg_models.py','reserved.py','core/wave_timing.py','core/process_family.py','core/handoff.py','native/initialization.py','native/graphics_contract.py','publication_check.py']
for rel in frozen:assert rel in same,rel
oldmethods=astmap(O/'code/runtime_engine.py','Engine');newmethods=astmap(P/'code/runtime_engine.py','Engine')
assert set(oldmethods)==set(newmethods)
unchanged_methods=[k for k in oldmethods if k not in {'__init__','emit'}]
assert all(oldmethods[k]==newmethods[k] for k in unchanged_methods)
oldnative=astmap(O/'code/native/native_egl.py');newnative=astmap(P/'code/native/native_egl.py')
assert oldnative==newnative
oldnative_methods=astmap(O/'code/native/native_egl.py','NativeEGL');newnative_methods=astmap(P/'code/native/native_egl.py','NativeEGL')
assert all(oldnative_methods[k]==newnative_methods[k] for k in oldnative_methods if k!='close')
oldcontroller=(O/'code/causal_contract.py').read_text()
assert (P/'code/causal_contract.py').read_text()==oldcontroller.replace("engine.emit('branch_start',branch=branch,", "engine.emit('branch_start',")
oldcontracts=(O/'code/core/contracts.py').read_text()
assert (P/'code/core/contracts.py').read_text()==oldcontracts.replace('A10_CAUSAL_C10_PREFLIGHT_V1','A10_CAUSAL_C10_PREFLIGHT_V2').replace('P10_A_CAUSAL_C10_PREFLIGHT_V1','P10_A_CAUSAL_C10_PREFLIGHT_V2').replace('P10_CAUSAL_C10_V1','P10_CAUSAL_C10_V2')
for name in ['child_environment','branch_evidence']:
    assert astmap(O/'code/launch.py')[name]==astmap(P/'code/launch.py')[name]
changedpy=[P/x['relative_path'] for x in changed]
for path in changedpy+[P/'cpu_checks/check_events.py']:ast.parse(path.read_text(),filename=str(path))
shell=subprocess.run(['bash','-n',str(P/'commands/run_proposed_causal_c10.sh')],capture_output=True,text=True)
assert shell.returncode==0,shell.stderr
assert (P/'commands/run_proposed_causal_c10.sh').read_text()==(O/'commands/run_proposed_causal_c10.sh').read_text().replace(str(O),str(P))
put(W/'STATIC_FREEZE_PROOF.json',dict(status='PASS',scope='changed AST and source identity only',changed_AST_files=[str(p) for p in changedpy],
    test_AST=str(P/'cpu_checks/check_events.py'),code_files=len(rows),changed_or_added_code_files=len(changed),unchanged_code_files=len(same),
    byte_identical_required_sources=frozen,byte_identical_data_manifests=copied,
    unchanged_runtime_engine_methods=unchanged_methods,UUID_parser_unchanged=True,all_native_methods_except_cleanup_unchanged=True,
    all_111_caps_byte_identical=True,timeout_and_lifecycle_sources_byte_identical=True,
    shell_syntax=dict(command=['bash','-n',str(P/'commands/run_proposed_causal_c10.sh')],returncode=shell.returncode,stdout=shell.stdout,stderr=shell.stderr),
    large_weights_hashed=0,actual_imports='standard library only',real_compute=0))
put(P/'code/CODE_MANIFEST.json',dict(schema='private_code_snapshot_v1',files=rows))
with (P/'MINIMAL_PATCH.diff').open('x') as f:f.writelines(patch)
put(P/'DIFF_MANIFEST.json',dict(schema='minimal_causal_event_repair_diff_v1',old_package=str(O),new_package=str(P),
    changed_code=changed,unchanged_code_count=len(same),removed_files=[],
    command=dict(old=ref(O/'commands/run_proposed_causal_c10.sh'),new=ref(P/'commands/run_proposed_causal_c10.sh'),reason='Only new private package root; explicit 300 handoff unchanged'),
    unchanged_inputs=[dict(old=ref(O/n),new=ref(P/n)) for n in copied],
    patch=ref(P/'MINIMAL_PATCH.diff'),proof=ref(W/'STATIC_FREEZE_PROOF.json'),
    added_row_metadata='synthetic recorder-owned scope flag; false in production, true in CPU fixtures; protected from payload override',
    exception_scope='Existing diagnostic/launcher handlers plus inner lifecycle preservation before restoration cleanup; original graphics cleanup error captured at catch',
    numeric_changes=False,old_artifacts_modified=False,shared_installations=0))
put(P/'INTEGRATION_MANIFEST.json',dict(schema='private_new_integration_lineage_v1',files=lineage,validated_whole_runtime=False,
    principal_changes='event recorder/controller and live traceback evidence only; independent V2 identity',
    source_packages=[str(O)],source_integration=ref(O/'INTEGRATION_MANIFEST.json'),diff=ref(P/'DIFF_MANIFEST.json'),
    public_interface_v1_modified=False,shared_guard_override=False))

oldp=read(O/'proposal/PROPOSAL.json');proposal=copy.deepcopy(oldp)
identity=dict(task_id='A10_CAUSAL_C10_PREFLIGHT_V2',task_revision=1,release_id='P10_A_CAUSAL_C10_PREFLIGHT_V2',node_role='A',
    run_id='A10_CAUSAL_C10_PREFLIGHT_V2_r1_A_wave10',wave_id='A_wave10_causal_C10',shard_id='A_shelfplace_C10_V2')
future_release=B/'releases'/(identity['release_id']+'.json')
paths=dict(release=str(future_release),claim=str(B/'results/A/P10_CAUSAL_C10_V2_release_claims'/(identity['release_id']+'.json')),
    output=str(B/'results/A/P10_CAUSAL_C10_V2_launcher_runs'/identity['run_id']),
    cache=str(B/'work/A/P10_CAUSAL_C10_V2_runtime_cache'/identity['run_id']))
assert not any(Path(x).exists() for x in paths.values())
put(P/'proposal/IDENTITY.json',identity)
put(P/'proposal/PATHS.json',dict(status='UNAUTHORIZED_TEMPLATE',paths=paths,read_only_absence_check=True,all_absent=True,created_runtime_paths=[]))
proposal.update(proposal_id='CAUSAL_C10_A_NATIVE_INDEPENDENT_REPLAY_V2',task_id=identity['task_id'],authorization_identity=identity,
    cwd=str(P),required_release_path=str(future_release),
    real_command=['bash',str(P/'commands/run_proposed_causal_c10.sh'),str(future_release)])
for key,path in [('config','config/CONFIG.json'),('input_manifest','INPUT_MANIFEST.json'),('external_sources','EXTERNAL_SOURCE_MANIFEST.json'),
    ('code_manifest','code/CODE_MANIFEST.json'),('integration_manifest','INTEGRATION_MANIFEST.json'),('budget','proposal/RESOURCE_BUDGET.json'),('command','commands/run_proposed_causal_c10.sh')]:proposal[key]=ref(P/path)
proposal['event_repair']=dict(scope='single duplicate branch removal, protected recorder identity, live primary/cleanup traceback',
    old_runtime_stack_backfilled=False,actual_old_failure='9 model initializations and 1 language embedding; no environment/cut; technical failure only',
    diff=ref(P/'DIFF_MANIFEST.json'),new_runtime_paths=paths)
for key in ['resource_caps','branch_caps','branch_numeric_caps','launcher_caps','source','device','cuda_environment','occupancy_handoff','occupancy',
    'timeout_seconds','kill_grace_seconds','timeout_scope','timeout_outside','branch_order','branch_attempts_max','cost_semantics','resource_estimates']:
    assert proposal[key]==oldp[key],key
assert len(proposal['resource_caps'])==111
put(P/'proposal/PROPOSAL.json',proposal)
release=copy.deepcopy(read(O/'proposal/RELEASE_TEMPLATE.json'))
release.update(status='UNAUTHORIZED_TEMPLATE',task_id=identity['task_id'],release_id=identity['release_id'],
    authorization_identity=identity,run_id=identity['run_id'],wave_id=identity['wave_id'],shard_id=identity['shard_id'],
    proposal_sha256=sha(P/'proposal/PROPOSAL.json'),code_manifest_sha256=proposal['code_manifest']['sha256'],
    input_manifest_sha256=proposal['input_manifest']['sha256'],config_sha256=proposal['config']['sha256'],external_source_manifest_sha256=proposal['external_sources']['sha256'])
put(P/'proposal/RELEASE_TEMPLATE.json',release)
board=dict(id=identity['task_id'],owner='A',status='ready',revision=1,dependencies=['A10_CAUSAL_EVENT_CPU_REPAIR_V1'],
    brief='tasks/'+identity['task_id']+'.md',release='releases/'+identity['release_id']+'.json',expected_result='receipts/A/'+identity['task_id']+'_RESULT.json')
put(P/'proposal/BOARD_TASK_TEMPLATE.json',board)
current=read(B/'CONTROL.json')
fields=dict(campaign_id=proposal['campaign_id'],mode='preflight',formal_gpu_runs_enabled=True,stop_requested=False,
    allowed_task_ids=[identity['task_id']],active_compute_release_id=identity['release_id'],active_compute_release='releases/'+identity['release_id']+'.json',
    active_compute_task_ids=[identity['task_id']],active_occupancy_handoff=proposal['occupancy_handoff'],
    current_compute_limits=proposal['resource_caps'],per_task_compute_limits={identity['task_id']:proposal['resource_caps']},closed_compute_releases=current['closed_compute_releases'])
put(P/'proposal/CONTROL_REQUIRED.json',dict(status='UNAUTHORIZED_TEMPLATE',meaning='proposed fields only; not written to current CONTROL',fields=fields,
    preserve_nine_closed_releases=True,all_prior_unused_caps_void=True))
put(W/'BUDGET_AND_IDENTITY_PROOF.json',dict(status='PASS',future_authorized=False,caps_count=111,
    old_budget=ref(O/'proposal/RESOURCE_BUDGET.json'),new_budget=ref(P/'proposal/RESOURCE_BUDGET.json'),
    resource_caps_identical=True,branch_caps_identical=True,source_and_seeds_identical=True,numerical_config_identical=True,
    native_initialization_and_graphics_caps_identical=True,per_child_timeout_seconds=1800,kill_grace_seconds=30,handoff_nominal_seconds=300,
    lifecycle='unchanged reserved.py/core wave/process/handoff bytes; same group and lock; no holder operation executed',
    identity=identity,paths_absent=paths,compute_claims=0,actual_launches=0))
print(json.dumps(dict(status='FROZEN',code_files=len(rows),changed=len(changed),unchanged=len(same),proposal=ref(P/'proposal/PROPOSAL.json'))))
