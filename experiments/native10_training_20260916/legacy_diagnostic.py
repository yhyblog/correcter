"""Prepared, NOT executed: old native50 dual-implementation diagnostics.

``run(config, ledger, case_indices=[0, 1, 2])`` is an explicit GPU entry point;
the caller must use the GPU lifecycle launcher and the frozen P0 ready checks.
Importing this module or calling inspect_reference_cases does not load models or
create a simulator. All writes and attempt charges belong to the new workflow.
Never call either legacy engine's capture/prepare_bank/branch/collect methods.

These outcome-exposed examples diagnose implementation equivalence only. They
are not native10 effectiveness data and never enter a new held-out denominator.
"""
from __future__ import annotations

from copy import deepcopy
import gc
import hashlib
import importlib
import json
from pathlib import Path
import time

import numpy as np

from .protocol import require_stage_budget
from .storage import ROOT, PACKAGE, arrays, dump, seal, sha256


LEGACY_ROOT = PACKAGE.parent / "ACT-RECAP/outputs/act_recap_ogg_flow_20260916"
CASE_IDS = (
    "shelf-place-v3__2026104012",
    "stick-pull-v3__2026104028",
    "disassemble-v3__2026104005",
)
IMPLEMENTATIONS = {
    "act": "ac_tmil.ogg_flow.collection",
    "corrector": "experiments.metaworld_small.collection",
}
METHODS = ("replan", "velocity_matched", "direct_matched", "post_matched",
           "reverse_matched", "random_matched", "velocity_native", "direct_native")
ROLLOUT_METHODS = ("replan", "post_matched")
REPEATS = (0, 1)
PHYSICS_ATOL = 1e-10
DIAGNOSTIC_LABEL = "old_native50_implementation_equivalence_not_native10_effectiveness"


def _read(path):
    return json.loads(Path(path).read_text())


def _digest(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _verified_seal(folder, config_sha256):
    """Read and verify old artifacts without importing their writer helpers."""
    folder = Path(folder).resolve()
    meta = _read(folder / "complete.json")
    if meta.get("config_sha256") != config_sha256 or not meta.get("files"):
        raise ValueError(f"Missing/inconsistent archived seal: {folder}")
    hashes = {str(folder / "complete.json"): sha256(folder / "complete.json")}
    for name, expected in meta["files"].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder) or sha256(path) != expected:
            raise ValueError(f"Archived file changed or escaped its directory: {path}")
        hashes[str(path)] = expected
    return hashes


def inspect_reference_cases():
    """CPU/read-only reference audit. Fixed source IDs and old repeats, no sampling."""
    cfg_path = LEGACY_ROOT / "config.json"
    cfg = _read(cfg_path)
    cfg_sha = sha256(cfg_path)
    if _read(LEGACY_ROOT / "config.identity.json").get("sha256") != cfg_sha:
        raise ValueError("Legacy config identity mismatch")
    if tuple(cfg["methods"]) != METHODS or cfg["prefix_steps"] != 10 or cfg["control_budget"] != 300:
        raise ValueError("Unexpected old flow protocol")
    expected_namespaces = {"candidate_seed_namespace": "ogg_flow_replan",
                           "suffix_seed_namespace": "ogg_flow_suffix",
                           "random_seed_namespace": "ogg_flow_random"}
    if any(cfg.get(key) != value for key, value in expected_namespaces.items()):
        raise ValueError("Historical random namespaces changed")
    records = []
    for index, case_id in enumerate(CASE_IDS):
        matches = [case for case in cfg["cases"] if case["case_id"] == case_id]
        if len(matches) != 1 or matches[0]["source_horizon"] != 50 or matches[0]["split"] != "development":
            raise ValueError(f"Expected a unique archived native50 source: {case_id}")
        case = matches[0]
        source = LEGACY_ROOT / "sources/single" / case_id
        protected = {str(cfg_path): cfg_sha,
                     str(LEGACY_ROOT / "config.identity.json"): sha256(LEGACY_ROOT / "config.identity.json")}
        protected.update(_verified_seal(source, cfg_sha))
        cuts = _read(source / "summary.json")["cuts"]
        if len(cuts) != 1:
            raise ValueError(f"Expected exactly one old cut: {case_id}")
        cut = int(cuts[0])
        branch_root = LEGACY_ROOT / "rollouts/development" / case_id / f"cut{cut:03d}"
        bank = branch_root / "candidates"
        protected.update(_verified_seal(bank, cfg_sha))
        historical = {}
        for method in ROLLOUT_METHODS:
            values = []
            for repeat in range(8):
                branch = branch_root / method / f"replicate_{repeat}"
                summary = _read(branch / "summary.json")
                values.append(int(summary["success"]))
                if repeat in REPEATS:
                    protected.update(_verified_seal(branch, cfg_sha))
            historical[method] = values
        gain = (sum(historical["post_matched"]) - sum(historical["replan"])) / 8
        if (index < 2 and gain <= 0) or (index == 2 and gain > 0):
            raise ValueError("Fixed diagnostic example does not meet its historical positive/nonpositive role")
        for path in (LEGACY_ROOT / "budget/attempts.jsonl",
                     PACKAGE / "outputs/metaworld_small_20260916/budget/attempts.jsonl"):
            if path.exists():
                protected[str(path)] = sha256(path)
        records.append(dict(index=index, case=case, source=str(source), cut=cut,
                            bank=str(bank), branch_root=str(branch_root),
                            role="exposed_positive" if index < 2 else "exposed_nonpositive",
                            historical_counts={key: sum(value) for key, value in historical.items()},
                            historical_replicates=8, historical_post_gain=gain,
                            input_hashes=protected))
    return dict(diagnostic=DIAGNOSTIC_LABEL, diagnostic_only=True,
                native10_effectiveness_evidence=False, config=cfg, config_sha256=cfg_sha,
                records=records, full_run_new_attempts=30,
                selection_note="4005 is the fixed exposed nonpositive example; 4000 has historical +0.25 post gain and is not used.")


