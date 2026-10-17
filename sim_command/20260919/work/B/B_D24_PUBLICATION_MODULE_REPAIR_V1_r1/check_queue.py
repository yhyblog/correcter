"""CPU-only regression: partial stage resumes after its live parent yields.

All scheduler mutations and launches are replaced in memory; scientific files
are read-only. Completed true and false outcomes must both remain excluded.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W = C / 'work/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1_r1'
sys.path.insert(0, str(W))
import quota_runtime as q
import recovery_policy
import supervisor


def main():
    base = q.BASES['H20']
    expected = q.expected('H20')
    # The completed original stage is immutable. A concurrently started
    # continuation is excluded from this fixture, so this test is reproducible.
    original = {}
    for path in (base / 'runs').glob('*/episodes/*/RESULT.json'):
        row = q.read(path)
        if row['status'] == 'complete':
            original[row['unit_id']] = (row, path)
    assert len(original) == 24
    pending = set(expected) - set(original)
    assert len(pending) == 976
    seen = set(original)
    outcome_fixture = (original, original, seen, [])
    original_read = q.read
    fake_issue = q.C / 'nodes/B/issues/CPU_ONLY_TEST_DO_NOT_WRITE.json'

    def read_fixture(path, *args, **kwargs):
        if Path(path) == fake_issue:
            return {'attempted_repairs': []}
        return original_read(path, *args, **kwargs)

    fake_root = Path('/tmp/B_publication_repair_no_launch_fixture')
    with patch.object(q, 'roots', return_value=[base]), \
         patch.object(q, 'reconcile_dead'), \
         patch.object(q, 'clean_exit', return_value=True), \
         patch.object(q, 'stage_attempts', return_value=24), \
         patch.object(q, 'outcomes', return_value=outcome_fixture), \
         patch.object(q, 'expected', return_value=expected), \
         patch.object(q, 'read', side_effect=read_fixture), \
         patch.object(supervisor, 'read', side_effect=read_fixture), \
         patch.object(q, 'build_wave', return_value=fake_root) as build, \
         patch.object(q, 'launch', return_value=SimpleNamespace(pid=0)) as launch, \
         patch.object(supervisor, 'own_decision', return_value={'issue_id': fake_issue.stem}), \
         patch.object(recovery_policy, 'repair_gate') as gate:
        with patch.object(q, 'alive', side_effect=lambda r: Path(r) == q.P):
            waiting = supervisor.schedule('H20')
            assert waiting['status'] == 'existing_unique_parent_owns_stage'
            launch.assert_not_called()
        with patch.object(q, 'alive', return_value=False):
            resumed = supervisor.schedule('H20')
            assert resumed['status'] == 'launched_once'
            assert set(build.call_args.args[1]) == pending
            assert not set(build.call_args.args[1]) & set(original)
            assert gate.call_args.args[4] == 1076
            assert len(gate.call_args.args[2]) == 976
            launch.assert_called_once()
        build.reset_mock()
        launch.reset_mock()
        with patch.object(q, 'alive', side_effect=lambda r: Path(r) == base):
            active = supervisor.schedule('H20')
            assert active['status'] == 'own_stage_active'
            launch.assert_not_called()

    # Import the corrected package in its own original path context.
    sys.path.insert(0, str(base / 'code'))
    import publication_data
    assert Path(publication_data.__file__).resolve() == base / 'code/publication_data.py'
    sample = publication_data.finite_values({'success': False, 'stat': float('nan')})
    assert sample['success'] is False and sample['stat'] is None
    json.dumps(sample, allow_nan=False)
    result = dict(status='PASS', utc=q.utc(), real_GPU_calls=0,
                  actual_launches=0, scientific_files_modified=0,
                  legal_terminals_preserved=24,
                  legal_false_preserved=sum(not row['success'] for row, _ in original.values()),
                  only_original_unentered_units=976,
                  tests=['live parent retains original launch ownership',
                         'dead parent claim cannot permanently block corrected continuation',
                         'active continuation never duplicates launch',
                         'correct private module imports and preserves false in finite JSON'])
    q.new_json(C / 'results/B/B_D24_PUBLICATION_MODULE_REPAIR_V1/CPU_CHECKS.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
