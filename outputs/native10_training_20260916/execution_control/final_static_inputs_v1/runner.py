"""One-shot orchestration of already authorized static inputs; no model stage."""
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import json
import os
import resource
import subprocess
import time
import traceback

from experiments.native10_training_20260916 import storage

ROOT = storage.ROOT
HERE = Path(__file__).resolve().parent
PLAN = ROOT/'preparation/final_input_execution_plan_v1.json'
REVIEW = storage.PACKAGE/'analysis/final_model_preflight_implementation_review.json'
WATCH = ROOT/'progress_audits/round2_runtime/round2_v1_01/latest.json'
THREADS = ('01a0a551-9ed3-7f53-9f39-b60d8674819d', '01a09fc3-ff82-72e3-87ef-9e9f63a792ce')


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def publish(state, **details):
    record = dict(state=state, updated_utc=now(), runner_pid=os.getpid(),
        runner=str(Path(__file__).resolve()), simulator_attempts=0, optimizer_updates=0,
        model_initializations=0, model_inference_calls=0, pca_fits=0,
        real_model_stage_automatically_started=False, **details)
    storage.dump(HERE/'latest.json', record, exclusive=False)
    with Path('/tmp/corrector_native10_executor_status.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = storage.PACKAGE/'coordination/NATIVE10_EXECUTOR_STATUS.json'
        status = read(path)
        status['final_static_input_execution'] = record
        for key in ('updated_at', 'updated_at_utc', 'updated_utc'):
            status[key] = record['updated_utc']
        temporary = path.with_name(path.name+'.tmp.static.'+str(os.getpid()))
        temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2)+'\n')
        temporary.replace(path)
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record


def notify(message):
    records = []
    for thread in THREADS:
        try:
            process = subprocess.run(['/home/tiger/.local/bin/codex', 'queue', '--thread', thread,
                '--message', message], capture_output=True, text=True, timeout=45)
            records.append(dict(thread=thread, returncode=process.returncode,
                                output=process.stdout, error=process.stderr))
        except Exception as error:
            records.append(dict(thread=thread, error=repr(error)))
    storage.dump(HERE/('notification_'+str(time.time_ns())+'.json'), records)


def ledger_bytes():
    with storage.LOCK_PATH.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        return (ROOT/'budget/attempts.jsonl').read_bytes()