def _unchanged(hashes):
    for name, expected in hashes.items():
        if sha256(name) != expected:
            raise ValueError(f"Read-only legacy input was modified: {name}")


def _load_arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key].copy() for key in archive.files}


def _array_comparison(left, right, *, physics=False):
    same_layout = left.shape == right.shape and left.dtype == right.dtype
    bit_exact = bool(same_layout and left.tobytes(order="C") == right.tobytes(order="C"))
    allowed = bool(same_layout and np.allclose(left, right, rtol=0, atol=PHYSICS_ATOL)) if physics else bit_exact
    report = dict(passed=allowed, bit_exact=bit_exact,
                  left_shape=list(left.shape), right_shape=list(right.shape),
                  left_dtype=str(left.dtype), right_dtype=str(right.dtype),
                  absolute_tolerance=PHYSICS_ATOL if physics else 0.)
    if same_layout and left.dtype.kind in "fc" and left.size:
        report["max_abs_error"] = float(np.max(np.abs(left.astype(np.float64) - right.astype(np.float64))))
    return report


def _compare_npz(left_path, right_path, *, physics_key=None):
    left, right = _load_arrays(left_path), _load_arrays(right_path)
    checks = {"keys": {"passed": set(left) == set(right), "left": sorted(left), "right": sorted(right)}}
    for key in sorted(set(left) & set(right)):
        checks[key] = _array_comparison(left[key], right[key], physics=key == physics_key)
    return checks


def _exact_json(left, right):
    # Includes signed-zero spelling. Runtime/memory costs are never passed here.
    kwargs = dict(sort_keys=True, separators=(",", ":"), allow_nan=False)
    return json.dumps(left, **kwargs) == json.dumps(right, **kwargs)


def _proposal_numerics(stats):
    return {key: stats[key] for key in ("policy_calls", "fallback", "updates", "times",
                                        "objective_forward_calls", "backward_calls")}


def _generation_numerics(meta):
    return dict(base_seed=meta["base_seed"], noise_hashes=meta["noise_hashes"],
                matching=meta["matching"], predictions=meta["predictions"],
                base_generation=_proposal_numerics(meta["base_generation"]),
                guidance={key: _proposal_numerics(value) for key, value in meta["guidance"].items()},
                post_gradient={key: value for key, value in meta["post_gradient"].items() if key != "seconds"})


def _comparison_result(kind, checks):
    return dict(kind=kind, status="passed" if all(check["passed"] for check in checks.values()) else "failed",
                passed=all(check["passed"] for check in checks.values()), checks=checks,
                diagnostic_only=True, native10_effectiveness_evidence=False,
                wall_time_and_memory_excluded_from_bitexact=True, physics_atol=PHYSICS_ATOL)


def _compare_generation(left, right):
    left, right = Path(left), Path(right)
    checks = {}
    for name in ("plans.npz", "directions.npz"):
        checks.update({f"{name}:{key}": value for key, value in _compare_npz(left/name, right/name).items()})
    if (left/"intermediates.npz").exists() and (right/"intermediates.npz").exists():
        checks.update({f"intermediates:{key}": value for key, value in _compare_npz(left/"intermediates.npz", right/"intermediates.npz").items()})
    a, b = _generation_numerics(_read(left/"generation.json")), _generation_numerics(_read(right/"generation.json"))
    for key in a:
        checks[key] = dict(passed=_exact_json(a[key], b[key]))
    return _comparison_result("regenerated_candidate_bank", checks)


