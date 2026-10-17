from pathlib import Path
import ast,hashlib,json,subprocess,sys,datetime
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');P=B/'results/A/A10_CAUSAL_C10_CPU_V1';W=B/'work/A/A10_CAUSAL_C10_CPU_V1_r1'
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p),realpath=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size_bytes=p.stat().st_size)
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
# Final changed checker self-bootstrap is reflected consistently in the new,
# still-unpublished private snapshot and downstream templates.
f=P/'INTEGRATION_MANIFEST.json';d=read(f)
for row in d['files']:row['new']=ref(Path(row['new']['path']))
write(f,d)
f=P/'code/CODE_MANIFEST.json';d=read(f)
for row in d['files']:
 q=P/'code'/row['path'];row.update(sha256=ref(q)['sha256'],size_bytes=q.stat().st_size)
write(f,d)
f=P/'proposal/PROPOSAL.json';d=read(f)
d['code_manifest']=ref(P/'code/CODE_MANIFEST.json');d['integration_manifest']=ref(P/'INTEGRATION_MANIFEST.json')
write(f,d)
f=P/'proposal/RELEASE_TEMPLATE.json';d=read(f);d.update(code_manifest_sha256=ref(P/'code/CODE_MANIFEST.json')['sha256'],proposal_sha256=ref(P/'proposal/PROPOSAL.json')['sha256']);write(f,d)
# Minimal final standalone publication command + shell syntax validation.
f=W/'final_publication_fixture';f.mkdir(exist_ok=False)
for name in ['CONTROL.json','TASK_BOARD.json']:(f/name).write_bytes((W/'publication_fixture_r1'/name).read_bytes())
d=read(P/'proposal/RELEASE_TEMPLATE.json');d['status']='released';write(f/'RELEASE.json',d)
checks=[]
for name,cmd in [('pure_JSON_publication', ['/usr/bin/python3','-I','-S','-B',str(P/'code/publication_check.py'),'--control',str(f/'CONTROL.json'),'--board',str(f/'TASK_BOARD.json'),'--release',str(f/'RELEASE.json')]),('shell_syntax',['bash','-n',str(P/'commands/run_proposed_causal_c10.sh')])]:
 started=datetime.datetime.now(datetime.timezone.utc).isoformat();result=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
 row=dict(name=name,command=cmd,started_utc=started,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
 checks.append(row)
 if result.returncode!=0:write(W/'FINAL_STATIC_COMMANDS.json',dict(status='FAILED',checks=checks));raise SystemExit(1)
ast.parse((P/'code/publication_check.py').read_text())
write(W/'FINAL_STATIC_COMMANDS.json',dict(status='PASS',checks=checks,additional_check='changed publication entry AST parsed'))
# Lightweight manifest integrity uses new source/config/proposal bytes only.
# Inherited external/weight references are metadata, never opened for hashing.
p=read(P/'proposal/PROPOSAL.json');verified=[]
for k in ['config','input_manifest','external_sources','code_manifest','integration_manifest','budget','command']:
 actual=ref(Path(p[k]['path']));assert actual['sha256']==p[k]['sha256'];verified.append(dict(key=k,**actual))
for row in read(P/'code/CODE_MANIFEST.json')['files']:
 f=P/'code'/row['path'];assert ref(f)['sha256']==row['sha256']
# Small control/ACK/closed-dependency reads only, not a live hardware query.
c=read(B/'CONTROL.json');board=read(B/'TASK_BOARD.json');cpu=B/'releases/P00_CAUSAL_C10_CPU_V1.json'
assert c['revision']==32 and board['revision']==39
assert c['mode']=='prepare' and c['formal_gpu_runs_enabled'] is False and c['active_compute_release_id'] is None
assert all(v==0 for v in c['current_compute_limits'].values())
assert ref(cpu)['sha256']=='a5597bbc90461f9918b02425f62a4e44fdbc9a04d3906dcffd43faec5ca3b74d'
assert not (B/'releases/P10_A_CAUSAL_C10_PREFLIGHT_V1.json').exists()
assert not (B/'results/A/P10_CAUSAL_C10_V1_release_claims/P10_A_CAUSAL_C10_PREFLIGHT_V1.json').exists()
write(W/'FINAL_CPU_AUDIT.json',dict(status='PASS',control=ref(B/'CONTROL.json'),task_board=ref(B/'TASK_BOARD.json'),CPU_release=ref(cpu),
    verified_small_package_references=verified,new_code_files_SHA_verified=len(read(P/'code/CODE_MANIFEST.json')['files']),
    inherited_weight_external_identity_basis='metadata inherited; no large weight or driver library rehash performed now',future_release_exists=False,future_claim_exists=False,
    current_compute_limits_all_zero=True,holder_queries=0,holder_stops=0,actual_launches=0,claims=0))
print(json.dumps(dict(status='PASS',final_checks=str(W/'FINAL_STATIC_COMMANDS.json'),final_audit=str(W/'FINAL_CPU_AUDIT.json'))))
