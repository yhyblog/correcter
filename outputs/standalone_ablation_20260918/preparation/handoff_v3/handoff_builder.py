from pathlib import Path
from datetime import datetime,timezone
import json,shutil,xml.etree.ElementTree as ET
from experiments.standalone_ablation_20260918 import prepare,storage,protocol
cpu=storage.ROOT/'preparation/cpu_v5';pending=storage.ROOT/'pending/task_document_v1';out=storage.ROOT/'preparation/handoff_v3'
fields=prepare.future_ready_fields(pending,cpu)
previous=storage.read(storage.ROOT/'preparation/handoff_v2/future_ready_fields.json')
oldcode=previous['standalone_preparation_binding']['code_sha256'];newcode=fields['standalone_preparation_binding']['code_sha256']
changed={name:dict(before=oldcode[name],after=digest) for name,digest in newcode.items() if oldcode.get(name)!=digest}
assert set(changed)=={str(prepare.CODE/'engine.py'),str(prepare.CODE/'test_engine.py')}
assert set(oldcode)==set(newcode)
for key in fields:
 if key!='standalone_preparation_binding':assert fields[key]==previous[key]
for key in fields['standalone_preparation_binding']:
 if key not in ('cpu_evidence','code_sha256'):assert fields['standalone_preparation_binding'][key]==previous['standalone_preparation_binding'][key]
rows=prepare.authorization_references(fields,base_dir=storage.PACKAGE)
for row in rows:storage.checked(row['original_path'],row['sha256'])
suites=list(ET.parse(cpu/'pytest.xml').getroot().iter('testsuite'));tests=sum(int(x.get('tests',0)) for x in suites)
assert tests==145 and all(int(x.get(k,0))==0 for x in suites for k in ('failures','errors','skipped'))
ready_sha=storage.sha256(prepare.READY);ready=storage.read(prepare.READY)
assert any(ready.get(k)!=v for k,v in fields.items()),'New matching READY arrived: inspect and do not use negative test'
negative_dest=storage.ROOT/'protocols/activity_revision_negative_check'
try:prepare.freeze(pending,prepare.READY,cpu,version='activity_revision_negative_check')
except ValueError as error:
 assert str(error)=='Exact actual input/code/CPU future READY binding differs'
 assert not negative_dest.exists()
 negative=dict(status='passed_expected_rejection',error=str(error),freeze_created=False,model_calls=0,simulator_calls=0)
