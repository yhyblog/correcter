"""Prepare a cross-protocol final-input specification, without model execution.

This independent interface consumes a sealed input bundle after both collection
waves have closed. It does not call the old single-collection _specification,
fit a PCA, deserialize weights, initialize a model, reserve an attempt or release
training. A later separately authorized preflight must consume this identity.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re

from . import storage
from .protocol import TASKS, canonical_hash, episode_key, seed_for

CODE = Path(__file__).resolve().parent
CONTRACT = storage.PACKAGE/'coordination/NATIVE10_FINAL_INPUT_CONTRACT.md'
CONTRACT_SHA = 'bceeccecbe2f5a41a27f05e8245ee8b9e68c525e8cb3d653a3460f275fab54a0'
DESIGN = storage.ROOT/'fit_protocols/round1_preflight_v1/training_design.json'
DESIGN_SHA = '3b9bbf7a67fc15123ac761c13358c0bfd8492ea9aea3c25649cefb02c66ef0cf'
FINAL_STEPS = [200, 400, 800, 1600, 2400, 3200, 4000]


def checked(path, expected):
    path = Path(path).resolve()
    if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected) or storage.sha256(path) != expected:
        raise ValueError('Required immutable input SHA differs: '+str(path))
    return path


def slot(row):
    return row.get('planned_slot_id', row['episode_id'])


def validate_final_view(loaded):
    """Check planned coverage and actual-source purposes, never filter on labels."""
    manifest = loaded['manifest']
    registry = {row['episode_id']: row for row in manifest}
    if len(registry) != len(manifest):
        raise ValueError('Duplicate registration identity')
    primary = [row for row in manifest if row.get('replacement_of') is None]
    result, purpose_ids = {}, {}
    for purpose, count, rounds in [('train', 600, {1, 2}), ('development', 100, None)]:
        packed = loaded[purpose]
        meta, rows = packed['metadata'], packed['rows']
        planned = [row for row in primary if row['split'] == purpose and (rounds is None or row.get('round') in rounds)]
        planned_ids = [row['episode_id'] for row in planned]
        if (len(planned) != count or Counter(row['task'] for row in planned) != Counter({task: count//5 for task in TASKS})
                or meta.get('purpose') != purpose or meta.get('planned_episode_count') != count
                or meta.get('manifest_sha256') != canonical_hash(manifest)
                or meta.get('complete_planned_selection_evidence') is not True
                or [slot(row) for row in meta['records']] != planned_ids):
            raise ValueError('Final input has changed planned coverage or technical incompleteness')
        records = {row['episode_id']: row for row in meta['records']}
        if any(not (row.get('critic_eligible') is True and row.get('control_complete') is True
                    or row.get('status') == 'no_cut' and row.get('full_episode_outcome_available') is True)
               for row in meta['records']):
            raise ValueError('Technical missing records cannot be relabeled as complete planned coverage')
        actual_ids = [row['episode_id'] for row in rows]
        eligible_ids = [row['episode_id'] for row in meta['records'] if row.get('critic_eligible') is True]
        if actual_ids != eligible_ids or len(set(actual_ids)) != len(actual_ids) or len(records) != count:
            raise ValueError('Effective rows must be exactly the unique eligible sources in planned order')
        lookup = {row['episode_id']: row for row in planned}
        for row in rows:
            actual, base = registry.get(row['episode_id']), lookup.get(slot(row))
            if (actual is None or base is None or row['episode_id'] != episode_key(row['task'], row['env_seed'])
                    or {k:v for k,v in row.items() if k != 'planned_slot_id'} != {k:v for k,v in actual.items() if k != 'planned_slot_id'}
                    or any(actual.get(key) != base.get(key) for key in ('task', 'split', 'round'))
                    or row['episode_id'] != slot(row) and actual.get('replacement_of') != slot(row)
                    or slot(records[row['episode_id']]) != slot(row)):
                raise ValueError('Effective row differs from its registered whole-episode identity')
        if len({slot(row) for row in rows}) != len(rows):
            raise ValueError('Two effective rows occupy the same planned source')
        purpose_ids[purpose] = list(records)
        result[purpose] = dict(planned=count, effective=len(rows), legitimate_without_critic_row=count-len(rows),
            effective_ids=actual_ids, planned_ids=planned_ids, actual_episode_ids=list(records),
            common_outcome_ids=[row['episode_id'] for row in meta['records'] if row.get('status') == 'no_cut'],
            by_task={task:dict(planned=count//5,effective=sum(row['task']==task for row in rows)) for task in TASKS})
    if set(purpose_ids['train']) & set(purpose_ids['development']):
        raise ValueError('Development leaked into training purposes')
    if result['train']['effective'] <= 16:
        raise ValueError('Too few unique valid training sources for the registered PCA16')
    return result


def sampling_recipe(rows, namespace):
    """Register draw counts/seeds only; actual bootstrap occurs after unique PCA."""
    counts = Counter(row['task'] for row in rows)
    if any(row['split'] != 'train' for row in rows) or len({row['episode_id'] for row in rows}) != len(rows):
        raise ValueError('Sampling recipe accepts only unique effective train sources')
    return dict(unit='complete actual training episode', total_draws=len(rows),
        task_draw_counts={task:counts[task] for task in TASKS}, replacement=True,
        source_uniform=True, teacher_weighting=False, round_weighting=False, outcome_weighting=False,
        implementation='training.stratified_episode_bootstrap',
        bootstrap_draws_materialized=False, materialize_after_unique_train_pca=True,
        members={path:[dict(member=member,
            initialization_seed=seed_for('training_initialization','final',path,member,namespace=namespace),
            bootstrap_seed=seed_for('training_bootstrap','final',path,member,namespace=namespace),
            minibatch_seed=seed_for('training_minibatches','final',path,member,namespace=namespace))
            for member in range(4)] for path in ('A','B')})


def build_specification(loaded, *, bundle_binding, design, design_binding, contract_binding, seed_namespace):
    """Pure CPU metadata preparation. Caller first verifies the complete bundle."""
    coverage = validate_final_view(loaded)
    approved = design['approved_parameters']
    if (approved['training_stages']['final']['checkpoints'] != FINAL_STEPS
            or approved['training_stages']['final']['max_updates_per_member'] != 4000
            or approved['loss']['weights'] != {'bce':1, 'gain':1, 'pair_difference':.5}
            or approved['paths']['A']['learning_rate'] != 1e-4
            or approved['paths']['B']['learning_rate'] != 3e-4
            or approved['ensemble']['members'] != 4):
        raise ValueError('Final preparation changed the approved scientific design')
    if loaded['input_bundle_sha256'] != bundle_binding['input_bundle_sha256']:
        raise ValueError('Joint input identity differs from supplied binding')
    sources = deepcopy(loaded['metadata']['sources'])
    if set(sources) != {'round1_train','round2_train','development'}:
        raise ValueError('Final preparation requires exactly two train sources and original development')
    protocols = {name:source['pipeline_binding']['input_protocol_sha256'] for name,source in sources.items()}
    if protocols['round1_train'] != protocols['development'] or protocols['round1_train'] == protocols['round2_train']:
        raise ValueError('Two true collection protocols and original dev provenance must remain explicit')
    train_ids, dev_ids = coverage['train']['effective_ids'], coverage['development']['effective_ids']
    all_dev_ids = coverage['development']['actual_episode_ids']
    recipe = sampling_recipe(loaded['train']['rows'], seed_namespace)
    purposes = dict(pca_fit=train_ids, training_loss=train_ids, bootstrap_available=train_ids,
                    checkpoint_inference=dev_ids, checkpoint_selection=all_dev_ids)
    intersections = {name: sorted(set(train_ids)&set(all_dev_ids))
        for name in ('pca_vs_development','loss_vs_development','bootstrap_vs_development')}
    return dict(schema='native10_final_prepare_interface_v1', task_id='native10-training-20260916',
        status='prepared_pending_final_preflight_release', phase='final', input_bundle=deepcopy(bundle_binding),
        source_bindings=sources, source_protocols=protocols, manifest_sha256=canonical_hash(loaded['manifest']),
        design=deepcopy(design_binding), input_contract=deepcopy(contract_binding), seed_namespace=seed_namespace,
        coverage=coverage, purpose_episode_ids=purposes, purpose_intersections=intersections,
        development_selection=dict(planned_denominator=100,model_inference_count=len(dev_ids),
            common_outcome_ids=coverage['development']['common_outcome_ids'],
            include_common_outcomes_in_full_denominator=True),
        canonical_input='original canonical arrays only; never concatenate critic PCA coordinates or Q features',
        preprocessing=dict(A='original old four-member projections; fresh warm start from original assets',
            B=dict(visual_dimensions=16,language_dimensions=8,fit_episode_ids=train_ids,
                fit_source_count=len(train_ids),unique_source_once=True,bootstrap_duplicates_used=False,
                fit_before_bootstrap=True,new_initialization_after_pca=True,
                implementation='training.fit_train_preprocessing', preserve_existing_near_zero_pc_floor=True)),
        old_weight_import=deepcopy(design['old_weight_import']), sampling_recipe=recipe,
        scientific_parameters={key:deepcopy(approved[key]) for key in
            ('loss','optimizer_common','ensemble','paths','training_stages','model_selection')},
        future_execution=dict(preflight_scope='final_fit_preflight',optimizer_stage='training_final',
            simulator_attempts=0,max_optimizer_updates_per_member=4000,max_optimizer_updates=32000,
            fixed_checkpoints=FINAL_STEPS,requires_new_ready_and_sealed_initialization=True,
            single_protocol_pipeline_allowed=False),
        execution=dict(simulator_calls=0,pca_fits=0,weight_deserializations=0,model_initializations=0,
            optimizer_updates=0,bootstrap_draws=0,training_released=False,preflight_released=False))


def prepare(*, bundle_binding, version, contract_path=CONTRACT):
    """Create a NEW pending specification after the static cross-protocol audit."""
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', version):
        raise ValueError('Use a safe explicit NEW version')
    contract = checked(contract_path, CONTRACT_SHA)
    design_path = checked(DESIGN, DESIGN_SHA)
    design = json.loads(design_path.read_text())
    if not isinstance(bundle_binding, dict):
        bundle_binding = json.loads(Path(bundle_binding).read_text())
    from .final_input_bundle_v1 import load_bundle
    loaded = load_bundle(bundle_binding)
    config_paths = {source['collection']['config_path'] for source in loaded['metadata']['sources'].values()}
    namespaces = {json.loads(Path(path).read_text())['seed_namespace'] for path in config_paths}
    if len(namespaces) != 1:
        raise ValueError('Collection seed namespaces differ')
    # Validate bytes only; weights and projection tensors are never deserialized.
    imports = design['old_weight_import']
    checked(storage.PACKAGE/imports['ranking'], imports['ranking_sha256'])
    for path,digest in imports['files'].items():
        checked(storage.PACKAGE/path,digest)
    specification = build_specification(loaded,bundle_binding=bundle_binding,design=design,
        design_binding=dict(path=str(design_path),sha256=DESIGN_SHA),
        contract_binding=dict(path=str(contract),sha256=CONTRACT_SHA),seed_namespace=namespaces.pop())
    paths = [Path(__file__), CODE/'final_input_bundle_v1.py', CODE/'training.py', CODE/'training_pipeline.py',
             CODE/'dataset.py', CODE/'artifact_loader.py', CODE/'protocol.py', CODE/'storage.py']
    specification['code_files'] = {str(path.resolve()):storage.sha256(path) for path in paths}
    destination = storage.ROOT/'final_preparations'/version
    destination.mkdir(parents=True,exist_ok=False)
    storage.dump(destination/'specification.json',specification)
    storage.seal(destination,role='native10_final_prepare_pending_interface',simulator_calls=0,
        pca_fits=0,model_initializations=0,optimizer_updates=0,not_execution_release=True)
    return dict(path=str(destination),seal_sha256=storage.sha256(destination/'complete.json'),
                input_bundle_sha256=loaded['input_bundle_sha256'],status=specification['status'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-binding',type=Path,required=True)
    parser.add_argument('--version',required=True)
    parser.add_argument('--contract-path',type=Path,default=CONTRACT)
    args=vars(parser.parse_args())
    print(json.dumps(prepare(**args),ensure_ascii=False))


if __name__=='__main__':
    main()
