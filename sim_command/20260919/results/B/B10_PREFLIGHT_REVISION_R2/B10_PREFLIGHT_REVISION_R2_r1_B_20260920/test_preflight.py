"""Targeted CPU checks only. No torch/numpy/CUDA imports or model execution."""
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid
import preflight as p

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
CASES = []

def fixture():
    config = p.read(p.HERE / 'config.json')
    task = config['compute_task_id']; rid = config['compute_release_id']; path = 'releases/' + rid + '.json'
    control = {'campaign_id': config['campaign_id'], 'stop_requested': False, 'formal_gpu_runs_enabled': True,
               'active_compute_release_id': rid, 'active_compute_release': path, 'active_compute_task_ids': [task],
               'allowed_task_ids': [task], 'roles': {'B': {'hostname': config['hostname']}},
               'current_compute_limits': deepcopy(config['limits']), 'per_task_compute_limits': {task: deepcopy(config['limits'])}, 'closed_compute_releases': []}
    board = {'campaign_id': config['campaign_id'], 'tasks': [{'id': task, 'owner': 'B', 'revision': 1, 'status': 'ready', 'release': path}]}
    release = {'campaign_id': config['campaign_id'], 'release_id': rid, 'task_id': task, 'task_revision': 1, 'owner': 'B', 'kind': 'formal_compute', 'status': 'released',
               'hostname': config['hostname'], 'participating_hosts': [config['hostname']], 'valid_from_utc': '2026-09-20T11:00:00Z', 'expires_at_utc': '2026-09-20T13:00:00Z',
               'gpu': deepcopy(config['gpu']), 'job_id': config['job_id'], 'retry_cap': 0, 'timeout_seconds': 180, 'termination_grace_seconds': 20, 'limits': deepcopy(config['limits'])}
    return control, board, release, config, path

def validate(values, host=None):
    control, board, release, config, path = values
    return p.metadata(control, board, release, config, host=host or config['hostname'], relative_release=path, now=NOW)

