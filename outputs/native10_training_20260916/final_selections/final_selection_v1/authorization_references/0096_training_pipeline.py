"""Prepared native10 A/B ensemble pipeline; no real execution occurs on import.

``preflight(config, phase=..., version=...)`` requires a separate CPU fit-before
scope and writes only zero-update PCA/initialization/reload evidence. ``run``
requires that sealed preflight binding and a separately released training
stage before any dataset or old-weight read. config.training_pipeline binds a
design {path,sha256}, datasets[phase][train|development] with {path,seal_sha256,
input_audit_path,input_audit_sha256,input_protocol_sha256}, and optional
stop_after[phase][A|B]. Dataset self-seals never substitute for upstream audits.
The input protocol is the collection protocol, avoiding a circular hash with
the later training configuration that binds the completed dataset audit.

Only new output versions are written. This module does not capture episodes,
launch policy evaluation, calibrate, inspect heldout labels, or resume a partial
fit. A failed run keeps its files and charged updates; a retry needs a new version.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re

import numpy as np
import torch

from corrector.critic import FrozenSelector, STATE_KEYS, from_state
from corrector.guidance import FrozenObjective
from . import storage
from .protocol import TASKS, canonical_hash, require_stage_budget, seed_for, validate_protocol
from .training import (CANDIDATES, CHECKPOINTS, STAGES, canonical_features,
                       checkpoint_selection_metrics, checkpoint_state,
                       choose_checkpoint, configure_trainable, cpu_threads, fit_member,
                       fit_train_preprocessing, initialize_model, save_checkpoint,
                       stratified_episode_bootstrap)


INPUT_CHECKS = (
    'manifest_registration', 'source_seals', 'bank_seals', 'branch_seals',
    'budget_attempts', 'raw_command_mapping', 'suffix_pairing',
    'alias_equivalence', 'complete_labels', 'no_future_split_access',
    'scene_identity', 'replacement_chain',
)
PREFLIGHT_ROLE = 'native10_fit_preflight_zero_updates'


def _read(path):
    return json.loads(Path(path).read_text())


def _slot(row):
    return row.get('planned_slot_id', row['episode_id'])


def _checked_file(path, expected):
    path = Path(path).resolve()
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected) or storage.sha256(path) != expected:
        raise ValueError(f'File SHA mismatch: {path}')
    return path


def _new_directory(path):
    path = Path(path).resolve()
    if not path.is_relative_to(storage.ROOT.resolve()):
        raise ValueError('All pipeline outputs must be within the new workflow ROOT')
    path.mkdir(parents=True, exist_ok=False)
    return path


def training_code_files():
    """Explicit current implementation identity for preparation, never a release."""
    code=Path(__file__).resolve().parent
    names=('training_pipeline.py','training.py','dataset.py','artifact_loader.py','protocol.py',
           'storage.py','semantics.py','candidates13.py','scene_identity.py')
    paths=[code/name for name in names]
    paths += [storage.PACKAGE/'src/corrector'/name for name in ('critic.py','guidance.py','actions.py')]
    return {str(path.resolve()):storage.sha256(path) for path in paths}


def _specification(config, phase):
    specification=deepcopy(config['training_pipeline'])
    supplied=specification.get('code_files',{})
    required=training_code_files()
    if not set(required)<=set(supplied) or any(supplied[name]!=digest for name,digest in required.items()):
        raise ValueError('Training implementation differs from its frozen code binding')
    for name,digest in supplied.items():_checked_file(name,digest)
    design=_read(_checked_file(specification['design']['path'],specification['design']['sha256']))
    if design.get('schema_version')!=2 or design.get('task_id')!='native10-training-20260916':
        raise ValueError('Expected approved version2 training design')
    if config['budget']['training_update_total']!=51200:
        raise ValueError('Total optimizer-update hard budget must be 51200')
    collection=specification.get('collection',{})
    collection_config_path=_checked_file(collection['config_path'],collection['config_sha256'])
    collection_freeze_path=_checked_file(collection['freeze_path'],collection['freeze_sha256'])
    collection_config=_read(collection_config_path);collection_freeze=_read(collection_freeze_path)
    if (collection_freeze.get('files',{}).get(str(collection_config_path))!=collection['config_sha256']
            or collection_config['episode_manifest']!=config['episode_manifest']
            or any(binding['input_protocol_sha256']!=collection_config['analysis_approval']['protocol_sha256']
                   for binding in specification['datasets'][phase].values())):
        raise ValueError('Original collection freeze/manifest/input protocol differs from the training datasets')
    stops=specification.get('stop_after',{}).get(phase,{path:CHECKPOINTS[phase][-1] for path in ('A','B')})
    if set(stops)!={'A','B'} or any(type(value) is not int or value not in CHECKPOINTS[phase] for value in stops.values()):
        raise ValueError('Both A/B paths require registered checkpoint stops')
    if 4*sum(stops.values())>(19200 if phase=='round1' else 32000):
        raise ValueError('Phase update limit exceeded')
    identity=dict(phase=phase,manifest_sha256=canonical_hash(config['episode_manifest']),
                  seed_namespace=config['seed_namespace'],design=specification['design'],
                  dataset_bindings=specification['datasets'][phase],code_files=supplied,stop_after=stops,
                  collection=collection)
    return specification,design,identity


def _version(version):
    if not isinstance(version,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',version):
        raise ValueError('Register a safe explicit output version')
    return version


def _sealed_preflight(directory, expected_sha):
    directory=Path(directory).resolve()
    if not directory.is_relative_to((storage.ROOT/'fit_preflight').resolve()):
        raise ValueError('Only independent new-workflow fit-before artifacts are accepted')
    complete=_checked_file(directory/'complete.json',expected_sha)
    seal=_read(complete)
    if seal.get('status')!='complete':raise ValueError('Fit-before artifact is not complete')
    files=seal.get('files')
    actual={str(path.relative_to(directory)) for path in directory.rglob('*')
            if path.is_file() and path!=complete}
    if not isinstance(files,dict) or set(files)!=actual:
        raise ValueError('Fit-before sealed file list changed or is incomplete')
    for name,digest in files.items():
        path=(directory/name).resolve()
        if not path.is_relative_to(directory):raise ValueError('Fit-before artifact escaped its directory')
        _checked_file(path,digest)
    return seal


def _require_preflight(config,phase):
    validate_protocol(config,require_runnable=True)
    scope=phase+'_fit_preflight'
    ready=_read(config['analysis_ready']['path'])
    if scope not in ready['released_scope']:
        raise ValueError('Analysis READY has not released CPU fit-before scope: '+scope)
    if (config['budget']['stages'].get(scope)!={'simulator_attempts':0,'training_updates':0}
            or config['stage_release_scopes'].get(scope)!=scope):
        raise ValueError('Fit-before stage/scope must explicitly have zero simulator and optimizer budgets')
    release=ready.get(scope,{})
    collection=config['training_pipeline'].get('collection',{})
    if (release.get('stage')!=scope or release.get('scope')!=scope
            or release.get('simulator_attempts_limit')!=0 or release.get('optimizer_updates_limit')!=0
            or release.get('training_updates')!=0
            or release.get('input_config_sha256')!=collection.get('config_sha256')
            or release.get('input_freeze_sha256')!=collection.get('freeze_sha256')):
        raise ValueError('READY fit-before limits or collection binding differ from the frozen configuration')
    return scope


def _parameter_mask(model):
    return dict(parameters=[dict(name=name,shape=list(value.shape),numel=value.numel(),
        requires_grad=value.requires_grad,dtype=str(value.dtype)) for name,value in model.named_parameters()],
        buffers=[dict(name=name,shape=list(value.shape),numel=value.numel(),requires_grad=value.requires_grad,
            dtype=str(value.dtype)) for name,value in model.named_buffers()])


def _sampling(rows,config,phase,path,member):
    seed=seed_for('training_bootstrap',phase,path,member,namespace=config['seed_namespace'])
    return dict(bootstrap=stratified_episode_bootstrap(rows,seed=seed),
        batch_seed=seed_for('training_minibatches',phase,path,member,namespace=config['seed_namespace']))


def load_audited_dataset(binding, *, purpose, manifest):
    """Verify sealed pack, independently audited source chain, and current bytes."""
    from .dataset import load_saved_dataset
    directory = Path(binding['path']).resolve()
    if not directory.is_relative_to((storage.ROOT/'datasets').resolve()):
        raise ValueError('Only new-workflow datasets may enter this pipeline')
    _checked_file(directory/'complete.json', binding['seal_sha256'])
    audit_path = _checked_file(binding['input_audit_path'], binding['input_audit_sha256'])
    if not audit_path.is_relative_to(storage.ROOT.resolve()):
        raise ValueError('Input audit must be within the new workflow ROOT')
    audit = _read(audit_path)
    if (audit.get('schema') != 'native10_input_artifact_audit_v1' or audit.get('status') != 'passed'
            or audit.get('dataset_seal_sha256') != binding['seal_sha256']
            or audit.get('manifest_sha256') != canonical_hash(manifest)
            or audit.get('protocol_sha256') != binding['input_protocol_sha256']
            or audit.get('purpose') != purpose
            or any(audit.get('checks', {}).get(key) is not True for key in INPUT_CHECKS)):
        raise ValueError('Independent input-artifact audit is incomplete or unbound')
    artifacts = audit.get('artifacts', [])
    if not artifacts or len({item['path'] for item in artifacts}) != len(artifacts):
        raise ValueError('Audited evidence files must be explicit and unique')
    for item in artifacts:
        if item.get('role') not in ('source', 'bank', 'branch', 'budget_snapshot'):
            raise ValueError('Unknown input artifact role')
        path = Path(item['path']).resolve()
        if not path.is_relative_to(storage.ROOT.resolve()):
            raise ValueError('Input evidence must remain inside the new workflow ROOT')
        _checked_file(path, item['sha256'])
    if not {'source', 'budget_snapshot'} <= {item['role'] for item in artifacts}:
        raise ValueError('Source and immutable budget-snapshot evidence are required')
    packed = load_saved_dataset(directory, purpose=purpose, expected_manifest_sha256=canonical_hash(manifest))
    records = packed['metadata']['records']
    if audit.get('episode_ids') != [_slot(row) for row in records]:
        raise ValueError('Input audit does not cover every planned episode in order')
    if packed['rows'] and not {'bank', 'branch'} <= {item['role'] for item in artifacts}:
        raise ValueError('Reached groups need candidate-bank and physical-label evidence')
    if not packed['metadata'].get('complete_planned_selection_evidence'):
        raise ValueError('Technical missing outcomes block this complete pipeline; preserve records and resolve audit')
    packed['pipeline_binding'] = deepcopy(binding)
    return packed


def validate_phase_datasets(train, development, manifest, phase):
    """Check coverage before feature fitting or old-weight import; no label filters."""
    if phase not in STAGES:
        raise ValueError('Only round1/final training phases are approved')
    rounds = {1} if phase == 'round1' else {1, 2}
    primary = [row for row in manifest if row.get('replacement_of') is None]
    registry = {row['episode_id']: row for row in manifest}
    if len(registry) != len(manifest):
        raise ValueError('Duplicate manifest episode identity')
    expected = [row for row in primary if row['split'] == 'train' and row.get('round') in rounds]
    expected_dev = [row for row in primary if row['split'] == 'development']
    if len(expected) != (300 if phase == 'round1' else 600) or len(expected_dev) != 100:
        raise ValueError('Registered training/development planned counts changed')
    for registered, count in ((expected, len(expected)//5), (expected_dev, 20)):
        if Counter(row['task'] for row in registered) != Counter({task: count for task in TASKS}):
            raise ValueError('Planned sources must retain the registered five-task balance')
    for packed, registered, purpose in ((train, expected, 'train'), (development, expected_dev, 'development')):
        meta = packed['metadata']
        ids = [row['episode_id'] for row in registered]
        if (meta.get('purpose') != purpose or meta.get('manifest_sha256') != canonical_hash(manifest)
                or [_slot(row) for row in meta['records']] != ids
                or meta.get('planned_episode_count') != len(ids)
                or not meta.get('complete_planned_selection_evidence')):
            raise ValueError('Dataset lost/replaced planned sources or has incomplete outcomes')
        expected_rows = {row['episode_id']: row for row in registered}
        records_by_actual = {row['episode_id']: row for row in meta['records']}
        if (len(records_by_actual) != len(meta['records'])
                or {row['episode_id'] for row in packed['rows']}
                != {row['episode_id'] for row in meta['records'] if row.get('critic_eligible') is True}):
            raise ValueError('Complete rows and unique actual source records disagree')
        for row in packed['rows']:
            actual = registry.get(row['episode_id'])
            slot = _slot(row)
            base = expected_rows.get(slot)
            if (actual is None or base is None
                    or {key: value for key, value in row.items() if key != 'planned_slot_id'}
                    != {key: value for key, value in actual.items() if key != 'planned_slot_id'}
                    or _slot(records_by_actual[row['episode_id']]) != slot
                    or (row['episode_id'] != slot and actual.get('replacement_of') != slot)
                    or (row['episode_id'] == slot and actual.get('replacement_of') is not None)
                    or any(actual.get(key) != base.get(key) for key in ('task', 'split', 'round'))):
                raise ValueError('Complete dataset row differs from registered episode/round or replacement slot')
        if len({_slot(row) for row in packed['rows']}) != len(packed['rows']):
            raise ValueError('Multiple actual episodes occupy one planned source slot')
    if set(row['episode_id'] for row in train['rows']) & set(row['episode_id'] for row in development['rows']):
        raise ValueError('Training and development source leakage')
    if len(train['rows']) <= 16:
        raise ValueError('Too few unique valid training sources for visual PCA16')
    return dict(train_planned=len(expected), train_reached=len(train['rows']),
                development_planned=100, development_reached=len(development['rows']),
                rounds=sorted(rounds), episode_split_checked=True)


def load_old_members(package, import_spec):
    """Read-only old members; check ranking and each file SHA before torch.load."""
    package = Path(package).resolve()
    ranking_path = (package/import_spec['ranking']).resolve()
    if not ranking_path.is_relative_to(package):
        raise ValueError('Old ranking path escapes its package')
    _checked_file(ranking_path, import_spec['ranking_sha256'])
    ranking = _read(ranking_path)
    expected_files = import_spec['files']
    if ranking.get('horizon') != 10 or len(ranking.get('model_hashes', {})) != 4 or len(expected_files) != 4:
        raise ValueError('Exactly four old ten-step members are required')
    states, members = [], []
    for member, digest in sorted(ranking['model_hashes'].items(), key=lambda item: int(item[0])):
        relative = str((ranking_path.parent/'models'/'refit'/f'member_{member}'/'selected.pt').relative_to(package))
        if expected_files.get(relative) != digest:
            raise ValueError('Old ranking and design file hashes disagree')
        path = (package/relative).resolve()
        if not path.is_relative_to(package):
            raise ValueError('Old checkpoint path escapes its package')
        _checked_file(path, digest)
        states.append(torch.load(path, weights_only=True, map_location='cpu'))
        members.append(dict(member=str(member), path=str(path), sha256=digest))
    return states, dict(ranking_sha256=import_spec['ranking_sha256'], members=members, read_only=True)


def frozen_models(states):
    if len(states) != 4:
        raise ValueError('Exactly four members required')
    with cpu_threads():
        return [from_state({key: value.detach().cpu().clone() for key, value in state.items()}).eval().requires_grad_(False)
                for state in states]


def predict_member(model, arrays):
    """Canonical source at a time; each candidate uses [detached a0,candidate]."""
    actions = torch.as_tensor(arrays['actions'], dtype=torch.float32)
    if actions.device.type != 'cpu' or actions.ndim != 4 or actions.shape[1:] != (13, 10, 4):
        raise ValueError('Expected thirteen CPU critic candidates per source')
    if not bool(torch.isfinite(actions).all()) or bool((actions.abs() > 1).any()):
        raise ValueError('Invalid bounded critic commands')
    if model.training or any(p.requires_grad or p.grad is not None for p in model.parameters()):
        raise ValueError('Predict with a frozen evaluation copy')
    if not len(actions):
        return np.empty((0, 13), np.float32)
    features = canonical_features(model, arrays)
    result = torch.empty(len(actions), 13)
    with cpu_threads(), torch.no_grad():
        for source in range(len(actions)):
            a0 = actions[source, 0].detach()
            for slot in range(13):
                pair = torch.stack([a0, actions[source, slot]])[None]
                probability = model(features[source:source+1], pair).sigmoid()[0]
                result[source, slot] = probability[0 if slot == 0 else 1]
    return result.numpy()


def development_selection(packed, member_probabilities):
    """Scatter reached predictions into the complete, frozen planned denominator."""
    meta, arrays = packed['metadata'], packed['arrays']
    if meta.get('purpose') != 'development' or not meta.get('complete_planned_selection_evidence'):
        raise ValueError('Complete planned development evidence is required')
    probabilities = np.asarray(member_probabilities)
    rows = packed['rows']
    if probabilities.shape != (4, len(rows), 13):
        raise ValueError('Four member predictions must follow complete-group row order')
    index = {row['episode_id']: i for i, row in enumerate(rows)}
    if len(index) != len(rows):
        raise ValueError('Duplicate development episode')
    records = meta['records'];n = len(records)
    if (len({row['episode_id'] for row in records}) != n or len({_slot(row) for row in records}) != n
            or n != meta['planned_episode_count']):
        raise ValueError('Invalid full-planned development record set')
    full_p = np.full((4, n, 13), np.nan, np.float32)
    outcomes = np.empty((n, 13, 4), np.bool_)
    weights = np.zeros((n, 13), np.float32);reached = np.zeros(n, np.bool_)
    for i, record in enumerate(records):
        if record.get('critic_eligible') is True:
            j = index.pop(record['episode_id'])
            if record.get('status') != 'complete' or not record.get('control_complete'):
                raise ValueError('Incomplete development source/control labels')
            full_p[:, i] = probabilities[:, j]
            outcomes[i] = arrays['outcomes'][j]
            weights[i] = arrays['gain_weights'][j];reached[i] = True
        elif (record.get('status') == 'no_cut' and record.get('full_episode_outcome_available') is True
              and isinstance(record.get('native10_outcome'), (bool, np.bool_))):
            outcomes[i] = record['native10_outcome']
        else:
            raise ValueError('Unknown technical outcomes cannot be zero-imputed')
    if index:
        raise ValueError('Reached prediction row is absent from planned development records')
    metrics = checkpoint_selection_metrics(full_p, outcomes, reached_mask=reached, gain_weights=weights)
    metrics['episode_ids'] = [row['episode_id'] for row in records]
    metrics['planned_slot_ids'] = [_slot(row) for row in records]
    metrics['selected_candidates'] = [CANDIDATES[slot] for slot in metrics['selected_slots']]
    return metrics, dict(member_probabilities=full_p, outcomes=outcomes, reached_mask=reached, gain_weights=weights)


def export_ensemble(states, directory, *, provenance):
    """New-only four-member plain state_dict export loadable by FrozenSelector."""
    if len(states) != 4:
        raise ValueError('Export exactly four members')
    directory = _new_directory(directory)
    models = frozen_models(states)
    hashes = {}
    for member, model in enumerate(models):
        saved = save_checkpoint(model, directory/'models'/'refit'/f'member_{member}'/'selected.pt')
        hashes[str(member)] = saved['sha256']
    storage.dump(directory/'ranking.json', dict(horizon=10, model_hashes=hashes,
                 candidate_order=list(CANDIDATES), a0_slot=0, provenance=provenance))
    storage.dump(directory/'config.json', dict(horizon=10, members=4, provenance=provenance,
                 candidate_probability_path='singleton source; two slots [a0,candidate]',
                 offline_ensemble_summary='float64 mean of member float32 probabilities'))
    storage.seal(directory, role='four_member_critic_export', model_hashes=hashes)
    selector = FrozenSelector(directory)
    selector.verify(check_files=True)
    return selector


def _member_gradient(model, features, a0, candidate):
    leaf = torch.as_tensor(candidate).detach().float().clone().requires_grad_(True)
    pair = torch.stack([torch.as_tensor(a0).detach().float(), leaf])[None]
    with cpu_threads(), torch.enable_grad():
        p = model(features, pair).sigmoid()[0]
        return torch.autograd.grad(p[1]-p[0], leaf)[0].detach()


def audit_reload(models, selector, arrays, rows):
    """Actual singleton FrozenObjective cache, probabilities and action gradients.

    Used before fit on every unique reached training source, and after selected
    export on every reached development source. Compares original/reloaded
    arithmetic bit-for-bit at identical shapes; no tolerance is relaxed. This
    audit has not passed on real data merely because synthetic tests pass.
    """
    if len(models) != 4 or len(rows) != len(arrays['actions']):
        raise ValueError('Audit source/member shape changed')
    if not len(rows):
        selector.verify(check_files=True)
        return dict(status='passed', source_count=0, vacuous_no_reached_sources=True,
                    real_data_claim_requires_real_input_provenance=True)
    old_cache = [canonical_features(model, arrays) for model in models]
    new_cache = [canonical_features(model, arrays) for model in selector.models]
    before_p = np.stack([predict_member(model, arrays) for model in models])
    after_p = np.stack([predict_member(model, arrays) for model in selector.models])
    if not np.array_equal(before_p, after_p):
        raise ValueError('Saved/reloaded member probabilities changed')
    summary_rounding_max=0.
    for source, row in enumerate(rows):
        observed = {key: arrays[key][source] for key in STATE_KEYS}
        actions = arrays['actions'][source]
        old = FrozenObjective(observed, actions[0], models=models)
        new = FrozenObjective(observed, actions[0], selector=selector)
        if old.evaluate(actions[0])['mean_gain']!=0 or new.evaluate(actions[0])['mean_gain']!=0:
            raise ValueError('Designated a0 does not retain exact zero advantage')
        for member in range(4):
            expected = old_cache[member][source:source+1]
            if not (torch.equal(expected, new_cache[member][source:source+1])
                    and torch.equal(expected, old.features[member])
                    and torch.equal(expected, new.features[member])):
                raise ValueError(f'Canonical feature/FrozenObjective cache differs: {row["episode_id"]}')
        for slot in range(13):
            previous = np.asarray(old.evaluate(actions[slot])['member_probabilities'], np.float32)
            evaluated=new.evaluate(actions[slot])
            reloaded = np.asarray(evaluated['member_probabilities'], np.float32)
            selected = previous[:, 0 if slot == 0 else 1]
            if not np.array_equal(previous, reloaded) or not np.array_equal(selected, before_p[:, source, slot]):
                raise ValueError('Canonical checkpoint prediction/FrozenObjective probability changed')
            offline_gain=float(before_p[:,source,slot].astype(np.float64).mean()-before_p[:,source,0].astype(np.float64).mean())
            summary_rounding_max=max(summary_rounding_max,abs(offline_gain-evaluated['mean_gain']))
        for slot in (0, 11):  # predetermined a0 and post; never select by observed outcomes
            first, _ = old.gradient(actions[slot]);second, _ = new.gradient(actions[slot])
            if not torch.equal(first, second):
                raise ValueError('Reloaded FrozenObjective action gradient changed')
            for member in range(4):
                first = _member_gradient(models[member], old.features[member], actions[0], actions[slot])
                second = _member_gradient(selector.models[member], new.features[member], actions[0], actions[slot])
                if not torch.isfinite(first).all() or not torch.equal(first, second):
                    raise ValueError('Reloaded member action gradient changed')
        old.verify();new.verify()
    selector.verify(check_files=True)
    return dict(status='passed', source_count=len(rows), episode_ids=[row['episode_id'] for row in rows],
                feature_cache_bit_exact=True, thirteen_candidate_member_probability_bit_exact=True,
                gradient_slots=[0, 11], member_and_ensemble_gradient_bit_exact=True,
                members_checked=4,a0_anchor_exactly_zero=True,state_and_anchor_immutable=True,
                input_action_representation='bounded float32 [13,10,4]; designated slot0 a0 detached',
                ensemble_offline_float64_vs_online_float32_max_gain_difference=summary_rounding_max,
                ensemble_summary_difference_is_report_only=True,
                probability_comparison='member float32; same singleton two-slot arithmetic',
                real_data_claim_requires_real_input_provenance=True)


def preflight(config, *, phase, version):
    """Separately released train-only PCA and A+B audit, with zero optimizer calls.

    The explicit scope is ``round1_fit_preflight`` or ``final_fit_preflight``.
    It is not a simulator or optimizer budget and cannot release ``run``. The
    later training configuration must bind this complete artifact's seal SHA.
    """
    if phase not in STAGES:raise ValueError('Only round1/final are registered')
    scope=_require_preflight(config,phase)
    _version(version)
    specification,design,identity=_specification(config,phase)
    directory=_new_directory(storage.ROOT/'fit_preflight'/phase/version)
    storage.dump(directory/'config.json',config)
    registration=dict(**identity,role=PREFLIGHT_ROLE,version=version,
        preflight_config_sha256=storage.sha256(directory/'config.json'),
        preflight_protocol_sha256=config['analysis_approval']['protocol_sha256'],
        preflight_ready=deepcopy(config['analysis_ready']),required_scope=scope,
        optimizer_updates=0,simulator_calls=0,model_fit_complete=False,
        numeric_runtime=dict(torch=str(torch.__version__),numpy=np.__version__,device='cpu',dtype='float32',threads=2))
    storage.dump(directory/'registration.json',registration)
    try:
        binding=identity['dataset_bindings']
        train=load_audited_dataset(binding['train'],purpose='train',manifest=config['episode_manifest'])
        dev=load_audited_dataset(binding['development'],purpose='development',manifest=config['episode_manifest'])
        coverage=validate_phase_datasets(train,dev,config['episode_manifest'],phase)
        states,imported=load_old_members(storage.PACKAGE,design['old_weight_import'])
        if any(not torch.equal(states[0][key],state[key]) for state in states for key in ('norm_mean','norm_std')):
            raise ValueError('Old visual normalizers differ across members')
        prep,pca_audit=fit_train_preprocessing(train['arrays'],train['rows'],range(len(train['rows'])),
            norm_mean=states[0]['norm_mean'],norm_std=states[0]['norm_std'])
        storage.dump(directory/'pca_fit_audit.json',pca_audit)
        initial_assets={};audits={};seeds={};sampling={};masks={}
        for path in ('A','B'):
            seeds[path]=[seed_for('training_initialization',phase,path,member,namespace=config['seed_namespace'])
                         for member in range(4)]
            models=[initialize_model(path,seed=seeds[path][member],
                **({'warm_start_state':states[member]} if path=='A' else {'preprocessing':prep})) for member in range(4)]
            sampling[path]=[_sampling(train['rows'],config,phase,path,member) for member in range(4)]
            masks[path]=[_parameter_mask(model) for model in models]
            initial_states=[checkpoint_state(model) for model in models]
            assets=directory/path/'initial'
            selector=export_ensemble(initial_states,assets,provenance=dict(registration,path=path,
                initialization_only=True,coverage=coverage,old_import=imported))
            audits[path]=audit_reload(frozen_models(initial_states),selector,train['arrays'],train['rows'])
            if audits[path].get('status')!='passed':raise ValueError('Fit-before numerical audit did not pass')
            storage.dump(directory/path/'reload_audit.json',audits[path])
            initial_assets[path]=dict(path=str(assets),seal_sha256=storage.sha256(assets/'complete.json'),
                                     model_hashes=selector.ranking['model_hashes'])
        storage.dump(directory/'sampling.json',sampling)
        storage.dump(directory/'trainable_masks.json',masks)
        result=dict(**registration,status='passed',coverage=coverage,old_import=imported,
                    pca_audit=pca_audit,initial_assets=initial_assets,initialization_seeds=seeds,
                    reload_audits=audits,both_paths_checked_before_any_optimizer_update=True,
                    pca_fit_audit_sha256=storage.sha256(directory/'pca_fit_audit.json'),
                    sampling_sha256=storage.sha256(directory/'sampling.json'),
                    trainable_masks_sha256=storage.sha256(directory/'trainable_masks.json'),
                    pca_fitting_performed=True,optimizer_model_fitting_performed=False,
                    preregistered_numerical_tolerances=dict(canonical_features='bit_exact',
                        member_probabilities='bit_exact',member_and_ensemble_gradients='bit_exact'),
                    training_released_by_this_artifact=False)
        storage.dump(directory/'result.json',result)
        storage.seal(directory,role=PREFLIGHT_ROLE,phase=phase,optimizer_updates=0,model_fit_complete=False)
        return dict(path=str(directory),seal_sha256=storage.sha256(directory/'complete.json'),
                    status='passed',phase=phase,optimizer_updates=0)
    except Exception as error:
        storage.dump(directory/'failure.json',dict(status='failed',role=PREFLIGHT_ROLE,
            error=repr(error),phase=phase,optimizer_updates=0,simulator_calls=0,model_fit_complete=False))
        raise


def load_preflight(config, *, phase, identity, coverage, train_rows):
    """Require both sealed initial ensembles before any optimizer is created."""
    binding=config['training_pipeline'].get('preflight',{}).get(phase)
    if not isinstance(binding,dict):raise ValueError('A complete independent fit-before binding is required')
    directory=Path(binding['path']).resolve()
    seal=_sealed_preflight(directory,binding['seal_sha256'])
    result=_read(directory/'result.json')
    prefit_config=_read(_checked_file(directory/'config.json',result.get('preflight_config_sha256')))
    _require_preflight(prefit_config,phase)
    _,_,saved_identity=_specification(prefit_config,phase)
    if (directory.parent!=storage.ROOT.resolve()/'fit_preflight'/phase
            or seal.get('role')!=PREFLIGHT_ROLE or seal.get('phase')!=phase
            or seal.get('optimizer_updates')!=0 or seal.get('model_fit_complete') is not False
            or result.get('role')!=PREFLIGHT_ROLE or result.get('status')!='passed'
            or result.get('optimizer_updates')!=0 or result.get('simulator_calls')!=0
            or result.get('model_fit_complete') is not False
            or result.get('both_paths_checked_before_any_optimizer_update') is not True
            or any(result.get(key)!=value for key,value in identity.items())
            or saved_identity!=identity
            or result.get('preflight_protocol_sha256')!=prefit_config['analysis_approval']['protocol_sha256']
            or result.get('preflight_ready')!=prefit_config['analysis_ready']
            or result.get('coverage')!=coverage):
        raise ValueError('Fit-before evidence is failed, incomplete, or differs from frozen training inputs')
    expected_runtime=dict(torch=str(torch.__version__),numpy=np.__version__,device='cpu',dtype='float32',threads=2)
    if result.get('numeric_runtime')!=expected_runtime:
        raise ValueError('Numerical runtime changed after fit-before audit')
    sampling=_read(_checked_file(directory/'sampling.json',result.get('sampling_sha256')))
    masks=_read(_checked_file(directory/'trainable_masks.json',result.get('trainable_masks_sha256')))
    saved_pca=_read(_checked_file(directory/'pca_fit_audit.json',result.get('pca_fit_audit_sha256')))
    if saved_pca!=result.get('pca_audit') or set(sampling)!={'A','B'} or set(masks)!={'A','B'}:
        raise ValueError('Fit-before sampling, masks or PCA diagnostic evidence is incomplete')
    if set(result.get('initial_assets',{}))!={'A','B'} or set(result.get('reload_audits',{}))!={'A','B'}:
        raise ValueError('Both A/B initial ensembles and numerical audits are required')
    ids=[row['episode_id'] for row in train_rows]
    pca=result.get('pca_audit',{})
    if (len(ids)!=coverage['train_reached'] or pca.get('fit_episode_ids')!=ids
            or pca.get('fit_source_count')!=len(ids) or pca.get('train_only') is not True
            or pca.get('bootstrap_duplicates_used') is not False
            or pca.get('visual_dimension')!=16 or pca.get('language_dimension')!=8):
        raise ValueError('Fit-before PCA evidence does not cover the unique current-stage train sources')
    states={}
    for path in ('A','B'):
        expected_sampling=[_sampling(train_rows,config,phase,path,member) for member in range(4)]
        if sampling[path]!=expected_sampling:
            raise ValueError('Fit-before source bootstrap/minibatch identity changed before training')
        audit=result['reload_audits'][path]
        if (audit.get('status')!='passed' or audit.get('source_count')!=len(ids) or audit.get('episode_ids')!=ids
                or any(audit.get(key) is not True for key in ('feature_cache_bit_exact',
                    'thirteen_candidate_member_probability_bit_exact','member_and_ensemble_gradient_bit_exact'))
                or audit.get('gradient_slots')!=[0,11]):
            raise ValueError('Fit-before numerical audit did not cover every training source')
        asset=result['initial_assets'][path]
        assets=Path(asset['path']).resolve()
        if assets!=directory/path/'initial':raise ValueError('Initial ensemble escaped its sealed preflight version')
        _checked_file(assets/'complete.json',asset['seal_sha256'])
        selector=FrozenSelector(assets)
        selector.verify(check_files=True)
        if selector.ranking['model_hashes']!=asset['model_hashes']:
            raise ValueError('Initial model hashes differ from fit-before evidence')
        states[path]=[checkpoint_state(model) for model in selector.models]
        owned=[from_state(state) for state in states[path]]
        for model in owned:configure_trainable(model,path)
        if masks[path]!=[_parameter_mask(model) for model in owned]:
            raise ValueError('Fit-before frozen/trainable parameter masks differ from training')
    result['sampling']=sampling
    return result,states


def run(config, ledger, *, phase, version):
    """Train two paths x four members, select one ensemble, and export it safely."""
    if phase not in STAGES:
        raise ValueError('Only round1/final are registered')
    require_stage_budget(config, STAGES[phase], resource='training_updates')
    _version(version)
    specification,design,identity=_specification(config,phase)
    stops=identity['stop_after']
    binding = specification['datasets'][phase]
    train = load_audited_dataset(binding['train'], purpose='train', manifest=config['episode_manifest'])
    dev = load_audited_dataset(binding['development'], purpose='development', manifest=config['episode_manifest'])
    coverage = validate_phase_datasets(train, dev, config['episode_manifest'], phase)
    prefit,initial_by_path=load_preflight(config,phase=phase,identity=identity,coverage=coverage,train_rows=train['rows'])
    directory = _new_directory(storage.ROOT/'models'/phase/version)
    provenance = dict(phase=phase, version=version, config_protocol_sha256=config['analysis_approval']['protocol_sha256'],
                      design=specification['design'], dataset_bindings=binding, coverage=coverage,
                      old_import=prefit['old_import'], preflight_binding=specification['preflight'][phase],
                      preflight_protocol_sha256=prefit['preflight_protocol_sha256'],
                      real_policy_evaluation_performed=False)
    storage.dump(directory/'registration.json', dict(**provenance, stop_after=stops))
    selection_records, checkpoint_paths, update_attempts = [], {}, []
    class VersionLedger:
        def reserve(self, stage, kind, identity, **kwargs):
            return ledger.reserve(stage, kind, f'{version}:{identity}', **kwargs)
    version_ledger = VersionLedger()
    try:
        for path in ('A', 'B'):
            init_seeds=prefit['initialization_seeds'][path]
            models=[from_state(state) for state in initial_by_path[path]]
            for model in models:
                model._native10_training_path=path
                configure_trainable(model,path)
            predictions = {step: [] for step in CHECKPOINTS[phase] if step <= stops[path]}
            for member, model in enumerate(models):
                member_dir = directory/path/f'member_{member}'
                def save_step(step, state, metrics):
                    owned = from_state(state).eval().requires_grad_(False)
                    checkpoint = save_checkpoint(owned, member_dir/f'step_{step}'/'selected.pt')
                    checkpoint_paths[(path, member, step)] = checkpoint
                    prediction = predict_member(owned, dev['arrays'])
                    predictions[step].append(prediction)
                    storage.arrays(member_dir/f'step_{step}'/'development_predictions.npz', probabilities=prediction)
                    storage.dump(member_dir/f'step_{step}'/'metadata.json', dict(checkpoint=checkpoint,
                                 last_minibatch=metrics, init_seed=init_seeds[member], dataset_binding=binding['development']))
                fitted = fit_member(config, version_ledger, phase=phase, path=path, member=member,
                    model=model, features=canonical_features(model, train['arrays']),
                    data=dict(rows=train['rows'], **train['arrays']), stop_after=stops[path], on_checkpoint=save_step)
                expected_sampling=prefit['sampling'][path][member]
                if (fitted.get('bootstrap')!=expected_sampling['bootstrap']
                        or fitted.get('batch_seed')!=expected_sampling['batch_seed']):
                    raise ValueError('Training used a different source bootstrap/minibatch seed than the sealed preflight')
                attempts = fitted.get('attempt_numbers', [])
                if (fitted.get('updates') != stops[path] or len(attempts) != stops[path]
                        or len(set(attempts)) != len(attempts) or set(attempts) & set(update_attempts)):
                    raise ValueError('Fit update count/unique ledger references do not match the registered stop')
                update_attempts.extend(attempts)
                fitted.pop('checkpoints')
                storage.dump(member_dir/'fit.json', fitted)
            for step, member_p in predictions.items():
                metrics, full = development_selection(dev, np.stack(member_p))
                record = dict(path=path, step=step, phase=phase, dataset_sha256=binding['development']['seal_sha256'], metrics=metrics)
                selection_records.append(record)
                storage.arrays(directory/path/f'development_step_{step}.npz', **full)
                storage.dump(directory/path/f'development_step_{step}.json', record)
        chosen = choose_checkpoint(selection_records)
        selected_states = []
        for member in range(4):
            checkpoint = checkpoint_paths[(chosen['path'], member, chosen['step'])]
            _checked_file(checkpoint['path'], checkpoint['sha256'])
            selected_states.append(torch.load(checkpoint['path'], weights_only=True, map_location='cpu'))
        selected = export_ensemble(selected_states, directory/'selected', provenance=dict(provenance, selection=chosen))
        reload_audit = audit_reload(frozen_models(selected_states), selected, dev['arrays'], dev['rows'])
        reload_metrics, _ = development_selection(dev, np.stack([predict_member(model, dev['arrays']) for model in selected.models]))
        if reload_metrics != chosen['metrics']:
            raise ValueError('Exported ensemble fails to reproduce selected development ranking/metrics')
        storage.dump(directory/'selected_reload_audit.json', reload_audit)
        result = dict(status='complete', **provenance, selection=chosen, compared_checkpoints=selection_records,
                      selected_assets=str(directory/'selected'), model_hashes=selected.ranking['model_hashes'],
                      optimizer_updates=len(update_attempts), optimizer_attempt_numbers=update_attempts,
                      independent_validation_success=False,
                      next_required='Freeze selected critic, then exactly one registered five-arm development rollout set.')
        storage.dump(directory/'result.json', result)
        storage.seal(directory, phase=phase, role='native10_two_path_training', model_hashes=selected.ranking['model_hashes'])
        return result
    except Exception as error:
        storage.dump(directory/'failure.json', dict(status='failed', error=repr(error), counted_updates_not_refunded=True))
        raise


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('preflight','run'))
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--phase',choices=tuple(STAGES),required=True)
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    config=_read(args.config)
    if args.action=='preflight':
        result=preflight(config,phase=args.phase,version=args.version)
    else:
        result=run(config,storage.AttemptLedger(config),phase=args.phase,version=args.version)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
