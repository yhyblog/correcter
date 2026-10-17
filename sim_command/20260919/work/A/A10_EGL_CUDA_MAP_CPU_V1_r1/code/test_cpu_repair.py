"""Finite CPU scenarios. No simulator, renderer, CUDA or model imports."""
import json
import os
from pathlib import Path
import socket
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'native_code_snapshot_v5/core'))
from observation_accounting import ObservationAccounting
from graphics_probe import choose_target, drm_identity
from probe_contract import CAPS, Journal, Refused, authorize, current, digest, reconcile


class CPURepairChecks(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.environ['CPU_TEST_ARTIFACT_ROOT'])/self._testMethodName
        self.root.mkdir(parents=True, exist_ok=False)

    def observation(self): return ObservationAccounting(self.root/'observation.jsonl')
    def init(self): return {'returned_operation_units': {'diagnostic_reset_calls': 1}}

    def test_native_reset_return_then_render_failure(self):
        row = self.observation().summary(self.init())
        self.assertEqual([row[k] for k in ('diagnostic_native_resets_returned','diagnostic_observations_returned','usable_observation_artifacts')], [1,0,0])

    def test_observation_return_then_invalid_image(self):
        x=self.observation();x.observation_returned();row=x.summary(self.init())
        self.assertEqual((row['diagnostic_observations_returned'],row['usable_observation_artifacts']), (1,0))

    def test_valid_saved_observation(self):
        x=self.observation();x.observation_returned();p=self.root/'synthetic-observation.npz';p.write_bytes(b'CPU fixture, not an experiment image')
        x.artifact_written(p);self.assertEqual(x.summary(self.init())['usable_observation_artifacts'],1)
        with self.assertRaises(ValueError):x.artifact_written(p)
        with self.assertRaises(ValueError):x.observation_returned()

    def test_no_native_reset_is_not_a_return(self):
        row=self.observation().summary({'returned_operation_units':{}})
        self.assertEqual(row['diagnostic_native_resets_returned'],0)

    def test_artifact_must_follow_full_return(self):
        x=self.observation()
        with self.assertRaises(ValueError):x.artifact_written(self.root/'missing')
        x.observation_returned()
        with self.assertRaises(ValueError):x.artifact_written(self.root/'missing')

    def test_failed_graphics_attempt_keeps_charge(self):
        x=Journal(self.root/'events.jsonl',CAPS)
        with self.assertRaises(RuntimeError):x.call('egl_initialize_calls',lambda:False,check=bool)
        r=reconcile(x.path);self.assertEqual(r['entered_budget_usage']['egl_initialize_calls'],1);self.assertEqual(r['failed'],1)
        touched=[]
        with self.assertRaises(Refused):x.call('egl_initialize_calls',lambda:touched.append(True))
        self.assertEqual(touched,[])

    def test_missing_terminal_retains_cost(self):
        x=Journal(self.root/'events.jsonl',CAPS)
        x.append(dict(event_id='CPU-missing',phase='entered',operation='graphics_context_creations',resource_units={'graphics_context_creations':1}))
        r=reconcile(x.path);self.assertEqual(r['incomplete'],1);self.assertEqual(r['entered_budget_usage']['graphics_context_creations'],1)

    def test_revocation_prevents_operation(self):
        touched=[]
        def deny():raise Refused('Synthetic revoked release')
        x=Journal(self.root/'events.jsonl',CAPS,deny)
        with self.assertRaises(Refused):x.call('render_calls',lambda:touched.append(True))
        self.assertEqual(touched,[]);self.assertEqual(x.path.read_text(),'')
        x.call('egl_release_thread_calls',lambda:True,cleanup=True)

    def test_physical_mapping_ignores_CUDA_order(self):
        device=dict(gpu_uuid='GPU-target',pci_bus_id='0000:0f:00.0')
        rows=[dict(egl_index=0,mapping=None),dict(egl_index=3,mapping=device)]
        self.assertEqual(choose_target(rows,device),3)
        with self.assertRaises(Refused):choose_target(rows+rows[1:],device)
        with self.assertRaises(Refused):choose_target(rows[:1],device)

    def test_drm_to_kernel_uuid_chain(self):
        sysroot=self.root/'sys';procroot=self.root/'proc';dev=self.root/'devices/0000:0f:00.0';dev.mkdir(parents=True)
        (sysroot/'card4').mkdir(parents=True);(sysroot/'card4/device').symlink_to(dev)
        (procroot/'0000:0f:00.0').mkdir(parents=True)
        (procroot/'0000:0f:00.0/information').write_text('GPU UUID: GPU-target\nBus Location: 0000:0f:00.0\n')
        row=drm_identity('/dev/dri/card4',sysroot,procroot);self.assertEqual(row['gpu_uuid'],'GPU-target')
        with self.assertRaises(Refused):drm_identity('/tmp/card4',sysroot,procroot)

    def fixture(self):
        from probe_contract import TASK
        campaign=self.root/'campaign';bundle=self.root/'bundle';(bundle/'proposal').mkdir(parents=True);campaign.mkdir()
        (bundle/'code').mkdir();(bundle/'code/input.py').write_text('# synthetic CPU input\n')
        ext=self.root/'external.py';ext.write_text('# synthetic external source\n')
        (bundle/'EXTERNAL_SOURCE_MANIFEST.json').write_text(json.dumps({'files':[dict(path=str(ext),realpath=str(ext.resolve()),sha256=digest(ext))]}))
        entries=[dict(path='code/input.py',sha256=digest(bundle/'code/input.py')),dict(path='EXTERNAL_SOURCE_MANIFEST.json',sha256=digest(bundle/'EXTERNAL_SOURCE_MANIFEST.json'))]
        (bundle/'BUNDLE_MANIFEST.json').write_text(json.dumps({'files':entries}))
        device=dict(gpu_uuid='GPU-target',gpu_index=0,gpu_model='CPU fixture',driver='fixture',pci_bus_id='0000:0f:00.0')
        common=dict(resource_caps=CAPS,max_retries=0,timeout_seconds=120,kill_grace_seconds=10,wave_participants=['A'],renderer_route='NVIDIA_EGL')
        p=dict(common,published_root=str(bundle),device=device,bundle_manifest_sha256=digest(bundle/'BUNDLE_MANIFEST.json'))
        pp=bundle/'proposal/PROPOSAL.json';pp.write_text(json.dumps(p))
        r=dict(common,**device,status='released',task_id=TASK,task_revision=1,role='A',hostname=socket.gethostname(),
            release_id='CPU_fixture_release',run_id='CPU_fixture_run',wave_id='CPU_fixture_wave',shard_id='CPU_fixture_shard',
            proposal_sha256=digest(pp),bundle_manifest_sha256=p['bundle_manifest_sha256'])
        rp=campaign/'RELEASE.json';rp.write_text(json.dumps(r))
        c=dict(mode='preflight',formal_gpu_runs_enabled=True,active_compute_release_id=r['release_id'],active_compute_release='RELEASE.json',
               allowed_task_ids=[TASK],active_compute_task_ids=[TASK],current_compute_limits=CAPS)
        (campaign/'CONTROL.json').write_text(json.dumps(c));(campaign/'TASK_BOARD.json').write_text(json.dumps({'tasks':[dict(id=TASK,owner='A',revision=1,status='ready',release='RELEASE.json')]}))
        return campaign,rp,pp,ext

    def test_CPU_authority_validates_without_graphics(self):
        c,r,p,_=self.fixture();release,proposal=authorize(c,r,p);self.assertEqual(release['task_revision'],1)
        self.assertNotIn('mujoco',sys.modules);self.assertNotIn('OpenGL',sys.modules);self.assertNotIn('torch',sys.modules)

    def test_mutated_runtime_source_is_denied(self):
        c,r,p,ext=self.fixture();ext.write_text('changed')
        with self.assertRaisesRegex(Refused,'Runtime file changed'):authorize(c,r,p)

    def test_closed_or_CPU_release_denied(self):
        c,r,p,_=self.fixture();d=json.loads(r.read_text());d['status']='closed';r.write_text(json.dumps(d))
        with self.assertRaises(Refused):authorize(c,r,p)

    def test_current_CONTROL_revocation_denied(self):
        c,r,p,_=self.fixture();rr,pp=authorize(c,r,p);d=json.loads((c/'CONTROL.json').read_text());d['formal_gpu_runs_enabled']=False;(c/'CONTROL.json').write_text(json.dumps(d))
        with self.assertRaises(Refused):current(c,r,rr,pp)

    def test_midrun_release_mutation_denied(self):
        c,r,p,_=self.fixture();rr,pp=authorize(c,r,p);r.write_text(r.read_text()+'\n')
        with self.assertRaisesRegex(Refused,'mutated'):current(c,r,rr,pp)

    def test_wrong_task_board_owner_denied(self):
        c,r,p,_=self.fixture();d=json.loads((c/'TASK_BOARD.json').read_text());d['tasks'][0]['owner']='B';(c/'TASK_BOARD.json').write_text(json.dumps(d))
        with self.assertRaises(Refused):authorize(c,r,p)


if __name__=='__main__':unittest.main(verbosity=2)
