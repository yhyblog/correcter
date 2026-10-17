"""Read existing platform records; no simulation, fitting, or GPU calls."""
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
B = ROOT / 'sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1'
A = ROOT / 'sim_command/20260919/results/A/A_D24_LIBERO_FULL_NATIVE_V1/launch_r6'
CFG = ROOT / 'sim_command/20260919/work/B/B_D24_LIBERO_POST_V1_r1/configs/pi05official_Post_libero_10_s0_r1.json'


def read(path):
    return json.loads(path.read_text())


paths = sorted((B / 'jobs').glob('pi05official_Post_libero_*_r1/development.jsonl'))
rows = [json.loads(line) for p in paths for line in p.read_text().splitlines() if line.strip()]
fit = read(B / 'D24_E8_LIBERO_POST_r1/FIT_RESULT.json')
config, data, resource, terminal = read(CFG), read(A / 'DATA_STATUS.json'), read(A / 'RESOURCE_SUMMARY.json'), read(A / 'RESULT.json')
assert len(rows) == len({r['source_id'] for r in rows}) == 160
assert {r['status'] for r in rows} == {'complete'}
assert set(Counter(r['parent_id'] for r in rows).values()) == {5}
assert {r['intervention_step'] for r in rows} == {20}
steps = sum(r['steps'] for r in rows)
seconds = sum(r['elapsed_seconds'] for r in rows)
ends = [datetime.fromisoformat(r['at_utc']) for r in rows]
starts = [t - timedelta(seconds=r['elapsed_seconds']) for t, r in zip(ends, rows)]
real_path = ROOT / 'sim_command/20260919/deadline_20260924/analysis_20260923_master_completion/HISTORICAL_PAIR_AND_REAL_DATA.json'
real_counts = read(real_path)['real_world_user_counts']
record = {
    'source_type': 'existing runtime logs/configuration; derived arithmetic explicitly named',
    'libero': {
        'Q_rollout_files': [str(p) for p in paths],
        'Q_config': str(CFG),
        'Q_fit_receipt': str(B / 'D24_E8_LIBERO_POST_r1/FIT_RESULT.json'),
        'full_data_status': str(A / 'DATA_STATUS.json'),
        'full_resource_summary': str(A / 'RESOURCE_SUMMARY.json'),
        'Q_parent_count': len({r['parent_id'] for r in rows}),
        'Q_candidate_count_per_parent': 5,
        'Q_repeat_count': 1,
        'Q_attempts': len(rows),
        'Q_control_steps': steps,
        'Q_prefix_control_steps_derived': sum(r['intervention_step'] for r in rows),
        'Q_settle_steps_derived_from_completed_runs_and_config': len(rows) * config['settle_steps'],
        'Q_summed_episode_seconds': seconds,
        'Q_episode_span_seconds_derived': (max(ends) - min(starts)).total_seconds(),
        'Q_span_scope': 'first logged episode start to last end; excludes first model/env initialization',
        'DG_new_attempts': resource['actual_new_attempts'],
        'DG_complete': data['complete_new_attempts'],
        'DG_technical_failures': data['technical_failures'],
        'DG_control_steps': resource['phases']['development']['steps'],
        'DG_summed_saved_episode_seconds': resource['summed_saved_episode_host_seconds'],
        'total_registered_attempts': len(rows) + resource['actual_new_attempts'],
        'total_recorded_control_steps': steps + resource['phases']['development']['steps'],
        'total_environment_steps_including_all_reset_and_initialization': None,
        'full_collection_wall_seconds_including_failed_initialization': None,
        'D_two_step_window_rows': {'train': data['D_train_rows'], 'historical_validation': data['D_validation_rows']},
        'G_pairs': {'train': data['G0_train_pairs'], 'historical_validation': data['G0_validation_pairs']},
        'G_repeat_count': sorted({r['repeats_per_branch'] for r in data['G0_labels']}),
        'G_target_values': sorted(set(data['G0_train_targets'] + data['G0_validation_targets'])),
        'Q_L11_parent_filter': data['Q'],
        'Q_BCE_fit_configuration': config['adaptation'],
        'Q_BCE_actual_updates': fit['optimizer_updates'],
        'Q_BCE_epochs_per_member_derived': config['adaptation']['fit_steps'] * config['adaptation']['fit_batch_size'] / fit['train_rows'],
        'Q_BCE_fit_seconds': fit['elapsed_seconds'],
        'full_small_network_updates': terminal['actual_small_network_updates'],
        'full_physical_state_equivalence_proven': None,
    },
    'real_robot': {
        'archived_user_evaluation_summary': str(real_path),
        'summary_origin': 'user aggregate evaluation counts; not raw collection/training logs',
        'aggregate_evaluation_counts': real_counts,
        'total_evaluation_trials_derived': len(real_counts['tasks']) * 2 * real_counts['trials_per_task_per_method'],
        'D_Q_G_training_manifest': None,
        'recovery_protocol_configuration': None,
        'pairing_threshold_configuration': None,
        'mismatch_replay_log': None,
        'Q_repeat_count': None,
        'G_repeat_count': None,
        'auxiliary_collection_attempts': None,
        'auxiliary_training_updates': None,
    },
}
(OUT / 'PLATFORM_PROTOCOL_AUDIT.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({
    'libero_attempts': record['libero']['total_registered_attempts'],
    'libero_recorded_control_steps': record['libero']['total_recorded_control_steps'],
    'libero_Q_training_updates': fit['optimizer_updates'],
    'real_training_manifest': None,
}, ensure_ascii=False))
