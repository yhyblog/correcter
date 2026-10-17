"""Audit only saved Batch3 outputs after the outer frozen command has exited."""
from pathlib import Path
import datetime,json,sys,re
from audit_saved_helpers import load,digest,ref,save,add,fields_comparison,independent_label
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=B/'work/A/A11_COMMON_POOL_BATCH3_V1';P=B/'results/A/A11_COMMON_POOL_BATCH3_V1'
PREP=B/'results/A/A11_BATCH3_PREP_CPU_V1'
release=load(W/'authorization/P11_A_COMMON_POOL_BATCH3_V1.json');run=Path(release['paths']['output'])
outer=load(B/'results/A/A11_COMMON_POOL_BATCH3_V1/OUTER_EXIT.json')
if outer is None:raise SystemExit('Outer command still active: post-exit audit not authorized to infer completion')
caps=release['resource_caps'];proposal=load(PREP/'proposal/PROPOSAL.json')
ARM=[('normal',None,None)]+[(f'Q_{a}_r{r}',a,r) for a in ('a0','local_plus','local_minus') for r in (0,1)]+[(f'G0_{a}_r{r}',a,r) for a in ('old','fresh0','fresh1','fresh2') for r in (0,1)]
from audit_saved_helpers import audit_journal
errors=[];missing=[];scopes=[];total_entered=dict.fromkeys(caps,0);total_returned=dict.fromkeys(caps,0)
total_failed=dict.fromkeys(caps,0);total_incomplete=dict.fromkeys(caps,0)
coverage=[];states=[];labels=[];devices=[];timings=[];private_indices=[];failures=[]
def mismatch(kind,detail):errors.append(dict(kind=kind,detail=detail))
def canonical_pci(value):
    if type(value) is not str or not re.fullmatch(r'[0-9A-Fa-f]{4,8}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-7]',value):return None
    domain,bus,device=value.lower().split(':')
    return f'{int(domain,16):04x}:{bus}:{device}'
def register(scope):
    scopes.append(scope);add(total_entered,scope['entered']);add(total_returned,scope['returned'])
    add(total_failed,scope['failed_units']);add(total_incomplete,scope['incomplete_entered_units'])
    if scope.get('present') and (scope.get('corrupt') or not scope.get('within_caps')):mismatch('journal',scope['path'])
    return scope
def optional_copy(source,name):
    source=Path(source)
    if source.exists():
        target=P/name
        with target.open('xb') as f:f.write(source.read_bytes())
        return ref(source)
    return None
