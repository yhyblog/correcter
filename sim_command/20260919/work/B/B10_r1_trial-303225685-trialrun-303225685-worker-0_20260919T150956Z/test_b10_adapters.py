"""Synthetic CPU checks: no optimizer steps, models from disk, or simulator."""
import copy
from pathlib import Path
import sys
import unittest
import numpy as np
import torch
from b10_adapters import (ContractError,CausalD5Monitor,EventLedger,GAFVelocityAdapter,
    check_parent_splits,validate_trajectory,gaf_view,lvm_pair_indices,e1_loss,
    legal_e6_cut,pi05_denoiser_hook,select_development_threshold)

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang')
sys.path[:0]=[str(ROOT/'Corrector'),str(ROOT/'Corrector/src')]
from experiments.native10_training_20260916.training import loss_parts
torch.set_num_threads(2)

def trajectory(parent='demo0',split='train'):
    n=12
    return {'dataset_revision':'synthetic_fixture_v1','split':split,'task':'synthetic-only','instruction':'CPU fixture','parent_episode_id':parent,'source_id':parent+'/source','branch_id':'normal','suffix_id':'s0','collection_policy_sha256':'1'*64,'seed':0,'H':10,'generated_length':50,'executed_prefix_length':10,'normalizer_sha256':'2'*64,'state_feature_sha256':'3'*64,'language_feature_sha256':'4'*64,'steps':list(range(n)),'observation_refs':[{'path':f'synthetic://{parent}/frame/{i}','sha256':'5'*64} for i in range(n+1)],'policy_state':np.zeros((n,4)).tolist(),'task_features':[1.,0.,0.],'action_policy':(np.arange(n*4).reshape(n,4)/100).tolist(),'raw_actions':np.zeros((n,4)).tolist(),'rewards':[0.]*11+[1.],'successes':[False]*11+[True],'first_success_step':12,'terminated':[False]*11+[True],'truncated':[False]*n,'cut_reason':'success','generated_chunk_ref':{'path':'synthetic://chunk','sha256':'6'*64},'outcome_complete':True,'synthetic_only':True}

class DataViewTests(unittest.TestCase):
    def test_gaf_target_is_discounted_success_timing(self):
        v=gaf_view([trajectory()],split='train',horizon=10,gamma=.5)
        self.assertEqual(tuple(v['action_chunks'].shape),(3,10,4))
        torch.testing.assert_close(v['targets'],torch.tensor([.5**11,.5**10,.5**9]))
        self.assertEqual(v['provenance'][-1]['start_step'],2)
    def test_parent_cannot_cross_splits(self):
        other=trajectory(split='development');other['branch_id']='candidate'
        with self.assertRaisesRegex(ContractError,'crosses splits'):check_parent_splits([trajectory(),other])
    def test_branch_suffix_never_concatenated(self):
        a=trajectory();b=trajectory('another');b['branch_id']='candidate'
        v=gaf_view([a,b],split='train');self.assertEqual(len(v['targets']),6)
        self.assertEqual({p['parent_episode_id'] for p in v['provenance']},{'demo0','another'})
    def test_reject_gaps_unknown_terminal_and_privileged_state(self):
        for field,value in [('steps',[0,1,2,3,4,5,7,8,9,10,11,12]),('terminated',[None]*12),('policy_state',np.zeros((12,39)).tolist())]:
            t=trajectory();t[field]=value
            with self.assertRaises(ContractError):validate_trajectory(t)
    def test_test_data_cannot_train(self):
        with self.assertRaises(ContractError):gaf_view([trajectory(split='test')],split='train')
    def test_incomplete_suffix_cannot_get_failure_target(self):
        t=trajectory();t['outcome_complete']=False
        with self.assertRaisesRegex(ContractError,'Censored'):gaf_view([t],split='train')
    def test_lvm_pair_remains_in_real_episode(self):
        pairs=lvm_pair_indices(trajectory(),k=10,normal_demo=True)
        self.assertEqual(len(pairs),3);self.assertEqual(pairs[-1]['target_step'],12)
        with self.assertRaises(ContractError):lvm_pair_indices(trajectory(),normal_demo=False)

