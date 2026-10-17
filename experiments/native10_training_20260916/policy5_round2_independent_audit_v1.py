"""Post-completion independent policy5 aggregation, without model/simulator calls.

Only stdlib and NumPy are imported. No production audit/summary function is called.
Adapted from the separately implemented first policy audit; seven statistical rules
remain identical. This module never reads or compares old policy outcomes.
All 100 collection seals must exist before any source/branch outcome is read.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT/"outputs/native10_training_20260916"
METHODS = ("continue_native10", "alarm_replan10", "velocity", "direct", "post")
PAIRS = ((1,0),(2,1),(3,1),(4,1),(2,0),(3,0),(4,0))
STAGE = "round2_development_policy"
BOOTSTRAP_SEED = 2026091622
BOOTSTRAP_DRAWS = 10000


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(2**20),b""):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
                                    ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def suffix_seed(namespace, episode_id, cut, repeat, index):
    return int(canonical(["native10_seed_v1",namespace,"branch_suffix_decision",
                          episode_id,cut,repeat,index])[:16],16) % (2**63-1)


class Checks:
    def __init__(self):
        self.count = 0
        self.hashes = {}

    def require(self, ok, message):
        self.count += 1
        if not ok:
            raise ValueError(message)

    def file(self,path,expected=None):
        path=Path(path).resolve();actual=sha(path)
        if expected is not None:
            self.require(actual==expected,"SHA mismatch: "+str(path))
        self.hashes[str(path)]=actual
        return actual

    def seal(self,directory,expected=None,protocol=None):
        directory=Path(directory).resolve()
        digest=self.file(directory/"complete.json",expected)
        value=read(directory/"complete.json")
        self.require(value.get("status")=="complete","Incomplete seal: "+str(directory))
        if protocol is not None:
            self.require(value.get("protocol_sha256")==protocol,"Seal protocol mismatch")
        files=value["files"]
        actual={str(p.relative_to(directory)) for p in directory.rglob("*")
                if p.is_file() and p!=directory/"complete.json"}
        self.require(actual==set(files),"Sealed inventory mismatch: "+str(directory))
        for filename,expected_hash in files.items():
            path=(directory/filename).resolve()
            self.require(path.is_relative_to(directory),"Sealed path escape")
            self.file(path,expected_hash)
        return digest


def comparison(candidate,baseline,bootstrap_indices=None):
    c=np.asarray(candidate,dtype=np.int8);b=np.asarray(baseline,dtype=np.int8)
    delta=(c-b).sum(axis=1,dtype=np.int64)/4.
    result=dict(gain=float(delta.mean()),rescues=int(np.count_nonzero((c==1)&(b==0))),
        harms=int(np.count_nonzero((c==0)&(b==1))),positive_sources=int(np.count_nonzero(delta>0)),
        negative_sources=int(np.count_nonzero(delta<0)),zero_sources=int(np.count_nonzero(delta==0)))
    if bootstrap_indices is not None:
        means=delta[bootstrap_indices].mean(axis=1)
        result["source_95ci"]=np.quantile(means,[.025,.975],method="linear").tolist()
    return result


def aggregate(labels,rows,task_order,*,draws=BOOTSTRAP_DRAWS):
    """Independent whole-source bootstrap, with all paired arms/repeats intact."""
    y=np.asarray(labels)
    if y.shape!=(len(rows),5,4) or not np.isin(y,[0,1]).all() or not len(rows):
        raise ValueError("Expected complete sources x five arms x four repeats")
    if len({r["episode_id"] for r in rows})!=len(rows):
        raise ValueError("Duplicate source")
    tasks=np.asarray([r["task"] for r in rows]);rng=np.random.default_rng(BOOTSTRAP_SEED)
    drawn=[]
    for task in task_order:
        indices=np.flatnonzero(tasks==task)
        if not len(indices):raise ValueError("Empty registered task")
        drawn.append(rng.choice(indices,size=(draws,len(indices)),replace=True))
    bootstrap=np.concatenate(drawn,axis=1)
    def group(mask):
        data=y[mask]
        if not len(data):return dict(sources=0)
        counts=data.sum(axis=(0,2),dtype=np.int64)
        return dict(sources=len(data),logical_outcomes_per_arm=len(data)*4,
            success_counts=dict(zip(METHODS,counts.tolist())),
            success_rates=dict(zip(METHODS,(counts/(len(data)*4)).tolist())))
    comparisons={METHODS[a]+"_minus_"+METHODS[b]:comparison(y[:,a],y[:,b],bootstrap) for a,b in PAIRS}
    no_cut=np.asarray([r["no_cut"] for r in rows],dtype=bool)
    per_task={task:group(tasks==task) for task in task_order}
    per_task_comparisons={task:{METHODS[a]+"_minus_"+METHODS[b]:comparison(y[tasks==task,a],y[tasks==task,b])
                               for a,b in PAIRS} for task in task_order}
    return dict(overall=group(np.ones(len(rows),dtype=bool)),comparisons=comparisons,
        per_task=per_task,per_task_comparisons=per_task_comparisons,
        alarm_conditioned=group(~no_cut),no_cut_common_outcomes=group(no_cut),
        bootstrap=dict(seed=BOOTSTRAP_SEED,replicates=draws,unit="episode/source",stratification="task",
                       task_order=list(task_order),source_order=[r["episode_id"] for r in rows],
                       quantile_method="linear",interval="percentile",multiplicity_adjusted=False,
                       suffix_repeats_independent=False),independent_validation_success=False)


def command_diagnostics(plans, directions, formal, matching):
    """Independent raw-command and bounded-critic arithmetic, without a model."""
    if set(plans) != set(METHODS[1:]):
        raise ValueError('Exactly four generated command plans required')
    raw=plans['alarm_replan10'];mask=formal['mask'];tol=float(matching['tolerance'])
    if (raw.shape!=(50,4) or raw.dtype!=np.dtype('float32') or not np.isfinite(raw).all()
            or mask.shape!=(10,4) or mask.dtype!=np.dtype('bool') or not 0<tol<=1e-5):
        raise ValueError('Invalid raw anchor, mask or frozen tolerance')
    equal=lambda a,b: a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()
    if not equal(mask,1-np.abs(np.clip(raw[:10],-1,1).astype(float))>=matching['boundary_clearance']):
        raise ValueError('Mask differs from the frozen feasible-coordinate rule')
    if not equal(formal['raw_a0'],raw) or not equal(directions['raw_a0'],raw):
        raise ValueError('Raw anchor differs from directions')
    if (not equal(directions['critic_a0'],np.clip(raw,-1,1))
            or not equal(directions['critic_candidates'],np.stack([np.clip(plans[n],-1,1) for n in METHODS[1:]]))):
        raise ValueError('Critic mapping differs from C(raw)')
    rows={};groups={}
    for name in METHODS[1:]:
        plan=plans[name]
        if plan.shape!=(50,4) or plan.dtype!=np.dtype('float32') or not np.isfinite(plan).all():
            raise ValueError('Invalid final command plan')
        if not equal(plan[10:],raw[10:]) or not equal(plan[:10][~mask],raw[:10][~mask]):
            raise ValueError('Command tail or masked coordinates changed')
        delta=plan[:10].astype(float)-raw[:10].astype(float)
        proxy=np.clip(plan[:10],-1,1).astype(float)-np.clip(raw[:10],-1,1).astype(float)
        if np.max(np.abs(proxy-delta))>tol:
            raise ValueError('Actual raw delta differs from the critic proxy delta')
        metrics={}
        for group,values in [('xyz',delta[:,:3]),('gripper',delta[:,3:])]:
            metrics[group+'_rms']=float(np.sqrt(np.mean(values**2)))
            metrics[group+'_linf']=float(np.max(np.abs(values)))
        if any(value>matching[key]+tol for key,value in metrics.items()):
            raise ValueError('Executed command perturbation exceeds a frozen cap')
        key=plan.tobytes();alias=groups.setdefault(key,name)
        rows[name]=dict(**metrics,raw_alias_of=alias,aliases_replan=equal(plan,raw),
                       raw_outside_unit_fraction=float((np.abs(plan[:10])>1).mean()))
    for group in ('xyz','gripper'):
        values=[rows[name][group+'_rms'] for name in METHODS[2:]]
        if max(values)-min(values)>tol:
            raise ValueError('Executed V/D/P command RMS is not matched')
    return dict(status='passed',methods=rows,raw_distinct_groups=len(groups),
                modifiable_coordinates=int(mask.sum()),modifiable_xyz_coordinates=int(mask[:,:3].sum()),
                modifiable_gripper_coordinates=int(mask[:,3].sum()),tolerance=tol,
                tail_and_mask_bit_exact=True,critic_mapping_bit_exact=True,
                comparison='within this new five-arm wave only; no cross-round pairing claim')


def audit(config_path,bank_version,output_version,primary_audit=None):
    c=Checks();config_path=Path(config_path).resolve();cfg=read(config_path)
    destination=ROOT/"policy5_independent_audits"/output_version
    c.require(destination.resolve().parent==(ROOT/"policy5_independent_audits").resolve(),"Unsafe output version")
    c.require(not destination.exists(),"Independent output must be new")
    bank=cfg["main_collection"]["banks"][bank_version];ids=bank["episode_ids"]
    c.require(bank["stage"]==STAGE and bank["kind"]=="policy5" and bank['generation_round']==2
              and len(ids)==len(set(ids))==100,"Expected complete registered round2 policy5 bank")
    collections=[ROOT/"collections"/STAGE/bank_version/identity for identity in ids]
    # Gate does not open a source or branch summary, nor compute partial effects.
    missing=[identity for identity,path in zip(ids,collections) if not (path/"complete.json").is_file()]
    c.require(not missing,f"Wait for every registered collection before outcomes: {len(missing)} incomplete")
    c.require(primary_audit is not None, "Completed primary audit is mandatory before outcomes")
    primary_audit=Path(primary_audit).resolve()
    c.require((primary_audit.parent/"complete.json").is_file(),"Wait for the complete primary audit seal")
    c.seal(primary_audit.parent)
    primary=read(primary_audit)
    c.require(primary.get("status")=="passed" and primary.get("stage")==STAGE
              and primary.get("bank_version")==bank_version,"Completed round2 primary audit required")
    c.require(primary.get('config_content_sha256')==canonical(cfg),'Primary audit config identity')
    protocol=cfg["analysis_approval"]["protocol_sha256"]
    for path in collections:c.seal(path,protocol=protocol)
    frozen=read(config_path.with_name("freeze.json"));c.file(config_path.with_name("freeze.json"))
    c.file(config_path,frozen["config_sha256"])
    ready=read(cfg["analysis_ready"]["path"]);c.file(cfg["analysis_ready"]["path"],cfg["analysis_ready"]["sha256"])
    approved=ready[STAGE]
    c.require(ready["version"]==11 and STAGE in ready["released_scope"],"READY11 release required")
    c.require(ids==approved["episode_ids"] and canonical(ids)==approved["episode_ids_canonical_sha256"],"READY source identity")
    c.require(cfg["methods"]==list(METHODS) and cfg["budget"]["stages"][STAGE]==dict(simulator_attempts=2100,training_updates=0),"Method/budget contract")
    stats=cfg["policy_statistics"]
    c.require(stats["bootstrap_draws"]==BOOTSTRAP_DRAWS and stats["bootstrap_seed"]==BOOTSTRAP_SEED
              and stats["ci"]=="percentile95" and stats["quantile_method"]=="linear" and stats["source_order"]==ids,"Statistics contract")
    lookup={row["episode_id"]:row for row in cfg["episode_manifest"]}
    c.require(all(lookup[x]["split"]=="development" and not lookup[x].get("replacement_of") for x in ids),"Only original dev slots")
    c.require(dict(Counter(lookup[x]["task"] for x in ids))==approved["per_task_source_counts"],"Task coverage")
    binding=cfg["policy_deployment"];original=read(binding["old_collection"]["config_path"])
    c.require(binding.get('schema')=='native10_policy_deployment_round2_v1','Original source and final teacher must be separate identities')
    c.file(binding["old_collection"]["config_path"],binding["old_collection"]["config_sha256"])
    old_protocol=original["analysis_approval"]["protocol_sha256"]
    selected=Path(cfg["critic_assets"]);c.seal(selected,approved["selected_critic"]["selected_seal"]["sha256"])
    ranking=read(selected/"ranking.json")
    c.require(ranking["model_hashes"]==bank["critic_member_hashes"],"Selected critic hashes")
    c.require((ranking["provenance"]["selection"]["path"],ranking["provenance"]["selection"]["step"])==("A",4000),"Fixed final A4000 selection")
    c.require(binding['selected_training']==primary['selected_training'],'Primary final training binding')
    for field in ('training_model_seal','selected_seal','selected_reload_audit','model_review'):
        ref=approved['selected_critic'][field];c.file(ref['path'],ref['sha256'])
    ledger_bytes=(ROOT/"budget/attempts.jsonl").read_bytes()
    ledger=[json.loads(line) for line in ledger_bytes.splitlines()];by_number={row["number"]:row for row in ledger}
    c.require(len(by_number)==len(ledger),"Global ledger ID duplicate")
    charged=[row for row in ledger if row["stage"]==STAGE]
    c.require(all(row["resource"]=="simulator_attempts" and row["amount"]==1 for row in charged),"Policy contains optimizer/nonunit charges")
    attempts=[]
    def charge(directory,summary,kind):
        saved=read(directory/"attempt.json");n=saved["number"]
        c.require(saved==by_number[n] and summary["budget_attempt"]==n,"Attempt record mismatch")
        c.require(saved["stage"]==STAGE and saved["kind"]==kind and saved["resource"]=="simulator_attempts"
                  and saved["amount"]==1 and saved["protocol_sha256"]==protocol
                  and saved["identity"]==str(directory.relative_to(ROOT)),"Attempt provenance mismatch")
        attempts.append(n)
    rows,labels,scenes=[],[],set();suffix_count=0
    for identity,collection_path in zip(ids,collections):
        perturbation=None;predictions=None;fallback=None
        case=lookup[identity];bound=binding["source_bindings"][identity];source=ROOT/"sources"/identity
        c.seal(source,bound["source_seal_sha256"],old_protocol);source_summary=read(source/"summary.json")
        collection=read(collection_path/"summary.json")
        c.require(source_summary["case"]==case and collection["case"]==case,"Source/case identity")
        c.require(collection["status"]=="complete" and collection["methods"]==list(METHODS)
                  and collection["replicates"]==4 and collection["logical_branch_count"]==20,"Collection methods/completion")
        c.require(collection["model_hashes"]==bank["model_hashes"] and collection["critic_member_hashes"]==bank["critic_member_hashes"]
                  and collection["source_seal_sha256"]==bound["source_seal_sha256"]
                  and collection["protocol_sha256"]==protocol,"Collection source/model protocol")
        c.require(collection["planned_episode_retained"] is True and collection["outcome_filter_applied"] is False
                  and collection["source_replaced"] is False,"Source selection/replacement")
        c.require(collection["cuts"]==source_summary["cuts"] and collection["no_cut"]==(not source_summary["cuts"]),"Original cut mismatch")
        scene=(case["task"],source_summary["scene_fingerprint"])
        c.require(scene not in scenes,"Repeated physical task scene");scenes.add(scene)
        outcomes=np.empty((5,4),bool)
        if source_summary["cuts"]:
            cut,=source_summary["cuts"]
            c.require(case["cut_rule"]==dict(kind="first_alarm") and cut==source_summary["first_legal_alarm_step"],"Development cut must be original first alarm")
            bank_path=ROOT/"banks"/bank_version/identity/f"cut{cut:03d}"
            bank_sha=c.seal(bank_path,protocol=protocol);generation=read(bank_path/"generation.json")
            c.require(generation["episode_id"]==identity and generation["cut_step"]==cut
                      and generation["model_hashes"]==bank["model_hashes"] and generation["source_seal_sha256"]==bound["source_seal_sha256"],"Bank provenance")
            c.require(collection["candidate_bank_sha256"]==bank_sha,"Collection bank seal")
            def npz(name):
                with np.load(bank_path/name,allow_pickle=False) as archive:
                    return {key:archive[key] for key in archive.files}
            perturbation=command_diagnostics(npz('plans.npz'),npz('directions.npz'),
                                             npz('formal_directions.npz'),cfg['matching'])
            predictions=generation['bank_predictions']
            c.require(set(predictions)==set(METHODS[1:])
                      and predictions['alarm_replan10']['mean_gain']==0,'Fixed a0 prediction anchor')
            fallback=dict(replan=generation['base_generation'].get('fallback'),
                          **{mode:generation['guidance'][mode].get('fallback') for mode in ('velocity','direct')},
                          matching=generation.get('matching'))
            charge(bank_path,generation,"candidate_restore")
            records={(x["method"],x["repeat"]):x for x in collection["branch_records"]}
            c.require(len(collection["branch_records"])==len(records)==collection["actual_branch_count"]==20
                      and set(records)=={(method,repeat) for method in METHODS for repeat in range(4)},"Incomplete five-arm branch records")
            shared_noise={};command_hashes={}
            for arm,method in enumerate(METHODS):
                for repeat in range(4):
                    branch=ROOT/"rollouts"/STAGE/bank_version/identity/f"cut{cut:03d}"/method/f"repeat_{repeat}"
                    record=records[(method,repeat)];c.seal(branch,record["seal_sha256"],protocol)
                    row=read(branch/"summary.json")
                    c.require(Path(record["summary_path"]).resolve()==(branch/"summary.json").resolve(),"Branch record path")
                    expected=dict(episode_id=identity,task=case["task"],env_seed=case["env_seed"],split="development",
                        method=method,candidate_name=method,repeat=repeat,cut_step=cut,status="complete",protocol_sha256=protocol,
                        model_hashes=bank["model_hashes"],critic_member_hashes=bank["critic_member_hashes"],
                        source_seal_sha256=bound["source_seal_sha256"],candidate_bank_sha256=bank_sha,
                        suffix_seed_namespace=cfg["seed_namespace"],paired_suffix_id=f"{identity}:cut{cut}:repeat{repeat}")
                    c.require(all(row.get(k)==v for k,v in expected.items()),"Branch identity/model/pairing")
                    c.require(type(row["success"]) is bool and all(record[k]==row[k] for k in ("success","budget_attempt","command_sha256")),"Branch success/reference mismatch")
                    c.require(row["source_horizon"]==row["suffix_horizon"]==10 and row["generated_horizon"]==50
                              and row["normalized_queue_injection"] is False and row["restore_included_in_attempt"] is True
                              and row["physical_outcome_reused"] is False,"Branch native10/restore semantics")
                    requested=row["original_queue_remaining"] if arm==0 else 10
                    c.require(row["requested_prefix_steps"]==requested and 0<=row["actual_prefix_steps"]<=requested,"Native queue or intervention prefix")
                    c.require(row["execution_role"]==("continue_native10" if arm==0 else "alarm_replan10"),"Execution role")
                    if method in command_hashes:c.require(row["command_sha256"]==command_hashes[method],"Prefix plan changed across repeats")
                    command_hashes[method]=row["command_sha256"]
                    for index,decision in enumerate(row["suffix_seeds"]):
                        c.require(type(decision["decision_index"]) is int and decision["decision_index"]==index,"Skipped/repeated suffix index")
                        c.require(decision["seed"]==suffix_seed(cfg["seed_namespace"],identity,cut,repeat,index),"Independent suffix seed reconstruction")
                        noise=decision["noise_sha256"];key=(repeat,index)
                        c.require(isinstance(noise,str) and len(noise)==64 and (key not in shared_noise or shared_noise[key]==noise),"Cross-arm paired noise mismatch")
                        shared_noise[key]=noise;suffix_count+=1
                    charge(branch,row,"branch_including_restore")
                    outcomes[arm,repeat]=row["success"]
        else:
            cut=None
            c.require(source_summary["no_alarm"] is True and source_summary["full_episode_outcome_available"] is True
                      and type(source_summary["success"]) is bool,"No-alarm outcome unavailable")
            c.require(collection["actual_branch_count"]==0 and collection["branch_records"]==[]
                      and collection["common_outcome_available"] is True and collection["common_outcome"]==source_summary["success"],"No-cut denominator changed")
            outcomes[:]=source_summary["success"]
        rows.append(dict(episode_id=identity,task=case["task"],env_seed=case["env_seed"],no_cut=cut is None,
                         actual_cut=cut,scene_fingerprint=scene[1],
                         command_diagnostics=perturbation,bank_predictions=predictions,generation_fallback=fallback,
                         comparisons={METHODS[a]+'_minus_'+METHODS[b]:comparison(
                             outcomes[None,a],outcomes[None,b]) for a,b in PAIRS},
                         paired_outcomes={method:outcomes[i].tolist() for i,method in enumerate(METHODS)},
                         success_counts=dict(zip(METHODS,outcomes.sum(1).tolist()))))
        labels.append(outcomes)
    c.require(len(attempts)==len(set(attempts))==1995 and set(attempts)=={x["number"] for x in charged},"Unaccounted/duplicate/extra policy attempts")
    kinds=Counter(x["kind"] for x in charged)
    c.require(kinds==Counter(candidate_restore=95,branch_including_restore=1900),"Policy charge breakdown")
    c.require(sum(r["no_cut"] for r in rows)==5 and len(scenes)==100,"Scene or no-cut coverage")
    c.require(sum(bool(y[0,0]) for y,r in zip(labels,rows) if r['no_cut'])==4,
              'The original five common outcomes must retain four successes and one failure')
    labels=np.stack(labels);statistics=aggregate(labels,rows,stats["task_order"])
    primary_comparison=dict(performed=False)
    if primary_audit is not None:
        c.seal(primary_audit.parent)
        c.file(primary_audit);primary=read(primary_audit)
        c.require(primary["status"]=="passed" and primary["planned_slots"]==100 and primary["new_attempts"]==1995,"Primary audit coverage")
        c.require(primary["stage"]==STAGE and primary["bank_version"]==bank_version,"Primary audit stage")
        for key in ("overall","comparisons","per_task","alarm_conditioned","no_cut_common_outcomes"):
            c.require(statistics[key]==primary["statistics"][key],"Independent statistics differ: "+key)
        c.require([r["episode_id"] for r in primary["per_source"]]==ids,"Primary source ordering")
        c.require(all(a["paired_outcomes"]==b["paired_outcomes"] for a,b in zip(rows,primary["per_source"])),"Primary per-repeat outcomes differ")
        primary_comparison=dict(performed=True,exact=True,path=str(Path(primary_audit).resolve()),sha256=sha(primary_audit))
    result=dict(status="passed",role="independent_complete_round2_policy5_reaggregation",created_utc=datetime.now(timezone.utc).isoformat(),
        code_sha256=sha(__file__),config_sha256=sha(config_path),cross_round_pairing_claim=False,stage=STAGE,bank_version=bank_version,
        checks_passed=c.count,planned_slots=100,reached_sources=95,unique_task_scenes=100,
        registered_source_order=ids,model_hashes=ranking["model_hashes"],new_policy_attempts=1995,
        policy_attempts_by_kind=dict(kinds),policy_attempt_numbers=attempts,suffix_seed_records_checked=suffix_count,
        recorded_resource_totals={r:sum(x["amount"] for x in ledger if x["resource"]==r) for r in {x["resource"] for x in ledger}},
        artifacts=c.hashes,statistics=statistics,per_source=rows,primary_audit_comparison=primary_comparison,
        budget_snapshot_sha256=hashlib.sha256(ledger_bytes).hexdigest(),numpy_version=np.__version__,
        simulator_calls=0,model_calls=0,optimizer_updates=0,partial_outcomes_read=False,
        independent_validation_success=False,
        limitations=["Independent implementation recomputes outcomes/statistics/seed identities from sealed raw summaries.",
                     "Raw command RMS/caps/masks/tails/critic mapping are independently checked; full physical trajectory/source-anchor equivalence is handled by the sealed production audit, without simulator replay.",
                     "No old policy outcomes are loaded; identical source IDs do not establish cross-round causal pairing.",
                     "Seven unadjusted development comparisons are descriptive, not heldout confirmation.",
                     "Four suffixes share one source; bootstrap resamples complete sources within tasks."])
    destination.mkdir(parents=True,exist_ok=False)
    (destination/"budget_snapshot.jsonl").write_bytes(ledger_bytes)
    np.savez_compressed(destination/"paired_outcomes.npz",outcomes=labels,episode_ids=np.asarray(ids),methods=np.asarray(METHODS))
    (destination/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    lines=["# Independent complete policy5 reaggregation","","All100 sources are complete; 95 alarm cuts and five known common outcomes retain 400 logical outcomes per arm.","",
           "| Arm | Successes /400 | Success rate |","|---|---:|---:|"]
    for method in METHODS:
        o=statistics["overall"];lines.append(f"| {method} | {o['success_counts'][method]} | {100*o['success_rates'][method]:.2f}% |")
    lines += ["","| Comparison | Gain pp | Source95% CI pp | Rescues | Harms | + / − / zero sources |","|---|---:|---|---:|---:|---|"]
    for name,value in statistics["comparisons"].items():
        lo,hi=value['source_95ci'];lines.append(f"| {name} | {100*value['gain']:.2f} | [{100*lo:.2f}, {100*hi:.2f}] | {value['rescues']} | {value['harms']} | {value['positive_sources']} / {value['negative_sources']} / {value['zero_sources']} |")
    lines += ["","Task-stratified whole-source bootstrap: 10,000 draws, seed2026091622, NumPy default_rng.choice, linear percentile95% intervals. No multiplicity correction. This is development evaluation, not independent heldout validation.","",
              "Verified 95 bank restores +1,900 paired branches =1,995 unique policy attempts. This read-only audit performs zero model/simulator/optimizer calls. See result.json for exact source order, input hashes, per-task/source outcomes and primary-audit comparison."]
    (destination/"report.md").write_text("\n".join(lines)+"\n")
    files={p.name:sha(p) for p in destination.iterdir() if p.is_file()}
    (destination/"complete.json").write_text(json.dumps(dict(status="complete",role=result["role"],files=files),indent=2)+"\n")
    return dict(status="passed",path=str(destination),checks_passed=c.count,primary_audit_comparison=primary_comparison)


def self_test():
    y=np.zeros((4,5,4),bool);y[0,2]=True;y[1,1,:2]=True;y[3]=True
    rows=[dict(episode_id=f"synthetic{i}",task=f"task{i//2}",no_cut=i==3) for i in range(4)]
    result=aggregate(y,rows,["task0","task1"],draws=100)
    value=result["comparisons"]["velocity_minus_alarm_replan10"]
    assert value["rescues"]==4 and value["harms"]==2 and value["gain"]==2/16
    assert (value["positive_sources"],value["negative_sources"],value["zero_sources"])==(1,1,2)
    assert result["overall"]["sources"]==4 and result["no_cut_common_outcomes"]["sources"]==1
    assert result==aggregate(y,rows,["task0","task1"],draws=100)
    assert len(result["comparisons"])==7
    return dict(status="passed",synthetic_only=True,model_calls=0,simulator_calls=0,optimizer_updates=0)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=ROOT/"policy_protocols/round2_policy_v1/config.json")
    parser.add_argument("--bank",default="round2_policy_v1")
    parser.add_argument("--output-version",default="round2_policy_v1_independent")
    parser.add_argument("--primary-audit",type=Path)
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    print(json.dumps(self_test() if args.self_test else audit(args.config,args.bank,args.output_version,args.primary_audit),ensure_ascii=False))