launch=load(run/'launcher/LAUNCH_RESULT.json');wave=load(run/'reserved/WAVE_EXIT.json')
group=load(run/'reserved/PROCESS_GROUP_EXIT.json')
exit_proven=group is not None and group.get('status')=='all_formal_group_members_exited'
if wave is not None and not exit_proven:mismatch('formal_group_exit_evidence_missing',None)
launcher_scope=register(audit_journal(run/'launcher/events.jsonl','numeric',{'native_nvml_identity_queries':8}))
if launch and launch['launcher_ledger']['entered']!=launcher_scope['entered']:mismatch('launcher_entered_disagreement',None)
branch_limits=load(PREP/'proposal/RESOURCE_BUDGET.json')
bound={p['parent_key']:p for p in branch_limits['parents']}
for parent in release['parents']:
    key=parent['parent_key'];root=Path(parent['paths']['output']);source=parent['source'];cut=source['cut']
    parent_cfg=load(parent['config']['path'])
    normal_ref=load(root/'normal/CUT_REFERENCE.json');normal_state=(normal_ref or {}).get('state')
    rows=[];parent_entered=dict.fromkeys(caps,0);parent_returned=dict.fromkeys(caps,0);parent_scopes=[]
    for name,family,repeat in ARM:
        out=root/name;start=load(root/'reserved'/(name+'_START.json'));exit_row=load(root/'reserved'/(name+'_EXIT.json'))
        result=load(out/'BRANCH_RESULT.json');ledger=load(out/'RESOURCE_LEDGER.json');sidecar=load(out/'SIDECAR_V1.json')
        entered=start is not None or exit_row is not None or out.exists()
        if not entered and not out.exists():
            rows.append(dict(role=name,started=False,result_present=False,outcome_complete=False,success=None,reason='not_started_no_label'))
            continue
        # Static pure-Python cap arithmetic; actual ledgers never define caps.
        sys.path.insert(0,str(PREP/'code'));import inheritance
        from budget import numeric_caps as static_numeric
        from task_profiles import initialization_caps
        numeric_caps=static_numeric(name,cut);init_caps=initialization_caps(source['task'],cut)
        if ledger and ledger['initialization']['caps']!=init_caps:
            mismatch('runtime_initialization_caps_drift',dict(parent=key,branch=name))
        from native.graphics_contract import CAPS as graphics_caps
        ns=register(audit_journal(out/'numeric_events.jsonl','numeric',numeric_caps))
        ins=register(audit_journal(out/'initialization_events.jsonl','initialization',init_caps))
        gs=register(audit_journal(out/'graphics_events.jsonl','graphics',graphics_caps))
        branch_entered=dict.fromkeys(caps,0);branch_returned=dict.fromkeys(caps,0)
        for s in (ns,ins,gs):add(branch_entered,s['entered']);add(branch_returned,s['returned']);parent_scopes.append(s['path'])
        add(parent_entered,branch_entered);add(parent_returned,branch_returned)
        if any(branch_entered[k]>bound[key]['attempt_caps'][name][k] for k in caps):mismatch('branch_caps',dict(parent=key,branch=name))
        if ledger:
            if ledger['total_entered']!=branch_entered:mismatch('branch_ledger_total',dict(parent=key,branch=name))
            if ledger['numeric']['entered']!=ns['entered'] or ledger['numeric']['returned']!=ns['returned']:mismatch('numeric_ledger',dict(parent=key,branch=name))
            if ledger['initialization']['entered_budget_usage']!=ins['entered'] or ledger['initialization']['returned_operation_units']!=ins['returned']:mismatch('initialization_ledger',dict(parent=key,branch=name))
            if ledger['graphics']['entered_budget_usage']!=gs['entered']:mismatch('graphics_ledger',dict(parent=key,branch=name))
            if ledger.get('primary') or ledger.get('cleanup'):failures.append(dict(parent=key,branch=name,primary=ledger.get('primary'),cleanup=ledger.get('cleanup'),ledger_ref=ref(out/'RESOURCE_LEDGER.json')))
        else:missing.append(dict(parent=key,branch=name,item='RESOURCE_LEDGER',reason='absent; no complete metering claim'))
        ev=load(out/'FAILURE.json')
        if ev and not ledger:failures.append(dict(parent=key,branch=name,primary=ev,cleanup=None))
        branch_events=[json.loads(line) for line in (out/'events.jsonl').read_text().splitlines()] if (out/'events.jsonl').exists() else []
        commitment=next((e for e in branch_events if e['event']=='commitment_finished'),None)
        resumed=[e for e in branch_events if e['event']=='H10_plan_installed' and e.get('absolute_step')==cut+(10 if name.startswith('Q_') else 5)] if name!='normal' else []
        observed=load(out/'CUT_STATE.json');verification=load(out/'STATE_VERIFICATION.json')
        compared=fields_comparison(normal_state,observed) if name!='normal' else dict(available=observed is not None,scope='reference_capture',physical_equality_proven=None)
        if verification and verification['level']=='full_state_verified' and compared.get('exact_equal') is not True:mismatch('false_full_state_verified',dict(parent=key,branch=name))
        states.append(dict(parent=key,branch=name,comparison=compared,reported_verification=verification,
            MJB_byte_equal_to_normal=(digest(out/'cut_model.mjb')==digest(root/'normal/cut_model.mjb')) if (out/'cut_model.mjb').exists() and (root/'normal/cut_model.mjb').exists() else None))
        outcome=(result or {}).get('outcome') or {};complete=outcome.get('outcome_complete') is True
        controls=(result or {}).get('controls');success=outcome.get('success') if complete else None
        row=dict(role=name,family=family,repeat=repeat,started=entered,branch_directory_present=out.exists(),
            START_record_present=start is not None,EXIT_record_present=exit_row is not None,
            result_present=result is not None,resource_ledger_present=ledger is not None,
            raw_exit_code=(exit_row or {}).get('returncode'),failure_scope=(exit_row or {}).get('failure_scope'),
            controls=controls,actual_returned_controls=branch_returned['env_steps'],observations=branch_returned['observation_calls'],
            legal_cut_reached=(result or {}).get('legal_cut_reached'),outcome_complete=complete,success=success,
            reason=outcome.get('reason') or 'missing_result_technical_or_interrupted',
            restore_level=(result or {}).get('restore_level'),full_state_exact_verified=compared.get('exact_equal'),
            returned_commitment_steps=((result or {}).get('intervention_evidence') or {}).get('returned_commitment_steps'),
            discarded_raw_tail=(commitment or {}).get('discarded_raw_tail'),H10_resumed=bool(resumed),
            intervention_evidence=(result or {}).get('intervention_evidence'),sidecar_present=sidecar is not None,
            entered_units=branch_entered,returned_units=branch_returned,
            complete_metering=ledger is not None and all(s['present'] and not s['corrupt'] and not s['incomplete_ids'] for s in (ns,ins,gs)),
            ledger_status=(ledger or {}).get('status'),physical_equality_proven=None)
        rows.append(row)
        timing=dict(parent=key,branch=name,task=source['task'],cut=cut,GPU_UUID=parent['device']['gpu_uuid'],
            child_elapsed_seconds=(exit_row or {}).get('elapsed_seconds'),ledger_elapsed_seconds=(ledger or {}).get('elapsed_seconds'),
            first_numeric_monotonic=ns.get('first_monotonic'),last_numeric_monotonic=ns.get('last_monotonic'),
            selected_numeric_intervals={k:v for k,v in ns['timing'].items() if k in ('load_PI05_SFT030000','policy_safetensors_load','policy_load_state_dict','native_raw50','real_control','format_real_next_observation','full_state_capture','full_state_compare')},
            start_record=ref(root/'reserved'/(name+'_START.json')) if start else None,
            start_record_write_time_ns=(root/'reserved'/(name+'_START.json')).stat().st_mtime_ns if start else None,
            start_time_semantics='file mtime is evidence-save time only; precise Popen timestamp was not serialized',
            exit_record=ref(root/'reserved'/(name+'_EXIT.json')) if exit_row else None)
        timings.append(timing)
        nvml=load(out/'NVML_IDENTITY.json');policy=load(out/'policy_device.json');loader=load(out/'policy_loader.json')
        mapping=load(out/'device_mapping.json');library=load(out/'loader_identity.json')
        expected_device=parent['device']
        matching_nvml=[r for r in (nvml or {}).get('rows',[]) if len(r)==5 and r[1]==expected_device['gpu_uuid']]
        nvml_good=(len(matching_nvml)==1 and matching_nvml[0][0]==str(expected_device['gpu_index']) and
            matching_nvml[0][2]==expected_device['gpu_model'] and matching_nvml[0][3]==expected_device['driver'] and
            canonical_pci(matching_nvml[0][4])==expected_device['pci_bus_id'])
        uuid_good=policy is not None and policy.get('normalized_uuid')==expected_device['gpu_uuid'] and policy.get('format_valid') is True
        selected=[d for d in (mapping or {}).get('devices',[]) if d.get('decision')=='target']
        mapping_good=(len(selected)==1 and mapping.get('cuda_init_return_code')==0 and
            mapping.get('stage')=='unique_mapping_complete' and selected[0]['egl_index']==mapping.get('selected_egl_index') and
            selected[0]['mapping']=={k:expected_device[k] for k in ('pci_bus_id','gpu_uuid')} and
            selected[0]['attribute']['return_code']==1 and selected[0]['cuda_pci']['return_code']==0 and
            policy is not None and policy.get('EGL_index')==mapping.get('selected_egl_index'))
        expected_library=str(Path(parent_cfg['native']['isolation_root'])/'isolation/lib'/('libcuda.so.'+expected_device['driver']))
        library_good=(library is not None and library.get('CUDA_before')==[] and library.get('environment')==parent_cfg['cuda_environment'] and
            all(library.get(k)==[expected_library] for k in ('CUDA_after_first_load','CUDA_after_EGL_load','after_mapping','after_torch_device_binding')))
        identity_good=(nvml_good and uuid_good and mapping_good and library_good and nvml['target']==expected_device and policy['physical_target']==expected_device and policy.get('accepted') is True and policy.get('target_matches') is True)
        strict_good=(loader is not None and not loader['errors'] and len(loader['file_calls'])==len(loader['state_calls'])==1 and
            loader['file_calls'][0]['path']==parent_cfg['collection_policy']['checkpoint']['path'] and
            loader['file_calls'][0]['returned'] and loader['state_calls'][0]['returned'] and loader['state_calls'][0]['strict'] is True and not loader['state_calls'][0]['missing_keys'] and not loader['state_calls'][0]['unexpected_keys'])
        devices.append(dict(parent=key,branch=name,expected=parent['device'],policy_device=policy,
            saved_NVML_fixed_target_matches=nvml_good,saved_policy_UUID_matches=uuid_good,
            saved_EGL_CUDA_mapping_matches=mapping_good,saved_library_and_visibility_matches=library_good,
            identity_complete=identity_good,strict_loader_complete=strict_good,loader=loader))
        if ledger and ledger['status']=='complete' and (not identity_good or not strict_good):mismatch('complete_branch_missing_identity_or_strict_load',dict(parent=key,branch=name))
    published=load(root/'reserved/PAIRED_LABELS.json');independent={};label_rows=[]
    for name,_,repeat in ARM[1:]:
        sc=load(root/name/'SIDECAR_V1.json')
        if not sc:continue
        label_rows.append(dict(arm=sc['plans']['candidate_family'],repeat=repeat,parent=sc['identity']['parent_id'],cut=sc['protocol']['cut_step'],
            target=sc['protocol']['target_namespace'],source_signature=sc['identity']['source_signature'],
            context_signature=(sc['restoration']['reference_state_ref'] or {}).get('sha256'),suffix_stream=sc['plans']['suffix_stream_id'],
            outcome_complete=sc['outcome']['outcome_complete'],success=sc['outcome']['success'],restore_level=sc['restoration']['level'],raw_group=sc['plans']['raw_alias_group']))
    for label,arms,kind in [('gain_local_plus',['local_plus','a0'],'gain'),('gain_local_minus',['local_minus','a0'],'gain'),('pair',['local_plus','local_minus'],'pair'),('G0',['old','fresh0','fresh1','fresh2'],'G0')]:
        independent[label]=independent_label(label_rows,arms,kind)
    agrees=published is not None and published['labels']==independent
    if published and not agrees:mismatch('independent_label_disagreement',key)
    repeat_groups=[]
    for namespace,family in [('Q_C10',a) for a in ('a0','local_plus','local_minus')]+[('G0_C5',a) for a in ('old','fresh0','fresh1','fresh2')]:
        pair=[r for r in label_rows if r['target']==namespace and r['arm']==family]
        repeat_groups.append(dict(namespace=namespace,arm=family,repeats=[r['repeat'] for r in pair],
            both_complete=len(pair)==2 and {r['repeat'] for r in pair}=={0,1} and all(r['outcome_complete'] and r['restore_level']=='full_state_verified' for r in pair)))
    labels.append(dict(parent=key,source_id=source['source_id'],cut=cut,publication_present=published is not None,independent_labels=independent,
        agrees_with_saved_labels=agrees,repeat_groups=repeat_groups,accepted_new_parent=False,pending_analysis=True))
    review_candidate=(exit_proven and len([r for r in rows if r['started']])==15 and all(r.get('outcome_complete') and r.get('complete_metering') and r.get('raw_exit_code')==0 for r in rows)
        and rows[0].get('legal_cut_reached') is True and all(r.get('full_state_exact_verified') for r in rows[1:]) and agrees and all(v['target_mask'] for v in independent.values()))
    before_cut=rows[0].get('outcome_complete') is True and rows[0].get('legal_cut_reached') is False
    coverage_note=('normal_complete_before_legal_cut; no paired sample; no replacement' if before_cut else
        'all15_started; inspect every outcome/state/target mask' if sum(r['started'] for r in rows)==15 else
        'partial_or_unstarted; inspect branch/wave evidence')
    coverage.append(dict(parent_key=key,source=source,device=parent['device'],branches=rows,branches_started=sum(r['started'] for r in rows),
        coverage_note=coverage_note,normal_complete_before_legal_cut=before_cut,
        complete_outcomes=sum(r['outcome_complete'] for r in rows),absolute_s300_outcomes=sum(r.get('controls')==300 and r['outcome_complete'] for r in rows),
        full_state_exact_comparisons=sum(r.get('full_state_exact_verified') is True for r in rows),
        complete_repeat_groups=sum(x['both_complete'] for x in repeat_groups),candidate_qualified_for_analysis=review_candidate,
        accepted_new_parent=False,child_entered_units=parent_entered,child_returned_units=parent_returned,private_scopes=parent_scopes))
    if (root/'reserved/PRIVATE_COST_INDEX.json').exists():private_indices.append(ref(root/'reserved/PRIVATE_COST_INDEX.json'))