class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.action=torch.zeros((1,50,32));self.velocity=torch.zeros_like(self.action)
        def q(**kwargs):return kwargs['action_chunk'].sum(dim=(1,2))
        self.adapter=GAFVelocityAdapter([q],state=torch.zeros(1,4),task_features=torch.zeros(1,3),beta=2,clip=None,uncertainty_scale=0)
    def test_reverse_time_moves_up_value_and_keeps_padding(self):
        guided,_=self.adapter(self.action,self.velocity,.5)
        self.assertTrue(bool((guided[:,:10,:4]==-.5).all()))
        self.assertTrue(bool((guided[:,10:,:]==0).all()));self.assertTrue(bool((guided[:,:,:][...,4:]==0).all()))
        self.assertGreater(float((self.action-.1*guided)[:,:10,:4].sum()),0)
    def test_detaches_denoiser(self):
        velocity=self.velocity.clone().requires_grad_(True)
        self.adapter(self.action,velocity,.5)
        self.assertIsNone(velocity.grad)
    def test_owned_hook_restored_after_exception(self):
        class Fake:
            def denoise_step(self,**kwargs):return torch.zeros_like(kwargs['x_t'])
        m=Fake();before=m.denoise_step
        with self.assertRaisesRegex(RuntimeError,'injected'):
            with pi05_denoiser_hook(m,self.adapter):
                m.denoise_step(x_t=self.action,timestep=torch.tensor([.5]))
                raise RuntimeError('injected')
        self.assertEqual(m.denoise_step,before);self.assertNotIn('denoise_step',m.__dict__)
        self.assertEqual(sum(e['status']=='returned' and e['event_type']=='flow_forward' for e in self.adapter.ledger.events),1)

class MonitorTests(unittest.TestCase):
    def monitor(self):return CausalD5Monitor(.5,np.ones(2),'e')
    def test_only_mature_actual_action_prediction_can_trigger(self):
        m=self.monitor();m.register(issued_step=0,predicted_features=np.zeros((5,2)),conditioned_raw_actions=np.zeros((5,4)))
        arguments=dict(issued_step=0,observed_step=5,actual_features=np.ones((5,2)),executed_raw_actions=np.zeros((5,4)),episode_id='e',plan_age=5,remaining_queue=5)
        with self.assertRaises(ContractError):m.observe(**(arguments|{'observed_step':0}))
        with self.assertRaises(ContractError):m.observe(**(arguments|{'executed_raw_actions':np.ones((5,4))}))
        with self.assertRaises(ContractError):m.observe(**(arguments|{'episode_id':'different'}))
        self.assertTrue(m.observe(**arguments)['triggered'])
        m.register(issued_step=10,predicted_features=np.zeros((5,2)),conditioned_raw_actions=np.zeros((5,4)))
        self.assertFalse(m.observe(**(arguments|{'issued_step':10,'observed_step':15}))['triggered'])
    def test_natural_boundary_and_late_cut_ineligible(self):
        self.assertFalse(legal_e6_cut(step=10,plan_age=0,remaining_queue=10))
        self.assertFalse(legal_e6_cut(step=295,plan_age=5,remaining_queue=5))
        self.assertTrue(legal_e6_cut(step=285,plan_age=5,remaining_queue=5))
    def test_threshold_uses_episode_frequency_and_includes_no_alarm(self):
        e=[{'parent_episode_id':str(i),'split':'development','eligible_scores':scores,'g0_intervened':i==0} for i,scores in enumerate([[.1,.9],[.3],[]])]
        result=select_development_threshold(e);self.assertEqual(result['achieved_anomaly_interventions'],1)
        self.assertFalse(result['selection_uses_success'])
        e[0]['split']='test'
        with self.assertRaises(ContractError):select_development_threshold(e)

class LossTests(unittest.TestCase):
    def test_l11_equals_original_and_ablation_keeps_same_source_means(self):
        generator=torch.Generator().manual_seed(17)
        logits=torch.randn(2,13,generator=generator);outcomes=torch.randint(0,2,(2,13,4),generator=generator)
        cw=torch.ones(2,13);gw=cw.clone();gw[:,0]=0;pw=torch.ones(2,5)
        common=dict(candidate_weights=cw,gain_weights=gw,pair_weights=pw)
        old=loss_parts(logits,outcomes,**common)
        for a,b in [(0,0),(1,0),(0,1),(1,1)]:
            actual=e1_loss(logits,outcomes,**common,gain_enabled=a,pair_enabled=b)
            torch.testing.assert_close(actual['loss'],old['bce']+a*old['gain_mse']+.5*b*old['pair_mse'])
    def test_small_weight_denominator_and_no_unknown_labels(self):
        logits=torch.zeros(1,13);outcomes=torch.zeros(1,13,4);cw=torch.ones(1,13)*.01;gw=torch.zeros(1,13);pw=torch.zeros(1,5)
        result=e1_loss(logits,outcomes,candidate_weights=cw,gain_weights=gw,pair_weights=pw,gain_enabled=0,pair_enabled=0)
        self.assertAlmostEqual(float(result['loss']),np.log(2),places=6)
        outcomes[0,2,1]=-1
        with self.assertRaises(ContractError):e1_loss(logits,outcomes,candidate_weights=cw,gain_weights=gw,pair_weights=pw,gain_enabled=1,pair_enabled=1)

if __name__=='__main__':unittest.main(verbosity=2)
