"""One-shot orchestration of the explicitly released final zero-update preflight."""
from pathlib import Path
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import time
import traceback

from experiments.native10_training_20260916 import storage
from experiments.native10_training_20260916 import final_fit_protocol_v1 as protocol
from experiments.native10_training_20260916 import final_fit_runner_v1 as runner

HERE = Path(__file__).resolve().parent
VERSION = 'final_preflight_v1'
READY_SHA = '684fa1d88290a68a64e21e898695a9271602e5bec0ecff7c707962ad625ff521'
SPEC_SHA = '08891c3ee6feb71aa41a8cfa7cb0fbed61930e16eb8938cf5bfeff1dd24ad946'
THREADS = ('01a0a551-9ed3-7f53-9f39-b60d8674819d', '01a09fc3-ff82-72e3-87ef-9e9f63a792ce')


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def publish(state, **extra):
    value = dict(state=state, updated_utc=now(), runner_pid=os.getpid(),
        control_directory=str(HERE), ready_version=9, ready_sha256=READY_SHA,
        specification_sha256=SPEC_SHA, simulator_attempts=0, optimizer_updates=0,
        formal_training_started=False, next_stage_automatically_started=False, **extra)
    storage.dump(HERE/'latest.json', value, exclusive=False)
    with Path('/tmp/corrector_native10_executor_status.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = storage.PACKAGE/'coordination/NATIVE10_EXECUTOR_STATUS.json'
        status = read(path)
        status.update(state=state, final_model_preflight_execution=value,
            latest_final_preflight_authorization_receipt=dict(version=9, sha256=READY_SHA, received_utc=value['updated_utc']),
            blocking_reason=None)
        for key in ('updated_at','updated_at_utc','updated_utc'):status[key]=value['updated_utc']
        temporary = path.with_name(path.name+'.tmp.final_preflight.'+str(os.getpid()))
        temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2)+'\n')
        temporary.replace(path)
    print(json.dumps(value, ensure_ascii=False), flush=True)


