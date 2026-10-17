"""CPU-only checks for future policy5 descriptive reporting; no deployment."""
import unittest

import numpy as np

from experiments.native10_training_20260916.policy5_audit_v1 import summarize, audit_suffix_identities
from experiments.native10_training_20260916.protocol import suffix_seed


class Policy5SummaryTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(episode_id=f'e{i}', task=f't{i//2}', no_cut=i == 3) for i in range(4)]
        self.labels = np.zeros((4, 5, 4), dtype=bool)
        self.labels[3] = True  # Known full common outcome, not four independent initial states.

    def test_common_outcome_retained_and_seven_comparisons(self):
        result = summarize(self.labels, self.rows, bootstrap_replicates=100)
        self.assertEqual(result['overall']['sources'], 4)
        self.assertEqual(result['overall']['logical_outcomes_per_arm'], 16)
        self.assertEqual(result['overall']['success_counts']['alarm_replan10'], 4)
        self.assertEqual(result['no_cut_common_outcomes']['sources'], 1)
        self.assertEqual(result['alarm_conditioned']['sources'], 3)
        self.assertEqual(len(result['comparisons']), 7)
        for record in result['comparisons'].values():
            self.assertEqual(record['gain'], 0)
            self.assertEqual(record['source_95ci'], [0, 0])
            self.assertEqual(record['zero_sources'], 4)

    def test_rescues_harms_and_source_signs(self):
        self.labels[0, 2] = True
        self.labels[1, 1, :2] = True
        result = summarize(self.labels, self.rows, bootstrap_replicates=100)
        pair = result['comparisons']['velocity_minus_alarm_replan10']
        self.assertEqual((pair['rescues'], pair['harms']), (4, 2))
        self.assertEqual(pair['gain'], 2/16)
        self.assertEqual((pair['positive_sources'], pair['negative_sources'], pair['zero_sources']), (1, 1, 2))
        self.assertEqual(result, summarize(self.labels, self.rows, bootstrap_replicates=100))

    def test_unknown_never_zero_imputed(self):
        bad = self.labels.astype(float); bad[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            summarize(bad, self.rows, bootstrap_replicates=100)

    def test_duplicate_episode_and_bad_dimensions_rejected(self):
        rows = [dict(row) for row in self.rows]; rows[1]['episode_id'] = rows[0]['episode_id']
        with self.assertRaises(ValueError):
            summarize(self.labels, rows, bootstrap_replicates=100)
        with self.assertRaises(ValueError):
            summarize(self.labels[:, :, :3], self.rows, bootstrap_replicates=100)

    def test_suffix_index_cannot_skip_or_repeat(self):
        case = dict(episode_id='disassemble-v3__9001', task='disassemble-v3', env_seed=9001)
        namespace = 'unit_test'
        valid = [dict(decision_index=i, seed=suffix_seed(case, 5, 0, i, namespace=namespace),
                      noise_sha256='a'*64) for i in range(2)]
        shared = {}; audit_suffix_identities(valid, case, 5, 0, namespace, shared)
        self.assertEqual(set(shared), {(0, 0), (0, 1)})
        for sequence in (valid[1:], [valid[0], valid[0]], [dict(valid[0], decision_index=False)]):
            with self.assertRaises(ValueError):
                audit_suffix_identities(sequence, case, 5, 0, namespace, {})
        with self.assertRaises(ValueError):
            audit_suffix_identities([dict(valid[0], noise_sha256='b'*64)], case, 5, 0, namespace, shared)


if __name__ == '__main__':
    unittest.main()
