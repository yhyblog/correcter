"""CPU-only audit of completed V3 files; no numerical method replay or imports."""
import ast
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import zipfile

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'A10_PV_OFFLINE_PREFLIGHT_V3'
WORK = BASE / 'work/A' / (TASK + '_r1')
OUT = BASE / 'results/A' / TASK
LAUNCH = BASE / 'results/A/P10_PV_V3_launcher_runs/A10_PV_OFFLINE_PREFLIGHT_V3_r1_A_wave08'
DIAG = LAUNCH / 'diagnostic'
PACKAGE = BASE / 'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1'


def read(path):
    return json.loads(path.read_text())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def ref(path):
    raw = path.read_bytes()
    return dict(path=str(path), sha256=digest(raw), size_bytes=len(raw))


def put(path, value):
    if path.exists():
        assert read(path) == value, 'Previously written CPU audit differs; do not overwrite'
        return
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def npy(raw):
    assert raw[:6] == b'\x93NUMPY'
    version = tuple(raw[6:8])
    assert version in [(1, 0), (2, 0), (3, 0)]
    width = 2 if version == (1, 0) else 4
    length = int.from_bytes(raw[8:8 + width], 'little')
    header = ast.literal_eval(raw[8 + width:8 + width + length].decode().strip())
    payload = raw[8 + width + length:]
    assert header['fortran_order'] is False
    size, fmt = {'<f4': (4, '<f'), '<f8': (8, '<d'), '|b1': (1, '<?')}[header['descr']]
    assert len(payload) == math.prod(header['shape']) * size
    values = [value[0] for value in struct.iter_unpack(fmt, payload)]
    assert all(math.isfinite(x) for x in values)
    return dict(header=header, payload=payload, values=values)


def arrays(path):
    if path.suffix == '.npy':
        return {path.name: npy(path.read_bytes())}
    with zipfile.ZipFile(path) as archive:
        return {name: npy(archive.read(name)) for name in archive.namelist()}


def ledger(path, caps):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    entered, returned = {}, {}
    counts, finished = dict.fromkeys(caps, 0), dict.fromkeys(caps, 0)
    for row in rows:
        event = row['event_id']
        if row['phase'] == 'entered':
            assert event not in entered
            entered[event] = row
            for name, value in row['units'].items():
                assert name in caps and type(value) is int and value >= 0
                counts[name] += value
        else:
            assert row['phase'] == 'returned' and row['error'] is None
            assert event in entered and event not in returned
            assert row['monotonic'] >= entered[event]['monotonic']
            returned[event] = row
            for name, value in entered[event]['units'].items():
                finished[name] += value
    assert set(entered) == set(returned) == set(range(1, len(entered) + 1))
    assert counts == finished == caps
    return dict(path=str(path), private_event_id_scope=str(path), entered_events=len(entered),
                returned_events=len(returned), entered=counts, returned=finished,
                failed=[], unresolved=[], status='PASS')


