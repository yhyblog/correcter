"""Final changed metadata/AST/shell checks; never the real batch launcher."""
from pathlib import Path
import ast,copy,hashlib,json,subprocess,sys,time
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A11_MT50_CONTINUATION_CPU_V1';W=Path(__file__).resolve().parent
O=P/'checks/final_metadata2';O.mkdir(exist_ok=False)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
proposal=read(P/'proposal/PROPOSAL.json');docs=read(P/'proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json');results=[]
for name,key in [('CONTROL','CONTROL'),('TASK_BOARD','TASK_BOARD'),('UNAUTHORIZED_RELEASE','RELEASE')]:write(O/(name+'.json'),docs[key])
future=copy.deepcopy(docs['RELEASE']);future.update(status='released');future['storage_admission']['accepts_monitoring_gaps']=True
write(O/'SYNTHETIC_FUTURE_RELEASE.json',future)
missing_risk=copy.deepcopy(future);missing_risk['storage_admission']['accepts_monitoring_gaps']=False
write(O/'MISSING_RISK_RELEASE.json',missing_risk)
board_running=copy.deepcopy(docs['TASK_BOARD']);next(r for r in board_running['tasks'] if r['id']==proposal['task_id'])['status']='running'
write(O/'RUNNING_BOARD.json',board_running)
# Audit guard wraps the real pure-JSON entry. No runtime module or hardware query.
wrapper=O/'guarded_publication_entry.py'
wrapper.write_text('''import runpy,sys
forbidden={'torch','mujoco','gymnasium','metaworld','pynvml','OpenGL','numpy'}
def guard(event,args):
    if event=='import' and args[0].split('.')[0] in forbidden:raise AssertionError('forbidden import '+args[0])
    if event in ('ctypes.dlopen','ctypes.dlsym','subprocess.Popen','os.system','os.kill','os.killpg'):raise AssertionError('forbidden runtime '+event)
    if event=='open' and isinstance(args[0],str) and (args[0].startswith(('/proc/','/sys/','/dev/')) or args[0].endswith(('.safetensors','.pt','.pth'))):raise AssertionError('forbidden file '+args[0])
sys.addaudithook(guard)
entry=sys.argv.pop(1);sys.path.insert(0,str(__import__('pathlib').Path(entry).parent));sys.argv[0]=entry
runpy.run_path(entry,run_name='__main__')
''')
for name,rel,board,expected in [('ready','SYNTHETIC_FUTURE_RELEASE.json','TASK_BOARD.json',0),('running','SYNTHETIC_FUTURE_RELEASE.json','RUNNING_BOARD.json',0),
    ('unauthorized','UNAUTHORIZED_RELEASE.json','TASK_BOARD.json',1),('missing_new_risk','MISSING_RISK_RELEASE.json','TASK_BOARD.json',1)]:
    cmd=[sys.executable,'-B',str(wrapper),str(P/'code/publication_check.py'),'--control',str(O/'CONTROL.json'),'--board',str(O/board),'--release',str(O/rel)]
    tick=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True,check=False,cwd=P)
    (O/(name+'.stdout')).write_text(r.stdout);(O/(name+'.stderr')).write_text(r.stderr)
    row=dict(name=name,argv=cmd,returncode=r.returncode,expected=expected,passed=r.returncode==expected,elapsed_seconds=time.monotonic()-tick,
        synthetic_authorization_fixture=True,actual_authority_granted=False);results.append(row)
    assert row['passed'],row
for file in sorted((P/'commands').glob('*.sh')):
    r=subprocess.run(['bash','-n',str(file)],capture_output=True,text=True,check=False)
    results.append(dict(name='shell_syntax_'+file.name,returncode=r.returncode,passed=r.returncode==0,executed=False));assert r.returncode==0
for file in sorted((P/'code').rglob('*.py')):ast.parse(file.read_text(),filename=str(file))
for key in ['code_manifest','config_manifest','external_manifest','input_manifest','inherited_package_manifest']:
    row=proposal[key];assert sha(row['path'])==row['sha256']
    if key in ['code_manifest','config_manifest']:
        for f in read(row['path'])['files']:assert sha(f['path'])==f['sha256'],f['path']
paths=proposal['paths'];assert all(not Path(v).exists() for v in paths.values())
assert docs['RELEASE']['status']=='UNAUTHORIZED_TEMPLATE' and docs['RELEASE']['storage_admission']['accepts_monitoring_gaps'] is False
table=read(P/'config/MT50_TASK_TABLE.json');plan=read(P/'REMAINING_PLAN_IDENTITIES.json')
assert len(table['rows'])==50 and table['known_task_count']==50 and table['unknown_task_count']==0
assert len(plan['identities'])==500 and sum(r['processed'] for r in plan['identities'])==9
assert sum(r['selected_for_this_unauthorized_proposal'] for r in plan['identities'])==8
previous=read(B/'results/A/A11_COMMON_POOL_REVISION_CPU_V2/SYNTHETIC_SHARD_CROSSTAB.json')
prior={(r['task_ordinal'],r['split'],r['parent_ordinal']):(r['cut'],r['owner_symbol']) for r in previous['synthetic_parent_design_rows']}
ids={r['task']:r['wrapper_environment_id'] for r in table['rows']}
assert all(prior[(ids[r['task']],r['split'],r['ordinal'])]==(r['cut'],r['proposed_owner']) for r in plan['identities'])
static=read(P/'TASK_SOURCE_EVIDENCE.json')
assert len([r for r in static['task_evidence'] if 'reused_source_evidence' in r])==5
assert len([r for r in static['task_evidence'] if 'source_ref' in r])==45
release=read(W/'authorization/P00_A_MT50_CONTINUATION_CPU_V1.json')
result=dict(status='PASS',checks=results,real_runtime_operations=release['limits'],
    AST_files=28,code_config_references_verified=True,metadata_only=True,
    current_actual_CONTROL_unchanged=(sha(B/'CONTROL.json')==sha(W/'authorization/CONTROL.json')),
    current_actual_TASK_BOARD_unchanged=(sha(B/'TASK_BOARD.json')==sha(W/'authorization/TASK_BOARD.json')),
    runtime_paths_absent={k:not Path(v).exists() for k,v in paths.items()},
    final_proposal_sha256=sha(P/'proposal/PROPOSAL.json'),initialization_table_qualification_wording_change_only=True,initialization_physics_summary_wording_only=True,
    targeted89_fixture_no_rerun=True,old_suites_executed=0)
assert result['current_actual_CONTROL_unchanged'] and result['current_actual_TASK_BOARD_unchanged']
write(O/'CHECK_RESULT.json',result)
print(json.dumps(dict(status='PASS',final_proposal_sha256=result['final_proposal_sha256'],checks=len(results),real_runtime_operations=0,runtime_paths_absent=True)))
