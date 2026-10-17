from pathlib import Path
from datetime import datetime,timezone
import json,shutil,xml.etree.ElementTree as ET
from experiments.standalone_ablation_20260918 import prepare,storage,operations
out=storage.ROOT/'preparation/handoff_v4';cpu=storage.ROOT/'preparation/cpu_v6';pending=storage.ROOT/'pending/operational_v1';ops=storage.ROOT/'preparation/operational_repair_v1'
fields=prepare.future_ready_fields(pending,cpu);previous=storage.read(storage.ROOT/'preparation/handoff_v3/future_ready_fields.json')
scientific=fields['standalone_ablation'].copy();binding=scientific.pop('operational_runtime');assert scientific==previous['standalone_ablation']
oldcode=previous['standalone_preparation_binding']['code_sha256'];newcode=fields['standalone_preparation_binding']['code_sha256']
changed={name:dict(before=oldcode.get(name),after=digest) for name,digest in newcode.items() if oldcode.get(name)!=digest}
assert {Path(p).name for p in changed}=={'operations.py','test_operations.py','prepare.py','runner.py','test_runner.py','audit.py','test_audit.py'}
for name in ('engine.py','candidates.py','collection.py','reference_generation.py','statistics.py','protocol.py','storage.py'):
 assert oldcode[str(prepare.CODE/name)]==newcode[str(prepare.CODE/name)]
