"""Synthetic CPU tests only; never invokes real Codex or GPU code."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import wakeup as w


class WakeupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.state=Path(self.tmp.name)
        for d in ['outbox','delivery','handler_acks','handler_claims','handled','jobs','dependency_changes']:(self.state/d).mkdir()
        self.job=dict(job_id='fixture_wave',task_id='fixture_B_task',run_id='fixture_001',revision=1,attempt=1,
            claim_identity='synthetic',result_path=str(self.state/'result.json'),armed_from_turn_id='old')
        self.proc=Mock(pid=12345);self.proc.poll.return_value=0
        self.patches=[patch.object(w,'STATE',self.state),patch.object(w,'authority',return_value={}),
            patch.object(w,'thread_profile',return_value={}),patch.object(w,'identity',return_value=dict(pid=12345,synthetic=True))]
        for p in self.patches:p.start()
        w.TRANSPORTS.clear()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup();w.TRANSPORTS.clear()
    def event(self,**kwargs):return w.emit(self.state,self.job,'synthetic_callback','terminal',synthetic=True,**kwargs)

    def test_event_stable_batch_identity_and_optional_terminal_state(self):
        e=self.event(extra=dict(exit_code=7,process_family_exited=True))
        second=self.event(extra=dict(exit_code=0,process_family_exited=False))
        self.assertEqual(e,second);self.assertEqual(e['exit_code'],7)
        self.assertEqual(len(list((self.state/'outbox').iterdir())),1)

    def test_busy_thread_and_offline_single_writer_gates(self):
        self.assertIsNone(w.transport_choice({'status':'inProgress'},True)[0])
        self.assertIsNone(w.transport_choice({'status':'inProgress'},False)[0])
        self.assertIsNone(w.transport_choice({'status':'completed'},True,'exec_resume')[0])
        self.assertEqual(w.transport_choice({'status':'completed'},True)[0],'queue')
        self.assertEqual(w.transport_choice({'status':'completed'},False)[0],'exec_resume')

    def test_disappeared_process_is_unknown_and_failure_not_success(self):
        self.assertEqual(w.terminal_job(self.job,False,None),'execution_unknown')
        self.assertEqual(w.terminal_job(self.job,False,{'status':'failed'}),'failed')
        self.assertIsNone(w.terminal_job(self.job,True,{'status':'complete'}))
        self.assertEqual(w.terminal_job(self.job,False,{'status':'partial'}),'partial')

    def test_transport_receipt_is_not_ACK_and_no_duplicate_dispatch(self):
        e=self.event();turn={'turn_id':'new','status':'completed'}
        with patch.object(w.subprocess,'Popen',return_value=self.proc) as spawn:
            w.dispatch(self.state,e,turn,True);w.reconcile_transports(self.state)
            self.assertEqual(w.dispatch(self.state,e,turn,True),'transport_accepted')
            self.assertEqual(spawn.call_count,1)
            argv=spawn.call_args.args[0]
            self.assertEqual(argv[:4],[str(w.CODEX),'queue','--thread',w.THREAD]);self.assertNotIn('--last',argv)
        status=w.readiness(self.state)
        self.assertFalse(status['real_handler_ACK_verified']);self.assertFalse((self.state/'WAKEUP_READY.json').exists())

    def test_offline_resume_fixed_UUID_no_model_or_permission_overrides(self):
        e=self.event(required_transport='exec_resume')
        with patch.object(w.subprocess,'Popen',return_value=self.proc) as spawn:
            w.dispatch(self.state,e,{'turn_id':'new','status':'completed'},False)
            argv=spawn.call_args.args[0]
            self.assertEqual(argv[:4],[str(w.CODEX),'exec','resume',w.THREAD])
            self.assertFalse(any(x in argv for x in ['--last','--model','--fork','--dangerously-bypass-approvals-and-sandbox','--ignore-rules','--ignore-user-config']))

    def test_unknown_enter_survives_notifier_restart_without_resend(self):
        e=self.event();p=self.state/'delivery'/e['event_id']/'STATE.json'
        w.atomic(p,dict(event_id=e['event_id'],status='dispatch_entered',route='queue'))
        w.reconcile_transports(self.state)
        with patch.object(w.subprocess,'Popen') as spawn:
            self.assertEqual(w.dispatch(self.state,e,{'status':'completed'},True),'delivery_unknown');spawn.assert_not_called()

    def test_real_new_turn_ACK_proof_and_idempotency(self):
        e=self.event();eid=e['event_id']
        w.atomic(self.state/'handler_claims'/f'{eid}.json',dict(turn_id='interrupted_prior_handler',synthetic=True))
        with patch.dict(w.os.environ,{'CODEX_THREAD_ID':w.THREAD}),patch.object(w,'thread_state',return_value=dict(turn_id='new',status='inProgress')),patch.object(w,'read_sql',return_value=[dict(item_json=json.dumps(dict(type='userMessage',content=eid))) ]):
            a=w.acknowledge(eid,'selftest_ack_only');b=w.acknowledge(eid,'selftest_ack_only')
            self.assertEqual(a,b);self.assertTrue(a['event_id_verified_in_original_turn_input'])

    def test_ACK_rejects_wrong_thread_or_original_arming_turn_or_missing_event(self):
        eid=self.event()['event_id']
        with patch.dict(w.os.environ,{'CODEX_THREAD_ID':'another_thread'}):
            with self.assertRaisesRegex(PermissionError,'original executor'):w.acknowledge(eid,'selftest_ack_only')
        with patch.dict(w.os.environ,{'CODEX_THREAD_ID':w.THREAD}),patch.object(w,'thread_state',return_value=dict(turn_id='old',status='inProgress')):
            with self.assertRaisesRegex(PermissionError,'new active'):w.acknowledge(eid,'selftest_ack_only')
        with patch.dict(w.os.environ,{'CODEX_THREAD_ID':w.THREAD}),patch.object(w,'thread_state',return_value=dict(turn_id='new',status='inProgress')),patch.object(w,'read_sql',return_value=[]):
            with self.assertRaisesRegex(PermissionError,'absent'):w.acknowledge(eid,'selftest_ack_only')

    def test_dependency_change_coalesced_no_poll_or_ACK_loop(self):
        baseline=dict(package_sha256=None,B_ready_tasks=[],stage_authorizations=[])
        with patch.object(w,'dependency_snapshot',return_value=baseline):
            w.observe_dependencies(self.state);w.observe_dependencies(self.state)
        self.assertEqual(list((self.state/'outbox').glob('*')),[])
        new=copy.deepcopy(baseline);new['package_sha256']='synthetic_new_package'
        with patch.object(w,'dependency_snapshot',return_value=new):
            w.observe_dependencies(self.state);w.observe_dependencies(self.state)
            w.atomic(self.state/'handler_acks'/'unrelated_ACK.json',dict(synthetic=False))
            w.observe_dependencies(self.state)
        self.assertEqual(len(list((self.state/'outbox').glob('*'))),1)

    def test_selftests_two_event_cap_and_arm_idempotence(self):
        with patch.object(w,'thread_state',return_value=dict(turn_id='original',status='inProgress')):
            a=w.arm();b=w.arm()
        self.assertEqual(set(a['events']),set(b['events']));self.assertEqual(len(a['events']),2)

    def test_shared_result_preserves_pending_until_verified_offline_proof(self):
        c=self.state/'campaign';home=self.state/'work';home.mkdir()
        w.atomic(home/'INSTALL_RESULT.json',dict(task_id='synthetic',scope='CPU'))
        value=dict(status='installed_waiting_real_handler_ACK',proofs=[],real_handler_ACK_verified=False,fixed_UUID_headless_resume_verified=False)
        with patch.object(w,'HERE',home),patch.object(w,'C',c):
            w.publish_validation_status(value)
            target=c/'receipts/B/B_LONG_TASK_WAKEUP_V1_RESULT.json'
            self.assertEqual(w.load(target)['status'],'pending_live_validation')
            value.update(status='original_thread_ACK_verified_offline_pending',proofs=[dict(synthetic=True)],real_handler_ACK_verified=True)
            w.publish_validation_status(value)
            self.assertEqual(w.load(target)['status'],'pending_live_validation')
            self.assertFalse(w.load(target)['wakeup_ready'])


if __name__=='__main__':unittest.main(verbosity=2)
