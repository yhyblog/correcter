import copy
import hashlib
import json
from pathlib import Path
import struct
import unittest
import views

SIDE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/sidecar_v1')


def rows(namespace='Q_C10'):
    arms = ['a0','local_plus','local_minus'] if namespace == 'Q_C10' else ['old','fresh0','fresh1','fresh2']
    return [dict(parent='SYNTHETIC_parent',source='SYNTHETIC_source',split='train',source_signature='a'*64,
                 context_signature='b'*64,cut=55,target=namespace,commitment=10 if namespace=='Q_C10' else 5,
                 absolute_target=300,native_H=10,arm=arm,repeat=r,planned_repeats=[0,1],
                 physical_id=f'SYNTHETIC_{namespace}_{arm}_{r}',raw_group=hashlib.sha256(arm.encode()).hexdigest(),
                 raw_C10_sha256=hashlib.sha256(arm.encode()).hexdigest(),suffix_stream=f'SYNTHETIC/{namespace}/r{r}',
                 complete=True,success=int(arm!='a0' and arm!='old'),outcome_reason=None,full_state=True)
            for arm in arms for r in (0,1)]


class ViewTests(unittest.TestCase):
    def test_A_published_LVM_examples_terminal_unknown(self):
        d=json.loads((SIDE/'synthetic_examples.json').read_text())
        for ex in d['examples'][:2]:
            self.assertEqual(views.lvm(ex['record'])['eligible'], 'LVM' in ex['expected_admitted'])
        r=copy.deepcopy(d['examples'][0]['record']);original=copy.deepcopy(r)
        self.assertTrue(views.lvm(r)['eligible']);self.assertEqual(r,original)
        self.assertEqual(views.lvm(r)['terminal_flags_preserved'],dict(terminated=None,truncated=None))

    def test_LVM_rejects_encoder_action_shape_cross_episode(self):
        base=json.loads((SIDE/'synthetic_examples.json').read_text())['examples'][0]['record']
        for key,value in [('token_shape',[4096]),('token_end_encoder_sha256','6'*64),
                          ('original_action_normalizer_sha256','7'*64),('token_end_ref',None)]:
            r=copy.deepcopy(base);r['window'][key]=value;self.assertFalse(views.lvm(r)['eligible'])
        r=copy.deepcopy(base);r['window']['episode_ids'][-1]='other';self.assertFalse(views.lvm(r)['eligible'])
        r=copy.deepcopy(base);r['input_signatures']['action_representation']='actual_clipped_command';self.assertFalse(views.lvm(r)['eligible'])

    def test_D5_independent_of_GAF_terminal_and_short_window(self):
        d=views.window_indices(n=8,outcome_value=None,first_success_state=None)
        self.assertEqual(d['D5'],[0,1,2,3]);self.assertEqual(d['GAF'],[])
        d=views.window_indices(n=10,outcome_value=1,first_success_state=10)
        self.assertEqual(d['GAF'],[0]);self.assertAlmostEqual(d['GAF_targets'][0],.99**9)
        d=views.window_indices(n=48,outcome_value=1,first_success_state=48)
        self.assertEqual(len(d['D5']),44);self.assertEqual(len(d['GAF']),39)
        self.assertNotIn(55,d['GAF'])

    def test_window_rejects_gaps_action_mapping_feature_or_language(self):
        self.assertFalse(views.window_indices(n=20,outcome_value=0,first_success_state=None,episode_contiguous=False)['D5'])
        r=views.window_indices(n=20,outcome_value=0,first_success_state=None,bad_actions=[4],bad_features=[10],language_ok=False)
        self.assertNotIn(0,r['D5']);self.assertNotIn(5,r['D5']);self.assertFalse(r['GAF'])

    def test_s300_inclusive_and_technical_cutoff_never_zero(self):
        p=dict(parent_absolute_target_state=300)
        o=dict(outcome_complete=True,last_observed_parent_state=300,first_success_step=None,success=0,reason='absolute_s300_complete')
        self.assertEqual(views.outcome(o,p),(0,None))
        o.update(first_success_step=300,success=1,reason='success');self.assertEqual(views.outcome(o,p),(1,None))
        for reason in ['technical_failure','quota_exhausted','timeout','unknown_timelimit']:
            o.update(reason=reason,first_success_step=None,success=0);self.assertIsNone(views.outcome(o,p)[0])
        o.update(last_observed_parent_state=299,reason='absolute_s300_complete');self.assertIsNone(views.outcome(o,p)[0])
        o.update(reason='frozen_absorbing_failure',terminated=True);self.assertIsNone(views.outcome(o,p)[0])
        self.assertEqual(views.outcome(o,p,absorbing_rule_verified=True)[0],0)

    def test_full_double_repeat_gain_pair_G0_formulas(self):
        q=rows();self.assertEqual(views.paired(q,'gain_local_plus')['target'],1.)
        self.assertEqual(views.paired(q,'pair')['target'],0.)
        g=rows('G0_C5');self.assertEqual(views.paired(g,'G0')['target'],1.)
        g[-1]['success']=0;self.assertAlmostEqual(views.paired(g,'G0')['target'],5/6)
        self.assertIsNone(views.paired(q,'G0')['target'])

    def test_missing_repeat_BCE_remains_separate(self):
        q=rows();q.pop(3)
        r=views.paired(q,'gain_local_plus');self.assertFalse(r['target_mask']);self.assertEqual(r['valid_pair_repeat_ids'],[0])
        b=[g for g in views.bce_groups(q) if g['logical_arms']==['local_plus']][0]
        self.assertTrue(b['eligible']);self.assertEqual(b['effective_repeat_count'],1)
        q=rows()
        for r in q:r['full_state']=False
        self.assertFalse(views.paired(q,'pair')['target_mask']);self.assertTrue(all(g['eligible'] for g in views.bce_groups(q)))

    def test_cross_identity_repeat_protocol_rejected(self):
        for key,value in [('parent','other'),('cut',5),('split','development'),('context_signature','c'*64),
                          ('suffix_stream','bad'),('commitment',5),('repeat',4),('full_state',False)]:
            q=rows();q[2][key]=value;self.assertFalse(views.paired(q,'gain_local_plus')['target_mask'],key)
        q=rows();q.append(copy.deepcopy(q[2]));self.assertFalse(views.paired(q,'gain_local_plus')['target_mask'])
        q=rows();q[3]['physical_id']=q[2]['physical_id'];self.assertFalse(views.paired(q,'gain_local_plus')['target_mask'])

    def test_raw_C10_alias_tail_dedup_and_clamp_equality(self):
        a=struct.pack('<200f',*([2.]*200));b=a[:160]+struct.pack('<160f',*([3.]*160))
        self.assertEqual(views.raw_c10_group(a),views.raw_c10_group(b))
        c=struct.pack('<200f',*([3.]*200));self.assertNotEqual(views.raw_c10_group(a),views.raw_c10_group(c))
        q=rows()
        for row in q:
            if row['arm']=='local_plus':row['raw_group']=q[0]['raw_group'];row['raw_C10_sha256']=q[0]['raw_C10_sha256'];row['success']=0
        self.assertFalse(views.paired(q,'gain_local_plus')['target_mask'])
        self.assertEqual(len(views.bce_groups(q)),2)


if __name__=='__main__':
    unittest.main(verbosity=2)
