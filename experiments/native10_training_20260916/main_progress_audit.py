"""Read-only partial main13 audit, isolated from frozen collection dependencies.

Below a fixed manifest-prefix threshold (minimum50), only operational progress
is returned. Scientific summaries require EVERY registered prefix slot sealed;
finishing quickly never determines cohort membership. Known no-cut outcomes stay
in the denominator, technical missing labels never become failures. No models,
simulators, training or stage-wide future outcome readers are invoked.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from . import artifact_loader as loader, storage
from .candidates13 import CANDIDATE_ORDER
from .dataset import CONTROL, STATE_KEYS, PAIR_INDICES, pack_group
from .protocol import canonical_hash, require_stage_budget, validate_manifest


def _read(path):
    return json.loads(Path(path).read_text())


def _stats(values):
    values = np.asarray(values, np.float64)
    return (dict(n=len(values), mean=float(values.mean()), median=float(np.median(values)),
                 p95=float(np.percentile(values, 95)), maximum=float(values.max())) if len(values) else dict(n=0))


def _bytes(paths):
    files = {str(file.resolve()):file.stat().st_size for path in paths if path.exists()
             for file in path.rglob('*') if file.is_file()}
    return dict(files=len(files), logical_file_bytes=sum(files.values()),
                note='Logical byte sizes, not allocated filesystem blocks; no unrelated bank tree is scanned.')


def progress(config, bank_version):
    registration = config['main_collection']['banks'][bank_version]
    stage = registration['stage']
    if registration['kind'] != 'labels13' or stage == 'p0':
        raise ValueError('Only an explicitly registered main labels13 bank may be read')
    require_stage_budget(config, stage)  # Before any source/outcome/ledger access.
    registry = validate_manifest(config['episode_manifest'])
    registered_ids = registration['episode_ids']
    if (not registered_ids or len(registered_ids) != len(set(registered_ids))
            or any(key not in registry or registry[key]['split'] not in ('train','development')
                   or registry[key].get('replacement_of') for key in registered_ids)):
        raise ValueError('Label bank must register only train/development primary slots')
    primary_ids = [key for key in registered_ids if registry[key]['split']=='train']
    if not primary_ids:raise ValueError('No registered training slots in this bank')
    protocol = registration.get('bank_protocol_sha256', config['analysis_approval']['protocol_sha256'])
    artifacts, resolved, unfinished = {}, {}, []
    for primary in primary_ids:
        directory = storage.ROOT/'slot_resolution'/primary
        if not (directory/'complete.json').exists():
            unfinished.append(primary);continue
        allowed = [protocol]+registration.get('allowed_source_protocol_sha256', [])
        loader._sealed(directory, allowed, 'source', artifacts)
        resolution = _read(directory/'resolution.json')
        actual = resolution.get('resolved_episode_id')
        permitted = [primary]+config['main_collection'].get('replacement_candidates', {}).get(primary, [])
        if (resolution.get('status') != 'resolved' or resolution.get('planned_slot_id') != primary
                or actual not in permitted or actual not in registry
                or resolution.get('substitution_after_outcome_forbidden') is not True):
            raise ValueError('Invalid sealed primary-slot resolution')
        collection = storage.ROOT/'collections'/stage/bank_version/registry[actual]['case_id']
        if not (collection/'complete.json').exists():
            unfinished.append(primary);continue
        # Do not deserialize collection summary/branch successes below threshold.
        loader._sealed(collection, [protocol], 'source', artifacts)
        resolved[primary] = dict(actual=actual, collection=str(collection), resolution=resolution)
    raw_ledger, ledger = loader._ledger_snapshot()
    raw_scenes, scenes = loader._scene_registry_snapshot()
    stage_attempts = [row for row in ledger.values() if row['stage'] == stage and row['resource'] == 'simulator_attempts']
    all_sources = [key for primary in primary_ids for key in [primary]+config['main_collection'].get('replacement_candidates', {}).get(primary, [])]
    all_source_set=set(all_sources)
    source_paths = [storage.ROOT/'sources'/registry[key]['case_id'] for key in all_sources]
    bank_paths = [storage.ROOT/'banks'/bank_version/registry[key]['case_id'] for key in all_sources]
    rollout_paths = [storage.ROOT/'rollouts'/stage/bank_version/registry[key]['case_id'] for key in all_sources]
    collection_paths = [storage.ROOT/'collections'/stage/bank_version/registry[key]['case_id'] for key in all_sources]
    accepted = [row for key,row in scenes.items() if key in all_source_set and row['status'] == 'accepted']
    scene_keys = [(row['task'],row['scene_fingerprint']) for row in accepted]
    elapsed = max(0., time.time()-min(row['unix'] for row in stage_attempts)) if stage_attempts else None
    operational = dict(planned_primary_slots=len(primary_ids), sealed_completed_slots=len(resolved),
        completed_primary_ids=[key for key in primary_ids if key in resolved], unfinished_primary_ids=unfinished,
        source_seals=sum((path/'complete.json').exists() for path in source_paths),
        source_rejection_seals=sum((path/'complete.json').exists() and (path/'rejection.json').exists() for path in source_paths),
        bank_seals=sum(len(list(path.glob('cut*/complete.json'))) for path in bank_paths if path.exists()),
        branch_seals=sum(len(list(path.glob('cut*/*/repeat_*/complete.json'))) for path in rollout_paths if path.exists()),
        accepted_scenes=len(scene_keys), unique_task_scene_fingerprints=len(set(scene_keys)),
        duplicate_accepted_scene_count=len(scene_keys)-len(set(scene_keys)),
        attempts_by_stage=dict(Counter(row['stage'] for row in ledger.values() if row['resource']=='simulator_attempts')),
        stage_attempts=len(stage_attempts), stage_attempt_kinds=dict(Counter(row['kind'] for row in stage_attempts)),
        stage_attempt_scope='Entire registered stage can include development; source/bank/branch progress counts above use training identities only.',
        global_simulator_attempts=sum(row['amount'] for row in ledger.values() if row['resource']=='simulator_attempts'),
        optimizer_updates=sum(row['amount'] for row in ledger.values() if row['resource']=='training_updates'),
        stage_elapsed_since_first_attempt_seconds=elapsed,
        cumulative_completed_slots_per_hour=len(resolved)/elapsed*3600 if elapsed else None,
        throughput_scope='Cumulative operational throughput since first stage attempt; includes active/incomplete work, excludes earlier loading, not steady-state capacity.',
        disk=_bytes([*source_paths, *bank_paths, *rollout_paths, *collection_paths]),
        ledger_snapshot_sha256=hashlib.sha256(raw_ledger).hexdigest(),
        scene_registry_snapshot_sha256=hashlib.sha256(raw_scenes).hexdigest())
    return dict(registration=registration, registry=registry, primary_ids=primary_ids, resolved=resolved,
                artifacts=artifacts, ledger=ledger, scenes=scenes, operational=operational)


def audit_one(primary_id, config, bank_version, snapshot):
    """Full source/scene/raw-command/paired-trajectory audit of one sealed slot."""
    registration = snapshot['registration'];stage = registration['stage']
    protocol = registration.get('bank_protocol_sha256', config['analysis_approval']['protocol_sha256'])
    registry, ledger, artifacts = snapshot['registry'],snapshot['ledger'],snapshot['artifacts']
    primary = registry[primary_id]
    case, source, rejections, attempts = loader._resolve(primary, registration, config, registry,
        ledger, artifacts, snapshot['scenes'])
    resolved = snapshot['resolved'][primary_id]
    if case is None or case['episode_id'] != resolved['actual']:
        raise ValueError('Ordered pre-action rejection chain differs from sealed resolution')
    summary, source_data, contexts, queues, number = loader._source(case, source, registration,
        config, ledger, artifacts, snapshot['scenes'])
    attempts.append(number)
    if (resolved['resolution']['source_seal_sha256'] != storage.sha256(source/'complete.json')
            or resolved['resolution']['scene_fingerprint'] != summary['scene_fingerprint']):
        raise ValueError('Resolution changed its source or scene')
    collection = _read(Path(resolved['collection'])/'summary.json')
    if (collection.get('case') != case or collection.get('cuts') != summary['cuts']
            or collection.get('source_seal_sha256') != storage.sha256(source/'complete.json')
            or collection.get('planned_episode_retained') is not True
            or collection.get('outcome_filter_applied') is not False):
        raise ValueError('Collection/source identity or retention changed')
    group = dict(episode=case, source_summary=summary)
    branches, bank_generation, metadata = [], None, None
    if summary['cuts']:
        cut = summary['cuts'][0]
        bank = storage.ROOT/'banks'/bank_version/case['case_id']/f'cut{cut:03d}'
        loader._sealed(bank,[protocol],'bank',artifacts)
        bank_generation = _read(bank/'generation.json');metadata = _read(bank/'metadata.json')
        plans = loader._npz(bank/'plans.npz')
        identity = dict(source_seal_sha256=storage.sha256(source/'complete.json'), protocol_sha256=protocol,
            candidate_bank_sha256=storage.sha256(bank/'complete.json'), model_hashes=registration['model_hashes'],
            suffix_seed_namespace=config['seed_namespace'])
        if (collection.get('candidate_bank_sha256') != identity['candidate_bank_sha256']
                or bank_generation.get('episode_id') != case['episode_id']
                or bank_generation.get('planned_slot_id') != primary_id
                or bank_generation.get('cut_step') != cut
                or any(bank_generation.get(key) != value for key,value in identity.items() if key != 'candidate_bank_sha256')):
            raise ValueError('Bank source/cut/model provenance changed')
        attempts.append(loader._attempt(bank,bank_generation,ledger,kind='candidate_restore',stage=stage,
            protocol=protocol,identity=str(bank.relative_to(storage.ROOT.resolve()))))
        if collection.get('actual_branch_count') != 56 or len(collection.get('branch_records', [])) != 56:
            raise ValueError('Reached source lacks all13+normal x4 physical branches')
        saved_rows = {(row['method'],row['repeat']):row for row in collection['branch_records']}
        expected = {(method, repeat) for method in (*CANDIDATE_ORDER,CONTROL) for repeat in range(4)}
        if set(saved_rows) != expected:
            raise ValueError('Collection candidate/repeat slots changed')
        noise_by_stream = {}
        for method, repeat in sorted(expected):
            branch = storage.ROOT/'rollouts'/stage/bank_version/case['case_id']/f'cut{cut:03d}'/method/f'repeat_{repeat}'
            loader._sealed(branch,[protocol],'branch',artifacts)
            row = _read(branch/'summary.json');record = saved_rows[(method,repeat)]
            if (row.get('method') != method or row.get('candidate_name') != method or row.get('repeat') != repeat
                    or record.get('seal_sha256') != storage.sha256(branch/'complete.json')
                    or Path(record.get('summary_path','')).resolve() != (branch/'summary.json').resolve()
                    or any(record.get(key) != row.get(key) for key in ('success','budget_attempt','command_sha256'))):
                raise ValueError('Collection physical branch reference changed')
            attempts.append(loader._attempt(branch,row,ledger,kind='branch_including_restore',stage=stage,
                protocol=protocol,identity=str(branch.relative_to(storage.ROOT.resolve()))))
            loader._branch_trajectory(row,branch,source_data,queues[cut],None if method==CONTROL else plans[method])
            for suffix in row['suffix_seeds']:
                key = (repeat,suffix['decision_index']);digest = suffix.get('noise_sha256')
                if not isinstance(digest,str) or len(digest)!=64:
                    raise ValueError('Actual suffix noise hash missing')
                if key in noise_by_stream and noise_by_stream[key] != digest:
                    raise ValueError('Paired suffix same repeat/decision index changed initial noise')
                noise_by_stream[key] = digest
            branches.append(row)
        group.update(observed={key:contexts[cut][key] for key in STATE_KEYS},candidate_plans=plans,
                     candidate_metadata=metadata,branch_summaries=branches,provenance=identity)
    elif (collection.get('actual_branch_count') != 0 or collection.get('branch_records')
            or collection.get('common_outcome_available') is not True
            or collection.get('common_outcome') != summary['success']):
        raise ValueError('No-cut source lacks its shared known complete outcome')
    packed = pack_group(**group)
    if packed['arrays'] is None and not (packed['metadata']['status']=='no_cut'
            and packed['metadata'].get('full_episode_outcome_available')):
        raise ValueError('Technical unknown may not enter complete partial statistics')
    return dict(primary_id=primary_id, case=case, source=summary, packed=packed,
                branch_rows=branches, bank_generation=bank_generation, candidate_metadata=metadata,
                attempts=attempts, rejections=rejections)


def paired(candidate, baseline):
    candidate,baseline=np.asarray(candidate),np.asarray(baseline)
    if candidate.shape!=baseline.shape or candidate.ndim!=2 or candidate.shape[1]!=4 or not len(candidate):
        raise ValueError('Paired labels must be source x4')
    if not np.isin(candidate,[0,1]).all() or not np.isin(baseline,[0,1]).all():
        raise ValueError('Unknown labels cannot be imputed as failure')
    rescue=int(((candidate==1)&(baseline==0)).sum());harm=int(((candidate==0)&(baseline==1)).sum())
    source_gain=candidate.mean(1)-baseline.mean(1)
    return dict(sources=len(candidate),logical_pairs=int(candidate.size),rescues=rescue,harms=harm,
        net_gain=(rescue-harm)/candidate.size,success_rate=float(candidate.mean()),
        baseline_success_rate=float(baseline.mean()),positive_sources=int((source_gain>0).sum()),
        negative_sources=int((source_gain<0).sum()),zero_sources=int((source_gain==0).sum()))


def summarize(groups):
    if not groups:
        raise ValueError('No fully audited groups')
    full, reached, raw_rows, per_source, branch_costs, banks = [],[],[],[],[],[]
    for group in groups:
        data=group['packed']['arrays'];source=group['source'];outcome=np.empty((14,4),np.bool_)
        valid=data is not None;reached.append(valid)
        detail=dict(planned_slot_id=group['primary_id'],episode_id=group['case']['episode_id'],
                    task=group['case']['task'],registered_cut_rule=group['case']['cut_rule'],
                    requested_cut=source['requested_cut'],actual_cut=source['actual_cut'],
                    selection_category=source['selection_category'],selection_reason=source['selection_reason'],
                    no_cut=not valid,scene_fingerprint=source['scene_fingerprint'],replacement=bool(group['rejections']))
        if valid:
            if not np.isin(data['outcomes'],[0,1]).all() or not np.isin(data['control_outcomes'],[0,1]).all():
                raise ValueError('Unknown labels cannot enter descriptive statistics')
            outcome[:13]=data['outcomes'];outcome[13]=data['control_outcomes']
            if not np.asarray(data['control_valid']).all():raise ValueError('Missing normal control')
            raw=np.asarray(data['raw_actions'],np.float64);critic=np.asarray(data['actions'],np.float64)
            mapping=float(np.abs((critic-critic[:1])-(raw-raw[:1])).max())
            mask=np.asarray(group['candidate_metadata']['clearance_mask'],bool)
            if mask.shape!=(10,4) or mapping>1e-6:raise ValueError('Raw/critic command mapping or mask shape changed')
            gain=outcome[:13].mean(1)-outcome[0].mean()
            detail.update(candidate_gain_vs_a0=dict(zip(CANDIDATE_ORDER,gain.tolist())),
                candidate_distinct_raw_groups=int(len(set(data['group_ids'].tolist()))),
                nonbase_aliases_to_a0=int((data['group_ids']==data['group_ids'][0]).sum()-1),
                raw_critic_delta_max_error=mapping,mask_mutable_fraction_per_dimension=mask.mean(0).tolist(),
                xyz_any_mutable=bool(mask[:,:3].any()),gripper_any_mutable=bool(mask[:,3].any()),
                channel_fallbacks={name:bool(value['fallback']) for name,value in group['candidate_metadata']['channels'].items()},
                raw_delta_xyz_rms=np.sqrt(np.mean((raw[:,:,:3]-raw[:1,:,:3])**2,axis=(1,2))).tolist(),
                raw_delta_gripper_rms=np.sqrt(np.mean((raw[:,:,3]-raw[:1,:,3])**2,axis=1)).tolist(),
                informative_mean_labels=bool(np.ptp(outcome[:13].mean(1))>0),
                any_candidate_mean_benefit=bool((gain>0).any()),any_candidate_mean_harm=bool((gain<0).any()),
                any_paired_discordance=bool((outcome[:13]!=outcome[:1]).any()))
            raw_rows.append(detail);banks.append(group['bank_generation']['generation_wall_seconds'])
        else:
            known=group['packed']['metadata']['native10_outcome']
            if not isinstance(known,(bool,np.bool_)):raise ValueError('Unknown no-cut outcome')
            outcome[:]=known
        names=(*CANDIDATE_ORDER,CONTROL)
        detail.update(paired_outcomes={name:outcome[index].tolist() for index,name in enumerate(names)},
                      success_means={name:float(outcome[index].mean()) for index,name in enumerate(names)},
                      outcome_origin='physical_paired_branches' if valid else 'shared_known_no_cut_episode_outcome')
        full.append(outcome);per_source.append(detail)
        branch_costs.extend(group['branch_rows'])
    labels=np.stack(full);reached=np.asarray(reached,bool)
    def comparisons(y):
        correction={name:paired(y[:,i],y[:,0]) for i,name in enumerate(CANDIDATE_ORDER)}
        total={name:paired(y[:,i],y[:,13]) for i,name in enumerate(CANDIDATE_ORDER)}
        interruption=paired(y[:,0],y[:,13])
        errors={name:total[name]['net_gain']-interruption['net_gain']-correction[name]['net_gain']
                for name in CANDIDATE_ORDER}
        if any(abs(value)>1e-12 for value in errors.values()):
            raise ValueError('Paired mean I+A=T decomposition failed')
        return dict(candidates_vs_a0=correction,candidates_vs_continue_native10=total,
                    replan_vs_continue_native10=interruption,
                    i_a_t_decomposition=dict(I='replan minus continue_native10',A='candidate minus replan',
                        T='candidate minus continue_native10',mean_identity_error=errors,
                        rescues_and_harms='Computed directly for each comparison; counts are not additive.'),
                    positive_vs_negative={f'{CANDIDATE_ORDER[a]}__vs__{CANDIDATE_ORDER[b]}':paired(y[:,a],y[:,b]) for a,b in PAIR_INDICES})
    return dict(cohort_primary_slots=len(groups),reached_legal_cuts=int(reached.sum()),known_no_cut=int((~reached).sum()),
        unique_task_scene_fingerprints=len({(row['task'],row['scene_fingerprint']) for row in per_source}),
        full_planned_denominator=comparisons(labels),
        conditional_legal_cut_denominator=comparisons(labels[reached]) if reached.any() else None,
        by_task={task:comparisons(labels[[row['task']==task for row in per_source]]) for task in sorted({row['task'] for row in per_source})},
        coverage=dict(selection_categories=dict(Counter(row['selection_category'] for row in per_source)),
            actual_cuts=dict(Counter(str(row['actual_cut']) for row in per_source)),
            registered_cut_types=dict(Counter(row['registered_cut_rule']['kind'] for row in per_source)),
            replacements=sum(row['replacement'] for row in per_source)),
        candidate_information=dict(denominator='sources with a legal cut, excluding no-cut from critic-input statistics',
            sources=len(raw_rows),informative_mean_labels=sum(row['informative_mean_labels'] for row in raw_rows),
            any_candidate_mean_benefit=sum(row['any_candidate_mean_benefit'] for row in raw_rows),
            any_candidate_mean_harm=sum(row['any_candidate_mean_harm'] for row in raw_rows),
            any_paired_discordance=sum(row['any_paired_discordance'] for row in raw_rows),
            distinct_raw_groups=_stats([row['candidate_distinct_raw_groups'] for row in raw_rows]),
            nonbase_aliases_to_a0=_stats([row['nonbase_aliases_to_a0'] for row in raw_rows]),
            channel_fallback_sources={name:sum(row['channel_fallbacks'].get(name,False) for row in raw_rows) for name in ('xyz','gripper')},
            mean_mutable_fraction_per_dimension=np.mean([row['mask_mutable_fraction_per_dimension'] for row in raw_rows],axis=0).tolist() if raw_rows else None,
            no_mutable_xyz=sum(not row['xyz_any_mutable'] for row in raw_rows),
            no_mutable_gripper=sum(not row['gripper_any_mutable'] for row in raw_rows)),
        cost=dict(actual_branches=len(branch_costs),bank_wall_seconds=_stats(banks),
            branch_wall_seconds=_stats([row['wall_seconds'] for row in branch_costs]),
            branch_restore_seconds=_stats([row['restore_seconds'] for row in branch_costs]),
            policy_seconds=sum(row['policy_seconds'] for row in branch_costs),policy_calls=sum(row['policy_calls'] for row in branch_costs),
            paired_sampling='same suffix decision index; normal and intervention absolute sampling times can differ'),
        per_source=per_source,ranking_or_winner_selected=False,
        interpretation='Descriptive training-cut cohort; scheduled/fallback intervention times are not the deployment first-alarm policy. No independent validation or method selection.')


def run(config, bank_version='round1_labels_v1', *, min_train=50, progress_only=False):
    if type(min_train) is not int or min_train<50:
        raise ValueError('Scientific partial threshold must be at least50 registered training primary slots')
    snapshot=progress(config,bank_version)
    prefix=snapshot['primary_ids'][:min_train]
    ready=len(prefix)==min_train and all(key in snapshot['resolved'] for key in prefix)
    result=dict(schema='native10_main_progress_audit_v1',utc=datetime.now(timezone.utc).isoformat(),
        bank_version=bank_version,protocol_sha256=config['analysis_approval']['protocol_sha256'],
        minimum_training_slots=min_train,cohort_rule='fixed registered primary manifest prefix; all slots must complete, regardless of finish order',
        threshold_ready=ready,scientific_summary_emitted=False,progress=snapshot['operational'],
        scientific_summary=None,simulator_calls=0,optimizer_updates_executed=0,
        source_artifacts_modified=False,posthoc_partial_only=True)
    if ready and not progress_only:
        groups=[audit_one(key,config,bank_version,snapshot) for key in prefix]
        attempts=[number for group in groups for number in group['attempts']]
        if len(attempts)!=len(set(attempts)):raise ValueError('Partial groups reuse physical attempt IDs')
        result.update(scientific_summary=summarize(groups),scientific_summary_emitted=True,
                      audited_attempt_numbers=sorted(attempts),input_artifacts=list(snapshot['artifacts'].values()))
    else:
        result['scientific_summary_withheld_reason']='progress_only_requested' if progress_only else 'fixed_registered_prefix_not_complete'
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=storage.ROOT/'main_protocols/round1_v1/config.json')
    parser.add_argument('--bank-version',default='round1_labels_v1')
    parser.add_argument('--min-train',type=int,default=50)
    parser.add_argument('--progress-only',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();config=_read(args.config)
    result=run(config,args.bank_version,min_train=args.min_train,progress_only=args.progress_only)
    result['config_sha256']=storage.sha256(args.config);result['auditor_sha256']=storage.sha256(__file__)
    payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if args.output:
        target=args.output.resolve()
        if not target.is_relative_to((storage.ROOT/'progress_audits').resolve()):
            raise ValueError('New report files must be under ROOT/progress_audits')
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x') as stream:stream.write(payload)
        print(json.dumps(dict(output=str(target),scientific_summary_emitted=result['scientific_summary_emitted'])))
    else:
        print(payload,end='')


if __name__=='__main__':main()