events=[json.loads(l) for l in (run/'reserved/SCHEDULER_EVENTS.jsonl').read_text().splitlines()] if (run/'reserved/SCHEDULER_EVENTS.jsonl').exists() else []
active_parents=set();max_parents=0;started_order={p['parent_key']:[] for p in release['parents']};group_event=None;published_after_exit=True
for event in events:
    kind=event['event'];key=event.get('parent_key')
    if event.get('synthetic') is not False:mismatch('runtime_synthetic_flag',event['event_id'])
    if kind=='parent_admitted':active_parents.add(key);max_parents=max(max_parents,len(active_parents))
    if kind=='branch_started':
        started_order[key].append(event['attempt_role'])
        expected=next(p for p in release['parents'] if p['parent_key']==key)
        if event['gpu_uuid']!=expected['device']['gpu_uuid']:mismatch('scheduler_UUID',key)
    if kind=='branch_compute_exited':
        role=event['attempt_role'];ex=load(run/key/'reserved'/(role+'_EXIT.json')) or {};br=ex.get('result') or {}
        continues=ex.get('returncode')==0 and ex.get('cleanup_complete') is True and not ex.get('remaining_group') and br.get('status')=='complete' and br.get('legal_cut_reached') and (role=='normal' or br.get('restore_level')=='full_state_verified')
        if not continues or role==ARM[-1][0]:active_parents.discard(key)
    if kind=='whole_wave_compute_exit':group_event=event['event_id'];active_parents.clear()
    if kind=='parent_data_published' and group_event is None:published_after_exit=False
