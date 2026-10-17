"""Isolated heldout capture/policy5 guards; importing performs no model work.

Actual collection requires separately frozen heldout and initialization-
replacement releases. Heldout uses new sources and its own bank a0, never
an old development anchor. Statistical selection is outside this collector.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import numpy as np
from .main_collection import (MainCollector, POLICY_METHODS, SPLIT_REPLICATES, _read,
    _sealed, _load_arrays, _bit_equal, select_cut)
from .protocol import TASKS, candidate_seed, canonical_hash, require_stage_budget, validate_manifest
from .storage import ROOT, AttemptLedger, dump, seal, sha256
from .policy_deployment_round2_v1 import _noise, _raw, _matched_rms

SCHEMA='native10_heldout_collection_v1'
STAGE=SCOPE='heldout'
BANK='heldout_policy_v1'
REPLACEMENT_STAGE='technical_reserve'
REPLACEMENT_SCOPE='heldout_initialization_replacements'
FINAL_MODEL_SEAL='864c00cfa1cfcbcc8736a898ab22e5afa821f15afbe2b8dc687f7731f2eea83e'
FINAL_SELECTED_SEAL='f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a'
EFFECTIVE_CUT_POLICY=dict(policy='first_legal_alarm_only',training_fallback_allowed=False,no_alarm_common_outcome=True)
GLOBAL_ACCEPTANCE=dict(primary_method='post',fallback_method='alarm_replan10',
    rule='mean_paired_post_minus_replan_strictly_positive',source_denominator=100,replicates=2,no_cut_difference=0)
MATCHING_DEPENDENCIES=('velocity_matched','direct_matched','post_matched','reverse_matched','random_matched')
SCIENTIFIC_KEYS=('source_horizon','prefix_horizon','suffix_horizon','control_budget','gate_threshold','guidance','matching','command_semantics','seed_namespace')
UNCHANGED=('episode_manifest','seed_namespace','source_horizon','prefix_horizon','suffix_horizon',
    'control_budget','gate_threshold','guidance','matching','cpu','split_replicates','scene_identity','command_semantics','methods')

def _inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()) or path.is_relative_to((ROOT/'p0').resolve()):
        raise ValueError('Deployment references must be inside the new workflow, outside P0')
    return path

def _file(path, expected):
    path = _inside(path)
    if not isinstance(expected, str) or len(expected) != 64 or sha256(path) != expected:
        raise ValueError('Deployment bound file SHA changed: '+str(path))
    return path

def _completed(path, expected, *, protocol=None):
    path = _inside(path)
    _file(path/'complete.json', expected)
    record = _read(path/'complete.json')
    # Training exports intentionally have no simulator protocol field. The exact
    # complete seal is still bound, and its entire file inventory is verified.
    _sealed(path, [protocol] if protocol is not None else [record.get('protocol_sha256')])
    return record

def _selected(config, binding, registration):
    path = _inside(binding['path'])
    if (path != (ROOT/'models/final/final_fit_v1').resolve()
            or binding['seal_sha256'] != FINAL_MODEL_SEAL
            or binding['selected_seal_sha256'] != FINAL_SELECTED_SEAL):
        raise ValueError('Heldout is fixed to the approved final A4000 model and selected seals')
    complete = _completed(path, binding['seal_sha256'])
    if complete.get('role') != 'native10_final_two_path_training' or complete.get('phase') != 'final':
        raise ValueError('Heldout requires the completed final A4000 two-path training export')
    result = _read(path/'result.json')
    selected = path/'selected'
    selection = result.get('selection', {})
    if (selection.get('path') != 'A' or selection.get('step') != 4000
            or result.get('optimizer_updates') != 32000 or result.get('simulator_calls') != 0):
        raise ValueError('Final heldout cannot replace A4000 or its completed 32000-update identity')
    if (result.get('status') != 'complete' or result.get('phase') != 'final'
            or _inside(result['selected_assets']) != selected
            or _inside(config['critic_assets']) != selected):
        raise ValueError('Selected critic must be the completed training result selection')
    export = _completed(selected, binding['selected_seal_sha256'])
    ranking = _read(selected/'ranking.json')
    hashes = ranking.get('model_hashes', {})
    if (export.get('role') != 'four_member_critic_export' or set(hashes) != {'0', '1', '2', '3'}
            or ranking.get('horizon') != 10 or ranking.get('a0_slot') != 0
            or hashes != result.get('model_hashes') or hashes != complete.get('model_hashes')
            or hashes != export.get('model_hashes') or hashes != registration['critic_member_hashes']):
        raise ValueError('Selected critic member hashes/role/horizon disagree')
    for member, digest in hashes.items():
        _file(selected/f'models/refit/member_{member}/selected.pt', digest)
        if registration['model_hashes'].get('critic_'+member) != digest:
            raise ValueError('Registered critic model identity differs from selected export')
    reload_path = _file(path/'selected_reload_audit.json', binding['selected_reload_audit_sha256'])
    audit = _read(reload_path)
    checks = ('feature_cache_bit_exact', 'thirteen_candidate_member_probability_bit_exact',
              'member_and_ensemble_gradient_bit_exact', 'a0_anchor_exactly_zero', 'state_and_anchor_immutable')
    if (audit.get('status') != 'passed' or audit.get('members_checked') != 4
            or audit.get('gradient_slots') != [0, 11] or any(audit.get(key) is not True for key in checks)):
        raise ValueError('Selected export lacks complete real development reload audit')
    review_binding = binding['model_review']
    review_path = Path(review_binding['path']).resolve()
    if (not review_path.is_relative_to(ROOT.parents[1].resolve())
            or sha256(review_path) != review_binding['sha256']):
        raise ValueError('Final selected model review binding changed')
    review = _read(review_path); reviewed = review.get('bindings', {})
    if (review.get('schema') != 'native10_final_trained_model_independent_review_v1'
            or review.get('status') != 'passed' or review.get('blockers') != []
            or review.get('model_hashes') != hashes
            or review.get('selection', {}).get('path') != 'A'
            or review.get('selection', {}).get('step') != 4000
            or Path(reviewed.get('model_directory','')).resolve() != path
            or Path(reviewed.get('selected_directory','')).resolve() != selected
            or reviewed.get('model_complete_sha256') != binding['seal_sha256']
            or reviewed.get('model_result_sha256') != sha256(path/'result.json')
            or reviewed.get('selected_complete_sha256') != binding['selected_seal_sha256']
            or reviewed.get('selected_reload_audit_sha256') != binding['selected_reload_audit_sha256']
            or reviewed.get('selected_config_sha256') != sha256(selected/'config.json')
            or reviewed.get('selected_ranking_sha256') != sha256(selected/'ranking.json')):
        raise ValueError('Independent review does not bind these actual final A4000 assets')
    model_paths = [str(selected/f'models/refit/member_{m}/selected.pt') for m in range(4)]
    if (len(review.get('selected_models', [])) != 4
            or any(record.get('member') != m or record.get('path') != model_paths[m]
                   or record.get('sha256') != hashes[str(m)]
                   or record.get('exact_tensor_match_to_A4000_checkpoint') is not True
                   for m,record in enumerate(review['selected_models']))):
        raise ValueError('Final model review member identities differ from actual selected export')
    return dict(path=str(path), seal_sha256=binding['seal_sha256'],
                selected_assets=str(selected), selected_seal_sha256=binding['selected_seal_sha256'],
                model_hashes=hashes, model_paths=model_paths, selection=dict(path='A',step=4000),
                selected_reload_audit_sha256=binding['selected_reload_audit_sha256'],
                selected_config_sha256=sha256(selected/'config.json'),
                selected_ranking_sha256=sha256(selected/'ranking.json'),
                model_review=dict(path=str(review_path),sha256=review_binding['sha256']))


def _load_selection(binding,*,require_actual=False):
    # Shared strict metadata validator; this never grants heldout execution.
    from .heldout_prepare_v1 import validate_final_selection_reference
    return validate_final_selection_reference(binding,require_actual=require_actual)


def _final_selection(config,binding,*,require_release):
    if binding.get('status')=='pending_selection_seal':
        if require_release: raise ValueError('Actual final selection seal is required before heldout execution')
        if set(binding)!={'status','expected_directory','preparation','payload'}:
            raise ValueError('Pending selection must use explicit preparation/payload bindings, never invented seal SHA')
        directory=_inside(binding['expected_directory'])
        preparation=binding['preparation'];folder=_inside(preparation['path'])
        _completed(folder,preparation['seal_sha256'])
        payload=_file(binding['payload']['path'],binding['payload']['sha256'])
        if not payload.is_relative_to(folder):raise ValueError('Pending selection payload must be inside sealed preparation')
        checked=_load_selection(binding,require_actual=False)
        if checked.get('status')!='pending_selection_seal':raise ValueError('Pending selection payload status differs')
        return dict(status='pending_selection_seal',expected_directory=str(directory),execution_authorized=False,
            preparation=deepcopy(preparation),payload=deepcopy(binding['payload']))
    if set(binding)!={'path','seal_sha256','result_sha256'}:
        raise ValueError('Heldout requires an explicit actual final selection directory/seal/result binding')
    directory=_inside(binding['path']);_completed(directory,binding['seal_sha256'])
    _file(directory/'result.json',binding['result_sha256'])
    result=_load_selection(binding,require_actual=True)
    if (result.get('status')!='sealed' or result.get('schema')!='native10_final_selection_v1'
            or result.get('stage')!='calibration_selection_seal' or result.get('scope')!='calibration_selection_seal'
            or result.get('method')!='post' or result.get('post_enabled_on_alarm') is not True
            or result.get('primary_comparison')!='post_minus_alarm_replan10'
            or result.get('physical_methods')!=list(POLICY_METHODS)
            or result.get('scientific_parameters')!={k:config[k] for k in SCIENTIFIC_KEYS}
            or result.get('heldout_release') is not False):
        raise ValueError('Final selection method, scope or frozen scientific parameters differ')
    critic=result.get('fixed_critic',{});training=config['heldout_collection']['selected_training']
    expected_assets=str(Path(config['critic_assets']).resolve())
    if (critic.get('path')!='A' or critic.get('step')!=4000 or critic.get('members')!=4
            or critic.get('selected_directory')!=expected_assets
            or critic.get('selected_seal')!={'path':str(Path(expected_assets)/'complete.json'),'sha256':training['selected_seal_sha256']}
            or critic.get('selected_reload_audit')!={'path':str(Path(training['path'])/'selected_reload_audit.json'),'sha256':training['selected_reload_audit_sha256']}):
        raise ValueError('Final selection is not bound to the actual fixed A4000 export')
    expected_hashes=config['main_collection']['banks'][BANK]['critic_member_hashes']
    members=critic.get('member_checkpoints',[])
    if (len(members)!=4 or any(row.get('path')!=str(Path(expected_assets)/f'models/refit/member_{index}/selected.pt')
            or row.get('sha256')!=expected_hashes[str(index)] for index,row in enumerate(members))):
        raise ValueError('Final selection four actual member file identities differ')
    return dict(status='sealed',**deepcopy(binding),method='post',post_enabled_on_alarm=True,
        primary_comparison='post_minus_alarm_replan10',selection_after_heldout_allowed=False)


def _scene_prefix(config):
    binding=config.get('heldout_preparation',{}).get('scene_registry_before')
    if not isinstance(binding,dict): raise ValueError('Heldout requires sealed scene registry prefix')
    snapshot=_file(binding['snapshot_path'],binding['sha256']);prefix=snapshot.read_bytes()
    live=_inside(binding['live_path'])
    if (live!=(ROOT/'scene_registry/entries.jsonl').resolve() or binding.get('bytes')!=len(prefix)
            or binding.get('records')!=len(prefix.splitlines()) or prefix and not prefix.endswith(b'\n')):
        raise ValueError('Heldout scene prefix identity/boundary changed')
    with live.open('rb') as stream:
        if stream.read(len(prefix))!=prefix: raise ValueError('Scene registry changed before immutable prefix end')
    return deepcopy(binding)


def validate_heldout_inputs(config, bank_version=BANK, *, require_release=False):
    """Read registered metadata/SHA only; pending validation grants no execution."""
    if bank_version!=BANK: raise ValueError('Only heldout_policy_v1 is registered')
    if (config.get('stage_release_scopes',{}).get(STAGE)!=SCOPE
            or config.get('stage_release_scopes',{}).get(REPLACEMENT_STAGE)!=REPLACEMENT_SCOPE):
        raise ValueError('Heldout and initialization replacements need separate exact scopes')
    if require_release:
        require_stage_budget(config,STAGE)
        require_stage_budget(config,REPLACEMENT_STAGE)
    limits=config['budget']
    if (limits.get('hard_total')!=50000 or limits.get('training_update_total')!=51200
            or limits['stages'].get(STAGE)!=dict(simulator_attempts=2200,training_updates=0)
            or limits['stages'].get(REPLACEMENT_STAGE)!=dict(simulator_attempts=1200,training_updates=0)
            or limits.get('count_failures') is not True or limits.get('count_retries') is not True):
        raise ValueError('Heldout budgets require 2200/1200, global 50000/51200, zero new updates')
    binding=config['heldout_collection']
    if (binding.get('schema')!=SCHEMA or binding.get('effective_cut_policy')!=EFFECTIVE_CUT_POLICY
            or binding.get('global_acceptance')!=GLOBAL_ACCEPTANCE
            or binding.get('fixed_primary_comparison')!='post_minus_alarm_replan10'
            or binding.get('selection_after_heldout_allowed') is not False):
        raise ValueError('Heldout must retain first alarm and the one preregistered global post choice')
    from .heldout_prepare_v1 import statistics_contract
    if config.get('heldout_statistics')!=statistics_contract(config):
        raise ValueError('Heldout statistics must freeze post primary, original 100 sources, four repeats and no reselection')
    original=binding['original_collection']
    old_path=_file(original['config_path'],original['config_sha256'])
    frozen_path=_file(original['freeze_path'],original['freeze_sha256'])
    old,frozen=_read(old_path),_read(frozen_path)
    if frozen.get('files',{}).get(str(old_path))!=original['config_sha256']:
        raise ValueError('Original policy freeze does not bind original configuration')
    old_bank=old['main_collection']['banks'][original['bank_version']]
    registration=config['main_collection']['banks'][bank_version]
    if (set(config['main_collection']['banks'])!={bank_version}
            or registration.get('kind')!='policy5' or registration.get('stage')!=STAGE
            or registration.get('generation_round')!=2 or registration.get('generation_phase')!='heldout'
            or registration.get('cut_selection_policy')!='analysis_lead_v1'
            or registration.get('allowed_source_protocol_sha256',[])!=[]
            or 'channel_radius_by_episode' in registration):
        raise ValueError('Heldout requires its sole policy5 bank, final critic lineage and new source protocol')
    for key in UNCHANGED:
        if key not in old or config.get(key)!=old[key]: raise ValueError('Heldout changed frozen scientific semantics: '+key)
    if config['split_replicates']!=SPLIT_REPLICATES or config['methods']!=list(POLICY_METHODS):
        raise ValueError('Heldout retains all five arms and exactly four paired suffixes')
    for key in ('replacement_candidates','replacement_capture_stage','concurrency'):
        if config['main_collection'].get(key)!=old['main_collection'].get(key):
            raise ValueError('Heldout changed original replacement registration/concurrency: '+key)
    if (config['main_collection']['replacement_capture_stage']!=REPLACEMENT_STAGE
            or config['main_collection']['concurrency'].get('workers_per_gpu')!=4
            or registration.get('random_seed_domain')!=old_bank.get('random_seed_domain')):
        raise ValueError('Heldout requires original ordered replacement and 8x4 execution semantics')
    if any(registration['model_hashes'].get(key)!=old_bank['model_hashes'][key] for key in ('vla','d','g0','implementation')):
        raise ValueError('Heldout changed frozen VLA/D/G0/implementation')
    lookup=validate_manifest(old['episode_manifest'])
    primaries=[row for row in old['episode_manifest'] if row['split']=='heldout' and not row.get('replacement_of')]
    ids=[row['episode_id'] for row in primaries]
    if (len(ids)!=100 or registration.get('episode_ids')!=ids
            or Counter(row['task'] for row in primaries)!=Counter({task:20 for task in TASKS})):
        raise ValueError('Heldout must retain original ordered 100 slots and 20 per task')
    if binding.get('requested_cut_rules_sha256')!=canonical_hash({r['episode_id']:r['cut_rule'] for r in primaries}):
        raise ValueError('Heldout original cut registration changed')
    cases={}
    for row in primaries:
        identity=row['episode_id']
        if (row.get('case_id')!=identity or row.get('round') is not None or row.get('source_horizon')!=10
                or row.get('cut_rule')!={'kind':'first_alarm'}):
            raise ValueError('Heldout sources must use original first alarm with no training fallback')
        cases[identity]=deepcopy(row)
        backups=config['main_collection']['replacement_candidates'].get(identity,[])
        if len(backups)!=2 or len(set(backups))!=2:
            raise ValueError('Heldout requires exactly two original ordered backups per slot')
        for ordinal,backup in enumerate(backups,1):
            candidate=lookup[backup]
            if (candidate.get('replacement_of')!=identity or candidate.get('case_id')!=backup
                    or candidate.get('replacement_ordinal')!=ordinal
                    or any(candidate.get(k)!=row.get(k) for k in ('task','split','round','cut_rule','source_horizon'))):
                raise ValueError('Heldout backup provenance or original order changed')
            cases[backup]=deepcopy(candidate)
    selection=_final_selection(config,binding['final_selection'],require_release=require_release)
    selected=_selected(config,binding['selected_training'],registration)
    scene=_scene_prefix(config)
    return dict(status='passed',stage=STAGE,scope=SCOPE,bank_version=bank_version,episode_ids=ids,cases=cases,
        planned_primary_sources=100,primary_capture_limit=100,expected_max_attempts=2200,
        expected_max_candidate_restores=100,expected_max_branches=2000,replacement_stage=REPLACEMENT_STAGE,
        selected_training=selected,final_selection=selection,scene_registry_before=scene,config_binding_sha256=canonical_hash(config),
        simulator_calls=0,model_calls=0,optimizer_updates=0,new_heldout_capture_allowed=True,
        old_guided_action_reuse_allowed=False,cross_bank_a0_identity_required=False,
        effective_cut_policy=deepcopy(EFFECTIVE_CUT_POLICY),global_acceptance=deepcopy(GLOBAL_ACCEPTANCE),
        heldout_selection_execution_authorized=False)


def _legal_cut(value):
    return bool(re.fullmatch(r'cut[0-9]{3}',value)) and 5<=int(value[3:])<=285 and int(value[3:])%10==5


class _HeldoutLedger:
    def __init__(self,delegate,inputs): self.delegate,self.inputs=delegate,inputs
    def reserve(self,stage,kind,identity,*,resource='simulator_attempts',requested=1):
        if resource!='simulator_attempts' or type(requested) is not int or requested!=1:
            raise ValueError('Heldout forbids updates and batched reservations')
        value=str(identity);cases=self.inputs['cases'];allowed=False
        if kind=='source_capture':
            case=cases.get(value)
            allowed=case is not None and stage==(REPLACEMENT_STAGE if case.get('replacement_of') else STAGE)
        else:
            parts=value.split('/')
            if stage==STAGE and kind=='candidate_restore' and len(parts)==4:
                allowed=parts[:2]==['banks',BANK] and parts[2] in cases and _legal_cut(parts[3])
            if stage==STAGE and kind=='branch_including_restore' and len(parts)==7:
                allowed=(parts[:3]==['rollouts',STAGE,BANK] and parts[3] in cases and _legal_cut(parts[4])
                    and parts[5] in POLICY_METHODS and parts[6] in ('repeat_0','repeat_1','repeat_2','repeat_3'))
        if not allowed: raise ValueError('Heldout attempt is outside registered stage/source/arm/repeat')
        return self.delegate.reserve(stage,kind,value,resource=resource,requested=requested)


def audit_heldout_commands(plans,formal,directions,generation,matching):
    """Same-bank raw/score/gradient metadata invariants; no historical a0 input."""
    if set(plans)!=set(POLICY_METHODS[1:]): raise ValueError('Heldout bank requires all four intervention plans')
    raw=_raw(plans['alarm_replan10']);base=np.clip(raw,-1,1)
    mask=1-np.abs(base[:10].astype(float))>=matching['boundary_clearance']
    if (not _bit_equal(formal['raw_a0'],raw) or not _bit_equal(formal['critic_a0'],base)
            or not _bit_equal(formal['mask'],mask) or not _bit_equal(directions['raw_a0'],raw)
            or not _bit_equal(directions['critic_a0'],base)
            or not _bit_equal(directions['critic_candidates'],np.stack([np.clip(plans[m],-1,1) for m in POLICY_METHODS[1:]]))):
        raise ValueError('Heldout same-bank a0/mask/critic mapping changed')
    for value in plans.values():
        value=_raw(value)
        if not _bit_equal(value[10:],raw[10:]) or not _bit_equal(value[:10][~mask],raw[:10][~mask]):
            raise ValueError('Heldout correction changed tail or masked raw coordinates')
    from .bank_audit import audit_raw_bank
    names=dict(alarm_replan10='replan',velocity='velocity_matched',direct='direct_matched',post='post_matched')
    raw_audit=audit_raw_bank(raw,{names[k]:v for k,v in plans.items()},matching)
    rms=_matched_rms(raw_audit,matching)
    dependency_plans={}
    for name in ('replan',)+MATCHING_DEPENDENCIES:
        delta=np.asarray(formal[name+'_actual_delta'])
        proxy=np.asarray(formal[name+'_critic_commands'])
        if delta.shape!=(10,4) or not np.isfinite(delta).all():
            raise ValueError('Heldout must preserve every original matched direction dependency')
        if proxy.shape!=(10,4) or proxy.dtype!=np.dtype('float32') or not np.isfinite(proxy).all():
            raise ValueError('Invalid saved matched critic commands')
        # Mirror preserve_raw_anchor: zero deltas retain the raw sign bit;
        # changed feasible commands equal the saved bounded candidate exactly.
        plan=raw.copy();changed=delta!=0
        plan[:10][changed]=proxy[changed]
        if (not _bit_equal(plan[:10].astype(float)-raw[:10].astype(float),delta)
                or not _bit_equal(np.clip(plan[:10],-1,1),proxy)):
            raise ValueError('Saved matched direction raw/critic representation changed')
        dependency_plans[name]=plan
    if any(not _bit_equal(dependency_plans[names[method]],plans[method]) for method in POLICY_METHODS[1:]):
        raise ValueError('Executed heldout candidates differ from complete matching dependency outputs')
    dependency_audit=audit_raw_bank(raw,dependency_plans,matching)
    dependency_spreads={g:max(dependency_audit['actual'][name]['actual_delta'][g+'_rms'] for name in MATCHING_DEPENDENCIES)
        -min(dependency_audit['actual'][name]['actual_delta'][g+'_rms'] for name in MATCHING_DEPENDENCIES) for g in ('xyz','gripper')}
    if any(value>matching['tolerance'] for value in dependency_spreads.values()):
        raise ValueError('Original full matching dependency amplitudes no longer agree')
    for name in ('post_command_gradient','post_internal_metric_direction'):
        value=np.asarray(formal[name])
        if value.shape!=(10,4) or not np.isfinite(value).all(): raise ValueError('Nonfinite/invalid saved post gradient')
    noise=_noise(generation)
    if (generation.get('same_noise') is not True or generation.get('a0_slot')!=0
            or generation.get('saved_queue_unchanged') is not True or generation.get('saved_before_any_branch') is not True
            or generation.get('bank_predictions',{}).get('alarm_replan10',{}).get('mean_gain')!=0
            or generation.get('post_gradient',{}).get('value')!=0):
        raise ValueError('Heldout fixed-state/slot-zero/gradient/noise invariant failed')
    for mode in ('velocity','direct'):
        for update in generation['guidance'][mode].get('updates',[]):
            if (update.get('mode')!=mode or update.get('direct_gradient_outside_mask')!=0
                    or update.get('objective_semantics')!='maximize_mean_member_relative_success_probability'):
                raise ValueError('Heldout saved gradient injection semantics changed')
    return dict(status='passed',raw_bank_audit=raw_audit,matched_rms=rms,noise_sha256=noise,
        complete_matching_dependencies=list(MATCHING_DEPENDENCIES),dependency_raw_audit=dependency_audit,
        dependency_rms_spread=dependency_spreads,reverse_random_physical_branches=False,
        raw50_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),raw_a0_identity_scope='within_this_new_heldout_bank',
        old_development_a0_compared=False,critic_command_mapping_exact=True,raw_tail_and_mask_preserved=True,
        finite_post_gradients=True,slot_zero_anchor_exact=True)


def verify_heldout_bank(bank_path,case,source_path,config):
    bank,source=_inside(bank_path),_inside(source_path);protocol=config['analysis_approval']['protocol_sha256']
    _sealed(source,[protocol]);_sealed(bank,[protocol]);generation=_read(bank/'generation.json')
    summary=_read(source/'summary.json');cut=summary['actual_cut']
    selection=select_cut(case,summary['available_legal_cuts'],summary['first_legal_alarm_step'])
    if (case['split']!='heldout' or summary['cuts']!=[cut] or selection['selection_reason']!='first_legal_alarm'
            or selection['selection_audit']['training_fallback_allowed'] is not False
            or any(summary.get(k)!=v for k,v in selection.items())
            or source!=(ROOT/'sources'/case['case_id']).resolve()
            or bank!=(ROOT/'banks'/BANK/case['case_id']/f'cut{cut:03d}').resolve()):
        raise ValueError('Heldout bank must belong to its new first legal alarm source')
    expected=dict(episode_id=case['episode_id'],cut_step=cut,stage=STAGE,bank_version=BANK,
        generation_round=2,generation_phase='heldout',source_protocol_sha256=protocol,
        source_seal_sha256=sha256(source/'complete.json'),base_seed=candidate_seed(case,cut,namespace=config['seed_namespace']))
    if any(generation.get(k)!=v for k,v in expected.items()): raise ValueError('Heldout bank/source/random-stream provenance differs')
    report=audit_heldout_commands(_load_arrays(bank/'plans.npz'),_load_arrays(bank/'formal_directions.npz'),
        _load_arrays(bank/'directions.npz'),generation,config['matching'])
    return dict(report,episode_id=case['episode_id'],cut=cut,bank_path=str(bank),bank_seal_sha256=sha256(bank/'complete.json'),
        source_seal_sha256=sha256(source/'complete.json'),base_seed=generation['base_seed'],checked_before_branch=True)


class HeldoutCollector(MainCollector):
    def __init__(self,engine,config,ledger,stage=STAGE,*,bank_version=BANK,_validated=None):
        inputs=deepcopy(_validated if _validated is not None else validate_heldout_inputs(config,bank_version,require_release=True))
        if stage!=STAGE or inputs['config_binding_sha256']!=canonical_hash(config):
            raise ValueError('Heldout collector differs from validated configuration')
        self.heldout_inputs=inputs
        super().__init__(engine,config,_HeldoutLedger(ledger,inputs),stage,bank_version=bank_version)

    def _verify_models(self):
        super()._verify_models()
        expected=self.heldout_inputs['selected_training'];selector=self.engine.selector
        paths=[str(Path(p).resolve()) for p in selector.model_paths]
        if (Path(selector.assets_dir).resolve()!=Path(expected['selected_assets']).resolve()
                or paths!=expected['model_paths'] or selector.ranking['model_hashes']!=expected['model_hashes']):
            raise ValueError('Actual loaded heldout critic differs from fixed A4000')
        first=not hasattr(self,'loaded_identity');selector.verify(check_files=first)
        if first:
            self.loaded_identity=dict(status='passed',stage=STAGE,selected_assets=expected['selected_assets'],
                selected_path=expected['selected_assets'],selected_seal_sha256=expected['selected_seal_sha256'],
                model_paths=paths,member_hashes=deepcopy(expected['model_hashes']),model_hashes=deepcopy(expected['model_hashes']),
                selected_reload_audit_sha256=expected['selected_reload_audit_sha256'],selection=dict(path='A',step=4000),
                optimizer_updates=0,final_selection=deepcopy(self.heldout_inputs['final_selection']),
                actual_selector_paths=True,checkpoint_file_sha=True,
                frozen_parameter_buffer_versions=True,eval_cpu_no_parameter_grad=True)

    def _authorize(self,case):
        if (self.heldout_inputs['cases'].get(case.get('episode_id'))!=case
                or canonical_hash(self.config)!=self.heldout_inputs['config_binding_sha256']):
            raise ValueError('Heldout source/config identity changed')
        super()._authorize(case)  # Includes original ordered sealed pre-action rejection checks.

    def _provenance(self,case,source,bank=None):
        return dict(super()._provenance(case,source,bank),generation_phase='heldout')

    def _bank(self,case,source,cut):
        bank,plans,metadata=super()._bank(case,source,cut)
        report=verify_heldout_bank(bank,case,source,self.config)
        folder=ROOT/'heldout_guard'/self.stage/self.bank_version/case['episode_id']
        if folder.exists():
            _sealed(folder,[self.protocol_sha256])
            if _read(folder/'bank_check.json')!=report: raise ValueError('Heldout recorded bank check changed')
        else:
            dump(folder/'bank_check.json',report)
            seal(folder,protocol_sha256=self.protocol_sha256,role='heldout_same_bank_check')
        return bank,plans,metadata

    def prepare_bank(self,case,source,cut_step):
        result=super().prepare_bank(case,source,cut_step)
        self._bank(case,source,cut_step)
        return result


def create_heldout_collector(config,stage=STAGE,*,bank_version=BANK,ledger=None):
    inputs=validate_heldout_inputs(config,bank_version,require_release=True)
    if stage!=STAGE: raise ValueError('Heldout factory cannot enter another stage')
    from .engine import create_engine
    engine=create_engine(config,stage)
    try:
        return HeldoutCollector(engine,config,ledger if ledger is not None else AttemptLedger(config),stage,
            bank_version=bank_version,_validated=inputs)
    except BaseException:
        engine.close();raise


def collect_heldout_slot(collector,primary):
    if (not isinstance(collector,HeldoutCollector) or primary.get('replacement_of')
            or primary.get('episode_id') not in collector.heldout_inputs['episode_ids']):
        raise ValueError('Heldout slot entry requires one original guarded primary')
    from .main_runner import resolve_slot
    return resolve_slot(collector,primary)
