"""Record actual deployment once; never launch scientific work."""
import ast
from queue_common import *

def main():
    authority();own=read(ROOT/'PROCESS.json');heart=read(ROOT/'HEARTBEAT.json')
    if not live(own) or heart['status']!='monitoring':raise RuntimeError('CPU supervisor not running')
    if (ROOT/'SUPERVISION_ERROR.json').exists():raise RuntimeError('unresolved supervisor startup error')
    if read(ROOT/'CPU_CHECK.json')['status']!='passed':raise RuntimeError('CPU checks missing')
    old=read(C/'receipts/C'/f'{TASK}_ACK.json')
    for r in old['observed']:
        if r['task_id'] in [X.name,P.name] and sha(r['claim']['path'])!=r['claim']['sha256']:raise RuntimeError('existing scientific claim changed')
    for p in WORK.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    powner=read(P/'PROCESS.json');pheart=read(P/'HEARTBEAT.json');guard=snapshot('/tmp/gpu_occupancy_guard/status.json')
    node=read(C/'nodes/C/identity.json');xexit=family(X)
    if not xexit['exited'] or not read(X/'RESULT.json')['all_owned_descendants_exited']:raise RuntimeError('X exit unresolved')
    if not live(powner) or pheart['status']!='evaluate':raise RuntimeError('Pi05 actual automatic transition not established')
    if pheart['progress']['loaded_workers']!=24:raise RuntimeError('24 Pi05 model-ready workers not established')
    if len(guard.get('gpus',{}))!=8 or any(r['state']!='reserved' for r in guard['gpus'].values()):raise RuntimeError('cached whole-wave reservation not established')
    native=read(ROOT/'tables'/X.name/'SUMMARY.json')
    assert native['valid']==1000 and native['missing']==0
    current_claims=len(list((P/'unit_claims').glob('*.json')))
    stages=[
      dict(stage='X_selected_Q_Post_Velocity',task_id=X.name,maximum_first_units=1000,status='complete',valid=1000,entry=str(X/'code/service.py'),config=ref(X/'config/CONFIG.json'),source_manifest=ref(X/'config/TEST_SOURCES.json'),claim=ref(X/'CLAIM.json'),result=ref(X/'RESULT.json'),automatic_continuation_requires_LLM=False,training_repeated=0),
      dict(stage='pi05_H40_selected_Q_Post_Velocity',task_id=P.name,maximum_first_units=1000,status='running',existing_process=powner,entry=str(P/'code/manager.py'),source_manifest=ref(P/'JOB_INDEX.json'),config=ref(P/'config/CONFIG.json'),automatic_continuation_requires_LLM=False,dependency='X reliable terminal and whole-family exit; Post-only selection and exact A transfer'),
      dict(stage='pi05_H50_selected_Q_Post_Velocity',task_id=P.name,maximum_first_units=1000,status='prequeued',entry=str(P/'code/manager.py'),source_manifest=ref(P/'JOB_INDEX.json'),automatic_continuation_requires_LLM=False,dependency='H40 dispatch drained; same resident worker queue'),
      dict(stage='bounded_engineering_continuation_if_needed',status='encoded_and_supervised',entry=ref(WORK/'supervisor.py'),builder=ref(WORK/'build_continuation.py'),prepared_entrypoints=ref(ROOT/'PREPARED_ENTRYPOINTS.json'),dependency='all original owners/families and prior continuation exited, valid Post-only lock, exact ownership, original deadlines and budgets',automatic_continuation_requires_LLM=False),
      dict(stage='CPU_tables',status='X_complete_Pi05_automatic_on_terminal',entry=ref(WORK/'export_task.py'),output=str(ROOT/'tables'),original_per_task_reports_preserved=True,automatic_continuation_requires_LLM=False)]
    job=C/'persistent_queue/nodes/C/wakeup/jobs/D24_C_QUOTA_INDEPENDENT_r1.json'
    assert read(job)['process_identity']==own
    ack=C/'persistent_queue/nodes/C/wakeup/handler_acks/C_929f672d9dc8af23599afa7711a80af3.json'
    assert read(ack)['actual_original_handler_verified'] and read(ack)['outcome']=='claimed'
    evidence=dict(utc=utc(),host=node['hostname'],boot_id=node['boot_id'],queue_process=own,actual_queue_alive=True,queue_heartbeat=heart,Pi05_original_process=powner,Pi05_original_alive=True,Pi05_heartbeat=pheart,Pi05_attempt_claims_snapshot=current_claims,X_actual_family_exit=xexit,guard_cached_status=guard,guard_snapshot_is_not_a_new_GPU_probe=True,GPU_UUIDs=read(P/'config/BASE.json')['device_list'],X_restoration=ref(X/'chains/evaluate/RESTORATION.json'),Pi05_all_holder_exit_ACK=ref(P/'chains/evaluate/HOLDER_EXIT_ACK.json'),notifier=read(C/'persistent_queue/nodes/C/wakeup/PROCESS.json'))
    atomic_json(ROOT/'RUNTIME_VERIFICATION.json',evidence)
    row=dict(task_id=TASK,revision=1,status='ready_quota_independent_ordinary_background_queue',utc=utc(),authorization=ref(AUTH),event_ACK=ref(ack),actual_process=own,actual_host=node['hostname'],actual_alive=True,runtime=ref(ROOT/'RUNTIME_VERIFICATION.json'),stages=stages,selection=ref(C/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json'),selection_lock=ref(C/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION_LOCK.json'),transfer=ref(C/'results/A/A_D24_FULL_Q_AUTORUN_HANDOFF_V2/TRANSFER_READY.json'),consumed_X_selection=ref(X/'SELECTION_CONSUMED.json'),consumed_pi05_selection=ref(P/'SELECTION_CONSUMED.json'),consumed_pi05_transfer=ref(P/'TRANSFER_CONSUMED.json'),pure_CPU_selection_and_dependencies=True,LLM_required_for_normal_next_stage=False,analysis_ACK_required_for_normal_next_stage=False,callback_failure_blocks_science=False,notification_registration=ref(job),notification_failure_handling='bounded attempt; persist failure; continue ordinary science without callback',native_cached_validator_real_recovery=ref(C/'results/C/C_D24_AUTORECOVERY_QUEUE_RULE_V1/CPU_METADATA_RECOVERY_VERIFIED.json'),retry_and_skip=dict(supervisor=ref(WORK/'supervisor.py'),source_inventory=ref(WORK/'inventory.py'),admission=ref(WORK/'continuation_adapter.py'),repair_policy=ref(OPS/'c_recovery_policy.py'),analysis_timeout_seconds=1800,independent_eligible_tasks_continue_immediately=True,same_fault_max_corrected_restarts=2,implemented_automatic_continuation_passes_per_task=1,per_failed_source_corrected_retry_max=1,completed_success_or_legal_failure_replayed=False,encoded_failed_source_correction='transient qio JSON commit Errno5/116/107 evidenced in raw traceback; atomic exclusive bounded commit adapter',unknown_faults='retain issue and missingness; do not replay unknown admitted units; continue eligible independent tasks',safe_unentered_tail_continuation='exact source mask and new run namespace, retaining original scientific claim and counters'),deadlines=dict(science_admission_cutoff_utc='2026-09-23T12:00:00Z',tables_due_utc='2026-09-23T15:00:00Z',original_scientific_stage_timeout_unchanged=True,Pi05_stage_deadline=read(P/'STAGE_DEADLINE.json'),CPU_wait_extension='not needed: original Pi05 dependency waiter already advanced'),budgets=dict(X_stage=1100,X_node=14000,pi05_stage=2200,pi05_node=16000,unchanged=True),CPU_check=ref(ROOT/'CPU_CHECK.json'),actual_GPU_failure_recovery_tested=False,ordinary_real_transition_verified='X 1000 valid and whole-family exit -> same Pi05 PID auto-start, 24 loaded workers',new_GPU_probe_calls=0,new_unique_scientific_units=0,new_training_updates=0,healthy_scientific_processes_restarted=0,private_code=ref(ROOT/'PREPARED_ENTRYPOINTS.json'),output=str(ROOT/'tables'),Post_current_paper=True,Velocity_continues_other_work=True,limitations=['Only encoded engineering cases resume automatically; unseen bugs remain issues.','Machine/container reboot requires verified recovery; this deployment survives terminal/chat closure.','Original scientific caps and deadlines may leave deferred units.','GPU fault recovery was not artificially triggered; CPU entry and admission invariants were tested.'],stop_LLM_wait=True,callback_completion_recursive_wakeup=False)
    atomic_json(ROOT/'QUOTA_INDEPENDENT_READY.json',row)
    atomic_json(ROOT/'STABLE_HANDOFF.json',dict(utc=utc(),status='stable_ordinary_queue',ready=ref(ROOT/'QUOTA_INDEPENDENT_READY.json'),runtime=ref(ROOT/'RUNTIME_VERIFICATION.json'),terminal_notification=ref(job),stop_LLM_wait=True,LLM_required=False))
    receipt=dict(task_id=TASK,revision=1,status='deployed',utc=utc(),ready=ref(ROOT/'QUOTA_INDEPENDENT_READY.json'),background_PID=own['pid'],X_valid=1000,Pi05_background='24 loaded workers; H40 then H50, exact 2000 scope',new_scientific_units=0,new_GPU_probe_calls=0,existing_claims_preserved=True,CPU_checks='passed',notification_armed=True,stop_LLM_wait=True)
    atomic_json(C/'receipts/C'/f'{TASK}_RESULT.json',receipt)
    print(__import__('json').dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()

