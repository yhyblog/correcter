"""Finalize the E1 r1 audit once the diagnosed repair has stable progress."""
from pathlib import Path
import hashlib
import d24_common as d


def ref(p):
    p=Path(p)
    return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def main():
    d.authorize(admission=True)
    eid='B_8bef6b4d53d13f423eb70d8f1c939974'
    wake=d.C/'persistent_queue/nodes/B/wakeup'
    event_path=wake/'outbox'/(eid+'.json')
    event=d.load(event_path)
    assert ref(event['claim_identity']['path'])['sha256']==event['claim_identity']['sha256']
    claim=d.load(event['claim_identity']['path'])
    assert not d.alive(claim['process'])
    assert ref(claim['config'])['sha256']==claim['config_sha256']
    old_cfg=d.load(claim['config'])
    assert all(not d.alive(d.load(Path(j['output'])/'PROCESS.json')) for j in old_cfg['jobs'])
    terminal=d.load(event['result_path'])
    assert terminal['status']=='complete' and terminal['all_owned_descendants_exited'] and terminal['occupancy_handoff_complete']
    batch=d.R/'D24_E1_RENDER_REPAIR_r3'
    registration=wake/'jobs/D24_E1_RENDER_REPAIR_r3__D24_E1_RENDER_REPAIR_r3__1.json'
    registered=d.load(registration)
    assert d.alive(registered['process_identity'])
    assert ref(registered['claim_identity']['path'])['sha256']==registered['claim_identity']['sha256']
    progress=d.load(batch/'PROGRESS.json')
    assert progress['status']=='running' and len(progress['active'])==8 and not progress['auxiliary_gpus']
    workers=[]
    for job in d.load(d.W/'E1_RENDER_REPAIR_BATCH_r3.json')['jobs']:
        out=Path(job['output']);status=d.load(out/'status.json');process=d.load(out/'PROCESS.json')
        ep_progress=[d.load(p) for p in out.glob('cells/*/EPISODE_PROGRESS.json')]
        assert d.alive(process) and status['status']=='running' and status['technical_failures']==0
        assert status['completed_episodes']>0 or any(v.get('step',0)>0 for v in ep_progress)
        workers.append(dict(job_id=job['job_id'],GPU=job['gpus'],process=process,status=status,episode_progress=ep_progress))
    guard=d.load('/tmp/gpu_occupancy_guard/status.json')
    assert len(guard['gpus'])==8 and all(v['state']=='reserved' for v in guard['gpus'].values())
    observer=d.identity(452085);assert observer['start_ticks']==91710679
    handoff=dict(at_utc=d.utc(),run='D24_E1_RENDER_REPAIR_r3',registered_trigger=ref(registration),
        supervisor=registered['process_identity'],progress=progress,workers=workers,guard=guard,observer=observer,
        planned_corrected_attempts=1120,valid_original_rows_preserved=80,
        all_holder_computation_disabled_until_whole_wave_drains=True,
        future_terminal_event='original B executor; durable observer registration',
        headless_after_terminal_closure='not independently newly certified',A_waits_for_B=False)
    d.exclusive(d.W/'STABLE_HANDOFF.json',handoff)
    audit=dict(event_id=eid,outcome='audited_complete',at_utc=d.utc(),task_id='B_D24_SPRINT_V1',run_id='D24_E1_EVAL_r1',
        audit_scope='terminal event audited; original scientific validity is partial, corrected continuation active',
        original_event=ref(event_path),claim_verified=True,original_claim=event['claim_identity'],
        terminal_result=ref(event['result_path']),original_process_family_exited=True,
        control=dict(root_revision=d.load(d.C/'CONTROL.json')['revision'],queue_revision=d.load(d.C/'persistent_queue/CONTROL.json')['revision'],
                     authorization_sha256=d.AUTH_SHA,task_board=ref(d.C/'TASK_BOARD.json')),
        original_reported_completed_episodes=1200,scientifically_valid_retained=80,technical_invalid=1120,
        invalid_outcomes_excluded=True,original_artifacts_preserved=True,
        anomaly='Legacy EGL/MuJoCo render-resource lifetime: black RGB after first environment close; worker did not detect it.',
        diagnosis=ref(d.W/'MESA_LIFECYCLE_DIAGNOSIS_ORIGINAL.json'),fixed_check=ref(d.W/'MESA_LIFECYCLE_FIXED_CHECK.json'),
        dispositions=ref(d.W/'DISPOSITIONS.json'),audited_summary=ref(d.R/'D24_E1_EVAL_r1/E1_AUDITED_PARTIAL_SUMMARY.json'),
        correction='B-private context-safe release and per-render binding; black RGB now fails closed',
        pre_scientific_handoff_failure=ref(d.W/'HANDOFF_r2_DIAGNOSIS.json'),
        retry_authority='D24 one corrected engineering retry;1120 structural invalid episodes only;80 valid episodes excluded',
        repair_config=ref(d.W/'E1_RENDER_REPAIR_BATCH_r3.json'),model_seeds_sources_scientific_parameters_unchanged=True,
        background_handoff=ref(d.W/'STABLE_HANDOFF.json'),background=handoff,
        E1_science_complete=False,whole_sprint_complete=False,A_waits_for_B=False)
    audit_path=d.C/'receipts/B/events'/(eid+'_AUDIT.json');d.exclusive(audit_path,audit)
    p=d.C/'receipts/B/B_D24_SPRINT_V1_RESULT.json';receipt=d.load(p)
    done=sum(w['status']['completed_episodes'] for w in workers)
    receipt.update(at_utc=d.utc(),status='running',latest_event_audit=str(audit_path),latest_handoff_audit=str(audit_path),
        stable_handoff=str(d.W/'STABLE_HANDOFF.json'),E1_repair_completed_at_snapshot=done,
        E1_evaluation_completed_at_snapshot=80+done,E1_repair_technical_failures_at_snapshot=0,
        E1_evaluation_status='r1:80 valid retained/1120 technical invalid; r2 corrected retry active on8GPUs',
        E1_evaluation_configuration=str(d.W/'E1_RENDER_REPAIR_BATCH_r3.json'),
        current_queue_runs=['D24_E1_RENDER_REPAIR_r3'],all_completion_triggers_registered=True)
    d.atomic(p,receipt)
    print(str(audit_path))


if __name__=='__main__':
    main()
