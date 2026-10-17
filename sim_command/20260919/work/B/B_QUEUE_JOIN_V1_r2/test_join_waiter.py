"""Only bootstrap/control-plane tests; no GPU operations or package install."""
import copy
import json
import subprocess
import time
import unittest
import uuid
from pathlib import Path
import b_join_waiter as b


class Tests(unittest.TestCase):
    def setUp(self):
        self.root = b.HERE / 'selftests' / uuid.uuid4().hex
        self.root.mkdir(parents=True)

    def test_detached_two_jobs_singleton_and_reentry(self):
        argv = [b.PYTHON, str(b.HERE / 'b_join_waiter.py'), 'synthetic-start', '--state', str(self.root)]
        # The launching process exits here; its separately-sessioned daemon
        # must keep running and finish both tasks without this parent.
        first = json.loads(subprocess.check_output(argv, text=True))
        self.assertEqual(first['status'], 'started')
        self.assertEqual(first['process_identity']['session_id'], first['process_identity']['pid'])
        second = json.loads(subprocess.check_output(argv, text=True))
        self.assertEqual(second['status'], 'already_running')
        self.assertEqual(first['process_identity'], second['process_identity'])
        deadline = time.monotonic() + 15
        while not (self.root / 'SYNTHETIC_RESULT.json').exists() and time.monotonic() < deadline:
            time.sleep(.1)
        self.assertEqual(b.read(self.root / 'SYNTHETIC_RESULT.json')['status'], 'PASS')
        before = {str(p): p.read_bytes() for p in self.root.glob('fake_*.OUTPUT.json')}
        self.assertEqual(len(before), 2)
        for i in (1, 2):
            self.assertEqual(b.run_once(self.root, 'fake_' + str(i), ['/should/not/run'], self.root)['status'], 'complete')
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.glob('fake_*.OUTPUT.json')})

    def test_crash_recovery_unknown_execution_never_retries(self):
        b.atomic(self.root / 'uncertain.ENTERED.json', {'owner': b.identity(), 'note': 'synthetic crash after enter'}, exclusive=True)
        r = b.run_once(self.root, 'uncertain', ['/should/not/run'], self.root)
        self.assertEqual(r['status'], 'blocked')
        self.assertFalse((self.root / 'uncertain.RESULT.json').exists())

    def test_failed_job_consumed_and_identity_checks(self):
        r = b.run_once(self.root, 'fail', [b.PYTHON, '-c', 'raise SystemExit(7)'], self.root)
        self.assertEqual(r['exit_code'], 7)
        again = b.run_once(self.root, 'fail', ['/should/not/run'], self.root)
        self.assertEqual(r, again)
        own = b.identity()
        self.assertTrue(b.alive(own))
        own['start_ticks'] += 1
        self.assertFalse(b.alive(own))

    def test_verified_fixed_entry_and_rejection_gates(self):
        auth = b.authorization()
        entry = self.root / 'join_b.py'
        entry.write_text('# synthetic; never executed\n')
        evidence = self.root / 'tests.json'
        b.atomic(evidence, {'synthetic_only': True, 'status': 'PASS', 'checks': dict.fromkeys(b.CHECKS, True)})
        ready = {'publisher': 'A', 'status': 'READY', 'immutable_after_publication': True,
                 'files': [{'path': p.name, 'sha256': b.digest(p.read_bytes())} for p in (entry, evidence)],
                 'b_join': {'node': 'B', 'host': b.HOST, 'authorization_sha256': b.AUTH_SHA,
                            'contract_sha256': auth['contract']['sha256'],
                            'plan_sha256': {k: v['sha256'] for k, v in auth['plan'].items()},
                            'scientific_baseline_sha256': {k: v['sha256'] for k, v in auth['scientific_baseline'].items()},
                            'tests': {'path': evidence.name, 'sha256': b.digest(evidence.read_bytes())},
                            'argv': [b.PYTHON, entry.name, '--node', 'B'],
                            'performs_local_machine_gates_before_admission': True,
                            'non_nested_reservation': True, 'collection_source_limit': 0,
                            'training_evaluation_requires_stage_authorization': True}}
        path = self.root / 'READY.json'
        b.atomic(path, ready)
        result = b.checked_package(path, auth)
        self.assertEqual(result['argv'][1], str(entry))
        for field, value in [('publisher', 'B'), ('immutable_after_publication', False)]:
            changed = copy.deepcopy(ready); changed[field] = value; b.atomic(path, changed)
            with self.assertRaises(ValueError): b.checked_package(path, auth)
        changed = copy.deepcopy(ready); changed['b_join']['argv'] = ['/bin/bash', 'anything']; b.atomic(path, changed)
        with self.assertRaises(ValueError): b.checked_package(path, auth)
        changed = copy.deepcopy(ready); changed['b_join']['contract_sha256'] = 'bad'; b.atomic(path, changed)
        with self.assertRaises(ValueError): b.checked_package(path, auth)
        b.atomic(path, ready); entry.write_text('modified\n')
        with self.assertRaises(ValueError): b.checked_package(path, auth)


if __name__ == '__main__':
    unittest.main(verbosity=2)
