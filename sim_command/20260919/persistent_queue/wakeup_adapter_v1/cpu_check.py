"""Targeted synthetic tests; no CLI callbacks, real locks, or GPU access."""
import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import observer as o


class Checks(unittest.TestCase):
    def test_busy_queues_once_then_preserves_resume_budget(self):
        self.assertEqual(o.choose({}, busy=True, now=10), 'queue')
        for n in (1, 2):
            self.assertEqual(o.choose(dict(attempts=n, queue_sent=True), busy=True, now=1000),
                             'waiting_for_original_writer_release')
            self.assertEqual(o.choose(dict(attempts=n, queue_sent=True), busy=False, now=1000),
                             'native_resume')

    def test_ack_and_cap_and_backoff(self):
        self.assertEqual(o.choose(dict(handler_acknowledged=True), busy=False, now=1), 'handled')
        self.assertEqual(o.choose(dict(attempts=3), busy=False, now=1), 'notification_budget_exhausted')
        self.assertEqual(o.choose(dict(next_unix=20), busy=False, now=10), 'pending')

    def test_no_concurrent_resume(self):
        self.assertEqual(o.choose(dict(attempts=1), busy=False, now=9999, resume_alive=True), 'pending')

    def event(self):
        return dict(event_id='fake', executor_thread_id=o.THREAD, hostname=o.HOST,
                    authorization_sha256=o.WAKE_SHA, synthetic=True, challenge='fixture')

    def test_ack_requires_bound_identity_challenge_and_compute_zero(self):
        e=self.event();a=dict(e,handled=True,scientific_compute=0)
        self.assertTrue(o.valid_ack(e,a))
        for k,v in [('event_id','wrong'),('executor_thread_id','wrong'),('challenge','wrong'),
                    ('synthetic',False),('handled',False),('scientific_compute',1)]:
            self.assertFalse(o.valid_ack(e,dict(a,**{k:v})))

    def test_busy_path_uses_real_deliver_serialization_and_is_bounded(self):
        with tempfile.TemporaryDirectory(prefix='wakeup_cpu_',dir='/tmp') as d:
            p=Path(d)/'EVENT.json';o.write(p,self.event(),True)
            response=type('Response',(),dict(returncode=0,stdout='Queued message fixture',stderr=''))()
            with patch.object(o,'writer_busy',return_value=True), \
                    patch.object(o.subprocess,'run',return_value=response) as run:
                a=o.deliver(p,1000);b=o.deliver(p,2000)
            self.assertEqual(run.call_count,1)
            self.assertEqual(a['attempts'],1);self.assertEqual(b['attempts'],1)
            self.assertFalse((Path(d)/'HANDLER_ACK.json').exists())
            self.assertEqual(b['state'],'waiting_for_original_writer_release')

    def test_transport_exception_has_finite_persisted_attempt(self):
        with tempfile.TemporaryDirectory(prefix='wakeup_cpu_',dir='/tmp') as d:
            p=Path(d)/'EVENT.json';o.write(p,self.event(),True)
            with patch.object(o,'writer_busy',return_value=True), \
                    patch.object(o.subprocess,'run',side_effect=TimeoutError('fixture')):
                a=o.deliver(p,1000)
            self.assertEqual(a['attempts'],1);self.assertEqual(a['state'],'transport_failed')
            self.assertEqual(o.read(Path(d)/'TRANSPORT.json')['error']['type'],'TimeoutError')

    def test_resume_argv_preserves_original_thread_and_permissions(self):
        with tempfile.TemporaryDirectory(prefix='wakeup_cpu_',dir='/tmp') as d:
            p=Path(d)/'EVENT.json';o.write(p,self.event(),True)
            proc=type('Proc',(),dict(pid=123))()
            with patch.object(o,'writer_busy',return_value=False), \
                    patch.object(o,'identity',return_value=dict(pid=123,start_ticks=456)), \
                    patch.object(o.subprocess,'Popen',return_value=proc) as popen:
                a=o.deliver(p,1000)
            argv=popen.call_args.args[0]
            self.assertEqual(argv[:4],['codex','exec','resume',o.THREAD])
            self.assertFalse(any(x in argv for x in ['--last','--model','--worktree','--fork',
                '--dangerously-bypass-approvals-and-sandbox','--ignore-user-config','--ignore-rules']))
            self.assertEqual(a['transport'],'native_resume')

    def test_real_event_classifier_does_not_infer_success_from_disappearance(self):
        r=dict(heartbeat_stale_seconds=120);h=dict(utc='2026-09-21T00:00:00+00:00',status='formal_chain')
        t=datetime.datetime.fromisoformat(h['utc']).timestamp()
        self.assertEqual(o.classify(r,now=t+1,daemon_alive=False,heartbeat=h,result=None),'execution_unknown')
        self.assertEqual(o.classify(r,now=t+121,daemon_alive=True,heartbeat=h,result=None),'blocked_heartbeat_stale')
        self.assertEqual(o.classify(r,now=t+1,daemon_alive=True,heartbeat=h,result=None),'running')
        self.assertEqual(o.classify(r,now=t+1000,daemon_alive=False,heartbeat=h,result={'fatal':'x'}),
                         'terminal_existing_notifier_owner')

    def test_ack_reconciliation_after_notifier_restart(self):
        with tempfile.TemporaryDirectory(prefix='wakeup_cpu_',dir='/tmp') as d:
            p=Path(d)/'outbox/fake/EVENT.json';e=self.event();o.write(p,e,True)
            o.write(p.parent/'TRANSPORT.json',dict(attempts=1,queue_sent=True),True)
            o.write(p.parent/'HANDLER_ACK.json',dict(e,handled=True,scientific_compute=0),True)
            with patch.object(o,'ROOT',Path(d)),patch.object(o,'writer_busy',side_effect=AssertionError('must not probe')):
                a=o.deliver(p,1000);b=o.deliver(p,2000)
            self.assertTrue(a['handler_acknowledged']);self.assertTrue(b['handler_acknowledged'])
            self.assertIsNone(o.read(Path(d)/'WAKEUP_READY.json')['physical_window_closed_test'])

    def test_prompt_scope_and_exclusive_creation(self):
        msg=o.prompt(Path('/tmp/fake/EVENT.json'),self.event())
        self.assertIn('只写此小ACK',msg)
        with tempfile.TemporaryDirectory(prefix='wakeup_cpu_',dir='/tmp') as d:
            p=Path(d)/'one.json';o.write(p,dict(fixture=True),True)
            with self.assertRaises(FileExistsError):o.write(p,dict(fixture=False),True)


if __name__=='__main__':
    unittest.main()