if max_parents>2:mismatch('concurrency_cap',max_parents)
for key,order in started_order.items():
    if order!=[n for n,_,_ in ARM[:len(order)]]:mismatch('cold_branch_order',dict(parent=key,actual=order))
scheduler_result=(wave or {}).get('result') or {}
parent_timing=[dict(parent_key=x['parent_key'],elapsed_seconds=x['elapsed_seconds'],status=x['status'],
    branches_started=x['branches_started'],clock_scope='scheduler admission to final branch exit; excludes final whole-wave publication')
    for x in scheduler_result.get('parents',[])]
interval_events=[]
for x in timings:
    if x['first_numeric_monotonic'] is not None and x['last_numeric_monotonic'] is not None:
        interval_events.extend([(x['first_numeric_monotonic'],1),(x['last_numeric_monotonic'],-1)])
interval_events.sort();active_windows=0;max_windows=0;last_point=None;covered_seconds=0.;concurrent_seconds=0.
for point,delta in interval_events:
    if last_point is not None:
        dt=point-last_point
        if active_windows>0:covered_seconds+=dt
        if active_windows>1:concurrent_seconds+=dt
    active_windows+=delta;max_windows=max(max_windows,active_windows);last_point=point
aux=dict(recorded_parent_admissions=sum(e['event']=='parent_admitted' for e in events),
    recorded_branch_starts=sum(e['event']=='branch_started' for e in events),maximum_active_parent_slots=max_parents,
    publications=sum(e['event']=='parent_data_published' for e in events),published_after_group_exit=published_after_exit,
    reported_polls=scheduler_result.get('polls'),reported_ownership_scans=(scheduler_result.get('cleanup') or {}).get('ownership_scans_before_drain'),
    precise_publication_group_scan_calls=None,precise_publication_scan_missing_reason='not explicitly serialized; one check per actual runtime publish call is static code accounting only',
    reservation_requests=1 if (run/'launcher/LIFECYCLE_REQUESTED.json').exists() else 0,
    restoration_observer_invocations=1 if (launch or {}).get('lifecycle') is not None else 0,
    scheduler_caps=release['scheduler_caps'],branch_order=started_order,
    cleanup_process_scan_count=None,cleanup_count_reason='mandatory drain retains reservation; exact final scan count not serialized')