else:raise AssertionError('Mismatched READY accepted')
ledger=storage.OLD_ROOT/'budget/attempts.jsonl';storage.checked(ledger,protocol.BASE_LEDGER_SHA)
storage.checked(prepare.OLD_CONFIG,prepare.OLD_CONFIG_SHA);storage.checked(prepare.OLD_CONFIG.with_name('freeze.json'),prepare.OLD_FREEZE_SHA)
storage.checked(storage.PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json','b4241436b80706e2edc3ed9f5c16ef3dca02dab029732776c7411f73779f5d3d')
assert not (storage.ROOT/'budget/attempts.jsonl').exists()
guard=storage.read('/tmp/gpu_occupancy_guard/status.json');states={k:v['state'] for k,v in guard['gpus'].items()};assert len(states)==8 and set(states.values())=={'holder'}
revision=dict(status='passed',changed_files=changed,unchanged_other_code_files=len(newcode)-2,
 successful_propose_ast_identical_after_only_known_logging_adapters_and_existing_guidance_handler_normalization=True,
 scientific_release_contract_unchanged=True,pending_unchanged=True,budget_unchanged=True,
 native_action_recorded_before_entry=True,returned_and_raised_events=True,persistent_per_proposal_activity=True,
 runtime_object_not_replaced=True,new_proposal_resets_activity=True,pre_sampling_failure_calls=0,
 native_action_failure_calls=1,post_sampling_validation_failure_calls=1,
 synthetic_archived_fallback_double_failure_calls=2,synthetic_archived_fallback_only_in_test=True,
 production_guidance_error_stops_without_fallback=True,interrupt_original_type_preserved=True,
 unknown_external_stub_counts_remain_null=True,strict_json_nonfinite_evidence=True,
 negative_freeze_check=negative,observed_ready=prepare.ref(prepare.READY))
storage.dump(out/'future_ready_fields.json',fields);storage.dump(out/'revision.json',revision)
storage.dump(out/'authorization_inventory_dry_run.json',dict(status='passed',references=rows,reference_count=len(rows),scope='future exact payload only; actual freeze inventories complete live READY'))
report=dict(status='native_action_activity_revision_complete_exact_rebinding_delivered',utc=datetime.now(timezone.utc).isoformat(),
 task=dict(path=fields['task_document'],sha256=fields['task_document_sha256']),cpu=prepare.ref(cpu,directory=True),cpu_tests=tests,code_files=len(newcode),
 pending=prepare.ref(pending,directory=True),future_ready_fields=prepare.ref(out/'future_ready_fields.json'),revision=prepare.ref(out/'revision.json'),
 authorization_inventory=prepare.ref(out/'authorization_inventory_dry_run.json'),supersedes_preparation=prepare.ref(storage.ROOT/'preparation/handoff_v2',directory=True),
 previous_ready=dict(path=str(prepare.READY),sha256=ready_sha,version=ready['version']),scope_and_budget_unchanged=True,
 new_model_calls=0,new_simulator_attempts=0,new_optimizer_updates=0,global_simulator_attempts=48183,global_optimizer_updates=51200,
 old_ledger_sha256=protocol.BASE_LEDGER_SHA,holder_states=states,eight_holders=True,requires_exact_ready_rebinding=True)
storage.dump(out/'handoff.json',report)
md=f'''# Standalone 采样失败活动记录补充交接

{report['utc']}。最新窄日志缺口已修复；最终 CPU **145 passed / 0 failed**（含既有成本、预算、配对和统计检查）。真实模型/仿真/优化调用均为0。

每次 propose 开始建立新活动记录，在底层 native_action 进入前追加调用，返回或异常时保存状态、耗时和当前 hook 证据。采样前失败为0次，采样内异常和采样后 shape/schedule/first-action 校验失败均为1次。generate_solo 同时汇总已返回和失败 proposal；不把未知外部 stub 调用数填0，不沿用上一调用的活动。KeyboardInterrupt 保留原异常类型。

旧 fallback 两次采样都抛异常的合成 CPU 例证明可恢复2次实际进入；生产路径沿上一修订遇 GuidanceError 立即停止，无 fallback。成功路径梯度与采样运算 AST 在仅归一化已知日志包装/局部代理及既有 GuidanceError 处理后与旧实现完全一致；原 runtime 对象不替换。未增加 Q 门、采样重试或其他算法改动。

仅 engine.py 和 test_engine.py 更新，其余20代码文件、TASK/pending/科学合同、50预检+1274正式/1500新增cap/50000全局上限全部不变。旧封存和历史 CPU/交接保留。

- CPU：`{cpu}`；seal `{storage.sha256(cpu/'complete.json')}`，包含22份受测源码和前后SHA。
- 新字段：`{out/'future_ready_fields.json'}`；SHA `{storage.sha256(out/'future_ready_fields.json')}`。
- 修订细节与故障例：`{out/'revision.json'}`。
- 机器交接：`{out/'handoff.json'}`。
- TASK SHA `{fields['task_document_sha256']}`。
- engine.py SHA `{newcode[str(prepare.CODE/'engine.py')]}`；test_engine.py SHA `{newcode[str(prepare.CODE/'test_engine.py')]}`。

现有 READY v{ready['version']} SHA `{ready_sha}` 精确绑定历史 CPUv4。真实 metadata freeze 已正确拒绝用它运行本次修订，未创建freeze或计费；需将新CPU/代码字段精确绑定，既有科学范围与权限不变，无需用户重复许可。新未来字段中的{len(rows)}项实际授权引用已核SHA。

全局仍48183sim/51200opt，新增0，八卡holder保持。本报告不声称真实预检或跨实现数值配对已通过。
'''
with (out/'HANDOFF.md').open('x') as f:f.write(md)
shutil.copyfile(__file__,out/'handoff_builder.py')
storage.seal(out,role='standalone_activity_log_preparation_handoff',model_calls=0,simulator_calls=0,optimizer_updates=0)
coord=storage.PACKAGE/'coordination/STANDALONE_ABLATION_ACTIVITY_LOG_HANDOFF_20260918.md'
with coord.open('x') as f:f.write(md)
statuspath=storage.PACKAGE/'coordination/STANDALONE_ABLATION_EXECUTOR_STATUS.json';status=storage.read(statuspath)
status.update(updated_utc=datetime.now(timezone.utc).isoformat(),state='activity_log_fix_complete_pending_exact_code_cpu_binding',
 authorization='Scientific scope and budgets released in READY v2; current logging-only revision awaits exact new code/CPU binding; no user reapproval required',
 engineering_stage='complete_145_cpu_passed_activity_journal',cpu_evidence=dict(path=str(cpu),status='passed',passed=tests,failed=0,seal_sha256=storage.sha256(cpu/'complete.json')),
 handoff=dict(path=str(out),seal_sha256=storage.sha256(out/'complete.json'),coordination_path=str(coord),coordination_sha256=storage.sha256(coord)),
 future_ready_fields=prepare.ref(out/'future_ready_fields.json'),technical_blockers=[],
 holder_check=dict(guard_pid=guard['pid'],states=states,eight_holders=True),
 observed_live_standalone_ready=dict(path=str(prepare.READY),version=ready['version'],sha256=ready_sha,binding_status='Scope approved; binds historical cpu_v4, current cpu_v5 requires exact rebind'),
 actual_runtime_released=False,next_step='Analysis metadata rebind of CPU and two code hashes; then one independent freeze and authorized preflight/audit/formal, no repeated science/user approval.')
status['current_revision']['status']='complete_145_cpu_passed'
status['budget_proposal'].update(authorized=True,runtime_authorized=False)
statuspath.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(handoff=str(out),handoff_seal_sha256=storage.sha256(out/'complete.json'),future_ready_fields_sha256=storage.sha256(out/'future_ready_fields.json'),cpu_seal_sha256=storage.sha256(cpu/'complete.json'),coordination_path=str(coord),coordination_sha256=storage.sha256(coord),tests=tests),ensure_ascii=False,indent=2))