def _compare_branch(left, right):
    left, right = Path(left), Path(right)
    checks = _compare_npz(left/"trajectory.npz", right/"trajectory.npz", physics_key="physics_states")
    a, b = _read(left/"summary.json"), _read(right/"summary.json")
    for key in ("case_id", "task", "env_seed", "step", "horizon", "method", "replicate",
                "success", "terminal_step", "actual_prefix_steps", "budget_truncated", "suffix_seeds",
                "suffix_policy_calls", "endpoint_image_sha256", "commands_sha256", "continuation"):
        checks["summary:"+key] = dict(passed=_exact_json(a[key], b[key]))
    return _comparison_result("replayed_prefix_and_real_suffix", checks)


def _record_comparison(path, result):
    dump(path, result)
    if not result["passed"]:
        failed = [key for key, item in result["checks"].items() if not item["passed"]]
        raise ValueError(f"Legacy implementation comparison failed at {path}: {failed}")


def _generate(engine, module, reference, cfg, dest, attempt, protocol_sha):
    case, cut, source = reference["case"], reference["cut"], Path(reference["source"])
    dump(dest/"attempt.json", attempt)
    start = time.perf_counter()
    trace, anchor = engine.restore(case, source, cut)
    restore_seconds = time.perf_counter()-start
    before = engine.runtime.fingerprint()
    source_context = source / f"cut{cut:03d}/context.npz"
    with np.load(source_context, allow_pickle=False) as archive:
        observed = {key: archive[key].copy() for key in module.STATE_KEYS}
    seed = module.seed_for(cfg["candidate_seed_namespace"], case["env_seed"], cut)
    raw_base, base_stats = engine.propose(seed)
    base = np.clip(raw_base, -1, 1).astype(np.float32)
    noises = {"replan": engine.hook.last_noise_sha}
    objective = module.FrozenObjective(observed, base, selector=engine.selector)
    generated, raw_generated, stats = {}, {}, {}
    for mode in ("velocity", "direct"):
        engine.hook.settings["mode"] = mode
        raw_generated[mode], stats[mode] = engine.propose(seed, objective)
        generated[mode] = np.clip(raw_generated[mode], -1, 1).astype(np.float32)
        noises[mode] = engine.hook.last_noise_sha
    if len(set(noises.values())) != 1 or noises["replan"] is None:
        raise ValueError("Dual diagnostic did not preserve shared a0/flow noise")
    tick = time.perf_counter()
    gradient, gradient_stats = objective.gradient()
    slopes = ((engine.transform.q99-engine.transform.q01)/2).detach().cpu().numpy()
    post_direction = gradient.numpy()*slopes[None]**2
    gradient_stats.update(seconds=time.perf_counter()-tick, transform_slopes=slopes.tolist(),
                          metric="S squared command gradient")
    plans, matching = module.construct(base, generated["velocity"], generated["direct"], post_direction,
        module.seed_for(cfg["random_seed_namespace"], case["env_seed"], cut), cfg["matching"])
    if set(plans) != set(METHODS):
        raise ValueError("Unexpected candidate set in historical diagnostic")
    predictions = {name: objective.evaluate(plans[name][:10]) for name in METHODS}
    if predictions["replan"]["mean_gain"] != 0:
        raise ValueError("Legacy a0 anchor changed")
    base_probs = np.array(predictions["replan"]["member_probabilities"])[:, 0]
    for name in METHODS:
        np.testing.assert_array_equal(np.array(predictions[name]["member_probabilities"])[:, 0], base_probs)
    objective.verify();engine.verify();engine.selector.verify()
    if engine.runtime.fingerprint() != before:
        raise ValueError("Legacy candidate-only generation stepped the environment")
    arrays(dest/"plans.npz", **plans)
    arrays(dest/"directions.npz", post_command_gradient=gradient.numpy(), post_internal_metric_direction=post_direction)
    arrays(dest/"intermediates.npz", raw_a0=raw_base, raw_velocity=raw_generated["velocity"],
           raw_direct=raw_generated["direct"], restored_physics=engine.runtime.physics_state(),
           restored_raw_source_plan=_load_arrays(source_context)["full_plan"])
    metadata = dict(case_id=case["case_id"], step=cut, base_seed=seed,
        base_generation=base_stats, guidance=stats, matching=matching, predictions=predictions,
        post_gradient=gradient_stats, noise_hashes=noises, objective_stats=objective.stats(),
        context_sha256=sha256(source_context), source_anchor_sha256=sha256(source/f"cut{cut:03d}/anchor.json"),
        source_plan_age=anchor["plan_age"], source_horizon=50, restored_prefix_steps=trace.step,
        restore_seconds=restore_seconds, wall_seconds=time.perf_counter()-start,
        saved_before_any_branch=True, budget_attempt=attempt["number"], diagnostic=DIAGNOSTIC_LABEL,
        historical_protocol_sha256=sha256(LEGACY_ROOT/"config.json"))
    dump(dest/"generation.json", metadata)
    seal(dest, protocol_sha256=protocol_sha, diagnostic_only=True)
    return plans