aux['actual_started_GPU_UUIDs']=sorted({e['gpu_uuid'] for e in events if e['event']=='branch_started'})
aux['frozen_assignments']=len(release['parents'])
aux_observed=dict(parent_admissions=aux['recorded_parent_admissions'],branch_process_starts=aux['recorded_branch_starts'],
    maximum_active_parents=max_parents,maximum_physical_GPU_assignments=len(aux['actual_started_GPU_UUIDs']),
    parent_publications=aux['publications'],reservation_requests=aux['reservation_requests'],
    restoration_observations=aux['restoration_observer_invocations'],poll_iterations=aux['reported_polls'],
    ownership_scans=aux['reported_ownership_scans'],publication_group_scans=None)
aux['observed_or_unknown']=aux_observed
aux['cap_checks']={k:None if v is None else v<=release['scheduler_caps'][k] for k,v in aux_observed.items()}
for k,v in aux['cap_checks'].items():
    if v is False:mismatch('scheduler_aux_cap',dict(resource=k,actual=aux_observed[k]))
if scheduler_result and aux['recorded_branch_starts']!=scheduler_result['branch_starts']:mismatch('scheduler_start_count',None)
save(P/'INDEPENDENT_LEDGER_AUDIT.json',dict(private_scopes=scopes,scope_count=len(scopes),
    entered=total_entered,returned=total_returned,failed_units=total_failed,incomplete_entered_units=total_incomplete,
    entered_equals_returned_plus_failed_plus_incomplete=all(total_entered[k]==total_returned[k]+total_failed[k]+total_incomplete[k] for k in caps),
    caps=caps,within_all116_caps=all(total_entered[k]<=caps[k] for k in caps),
    event_pairs=dict(entered=sum(s['entries'] for s in scopes),terminal=sum(s['terminals'] for s in scopes),
        failed=sum(s['failed'] for s in scopes),incomplete=sum(len(s['incomplete_ids']) for s in scopes)),
    missing_or_corrupt_scopes=[s['path'] for s in scopes if not s['present'] or s['corrupt']],
    private_event_IDs_never_concatenated_into_public_UUID_ledger=True,missing_evidence_is_not_zero=True))
