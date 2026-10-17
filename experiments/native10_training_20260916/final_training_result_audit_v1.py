"""Post-seal final training audit: NumPy plus CPU state_dict reads; no model.

Two complete seals are mandatory before any final result, prediction or ranking
is opened. No pipeline/critic/simulator/optimizer import or forward/backward.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import resource
import sys
import tarfile
import time
import numpy as np
import torch
from .training_result_audit_v1 import (Audit,digest,digest_bytes,read,seed,equal_tensor,
    selection_metrics,selection_key,reconstruct_bootstrap,CANDIDATES)
from .protocol import canonical_hash,protocol_digest

PROJECT=Path(__file__).resolve().parents[2]
ROOT=PROJECT/'outputs/native10_training_20260916'
STEPS=(200,400,800,1600,2400,3200,4000)


def completed_paths(model_version):
    if not isinstance(model_version,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',model_version):
        raise ValueError('Unsafe final model version')
    model=ROOT/'models/final'/model_version;execution=ROOT/'final_fit_execution/fit'/model_version
    # Existence-only check: never inspect an unfinished result or prediction.
    missing=[str(p/'complete.json') for p in (model,execution) if not (p/'complete.json').is_file()]
    return model,execution,missing


def verify_minibatches(a,reconstructed,actual,sealed,sampling):
    a.require(reconstructed.shape==actual.shape==sealed.shape==(4000,32),'Final minibatch shape')
    a.require(reconstructed.dtype==actual.dtype==sealed.dtype==np.int64,'Final minibatch dtype')
    a.require(reconstructed.tobytes()==actual.tobytes()==sealed.tobytes(),'Actual/rebuilt/sealed minibatches differ')
    a.require(digest_bytes(actual.tobytes())==sampling['minibatch_plan_sha256']
              and sampling['minibatch_plan_shape']==[4000,32] and sampling['minibatch_plan_dtype']=='int64','Minibatch hash/schema')


def verify_checkpoint(a,state,initial,trainable):
    a.require(set(state)==set(initial),'Checkpoint state schema')
    changed=[]
    for name,value in state.items():
        a.require(value.device.type=='cpu' and value.dtype==initial[name].dtype
                  and value.shape==initial[name].shape and torch.isfinite(value).all().item(),'Nonfinite/schema checkpoint')
        if name not in trainable:
            a.require(equal_tensor(value,initial[name]),'Frozen value changed: '+name)
        elif not equal_tensor(value,initial[name]):changed.append(name)
    a.require(bool(changed),'No trainable parameter changed from preflight')
    return changed


def verify_ledger_delta(a,before,after,version,protocol_sha):
    a.require(after.startswith(before),'Budget history changed')
    prior=[json.loads(line) for line in before.splitlines()];rows=[json.loads(line) for line in after.splitlines()]
    for number,row in enumerate(rows,1):
        a.require(row['number']==number and row['resource'] in ('simulator_attempts','training_updates')
                  and type(row['amount']) is int and row['amount']>=1,'Invalid global ledger record')
    added=rows[len(prior):]
    expected=[f'{version}:final:{p}:{m}:{step}' for p in ('A','B') for m in range(4) for step in range(1,4001)]
    a.require(len(added)==32000 and [r['identity'] for r in added]==expected,'Final update identities duplicate/missing/out of order')
    for row in added:
        a.require(row['stage']=='training_final' and row['resource']=='training_updates' and row['amount']==1
                  and row['kind']=='critic_optimizer_update' and row['protocol_sha256']==protocol_sha,'Unauthorized final resource')
    a.require(not any(r['stage']=='training_final' for r in prior),'Earlier final update attempts cannot be omitted')
    totals=Counter()
    for row in rows:totals[row['resource']]+=row['amount']
    a.require(totals['simulator_attempts']<=50000 and totals['training_updates']<=51200,'Workflow resource cap')
    return dict(optimizer_updates=32000,simulator_attempts=0,attempt_numbers=[r['number'] for r in added],
                before_entries=len(prior),after_entries=len(rows),totals=dict(totals))


def verify_freeze(a,config_path,freeze_path):
    config=read(config_path);freeze=read(freeze_path)
    a.file(freeze_path);a.file(config_path,freeze['config_sha256'])
    a.require(freeze.get('role')=='native10_final_fit_protocol_v1' and freeze.get('mode')=='fit' and freeze.get('phase')=='final','Wrong final fit freeze')
    a.require(freeze['files'].get(str(config_path))==digest(config_path),'Config absent from freeze')
    for path,expected in freeze['files'].items():a.file(path,expected)
    archive=freeze['code_snapshot'];a.file(archive['path'],archive['sha256'])
    with tarfile.open(archive['path'],'r:gz') as stream:
        members=stream.getmembers();expected=archive['files']
        a.require(len(members)==len(expected) and {m.name for m in members}=={p.lstrip('/') for p in expected},'Code archive inventory')
        for m in members:
            a.require(m.isfile() and digest_bytes(stream.extractfile(m).read())==expected['/'+m.name],'Code archive bytes')
    ready=read(config['analysis_ready']['path']);a.file(config['analysis_ready']['path'],config['analysis_ready']['sha256'])
    a.require(ready['version']==10 and 'final_critic_training' in ready['released_scope'],'Final READYv10 release missing')
    a.require(config['stage_release_scopes']['training_final']=='final_critic_training','Final stage scope')
    a.require(config['budget']['stages']['training_final']=={'simulator_attempts':0,'training_updates':32000},'Final budget')
    a.require(config['final_training_pipeline']['stop_after']=={'A':4000,'B':4000},'Changed stops')
    a.require(config['status']=='frozen' and config['analysis_approval']['status']=='approved'
              and config['analysis_approval']['protocol_sha256']==protocol_digest(config),'Final protocol digest')
    return config,freeze


def audit(config_path,freeze_path,model_version='final_fit_v1',output_version='final_fit_v1'):
    begin,cpu=time.perf_counter(),time.process_time()
    directory,execution,missing=completed_paths(model_version)
    if missing:raise RuntimeError('Final result AND execution seals are required; unfinished predictions were not read: '+', '.join(missing))
    destination=ROOT/'final_training_audits'/output_version
    if destination.resolve().parent!=(ROOT/'final_training_audits').resolve() or destination.exists():raise ValueError('Use a safe new audit version')
    torch.set_num_threads(2)
    a=Audit();seal=a.seal(directory);execution_seal=a.seal(execution)
    a.require(seal.get('role')=='native10_final_two_path_training' and seal.get('phase')=='final','Wrong final completed model role')
    a.require(execution_seal.get('role')=='native10_final_cpu_execution_receipt' and execution_seal.get('mode')=='fit','Wrong execution receipt role')
    ledger_live_before=(ROOT/'budget/attempts.jsonl').read_bytes()
    config_path=Path(config_path).resolve();freeze_path=Path(freeze_path).resolve()
    config,freeze=verify_freeze(a,config_path,freeze_path);specification=config['final_training_pipeline']
    a.require(read(directory/'config.json')==config,'Saved fit config differs from authorized freeze')
    result,registration=read(directory/'result.json'),read(directory/'registration.json')
    receipt,launch=read(execution/'result.json'),read(execution/'registration.json')
    a.require(receipt['status']=='complete' and receipt['mode']=='fit' and receipt['version']==model_version,'Wrong completed execution')
    a.require(receipt['pipeline_result']==result,'Execution/result mismatch')
    a.require(launch['config_path']==str(config_path) and launch['config_sha256']==digest(config_path)
              and launch['freeze_path']==str(freeze_path) and launch['freeze_sha256']==digest(freeze_path),'Execution launch binding')
    a.require(receipt['cpu_only'] is True and receipt['next_stage_automatically_started'] is False,'Unauthorized next stage')
    before=(execution/'budget_before.jsonl').read_bytes();after=(execution/'budget_after.jsonl').read_bytes()
    resources=verify_ledger_delta(a,before,after,model_version,config['analysis_approval']['protocol_sha256'])
    a.require(ledger_live_before.startswith(after),'Live ledger does not preserve completed training snapshot')
    a.require(launch['resource_before']['sha256']==digest_bytes(before) and receipt['resource_after']['sha256']==digest_bytes(after),'Execution budget hash')
    a.require(receipt['resources']['optimizer_updates']==32000 and receipt['resources']['simulator_attempts']==0
              and receipt['resources']['attempt_numbers']==resources['attempt_numbers'],'Receipt resource delta')
    a.require(result['status']=='complete' and result['phase']=='final' and result['version']==model_version,'Wrong result identity')
    a.require(result['optimizer_updates']==32000 and result['simulator_calls']==0,'Final resource count')
    for key in ('identity','input_bundle','source_bindings','coverage','preflight_binding','config_protocol_sha256','source_sets'):
        a.require(result[key]==registration[key], 'Registration mismatch: '+key)
    a.require(result['config_protocol_sha256']==config['analysis_approval']['protocol_sha256'],'Wrong fit protocol')
    for key in ('preprocessing_refitted','new_initialization_generated','real_policy_evaluation_performed','independent_validation_success','next_stage_automatically_started'):
        a.require(result[key] is False,'Unexpected fit claim: '+key)
    expected_identity={k:v for k,v in specification.items() if k not in ('schema','preflight')}
    expected_identity['seed_namespace']=config['seed_namespace']
    a.require(freeze['specification_sha256']==canonical_hash(expected_identity),'Frozen specification digest')
    a.require(result['identity']==expected_identity and result['input_bundle']==specification['input_bundle']
              and result['source_bindings']==specification['source_bindings'],'Cross-protocol identity drift')
    pre=Path(specification['preflight']['path']);a.seal(pre,specification['preflight']['seal_sha256'])
    a.file(pre/'result.json',specification['preflight']['result_sha256']);pref=read(pre/'result.json')
    a.require(result['preflight_binding']==specification['preflight']
              and result['preflight_protocol_sha256']==pref['preflight_protocol_sha256']
              and result['coverage']==pref['coverage'],'Actual fit/preflight binding differs')
    a.require(pref['status']=='passed' and pref['identity']==expected_identity and pref['optimizer_updates']==0
              and pref['simulator_calls']==0 and pref['model_fit_complete'] is False,'Final preflight binding failed')
    a.require(pref['all_eight_initial_states_checked'] is True
              and pref['both_paths_checked_before_any_optimizer_update'] is True,'Prefit initialization order evidence')
    a.require(pref['numeric_runtime']==expected_identity['numeric_runtime'] and pref['numeric_contract']=='canonical_strict_passed_dense_reported'
              and pref['canonical_reload_passed'] is True and pref['dense_diagnostics_complete'] is True,'Frozen numerical contract')
    for filename,field in [('pca_fit_audit.json','pca_fit_audit_sha256'),('preprocessing.npz','preprocessing_sha256'),
        ('sampling.json','sampling_sha256'),('minibatch_plans.npz','minibatch_plans_sha256'),
        ('trainable_masks.json','trainable_masks_sha256'),('source_sets.json','source_sets_sha256')]:a.file(pre/filename,pref[field])
    masks, sampling = read(pre/"trainable_masks.json"), read(pre/"sampling.json")
    bindings={key:source['pipeline_binding'] for key,source in specification['source_bindings'].items()}
    bundle_dir=Path(specification['input_bundle']['path'])
    a.seal(bundle_dir,specification['input_bundle']['seal_sha256'])
    for binding in bindings.values():
        a.seal(Path(binding["path"]), binding["seal_sha256"])
        a.file(binding["input_audit_path"], binding["input_audit_sha256"])
    train_rows = read(bundle_dir/"train/rows.json")
    a.require(train_rows==read(Path(bindings['round1_train']['path'])/'rows.json')+read(Path(bindings['round2_train']['path'])/'rows.json'),'Union train rows differ from children')
    train_ids=[row['episode_id'] for row in train_rows]
    a.require(len(set(train_ids))==len(train_rows), 'Duplicate final train source')
    a.require(Counter(row['round'] for row in train_rows)=={1:300,2:300},'Final round counts')
    a.require(Counter(row['task'] for row in train_rows)=={task:120 for task in config['tasks']},'Final task counts')
    sealed_plans_path=pre/'minibatch_plans.npz';a.file(sealed_plans_path,pref['minibatch_plans_sha256'])
    with np.load(sealed_plans_path,allow_pickle=False) as archive:
        sealed_plans={key:archive[key].copy() for key in archive.files}
    a.require(set(sealed_plans)=={f'{p}_{m}' for p in ('A','B') for m in range(4)},'Eight sealed minibatch plans')
    with np.load(pre/'preprocessing.npz',allow_pickle=False) as archive:
        preprocessing={key:archive[key].copy() for key in archive.files}
    source_sets=read(pre/'source_sets.json')
    a.require(source_sets==pref['source_sets']==result['source_sets'],'Source-set identity')
    a.require(source_sets['train']['effective_episode_ids']==train_ids and source_sets['train']['planned_count']==600,'Train preflight coverage')
    pca=read(pre/'pca_fit_audit.json')
    a.require(pca==pref['pca_audit'] and pca['fit_episode_ids']==train_ids and pca['fit_source_count']==600
              and pca['train_only'] is True and pca['bootstrap_duplicates_used'] is False
              and pca['visual_dimension']==16 and pca['language_dimension']==8,'Frozen unique-train PCA metadata')
    dev_dir = Path(bindings["development"]["path"])
    dev_rows, dev_metadata = read(dev_dir/"rows.json"), read(dev_dir/"metadata.json")
    a.require(len(train_rows) == 600 and all(r["split"] == "train" and r["round"] in (1,2) for r in train_rows), "Training split")
    a.require(len(dev_rows) == 95 and len(dev_metadata["records"]) == 100, "Full development denominator")
    a.require(not ({r["episode_id"] for r in train_rows} & {r["episode_id"] for r in dev_metadata["records"]}), "Split overlap")
    with np.load(dev_dir/"arrays.npz", allow_pickle=False) as arrays:
        y_reached = arrays["outcomes"].copy()
        gw_reached = arrays["gain_weights"].copy()
        aliases = arrays["alias_indices"].copy()
    for source, groups in enumerate(aliases):
        counts = Counter(groups.tolist())
        expected_weights = np.asarray([0. if group == groups[0] else 1./counts[group]
                                       for group in groups], dtype=np.float32)
        a.require(np.array_equal(gw_reached[source], expected_weights), "Development gain alias weights")
        for slot, canonical in enumerate(groups):
            a.require(np.array_equal(y_reached[source,slot],y_reached[source,canonical]), "Development alias outcomes")
    index = {row["episode_id"]: i for i, row in enumerate(dev_rows)}
    n = len(dev_metadata["records"])
    y = np.empty((n,13,4), bool); gw = np.zeros((n,13),np.float32)
    reached = np.zeros(n,bool); scatter = []
    for i, record in enumerate(dev_metadata["records"]):
        if record.get("critic_eligible") is True:
            a.require(record["status"] == "complete" and record["control_complete"], "Incomplete dev labels")
            j = index.pop(record["episode_id"])
            y[i], gw[i], reached[i] = y_reached[j], gw_reached[j], True
            scatter.append((i,j))
        else:
            a.require(record["status"] == "no_cut" and record["full_episode_outcome_available"] is True
                      and isinstance(record["native10_outcome"], bool), "Unknown no-cut outcome")
            y[i] = record["native10_outcome"]
    a.require(not index and reached.sum() == 95, "Development row scatter")
    a.require(source_sets['development']['effective_episode_ids']==[r['episode_id'] for r in dev_rows]
              and source_sets['development']['planned_count']==100 and source_sets['development']['no_cut_count']==5,'Dev preflight coverage')
    ledger_bytes=(execution/'budget_after.jsonl').read_bytes()
    ledger=[json.loads(line) for line in ledger_bytes.splitlines()]
    ledger_index = {row["number"]: row for row in ledger}
    a.require(len(ledger_index) == len(ledger), "Duplicate global ledger ID")
    training_ledger = [row for row in ledger if row["stage"] == "training_final"]
    a.require(len(training_ledger) == 32000, "Training stage attempts differ")
    a.require(all(row["resource"] == "training_updates" and row["amount"] == 1 for row in training_ledger), "Invalid training resource")
    updates, members, states = [], [], {}
    for path in ("A", "B"):
        asset=pref['initial_assets'][path]
        a.require(Path(asset['path']).resolve()==(pre/path/'initial').resolve(),'Initial path')
        a.seal(pre/path/'initial',asset['seal_sha256'])
        ranking=read(pre/path/'initial/ranking.json')
        a.require(ranking['model_hashes']==asset['model_hashes'] and set(asset['model_hashes'])=={'0','1','2','3'},'Initial member identities')
        for member in range(4):
            member_dir = directory/path/f"member_{member}"
            fit = read(member_dir/"fit.json")
            a.require((fit["phase"],fit["path"],fit["member"],fit["updates"]) == ("final",path,member,4000), "Fit identity")
            a.require(fit["source_ids"] == [row["episode_id"] for row in train_rows], "Fit source identities")
            a.require(fit["normal_control_used_in_critic"] is False and fit["calibration_or_heldout_used"] is False, "Forbidden training sources")
            boot_seed = seed(config["seed_namespace"], "training_bootstrap", "final", path, member)
            batch_seed = seed(config["seed_namespace"], "training_minibatches", "final", path, member)
            bootstrap = reconstruct_bootstrap(train_rows, config["tasks"], boot_seed)
            a.require(fit["bootstrap"] == sampling[path][member]["bootstrap"] == bootstrap, "Bootstrap mismatch")
            a.require(fit["batch_seed"] == sampling[path][member]["batch_seed"] == batch_seed, "Minibatch seed mismatch")
            pool = np.asarray(bootstrap["indices"],np.int64)
            rng = np.random.default_rng(batch_seed)
            batches = np.stack([pool[rng.integers(0,len(pool),32)] for _ in range(4000)])
            actual_batches=np.asarray(fit['minibatches'])
            verify_minibatches(a,batches,actual_batches,sealed_plans[f'{path}_{member}'],sampling[path][member])
            ids = fit["attempt_numbers"]
            a.require(len(ids) == len(set(ids)) == 4000, "Fit update IDs")
            for step, number in enumerate(ids, 1):
                row = ledger_index[number]
                a.require(row["stage"] == "training_final" and row["kind"] == "critic_optimizer_update"
                          and row["identity"] == f"{model_version}:final:{path}:{member}:{step}"
                          and row["protocol_sha256"] == result["config_protocol_sha256"]
                          and row["resource"] == "training_updates" and row["amount"] == 1, "Update ledger identity")
            updates.extend(ids)
            initial_path = pre/path/"initial/models/refit"/f"member_{member}"/"selected.pt"
            a.file(initial_path,asset['model_hashes'][str(member)])
            initial = torch.load(initial_path, map_location="cpu", weights_only=True)
            mask = masks[path][member]
            parameter_names = {x["name"] for x in mask["parameters"]}
            buffer_names = {x["name"] for x in mask["buffers"]}
            trainable = [x["name"] for x in mask["parameters"] if x["requires_grad"]]
            a.require(fit["trainable_parameters"] == trainable, "Trainable mask differs from preflight")
            a.require(set(initial) == parameter_names | buffer_names and not parameter_names & buffer_names, "Mask incomplete")
            a.require(set(trainable) == {k for k in parameter_names if path == "B" or k.split('.')[0] in ("residual","advantage")}, "Wrong A/B parameter modules")
            for field in mask["parameters"] + mask["buffers"]:
                tensor = initial[field["name"]]
                a.require(list(tensor.shape) == field["shape"] and str(tensor.dtype) == field["dtype"]
                          and tensor.numel() == field["numel"] and torch.isfinite(tensor).all().item(), "Initial tensor schema/finite")
            for name in buffer_names:
                key=('B__' if path=='B' else f'A{member}__')+name
                value=initial[name].numpy()
                a.require(key in preprocessing and value.dtype==preprocessing[key].dtype
                          and value.shape==preprocessing[key].shape and value.tobytes()==preprocessing[key].tobytes(),
                          'PCA/normalizer buffer differs from sealed preprocessing')
            expected_init=seed(config['seed_namespace'],'training_initialization','final',path,member)
            a.require(pref['initialization_seeds'][path][member]==expected_init,'Sealed initialization seed')
            a.require([m['step'] for m in fit['history']]==list(STEPS),'Loss history checkpoints')
            for metric in fit['history']:
                a.require(metric['last_minibatch_only'] is True and all(np.isfinite(metric[k]) for k in ('loss','bce','gain_mse','pair_mse')),'Invalid loss history')
            changed_counts = {}
            for step in STEPS:
                checkpoint_dir = member_dir/f"step_{step}"
                metadata = read(checkpoint_dir/"metadata.json")
                cp = checkpoint_dir/"selected.pt"
                a.require(Path(metadata["checkpoint"]["path"]).resolve() == cp.resolve(), "Checkpoint metadata path")
                a.file(cp, metadata["checkpoint"]["sha256"])
                a.require(metadata["init_seed"] == pref["initialization_seeds"][path][member], "Initialization identity")
                a.require(metadata["original_development_binding"] == bindings["development"], "Checkpoint development binding")
                a.require(metadata['last_minibatch']==next(m for m in fit['history'] if m['step']==step),'Checkpoint loss metadata differs from fit history')
                state = torch.load(cp,map_location="cpu",weights_only=True)
                changed=verify_checkpoint(a,state,initial,trainable)
                changed_counts[str(step)] = len(changed)
                states[(path,member,step)] = state
            members.append(dict(path=path,member=member,updates=4000,bootstrap_exact=True,
                all_minibatches_exact=True,trainable_parameter_tensors=len(trainable),
                frozen_parameter_tensors=len(parameter_names)-len(trainable),frozen_buffer_tensors=len(buffer_names),
                changed_trainable_tensors_by_step=changed_counts,all_frozen_values_bit_exact=True))
    a.require(len(updates) == len(set(updates)) == 32000, "Eight fits overlap update IDs")
    a.require(updates == result["optimizer_attempt_numbers"], "Result update IDs mismatch")
    a.require(set(updates) == {row["number"] for row in training_ledger}, "Unaccounted training updates")
    records, max_mse_error = [], 0.
    expected_ids = [r["episode_id"] for r in dev_metadata["records"]]
    expected_slots = [r.get("planned_slot_id", r["episode_id"]) for r in dev_metadata["records"]]
    for path in ("A", "B"):
        for step in STEPS:
            member_p = []
            for member in range(4):
                with np.load(directory/path/f"member_{member}/step_{step}/development_predictions.npz") as f:
                    value = f["probabilities"].copy()
                a.require(value.shape == (95,13) and value.dtype == np.float32, "Member prediction schema")
                for j, groups in enumerate(aliases):
                    for slot in range(13):
                        a.require(value[j,slot] == value[j,groups[slot]], "Raw-alias predictions differ")
                member_p.append(value)
            p = np.full((4,n,13),np.nan,np.float32)
            for i,j in scatter:
                p[:,i] = np.stack(member_p)[:,j]
            with np.load(directory/path/f"development_step_{step}.npz") as cached:
                for name, expected in dict(member_probabilities=p,outcomes=y,reached_mask=reached,gain_weights=gw).items():
                    a.require(np.array_equal(cached[name],expected,equal_nan=True), f"Selection cached array mismatch: {name}")
            metrics = selection_metrics(p,y,reached,gw)
            saved = read(directory/path/f"development_step_{step}.json")
            a.require(saved["path"] == path and saved["step"] == step and saved["phase"] == "final"
                      and saved["dataset_sha256"] == bindings["development"]["seal_sha256"], "Selection bank identity")
            for key, value in metrics.items():
                if key == "gain_mse":
                    error = abs(value-saved["metrics"][key]);max_mse_error=max(error,max_mse_error)
                    a.require(error <= 1e-12, "Independent float64 reduction mismatch")
                else:
                    a.require(value == saved["metrics"][key], f"Independent selection metric differs: {key}")
            a.require(saved['metrics']['gain_mse_denominator']=='all reached source groups, including empty-gain groups as zero'
                      and saved['metrics']['ensemble_mean_arithmetic']=='float64 of member float probabilities','Selection arithmetic metadata')
            a.require(saved["metrics"]["episode_ids"] == expected_ids and saved["metrics"]["planned_slot_ids"] == expected_slots, "Selection source order")
            a.require(saved["metrics"]["selected_candidates"] == [CANDIDATES[s] for s in metrics["selected_slots"]], "Selected candidate names")
            a.require(saved in result["compared_checkpoints"], "Result omitted checkpoint record")
            records.append(dict(path=path,step=step,metrics=metrics))
    a.require(len(result['compared_checkpoints'])==14,'Expected fourteen compared ensemble checkpoints')
    a.require(len(list(directory.glob('*/member_*/step_*/selected.pt')))==56,'Expected exactly56 trained checkpoints')
    a.require(len(list(directory.glob('*/development_step_*.json')))==14,'Expected exactly14 ensemble selection files')
    chosen = max(records,key=selection_key)
    saved_chosen=max(result['compared_checkpoints'],key=selection_key)
    a.require((chosen['path'],chosen['step'])==(saved_chosen['path'],saved_chosen['step']),'Exact selection key differs across independent/scalar reductions')
    a.require((chosen["path"],chosen["step"]) == (result["selection"]["path"],result["selection"]["step"]), "Independent selected checkpoint differs")
    a.require(result["selection"] == read(directory/chosen["path"]/f"development_step_{chosen['step']}.json"), "Selected record differs from its checkpoint metrics")
    selected_dir = directory/"selected"
    a.require(Path(result["selected_assets"]).resolve() == selected_dir.resolve(), "Selected export path")
    a.seal(selected_dir)
    ranking = read(selected_dir/"ranking.json")
    a.require(ranking["model_hashes"] == result["model_hashes"] and len(ranking["model_hashes"]) == 4, "Selected hashes")
    a.require(ranking["provenance"]["selection"] == result["selection"], "Export selection provenance")
    for member in range(4):
        selected_path = selected_dir/f"models/refit/member_{member}/selected.pt"
        a.file(selected_path,ranking["model_hashes"][str(member)])
        selected = torch.load(selected_path,map_location="cpu",weights_only=True)
        expected = states[(chosen["path"],member,chosen["step"])]
        a.require(set(selected) == set(expected) and all(equal_tensor(selected[k],expected[k]) for k in selected), "Selected export differs from trained checkpoint")
    reload = read(directory/"selected_reload_audit.json")
    a.require(reload["status"] == "passed" and reload["source_count"] == 95
              and reload["episode_ids"] == [r["episode_id"] for r in dev_rows], "Reload evidence coverage")
    a.require(reload["gradient_slots"] == [0,11] and reload["members_checked"] == 4, "Reload member/gradient coverage")
    for field in ("feature_cache_bit_exact","thirteen_candidate_member_probability_bit_exact",
                  "member_and_ensemble_gradient_bit_exact","a0_anchor_exactly_zero","state_and_anchor_immutable"):
        a.require(reload[field] is True, f"Reload evidence failed: {field}")
    a.require(result['optimizer_attempt_numbers']==resources['attempt_numbers'],'Execution and member update list differ')
    for path in ('A','B'):
        for purpose,expected_count in [('train',600),('development',95)]:
            audit_record=pref['reload_audits'][path][purpose]
            expected_sources=source_sets[purpose]['effective_episode_ids']
            a.require(audit_record['status']=='passed' and audit_record['source_count']==expected_count
                      and audit_record['episode_ids']==expected_sources and audit_record['members_checked']==4
                      and audit_record['gradient_slots']==[0,11],'Preflight canonical coverage')
            for key in ('feature_cache_bit_exact','thirteen_candidate_member_probability_bit_exact',
                        'member_and_ensemble_gradient_bit_exact','a0_anchor_exactly_zero','state_and_anchor_immutable'):
                a.require(audit_record[key] is True,'Preflight canonical evidence: '+key)
    a.require((ROOT/'budget/attempts.jsonl').read_bytes()==ledger_live_before,'Readonly audit changed/overlapped budget activity')
    for artifact in (directory/'complete.json',execution/'complete.json',pre/'complete.json'):
        a.require(digest(artifact)==a.input_hashes[str(artifact.resolve())],'Completed seal changed during audit')
    report=dict(status='passed',role='independent_final_post_training_artifact_audit',created_utc=datetime.now(timezone.utc).isoformat(),
        model_version=model_version,model_directory=str(directory),execution_directory=str(execution),checks_passed=a.checks,
        audit_code_sha256=digest(__file__),reused_audit_helper_sha256=digest(Path(__file__).with_name('training_result_audit_v1.py')),
        inputs=a.input_hashes,optimizer_updates_verified=32000,unique_update_ids=32000,updates_per_member=4000,
        compared_ensemble_checkpoints=14,checkpoint_state_dicts_checked=56,initial_state_dicts_checked=8,selected_exports_checked=4,
        model_instances_created=0,model_forward_calls=0,gradient_calls=0,pca_calls=0,simulator_calls=0,optimizer_updates_by_auditor=0,
        torch_state_dict_load_only=True,torch_threads=torch.get_num_threads(),numpy_version=np.__version__,torch_version=str(torch.__version__),
        executable=str(Path(sys.executable).resolve()),python=sys.version,members=members,
        resource_delta=resources,budget_snapshot_sha256=digest_bytes(ledger_bytes),budget_live_before_sha256=digest_bytes(ledger_live_before),
        budget_live_after_sha256=digest_bytes(ledger_live_before),budget_unchanged_by_auditor=True,
        selection_recomputed=records,independent_selection=chosen,selected_record=result['selection'],model_hashes=result['model_hashes'],
        planned_development=100,reached_development=95,known_no_cut_development=5,
        max_numpy_vs_torch_gain_mse_difference=max_mse_error,independent_metric_reduction_tolerance=1e-12,
        numeric_tolerance_note='Only existing NumPy/Torch scalar reduction comparison; exact checkpoint keys never use this tolerance.',
        recorded_selected_reload_audit=reload,reload_forward_or_gradient_independently_rerun=False,
        preprocessing_reused_without_refitting=True,all_actual_minibatches_equal_sealed_plans=True,
        cost=dict(training=result['cost'],execution={k:receipt[k] for k in ('wall_seconds','verification_seconds','max_process_rss_kib','started_utc','finished_utc')},
                  auditor=dict(wall_seconds=time.perf_counter()-begin,cpu_seconds=time.process_time()-cpu,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)),
        limitations=['Final selection is the frozen development candidate-bank proxy; it is not independent policy validation.',
                     'Production strict probability/gradient reload evidence was verified as sealed metadata, not rerun.',
                     'No new comparison rule, scientific threshold, PCA, inference, model or optimizer was run by this audit.'])
    destination.mkdir(parents=True,exist_ok=False)
    (destination/'budget_snapshot.jsonl').write_bytes(ledger_bytes)
    (destination/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    lines=['最终 A/B 训练只读交付审计','',f"审计通过：32000 条更新身份逐项不重不漏，8 成员各4000步；14 个 ensemble 检查点、56 个成员检查点以及4个 selected 导出均已核验。",'',
        f"封存选模结果为 {chosen['path']} / step {chosen['step']}；独立按原精确优先序重算一致。开发集固定100源×4后缀，包括95个cut和5个共同结局；未改变筛选规则。",'',
        '| 路径 | 步数 | 开发候选选择增益 pp | 救回 | 损害 | gain MSE |','| --- | --- | --- | --- | --- | --- |']
    for record in records:
        m=record['metrics'];lines.append(f"| {record['path']} | {record['step']} | {100*m['gain']:.2f} | {m['rescues']} | {m['harms']} | {m['gain_mse']:.10f} |")
    lines+=['','sealed PCA、8初态、bootstrap、参数mask、4000×32实际minibatch序列均一致。全部冻结参数/预处理buffer逐字节保持，selected导出等于选定训练检查点。',
        '','selected_reload_audit 已封存的元数据覆盖95源、13概率、槽0/11四成员及ensemble梯度；审计未重新运行模型或梯度。',
        '',f"训练本体墙钟 {result['cost']['wall_seconds']:.2f}s、CPU {result['cost']['cpu_seconds']:.2f}s；含入口验证执行墙钟 {receipt['wall_seconds']:.2f}s。完整成本在audit.json，不据此推断跨硬件加速。",'',
        '本次审计新增模型实例/forward、PCA、梯度、仿真和优化更新均为0，仅读取CPU state_dict。开发候选库选择不是独立验证成功，也不是实际flow纠偏部署效果。', '',
        '[完整审计记录](audit.json)；输入代码、数据、模型和封存文件 SHA 清单保存在 inputs。']
    (destination/'report.md').write_text('\n'.join(lines)+'\n')
    (destination/'complete.json').write_text(json.dumps(dict(status='complete',role=report['role'],files={p.name:digest(p) for p in destination.iterdir() if p.is_file()}),indent=2)+'\n')
    return dict(status='passed',path=str(destination),seal_sha256=digest(destination/'complete.json'),checks_passed=a.checks,
                selection={'path':chosen['path'],'step':chosen['step']})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'final_fit_protocols/final_fit_v1/config.json')
    parser.add_argument('--freeze',type=Path,default=ROOT/'final_fit_protocols/final_fit_v1/freeze.json')
    parser.add_argument('--model-version',default='final_fit_v1');parser.add_argument('--output-version',default='final_fit_v1')
    parser.add_argument('--status-only',action='store_true');args=parser.parse_args()
    if args.status_only:
        model,execution,missing=completed_paths(args.model_version)
        result=dict(status='ready_for_postseal_audit' if not missing else 'not_complete',missing_seals=missing,intermediate_results_read=False)
    else:result=audit(args.config,args.freeze,args.model_version,args.output_version)
    print(json.dumps(result,ensure_ascii=False))