def main():
    launch = read(LAUNCH / 'LAUNCH_RESULT.json')
    outer = read(WORK / 'COMMAND_RESULT.json')
    release = read(BASE / 'releases/P10_A_PV_OFFLINE_PREFLIGHT_V3.json')
    cfg = read(PACKAGE / 'config/CONFIG.json')
    assert launch['status'] == 'complete' and launch['returncode'] == 0 and launch['error'] is None
    assert outer['exit_code'] == 0 and outer['child_reaped'] and outer['spawned_commands'] == 1
    parent = ledger(LAUNCH / 'launcher_events.jsonl', release['launcher_caps'])
    child = ledger(DIAG / 'events.jsonl', release['diagnostic_caps'])
    totals = {key: parent['entered'].get(key, 0) + child['entered'].get(key, 0)
              for key in release['resource_caps']}
    assert totals == release['resource_caps'] == launch['total_entered'] == launch['total_returned']
    put(OUT / 'PRIVATE_LEDGER_AUDIT.json', dict(
        status='PASS', launcher=parent, diagnostic=child, resource_totals_after_separate_reconciliation=totals,
        counter_count=len(totals), event_ids_merged=False, public_interface_UUID_ledger=False,
        incremental_entered_units=True, nested_aliases_must_not_be_added=True,
        client_handoff_poll_count=None, persistent_daemon_poll_count=None,
        poll_missing_reason='Successful poll counts/raw empty response were not emitted by the frozen client; no additional query.'))

    saved = {}
    for path in sorted(DIAG.iterdir()):
        if path.suffix in ['.npy', '.npz']:
            saved[path.name] = arrays(path)
    summary = {name: {key: dict(value['header'], payload_sha256=digest(value['payload']),
                                payload_size=len(value['payload']), finite=True)
                      for key, value in items.items()} for name, items in saved.items()}
    raw = saved['cached_raw_a0.npy']['cached_raw_a0.npy']['payload']
    assert digest(raw) == cfg['source']['raw50_sha256']
    source_raw = npy(Path(cfg['source']['raw_plans_path']).read_bytes())
    assert source_raw['header']['shape'] == (5, 50, 4)
    assert source_raw['payload'][:len(raw)] == raw
    noise = saved['reconstructed_noise.npy']['reconstructed_noise.npy']
    assert noise['header']['shape'] == (1, 50, 32) and digest(noise['payload']) == cfg['source']['noise_sha256']
    branches = {}
    for branch in ['Post', 'Velocity']:
        items = saved[branch + '_arrays.npz']
        result = read(DIAG / (branch + '_result.json'))
        plan = items['raw_plan.npy']['payload']
        mask = items['mask.npy']['values']
        delta = items['actual_delta.npy']['values']
        assert items['raw_a0.npy']['payload'] == raw
        assert digest(plan) == result['audit']['raw_plan_sha256']
        assert digest(items['raw_direction.npy']['payload']) == result['audit']['direction_sha256']
        assert plan[160:] == raw[160:]
        unchanged = lambda i: plan[4 * i:4 * (i + 1)] == raw[4 * i:4 * (i + 1)]
        assert all(unchanged(i) for i in range(40) if not mask[i])
        assert all(unchanged(i) for i in range(40) if delta[i] == 0)
        assert result['audit']['status'] == 'passed' and result['Q_acceptance_gate'] is False
        branches[branch] = dict(tail40_bit_exact=True, mask_outside_bit_exact=True,
                                zero_delta_bit_exact=True, raw_anchor_bit_exact=True,
                                array_hashes_match_runtime_audit=True,
                                own_radius_runtime_audit=result['audit']['own_only_projection'],
                                other_directions_used=result['matching']['other_directions_used'])
    context = saved['Q_observed_context.npz']
    encoder = saved['same_source_encoder_outputs.npz']
    assert context['history_mask.npy']['payload'] == b'\0\0\0\0\1'
    assert context['proprio_mask.npy']['payload'] == b'\0\0\0\0\1'
    assert context['past_actions.npy']['payload'] == bytes(64)
    assert context['history.npy']['payload'][:4 * 4096 * 4] == bytes(4 * 4096 * 4)
    assert context['proprio.npy']['payload'][:64] == bytes(64)
    assert context['history.npy']['payload'][4 * 4096 * 4:] == encoder['spatial.npy']['payload']
    assert context['language.npy']['payload'] == encoder['language.npy']['payload']
    with zipfile.ZipFile(Path(cfg['source']['observation_path'])) as source_archive:
        source_obs = {'proprioception.npy': npy(source_archive.read('proprioception.npy'))}
    step0_proprio_f32 = b''.join(struct.pack('<f', value) for value in source_obs['proprioception.npy']['values'])
    assert context['proprio.npy']['payload'][64:] == step0_proprio_f32
    put(OUT / 'SAVED_ARRAY_AUDIT.json', dict(status='PASS', method='stdlib NPY/ZIP byte and finite-value inspection only; no model or projection replay',
        arrays=summary, array_count=sum(len(v) for v in saved.values()), branches=branches,
        history_mask=[0, 0, 0, 0, 1], past_actions_zero=True, masked_history_padding_zero=True,
        source_step0_proprio_exact=True, encoder_context_payloads_match=True,
        source_raw0_payload_exact=True, noise_payload_sha256=digest(noise['payload']),
        source_array_refs=[ref(Path(cfg['source']['raw_plans_path'])), ref(Path(cfg['source']['observation_path']))]))

    marks = [json.loads(row) for row in (LAUNCH / 'wave_timing.jsonl').read_text().splitlines()]
    by_phase = {row['phase']: row for row in marks}
    start = datetime.datetime.fromisoformat(outer['started_at_utc']).replace(microsecond=0)
    end = datetime.datetime.fromisoformat(outer['finished_at_utc'])
    log_path = Path('/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.log')
    selected = []
    with log_path.open() as stream:
        for line in stream:
            try:
                when = datetime.datetime.strptime(line[:20], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                continue
            if start <= when <= end:
                selected.append((when.timestamp(), line.rstrip('\n')))
    with (WORK / 'GUARD_LOG_EXCERPT.txt').open('x') as stream:
        stream.write('\n'.join(line for _, line in selected) + '\n')
    yields, starts = {}, {}
    for when, line in selected:
        match = re.search(r'GPU (\d): (.*)', line)
        if not match:
            continue
        gpu, detail = match.groups()
        if 'yielded;' in detail:
            yields[gpu] = dict(unix_seconds=when, line=line)
        if 'started holder manager' in detail:
            assert when > by_phase['lifecycle_returned']['unix_seconds']
            starts[gpu] = dict(unix_seconds=when, line=line)
    assert set(yields) == set(starts) == set(map(str, range(8)))
    restoration = launch['restoration']
    assert restoration['status'] == 'occupancy_resolved'
    assert all(row['state'] == 'holder' and row['driver_pids'] for row in restoration['guard_status']['gpus'].values())
    assert launch['process_family_cleanup']['status'] == 'all_formal_group_members_exited'
    assert launch['process_family_cleanup']['actions'] == []
    late_yields = {key: row for key, row in yields.items()
                   if row['unix_seconds'] > by_phase['reserved_command_started']['unix_seconds']}
    put(OUT / 'HANDOFF_LIFECYCLE_AUDIT.json', dict(status='PASS', timing=launch['timing'],
        handoff_environment=read(LAUNCH / 'handoff_environment.json'), formal_cleanup=launch['process_family_cleanup'],
        launcher_reaped=outer['child_reaped'], restoration=restoration, yielded_rows=yields, restored_rows=starts,
        no_holder_start_logged_during_formal_window=True, source_log=str(log_path), excerpt=ref(WORK / 'GUARD_LOG_EXCERPT.txt'),
        handoff_client_success_poll_count=None, handoff_client_success_last_empty_rows=None,
        persistent_daemon_poll_count=None, extra_hardware_queries_for_audit=0,
        identity_query_count=totals['native_nvml_identity_queries'],
        yielded_log_rows_after_reserved_entry=late_yields,
        yielded_timestamp_semantics='Daemon logs yielded after stop(manager) returns; stop may wait15s after signalling. These timestamps are not last GPU-compute times. GPU7 log is later than reserved entry; the successful frozen client empty-compute-apps gate is the launch evidence. Its raw successful poll was not saved, and is not fabricated.',
        runtime_handoff_scope='Single successful handoff in this attempt; no general reliability claim.'))
    numeric = read(DIAG / 'numeric_checks.json')
    loader = read(DIAG / 'policy_loader.json')
    device = read(DIAG / 'policy_device.json')
    assert numeric['status'] == 'passed' and numeric['frozen_models'] and numeric['finite_action_gradients']
    assert len(loader['file_calls']) == len(loader['state_calls']) == 1 and loader['errors'] == []
    assert loader['state_calls'][0]['strict'] and loader['state_calls'][0]['returned']
    assert not loader['state_calls'][0]['missing_keys'] and not loader['state_calls'][0]['unexpected_keys']
    assert device['accepted'] and device['conversion_calls'] == 1 and device['normalized_uuid'] == release['device']['gpu_uuid']
    post = read(DIAG / 'Post_result.json');velocity = read(DIAG / 'Velocity_result.json')
    put(OUT / 'NUMERIC_SUMMARY.json', dict(status='PASS', scope='one cached step0 numerical diagnostic only',
        source=cfg['source'], numeric_checks=numeric, policy_loader=loader, policy_device=device,
        Post=dict(score=post['score'], gradient=post['gradient'], matching=post['matching'], constraints=post['audit']),
        Velocity=dict(score=velocity['score'], updates=velocity['updates'], matching=velocity['matching'], constraints=velocity['audit']),
        velocity_local_objective_decrease_taus=[r['tau'] for r in velocity['updates'] if r['objective_after'] < r['objective_before']],
        no_Q_acceptance_gate=True, diagnostic_sampling_calls=dict(Post=0, Velocity=1),
        deployment_sampling_calls=dict(Post=1, Velocity=2), deployment_cost_comparison=False,
        task_success_sample=False, MT50_Q_training_completed=False,
        peak_vram_measurement_scope='PyTorch allocator peak in diagnostic process; not whole-device utilization integral',
        measured_peak_host_RAM_bytes=None, GPU_utilization_seconds=None))
    print(json.dumps(dict(status='PASS', parent_private_events=parent['entered_events'],
                         child_private_events=child['entered_events'], resource_counter_count=len(totals),
                         saved_array_count=sum(len(v) for v in saved.values()), output=str(OUT)), indent=2))


if __name__ == '__main__':
    main()