class MetadataTests(unittest.TestCase):
    def test_exact_active_B_release_succeeds_without_runtime(self):
        self.assertEqual(validate(fixture())['owner'], 'B')
        values = fixture(); values[1]['tasks'][0]['status'] = 'running'
        self.assertEqual(validate(values)['status'], 'running')
    def test_rejection_matrix(self):
        mutations = {
            'wrong host': lambda c,b,r,k: r.update(hostname='server-A'),
            'CONTROL owner host differs': lambda c,b,r,k: c['roles']['B'].update(hostname='server-A'),
            'another release active': lambda c,b,r,k: c.update(active_compute_release_id='A-only-release'),
            'no active release': lambda c,b,r,k: c.update(active_compute_release_id=None),
            'another release path': lambda c,b,r,k: c.update(active_compute_release='releases/old.json'),
            'another task active': lambda c,b,r,k: c.update(active_compute_task_ids=['A10']),
            'multiple tasks active': lambda c,b,r,k: c.update(active_compute_task_ids=[k['compute_task_id'],'A10']),
            'not allowed': lambda c,b,r,k: c.update(allowed_task_ids=[]),
            'draft release': lambda c,b,r,k: r.update(status='draft'),
            'closed release history': lambda c,b,r,k: c.update(closed_compute_releases=[{'release_id':r['release_id']}]),
            'expired release': lambda c,b,r,k: r.update(expires_at_utc='2026-09-20T11:59:59Z'),
            'future release': lambda c,b,r,k: r.update(valid_from_utc='2026-09-20T12:00:01Z'),
            'missing expiry': lambda c,b,r,k: r.pop('expires_at_utc'),
            'timezone missing': lambda c,b,r,k: r.update(expires_at_utc='2026-09-20T13:00:00'),
            'wrong owner': lambda c,b,r,k: b['tasks'][0].update(owner='A'),
            'wrong revision': lambda c,b,r,k: b['tasks'][0].update(revision=2),
            'wrong release revision': lambda c,b,r,k: r.update(task_revision=2),
            'wrong board release': lambda c,b,r,k: b['tasks'][0].update(release='releases/stale.json'),
            'board complete': lambda c,b,r,k: b['tasks'][0].update(status='complete'),
            'board released is invalid': lambda c,b,r,k: b['tasks'][0].update(status='released'),
            'duplicate board entry': lambda c,b,r,k: b['tasks'].append(deepcopy(b['tasks'][0])),
            'joint wave': lambda c,b,r,k: r.update(participating_hosts=[k['hostname'],'server-A']),
            'global inference cap insufficient': lambda c,b,r,k: c['current_compute_limits'].update(model_gpu_inference_calls=1),
            'global initialization missing': lambda c,b,r,k: c['current_compute_limits'].pop('model_initializations'),
            'global cap bool rejected': lambda c,b,r,k: c['current_compute_limits'].update(model_initializations=True),
            'task cap insufficient': lambda c,b,r,k: c['per_task_compute_limits'][k['compute_task_id']].update(model_initializations=0),
            'release cap drift': lambda c,b,r,k: r['limits'].update(model_gpu_inference_calls=3),
            'stop': lambda c,b,r,k: c.update(stop_requested=True),
            'GPU disabled': lambda c,b,r,k: c.update(formal_gpu_runs_enabled=False),
            'GPU binding changed': lambda c,b,r,k: r['gpu'].update(uuid='GPU-other'),
            'retries': lambda c,b,r,k: r.update(retry_cap=1),
            'timeout enlarged': lambda c,b,r,k: r.update(timeout_seconds=181),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                values = fixture(); mutate(*values[:4])
                with self.assertRaises(p.Refused): validate(values)
                CASES.append({'case':label,'expected':'refused','passed':True})

class GpuTests(unittest.TestCase):
    def setUp(self):
        self.rows = p.parse_gpu_rows((p.HERE / 'evidence/gpu_identity.csv').read_text())
        self.expected = p.read(p.HERE / 'config.json')['gpu']
    def test_uuid_binding_ignores_index_reordering(self):
        self.rows[0]['index'] = 7
        self.assertEqual(p.gpu_identity(self.rows,self.expected)['uuid'],self.expected['uuid'])
    def test_wrong_uuid_driver_model_or_pci_refused(self):
        for key in ['uuid','driver_version','name','pci_bus_id']:
            with self.subTest(key=key):
                rows=deepcopy(self.rows);rows[0][key]='wrong'
                with self.assertRaises(p.Refused):p.gpu_identity(rows,self.expected)
                CASES.append({'case':'GPU '+key+' mismatch','expected':'refused','passed':True})
        expected=deepcopy(self.expected);expected['cuda_visible_devices']='0'
        with self.assertRaises(p.Refused):p.gpu_identity(self.rows,expected)
        with self.assertRaises(p.Refused):p.gpu_identity(self.rows[:1],self.expected)
    def test_nvml_failure_is_refusal_not_missing_driver_claim(self):
        with patch.object(p.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','NVML unavailable')):
            with self.assertRaisesRegex(p.Refused,'query failed'):p.query_gpu()

class FileAndEntryTests(unittest.TestCase):
    def setUp(self):
        self.root=p.HERE/'evidence'/('file_fixture_'+uuid.uuid4().hex);self.root.mkdir()
        for name,content in [('preflight.py','synthetic source'),('local_source_snapshot/siglip_dynamics_mlp.py','synthetic model source'),('commands/run_preflight.sh','synthetic command'),('inputs/best_cosine_model.pt','synthetic bytes, not a model'),('inputs/config.json','{}'),('lifecycle.sh','synthetic lifecycle')]:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        self.config={'inputs':{name:{'path':str(self.root/'inputs'/file),'sha256':p.sha(self.root/'inputs'/file),'bytes':(self.root/'inputs'/file).stat().st_size} for name,file in [('model','best_cosine_model.pt'),('model_config','config.json')]},'lifecycle_dependencies':[{'path':str(self.root/'lifecycle.sh'),'sha256':p.sha(self.root/'lifecycle.sh')}]}
        p.atomic(self.root/'config.json',self.config)
        p.atomic(self.root/'CODE_SNAPSHOT.json',{'files':[{'path':str(path.relative_to(self.root)),'sha256':p.sha(path)} for path in [self.root/'preflight.py',self.root/'local_source_snapshot/siglip_dynamics_mlp.py',self.root/'commands/run_preflight.sh',self.root/'config.json']]})
        self.release={'config_path':str(self.root/'config.json'),'config_sha256':p.sha(self.root/'config.json'),'code_manifest_path':str(self.root/'CODE_SNAPSHOT.json'),'code_manifest_sha256':p.sha(self.root/'CODE_SNAPSHOT.json'),'inputs':deepcopy(self.config['inputs'])}
    def test_good_frozen_files(self):p.files(self.root,self.root/'config.json',self.release,self.config)
    def test_input_code_config_lifecycle_drift(self):
        for name in ['inputs/best_cosine_model.pt','preflight.py','config.json','lifecycle.sh']:
            path=self.root/name;old=path.read_bytes();path.write_bytes(old+b'x')
            with self.subTest(name=name):
                with self.assertRaises(p.Refused):p.files(self.root,self.root/'config.json',self.release,self.config)
            path.write_bytes(old)
    def test_release_input_sha_drift(self):
        self.release['inputs']['model']['sha256']='0'*64
        with self.assertRaises(p.Refused):p.files(self.root,self.root/'config.json',self.release,self.config)
    def test_real_P00_cannot_reach_GPU_query_or_import(self):
        with patch.object(p,'query_gpu',side_effect=AssertionError('must not query GPU')):
            with self.assertRaises(p.Refused):p.authorize(p.HERE/'config.json',p.CAMPAIGN/'releases/P00_PREFLIGHT_CORRECTIONS_V1.json')
        self.assertNotIn('torch',sys.modules);self.assertNotIn('numpy',sys.modules)

if __name__=='__main__':
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (p.HERE/'evidence/CPU_TESTS.log').write_text(stream.getvalue())
    report={'status':'pass' if result.wasSuccessful() else 'fail','tests_run':result.testsRun,'rejection_subcases':CASES,'errors':[(str(t),e) for t,e in result.errors],'failures':[(str(t),e) for t,e in result.failures],'model_runtime_imports':[name for name in ['torch','numpy','jax','cupy'] if name in sys.modules],'actual_GPU_queries':0,'actual_model_calls':0,'actual_cuda_initializations':0,'synthetic_only':True}
    p.atomic(p.HERE/'evidence/CPU_CHECK_RESULT.json',report);print(json.dumps(report,indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
