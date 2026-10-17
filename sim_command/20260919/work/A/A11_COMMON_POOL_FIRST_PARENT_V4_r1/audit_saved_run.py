"""Post-run CPU audit of saved files only. No runtime/project imports or probes."""
import collections
import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
B = ROOT / 'Corrector/sim_command/20260919'
TASK = 'A11_COMMON_POOL_FIRST_PARENT_V4'
W = B / 'work/A' / (TASK + '_r1')
OUT = B / 'results/A' / TASK
PREP = B / 'results/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1'
RELEASE = B / 'releases/P11_A_COMMON_POOL_FIRST_PARENT_V4.json'


def read(p):
    return json.loads(Path(p).read_text())


HASH_CACHE = {}


def ref(p):
    p = Path(p)
    st = p.stat()
    key = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    if key not in HASH_CACHE:
        h = hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        HASH_CACHE[key] = h.hexdigest()
    return {'path': str(p), 'realpath': str(p.resolve()),
            'sha256': HASH_CACHE[key], 'size_bytes': st.st_size}


def write(name, obj):
    p = OUT / name
    with p.open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    return ref(p)


def ledger(path, kind):
    starts, ends, issues = {}, {}, []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            row = json.loads(line)
            key, phase = row['event_id'], row['phase']
            if phase == 'entered':
                assert key not in starts, 'duplicate entry'
                units = row.get('units', row.get('resource_units'))
                assert isinstance(units, dict)
                assert all(k in caps and type(v) is int and v >= 0 for k, v in units.items())
                starts[key] = (row, units)
            else:
                assert phase in ('returned', 'failed', 'raised'), 'invalid phase'
                assert key in starts and key not in ends, 'orphan/duplicate terminal'
                first, units = starts[key]
                if kind == 'initialization':
                    assert all(row[k] == first[k] for k in ('units', 'source', 'stage', 'wall_start'))
                if kind == 'graphics':
                    assert row['operation'] == first['operation']
                    assert row['resource_units'] == units
                ends[key] = row
        except Exception as e:
            issues.append({'line': line_number, 'error': type(e).__name__ + ': ' + str(e)})
    counts = {phase: dict.fromkeys(caps, 0) for phase in ('entered', 'returned', 'failed', 'incomplete')}
    failed, missing = [], []
    for key, (row, units) in starts.items():
        terminal = ends.get(key)
        phase = 'incomplete' if terminal is None else ('returned' if terminal['phase'] == 'returned' else 'failed')
        if phase == 'incomplete':
            missing.append(key)
        if phase == 'failed':
            failed.append(key)
        for k, v in units.items():
            counts['entered'][k] += v
            counts[phase][k] += v
    return {'reference': ref(path), 'kind': kind, 'identity_scope': str(path),
            'events_entered': len(starts), 'events_returned': sum(x['phase'] == 'returned' for x in ends.values()),
            'events_failed': len(failed), 'events_incomplete': len(missing),
            'failed_ids': failed, 'incomplete_ids': missing, 'record_errors': issues,
            'counts_complete': not issues and not missing, **counts}