def _branch(engine, module, reference, cfg, method, plan, repeat, dest, attempt, protocol_sha):
    """Historical ten-step bounded prefix/fixed10 suffix; never legacy branch()."""
    case, cut, source = reference["case"], reference["cut"], Path(reference["source"])
    dump(dest/"attempt.json", attempt)
    begin = time.perf_counter()
    trace, _ = engine.restore(case, source, cut)
    replay_seconds = time.perf_counter()-begin
    runtime = engine.runtime
    for command in plan[:10]:
        if trace.terminal or trace.step >= 300:
            break
        trace.execute(runtime, command)
    length = trace.step-cut
    if length <= 0:
        raise ValueError("Empty historical intervention prefix")
    endpoint = _digest(runtime.frame())
    runtime.clear_policy(10)
    suffix = []
    while not trace.terminal and trace.step < 300:
        step, index = trace.step, len(suffix)
        seed = module.seed_for(cfg["suffix_seed_namespace"], case["env_seed"], cut, repeat, index)
        calls = trace.policy_calls
        trace.native(runtime, seed)
        if trace.policy_calls != calls:
            suffix.append(dict(step=step, decision_index=index, seed=seed))
    arrays(dest/"trajectory.npz", **trace.arrays())
    row = dict(status="complete", case_id=case["case_id"], task=case["task"], env_seed=case["env_seed"],
        step=cut, horizon=10, method=method, replicate=repeat, success=bool(any(trace.successes)),
        terminal_step=trace.step, actual_prefix_steps=length, budget_truncated=cut+10>300,
        suffix_seeds=suffix, suffix_policy_calls=trace.policy_calls, suffix_policy_seconds=trace.policy_seconds,
        replay_seconds=replay_seconds, environment_seconds=trace.environment_seconds,
        wall_seconds=time.perf_counter()-begin, endpoint_image_sha256=endpoint,
        commands_sha256=_digest(plan[:10]), continuation="clear_queue_then_fixed10_v1",
        control_hz=30, physics_hz=400, action_scale=.015, budget_attempt=attempt["number"],
        diagnostic=DIAGNOSTIC_LABEL, diagnostic_only=True, native10_effectiveness_evidence=False,
        source_horizon=50, restore_included_in_attempt=True)
    dump(dest/"summary.json", row)
    engine.verify();engine.selector.verify()
    seal(dest, protocol_sha256=protocol_sha, diagnostic_only=True)