rows=prepare._inventory(fields,out/'future_authorization_dry_run');assert all(storage.sha256(r['original_path'])==storage.sha256(r['snapshot_path'])==r['sha256'] for r in rows)
oldfreeze=storage.read(prepare.OLD_CONFIG.with_name('freeze.json'));rebound=operations.inherited_files(binding,oldfreeze);report=storage.read(ops/'inherited_dependency_audit.json');assert len(report['files'])==1702 and len(report['large_assets'])==1 and len(report['drift'])==2
suites=list(ET.parse(cpu/'pytest.xml').getroot().iter('testsuite'));tests=sum(int(x.get('tests',0)) for x in suites);assert tests==86 and all(int(x.get(k,0))==0 for x in suites for k in ('errors','failures','skipped'))
failed=storage.ROOT/'protocols/standalone_v1/freeze.json';assert storage.sha256(failed)=='0222d4614d0a1b41f9a0b807557eb1691cad99b2e91dc2d3509120f129b30e0b'
storage.checked(storage.OLD_ROOT/'budget/attempts.jsonl','3f293430a26d7c0405c33b797788fdfd099f3b8d0a42aec7c37a89338a4ef552');assert not (storage.ROOT/'budget/attempts.jsonl').exists()
guard=storage.read('/tmp/gpu_occupancy_guard/status.json');states={k:v['state'] for k,v in guard['gpus'].items()};assert len(states)==8 and set(states.values())=={'holder'}
storage.dump(out/'future_ready_fields.json',fields)
summary=dict(status='bounded_operational_repair_passed_pending_exact_ready_binding',utc=datetime.now(timezone.utc).isoformat(),decision=prepare.ref(storage.PACKAGE/'coordination/STANDALONE_ABLATION_OPERATIONAL_REPAIR_DECISION_20260918.md'),cpu=prepare.ref(cpu,directory=True),cpu_passed=tests,cpu_scope='four affected test modules only; original unchanged science 145-test cpu_v5 evidence reused, not rerun',previous_science_cpu=prepare.ref(storage.ROOT/'preparation/cpu_v5',directory=True),tested_code_files=len(newcode),changed_files=changed,scientific_contract_identical_except_new_operational_runtime_field=True,all_original_episode_source_and_seed_content_unchanged=True,pending=prepare.ref(pending,directory=True),operational_provenance=prepare.ref(ops,directory=True),operational_binding=prepare.ref(ops/'binding.json'),full_inherited_audit=prepare.ref(ops/'inherited_dependency_audit.json'),inherited_file_count=1702,large_weight_count=1,only_two_external_operations_files_drift=True,science_and_weights_unchanged=True,current_runtime_files=len(storage.read(ops/'binding.json')['runtime_files']),authorization_unique_files=len(rows),authorization_original_and_snapshot_sha_checked=True,future_ready_fields=prepare.ref(out/'future_ready_fields.json'),preflight=dict(physical_gpu_slots=8,real_workers=5,empty_device_slots=3,empty_command=['/usr/bin/true'],source_count=5,attempts=50,empty_model_environment_attempts=0),formal=dict(workers=32,sources=100,cut_sources=98,attempts=1274),budget=dict(plan=1324,new_cap=1500,repair_locked=True,global_cap=50000),failed_standalone_v1=dict(path=str(failed.parent),freeze_sha256=storage.sha256(failed),preserved=True,runnable=False),observed_ready=prepare.ref(prepare.READY),requires_exact_ready_rebinding=True,model_calls=0,simulator_attempts=0,optimizer_updates=0,global_simulator_attempts=48183,global_optimizer_updates=51200,holder_states=states,eight_holders=True,global_operations_files_modified=False,old_seals_modified=False)
storage.dump(out/'handoff.json',summary)
md=f'''# Standalone 有界运维修复交接

{summary['utc']}。原失败 standalone_v1 完整保留、不可运行。新工程准备通过，当前真实模型/仿真/优化均0。

一次全量继承审计覆盖 **1702文件及1个9,354,050,752字节权重**，只有外部 gpu_occupancy_lifecycle.sh / gpu_occupancy_guard.py 变化。科学实现和权重保持原SHA。两脚本旧正文从旧heldout真实tar提取并核原SHA；当前正文单独保存，真实diff只增加holder占用参数 .50/.20。当前新增完整运维闭包还绑定 gpu_hold.py、原wave脚本及 /usr/bin/true；不为旧快照缺失的holder编造历史SHA。旧全局文件与旧freeze不改。

新protocol仅在显式白名单内替换这两个运行SHA；旧freeze、旧正文与历史位置另行保留。缺少原依赖、科学漂移、大权重不符或未列明runtime修改均拒绝。新READY枚举旧/新证据真实文件引用，future字段{len(rows)}个唯一引用的原件及副本SHA均已核。

预检八设备槽：0–4仍各一个原supervisor与源；5–7仅`/usr/bin/true`，无模型、环境、源或attempt。仍5源50次。正式八卡四worker共32不变；严格审计全部job命令、rank、源与空槽零工作契约。真实旧wave工具在mock子进程CPU例中已接受八槽spec，不改全局wave。整波仍一次lifecycle；退出释放后holder为guard异步恢复，实际结束后需核8holder，不能仅凭命令退出声称恢复完成。

**本次必要CPU：86 passed / 0 failed**，仅4个受影响测试模块；此前cpu_v5的145项科学/日志测试证据沿用，未重复运行。24份当前代码/测试/脚本前后SHA一致。只改5个prepare/runner/audit工程及对应测试文件，新增operations与测试；engine/candidates/collection/reference/statistics/protocol/storage身份不变。

- 新pending：`{pending}`，seal `{storage.sha256(pending/'complete.json')}`。与原pending仅增加operational_runtime字段。
- 运维来源包：`{ops}`，seal `{storage.sha256(ops/'complete.json')}`。
- CPU：`{cpu}`，seal `{storage.sha256(cpu/'complete.json')}`。
- 新完整future字段：`{out/'future_ready_fields.json'}`，SHA `{storage.sha256(out/'future_ready_fields.json')}`。
- 机器交接：`{out/'handoff.json'}`。

原科学契约逐项不变，仅增加独立operational_runtime引用；计划50+1274=1324、新cap1500、repair锁、全局50000不变。live v3不匹配本次新工程，尚未尝试新freeze或wave。分析端精确重绑后使用新version目录，不能覆盖失败standalone_v1。当前全局48183sim/51200opt，8holder保持。
'''
with (out/'HANDOFF.md').open('x') as f:f.write(md)
shutil.copyfile(__file__,out/'handoff_builder.py');storage.seal(out,role='standalone_operational_repair_handoff',model_calls=0,simulator_calls=0,optimizer_updates=0)
coord=storage.PACKAGE/'coordination/STANDALONE_ABLATION_OPERATIONAL_REPAIR_HANDOFF_20260918.md'
with coord.open('x') as f:f.write(md)
p=storage.PACKAGE/'coordination/STANDALONE_ABLATION_EXECUTOR_STATUS.json';s=storage.read(p);s.update(updated_utc=datetime.now(timezone.utc).isoformat(),state='operational_repair_complete_pending_exact_ready_binding',engineering_stage='86_affected_cpu_passed_science_unchanged',cpu_evidence=dict(path=str(cpu),status='passed',passed=86,failed=0,seal_sha256=storage.sha256(cpu/'complete.json'),scope='four affected modules only; reuse unchanged cpu_v5 science checks'),handoff=dict(path=str(out),seal_sha256=storage.sha256(out/'complete.json'),coordination_path=str(coord),coordination_sha256=storage.sha256(coord)),future_ready_fields=prepare.ref(out/'future_ready_fields.json'),pending=prepare.ref(pending,directory=True),technical_blockers=[],actual_runtime_released=False,next_step='Exact new operations/code/CPU READY binding then fresh standalone_v2 freeze/lifecycle preflight; failed v1 remains preserved. No science/user reapproval needed.')
s['operational_repair'].update(status='complete',provenance=prepare.ref(ops,directory=True),global_ops_modified=False)
p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(handoff=str(out),handoff_seal_sha256=storage.sha256(out/'complete.json'),future_ready_fields_sha256=storage.sha256(out/'future_ready_fields.json'),coordination_sha256=storage.sha256(coord),cpu=summary['cpu'],authorization_unique_files=len(rows)),indent=2))
