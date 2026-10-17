"""Execute exactly one READY-v10-authorized final CPU fit from sealed assets."""
from pathlib import Path
from datetime import datetime, timezone
import fcntl
import json
import os
import shutil
import subprocess
import threading
import time
import traceback

from experiments.native10_training_20260916 import storage
from experiments.native10_training_20260916 import final_fit_protocol_v1 as protocol
from experiments.native10_training_20260916 import final_fit_runner_v1 as runner

HERE=Path(__file__).resolve().parent
VERSION='final_fit_v1'
READY_SHA='e44b37c380d50ce1bf88acc9f6c832fae1367b12fae0b0074076b269cce4938f'
SPEC_SHA='08891c3ee6feb71aa41a8cfa7cb0fbed61930e16eb8938cf5bfeff1dd24ad946'
THREADS=('01a0a551-9ed3-7f53-9f39-b60d8674819d','01a09fc3-ff82-72e3-87ef-9e9f63a792ce')
PUBLICATION_LOCK=threading.Lock()


def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text())


def publish(state,**extra):
    with PUBLICATION_LOCK:
        item=dict(state=state,updated_utc=now(),pid=os.getpid(),control_directory=str(HERE),
            ready_version=10,ready_sha256=READY_SHA,specification_sha256=SPEC_SHA,
            simulator_budget=0,optimizer_budget=32000,cpu_only=True,next_stage_automatically_started=False,**extra)
        storage.dump(HERE/'latest.json',item,exclusive=False)
        with Path('/tmp/corrector_native10_executor_status.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            p=storage.PACKAGE/'coordination/NATIVE10_EXECUTOR_STATUS.json';s=read(p)
            s.update(state=state,final_training=item,blocking_reason=None,
                latest_final_training_authorization_receipt=dict(version=10,sha256=READY_SHA),
                next_dependency='Complete the frozen final A/B fit and fixed checkpoint selection; policy/cal/held remain locked.')
            for key in ('updated_at','updated_at_utc','updated_utc'):s[key]=item['updated_utc']
            totals=item.get('resource_totals')
            if totals:
                s.update(global_simulator_attempts=totals.get('simulator_attempts',0),
                    optimizer_updates=totals.get('training_updates',0),actual_optimizer_updates=totals.get('training_updates',0))
                s.setdefault('current_resources',{}).update(totals)
            tmp=p.with_name(p.name+'.tmp.finalfit.'+str(os.getpid()));tmp.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
        print(json.dumps(item,ensure_ascii=False),flush=True)


def notify(message):
    records=[]
    for thread in THREADS:
        try:
            p=subprocess.run(['/home/tiger/.local/bin/codex','queue','--thread',thread,'--message',message],capture_output=True,text=True,timeout=45)
            records.append(dict(thread=thread,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        except Exception as error:records.append(dict(thread=thread,error=repr(error)))
    storage.dump(HERE/('notification_'+str(time.time_ns())+'.json'),records)


def copy(source,destination,digest):
    protocol.checked(source,digest);destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,destination);protocol.checked(destination,digest)


def watch(stop,frozen,started):
    while not stop.wait(30):
        try:
            snapshot=runner.ledger_snapshot()
            count=snapshot['stages'].get('training_final',{}).get('training_updates',0)
            models=storage.ROOT/'models/final'/VERSION
            complete_members=sorted(str(p.relative_to(models)) for p in models.glob('*/member_*/fit.json'))
            publish('final_training_running' if count else 'final_fit_verifying_sealed_inputs',started_utc=started,
                protocol=frozen,optimizer_updates_this_stage=count,resource_totals=snapshot['totals'],
                input_registration_exists=(models/'registration.json').exists(),complete_member_records=complete_members,
                intermediate_development_results_inspected=False)
        except Exception as error:
            # Monitoring is not the permission gate; the frozen runner owns it.
            storage.dump(HERE/('monitor_error_'+str(time.time_ns())+'.json'),dict(utc=now(),error=repr(error)))


def main():
    with (HERE/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (HERE/'started.json').exists():raise FileExistsError('Final fit already launched')
        started=now();start=time.monotonic()
        live=storage.PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json'
        protocol.checked(live,READY_SHA);ready=read(live);release=protocol._release(ready,'fit')
        assert ready['version']==10 and release['specification_sha256']==SPEC_SHA
        before=runner.ledger_snapshot()
        assert before['totals']==dict(simulator_attempts=42874,training_updates=19200)
        assert before['stages'].get('training_final',{}).get('training_updates',0)==0
        storage.dump(HERE/'started.json',dict(started_utc=started,pid=os.getpid(),runner_sha256=storage.sha256(__file__)))
        publish('final_fit_v10_prepare_running',started_utc=started,resource_totals=before['totals'])
        evidence=HERE/'authorization';evidence.mkdir()
        refs={str(live):READY_SHA}
        for key in ('task_document','protocol_review'):
            refs[str(storage.PACKAGE/ready[key])]=ready[key+'_sha256']
        for key in ('analysis_decision','independent_preflight_review','resource_completion_review'):
            b=release[key];refs[b['path']]=b['sha256']
        refs[str(storage.PACKAGE/ready['final_numerical_decision'])]=ready['final_numerical_decision_sha256']
        for source,digest in refs.items():
            source=Path(source)
            relative=Path('coordination')/source.name if source==live or source.name in (Path(ready['task_document']).name,Path(ready['protocol_review']).name) else Path('references')/source.relative_to(storage.PACKAGE)
            copy(source,evidence/relative,digest)
        copy(Path(__file__),evidence/'runner.py',storage.sha256(__file__))
        storage.dump(evidence/'bindings.json',dict(original_references=refs,preflight=release['preflight'],specification_sha256=SPEC_SHA))
        storage.seal(evidence,role='final_fit_v10_supplemental_execution_evidence')
        cpu=read(storage.ROOT/'preparation/final_model_freeze_inputs_v1.json')['cpu_evidence_argument_for_final_fit_protocol_prepare']
        cpu=cpu+[dict(path=str(evidence),seal_sha256=storage.sha256(evidence/'complete.json'))]
        frozen=protocol.prepare(bundle_binding=release['input_bundle'],ready_path=evidence/'coordination/NATIVE10_ANALYSIS_READY.json',
            version=VERSION,mode='fit',preflight_binding=release['preflight'],cpu_evidence=cpu)
        storage.dump(HERE/'protocol_binding.json',frozen)
        prepare_seconds=time.monotonic()-start
        publish('final_fit_verifying_sealed_inputs',started_utc=started,protocol=frozen,preparation_seconds=prepare_seconds,
            optimizer_updates_this_stage=0,resource_totals=before['totals'])
        notify('[native10 final fit actual launch] READY v10授权已核；CPU两线程A/B各4×4000，32000更新上限/0sim；只加载已封存prefit，不重拟PCA/初始化。PID '+str(os.getpid())+
            '；config '+frozen['config_sha256']+'；freeze '+frozen['freeze_sha256']+'；控制目录 '+str(HERE)+
            '。入口已启动，当前先核输入/初态，optimizer仍0；8holder保留，不读中途dev挑赢家，policy/cal/held未启动。')
        stop=threading.Event();monitor=threading.Thread(target=watch,args=(stop,frozen,started),daemon=True);monitor.start()
        try:result=runner.execute('fit',config_path=frozen['config'],freeze_path=frozen['freeze'],version=VERSION)
        finally:stop.set();monitor.join()
        after=runner.ledger_snapshot()
        assert after['totals']==dict(simulator_attempts=42874,training_updates=51200)
        assert result['resources']['optimizer_updates']==32000 and result['resources']['simulator_attempts']==0
        model=storage.ROOT/'models/final'/VERSION
        storage.dump(HERE/'result.json',dict(status=result['status'],execution_path=result['path'],execution_seal_sha256=result['seal_sha256'],
            model_path=str(model),model_seal_sha256=storage.sha256(model/'complete.json'),protocol=frozen,
            started_utc=started,finished_utc=now(),total_wall_seconds=time.monotonic()-start,prepare_seconds=prepare_seconds,
            resource_before=runner._metadata(before),resource_after=runner._metadata(after),next_stage_automatically_started=False))
        publish('final_training_complete_pending_analysis_review',started_utc=started,protocol=frozen,
            model_path=str(model),model_seal_sha256=storage.sha256(model/'complete.json'),
            execution_path=result['path'],execution_seal_sha256=result['seal_sha256'],
            optimizer_updates_this_stage=32000,resource_totals=after['totals'])
        notify('[native10 final fit completed] 固定A/B最终fit已complete，32000新更新/0sim，global42874sim/51200opt。产物 '+str(model)+
            ' seal '+storage.sha256(model/'complete.json')+'；执行receipt '+result['path']+'；selected及reload审计已完成，请分析端审查。'+
            'root继续整理完整handoff，不自动开启policy/cal/held。')


if __name__=='__main__':
    try:main()
    except BaseException as error:
        storage.dump(HERE/('failure_'+str(time.time_ns())+'.json'),dict(status='failed',utc=now(),error=repr(error),traceback=traceback.format_exc(),counted_updates_preserved=True,automatic_retry=False))
        publish('final_training_technical_failure',error=repr(error))
        notify('[native10 final fit technical error] '+repr(error)+'；证据 '+str(HERE)+'；保留账本，无自动重试或下一阶段。')
        raise