save(P/'INITIALIZATION_STAGE_AUDIT.json',dict(
    scopes=[dict(path=s['path'],present=s['present'],stage_source_units=s['initialization_by_stage_source']) for s in scopes if s['kind']=='initialization'],
    direct_mj_step_accounting='only explicit direct entries count separately; do_simulation already charges nested n_frames',
    actual_direct_step_entered=sum(v['entered'].get('initialization_physics_substeps',0) for s in scopes for k,v in s['initialization_by_stage_source'].items() if k.endswith(':mujoco.mj_step.direct')),
    actual_direct_step_returned=sum(v['returned'].get('initialization_physics_substeps',0) for s in scopes for k,v in s['initialization_by_stage_source'].items() if k.endswith(':mujoco.mj_step.direct')),
    recomputed_from_saved_private_events_only=True,new_simulation_or_probes=0))
save(P/'PARENT_AND_BRANCH_COVERAGE.json',dict(parents=coverage,existing_accepted_parents=16,new_accepted_parents=0,
    qualification_scope='candidate evidence for analysis only; retain every success/failure/unstarted branch',physical_equality_proven=None))
save(P/'STATE_CLOSURE_AUDIT.json',dict(comparisons=states,physical_equality_proven=None))
save(P/'INDEPENDENT_PAIRED_LABELS.json',dict(parents=labels,publication_or_training_performed=False))
save(P/'DEVICE_AND_LOADER_AUDIT.json',dict(attempts=devices,live_queries=0))
save(P/'SCHEDULER_AUX_AUDIT.json',aux)
save(P/'SAVED_TIMING_AUDIT.json',dict(outer_elapsed_seconds=outer['elapsed_seconds'],attempts=timings,
    parents=parent_timing,sum_known_child_elapsed_seconds=sum(x['child_elapsed_seconds'] or 0 for x in timings),
    missing_child_elapsed_count=sum(x['child_elapsed_seconds'] is None for x in timings),
    numeric_host_windows=dict(maximum_simultaneous=max_windows,union_seconds=covered_seconds,at_least_two_seconds=concurrent_seconds,
        scope='first-to-last numeric event host windows; excludes pre-ledger hash/startup and unmetered cleanup tails; not GPU activity'),
    actual_started_cold_loads=total_entered['policy_model_loads'],parent_concurrency_by_saved_event_order=max_parents,
    numeric_intervals_are_host_monotonic_not_GPU_seconds=True,missing_Popen_timestamps_not_fabricated=True,
    successful_handoff_raw_poll_count=(launch or {}).get('successful_handoff_raw_poll_count'),
    logical_input_read_bytes_actual=None,logical_quote_known_sizes_only=True,strict_total_read_upper_bytes=None,
    full_data_CPU_runtime_audit_does_not_reload_checkpoint=True))
