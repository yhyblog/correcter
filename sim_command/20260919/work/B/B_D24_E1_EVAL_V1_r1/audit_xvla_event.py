"""Publish the completed X N event audit after a verified E1 handoff."""
import hashlib
from pathlib import Path
import d24_common as d


def ref(p):
    p=Path(p)
    return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def main():
    d.authorize(admission=True)
    eid='B_1e58b6736df1bff18f088f0623e00d90'
    wake=d.C/'persistent_queue/nodes/B/wakeup'
    event_path=wake/'outbox'/(eid+'.json')
    event=d.load(event_path)
    claim=d.load(event['claim_identity']['path'])
    assert ref(event['claim_identity']['path'])['sha256']==event['claim_identity']['sha256']
    assert ref(claim['config'])['sha256']==claim['config_sha256']
    assert not d.alive(claim['process'])
    terminal=d.load(event['result_path'])
    assert terminal['status']=='complete' and terminal['exit_code']==0
    assert terminal['all_owned_descendants_exited'] and terminal['occupancy_handoff_complete']
    batch=d.R/'D24_E1_EVAL_r1'
    registration=wake/'jobs/D24_E1_EVAL_r1__D24_E1_EVAL_r1__1.json'
    registered=d.load(registration)
    assert d.alive(registered['process_identity'])
    assert ref(registered['claim_identity']['path'])['sha256']==registered['claim_identity']['sha256']
    progress=d.load(batch/'PROGRESS.json')
    assert progress['status']=='running' and len(progress['active'])==8 and progress['auxiliary_gpus']==[]
    workers=[]
    cfg=d.load(d.W/'E1_EVAL_BATCH.json')
    for job in cfg['jobs']:
        out=Path(job['output'])
        process=d.load(out/'PROCESS.json')
        status=d.load(out/'status.json')
        episodes=[d.load(p) for p in out.glob('cells/*/EPISODE_PROGRESS.json')]
        assert d.alive(process) and status['status']=='running' and status['technical_failures']==0
        assert status['completed_episodes']>0 or any(x.get('step',0)>0 for x in episodes)
        loader=d.load(out/'policy_loader.json')
        assert not loader['errors'] and loader['file_calls'][0]['returned'] and loader['state_calls'][0]['returned']
        workers.append(dict(job_id=job['job_id'],gpu_assignment=job['gpus'],process=process,status=status,episode_progress=episodes))
    guard=d.load('/tmp/gpu_occupancy_guard/status.json')
    assert len(guard['gpus'])==8 and all(v['state']=='reserved' for v in guard['gpus'].values())
    observer=d.identity(452085)
    assert observer['start_ticks']==91710679
    handoff=dict(at_utc=d.utc(),supervisor=registered['process_identity'],registration=ref(registration),
        runner_progress=progress,workers=workers,observer=observer,guard=guard,
        holder_policy='all eight holders off for whole E1 wave; restored after all jobs including failures drain',
        no_duplicate_launch=True,planned_episodes=1200,planned_cells=24,A_waits_for_B=False,
        autonomous_scope='finite eight-worker queue; registered terminal callback to original B session',
        headless_after_terminal_closure='not newly certified by this run; existing same-thread callback is observed')
    d.exclusive(d.W/'STABLE_HANDOFF.json',handoff)
    root_control=d.load(d.C/'CONTROL.json');queue_control=d.load(d.C/'persistent_queue/CONTROL.json')
    summary_path=d.R/'D24_XVLA_N_r1/N_COMPLETE_SUMMARY.json';summary=d.load(summary_path)
    audit=dict(event_id=eid,task_id='B_D24_SPRINT_V1',run_id='D24_XVLA_N_r1',outcome='audited_complete',
        at_utc=d.utc(),event=ref(event_path),claim_verified=True,claim=event['claim_identity'],
        original_process_exited=True,result=ref(event['result_path']),summary=ref(summary_path),
        X_VLA_N=dict(episodes=500,successes=403,success_rate=.806,technical_failures=0,unknown=0),
        root_control=dict(revision=root_control['revision'],stop_requested=root_control['stop_requested']),
        queue_control=dict(revision=queue_control['revision'],global_stop=queue_control['global_stop'],B=queue_control['nodes']['B']),
        authorization_sha256=d.AUTH_SHA,task_board=ref(d.C/'TASK_BOARD.json'),
        decision='Preserve all completed X episodes. Start one new E1 evaluation batch under existing D24 authorization.',
        continuation_config=ref(d.W/'E1_EVAL_BATCH.json'),stable_handoff=ref(d.W/'STABLE_HANDOFF.json'),
        background=handoff,prior_N_gaps=dict(technical_failure_unresolved=5,unknown=5),
        remaining_stages=['E6 causal D5 development trace and threshold','Smol/X Post','LIBERO Post','external comparisons'],
        whole_sprint_complete=False,A_waits_for_B=False,
        occupancy_history_note='Completed X batch retains its original auxiliary-holder history; E1 uses latest explicit user whole-wave all-holder-off instruction')
    audit_path=d.C/'receipts/B/events'/(eid+'_AUDIT.json')
    d.exclusive(audit_path,audit)
    p=d.C/'receipts/B/B_D24_SPRINT_V1_RESULT.json';receipt=d.load(p)
    receipt.update(at_utc=d.utc(),status='running',E1_status='48 fits complete;24-cell Post/Velocity evaluation running on8GPUs',
        E1_evaluation_status='D24_E1_EVAL_r1 active,1200 planned episodes',
        E1_evaluation_configuration=str(d.W/'E1_EVAL_BATCH.json'),
        E1_evaluation_completed_at_snapshot=sum(w['status']['completed_episodes'] for w in workers),
        X_VLA_status='SFT complete at30000; fixed final checkpoint N evaluation500/500 complete',
        X_VLA_N_status='complete:403 successes/500 completed;zero technical failures',
        X_VLA_N_completed_at_snapshot=500,X_VLA_N_technical_failures_at_snapshot=0,
        X_VLA_N_summary=str(summary_path),X_VLA_status_at_utc=d.utc(),
        GPU_N_status='All admitted N batches terminal:1390/1400 complete;5 technical failures and5 unknown retained',
        N_incremental_summary=str(summary_path.parent/'ALL_N_SUMMARY.json'),
        N_incremental_csv=str(summary_path.parent/'ALL_N_SUMMARY.csv'),
        N_incremental_totals=dict(planned=1400,complete=1390,technical_failure_unresolved=5,unknown=5,unstarted=0,episode_claim_attempts=1401),
        current_queue_runs=['D24_E1_EVAL_r1'],all_completion_triggers_registered=True,
        stable_handoff=str(d.W/'STABLE_HANDOFF.json'),latest_event_audit=str(audit_path),
        latest_handoff_audit=str(audit_path),remaining_stages=audit['remaining_stages'])
    d.atomic(p,receipt)
    with (d.C/'receipts/B/B_D24_SPRINT_V1_REPORT.md').open('a') as f:
        f.write('\n\n## '+d.utc()+' X-VLA N callback audit and E1 continuation\n\n')
        f.write('X-VLA N completed500/500:403 successes (80.6%),zero technical failures. Frozen final30000-step checkpoint;49 training task labels/50 evaluation tasks disclosed. All N totals1390/1400;5 technical failures and5 unknown retained as missing.\n\n')
        f.write('E1 evaluation:24 settings (4 losses ×3 complete fit seeds ×Post/Velocity),same50 fixed five-task test sources,1200 planned episodes,eight resident workers. No new fit or completed-episode replay. All-card formal reservation suppresses all holders until the wave drains. Mesa renderer is shared across B E1 cells and differs from A NVIDIA EGL.\n\n')
        f.write('Audit: '+str(audit_path)+'\nHandoff: '+str(d.W/'STABLE_HANDOFF.json')+'\n')
    print(str(audit_path))


if __name__=='__main__':
    main()
