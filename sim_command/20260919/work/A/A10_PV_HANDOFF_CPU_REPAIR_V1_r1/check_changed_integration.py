"""Only the changed CPU metadata/environment/install interfaces and syntax."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1'
W=B/'work/A/A10_PV_HANDOFF_CPU_REPAIR_V1_r1'
sys.path.insert(0,str(P/'code'))
from core.handoff import HANDOFF_SPEC,require_handoff_environment
from core.contracts import ContractError

def put(path,obj):
    with path.open('x') as f:f.write(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

cfg=json.loads((P/'config/CONFIG.json').read_text())
text=(P/'code/launch.py').read_text()
node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='child_environment')
scope=dict(os=SimpleNamespace(environ={}),ContractError=ContractError,require_handoff_environment=require_handoff_environment)
exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_child_environment_fake_only','exec'),scope)
base=dict(cfg['cuda_environment']);base[HANDOFF_SPEC['environment_variable']]='300'
out=scope['child_environment'](cfg,Path('/synthetic/no_io/cache'),parent=base)
assert out[HANDOFF_SPEC['environment_variable']]=='300'
assert base[HANDOFF_SPEC['environment_variable']]=='300'
for value in [None,'90','bad']:
    bad=dict(base)
    if value is None:bad.pop(HANDOFF_SPEC['environment_variable'])
    else:bad[HANDOFF_SPEC['environment_variable']]=value
    try:scope['child_environment'](cfg,Path('/synthetic/no_io/cache'),parent=bad);raise AssertionError('Environment drift accepted')
    except ValueError:pass
wrong_cfg=copy.deepcopy(cfg);wrong_cfg['occupancy_handoff']['timeout_seconds']=90
try:require_handoff_environment(wrong_cfg,base);raise AssertionError('Config drift accepted')
except ValueError:pass
assert 'export CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300\n' in (P/'commands/run_proposed_pv_offline.sh').read_text()
assert text.index('checked,p=load_authorization(a.release,full=True)') < text.index('handoff=require_handoff_environment(cfg,os.environ)') < text.index("rows=meter.call('pre_reservation_NVML_identity'")
assert "cmd=[cfg['occupancy_lifecycle'],'run','--'" in text

installer=P/'commands/transition_guard_file_cpu.py'
modspec=importlib.util.spec_from_file_location('future_installer_metadata',installer);module=importlib.util.module_from_spec(modspec);modspec.loader.exec_module(module)
identity=json.loads((P/'guard_patch/PATCH_IDENTITY.json').read_text())
control=json.loads((W/'ack_snapshots/CONTROL.json').read_text())
install_results=[]
for operation in ['install','rollback']:
    t=json.loads((P/'guard_patch'/f'{operation.upper()}_RELEASE_TEMPLATE.json').read_text())
    t['release_id']='SYNTHETIC_'+operation.upper()+'_RELEASE'
    path=B/'releases'/(t['release_id']+'.json')
    c=copy.deepcopy(control);c['active_guard_installation_release']=str(path.relative_to(B))
    try:module.validate(t,c,identity,operation,path,t['owner_host']);raise AssertionError('Unauthorized install template accepted')
    except ValueError:pass
    t['status']='released'
    before,after=module.validate(t,c,identity,operation,path,t['owner_host'])
    assert (before,after)==(('original','patched') if operation=='install' else ('patched','original'))
    c['formal_gpu_runs_enabled']=True
    try:module.validate(t,c,identity,operation,path,t['owner_host']);raise AssertionError('Active-compute installation accepted')
    except ValueError:pass
    install_results.append(dict(operation=operation,unauthorized_rejected=True,synthetic_exact_release_accepted=True,active_compute_window_rejected=True,shared_writes=0))

changed=[P/'guard_patch/gpu_occupancy_guard.patched.py',P/'code/core/contracts.py',P/'code/core/handoff.py',P/'code/launch.py',P/'code/diagnostic.py',P/'commands/check_publication_metadata_cpu.py',installer,W/'prepare_guard_patch.py',W/'prepare_v3_package.py',W/'prepare_installation_proposal.py',W/'check_handoff_fakes.py',Path(__file__)]
for path in changed:ast.parse(path.read_text(),filename=str(path))
shell=subprocess.run(['/bin/bash','-n',str(P/'commands/run_proposed_pv_offline.sh')],capture_output=True,text=True)
assert shell.returncode==0,shell.stderr
fixture=W/'targeted_fixtures'
argv=['/usr/bin/python3','-I','-S','-B',str(P/'commands/check_publication_metadata_cpu.py'),'--control',str(fixture/'CONTROL_CANDIDATE.json'),'--board',str(fixture/'TASK_BOARD_CANDIDATE.json'),'--release-json',str(fixture/'RELEASE_CANDIDATE.json')]
check=subprocess.run(argv,capture_output=True,text=True)
assert check.returncode==0,check.stdout+check.stderr
answer=json.loads(check.stdout);assert answer['status']=='PASS_METADATA_ONLY_NOT_AUTHORIZATION'
result=dict(status='passed',actual_child_environment_positive_and_negative_checks=4,wrong_config_rejected=True,
    frozen_shell_export=True,handoff_CPU_environment_gate_before_parent_NVML=True,unchanged_lifecycle_invocation=True,
    install_rollback_metadata_checks=install_results,install_entry_main_invocations=0,AST_changed_or_added_paths=[str(x) for x in changed],
    shell_syntax=dict(argv=shell.args,returncode=shell.returncode,stdout=shell.stdout,stderr=shell.stderr,executed_shell=False),
    publication_CLI=dict(argv=argv,returncode=check.returncode,result=answer,stderr=check.stderr,fixture_only_not_authorization=True),
    real_guard_launcher_claim_or_GPU_calls=0,holder_queries_stops=0,shared_installations=0,daemon_restarts=0,deletions=0)
put(W/'CHANGED_INTEGRATION_AND_SYNTAX_CHECKS.json',result)
print(json.dumps(dict(status='passed',changed_AST_files=len(changed),environment_checks=5,installation_metadata_cases=6,shell_syntax='passed',publication_CLI='passed',real_operations=0),indent=2))
