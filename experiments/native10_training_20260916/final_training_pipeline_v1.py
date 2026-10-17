"""Cross-protocol final preflight and fit; all execution needs its own READY.

Only scientific functions are reused from the first pipeline. Its single-
collection specification, preflight gate and initialization loader are never
called. Importing this module neither reads a dataset nor creates a model.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
import torch

from corrector.critic import FrozenSelector, STATE_KEYS, TenStepCritic, from_state, observed_features
from . import storage, training_pipeline as core
from .final_input_bundle_v1 import load_bundle
from .protocol import canonical_hash, seed_for

PHASE = 'final'
ROLE = 'native10_final_fit_preflight_zero_updates'
SCHEMA = 'native10_final_training_pipeline_v1'
NUMERICAL_DECISION_SHA = '3e556bad66cff0105c243b841cd24b619efdcc1c681bbf38b41bb0b71888cb1a'
NUMERIC_CONTRACT = 'canonical_strict_passed_dense_reported'


def _read(path):
    return json.loads(Path(path).read_text())


def pipeline_code_files():
    """All executable input/numeric dependencies, including the new entrypoints."""
    files = core.training_code_files()
    names = ('final_training_pipeline_v1.py', 'final_input_bundle_v1.py',
             'final_fit_protocol_v1.py', 'final_fit_runner_v1.py', 'final_prepare_v1.py')
    for name in names:
        path = Path(__file__).parent/name
        files[str(path.resolve())] = storage.sha256(path)
    return files


def _validate_specification(config, mode):
    from .final_fit_protocol_v1 import validate_specification
    specification, design, identity = validate_specification(config, mode=mode)
    required = pipeline_code_files()
    supplied = specification['code_files']
    if not set(required) <= set(supplied) or any(supplied[p] != h for p,h in required.items()):
        raise ValueError('Actual cross-protocol/numerical implementation is not frozen')
    if specification.get('stop_after') != {'A':4000,'B':4000}:
        raise ValueError('Final paths must retain the fixed 4000-step cap/checkpoint schedule')
    if specification.get('documents',{}).get('numerical_decision',{}).get('sha256')!=NUMERICAL_DECISION_SHA:
        raise ValueError('Final numerical decision is not bound in the specification')
    if specification.get('numeric_runtime')!=_runtime():
        raise ValueError('Actual numeric runtime differs from frozen final specification')
    return specification, design, identity


def _inputs(config, mode):
    specification, design, identity = _validate_specification(config, mode)
    bundle = load_bundle(specification['input_bundle'])
    if (bundle['verification']['bundle_identity'] != specification['input_bundle']
            or bundle['metadata']['sources'] != specification['source_bindings']
            or bundle['manifest'] != config['episode_manifest']
            or canonical_hash(bundle['manifest']) != specification['manifest_sha256']
            or canonical_hash(bundle['bundle_manifest']['feature_contract']) != specification['feature_contract_sha256']):
        raise ValueError('Verified bundle differs from the frozen final input identity')
    coverage = core.validate_phase_datasets(bundle['train'],bundle['development'],bundle['manifest'],PHASE)
    return specification, design, identity, bundle, coverage


def _runtime():
    from .final_fit_protocol_v1 import numeric_runtime
    result=numeric_runtime()
    result.update(torch=str(torch.__version__),numpy=np.__version__,python=sys.version,
                  executable=str(Path(sys.executable).resolve()),device='cpu',
                  dtype=str(torch.get_default_dtype()).removeprefix('torch.'),threads=2)
    return result


def _source_sets(bundle):
    result = {}
    for purpose in ('train','development'):
        pack = bundle[purpose]
        result[purpose] = dict(effective_episode_ids=[r['episode_id'] for r in pack['rows']],
            effective_planned_slot_ids=[r.get('planned_slot_id',r['episode_id']) for r in pack['rows']],
            planned_slot_ids=[r.get('planned_slot_id',r['episode_id']) for r in pack['metadata']['records']],
            effective_per_task=dict(Counter(r['task'] for r in pack['rows'])),
            planned_count=pack['metadata']['planned_episode_count'],effective_count=len(pack['rows']),
            no_cut_count=sum(r['status']=='no_cut' for r in pack['metadata']['records']))
    return result


def _sampling(rows, config, path, member):
    seed = seed_for('training_bootstrap',PHASE,path,member,namespace=config['seed_namespace'])
    result=dict(bootstrap=core.stratified_episode_bootstrap(rows,seed=seed),
                batch_seed=seed_for('training_minibatches',PHASE,path,member,namespace=config['seed_namespace']))
    plan=_minibatches(result)
    result.update(minibatch_plan_sha256=hashlib.sha256(plan.tobytes()).hexdigest(),
                  minibatch_plan_shape=list(plan.shape),minibatch_plan_dtype=str(plan.dtype))
    return result


def _minibatches(sample):
    # Exact existing fit_member draw order, not a new RNG implementation.
    pool=np.asarray(sample['bootstrap']['indices'],dtype=np.int64)
    if not len(pool):raise ValueError('Final fit needs effective train sources')
    rng=np.random.default_rng(sample['batch_seed'])
    return np.stack([pool[rng.integers(0,len(pool),32)] for _ in range(4000)])


def _difference(first, second):
    if first.shape != second.shape or first.dtype != second.dtype:
        raise ValueError('Batch diagnostic changed tensor shape/dtype')
    finite = bool(torch.isfinite(first).all() and torch.isfinite(second).all())
    if not finite:
        raise ValueError('Nonfinite batch/singleton diagnostic')
    reference,comparison=first.double(),second.double()
    delta=reference-comparison
    if not bool(torch.isfinite(delta).all()):raise ValueError('Nonfinite dense diagnostic difference')
    maximum=lambda value:float(value.abs().max()) if value.numel() else 0.
    rms=lambda value:float(value.square().mean().sqrt()) if value.numel() else 0.
    return dict(exact_equal=torch.equal(first,second),finite=True,shape=list(first.shape),
                mismatched_elements=int((first!=second).sum()),
                max_abs_difference=maximum(delta),reference_max_abs=maximum(reference),reference_rms=rms(reference),
                comparison_max_abs=maximum(comparison),comparison_rms=rms(comparison),
                measurement_dtype='float64; computation remains float32',relative_error_reported=False)


def _fingerprint(values):
    digest=hashlib.sha256()
    for name,value in sorted(values.items()):
        tensor=torch.as_tensor(value).detach()
        if tensor.device.type!='cpu':raise ValueError('Numerical diagnostics require CPU tensors')
        array=tensor.contiguous().numpy()
        digest.update(name.encode());digest.update(str(array.dtype).encode());digest.update(str(array.shape).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def batch_singleton_diagnostics(models, arrays, rows):
    """Report raw batch differences without allclose or tolerance relaxation.

    Every probability call preserves two candidate slots [a0,candidate]. A
    nonexact result is reported under the explicit numerical decision; it is
    never substituted for canonical singleton production computation.
    """
    if len(models)!=4 or len(rows)!=len(arrays['actions']):
        raise ValueError('Batch audit needs all four members and the exact source set')
    ids = [r['episode_id'] for r in rows]
    if not ids:
        return dict(status='reported_exact',source_count=0,episode_ids=[],members=[],
                    vacuous_no_reached_sources=True,all_bit_exact=True,diagnostics_complete=True,
                    numeric_contract=NUMERIC_CONTRACT,decision_sha256=NUMERICAL_DECISION_SHA)
    states = {key:torch.as_tensor(arrays[key]).detach() for key in STATE_KEYS}
    actions = torch.as_tensor(arrays['actions']).detach().float()
    if (actions.shape!=(len(rows),13,10,4) or not bool(torch.isfinite(actions).all())
            or bool((actions.abs()>1).any()) or len(ids)!=len(set(ids))):
        raise ValueError('Dense audit actions/source identity changed')
    before_inputs=_fingerprint(dict(states,actions=actions))
    before_models=[_fingerprint(model.state_dict()) for model in models]
    versions=[(value,value._version) for model in models for value in list(model.parameters())+list(model.buffers())]
    for model in models:
        if (type(model) is not TenStepCritic or any(type(layer) not in (torch.nn.Sequential,torch.nn.Linear,torch.nn.SiLU)
                for layer in list(model.modules())[1:])):
            raise ValueError('Only frozen source-independent Linear/SiLU critic structure is approved')
        if any(v.device.type!='cpu' or v.dtype!=torch.float32 for v in list(model.parameters())+list(model.buffers())):
            raise ValueError('Model dtype/device drifted from the frozen float32 CPU contract')
    records,caches,batch_features = [],[],[]
    with core.cpu_threads(),torch.no_grad():
        for member,model in enumerate(models):
            if model.training or any(p.requires_grad or p.grad is not None for p in model.parameters()):
                raise ValueError('Batch diagnostic requires frozen CPU evaluation models')
            observed_batch = observed_features(states,model.norm_mean,model.norm_std)
            observed_single = [observed_features({k:v[i:i+1] for k,v in states.items()},
                               model.norm_mean,model.norm_std) for i in range(len(rows))]
            observed = {name:_difference(torch.cat([r[j] for r in observed_single]),observed_batch[j])
                        for j,name in enumerate(('visual','language','other'))}
            singleton = core.canonical_features(model,arrays)
            batched = model.features(states)
            caches.append(singleton);batch_features.append(batched)
            single_p = torch.from_numpy(core.predict_member(model,arrays))
            batch_p = torch.empty_like(single_p)
            for slot in range(13):
                pair = torch.stack([actions[:,0],actions[:,slot]],dim=1)
                probability=model(batched,pair).sigmoid()
                if slot==0 and not torch.equal(probability[:,1]-probability[:,0],torch.zeros(len(rows))):
                    raise ValueError('Dense designated a0 relative advantage is not exactly zero')
                batch_p[:,slot] = probability[:,0 if slot==0 else 1]
            records.append(dict(member=member,observed_features=observed,
                projected_features=_difference(singleton,batched),
                probabilities=_difference(single_p,batch_p),action_batch_shape=[len(rows),2,10,4],
                probability_slots=list(range(13)),dtype='float32',threads=2,gradients={}))
    ensemble={}
    with core.cpu_threads(),torch.enable_grad():
        for slot in (0,11):
            for member,model in enumerate(models):
                leaf=actions[:,slot].detach().clone().requires_grad_(True)
                anchor=actions[:,0].detach()
                if anchor.requires_grad:raise ValueError('Dense a0 anchor was not detached')
                pair=torch.stack([anchor,leaf],dim=1)
                p=model(batch_features[member],pair).sigmoid()
                dense=torch.autograd.grad((p[:,1]-p[:,0]).sum(),leaf)[0]
                singleton=torch.stack([core._member_gradient(model,caches[member][i:i+1],actions[i,0],actions[i,slot])
                                       for i in range(len(rows))])
                records[member]['gradients'][str(slot)]=_difference(singleton,dense)
            leaf=actions[:,slot].detach().clone().requires_grad_(True)
            pair=torch.stack([actions[:,0].detach(),leaf],dim=1)
            p=torch.stack([m(f,pair).sigmoid() for m,f in zip(models,batch_features)])
            dense=torch.autograd.grad((p[:,:,1]-p[:,:,0]).mean(0).sum(),leaf)[0]
            singleton=torch.stack([core.FrozenObjective({k:arrays[k][i] for k in STATE_KEYS},actions[i,0],
                                   models=models).gradient(actions[i,slot])[0] for i in range(len(rows))])
            ensemble[str(slot)]=_difference(singleton,dense)
    exact = all(record['projected_features']['exact_equal'] and record['probabilities']['exact_equal']
                and all(r['exact_equal'] for r in record['observed_features'].values())
                and all(r['exact_equal'] for r in record['gradients'].values()) for record in records)
    exact=exact and all(r['exact_equal'] for r in ensemble.values())
    if (before_inputs!=_fingerprint(dict(states,actions=actions))
            or before_models!=[_fingerprint(model.state_dict()) for model in models]
            or any(value._version!=version for value,version in versions)
            or any(p.grad is not None for model in models for p in model.parameters())):
        raise ValueError('Dense diagnostic changed state, a0, commands or frozen model')
    return dict(status='reported_exact' if exact else 'reported_differences',
        source_count=len(rows),episode_ids=ids,members=records,all_bit_exact=exact,
        ensemble_gradients=ensemble,gradient_slots=[0,11],
        reference_path='canonical singleton',comparison_path='dense batch',
        diagnostics_complete=True,numeric_contract=NUMERIC_CONTRACT,decision_sha256=NUMERICAL_DECISION_SHA,
        input_sha256=before_inputs,model_state_sha256=before_models,numeric_runtime=_runtime(),
        state_a0_actions_model_unchanged=True,a0_detached=True,a0_relative_advantage_exact_zero=True,
        source_independent_linear_silu_structure=True,
        member_gradient_reduction='sum source gains; no 1/N scaling',
        ensemble_gradient_reduction='mean members then sum sources; no 1/N scaling',
        production_path='canonical singleton source; two slots [a0,candidate]',
        new_tolerance_introduced=False,diagnostic_batch_path_used_for_canonical_inference=False)


def _audit_ok(record, rows):
    ids = [r['episode_id'] for r in rows]
    if record.get('status') != 'passed' or record.get('source_count') != len(ids):
        raise ValueError('Reload numerical check failed or lost source coverage')
    if not ids:
        if record.get('vacuous_no_reached_sources') is not True:
            raise ValueError('Empty set must be reported as vacuous')
        return
    if (record.get('episode_ids')!=ids or record.get('gradient_slots')!=[0,11]
            or record.get('members_checked')!=4
            or any(record.get(k) is not True for k in ('feature_cache_bit_exact',
                'thirteen_candidate_member_probability_bit_exact','member_and_ensemble_gradient_bit_exact',
                'a0_anchor_exactly_zero','state_and_anchor_immutable'))):
        raise ValueError('Reload audit must cover all members, 13 probabilities and slot0/11 gradients')


def _dense_ok(report, arrays, rows, models):
    """Validate complete finite diagnostics without accepting a new tolerance."""
    ids=[r['episode_id'] for r in rows];n=len(ids)
    if (report.get('source_count')!=n or report.get('episode_ids')!=ids
            or report.get('status') not in ('reported_exact','reported_differences')
            or report.get('diagnostics_complete') is not True
            or report.get('numeric_contract')!=NUMERIC_CONTRACT
            or report.get('decision_sha256')!=NUMERICAL_DECISION_SHA
            or type(report.get('all_bit_exact')) is not bool):
        raise ValueError('Dense diagnostic source coverage/contract is incomplete')
    if not n:
        if report.get('vacuous_no_reached_sources') is not True:raise ValueError('Missing empty-set diagnostic')
        return
    if (report.get('model_state_sha256')!=[_fingerprint(m.state_dict()) for m in models]
            or report.get('input_sha256')!=_fingerprint({k:arrays[k] for k in [*STATE_KEYS,'actions']})
            or report.get('numeric_runtime')!=_runtime() or report.get('gradient_slots')!=[0,11]
            or report.get('member_gradient_reduction')!='sum source gains; no 1/N scaling'
            or report.get('ensemble_gradient_reduction')!='mean members then sum sources; no 1/N scaling'
            or any(report.get(k) is not True for k in ('state_a0_actions_model_unchanged','a0_detached',
                'a0_relative_advantage_exact_zero','source_independent_linear_silu_structure'))
            or report.get('new_tolerance_introduced') is not False
            or report.get('diagnostic_batch_path_used_for_canonical_inference') is not False):
        raise ValueError('Dense diagnostic input/model identity or gradient semantics changed')
    differences=[]
    def value(record,shape):
        if (record.get('shape')!=shape or record.get('finite') is not True
                or type(record.get('exact_equal')) is not bool
                or type(record.get('mismatched_elements')) is not int
                or not 0<=record['mismatched_elements']<=int(np.prod(shape))
                or record['exact_equal']!=(record['mismatched_elements']==0)
                or any(not np.isfinite(record.get(k,float('nan'))) or record[k]<0 for k in
                    ('max_abs_difference','reference_max_abs','reference_rms','comparison_max_abs','comparison_rms'))):
            raise ValueError('Dense diagnostic difference/finite/reference-scale evidence is incomplete')
        differences.append(record)
    members=report.get('members',[])
    if len(members)!=4:raise ValueError('Dense diagnostics require all four members')
    for member,record in enumerate(members):
        if (record.get('member')!=member or record.get('action_batch_shape')!=[n,2,10,4]
                or record.get('probability_slots')!=list(range(13))):
            raise ValueError('Dense member/candidate axes changed')
        for name,width in (('visual',8192),('language',2048),('other',37)):
            value(record['observed_features'][name],[n,width])
        value(record['projected_features'],[n,61]);value(record['probabilities'],[n,13])
        for slot in ('0','11'):value(record['gradients'][slot],[n,10,4])
    for slot in ('0','11'):value(report['ensemble_gradients'][slot],[n,10,4])
    exact=all(v['exact_equal'] for v in differences)
    if report['all_bit_exact']!=exact or report['status']!=('reported_exact' if exact else 'reported_differences'):
        raise ValueError('Dense reported exactness differs from its actual diagnostics')


def _cost(start_wall,start_cpu,stages):
    return dict(wall_seconds=time.perf_counter()-start_wall,cpu_seconds=time.process_time()-start_cpu,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,stages=stages,
        simulator_attempts=0,optimizer_updates=0,device='cpu',scope='model preflight only')


def preflight(config, *, version):
    """Create eight sealed initial states only after full cross-protocol checks."""
    core._version(version)
    wall,cpu = time.perf_counter(),time.process_time();timings={}
    spec,design,identity,bundle,coverage = _inputs(config,'preflight')
    timings['input_audit_seconds']=time.perf_counter()-wall
    if torch.is_inference_mode_enabled():
        raise ValueError('Action-gradient preflight cannot run under inference_mode')
    directory = core._new_directory(storage.ROOT/'fit_preflight/final'/version)
    storage.dump(directory/'config.json',config)
    source_sets = _source_sets(bundle)
    registration = dict(schema=SCHEMA,role=ROLE,phase=PHASE,version=version,identity=identity,
        coverage=coverage,source_sets=source_sets,numeric_runtime=_runtime(),
        preflight_config_sha256=storage.sha256(directory/'config.json'),
        preflight_protocol_sha256=config['analysis_approval']['protocol_sha256'],
        preflight_ready=deepcopy(config['analysis_ready']),optimizer_updates=0,simulator_calls=0,
        model_fit_complete=False,final_training_released=False)
    storage.dump(directory/'registration.json',registration)
    storage.dump(directory/'source_sets.json',source_sets)
    train,dev=bundle['train'],bundle['development']
    try:
        begin=time.perf_counter()
        states, imported = core.load_old_members(storage.PACKAGE,design['old_weight_import'])
        if any(not torch.equal(states[0][key],state[key]) for state in states for key in ('norm_mean','norm_std')):
            raise ValueError('Original frozen visual normalizers differ across members')
        prep,pca_audit = core.fit_train_preprocessing(train['arrays'],train['rows'],range(len(train['rows'])),
            norm_mean=states[0]['norm_mean'],norm_std=states[0]['norm_std'])
        timings['old_import_and_train_pca_seconds']=time.perf_counter()-begin
        storage.dump(directory/'pca_fit_audit.json',pca_audit)
        initial_assets={};audits={};batch={};seeds={};sampling={};masks={};transforms={}
        transforms.update({'B__'+k:v.detach().cpu().numpy().copy() for k,v in prep.items()})
        for path in ('A','B'):
            begin=time.perf_counter()
            seeds[path]=[seed_for('training_initialization',PHASE,path,m,namespace=config['seed_namespace']) for m in range(4)]
            models=[core.initialize_model(path,seed=seeds[path][m],
                **({'warm_start_state':states[m]} if path=='A' else {'preprocessing':prep})) for m in range(4)]
            if path=='A':
                for member,model in enumerate(models):
                    if any(not torch.equal(value,states[member][key]) for key,value in model.state_dict().items()):
                        raise ValueError('A initialization changed its original member/projector')
                    transforms.update({f'A{member}__'+k:v.detach().cpu().numpy().copy() for k,v in model.named_buffers()})
            elif any(not torch.equal(value,prep[key]) for model in models for key,value in model.named_buffers()):
                raise ValueError('B members do not share the unique-train preprocessing')
            sampling[path]=[_sampling(train['rows'],config,path,m) for m in range(4)]
            masks[path]=[core._parameter_mask(model) for model in models]
            initial=[core.checkpoint_state(model) for model in models]
            assets=directory/path/'initial'
            selector=core.export_ensemble(initial,assets,provenance=dict(identity=identity,path=path,
                initialization_only=True,coverage=coverage,old_import=imported))
            frozen=core.frozen_models(initial);audits[path]={};batch[path]={}
            for purpose,pack in (('train',train),('development',dev)):
                record=core.audit_reload(frozen,selector,pack['arrays'],pack['rows'])
                _audit_ok(record,pack['rows']);audits[path][purpose]=record
                batch[path][purpose]=batch_singleton_diagnostics(frozen,pack['arrays'],pack['rows'])
                _dense_ok(batch[path][purpose],pack['arrays'],pack['rows'],frozen)
            storage.dump(directory/path/'reload_audit.json',audits[path])
            storage.dump(directory/path/'batch_singleton_audit.json',batch[path])
            initial_assets[path]=dict(path=str(assets),seal_sha256=storage.sha256(assets/'complete.json'),
                                     model_hashes=selector.ranking['model_hashes'])
            timings[path+'_initialization_export_checks_seconds']=time.perf_counter()-begin
        storage.arrays(directory/'preprocessing.npz',**transforms)
        storage.arrays(directory/'minibatch_plans.npz',**{f'{path}_{m}':_minibatches(sampling[path][m])
                       for path in ('A','B') for m in range(4)})
        storage.dump(directory/'sampling.json',sampling)
        storage.dump(directory/'trainable_masks.json',masks)
        exact = all(record['all_bit_exact'] for records in batch.values() for record in records.values())
        result=dict(**registration,status='passed',
            old_import=imported,pca_audit=pca_audit,initial_assets=initial_assets,initialization_seeds=seeds,
            reload_audits=audits,batch_singleton_audits=batch,
            both_paths_checked_before_any_optimizer_update=True,all_eight_initial_states_checked=True,
            canonical_reload_passed=True,batch_singleton_bit_exact=exact,
            numeric_contract=NUMERIC_CONTRACT,numerical_decision_sha256=NUMERICAL_DECISION_SHA,
            dense_diagnostics_complete=True,numerical_review_required=False,
            dense_report_analysis_review_required_before_training=True,training_released_by_this_artifact=False,
            pca_fit_audit_sha256=storage.sha256(directory/'pca_fit_audit.json'),
            preprocessing_sha256=storage.sha256(directory/'preprocessing.npz'),
            sampling_sha256=storage.sha256(directory/'sampling.json'),
            minibatch_plans_sha256=storage.sha256(directory/'minibatch_plans.npz'),
            trainable_masks_sha256=storage.sha256(directory/'trainable_masks.json'),
            source_sets_sha256=storage.sha256(directory/'source_sets.json'),
            cost=_cost(wall,cpu,timings),pca_fitting_performed=True,optimizer_model_fitting_performed=False)
        storage.dump(directory/'result.json',result)
        storage.seal(directory,role=ROLE,phase=PHASE,audit_status=result['status'],optimizer_updates=0,model_fit_complete=False)
        return dict(path=str(directory),seal_sha256=storage.sha256(directory/'complete.json'),
                    result_sha256=storage.sha256(directory/'result.json'),status=result['status'],phase=PHASE,optimizer_updates=0)
    except Exception as error:
        storage.dump(directory/'failure.json',dict(status='failed',role=ROLE,error=repr(error),optimizer_updates=0,
            simulator_calls=0,model_fit_complete=False,cost=_cost(wall,cpu,timings)))
        raise


def _sealed(directory, expected):
    directory=Path(directory).resolve()
    if directory.parent != (storage.ROOT/'fit_preflight/final').resolve():
        raise ValueError('Initial states must come from a new final preflight version')
    complete=core._checked_file(directory/'complete.json',expected)
    seal=_read(complete)
    actual={str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and p!=complete}
    if seal.get('status')!='complete' or set(seal.get('files',{}))!=actual:
        raise ValueError('Preflight is incomplete or its file inventory changed')
    for name,digest in seal['files'].items():
        path=(directory/name).resolve()
        if not path.is_relative_to(directory):raise ValueError('Preflight file escaped directory')
        core._checked_file(path,digest)
    return seal


def load_preflight(config, *, bundle=None, identity=None, coverage=None):
    """Recheck every binding before returning the exact eight initial states.

    Never reads old weights, reruns PCA or calls initialize_model. The caller
    must use the returned checkpoints; successful loading does not grant fit.
    """
    spec,_,current_identity,current_bundle,current_coverage=_inputs(config,'fit')
    if identity is not None and identity!=current_identity or coverage is not None and coverage!=current_coverage:
        raise ValueError('Caller final input identity/coverage changed')
    if bundle is not None and bundle['verification']!=current_bundle['verification']:
        raise ValueError('Caller bundle verification changed')
    identity,bundle,coverage=current_identity,current_bundle,current_coverage
    return _load_preflight_verified(config,spec,identity,bundle,coverage)


def _load_preflight_verified(config,spec,identity,bundle,coverage):
    """Internal continuation only after _inputs has checked this full bundle."""
    binding=spec.get('preflight')
    if not isinstance(binding,dict):raise ValueError('Final fit needs separately sealed preflight')
    directory=Path(binding['path']).resolve();seal=_sealed(directory,binding['seal_sha256'])
    result=_read(core._checked_file(directory/'result.json',binding['result_sha256']))
    prefit_config=_read(core._checked_file(directory/'config.json',result.get('preflight_config_sha256')))
    _,_,saved_identity=_validate_specification(prefit_config,'preflight')
    if (seal.get('role')!=ROLE or seal.get('phase')!=PHASE or seal.get('audit_status')!='passed'
            or seal.get('optimizer_updates')!=0 or seal.get('model_fit_complete') is not False
            or result.get('role')!=ROLE or result.get('status')!='passed'
            or result.get('optimizer_updates')!=0 or result.get('simulator_calls')!=0
            or result.get('model_fit_complete') is not False
            or result.get('identity')!=identity or saved_identity!=identity
            or result.get('coverage')!=coverage or result.get('numeric_runtime')!=_runtime()
            or result.get('preflight_protocol_sha256')!=prefit_config['analysis_approval']['protocol_sha256']
            or result.get('preflight_ready')!=prefit_config['analysis_ready']
            or result.get('numeric_contract')!=NUMERIC_CONTRACT
            or result.get('numerical_decision_sha256')!=NUMERICAL_DECISION_SHA
            or result.get('dense_diagnostics_complete') is not True
            or result.get('canonical_reload_passed') is not True
            or type(result.get('batch_singleton_bit_exact')) is not bool
            or result['batch_singleton_bit_exact']!=all(report.get('all_bit_exact') is True
                for reports in result.get('batch_singleton_audits',{}).values() for report in reports.values())
            or result.get('dense_report_analysis_review_required_before_training') is not True
            or result.get('numerical_review_required') is not False
            or result.get('all_eight_initial_states_checked') is not True
            or result.get('both_paths_checked_before_any_optimizer_update') is not True):
        raise ValueError('Final preflight failed or changed frozen identity')
    checks=_read(core._checked_file(directory/'source_sets.json',result['source_sets_sha256']))
    if checks!=_source_sets(bundle) or checks!=result.get('source_sets'):
        raise ValueError('Actual train/dev check sets differ from the sealed preflight')
    pca=_read(core._checked_file(directory/'pca_fit_audit.json',result['pca_fit_audit_sha256']))
    rows=bundle['train']['rows'];ids=[r['episode_id'] for r in rows]
    if (pca!=result['pca_audit'] or pca.get('fit_episode_ids')!=ids or pca.get('fit_source_count')!=len(ids)
            or pca.get('train_only') is not True or pca.get('bootstrap_duplicates_used') is not False
            or pca.get('visual_dimension')!=16 or pca.get('language_dimension')!=8):
        raise ValueError('Sealed PCA did not use each unique effective train source once')
    sampling=_read(core._checked_file(directory/'sampling.json',result['sampling_sha256']))
    masks=_read(core._checked_file(directory/'trainable_masks.json',result['trainable_masks_sha256']))
    plans=core._checked_file(directory/'minibatch_plans.npz',result['minibatch_plans_sha256'])
    with np.load(plans,allow_pickle=False) as archive:
        minibatches={k:archive[k].copy() for k in archive.files}
    if set(minibatches)!={f'{p}_{m}' for p in ('A','B') for m in range(4)}:
        raise ValueError('Eight complete final minibatch plans are required')
    preprocessing=core._checked_file(directory/'preprocessing.npz',result['preprocessing_sha256'])
    with np.load(preprocessing,allow_pickle=False) as archive:
        transforms={k:archive[k].copy() for k in archive.files}
    states={}
    for path in ('A','B'):
        if sampling.get(path)!=[_sampling(rows,config,path,m) for m in range(4)]:
            raise ValueError('Final bootstrap/minibatch plan differs from sealed actual train set')
        for member in range(4):
            actual=minibatches[f'{path}_{member}'];expected=_minibatches(sampling[path][member])
            if actual.dtype!=expected.dtype or actual.shape!=expected.shape or actual.tobytes()!=expected.tobytes():
                raise ValueError('Sealed 4000x32 minibatch indices changed')
        for purpose in ('train','development'):
            _audit_ok(result['reload_audits'][path][purpose],bundle[purpose]['rows'])
            batch=result['batch_singleton_audits'][path][purpose]
            if (batch.get('status') not in ('reported_exact','reported_differences')
                    or batch.get('diagnostics_complete') is not True
                    or batch.get('numeric_contract')!=NUMERIC_CONTRACT
                    or batch.get('decision_sha256')!=NUMERICAL_DECISION_SHA
                    or batch.get('episode_ids')!=checks[purpose]['effective_episode_ids']):
                raise ValueError('Final dense diagnostic lacks complete approved reporting evidence')
        asset=result['initial_assets'][path];assets=Path(asset['path']).resolve()
        if assets!=directory/path/'initial':raise ValueError('Initial assets escaped final preflight')
        core._checked_file(assets/'complete.json',asset['seal_sha256'])
        selector=FrozenSelector(assets);selector.verify(check_files=True)
        if selector.ranking['model_hashes']!=asset['model_hashes']:
            raise ValueError('Initial four-member checkpoint identity changed')
        for purpose in ('train','development'):
            _dense_ok(result['batch_singleton_audits'][path][purpose],bundle[purpose]['arrays'],
                      bundle[purpose]['rows'],selector.models)
        states[path]=[core.checkpoint_state(m) for m in selector.models]
        owned=[from_state(s) for s in states[path]]
        for member,model in enumerate(owned):
            core.configure_trainable(model,path)
            for name,value in model.named_buffers():
                key=('B__' if path=='B' else f'A{member}__')+name
                if key not in transforms or not np.array_equal(value.detach().numpy(),transforms[key]):
                    raise ValueError('Initial preprocessing differs from the sealed transforms')
        if masks.get(path)!=[core._parameter_mask(m) for m in owned]:
            raise ValueError('Frozen/trainable masks changed after the final preflight')
    result['sampling']=sampling
    return result,states


def run(config, ledger, *, version):
    """Fit from approved sealed initial states; no new PCA or initialization."""
    core._version(version)
    begin,cpu=time.perf_counter(),time.process_time()
    spec,_,identity,bundle,coverage=_inputs(config,'fit')
    prefit,initial=_load_preflight_verified(config,spec,identity,bundle,coverage)
    train,dev=bundle['train'],bundle['development'];stops=spec['stop_after']
    directory=core._new_directory(storage.ROOT/'models/final'/version)
    storage.dump(directory/'config.json',config)
    provenance=dict(schema=SCHEMA,phase=PHASE,version=version,identity=identity,coverage=coverage,
        config_protocol_sha256=config['analysis_approval']['protocol_sha256'],
        input_bundle=spec['input_bundle'],source_bindings=spec['source_bindings'],
        preflight_binding=spec['preflight'],preflight_protocol_sha256=prefit['preflight_protocol_sha256'],
        old_import=prefit['old_import'],source_sets=prefit['source_sets'],
        preprocessing_refitted=False,new_initialization_generated=False,real_policy_evaluation_performed=False)
    storage.dump(directory/'registration.json',dict(**provenance,stop_after=stops))
    selected_records,checkpoints,attempts=[],{},[]
    class VersionLedger:
        def reserve(self,stage,kind,identity,**kwargs):
            return ledger.reserve(stage,kind,f'{version}:{identity}',**kwargs)
    version_ledger=VersionLedger()
    try:
        for path in ('A','B'):
            models=[from_state(s) for s in initial[path]]
            for model in models:
                model._native10_training_path=path;core.configure_trainable(model,path)
            predictions={step:[] for step in core.CHECKPOINTS[PHASE] if step<=stops[path]}
            for member,model in enumerate(models):
                member_dir=directory/path/f'member_{member}'
                def save_step(step,state,metrics):
                    owned=from_state(state).eval().requires_grad_(False)
                    saved=core.save_checkpoint(owned,member_dir/f'step_{step}'/'selected.pt')
                    checkpoints[path,member,step]=saved
                    probabilities=core.predict_member(owned,dev['arrays'])
                    predictions[step].append(probabilities)
                    storage.arrays(member_dir/f'step_{step}'/'development_predictions.npz',probabilities=probabilities)
                    storage.dump(member_dir/f'step_{step}'/'metadata.json',dict(checkpoint=saved,last_minibatch=metrics,
                        init_seed=prefit['initialization_seeds'][path][member],
                        original_development_binding=spec['source_bindings']['development']['pipeline_binding']))
                fitted=core.fit_member(config,version_ledger,phase=PHASE,path=path,member=member,model=model,
                    features=core.canonical_features(model,train['arrays']),data=dict(rows=train['rows'],**train['arrays']),
                    stop_after=stops[path],on_checkpoint=save_step)
                expected=prefit['sampling'][path][member]
                if fitted.get('bootstrap')!=expected['bootstrap'] or fitted.get('batch_seed')!=expected['batch_seed']:
                    raise ValueError('Fit changed sealed bootstrap/minibatch sampling')
                actual_batches=np.asarray(fitted.get('minibatches',[]),dtype=np.int64)
                if (list(actual_batches.shape)!=expected['minibatch_plan_shape']
                        or hashlib.sha256(actual_batches.tobytes()).hexdigest()!=expected['minibatch_plan_sha256']):
                    raise ValueError('Actual fit minibatch sequence differs from the sealed plan')
                numbers=fitted.get('attempt_numbers',[])
                if (fitted.get('updates')!=stops[path] or len(numbers)!=stops[path]
                        or len(set(numbers))!=len(numbers) or set(numbers)&set(attempts)):
                    raise ValueError('Final update ledger count/identity differs from fixed schedule')
                attempts.extend(numbers);fitted.pop('checkpoints')
                storage.dump(member_dir/'fit.json',fitted)
            for step,probabilities in predictions.items():
                metrics,full=core.development_selection(dev,np.stack(probabilities))
                record=dict(path=path,step=step,phase=PHASE,
                    dataset_sha256=spec['source_bindings']['development']['pipeline_binding']['seal_sha256'],metrics=metrics)
                selected_records.append(record)
                storage.arrays(directory/path/f'development_step_{step}.npz',**full)
                storage.dump(directory/path/f'development_step_{step}.json',record)
        chosen=core.choose_checkpoint(selected_records);selected_states=[]
        for member in range(4):
            selected=checkpoints[chosen['path'],member,chosen['step']]
            core._checked_file(selected['path'],selected['sha256'])
            selected_states.append(torch.load(selected['path'],weights_only=True,map_location='cpu'))
        selector=core.export_ensemble(selected_states,directory/'selected',provenance=dict(provenance,selection=chosen))
        checked=core.audit_reload(core.frozen_models(selected_states),selector,dev['arrays'],dev['rows'])
        _audit_ok(checked,dev['rows'])
        metrics,_=core.development_selection(dev,np.stack([core.predict_member(m,dev['arrays']) for m in selector.models]))
        if metrics!=chosen['metrics']:
            raise ValueError('Selected export changed original dev100 ranking/metrics')
        storage.dump(directory/'selected_reload_audit.json',checked)
        result=dict(status='complete',**provenance,selection=chosen,compared_checkpoints=selected_records,
            selected_assets=str(directory/'selected'),model_hashes=selector.ranking['model_hashes'],
            optimizer_updates=len(attempts),optimizer_attempt_numbers=attempts,simulator_calls=0,
            independent_validation_success=False,next_stage_automatically_started=False,
            cost=dict(wall_seconds=time.perf_counter()-begin,cpu_seconds=time.process_time()-cpu,
                      peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,device='cpu'))
        storage.dump(directory/'result.json',result)
        storage.seal(directory,role='native10_final_two_path_training',phase=PHASE,model_hashes=selector.ranking['model_hashes'])
        return result
    except Exception as error:
        storage.dump(directory/'failure.json',dict(status='failed',error=repr(error),counted_updates_not_refunded=True,
            simulator_calls=0,next_stage_automatically_started=False,
            wall_seconds=time.perf_counter()-begin,cpu_seconds=time.process_time()-cpu))
        raise