if __name__ == '__main__':
    # The outer wrapper writes this only after the single command has exited.
    outer = read(W / 'OUTER_EXECUTION_RESULT.json')
    r = read(RELEASE)
    assert ref(RELEASE)['sha256'] == 'b924b93d2318edcf22dfe36d0bafee6df5feebc02432d26375e4e6ca37d3723a'
    run = Path(r['paths']['output'])
    launch = read(run / 'launcher/LAUNCH_RESULT.json')
    wave = read(run / 'reserved/WAVE_EXIT.json')
    caps = r['resource_caps']
    assert len(caps) == 116
    OUT.mkdir(exist_ok=False)
    planned = read(run / 'reserved/ATTEMPT_COVERAGE.json')['planned']
    scopes = [ledger(run / 'launcher/events.jsonl', 'launcher_numeric')]
    comparisons, rows, state_checks, event_checks = [], [], [], []
    failures, device_rows, raw_results, missing_ledgers = [], [], {}, []
    normal_state = read(run / 'normal/CUT_STATE.json') if (run / 'normal/CUT_STATE.json').exists() else None
    for item in planned:
        name = item['role']
        d = run / name
        result = read(d / 'BRANCH_RESULT.json') if (d / 'BRANCH_RESULT.json').exists() else None
        raw_results[name] = result
        events = [json.loads(x) for x in (d / 'events.jsonl').read_text().splitlines()] if (d / 'events.jsonl').exists() else []
        commit = next((x for x in events if x['event'] == 'commitment_finished'), None)
        entry = next((x for x in events if x['event'] == 'intervention_entered'), None)
        after = [x for x in events if x['event'] == 'H10_plan_installed' and x.get('absolute_step', -1) >= (commit['absolute_step'] if commit else 301)]
        event_checks.append(dict(branch=name, events=len(events), synthetic_values=sorted({str(x.get('synthetic')) for x in events}),
            unique_local_event_ids=len({x['event_id'] for x in events}) == len(events),
            commitment_entered=entry, commitment_finished=commit,
            first_suffix_H10=after[0] if after else None))
        sidecar = read(d / 'SIDECAR_V1.json') if (d / 'SIDECAR_V1.json').exists() else None
        state = read(d / 'STATE_VERIFICATION.json') if (d / 'STATE_VERIFICATION.json').exists() else None
        if state:
            observed = read(d / 'CUT_STATE.json')
            a = {x['name']: x for x in normal_state['fields']}
            z = {x['name']: x for x in observed['fields']}
            differences = sorted(k for k in set(a) | set(z) if a.get(k) != z.get(k))
            state_checks.append(dict(branch=name, saved_level=state['level'], tolerance=state['tolerance'],
                saved_bitwise_equal=state['bitwise_equal'], field_count=len(state['fields']),
                raw_captured_fields_equal=not differences, raw_field_differences=differences,
                raw_unknown_fields=observed['unknown_fields'], saved_unknown_fields=state['unknown_fields'],
                MJB_ref=ref(d / 'cut_model.mjb'), MJB_matches_normal=ref(d / 'cut_model.mjb')['sha256'] == ref(run / 'normal/cut_model.mjb')['sha256'],
                physical_equality_proven=state['physical_equality_proven'], qualification_scope=state['qualification_scope'],
                verification_ref=ref(d / 'STATE_VERIFICATION.json')))
        saved = read(d / 'RESOURCE_LEDGER.json') if (d / 'RESOURCE_LEDGER.json').exists() else None
        local_scopes = []
        if saved:
            for fname, kind, saved_counts in [
                ('numeric_events.jsonl', 'numeric', saved['numeric']['entered']),
                ('initialization_events.jsonl', 'initialization', saved['initialization']['entered_budget_usage']),
                ('graphics_events.jsonl', 'graphics', saved['graphics']['entered_budget_usage'])]:
                s = ledger(d / fname, kind)
                s['branch'] = name
                matches = all(s['entered'][k] == v for k, v in saved_counts.items())
                comparisons.append(dict(branch=name, kind=kind, saved_entered_matches=matches))
                assert matches
                local_scopes.append(s)
            assert all(sum(s['entered'][k] for s in local_scopes) == v for k, v in saved['total_entered'].items())
            scopes.extend(local_scopes)
            if saved['primary'] or saved['cleanup']:
                failures.append(dict(branch=name, primary=saved['primary'], cleanup=saved['cleanup']))
        elif item['started']:
            missing_ledgers.append(dict(branch=name, reason='Started branch has no final RESOURCE_LEDGER; wave sums are known recorded lower bounds.'))
            for fname, kind in [('numeric_events.jsonl', 'numeric'), ('initialization_events.jsonl', 'initialization'), ('graphics_events.jsonl', 'graphics')]:
                if (d / fname).exists():
                    s = ledger(d / fname, kind)
                    s['branch'] = name
                    local_scopes.append(s)
                    scopes.append(s)
        if (d / 'policy_device.json').exists():
            device_rows.append(dict(branch=name, device=read(d / 'policy_device.json'), loader=read(d / 'policy_loader.json'),
                device_ref=ref(d / 'policy_device.json'), loader_ref=ref(d / 'policy_loader.json')))
        complete = bool(result and result.get('status') == 'complete' and result.get('outcome', {}).get('outcome_complete'))
        rows.append(dict(**item, execution_status=result.get('status') if result else ('failed_or_incomplete' if item['started'] else 'not_started'),
            controls_returned=result['controls'] if result else (local_scopes[0]['returned']['env_steps'] if local_scopes else None),
            observations_returned=local_scopes[0]['returned']['observation_calls'] if local_scopes else None,
            legal_cut_reached=result.get('legal_cut_reached') if result else any(x['event'] == 'cut_captured' for x in events),
            commitment_steps_returned=commit['actual_steps'] if commit else 0,
            discarded_raw_tail=commit['discarded_raw_tail'] if commit else None,
            H10_suffix_resumed=bool(after), absolute_s300_reached=bool(result and result['controls'] == 300),
            outcome_complete=complete, success=result['outcome']['success'] if complete else None,
            success_missing_reason=None if complete else 'No completed task outcome; technical failure is not success=0.',
            restore_level=result.get('restore_level') if result else (state['level'] if state else None),
            full_state_verified=bool(state and state['level'] == 'full_state_verified' and state['bitwise_equal']),
            qualification_scope=state['qualification_scope'] if state else 'normal reference capture only' if name == 'normal' else 'not_measured',
            intervention_evidence=result.get('intervention_evidence') if result else saved.get('intervention_evidence') if saved else None,
            sidecar_restoration={k: v for k, v in sidecar['restoration'].items() if k != 'fields'} if sidecar else None,
            single_outcome_qualified=complete, repeat_metadata=sidecar['repeats'] if sidecar else None))

    totals = {phase: {k: sum(s[phase][k] for s in scopes) for k in caps}
              for phase in ('entered', 'returned', 'failed', 'incomplete')}
    cap_violations = {k: dict(actual=v, cap=caps[k]) for k, v in totals['entered'].items() if v > caps[k]}
    complete_counts = not missing_ledgers and all(s['counts_complete'] for s in scopes)
    write('INDEPENDENT_LEDGER_AUDIT.json', dict(private_scopes=scopes, saved_comparisons=comparisons,
        totals=totals, release_caps=caps, cap_violations=cap_violations, within_all_116_caps=not cap_violations,
        counts_complete=complete_counts, public_UUID_bridge=False,
        semantics='Per-file event identities; entered charged once. Only operation vectors are summed. Guard polling is not an NVML identity event.',
        primary_and_cleanup_failures=failures, missing_final_ledgers=missing_ledgers,
        operation_totals_are_lower_bounds_if_counts_incomplete=True))
    labels = read(run / 'reserved/PAIRED_LABELS.json')
    write('BRANCH_COVERAGE.json', dict(planned_attempts=15, actually_started=[x['role'] for x in rows if x['started']],
        complete_outcomes=[x['role'] for x in rows if x['outcome_complete']],
        full_state_verified=[x['role'] for x in rows if x['full_state_verified']],
        per_branch=rows, paired_labels=labels, paired_labels_ref=ref(run / 'reserved/PAIRED_LABELS.json'),
        no_success_zero_for_missing_outcome=True, not_a_method_ranking=True))
    write('STATE_AND_COMMITMENT_AUDIT.json', dict(state_comparisons=state_checks,
        normal_state_ref=ref(run / 'normal/CUT_STATE.json') if normal_state else None,
        normal_MJB_ref=ref(run / 'normal/cut_model.mjb') if normal_state else None,
        reference_state_unknown_fields=normal_state['unknown_fields'] if normal_state else None,
        event_audits=event_checks, event_IDs_scoped_to_each_branch=True,
        interpretation='Exact captured fields and MJB under frozen closure only; physical_equality_proven stays null. Forced candidate collection is distinct from online G0 triggering.'))
    write('IDENTITY_AND_INPUTS.json', dict(release=ref(RELEASE), identity=r['identity'], source=r['source'],
        device=r['device'], actual_devices_and_strict_loaders=device_rows,
        frozen_proposal_ref=ref(PREP / 'proposal/PROPOSAL.json'), frozen_config_ref=ref(PREP / 'config/CONFIG.json'),
        frozen_input_manifest_ref=ref(PREP / 'INPUT_MANIFEST.json'),
        weights_or_external_driver_libraries_postrun_rehashed=False,
        preceding_V3_consumed_closed_not_reused=True))

    group = read(run / 'reserved/PROCESS_GROUP_EXIT.json')
    child_exits = []
    for item in planned:
        path = run / 'reserved' / (item['role'] + '_EXIT.json')
        if path.exists():
            child_exits.append(dict(branch=item['role'], exit=read(path), reference=ref(path)))
    gpus = launch.get('restoration', {}).get('guard_status', {}).get('gpus', {})
    holders = sum(x.get('state') == 'holder' for x in gpus.values())
    log = ROOT / 'gpu_occupancy_guard.log'
    with log.open('rb') as f:
        offset = max(0, log.stat().st_size - 1000000)
        f.seek(offset)
        text = f.read().decode(errors='replace')
    start, end = outer['started_at_utc'][:19], outer['ended_at_utc'][:19]
    lines = [x for x in text.splitlines() if start <= x[:19] <= end]
    with (OUT / 'HOLDER_MANAGER_LOG_WINDOW.txt').open('x') as f:
        f.write('\n'.join(lines) + '\n')
    write('EXIT_AND_RESTORATION.json', dict(raw_outer_execution=outer, saved_wave_exit=wave,
        saved_process_group_exit=group, saved_child_exits=child_exits,
        all_started_children_exit_evidenced=len(child_exits) == sum(x['started'] for x in planned),
        all_saved_child_cleanup_complete=all(x['exit'].get('cleanup_complete') is True and x['exit'].get('remaining_group') == [] for x in child_exits),
        saved_restoration=launch['restoration'], holder_count_restored=holders,
        manager_log_window=ref(OUT / 'HOLDER_MANAGER_LOG_WINDOW.txt'),
        successful_handoff_raw_poll_count=launch['successful_handoff_raw_poll_count'],
        handoff_missing_reason=launch['handoff_missing_reason'],
        manager_times_are_not_successful_raw_poll_evidence=True,
        timeouts_by_scope=r['timeouts'], observed_launcher_seconds=launch['elapsed_seconds'],
        observed_preparation_seconds=read(run / 'launcher/LIFECYCLE_REQUESTED.json')['elapsed_preparation'],
        GPU_seconds=None, GPU_seconds_missing_reason='No direct compute-duration measurement; wall time is not GPU seconds.',
        postrun_hardware_process_or_holder_probes=0))

    files = [p for p in run.rglob('*') if p.is_file()]
    inodes = {}
    for p in files:
        st = p.stat()
        inodes.setdefault((st.st_dev, st.st_ino), (st.st_size, st.st_blocks * 512))
    monitor = [json.loads(x) for x in (run / 'launcher/STORAGE_MONITOR.jsonl').read_text().splitlines()]
    write('STORAGE_AUDIT.json', dict(admission=read(run / 'launcher/STORAGE_ADMISSION.json'),
        saved_monitor_summary=launch['storage_monitor'], monitor_records=len(monitor), monitor_last=monitor[-1],
        runtime_file_paths=len(files), unique_inodes=len(inodes),
        path_bytes_including_hardlink_aliases=sum(p.stat().st_size for p in files),
        unique_inode_payload_bytes=sum(x[0] for x in inodes.values()),
        reported_unique_inode_allocated_bytes=sum(x[1] for x in inodes.values()),
        bounded_storage_unknowns_preserved=['project quota', 'exclusive reservation', 'unlinked files',
            'shared cache/native outside-path writes', 'scan/drain overshoot', 'RSS peak'],
        postrun_capacity_query=False, deletion=False))
    # SHA every saved runtime file; cache hardlink contents. No model/driver assets.
    runtime_rows = [ref(p) for p in sorted(files)]
    write('RUNTIME_FILE_MANIFEST.json', dict(files=runtime_rows, file_count=len(runtime_rows),
        retains_partial_hardlink_alias_paths=True, new_runtime_files_only=True))
    print(json.dumps(dict(stage='saved_ledgers_coverage_and_runtime_files_audited',
        scopes=len(scopes), runtime_files=len(runtime_rows), complete_outcomes=sum(x['outcome_complete'] for x in rows),
        counts_complete=complete_counts, cap_violations=cap_violations, holders=holders)), flush=True)
    reference_checks = {}
    reference_errors = []
    def inspect_refs(value, source):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                path = Path(value['path'])
                if path.is_relative_to(run):
                    key = str(path)
                    if key not in reference_checks:
                        reference_checks[key] = dict(actual=ref(path), reference_count=0, expected_SHAs=[], examples=[])
                    check = reference_checks[key]
                    check['reference_count'] += 1
                    if value['sha256'] not in check['expected_SHAs']:
                        check['expected_SHAs'].append(value['sha256'])
                    if len(check['examples']) < 2 and source not in check['examples']:
                        check['examples'].append(source)
                    if value['sha256'] != check['actual']['sha256']:
                        reference_errors.append(dict(source=source, path=key, expected=value['sha256'], actual=check['actual']['sha256']))
            for x in value.values():
                inspect_refs(x, source)
        elif isinstance(value, list):
            for x in value:
                inspect_refs(x, source)
    for p in files:
        if p.suffix == '.json':
            inspect_refs(read(p), str(p))
    write('RUNTIME_REFERENCE_AUDIT.json', dict(status='PASS' if not reference_errors else 'FAILED',
        unique_referenced_files=len(reference_checks), reference_count=sum(x['reference_count'] for x in reference_checks.values()),
        checks=reference_checks, errors=reference_errors, no_model_or_external_driver_rehash=True))
    bank = read(run / 'normal/BANK.json') if (run / 'normal/BANK.json').exists() else None
    bank_checks = []
    if bank:
        for key, item in bank['plans'].items():
            path = Path(item['raw50_ref']['path'])
            data = path.read_bytes()
            bank_checks.append(dict(plan_key=key, raw50_ref=ref(path), raw50_bytes=len(data),
                declared_shape=item['shape'], declared_dtype=item['dtype'],
                noise_ref=item.get('noise_ref'), logical_alias_of=item.get('logical_alias_of'),
                exact_declared_SHA=ref(path)['sha256'] == item['raw50_ref']['sha256']))
        a0 = bank['plans']['a0']
        f0 = bank['plans']['fresh0']
        alias_exact = a0['raw50_ref'] == f0['raw50_ref'] and a0['noise_ref'] == f0['noise_ref']
    else:
        alias_exact = None
    write('BANK_AND_REPEAT_QUALIFICATION.json', dict(bank_ref=ref(run / 'normal/BANK.json') if bank else None,
        declared_source_context={k: bank[k] for k in ('parent_source_id', 'source_id', 'cut', 'run_id', 'source_signature', 'synthetic')} if bank else None,
        candidate_checks=bank_checks, a0_fresh0_shared_plan_and_noise_exact=alias_exact,
        outcomes_not_aliased=True, paired_labels=labels,
        qualification_rule='Single outcome, full-state cut comparison and both repeats are separate. No labels synthesized for missing branches.',
        no_model_recompute_no_resampling=True))
    label_checks = []
    definitions = {'gain_local_plus': ('Q_C10', ['local_plus', 'a0']),
        'gain_local_minus': ('Q_C10', ['local_minus', 'a0']),
        'pair': ('Q_C10', ['local_plus', 'local_minus']),
        'G0': ('G0_C5', ['old', 'fresh0', 'fresh1', 'fresh2'])}
    for key, (namespace, arms) in definitions.items():
        records = [x for x in labels['records'] if x['target'] == namespace and x['arm'] in arms]
        matrix = {(x['arm'], x['repeat']): x for x in records}
        duplicates = len(matrix) != len(records)
        common = ('parent', 'cut', 'target', 'source_signature', 'context_signature')
        cross_valid = bool(records) and all(len({json.dumps(x.get(k), sort_keys=True) for x in records}) == 1
            and all(x.get(k) is not None for x in records) for k in common)
        cross_valid = cross_valid and all(x['target'] == namespace and x['cut'] == 5 for x in records)
        raw_stable = all(len({x.get('raw_group') for x in records if x['arm'] == arm}) == 1
            and all(x.get('raw_group') for x in records if x['arm'] == arm) for arm in arms)
        valid = []
        for repeat in (0, 1):
            members = [matrix.get((arm, repeat)) for arm in arms]
            if all(x is not None and x['outcome_complete'] and x['success'] in (0, 1)
                   and x['restore_level'] == 'full_state_verified' for x in members):
                same_stream = len({x['suffix_stream'] for x in members}) == 1 and members[0]['suffix_stream'] is not None
                if cross_valid and raw_stable and same_stream:
                    valid.append(repeat)
        alias = key != 'G0' and all(matrix.get((arms[0], repeat), {}).get('raw_group') is not None
            and matrix.get((arms[0], repeat), {}).get('raw_group') == matrix.get((arms[1], repeat), {}).get('raw_group')
            for repeat in (0, 1))
        distinct = all(matrix.get((arm, 0), {}).get('suffix_stream') != matrix.get((arm, 1), {}).get('suffix_stream') for arm in arms)
        eligible = valid == [0, 1] and not alias and distinct and not duplicates
        means = {arm: sum(matrix[(arm, rep)]['success'] for rep in (0, 1)) / 2 for arm in arms} if eligible else None
        expected = (sum(means[a] for a in arms[1:]) / 3 - means['old']) if eligible and key == 'G0' else means[arms[0]] - means[arms[1]] if eligible else None
        saved = labels['labels'][key]
        matches = saved == dict(valid_pair_repeat_ids=valid, target_mask=eligible, target=expected, raw_alias_masked=alias)
        label_checks.append(dict(label=key, members=len(records), duplicate_members=duplicates,
            valid_pair_repeat_ids=valid, suffix_repeat_streams_distinct=distinct, raw_alias_masked=alias,
            target_mask=eligible, arm_success_means=means, computed_target=expected, saved=saved, matches=matches))
    write('INDEPENDENT_LABEL_ARITHMETIC.json', dict(checks=label_checks,
        status='PASS' if all(x['matches'] for x in label_checks) else 'FAILED',
        source=ref(run / 'reserved/PAIRED_LABELS.json'),
        no_model_recompute=True, no_missing_outcome_filled_as_zero=True,
        scientific_limit='Single planned parent labels only, not success-rate estimates or method ranking.'))
    with (OUT / 'LAUNCH_RESULT.json').open('xb') as f:
        f.write((run / 'launcher/LAUNCH_RESULT.json').read_bytes())
    summary = dict(task_id=TASK, launcher_status=launch['status'], returncode=outer['returncode'],
        command_invocations=1, claim_count=1, elapsed_seconds=outer['elapsed_seconds'],
        planned_attempts=15, started_attempts=sum(x['started'] for x in rows),
        complete_outcomes=sum(x['outcome_complete'] for x in rows),
        s300_outcomes=sum(x['absolute_s300_reached'] for x in rows),
        full_state_verified_branches=sum(x['full_state_verified'] for x in rows),
        private_ledger_scope_count=len(scopes), entered_event_count=sum(x['events_entered'] for x in scopes),
        returned_event_count=sum(x['events_returned'] for x in scopes), failed_event_count=sum(x['events_failed'] for x in scopes),
        incomplete_event_count=sum(x['events_incomplete'] for x in scopes),
        counts_complete=complete_counts, within_all_116_caps=not cap_violations,
        actual_nonzero_operation_units={k: v for k, v in totals['entered'].items() if v},
        primary_and_cleanup_failures=failures, holder_count_restored=holders,
        runtime_files=len(files), unique_runtime_reference_files=len(reference_checks), runtime_reference_errors=reference_errors,
        full_state_raw_comparisons_equal=all(x['raw_captured_fields_equal'] and x['MJB_matches_normal'] for x in state_checks),
        actual_reward_outcomes_not_a_success_rate_or_ranking=True, release_consumed=True, unused_caps_reusable=False)
    write('AUDIT_SUMMARY.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