def run(config, ledger, case_indices=None):
    """Explicit, counted P0 GPU entry point; separate GPUs may select disjoint cases.

    Each case uses sequential ACT/Corrector engines: two generation+restore
    attempts and eight branch+restore attempts, ten in total. Existing output is
    never overwritten or silently resumed. Failed attempts stay in the ledger.
    """
    require_stage_budget(config, "p0")
    if case_indices is None:
        case_indices = list(range(len(CASE_IDS)))
    if not case_indices or any(type(i) is not int or i < 0 or i >= len(CASE_IDS) for i in case_indices) or len(set(case_indices)) != len(case_indices):
        raise ValueError("Select unique fixed diagnostic case indices from 0,1,2")
    reference = inspect_reference_cases()
    cfg = reference["config"]
    protocol_sha = config["analysis_approval"]["protocol_sha256"]
    # Guard against legacy config() falling back to its writer on missing files.
    for path in (PACKAGE.parent/"ACT-RECAP/outputs/act_recap_ogg_20260915/config.json",
                 LEGACY_ROOT/"config.json", PACKAGE/"outputs/metaworld_small_20260916/config.json"):
        if not path.is_file():
            raise FileNotFoundError(f"Required read-only legacy config is absent: {path}")
    import torch
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(4)
    reports = []
    try:
        for index in case_indices:
            item = reference["records"][index]
            case_id = item["case"]["case_id"]
            dest = ROOT/"diagnostics/legacy"/case_id
            if dest.exists():
                raise FileExistsError(f"Preserve prior diagnostic attempt; do not overwrite: {dest}")
            dest.mkdir(parents=True, exist_ok=False)
            dump(dest/"registration.json", dict(diagnostic=DIAGNOSTIC_LABEL, diagnostic_only=True,
                native10_effectiveness_evidence=False, selected_reference=item,
                implementations=IMPLEMENTATIONS, methods=list(ROLLOUT_METHODS), repeats=list(REPEATS),
                expected_new_attempts=10, source_horizon=50, intervention_prefix=10, suffix_horizon=10,
                old_namespaces={key: cfg[key] for key in ("candidate_seed_namespace", "random_seed_namespace", "suffix_seed_namespace")},
                old_guidance=cfg["guidance"], old_matching=cfg["matching"], physics_atol=PHYSICS_ATOL,
                other_arrays_and_numerical_metadata_bit_exact=True, protocol_sha256=protocol_sha,
                code_sha256=sha256(Path(__file__))))
            attempts = []
            comparisons = []
            try:
                for implementation, module_name in IMPLEMENTATIONS.items():
                    engine = None
                    attempt = ledger.reserve("p0", "legacy_generation_including_restore", f"{case_id}:{implementation}:generation")
                    attempts.append(attempt["number"])
                    module = importlib.import_module(module_name)
                    try:
                        engine = module.FlowEngine()
                        engine.study = deepcopy(cfg)
                        engine.hook.settings.clear()
                        engine.hook.settings.update(dict(cfg["guidance"], mode="velocity"))
                        out = dest/implementation
                        plans = _generate(engine, module, item, cfg, out/"generation", attempt, protocol_sha)
                        name = f"{implementation}_generation_vs_archive.json"
                        _record_comparison(dest/"comparisons"/name, _compare_generation(out/"generation", item["bank"]))
                        comparisons.append(name)
                        for method in ROLLOUT_METHODS:
                            for repeat in REPEATS:
                                branch = out/"rollouts"/method/f"replicate_{repeat}"
                                attempt = ledger.reserve("p0", "legacy_branch_including_restore", f"{case_id}:{implementation}:{method}:{repeat}")
                                attempts.append(attempt["number"])
                                _branch(engine, module, item, cfg, method, plans[method], repeat, branch, attempt, protocol_sha)
                                archived = Path(item["branch_root"])/method/f"replicate_{repeat}"
                                name = f"{implementation}_{method}_{repeat}_vs_archive.json"
                                _record_comparison(dest/"comparisons"/name, _compare_branch(branch, archived))
                                comparisons.append(name)
                    finally:
                        if engine is not None:
                            engine.close()
                            del engine
                        gc.collect()
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                name = "act_vs_corrector_generation.json"
                _record_comparison(dest/"comparisons"/name,
                                   _compare_generation(dest/"act/generation", dest/"corrector/generation"))
                comparisons.append(name)
                for method in ROLLOUT_METHODS:
                    for repeat in REPEATS:
                        suffix = Path("rollouts")/method/f"replicate_{repeat}"
                        name = f"act_vs_corrector_{method}_{repeat}.json"
                        _record_comparison(dest/"comparisons"/name, _compare_branch(dest/"act"/suffix, dest/"corrector"/suffix))
                        comparisons.append(name)
                _unchanged(item["input_hashes"])
                if len(attempts) != 10 or len(set(attempts)) != 10:
                    raise ValueError("Unexpected legacy diagnostic attempt accounting")
                result = dict(status="passed", all_passed=True, case_id=case_id,
                    diagnostic_only=True, native10_effectiveness_evidence=False, diagnostic=DIAGNOSTIC_LABEL,
                    new_attempts=len(attempts), attempt_numbers=attempts, comparisons=comparisons,
                    archived_inputs_unchanged=True, expected_comparisons=15, physics_atol=PHYSICS_ATOL,
                    selected_role=item["role"], protocol_sha256=protocol_sha)
                dump(dest/"result.json", result)
                seal(dest, protocol_sha256=protocol_sha, diagnostic_only=True)
                reports.append(result)
            except BaseException as error:
                dump(dest/"failure.json", dict(status="failed", error_type=type(error).__name__, error=str(error),
                    attempt_numbers=attempts, diagnostic_only=True, native10_effectiveness_evidence=False,
                    protocol_sha256=protocol_sha))
                raise
    finally:
        torch.set_num_threads(previous_threads)
    return dict(status="passed", diagnostic_only=True, native10_effectiveness_evidence=False, cases=reports)
