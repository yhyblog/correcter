"""Build only this task's new CPU package; never execute a runtime entry."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import os
import shlex

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'A10_TORCH_UUID_ABI_CPU_REPAIR_V1'
P = B/'results/A'/TASK
OLD = B/'results/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1'
W = B/'work/A'/f'{TASK}_r1'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path)
    return dict(path=str(path), realpath=str(path.resolve()), size_bytes=path.stat().st_size, sha256=sha(path))


def write(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


assert not (P/'CPU_READY.json').exists(), 'Published packages are immutable'
source_files = []
for name, line_ranges in [('local_version.py.txt', [(4, 7)]), ('local_C_init.pyi.txt', [(10857, 10874)]),
                          ('Module.cpp', [(1022, 1048), (1054, 1069), (1108, 1110)])]:
    path = P/'abi_evidence'/name
    lines = path.read_text().splitlines()
    source_files.append(dict(ref(path), excerpts=[dict(start_line=a, end_line=z,
        text='\n'.join(f'{i}: {lines[i-1]}' for i in range(a, z+1))) for a, z in line_ranges]))
write(P/'ABI_SOURCE_REVIEW.json', dict(
    official_url='https://raw.githubusercontent.com/pytorch/pytorch/e2d141dbde55c2a4370fac5165b0561b6af4798b/torch/csrc/cuda/Module.cpp',
    local_version='2.7.1+cu126', git_commit='e2d141dbde55c2a4370fac5165b0561b6af4798b', files=source_files,
    conclusion='Local annotation says str; corresponding official C++ binding registers _CUuuid, __str__, and the direct device-property uuid field. This supports a trusted class-token branch; it is not runtime type evidence from the failed V2.',
    old_V2_runtime_uuid_type=None, old_V2_runtime_uuid_type_status='unknown; no retrospective inference',
    torch_imports=0, hardware_queries=0, module_dlopen=0))

external = read(OLD/'EXTERNAL_SOURCE_MANIFEST.json')
stub = Path('/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/lib/python3.12/site-packages/torch/_C/__init__.pyi')
version = stub.parent.parent/'version.py'
assert next(r['sha256'] for r in external['files'] if r['path'] == str(stub)) == sha(stub)
assert sha(version) == sha(P/'abi_evidence/local_version.py.txt')
assert not any(r['path'] == str(version) for r in external['files'])
external['files'].append(ref(version))
external['files'].sort(key=lambda r: r['path'])
external['inherited_manifests'].append(ref(OLD/'EXTERNAL_SOURCE_MANIFEST.json'))
external['targeted_sources'] = [ref(stub), ref(version)]
external['scope'] = 'Reuse all 3133 accepted native V2 external identities; only named Torch stub/version read this task, adding version.py. Full runtime identities are checked by a future released entry. No library loading or package scan.'
write(P/'EXTERNAL_SOURCE_MANIFEST.json', external)

proposal = read(OLD/'proposal/PROPOSAL.json')
for name, entry in [('run_proposed_native_preflight.sh', 'launch_preflight.py'),
                    ('check_authorization_cpu.sh', 'authorize_cpu.py')]:
    text = '#!/usr/bin/env bash\nset -euo pipefail\nif [[ $# != 1 ]]; then\n  echo "Usage: $0 NEW_RELEASE_JSON" >&2\n  exit 2\nfi\n'
    text += 'exec ' + shlex.quote(proposal['python']) + ' -B ' + shlex.quote(str(P/'code'/entry))
    text += ' --campaign ' + shlex.quote(str(B)) + ' --proposal ' + shlex.quote(str(P/'proposal/PROPOSAL.json')) + ' --release "$1"\n'
    path = P/'commands'/name
    path.write_text(text)
    path.chmod(0o755)

files = [dict(path=str(f.relative_to(P/'code')), size_bytes=f.stat().st_size, sha256=sha(f))
         for f in sorted((P/'code').rglob('*')) if f.is_file() and f.name != 'CODE_MANIFEST.json' and '__pycache__' not in f.parts]
write(P/'code/CODE_MANIFEST.json', dict(schema_version=1, root=str(P/'code'), files=files))
old_files = {r['path']: r for r in read(OLD/'code/CODE_MANIFEST.json')['files']}
changed = [r['path'] for r in files if r['sha256'] != old_files[r['path']]['sha256']]
assert changed == ['core/native_egl.py', 'core/release.py'], changed
diff = ''
for name in changed:
    diff += ''.join(difflib.unified_diff((OLD/'code'/name).read_text().splitlines(True),
        (P/'code'/name).read_text().splitlines(True), fromfile='accepted_V2/' + name, tofile='proposed_V3/' + name))
(P/'UUID_ONLY_DIFF.patch').write_text(diff)
write(P/'DERIVATION.json', dict(parent_package=str(OLD), parent_code_manifest=ref(OLD/'code/CODE_MANIFEST.json'),
    new_code_manifest=ref(P/'code/CODE_MANIFEST.json'), code_files=len(files), unchanged_code_files=len(files)-len(changed),
    changed_code_files=changed, diff=ref(P/'UUID_ONLY_DIFF.patch'), old_code_content_SHA_verified_on_copy=True,
    old_artifacts_modified=False, shared_packages_modified=False, newly_hashed_model_bytes=0,
    runtime_raw_type_still_unknown=True))

(P/'UUID_REPAIR_NOTES.md').write_text('''| 项目 | 可用 / 缺口 |
|---|---|
| ABI 静态依据 | 本地 2.7.1+cu126 / 提交 e2d141…，stub 与官方绑定差异见 ABI_SOURCE_REVIEW.json |
| 类型支持 | 原生 str，或 type(raw) is 已加载 torch._C._CUuuid；拒绝子类、同名伪造类与任意可转字符串对象 |
| 文本合同 | 原生 str 不转换；可信 _CUuuid 仅 str 一次；完整 ASCII 8-4-4-4-12，可选字面 GPU-，只归一 hex 大小写 |
| 证据顺序 | 既有 properties 返回后，先 fsync policy_device_type.json，再转换/格式/目标比对并 fsync policy_device.json，之后决定拒绝或继续 |
| 失败证据 | 保留原类型模块/qualname、可信 token 身份匹配、转换次数/异常、文本、格式/目标判定；未进行的判定为 null |
| 旧运行类型 | 未知，不回填；静态源码不证明旧运行实际对象类型 |
| 实际设备验证 | 本轮未进行；须另行发布 native V3 release |

只改 core/native_egl.py 的 UUID 分支和证据、core/release.py 的新 V3 任务身份。
八设备物理映射、固定 UUID/PCI、可见性、隔离库、采样/初始化/渲染、独占 claim 和 lifecycle 原样保留。
新增 policy_device_type.json 是 CPU 证据写入，不增加设备 properties、CUDA UUID 或 EGL 调用。
转换异常无第二次转换；未知对象不调用 str。可信类来自既有 Torch 导入，fake 测试仅注入受控类。

未来一次有限运行仍为 1 attempt、5 native/50 flow、1 policy step/13 子步、前后 2 张 corner2 RGB；
52 native reset、104 reset_model、26000 初始化子步、108 显式 graphics、2 次入口 NVML 身份核对。
无独立 UUID 小探针、无球体渲染。完整 rollout、monitor、critic、反向、更新、重试、删除均 0。
全 A8 holder 保持停算直到整个受管进程组退出，包括失败；1800+30 秒只约束诊断子进程，非端到端上限。
CPU checker 可只读验授权但有效 release 时会 hash 权重；真实入口已自带全 SHA，不应在真实运行前额外调用。
当前发布不是授权；不运行真实入口作 dry-run。全部新证据保留。
''')

manifest_files = [ref(P/n) for n in ['code/CODE_MANIFEST.json', 'config/INTEGRATION.json',
    'EXTERNAL_SOURCE_MANIFEST.json', 'REUSED_ASSETS.json', 'proposal/source_manifest.json',
    'ABI_SOURCE_REVIEW.json', 'DERIVATION.json', 'UUID_ONLY_DIFF.patch', 'UUID_REPAIR_NOTES.md']]
for folder in ['commands', 'tests', 'abi_evidence']:
    manifest_files += [ref(f) for f in sorted((P/folder).iterdir()) if f.is_file()]
libs = read(OLD/'REUSED_ASSETS.json')['libraries']
manifest_files += libs
write(P/'INTEGRATION_MANIFEST.json', dict(files=manifest_files,
    exclusions=['PROPOSAL/RELEASE_TEMPLATE/CONTROL_REQUIRED/CPU_READY depend on this manifest and are bound by final receipt'],
    runtime_verification='Full SHA and realpath verification by new released entry; existing libraries reused unchanged'))
proposal.update(proposal_id='A10_NATIVE_PREFLIGHT_V3_TORCH_UUID_ABI_R1', task_id='A10_PREFLIGHT_NATIVE_V3', status='proposed_not_released',
    code_manifest_path=str(P/'code/CODE_MANIFEST.json'), source_manifest_path=str(P/'proposal/source_manifest.json'),
    external_source_manifest_path=str(P/'EXTERNAL_SOURCE_MANIFEST.json'), external_source_manifest_sha256=sha(P/'EXTERNAL_SOURCE_MANIFEST.json'),
    integration_manifest_path=str(P/'INTEGRATION_MANIFEST.json'), integration_manifest_sha256=sha(P/'INTEGRATION_MANIFEST.json'),
    integration_config_path=str(P/'config/INTEGRATION.json'), integration_config_sha256=sha(P/'config/INTEGRATION.json'),
    real_command=[str(P/'commands/run_proposed_native_preflight.sh'), 'NEW_RELEASE_JSON'],
    cpu_authorization_command=[str(P/'commands/check_authorization_cpu.sh'), 'NEW_RELEASE_JSON'],
    uuid_contract=dict(supported_types=['exact native str', 'exact class token torch._C._CUuuid from existing import'],
        native_str_conversions=0, trusted_CUuuid_conversions_max=1, original_properties_calls_max=1,
        new_hardware_queries=0, strict_ASCII_canonical_UUID=True, old_V2_raw_type='unknown',
        evidence_files=['policy_device_type.json', 'policy_device.json'], static_source_review=ref(P/'ABI_SOURCE_REVIEW.json')),
    zero_work_constraints=dict(completed_rollouts=0, monitor_calls=0, critic_forward_calls=0,
        critic_backward_calls=0, vla_backward_calls=0, optimizer_updates=0, retries=0, deletions=0))
proposal['required_inputs'] += [ref(P/'config/INTEGRATION.json'), ref(B/'manifests/A_NATIVE_PREFLIGHT_V2_FINAL_ACCEPTANCE.json')]
proposal['resource_estimates']['source_package_bytes_hashed'] += version.stat().st_size
proposal['resource_estimates']['output_retention'].append('policy_device_type.json pre-conversion raw type; policy_device.json text/conversion/format/target decision')
write(P/'proposal/PROPOSAL.json', proposal)
template = read(OLD/'proposal/RELEASE_TEMPLATE.json')
template.update(status='TEMPLATE_NOT_AUTHORIZED', task_id=proposal['task_id'], release_id='P10_A_NATIVE_PREFLIGHT_V3',
    wave_id='corrector-sim-20260919-A-native-V3-wave05', run_id='A10_PREFLIGHT_NATIVE_V3_r1_A_wave05', shard_id='A-native-V3-shelf-place-once',
    proposal_sha256=sha(P/'proposal/PROPOSAL.json'), code_manifest_sha256=sha(P/'code/CODE_MANIFEST.json'),
    **{k: proposal[k] for k in ['external_source_manifest_sha256', 'integration_manifest_sha256', 'integration_config_sha256', 'real_command', 'cpu_authorization_command']},
    instructions='TEMPLATE ONLY. Analysis must issue a new released V3 file and bind CONTROL/TASK_BOARD. Any claim consumes the release, including pre-diagnostic failure. No old releases, retries, independent UUID probes, extra CPU checker before real launch, or deletion. Existing all8-holder process-family lifecycle and 1800+30 child-only timeout unchanged.')
write(P/'proposal/RELEASE_TEMPLATE.json', template)
control = read(OLD/'proposal/CONTROL_REQUIRED.json')
control.update(status='TEMPLATE_NOT_AUTHORIZED', active_compute_release_id=template['release_id'],
    active_compute_release='releases/' + template['release_id'] + '.json', active_compute_task_ids=[proposal['task_id']],
    allowed_task_ids=[proposal['task_id']], per_task_compute_limits={proposal['task_id']: proposal['native_control_minimum_limits']},
    task_board_entry=dict(id=proposal['task_id'], revision=1, owner='A', status='ready', release='releases/' + template['release_id'] + '.json'))
write(P/'proposal/CONTROL_REQUIRED.json', control)
heartbeat = B/'nodes/A'/f'{TASK}_HEARTBEAT.json'
h = read(heartbeat)
h.update(updated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), progress='Minimal V3 package and unauthorized templates built; targeted fake checks next')
write(heartbeat, h)
print(json.dumps(dict(code_files=len(files), changed=changed, external_files=len(external['files']), integration_refs=len(manifest_files),
    proposal_sha256=sha(P/'proposal/PROPOSAL.json'), status='PROPOSED_NOT_AUTHORIZED'), indent=2))