save(P/'FAILURE_AND_MISSING_EVIDENCE.json',dict(failures=failures,missing=missing,
    wave_primary=(wave or {}).get('primary'),scheduler_primary=scheduler_result.get('primary'),
    publication_failures=scheduler_result.get('publication_failures'),launcher_primary=(launch or {}).get('primary'),
    outer_error=outer.get('invocation_error'),historical_failures_not_rewritten=True))
restoration=((launch or {}).get('lifecycle') or {}).get('restoration')
save(P/'EXIT_AND_RESTORATION.json',dict(outer=outer,group_exit=group,group_exit_proven=exit_proven,
    wave_result=wave,lifecycle=(launch or {}).get('lifecycle'),restoration=restoration,
    eight_holders_recorded=sum(x.get('state')=='holder' for x in ((restoration or {}).get('guard_status') or {}).get('gpus',{}).values()),
    saved_evidence_only=True,new_holder_or_process_queries=0,unrelated_processes_not_terminated=True))
optional_copy(run/'launcher/LAUNCH_RESULT.json','LAUNCH_RESULT.json')
optional_copy(run/'reserved/WAVE_EXIT.json','WAVE_EXIT.json')
save(P/'AUDIT_INTERMEDIATE.json',dict(errors=errors,missing=missing,total_entered=total_entered,total_returned=total_returned,
    parent_count=8,parents_started=sum(p['branches_started']>0 for p in coverage),
    actual_children=sum(p['branches_started'] for p in coverage),complete_outcomes=sum(p['complete_outcomes'] for p in coverage),
    all15_and14states_and4paired_targets=sum(p['candidate_qualified_for_analysis'] for p in coverage),
    raw_exit_code=outer['returncode'],group_exit_proven=exit_proven,physical_equality_proven=None))
print(json.dumps(dict(status='SAVED_METADATA_AUDITED',errors=errors,children=sum(p['branches_started'] for p in coverage),
    complete_outcomes=sum(p['complete_outcomes'] for p in coverage),resource_scopes=len(scopes))))
