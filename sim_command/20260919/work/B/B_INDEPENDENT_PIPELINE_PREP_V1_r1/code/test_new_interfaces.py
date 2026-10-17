"""New CPU metadata/queue interfaces only. No model/framework imports."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import stage_gate as gate
import resource_admission as admission
import calibrate_e6
import fit_worker


class NewInterfaces(unittest.TestCase):
    def test_current_authority_denies_unregistered_stage_before_models(self):
        with self.assertRaisesRegex(PermissionError,'no once-frozen'):
            gate.registered_stage(gate.Q/'stages/B13_E1_FIT_TRAIN600_V1.json',
                control={'global_stop':False,'nodes':{'B':{'enabled':True}}},hostname=gate.HOST)
        self.assertNotIn('torch',sys.modules)

    def test_foreign_host_cannot_admit(self):
        with self.assertRaisesRegex(PermissionError,'host identity'):
            gate.registered_stage(gate.Q/'stages/a.json',control={},hostname='A-fixture')

    def test_registered_stage_sha_current_authority_and_stop(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);q=root/'queue';(q/'stages').mkdir(parents=True)
            auth=root/'auth.json';auth.write_text('{}')
            s=q/'stages/s.json';s.write_text(json.dumps(dict(owner='B',hostname=gate.HOST,authorized=True,
                kind='frozen_training_stage',basis_authorization_sha256=gate.sha(auth),automatic_retry=False,stage_id='fixture')))
            control=dict(global_stop=False,nodes={'B':{'enabled':True}},authorization=dict(path='auth.json',sha256=gate.sha(auth)),
                stage_authorizations=[dict(path='queue/stages/s.json',sha256=gate.sha(s))])
            with patch.object(gate,'Q',q),patch.object(gate,'C',root):
                self.assertEqual(gate.registered_stage(s,control=control,hostname=gate.HOST)['stage_id'],'fixture')
                changed_override=copy.deepcopy(control)
                changed_override['operational_overrides']=[dict(path='override.json',sha256='unbound')]
                with self.assertRaisesRegex(PermissionError,'operational overrides'):
                    gate.registered_stage(s,control=changed_override,hostname=gate.HOST)
                stopped=copy.deepcopy(control);stopped['nodes']['B']['enabled']=False
                with self.assertRaisesRegex(PermissionError,'stopped'):gate.registered_stage(s,control=stopped,hostname=gate.HOST)
                auth.write_text('{"changed":true}')
                with self.assertRaisesRegex(PermissionError,'authorization SHA'):gate.registered_stage(s,control=control,hostname=gate.HOST)
                s.write_text('{}')
                with self.assertRaisesRegex(PermissionError,'SHA changed'):gate.registered_stage(s,control=control,hostname=gate.HOST)

    def capacities(self):
        return dict(host_available_bytes=100,cgroup_remaining_bytes=100,cpu_threads=100,tmp_free_bytes=100,
            shared_free_bytes=admission.A_FLOOR+100,shared_reserved_bytes=0,A_reserved_bytes=0,
            A_pending=True,active_jobs=0,gpu_free_bytes={str(i):10 for i in range(8)})

    def jobs(self,n=9):
        return [dict(job_id=str(i),authorized=True,dependencies_ready=True,
            resources=dict(gpus=1,ram_bytes=10,cpu_threads=1,tmp_bytes=1,shared_bytes=1,vram_bytes_per_gpu=8)) for i in range(n)]

    def test_eight_real_jobs_and_refill(self):
        jobs=self.jobs();first,rejected=admission.choose(jobs,self.capacities())
        self.assertEqual(len(first),8);self.assertEqual(len({s['gpu_ids'][0] for s in first}),8)
        cap=self.capacities();cap.update(active_jobs=7,gpu_free_bytes={'3':10})
        next_jobs,_=admission.choose([jobs[8]],cap)
        self.assertEqual(next_jobs,[dict(job_id='8',gpu_ids=['3'])])

    def test_blocked_dependency_does_not_block_other_B_stage(self):
        jobs=self.jobs(2);jobs[0]['dependencies_ready']=False
        selected,_=admission.choose(jobs,self.capacities());self.assertEqual([s['job_id'] for s in selected],['1'])

    def test_cgroup_memory_and_unknown_capacity(self):
        cap=self.capacities();cap['cgroup_remaining_bytes']=21
        self.assertEqual(len(admission.choose(self.jobs(),cap)[0]),2)
        cap['cgroup_remaining_bytes']=None
        self.assertEqual(admission.choose(self.jobs(),cap)[0],[])

    def test_A_floor_and_existing_reservation_not_double_charged(self):
        cap=self.capacities();cap.update(shared_reserved_bytes=admission.A_FLOOR,A_reserved_bytes=admission.A_FLOOR)
        self.assertEqual(len(admission.choose(self.jobs(),cap)[0]),8)
        cap['shared_free_bytes']=admission.A_FLOOR
        self.assertEqual(admission.choose(self.jobs(),cap)[0],[])

    def test_E6_new_manifest_rejects_wrong_split_and_bad_alignment(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);trace=d/'synthetic_fixture.json';trace.write_text(json.dumps([dict(parent_episode_id='fixture',split='development',
                eligible_scores=[1.],g0_intervened=False,causal_D5_action_alignment_verified=False)]))
            m=dict(synthetic=False,split='train',episodes=dict(path=str(trace),sha256=gate.sha(trace)),
                frozen_D_identity='fixture',downstream='R',horizon=5)
            path=d/'manifest.json';path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'development-only'):calibrate_e6.calibrate(path,d/'out.json')
            m['split']='development';path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'alignment'):calibrate_e6.calibrate(path,d/'out.json')
            self.assertFalse((d/'out.json').exists());self.assertNotIn('torch',sys.modules)

    def test_fit_wrapper_persists_failed_status_with_mocked_frameworks(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(sys.modules,{'torch':types.SimpleNamespace(set_num_threads=lambda n:None),'numpy':types.SimpleNamespace()}):
            cfg=dict(job_id='synthetic_no_model',kind='unsupported_fixture',limits={'optimizer_updates':0})
            with self.assertRaisesRegex(ValueError,'Unsupported'):
                fit_worker.execute(cfg,dict(release_id='synthetic_only'),d)
            result=json.loads((Path(d)/'status.json').read_text())
            self.assertEqual(result['status'],'failed');self.assertEqual(result['counts']['optimizer_updates'],0)

    def test_generated_E1_matrix_is_three_full_seeds_four_members(self):
        proposal=json.loads((gate.PREP/'proposals/B13_E1_FIT_TRAIN600_V1.json').read_text())
        configs=[gate.load(j['config']['path']) for j in proposal['jobs'].values()]
        expected={(loss,seed,member) for loss in ('L00','L01','L10','L11') for seed in (9101,9102,9103) for member in (1041,1042,1043,1044)}
        self.assertEqual({(c['loss_id'],c['train_seed'],c['member']) for c in configs},expected)
        self.assertEqual(proposal['aggregate_operation_limits']['optimizer_attempts'],192000)
        self.assertFalse(proposal['authorized'])
        self.assertTrue(all(c['device']=='cpu' and c['limits']['backward_calls']==4000 for c in configs))


if __name__=='__main__':unittest.main(verbosity=2)
