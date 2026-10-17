"""CPU-only event audit; never calls queue start, repair publication or GPU tools."""
import csv,json,hashlib,collections,datetime,socket,time
from pathlib import Path
import queue_common as q
from inventory import allowed_units
from selection_bridge import locked_post_choice
EID='C_a2a963ba799b5b6e2c207d603c250443'
A=q.ROOT/'event_audits'/EID
A.mkdir(parents=True,exist_ok=True)

def dump(name,value):q.new_json(A/name,value)
def table(name,rows):
    rows=list(rows);keys=list(dict.fromkeys(k for r in rows for k in r))
    with (A/name).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def verify(row):return q.verify(row,base=q.C)
def scalar(row):return {k:v for k,v in row.items() if isinstance(v,(str,int,float,bool,type(None)))}

def main():
    event_path=q.C/'persistent_queue/nodes/C/wakeup/outbox'/(EID+'.json');event=q.read(event_path)
    assert event['event_id']==EID and event['job']['task_id']==q.TASK and event['synthetic'] is False
    assert event['hostname']==socket.gethostname() and event['executor_thread_id']=='01a0c793-10d2-7791-a250-fd65d88e1ccb'
    verify(event['job']['claim_identity']);claim=q.read(q.ROOT/'CLAIM.json');result=q.read(event['job']['result_path']);ready=q.read(q.ROOT/'QUOTA_INDEPENDENT_READY.json')
    assert result==event['result'] and claim['process']==event['job']['process_identity'] and claim['CPU_only'] is True
    assert claim['authorization_sha256']==q.AUTH_SHA and q.sha(q.AUTH)==q.AUTH_SHA
    assert result['continuations']==[] and not list((q.ROOT/'continuations').glob('*.json'))
    assert result['new_scientific_units']==0 and result['new_training_updates']==0
    assert not q.live(claim['process'])
    references={}
    for key in ['CPU_check','authorization','event_ACK','native_cached_validator_real_recovery','consumed_X_selection','consumed_pi05_selection','consumed_pi05_transfer','runtime','selection','selection_lock']:
        verify(ready[key]);references[key]=ready[key]
    for key in ['admission','repair_policy','source_inventory','supervisor']:
        verify(ready['retry_and_skip'][key]);references['retry_'+key]=ready['retry_and_skip'][key]
    selection=locked_post_choice();assert selection['chosen_loss']=='L01'
    summary=[];all_rows=[];all_cells=[];all_pairs=[];protected=[]
    for root,expected_count in [(q.X,1000),(q.P,2000)]:
        is_x=root==q.X;dest=q.ROOT/'tables'/root.name
        terminal=q.read(root/'RESULT.json');family=q.family(root)
        assert family['exited'] and terminal['status']=='complete' and terminal['all_owned_descendants_exited'] and terminal['occupancy_handoff_complete']
        original_claim=q.ref(root/'CLAIM.json');protected.append(original_claim)
        if is_x:assert original_claim['sha256']==ready['stages'][0]['claim']['sha256']
        consumed=q.read(root/'SELECTION_CONSUMED.json');assert consumed['chosen_loss']=='L01' and consumed['fixed_fit_seed']==9101
        assert consumed['A_selection']['sha256']==selection['selection_ref']['sha256']
        original=list(csv.DictReader((root/'FINAL_EPISODES.csv').open()))
        original_by_id={(r['method']+'/'+r['source_id'] if is_x else r['unit_id']):r for r in original}
        assert len(original_by_id)==len(original)==expected_count
        rows=list(csv.DictReader((dest/'SOURCE_TERMINALS.csv').open()));byid={r['unit_id']:r for r in rows}
        assert len(rows)==len(byid)==expected_count and set(byid)==set(original_by_id)
        expected={}
        if is_x:
            sources=q.read(root/'config/TEST_SOURCES.json')['sources']
            for m in ('Post','Velocity'):
                for source in sources:expected[m+'/'+source['source_id']]=dict(source=source,H=10,method=m)
        else:
            index=q.read(root/'JOB_INDEX.json')
            for entry in index['jobs']:
                job=q.read(verify(entry))
                for source in job['sources']:
                    uid=job['cell_id']+'__'+source['source_id'];assert uid not in expected
                    expected[uid]=dict(source=source,H=job['H'],method=job['method'])
        assert set(expected)==set(byid)
        claimdir=root/('claims/attempts' if is_x else 'unit_claims')
        claim_records=[q.read(p) for p in claimdir.glob('*.json')]
        claimmap={r['identity'] if is_x else r['unit_id']:r for r in claim_records}
        assert len(claimmap)==len(claim_records)==expected_count and set(claimmap)==set(expected)
        ordinals=[r['number'] if is_x else r['stage_ordinal'] for r in claim_records]
        assert sorted(ordinals)==list(range(1,expected_count+1))
        assert not list((root/'quota_attempt_lineage').glob('*.json'))
        counter=q.read(root/'ATTEMPT_COUNTER.json')
        assert counter['reserved_attempts' if is_x else 'count']==expected_count
        for uid,r in byid.items():
            old=original_by_id[uid];definition=expected[uid];c=claimmap[uid]
            assert r['status']=='complete' and r['success'] in ('True','False') and r['attempts']=='1'
            assert all(r[k]==old[k] for k in ['source_id','task','method','status','success','result_path'])
            assert r['source_id']==definition['source']['source_id'] and r['method']==definition['method']
            for k in ('policy_seed','reset_seed' if is_x else 'env_seed'):assert int(old[k])==definition['source'][k]
            if not is_x:assert c['source']==definition['source'] and c['H']==definition['H'] and c['retry'] is False
            normal_H=definition['H'];raw_length=30 if is_x else 50
            all_rows.append(dict(**r,science_task=root.name,model='X-VLA' if is_x else 'pi05',legacy_H=r['H'],legacy_cell_id=r['cell_id'],normal_H=normal_H,raw_plan_length=raw_length,commitment_C=10,Q_loss='L01',Q_fit_seed=9101,original_scope_historical=True,current_paper_at_audit=False,table_role='historical_L01_Post' if r['method']=='Post' else 'historical_L01_Velocity_other_work'))
        cells=list(csv.DictReader((dest/'CELLS.csv').open()))
        for cell in cells:
            rs=[r for r in rows if r['cell_id']==cell['cell_id']]
            assert len(rs)==500==int(cell['planned'])==int(cell['valid']) and sum(r['success']=='True' for r in rs)==int(cell['successes'])
            assert int(cell['technical'])==int(cell['unknown'])==int(cell['unstarted'])==0
            assert abs(float(cell['success_rate'])-int(cell['successes'])/500)<1e-12
            all_cells.append(dict(**cell,science_task=root.name,model='X-VLA' if is_x else 'pi05',legacy_H=cell['H'],normal_H=10 if is_x else int(cell['H']),raw_plan_length=30 if is_x else 50,commitment_C=10,Q_loss='L01',Q_fit_seed=9101,current_paper_at_audit=False))
        missing=list(csv.DictReader((dest/'MISSING.csv').open()));assert not missing
        for pair in csv.DictReader((dest/'PAIRED.csv').open()):
            assert pair['missing_imputed']=='False' and int(pair['paired_valid'])<=500
            all_pairs.append(dict(**pair,science_task=root.name,legacy_H=pair['H'],normal_H=10 if is_x else int(pair['H']),Q_loss='L01',current_paper_at_audit=False))
        stats=q.read(dest/'SUMMARY.json');assert stats['expected']==stats['valid']==stats['claim_attempts']==expected_count and stats['missing']==0
        costs=q.read(dest/'ALL_ATTEMPT_COSTS.json');attempts=costs['attempts'];assert len(attempts)==expected_count and len({r['unit_id'] for r in attempts})==expected_count
        assert costs['unknown_costs_not_imputed'] is True
        assert all(r['status']=='complete' and type(r['success']) is bool for r in attempts)
        marker=q.read(q.ROOT/'exports'/(root.name+'.json'));assert marker['exit_code']==0 and marker['blocks_next_stage'] is False
        waves=terminal.get('waves') or [terminal.get('wave')] if terminal.get('waves') or terminal.get('wave') else [q.read(root/'chains/evaluate/RESULT.json')]
        assert all(w['cleanup']['status']=='all_formal_group_members_exited' and w['restoration']['status']=='occupancy_resolved' for w in waves)
        summary.append(dict(task_id=root.name,valid=expected_count,successes=sum(r['success']=='True' for r in rows),legal_task_failures=sum(r['success']=='False' for r in rows),unknown=0,technical=0,attempts=expected_count,unique_ordinal_count=len(set(ordinals)),corrected_retries=0,original_claim=original_claim,original_counter=q.ref(root/'ATTEMPT_COUNTER.json'),actual_family_exit=family,selection=q.ref(root/'SELECTION_CONSUMED.json'),tables=q.ref(dest/'SUMMARY.json'),all_attempt_costs=q.ref(dest/'ALL_ATTEMPT_COSTS.json'),export=marker,prior_holder_restoration_verified=True))
    # Pure functions only: no fault publication, repairs, process kills, or GPU work.
    units=[dict(unit_id='unentered',prior_attempts=0),dict(unit_id='unknown',prior_attempts=1),dict(unit_id='io_once',prior_attempts=1),dict(unit_id='io_twice',prior_attempts=2)]
    fault=dict(error='[Errno 5] transient',traceback='qio.py new_json')
    allowed,deferred=allowed_units(dict(remaining=units,states={'io_once':fault,'io_twice':fault}),True,True)
    assert {r['unit_id'] for r in allowed}=={'unentered','io_once'} and {r['unit_id'] for r in deferred}=={'unknown','io_twice'}
    fix=dict(change='CPU fixture only',evidence=['synthetic fixture, never an experiment'],science_changed=False)
    for success in (True,False):
        try:q.policy.validate_repair(dict(attempted_repairs=[]),fix,['done'],{'done':dict(status='complete',success=success)},1,family_exited=True)
        except ValueError:pass
        else:raise AssertionError('legal terminal accepted for replay')
    issue=dict(issue_id='cpu-fixture',status='reported',reported_at_unix=0,analysis_response_due_unix=1800)
    assert q.policy.advance_issue(issue,dict(status='ACK'),1799)['status']=='reported'
    expired=q.policy.advance_issue(issue,dict(status='ACK'),1800);assert expired['status']=='blocked_deferred' and expired['analysis_response_due_unix']==1800
    logic=dict(utc=q.utc(),CPU_only=True,passed=True,valid_true_and_false_protected=True,unknown_admitted_not_retried=True,one_evidenced_transient_IO_retry_only=True,attempt2_not_retried=True,ACK_does_not_reset_1800s=True,actual_GPU_fault_injection=False,automatic_continuations_observed=0,limits='Only predefined corrections were CPU-verified; no claim of arbitrary autonomous bug repair.')
    dump('CPU_LOGIC_CHECK.json',logic)
    current=q.C/'results/C/C_D24_CROSSBASE_H_SWEEP_V1';current_claim=q.read(current/'CLAIM.json');heart=q.read(current/'HEARTBEAT.json');current_identity=current_claim['process']
    assert q.live(current_identity) and heart['process']==current_identity
    assert current_claim['authorization_sha256']=='4f8406e67e2d0b73beda277b3bc633749060f30e8420e8513285780a06952c5f'
    current_registration=q.read(q.C/'persistent_queue/nodes/C/wakeup/jobs/D24_C_CROSSBASE_H_SWEEP_r1.json');assert current_registration['process_identity']==current_identity
    progress={k:v for k,v in (heart.get('progress') or {}).items() if k!='workers'}
    guard=q.read('/tmp/gpu_occupancy_guard/status.json');assert time.time()-guard['updated']<30 and len(guard['gpus'])==8 and all(v['state']=='reserved' for v in guard['gpus'].values())
    live=dict(utc=q.utc(),current_claim=q.ref(current/'CLAIM.json'),original_scientific_owner_preserved=current_identity,actual_owner_alive=True,heartbeat_utc=heart['utc'],heartbeat_status=heart['status'],progress=progress,claim_counter_snapshot=q.read(current/'ATTEMPT_COUNTER.json'),cached_guard=guard,guard_is_not_new_GPU_probe=True,notification_registered=True,stable_handoff=q.ref(current/'STABLE_HANDOFF.json'),new_grant_cutoff='2026-09-23T14:45:00Z',old_CPU_cutoff_does_not_limit_new_grant=True,healthy_scientific_processes_restarted=0,current_queue_code_changed=False)
    dump('CURRENT_QUEUE_UNCHANGED.json',live)
    table('AUDITED_SOURCE_TERMINALS.csv',all_rows);table('AUDITED_CELLS.csv',all_cells);table('AUDITED_PAIRS.csv',all_pairs)
    annotation=dict(utc=q.utc(),task_id=q.TASK,event_id=EID,original_tables_preserved=True,corrected_views=str(A),corrections=[dict(scope='X old quota CPU tables',legacy_H=30,raw_plan_length=30,normal_H=10,commitment_C=10,reason='Original native controller restores native_K=10; H30 label denotes raw chunk, not this new H30 sweep.'),dict(scope='Both original scientific tasks',Q_loss='L01',Q_fit_seed=9101,current_paper_at_audit=False,reason='Historical Post-only selected L01 outputs; later user-selected L11 publication supersedes current-paper labels. Do not overwrite historical results.')],active_science_unchanged=True)
    dump('TABLE_SEMANTICS.json',annotation)
    q.new_json(q.ROOT/'AUDITED_TABLE_INDEX.json',dict(event_id=EID,utc=q.utc(),audited_cells=str(A/'AUDITED_CELLS.csv'),audited_sources=str(A/'AUDITED_SOURCE_TERMINALS.csv'),audited_pairs=str(A/'AUDITED_PAIRS.csv'),semantics=q.ref(A/'TABLE_SEMANTICS.json'),legacy_tables_immutable=True))
    # No live process or shared control mutation; references still match.
    for item in protected:verify(item)
    audit=dict(utc=q.utc(),event_id=EID,task_id=q.TASK,status='audited_CPU_supervision_terminal',event=q.ref(event_path),CPU_claim=q.ref(q.ROOT/'CLAIM.json'),CPU_result=q.ref(q.ROOT/'RESULT.json'),CPU_owner_exited=True,CPU_exit_reason='original scope complete and original 2026-09-23T12:00:00Z admission cutoff reached',referenced_evidence=references,scientific_scopes=summary,total_valid=3000,total_original_attempts=3000,automatic_continuations=0,legal_terminal_replays=0,unknown_imputed_as_failure=0,Post_only_selection_lock_valid=True,historical_loss='L01',fixed_fit_seed=9101,background_transition='Original X1000 valid/family exit -> same pi05 waiter advanced to H40/H50 2000 without LLM/ACK gate; existing timestamped runtime proof reused',CPU_logic=q.ref(A/'CPU_LOGIC_CHECK.json'),CPU_table_semantics_corrected=q.ref(A/'TABLE_SEMANTICS.json'),current_queue=q.ref(A/'CURRENT_QUEUE_UNCHANGED.json'),scientific_compute_added_by_this_callback=0,new_GPU_calls_by_this_callback=0,training_updates_added=0,healthy_scientific_process_restarts=0,new_wakeup_events_emitted=0,callback_completion_does_not_emit_event=True,limitations=['Prior readiness actual_alive fields are timestamped historical snapshots, not current liveness.','Only encoded recovery branches were CPU checked; no GPU failure was injected.','CPU table evidence was joined to frozen source/job manifests, per-unit claims and original final tables; no historical model rerun.'])
    dump('AUDIT.json',audit)
    (A/'AUDIT.md').write_text('''# C CPU 自动队列终局审计

事件 `C_a2a963ba799b5b6e2c207d603c250443` 已核对。旧 CPU 监督器在原范围完成且 12:00 UTC 截止后正常退出。

- 原 X Post/Velocity 1000 条、π0.5 H40/H50 Post/Velocity 2000 条均有唯一合法终局和一次 claim；未知与技术缺项为 0，修正接续为 0。
- 原科学 claim、Post-only L01/fit9101 锁、自动阶段衔接、正式家族退出及当时 holder 恢复证据一致。原状态记录保留，未重放任何合法结果。
- 定向纯 CPU 检查确认合法成功/失败均禁止重试、未知不自动重试、只有一次有依据的 I/O 修正重试、普通 ACK 不重置 1800 秒期限。未注入 GPU 故障。
- 已增加清楚标注的 CPU 派生表：旧 X 表 H30 是 raw chunk30，normal_H 为 10；原 L01 结果属于历史版本，不应被当前 L11 论文数据入口误读。原表与 raw 不改写。
- 当前 `C_D24_CROSSBASE_H_SWEEP_V1` 保持原 claim 和健康后台队列，使用其独立新授权与 14:45 UTC 准入截止。当前八卡 reserved，正式整波 holder 停算。

本回调新增 GPU 调用、科学单元、训练、队列重启和唤醒事件均为 0。详见 AUDIT.json；当前活性快照见 CURRENT_QUEUE_UNCHANGED.json。
''')
    print(json.dumps(dict(audit=str(A/'AUDIT.json'),valid=3000,continuations=0,current_queue=progress,CPU_table_semantics_repaired=True),ensure_ascii=False))
if __name__=='__main__':main()