def run():
    if storage.sha256(PLAN) != 'a6c8318d7c12a4b6465bcfcd93880ef4d8811c86e1e17767197845123fc1cd6f':
        raise ValueError('Registered static execution plan changed')
    if storage.sha256(REVIEW) != 'b9da5d7c974027a5689259b663653969dfcc1ace8cf7dca1b2e8ba0b71256262':
        raise ValueError('Independent engineering review changed')
    plan = read(PLAN)
    review = read(REVIEW)
    if review['status'] != 'passed_engineering_synthetic_only':
        raise ValueError('Expected the independent engineering-only pass')
    for name, digest in review['evidence']['entrypoint_sha256'].items():
        if storage.sha256(name) != digest:
            raise ValueError('Reviewed execution implementation changed: '+name)
    if (HERE/'result.json').exists():
        raise FileExistsError('This one-shot chain has already completed')
    publish('waiting_for_all300_and_successful_wave_exit',
        engineering_review_sha256=storage.sha256(REVIEW), plan_sha256=storage.sha256(PLAN))
    deadline = time.monotonic()+86400
    while True:
        status = read(WATCH)
        if status.get('technical_problems'):
            raise RuntimeError('Collection reported technical problems; no automatic retry')
        if status.get('all_300_terminal') and status.get('launch_result') is not None:
            launch = status['launch_result']
            # launch_result is written only after the entire lifecycle command
            # returns; the bookkeeping launcher may still be exiting briefly.
            if launch.get('status') != 'complete' or launch.get('returncode') != 0:
                raise RuntimeError('All slots disposed but no successful lifecycle wave exit')
            break
        if not status.get('launch_process_alive') and status.get('launch_result') is not None:
            raise RuntimeError('Collection exited without all original slots disposed')
        if status.get('launch_process_alive') is False and not status.get('launch_result_pending'):
            raise RuntimeError('Collection launcher exited without a complete lifecycle result')
        if time.monotonic() >= deadline:
            raise TimeoutError('Collection completion wait exceeded one day')
        time.sleep(30)

    # Only the already-reviewed static modules are called below. Their own
    # full-wave gate precedes any round2 outcome/trajectory loading.
    from experiments.native10_training_20260916.round2_dataset_audit_v1 import run_audit
    from experiments.native10_training_20260916.final_input_bundle_v1 import create_bundle
    from experiments.native10_training_20260916.final_prepare_v1 import prepare
    from experiments.native10_training_20260916.final_fit_protocol_v1 import preview_specification

    before = ledger_bytes()
    start = time.perf_counter()
    timings = {}
    publish('static_round2_dataset_audit_running', terminal_primary_slots=300,
            runtime_snapshot_utc=status['updated_at'])
    collection = plan['round2_collection']
    begin = time.perf_counter()
    audited = run_audit(collection['config_path'], collection['freeze_path'], plan['wave_id'],
                        plan['new_dataset_version'], contract_path=Path(plan['contract']['path']))
    storage.dump(HERE/'round2_audit_binding.json', audited)
    timings['dataset_audit_seconds'] = time.perf_counter()-begin
    if audited['status'] != 'passed':
        raise RuntimeError('Static dataset audit incomplete; no bundle/model progression')
    result = read(Path(audited['path'])/'result.json')
    analysis_sources = dict(result['analysis_sources'])
    analysis_sources[result['contract']['path']] = result['contract']['sha256']
    publish('static_joint_bundle_running', round2_dataset_binding=audited['dataset_binding'])
    begin = time.perf_counter()
    bundle = create_bundle(plan['new_bundle_version'],
        round1_train=dict(dataset_binding=plan['original_train_binding'],
            collection=plan['original_collection'], bank_version='round1_labels_v1'),
        round2_train=dict(dataset_binding=audited['dataset_binding'], collection=collection,
            bank_version='round2_labels_v1', completion_audit=audited['completion_audit']),
        development=dict(dataset_binding=plan['original_development_binding'],
            collection=plan['original_collection'], bank_version='round1_labels_v1'),
        feature_contract=None, analysis_sources=analysis_sources)
    storage.dump(HERE/'input_bundle_binding.json', bundle)
    timings['bundle_seconds'] = time.perf_counter()-begin
    publish('pending_and_metadata_preview_running', input_bundle=bundle)
    begin = time.perf_counter()
    pending = prepare(bundle_binding=bundle, version=plan['new_pending_prepare_version'],
                      contract_path=Path(plan['contract']['path']))
    storage.dump(HERE/'pending_binding.json', pending)
    preview = preview_specification(bundle)
    preview_dir = ROOT/'final_previews/final_input_preview_v1'
    preview_dir.mkdir(parents=True, exist_ok=False)
    storage.dump(preview_dir/'metadata_preview.json', preview)
    storage.dump(preview_dir/'input_bundle_binding.json', bundle)
    storage.seal(preview_dir, role='native10_final_metadata_preview',
        specification_sha256=preview['specification_sha256'], model_calls=0, pca_fits=0,
        optimizer_updates=0, simulator_calls=0, real_model_stage_released=False)
    preview_binding = dict(path=str(preview_dir), seal_sha256=storage.sha256(preview_dir/'complete.json'),
        metadata_preview_sha256=storage.sha256(preview_dir/'metadata_preview.json'),
        specification_sha256=preview['specification_sha256'])
    storage.dump(HERE/'preview_binding.json', preview_binding)
    timings['pending_and_preview_seconds'] = time.perf_counter()-begin
    after = ledger_bytes()
    if after != before:
        raise RuntimeError('Formal resource ledger changed during zero-resource static chain')
    manifest = read(Path(bundle['path'])/'manifest.json')
    output = dict(status='static_inputs_complete_real_preflight_unreleased', finished_utc=now(),
        round2_audit=audited, input_bundle=bundle, pending=pending,
        specification_sha256=preview['specification_sha256'],
        metadata_preview=preview_binding,
        coverage=manifest['summary'], ledger_unchanged=True,
        ledger_sha256=hashlib.sha256(before).hexdigest(), ledger_record_count=len(before.splitlines()),
        model_calls=0, pca_fits=0, simulator_calls=0, optimizer_updates=0,
        real_model_preflight_executed=False, new_model_stage_started=False,
        wall_seconds=time.perf_counter()-start, timing_seconds=timings,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    storage.dump(HERE/'result.json', output)
    publish('static_inputs_complete_pending_real_preflight_ready',
        result_path=str(HERE/'result.json'), result_sha256=storage.sha256(HERE/'result.json'),
        input_bundle=bundle, specification_sha256=preview['specification_sha256'],
        coverage=manifest['summary'], wall_seconds=output['wall_seconds'])
    notify('执行端静态输入链完成（非真实模型预检）：round2 audit/dataset、600联合bundle、pending及metadata preview已生成；'
        f"specification SHA {preview['specification_sha256']}；bundle seal {bundle['seal_sha256']}；"
        f"证据 {HERE/'result.json'}，SHA {storage.sha256(HERE/'result.json')}。"
        '全部正式资源账本不变，PCA/init/model inference/opt/sim均0；真实0/0模型预检仍等独立READY。请分析端审查完整输入绑定。')


if __name__ == '__main__':
    os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    with Path('/tmp/corrector_native10_final_static_inputs_v1.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            run()
        except BaseException as error:
            record = publish('static_input_chain_failed_no_retry', error=repr(error), traceback=traceback.format_exc(),
                automatic_retry=False, existing_artifacts_preserved=True)
            storage.dump(HERE/'failure.json', record)
            notify('执行端静态输入链停止，未启动模型/优化/仿真；保留原数据和全部日志，不自动重试。'
                   f"错误：{error!r}；证据 {HERE/'failure.json'}。")
            raise