def notify(message):
    responses=[]
    for thread in THREADS:
        try:
            p=subprocess.run(['/home/tiger/.local/bin/codex','queue','--thread',thread,'--message',message],
                capture_output=True,text=True,timeout=45)
            responses.append(dict(thread=thread,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        except Exception as error:responses.append(dict(thread=thread,error=repr(error)))
    storage.dump(HERE/('notification_'+str(time.time_ns())+'.json'),responses)


def copy_checked(source, destination, expected):
    protocol.checked(source,expected)
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,destination)
    protocol.checked(destination,expected)


def main():
    # A persistent exclusive lock plus exclusive artifacts prevent duplicate execution.
    with (HERE/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (HERE/'started.json').exists():raise FileExistsError('One-shot preflight already started')
        started=now();begin=time.monotonic()
        storage.dump(HERE/'started.json',dict(started_utc=started,pid=os.getpid(),runner_sha256=storage.sha256(__file__)))
        live=storage.PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json'
        protocol.checked(live,READY_SHA);ready=read(live);release=protocol._release(ready,'preflight')
        if ready['version']!=9 or release['specification_sha256']!=SPEC_SHA:raise ValueError('Unexpected READY/specification')
        before=runner.ledger_snapshot()
        storage.dump(HERE/'ledger_before.json',runner._metadata(before))
        publish('final_preflight_v9_prepare_running',started_utc=started)

        # Bind review, decision, metadata preview and pending artifacts without
        # changing the science/input specification or any old dependency.
        evidence=HERE/'authorization';evidence.mkdir()
        refs={str(live):READY_SHA}
        for key in ('task_document','protocol_review'):
            refs[str(storage.PACKAGE/ready[key])]=ready[key+'_sha256']
        for key in ('analysis_decision','real_input_review','preview_spec_review','engineering_review',
                    'numerical_decision','implementation_brief','runtime_preparation_evidence',
                    'target_runtime_numerical_cpu_evidence','static_input_execution'):
            binding=release[key];refs[binding['path']]=binding['sha256']
        for source,digest in refs.items():
            source=Path(source)
            relative=Path('coordination')/source.name if source==live or source.name in (Path(ready['task_document']).name,Path(ready['protocol_review']).name) else Path('references')/source.relative_to(storage.PACKAGE)
            copy_checked(source,evidence/relative,digest)
        for key in ('metadata_preview','pending_specification'):
            binding=release[key];source=Path(binding['path'])
            seal=protocol.sealed(source,binding['seal_sha256'])
            copy_checked(source/'complete.json',evidence/key/'complete.json',binding['seal_sha256'])
            for name,digest in seal['files'].items():copy_checked(source/name,evidence/key/name,digest)
        copy_checked(Path(__file__),evidence/'runner.py',storage.sha256(__file__))
        storage.dump(evidence/'bindings.json',dict(ready_sha256=READY_SHA,specification_sha256=SPEC_SHA,
            original_references=refs,metadata_preview=release['metadata_preview'],pending_specification=release['pending_specification']))
        storage.seal(evidence,role='final_preflight_v9_supplemental_execution_evidence')
        inputs=read(storage.ROOT/'preparation/final_model_freeze_inputs_v1.json')
        cpu_evidence=inputs['cpu_evidence_argument_for_final_fit_protocol_prepare']+[
            dict(path=str(evidence),seal_sha256=storage.sha256(evidence/'complete.json'))]
        frozen=protocol.prepare(bundle_binding=release['input_bundle'],ready_path=evidence/'coordination/NATIVE10_ANALYSIS_READY.json',
            version=VERSION,mode='preflight',cpu_evidence=cpu_evidence)
        storage.dump(HERE/'protocol_binding.json',frozen)
        preparation_seconds=time.monotonic()-begin
        publish('final_real_model_preflight_running',started_utc=started,model_stage_start_utc=now(),
            protocol=frozen,preparation_seconds=preparation_seconds)
        notify('[final native10 preflight actual launch] READY v9条件已闭合，CPU真实零更新预检开始；config SHA '+frozen['config_sha256']+
            '；freeze '+frozen['freeze_sha256']+'；spec '+SPEC_SHA+'。PID '+str(os.getpid())+
            '；控制目录 '+str(HERE)+'。0sim/0optimizer，八卡holder保留；train方向诊断并行，不是新门槛，不启动fit。')
        result=runner.execute('preflight',config_path=frozen['config'],freeze_path=frozen['freeze'],version=VERSION)
        after=runner.ledger_snapshot()
        if before['raw']!=after['raw']:raise ValueError('Zero-update preflight modified resource ledger')
        storage.dump(HERE/'result.json',dict(status=result['status'],execution=result,
            protocol=frozen,started_utc=started,finished_utc=now(),preparation_seconds=preparation_seconds,
            total_wall_seconds=time.monotonic()-begin,resource_before=runner._metadata(before),resource_after=runner._metadata(after),
            ledger_byte_identical=True,next_stage_automatically_started=False))
        state='final_real_preflight_passed_pending_training_release' if result['status']=='passed' else 'final_real_preflight_pending_numerical_review'
        publish(state,started_utc=started,protocol=frozen,execution_path=result['path'],execution_seal_sha256=result['seal_sha256'],
            result_path=str(HERE/'result.json'),ledger_sha256=after['sha256'],total_wall_seconds=time.monotonic()-begin)
        notify('[final native10 preflight completed] status='+result['status']+'；执行封存 '+result['path']+
            ' SHA '+result['seal_sha256']+'；控制结果 '+str(HERE/'result.json')+
            '。账本逐字不变42,874sim/19,200opt；未启动正式fit。请审真实canonical/dense与8初态，root继续完整handoff。')


if __name__=='__main__':
    try:main()
    except BaseException as error:
        failure=dict(status='failed',utc=now(),error=repr(error),traceback=traceback.format_exc(),automatic_retry=False)
        storage.dump(HERE/('failure_'+str(time.time_ns())+'.json'),failure)
        publish('final_real_preflight_technical_failure',error=repr(error))
        notify('[final native10 preflight technical error] '+repr(error)+'；证据 '+str(HERE)+'；无自动重试或后续阶段。')
        raise
