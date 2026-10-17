"""Independent, post-seal round1 audit: tensor reads and NumPy only, no forward.

Does not import the training pipeline, model classes, simulator or optimizers.
Existing numerical reload evidence is verified, never silently rerun.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import torch


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT / "outputs/native10_training_20260916"
STEPS = (200, 400, 800, 1600, 2400)
CANDIDATES = ("a0", "xyz_positive", "xyz_negative", "gripper_positive",
              "gripper_negative", "random_half_positive", "random_half_negative",
              "random_full_positive", "random_full_negative", "velocity", "direct",
              "post", "reverse_post")


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def seed(namespace, *identity):
    value = json.dumps(["native10_seed_v1", namespace, *identity], sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return int(digest_bytes(value.encode())[:16], 16) % (2**63 - 1)


def equal_tensor(a, b):
    return (a.dtype == b.dtype and a.shape == b.shape
            and a.detach().contiguous().numpy().tobytes() == b.detach().contiguous().numpy().tobytes())


def selection_metrics(probabilities, outcomes, reached, gain_weights):
    """Independent implementation of registered, source-normalized selection."""
    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(outcomes, dtype=np.float64)
    mask = np.asarray(reached, dtype=bool)
    if p.shape != (4, len(y), 13) or y.shape != (len(mask), 13, 4):
        raise ValueError("Incomplete selection shapes")
    if not np.isfinite(p[:, mask]).all() or not np.isin(y, [0, 1]).all():
        raise ValueError("Invalid probabilities/outcomes")
    if np.any(p[:, mask] < 0) or np.any(p[:, mask] > 1):
        raise ValueError("Probabilities outside [0,1]")
    if not np.array_equal(y[~mask], np.broadcast_to(y[~mask, :1, :1], y[~mask].shape)):
        raise ValueError("No-cut sources must retain shared known outcomes")
    mean = np.where(mask[None, :, None], p, 0.).mean(axis=0)
    slots = np.argmax(mean, axis=1)
    slots[~mask] = 0
    selected = y[np.arange(len(y)), slots]
    base = y[:, 0]
    rescues = int(np.count_nonzero((selected == 1) & (base == 0)))
    harms = int(np.count_nonzero((selected == 0) & (base == 1)))
    weights = np.asarray(gain_weights, dtype=np.float64)
    error = ((mean - mean[:, :1]) - (y.mean(2) - y[:, :1].mean(2)))**2
    source_mse = (error * weights).sum(1) / np.where(weights.sum(1) > 0, weights.sum(1), 1.)
    return dict(planned_episodes=len(y), reached_episodes=int(mask.sum()),
                gain=(rescues-harms)/(len(y)*4), rescues=rescues, harms=harms,
                baseline_success=float(base.mean()), selected_success=float(selected.mean()),
                gain_mse=float(source_mse[mask].mean()) if mask.any() else 0.,
                selected_slots=slots.tolist(),
                gain_conditional=(rescues-harms)/(int(mask.sum())*4) if mask.any() else None)


def selection_key(record):
    m = record["metrics"]
    return (m["gain"], -m["harms"], -m["gain_mse"], -record["step"], record["path"] == "B")


class Audit:
    def __init__(self):
        self.checks = 0
        self.input_hashes = {}

    def require(self, condition, message):
        self.checks += 1
        if not condition:
            raise ValueError(message)

    def file(self, path, expected=None):
        path = Path(path).resolve()
        actual = digest(path)
        if expected is not None:
            self.require(actual == expected, f"SHA mismatch: {path}")
        self.input_hashes[str(path)] = actual
        return actual

    def seal(self, directory, expected=None):
        directory = Path(directory).resolve()
        self.file(directory/"complete.json", expected)
        data = read(directory/"complete.json")
        self.require(data.get("status") == "complete", f"Not complete: {directory}")
        actual = {str(p.relative_to(directory)) for p in directory.rglob("*")
                  if p.is_file() and p != directory/"complete.json"}
        self.require(actual == set(data["files"]), f"Seal file list changed: {directory}")
        for name, expected in data["files"].items():
            path = (directory/name).resolve()
            self.require(path.is_relative_to(directory), "Seal path escaped")
            self.file(path, expected)
        return data


def reconstruct_bootstrap(rows, tasks, random_seed):
    rng = np.random.default_rng(random_seed)
    indices, per_task = [], {}
    for task in tasks:
        group = np.asarray([i for i, row in enumerate(rows) if row["task"] == task], dtype=np.int64)
        chosen = rng.choice(group, size=len(group), replace=True).tolist()
        indices.extend(chosen)
        per_task[task] = dict(unique_available=len(group), drawn=len(chosen))
    ids = [rows[i]["episode_id"] for i in indices]
    return dict(seed=random_seed, indices=indices, episode_ids=ids,
                multiplicities=dict(Counter(ids)), per_task=per_task,
                source_grouped=True, outcome_weighting=False)


def audit(config_path, model_version, output_version):
    torch.set_num_threads(2)
    torch.set_num_interop_threads(2)
    a = Audit()
    config_path = Path(config_path).resolve()
    config = read(config_path)
    specification = config["training_pipeline"]
    directory = ROOT/"models/round1"/model_version
    destination = ROOT/"training_audits"/output_version
    a.require(directory.resolve().parent == (ROOT/"models/round1").resolve(), "Unsafe model version")
    a.require(destination.resolve().parent == (ROOT/"training_audits").resolve(), "Unsafe output version")
    a.require(not destination.exists(), "Audit output is exclusive; use a new version")
    # Fail before reading incomplete model results or writing anything.
    seal = a.seal(directory)
    a.require(seal.get("role") == "native10_two_path_training", "Wrong completed model role")
    result, registration = read(directory/"result.json"), read(directory/"registration.json")
    freeze = read(config_path.parent/"freeze.json")
    a.file(config_path.parent/"freeze.json")
    for filename, expected in freeze["files"].items():
        a.file(filename, expected)
    a.file(freeze["code_snapshot"]["path"], freeze["code_snapshot"]["sha256"])
    a.file(config_path, freeze["config_sha256"])
    a.require(result["status"] == "complete" and result["phase"] == "round1", "Wrong result status/phase")
    a.require(result["version"] == model_version, "Model version mismatch")
    a.require(result["optimizer_updates"] == 19200, "Expected exactly19200 optimizer updates")
    a.require(result["real_policy_evaluation_performed"] is False, "Unexpected policy rollout claim")
    a.require(result["independent_validation_success"] is False, "Unsupported validation claim")
    for key in ("design", "dataset_bindings", "coverage", "preflight_binding", "config_protocol_sha256"):
        a.require(result[key] == registration[key], f"Registration mismatch: {key}")
    a.require(result["config_protocol_sha256"] == config["analysis_approval"]["protocol_sha256"], "Wrong protocol")
    a.require(config["budget"]["stages"]["training_round1"] == dict(simulator_attempts=0, training_updates=19200), "Training budget")
    a.require(specification["stop_after"]["round1"] == dict(A=2400, B=2400), "Stops changed")
    ready = read(config["analysis_ready"]["path"])
    a.file(config["analysis_ready"]["path"], config["analysis_ready"]["sha256"])
    a.require(ready["version"] == 6 and "round1_critic_training" in ready["released_scope"], "Training not released by READYv6")
    a.require(config["stage_release_scopes"]["training_round1"] == "round1_critic_training", "Wrong scope")
    for stage in ("round1_development_policy", "round2_labels", "calibration", "heldout", "training_final"):
        a.require(config["stage_release_scopes"][stage] not in ready["released_scope"], "Unexpected future scope")
    pre = Path(specification["preflight"]["round1"]["path"])
    a.seal(pre, specification["preflight"]["round1"]["seal_sha256"])
    pref = read(pre/"result.json")
    for key, value in {"design": specification["design"], "dataset_bindings": specification["datasets"]["round1"],
                       "code_files": specification["code_files"], "stop_after": specification["stop_after"]["round1"]}.items():
        a.require(pref[key] == value, f"Preflight identity mismatch: {key}")
    masks, sampling = read(pre/"trainable_masks.json"), read(pre/"sampling.json")
    bindings = specification["datasets"]["round1"]
    for binding in bindings.values():
        a.seal(Path(binding["path"]), binding["seal_sha256"])
        a.file(binding["input_audit_path"], binding["input_audit_sha256"])
    train_rows = read(Path(bindings["train"]["path"])/"rows.json")
    dev_dir = Path(bindings["development"]["path"])
    dev_rows, dev_metadata = read(dev_dir/"rows.json"), read(dev_dir/"metadata.json")
    a.require(len(train_rows) == 300 and all(r["split"] == "train" and r["round"] == 1 for r in train_rows), "Training split")
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
    ledger_bytes = (ROOT/"budget/attempts.jsonl").read_bytes()
    ledger = [json.loads(line) for line in ledger_bytes.splitlines()]
    ledger_index = {row["number"]: row for row in ledger}
    a.require(len(ledger_index) == len(ledger), "Duplicate global ledger ID")
    training_ledger = [row for row in ledger if row["stage"] == "training_round1"]
    a.require(len(training_ledger) == 19200, "Training stage attempts differ")
    a.require(all(row["resource"] == "training_updates" and row["amount"] == 1 for row in training_ledger), "Invalid training resource")
    updates, members, states = [], [], {}
    for path in ("A", "B"):
        a.seal(pre/path/"initial")
        for member in range(4):
            member_dir = directory/path/f"member_{member}"
            fit = read(member_dir/"fit.json")
            a.require((fit["phase"],fit["path"],fit["member"],fit["updates"]) == ("round1",path,member,2400), "Fit identity")
            a.require(fit["source_ids"] == [row["episode_id"] for row in train_rows], "Fit source identities")
            a.require(fit["normal_control_used_in_critic"] is False and fit["calibration_or_heldout_used"] is False, "Forbidden training sources")
            boot_seed = seed(config["seed_namespace"], "training_bootstrap", "round1", path, member)
            batch_seed = seed(config["seed_namespace"], "training_minibatches", "round1", path, member)
            bootstrap = reconstruct_bootstrap(train_rows, config["tasks"], boot_seed)
            a.require(fit["bootstrap"] == sampling[path][member]["bootstrap"] == bootstrap, "Bootstrap mismatch")
            a.require(fit["batch_seed"] == sampling[path][member]["batch_seed"] == batch_seed, "Minibatch seed mismatch")
            pool = np.asarray(bootstrap["indices"],np.int64)
            rng = np.random.default_rng(batch_seed)
            batches = np.stack([pool[rng.integers(0,len(pool),32)] for _ in range(2400)])
            a.require(np.array_equal(batches, np.asarray(fit["minibatches"])), "Minibatch reconstruction mismatch")
            ids = fit["attempt_numbers"]
            a.require(len(ids) == len(set(ids)) == 2400, "Fit update IDs")
            for step, number in enumerate(ids, 1):
                row = ledger_index[number]
                a.require(row["stage"] == "training_round1" and row["kind"] == "critic_optimizer_update"
                          and row["identity"] == f"{model_version}:round1:{path}:{member}:{step}"
                          and row["protocol_sha256"] == result["config_protocol_sha256"]
                          and row["resource"] == "training_updates" and row["amount"] == 1, "Update ledger identity")
            updates.extend(ids)
            initial_path = pre/path/"initial/models/refit"/f"member_{member}"/"selected.pt"
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
            changed_counts = {}
            for step in STEPS:
                checkpoint_dir = member_dir/f"step_{step}"
                metadata = read(checkpoint_dir/"metadata.json")
                cp = checkpoint_dir/"selected.pt"
                a.require(Path(metadata["checkpoint"]["path"]).resolve() == cp.resolve(), "Checkpoint metadata path")
                a.file(cp, metadata["checkpoint"]["sha256"])
                a.require(metadata["init_seed"] == pref["initialization_seeds"][path][member], "Initialization identity")
                a.require(metadata["dataset_binding"] == bindings["development"], "Checkpoint development binding")
                state = torch.load(cp,map_location="cpu",weights_only=True)
                a.require(set(state) == set(initial), "Checkpoint state schema")
                changed = []
                for name, value in state.items():
                    a.require(value.device.type == "cpu" and value.dtype == initial[name].dtype
                              and value.shape == initial[name].shape and torch.isfinite(value).all().item(), "Nonfinite/schema checkpoint")
                    if name not in trainable:
                        a.require(equal_tensor(value, initial[name]), f"Frozen value changed: {path}/{member}/{step}/{name}")
                    elif not equal_tensor(value, initial[name]):
                        changed.append(name)
                a.require(bool(changed), "No trainable parameter changed from preflight")
                changed_counts[str(step)] = len(changed)
                states[(path,member,step)] = state
            members.append(dict(path=path,member=member,updates=2400,bootstrap_exact=True,
                all_minibatches_exact=True,trainable_parameter_tensors=len(trainable),
                frozen_parameter_tensors=len(parameter_names)-len(trainable),frozen_buffer_tensors=len(buffer_names),
                changed_trainable_tensors_by_step=changed_counts,all_frozen_values_bit_exact=True))
    a.require(len(updates) == len(set(updates)) == 19200, "Eight fits overlap update IDs")
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
            a.require(saved["path"] == path and saved["step"] == step and saved["phase"] == "round1"
                      and saved["dataset_sha256"] == bindings["development"]["seal_sha256"], "Selection bank identity")
            for key, value in metrics.items():
                if key == "gain_mse":
                    error = abs(value-saved["metrics"][key]);max_mse_error=max(error,max_mse_error)
                    a.require(error <= 1e-12, "Independent float64 reduction mismatch")
                else:
                    a.require(value == saved["metrics"][key], f"Independent selection metric differs: {key}")
            a.require(saved["metrics"]["episode_ids"] == expected_ids and saved["metrics"]["planned_slot_ids"] == expected_slots, "Selection source order")
            a.require(saved["metrics"]["selected_candidates"] == [CANDIDATES[s] for s in metrics["selected_slots"]], "Selected candidate names")
            a.require(saved in result["compared_checkpoints"], "Result omitted checkpoint record")
            records.append(dict(path=path,step=step,metrics=metrics))
    a.require(len(result["compared_checkpoints"]) == 10, "Expected ten compared ensemble checkpoints")
    chosen = max(records,key=selection_key)
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
    # Confirm the completed model seal did not change during this audit.
    a.require(digest(directory/"complete.json") == a.input_hashes[str((directory/"complete.json").resolve())], "Model seal changed during audit")
    report = dict(status="passed",role="independent_post_training_artifact_audit",created_utc=datetime.now(timezone.utc).isoformat(),
        model_version=model_version,model_directory=str(directory),checks_passed=a.checks,
        audit_code_sha256=digest(__file__),inputs=a.input_hashes,
        optimizer_updates_verified=19200,unique_update_ids=19200,simulator_calls=0,optimizer_updates_by_auditor=0,
        model_forward_calls=0,torch_state_dict_load_only=True,torch_threads=torch.get_num_threads(),
        torch_interop_threads=torch.get_num_interop_threads(),numpy_version=np.__version__,torch_version=str(torch.__version__),
        budget_snapshot_sha256=digest_bytes(ledger_bytes),budget_snapshot_entries=len(ledger),
        budget_resource_totals=dict(Counter({resource:sum(x["amount"] for x in ledger if x["resource"] == resource)
                                            for resource in {x["resource"] for x in ledger}})),
        members=members,checkpoint_state_dicts_checked=40,selected_exports_checked=4,
        selection_recomputed=records,independent_selection=chosen,planned_development=100,reached_development=95,
        known_no_cut_development=5,max_numpy_vs_torch_gain_mse_difference=max_mse_error,
        independent_metric_reduction_tolerance=1e-12,
        numeric_tolerance_note="Only NumPy/Torch float64 scalar reduction comparison; model probability/gradient evidence retains original bit-exact rule.",
        recorded_selected_reload_audit=reload,reload_forward_or_gradient_independently_rerun=False,
        limitations=["This audit independently recomputes metrics from sealed predictions, not model forward outputs.",
                     "Probability and gradient reload evidence is verified from the sealed production audit; no forward/backward rerun.",
                     "Development candidate-bank selection is a proxy; no independent validation or actual policy-effectiveness claim."])
    destination.mkdir(parents=True,exist_ok=False)
    (destination/"budget_snapshot.jsonl").write_bytes(ledger_bytes)
    (destination/"audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    lines=["# Independent round1 training artifact audit", "", "Status: passed.", "",
           "Verified 19,200 unique optimizer updates, eight reconstructed source bootstraps and all minibatches; 40 checkpoints retain every frozen parameter and buffer bit-for-bit, and trainable tensors changed.", "",
           f"Independent selection: path {chosen['path']}, step {chosen['step']}. Full development denominator: 100 sources × 4 repeats, including 5 known no-cut sources.", "",
           "| Path | Step | Net gain (pp) | Rescues | Harms | Relative gain MSE |", "|---|---:|---:|---:|---:|---:|"]
    for record in records:
        m=record['metrics'];lines.append(f"| {record['path']} | {record['step']} | {100*m['gain']:.2f} | {m['rescues']} | {m['harms']} | {m['gain_mse']:.10f} |")
    lines += ["", "Selected exported tensors exactly equal the chosen trained checkpoints. The sealed production reload audit covers all 95 reached development sources, 13 probability slots, and gradient slots 0 and 11 for four members and the ensemble.", "",
              "This independent audit ran zero model forward calls, optimizer updates or simulator calls. It verifies the existing numerical reload evidence without rerunning gradients. Candidate-bank selection is not independent validation or actual flow-guidance effectiveness."]
    (destination/"report.md").write_text("\n".join(lines)+"\n")
    files={p.name:digest(p) for p in destination.iterdir() if p.is_file()}
    (destination/"complete.json").write_text(json.dumps(dict(status="complete",role=report["role"],files=files),indent=2)+"\n")
    return dict(status="passed",path=str(destination),checks_passed=a.checks,selection=dict(path=chosen["path"],step=chosen["step"]))


def self_test():
    torch.set_num_threads(2)
    torch.set_num_interop_threads(2)
    p=np.full((4,3,13),.5,np.float32);p[:,0,1]=.75;p[:,2]=np.nan
    y=np.zeros((3,13,4),bool);y[0,1,:2]=True;y[2]=True
    weights=np.ones((3,13),np.float32);weights[:,0]=0;weights[2]=0
    got=selection_metrics(p,y,[True,True,False],weights)
    assert got["selected_slots"] == [1,0,0]
    assert got["rescues"] == 2 and got["harms"] == 0 and got["gain"] == 2/12
    base=dict(gain=.1,harms=1,gain_mse=.2)
    records=[dict(path="A",step=400,metrics=base),dict(path="B",step=400,metrics=base),dict(path="A",step=200,metrics=base)]
    assert max(records,key=selection_key)["step"] == 200
    assert max(records[:2],key=selection_key)["path"] == "B"
    return dict(status="passed",synthetic_only=True,model_forward_calls=0,optimizer_updates=0,simulator_calls=0)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=ROOT/"fit_protocols/round1_fit_v1/config.json")
    parser.add_argument("--model-version",default="round1_fit_v1")
    parser.add_argument("--output-version",default="round1_fit_v1_new")
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    print(json.dumps(self_test() if args.self_test else audit(args.config,args.model_version,args.output_version),ensure_ascii=False))
