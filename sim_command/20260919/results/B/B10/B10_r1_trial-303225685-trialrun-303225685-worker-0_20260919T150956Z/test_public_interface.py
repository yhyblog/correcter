"""Public v1 compatibility and accounting checks with explicit synthetic records."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
import torch
from b10_adapters import ContractError,EventLedger,GAFVelocityAdapter,CausalD5Monitor,gaf_view
from public_interface import validate_record,public_to_trajectory,public_events,attach_durable_public_journal
from a_accounting_snapshot.accounting import summarize

HERE=Path(__file__).resolve().parent
EXAMPLES=[json.loads(line) for line in (HERE/'a_interface_v1/examples.jsonl').read_text().splitlines()]
TEMPLATES={x['record_type']:x for x in EXAMPLES}

def transitions():
    rows=[];features={}
    refs=[{'path':f'synthetic://b10/frame/{i}','sha256':hashlib.sha256(str(i).encode()).hexdigest(),'format':'synthetic-json'} for i in range(13)]
    for i in range(12):
        r=copy.deepcopy(TEMPLATES['transition']);r.update(step=i,next_step=i+1,H=10,executed_prefix_length=1,observation_ref=refs[i],next_observation_ref=refs[i+1],raw_actions=[[0.]*4],normalized_actions=[[0.]*4],rewards=[float(i==11)],successes=[i==11],terminated=i==11,truncated=False,first_success_step=12 if i==11 else None,cut_reason='success' if i==11 else 'natural_boundary',terminal_success=True)
        r['identity'].update(node_role='B',task_id='B10',hostname='synthetic-B',run_id='synthetic-B10')
        if i!=11:r['missing_reasons']['first_success_step']='No successful action result has arrived'
        features[refs[i]['sha256']]=[0.]*4;rows.append(r)
    return rows,features

def events(ledger,**kwargs):
    context=copy.deepcopy(TEMPLATES['context']);context['method']['name']='GAF-v1-adapted'
    context['identity'].update(node_role='B',task_id='B10',hostname='synthetic-B',run_id='synthetic-B10')
    return public_events(ledger,context,hardware=TEMPLATES['event']['hardware'],synthetic=True,**kwargs)

class PublicTests(unittest.TestCase):
    def test_entered_event_is_durable_before_operation_and_failure(self):
        ledger=EventLedger();path=HERE/'evidence'/('durable_'+ledger.ledger_id+'.synthetic.jsonl')
        attach_durable_public_journal(ledger,path,TEMPLATES['context'],hardware=TEMPLATES['event']['hardware'],synthetic=True)
        with self.assertRaisesRegex(ValueError,'synthetic'):
            with ledger.operation('guided_sample'):
                entered=[json.loads(x) for x in path.read_text().splitlines()]
                self.assertEqual(len(entered),1);self.assertEqual(entered[0]['phase'],'entered')
                raise ValueError('synthetic interruption')
        wire=[json.loads(x) for x in path.read_text().splitlines()]
        self.assertEqual(summarize(wire)['counts']['vla_sampling_calls'],1)
        self.assertEqual(summarize(wire)['failed_events'],1)
    def test_all_seven_published_examples(self):
        for row in EXAMPLES:validate_record(row,allow_synthetic=True)
    def test_per_step_roundtrip_and_discount_index(self):
        rows,features=transitions()
        t=public_to_trajectory(rows,state_features_by_sha=features,task_features=[1.,0.],state_feature_sha256='a'*64,language_feature_sha256='b'*64,allow_synthetic=True)
        self.assertEqual(t['first_success_step'],12)
        self.assertEqual(float(gaf_view([t],split='development',gamma=.5)['targets'][0]),.5**11)
    def test_aggregate_endpoint_does_not_fabricate_intermediates(self):
        with self.assertRaisesRegex(ContractError,'per-step'):
            public_to_trajectory([TEMPLATES['transition']],state_features_by_sha={},task_features=[],state_feature_sha256='a'*64,language_feature_sha256='b'*64,allow_synthetic=True)
    def test_missing_reason_and_synthetic_fence(self):
        with self.assertRaises(ContractError):validate_record(TEMPLATES['context'])
        row=copy.deepcopy(TEMPLATES['event']);row['missing_reasons'].pop('error')
        with self.assertRaisesRegex(ContractError,'Null lacks'):validate_record(row,allow_synthetic=True)
    def test_accounting_success_failure_and_missing_terminal(self):
        ledger=EventLedger()
        with ledger.operation('guided_sample'):
            with ledger.operation('flow_forward'):pass
        try:
            with ledger.operation('guided_sample'):
                with ledger.operation('critic_forward'):raise ValueError('synthetic failure')
        except ValueError:pass
        ledger.emit('guided_sample',status='entered')
        wire=events(ledger,decision_index=2,sampling_index=4)
        actual=summarize(wire);deployment=summarize(wire,method='GAF-v1-adapted')
        self.assertEqual(actual['counts']['vla_sampling_calls'],3)
        self.assertEqual(actual['failed_events'],2);self.assertEqual(len(actual['incomplete_events']),1)
        self.assertEqual(actual['counts'],deployment['counts'])
        self.assertEqual({r['decision_index'] for r in wire},{2})
        self.assertEqual(summarize(wire,method='N')['counts']['vla_sampling_calls'],0)
    def test_research_shadow_and_reused_costs(self):
        ledger=EventLedger()
        with ledger.operation('monitor'):pass
        wire=events(ledger,methods=[],research_only=True)
        self.assertEqual(summarize(wire)['counts']['monitor_calls'],1)
        self.assertEqual(summarize(wire,method='N')['counts']['monitor_calls'],0)
        self.assertEqual(summarize(wire,event_refs=[wire[0]['event_id']]*2)['counts']['monitor_calls'],1)
        other=EventLedger()
        with other.operation('monitor'):pass
        self.assertNotEqual(wire[0]['event_id'],events(other)[0]['event_id'])
    def test_ensemble_guidance_matches_pinned_public_code(self):
        from guided_action_flow.guidance.qgf import QGuidanceConfig,q_guided_velocity
        generator=torch.Generator().manual_seed(42)
        x=torch.randn((2,50,32),generator=generator);v=torch.randn(x.shape,generator=generator)
        def make_q(scale):
            return lambda **kw:scale*kw['action_chunk'].square().sum((1,2))
        critics=[make_q(.2),make_q(.4),make_q(.6)]
        state=torch.zeros(2,4);task=torch.zeros(2,3);t=torch.tensor([.2,.8])
        adapter=GAFVelocityAdapter(critics,state=state,task_features=task,beta=2,clip=1,uncertainty_scale=20,min_gate=.1)
        expected,_=q_guided_velocity(critic=critics,obs_features=state,task_features=task,action_t=x[:,:10,:4],velocity_t=v[:,:10,:4],time_t=t,config=QGuidanceConfig(beta=2,grad_clip_norm=1,uncertainty_scale=20,min_gate=.1))
        actual,_=adapter(x,v,t)
        torch.testing.assert_close(actual[:,:10,:4],expected)
        torch.testing.assert_close(actual[:,10:,:],v[:,10:,:]);torch.testing.assert_close(actual[:,:10,4:],v[:,:10,4:])
        self.assertEqual(sum(e['event_type']=='critic_forward' and e['status']=='entered' for e in adapter.ledger.events),3)
    def test_d5_member_scales_and_missing_predictions(self):
        monitor=CausalD5Monitor(2.,np.array([[1.,1.],[2.,2.]]),'physical-branch0')
        monitor.register(issued_step=0,predicted_features=np.zeros((2,5,2)),conditioned_raw_actions=np.zeros((5,4)))
        kwargs=dict(issued_step=0,observed_step=5,actual_features=np.ones((5,2)),executed_raw_actions=np.zeros((5,4)),episode_id='physical-branch0',plan_age=5,remaining_queue=5)
        out=monitor.observe_or_skip(**kwargs);self.assertAlmostEqual(out['score'],.625)
        self.assertFalse(out['triggered'])
        out=monitor.observe_or_skip(**kwargs);self.assertIsNone(out['score']);self.assertFalse(out['triggered'])

if __name__=='__main__':unittest.main(verbosity=2)
