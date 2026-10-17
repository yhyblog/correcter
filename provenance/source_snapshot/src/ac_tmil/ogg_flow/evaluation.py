"""Sealed-command audit and paired whole-source flow mechanism evaluation.

Preflight audits expose technical checks and command/cost measurements only.
Development evaluation is a separate CLI operation, requires formal freezing,
and never chooses or modifies a method, strength, or acceptance rule.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path

import numpy as np

from ac_tmil.ogg.common import digest
from ac_tmil.ogg_research.statistics import estimate
from ac_tmil.ogg_research_v2.evaluation import sealed
from .candidates import construct, radii
from .common import ROOT, DOC, REPO, METHODS, MATCHED, V3, read, dump, file_sha256, seed_for


def _json(path):
    return json.loads(Path(path).read_text())


def _array_file(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: value.copy() for key, value in archive.items()}


def _numbers(values):
    values = np.asarray([value for value in values if value is not None], dtype=float)
    if not len(values):
        return dict(n=0, mean=None, min=None, max=None)
    assert np.isfinite(values).all()
    return dict(n=len(values), mean=float(values.mean()), min=float(values.min()),
                max=float(values.max()), median=float(np.median(values)))


def _budget():
    path = ROOT / "budget/attempts.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    assert len(rows) <= 3000
    assert [row["number"] for row in rows] == list(range(1, len(rows) + 1))
    identities = Counter(row["identity"] for row in rows)
    return dict(attempts=len(rows), hard_maximum=3000, remaining=3000-len(rows),
                by_kind=dict(Counter(row["kind"] for row in rows)),
                repeated_identity_attempts=sum(value-1 for value in identities.values()),
                ledger_sha256=file_sha256(path) if path.exists() else None,
                incomplete_and_failed_attempts_remain_counted=True), rows


def _frozen_dependencies(cfg, stage):
    ranking = read(V3 / "learning/ranking.json")
    assert file_sha256(V3 / "learning/ranking.json") == cfg["critic_ranking_sha256"]
    hashes = {}
    for member, expected in ranking["model_hashes"].items():
        path = V3 / f"learning/models/refit/member_{member}/selected.pt"
        actual = file_sha256(path)
        assert actual == expected
        hashes[str(path)] = actual
    prior = read(ROOT / "provenance/previous.json")
    for path, expected in prior["dependencies"].items():
        assert file_sha256(Path(path)) == expected, path
    if stage == "development":
        frozen = read(ROOT / "formal_freeze.json")
        assert frozen["config_sha256"] == file_sha256(ROOT / "config.json")
        assert frozen["development_sources_absent"]
        assert not frozen["preflight_outcomes_used_for_settings"]
        for name, expected in frozen["code_hashes"].items():
            assert file_sha256(REPO / name) == expected, name
    return dict(critic_model_sha256=hashes, dependencies_verified=len(prior["dependencies"]),
                ranking_sha256=cfg["critic_ranking_sha256"])


def check_branch(folder, plan, case, cut, rep, source, cfg):
    sealed(folder, ROOT / "config.json")
    summary = _json(folder / "summary.json")
    assert summary["case_id"] == case["case_id"] and summary["task"] == case["task"]
    assert (summary["step"], summary["horizon"], summary["replicate"]) == (cut, 10, rep)
    assert summary["method"] == folder.parent.name
    if "control_hz" in summary:
        assert (summary["control_hz"], summary["physics_hz"], summary["action_scale"]) == (30, 400, .015)
    trace = _array_file(folder / "trajectory.npz")
    length, terminal = summary["actual_prefix_steps"], summary["terminal_step"]
    assert 0 < length <= min(10, cfg["control_budget"]-cut)
    assert len(trace["actions"]) == terminal <= cfg["control_budget"]
    assert len(trace["physics_states"]) == terminal+1
    assert len(trace["done_flags"]) == len(trace["success_flags"]) == terminal
    assert np.isfinite(trace["actions"]).all() and np.isfinite(trace["physics_states"]).all()
    np.testing.assert_array_equal(trace["actions"][:cut], source["actions"][:cut])
    np.testing.assert_allclose(trace["physics_states"][:cut+1], source["physics_states"][:cut+1], atol=1e-10, rtol=0)
    np.testing.assert_array_equal(trace["actions"][cut:cut+length], plan[:length])
    if length < min(10, cfg["control_budget"]-cut):
        assert trace["done_flags"][cut+length-1]
    assert bool(trace["success_flags"].any()) == summary["success"]
    assert summary["commands_sha256"] == digest(plan[:10])
    sampling_steps = np.arange(cut+length, terminal, 10, dtype=np.int64)
    seeds = [seed_for(cfg["suffix_seed_namespace"], case["env_seed"], cut, rep, index)
             for index in range(len(sampling_steps))]
    np.testing.assert_array_equal(trace["actual_sampling_steps"], sampling_steps)
    np.testing.assert_array_equal(trace["generated_steps"], sampling_steps)
    np.testing.assert_array_equal(trace["actual_sampling_seeds"], seeds)
    assert len(trace["generated_plans"]) == len(seeds) == summary["suffix_policy_calls"]
    assert summary["suffix_seeds"] == [dict(step=int(step), decision_index=index, seed=seed)
                                         for index, (step, seed) in enumerate(zip(sampling_steps, seeds))]
    prefix = trace["physics_states"][cut:cut+length+1].copy()
    return summary, (prefix, summary["endpoint_image_sha256"])


def _matching(plans, generation, cfg):
    assert set(plans) == set(METHODS)
    a0 = plans["replan"][:10].astype(float)
    actual = {}
    for method, plan in plans.items():
        assert plan.shape == (50, 4) and plan.dtype == np.float32
        assert np.isfinite(plan).all() and np.abs(plan).max() <= 1
        actual[method] = radii(plan[:10].astype(float)-a0)
        for name, value in actual[method].items():
            assert abs(value-generation["matching"]["actual"][method][name]) < 1e-12
    tolerance = cfg["matching"]["tolerance"]
    mask = 1-np.abs(a0) >= cfg["matching"]["boundary_clearance"]
    np.testing.assert_array_equal(mask, generation["matching"]["mask"])
    for method in MATCHED:
        delta = plans[method][:10].astype(float)-a0
        assert np.max(np.abs(delta[~mask]), initial=0.) == 0.
        np.testing.assert_array_equal(plans[method][10:], plans["replan"][10:])
        for group in ("xyz", "gripper"):
            assert actual[method][group+"_linf"] <= cfg["matching"][group+"_linf"] + tolerance
            assert actual[method][group+"_rms"] <= cfg["matching"][group+"_rms"] + tolerance
            target = generation["matching"]["groups"][group]["achieved_target"]
            assert abs(actual[method][group+"_rms"]-target) < tolerance
    for group in ("xyz", "gripper"):
        measured = [actual[method][group+"_rms"] for method in MATCHED]
        assert max(measured)-min(measured) < tolerance
    assert np.max(np.abs(plans["direct_matched"][:10].astype(float)+plans["reverse_matched"][:10]-2*a0)) < tolerance
    return actual


def _generation_checks(generation, plans, cfg, case, cut, source, stage):
    assert generation["base_seed"] == seed_for(cfg["candidate_seed_namespace"], case["env_seed"], cut)
    assert generation["context_sha256"] == file_sha256(source / f"cut{cut:03d}/context.npz")
    assert set(generation["predictions"]) == set(METHODS)
    for method, prediction in generation["predictions"].items():
        q = np.asarray(prediction["member_probabilities"], dtype=float)
        assert q.shape == (4, 2) and np.isfinite(q).all() and (q >= 0).all() and (q <= 1).all()
        assert np.isclose(prediction["mean_gain"], (q[:, 1]-q[:, 0]).mean(), atol=2e-7, rtol=0)
        assert np.isclose(prediction["a0_mean_probability"], q[:, 0].mean(), atol=2e-7, rtol=0)
        assert np.isclose(prediction["candidate_mean_probability"], q[:, 1].mean(), atol=2e-7, rtol=0)
        np.testing.assert_array_equal(q[:, 0], np.asarray(generation["predictions"]["replan"]["member_probabilities"])[:, 0])
    assert generation["predictions"]["replan"]["mean_gain"] == 0.
    noise = generation["noise_hashes"]
    if isinstance(noise, dict):
        required = [noise[key] for key in ("replan", "velocity", "direct")]
    else:
        required = list(noise)
    assert len(required) >= 3 and len(set(required)) == 1 and required[0] is not None
    assert generation["saved_before_any_branch"]
    for mode in ("velocity", "direct"):
        stats = generation["guidance"][mode]
        if not stats.get("fallback"):
            np.testing.assert_allclose([item["tau"] for item in stats["updates"]], cfg["guidance"]["times"], atol=1e-6, rtol=0)
        for update in stats.get("updates", []):
            assert update["direct_gradient_outside_mask"] == 0.
            assert update["mode"] == mode and update["alpha"] == cfg["guidance"]["alpha"]
    if stage == "preflight":
        checks = generation["preflight_checks"]
        for name in ("zero_strength_bit_identical", "velocity_actual_sampler_sign_passed",
                     "direct_actual_sampler_sign_passed", "same_noise", "a0_anchor_exact",
                     "frozen_models", "no_environment_steps"):
            assert checks[name] is True
        for mode in ("velocity", "direct"):
            assert checks[mode+"_actual_sampler_linear_gain"] >= -1e-5
    for name in ("same_noise", "a0_anchor_exact", "frozen_models", "no_environment_steps"):
        assert generation["preflight_checks"][name] is True
    return _matching(plans, generation, cfg)


def _concurrency_checks(inputs):
    checks = []
    for path in sorted((ROOT / "checks").glob("*/worker_*/passed.json")):
        passed = _json(path)
        assert passed["status"] == "passed" and passed["full_trajectory_bit_identical"]
        folder, reference = path.parent, Path(passed["reference"])
        sealed(folder, ROOT / "config.json")
        sealed(reference, ROOT / "config.json")
        original, duplicate = _array_file(reference / "trajectory.npz"), _array_file(folder / "trajectory.npz")
        assert set(original) == set(duplicate)
        for key in original:
            np.testing.assert_array_equal(original[key], duplicate[key])
        first, second = _json(reference / "summary.json"), _json(folder / "summary.json")
        for key in ("success", "terminal_step", "actual_prefix_steps", "commands_sha256", "endpoint_image_sha256", "suffix_seeds"):
            assert first[key] == second[key]
        for item in (path, folder / "complete.json", reference / "complete.json"):
            inputs[str(item)] = file_sha256(item)
        checks.append(dict(path=str(folder), reference=str(reference), budget_attempt=second["budget_attempt"]))
    return checks


def collect(stage):
    """Read one complete stage; caller decides whether outcomes may be reported."""
    assert stage in ("preflight", "development")
    cfg = read(ROOT / "config.json")
    assert cfg["methods"] == METHODS and cfg["prefix_steps"] == 10 and cfg["replicates"] == 8
    repeats = cfg["preflight_replicates"] if stage == "preflight" else cfg["replicates"]
    cases = [case for case in cfg["cases"] if case["split"] == stage]
    assert len(cases) == (5 if stage == "preflight" else 30)
    assert len({case["case_id"] for case in cases}) == len(cases)
    frozen = _frozen_dependencies(cfg, stage)
    rows, generations, branches, amplitudes = [], [], [], []
    counts = Counter(planned_sources=len(cases))
    inputs = {str(ROOT / "config.json"): file_sha256(ROOT / "config.json")}
    source_costs = []
    for case in cases:
        target = ROOT / "rollouts" / stage / case["case_id"]
        meta = sealed(target, ROOT / "config.json")
        source = ROOT / "sources/single" / case["case_id"]
        sealed(source, ROOT / "config.json")
        for path in (target / "complete.json", source / "complete.json"):
            inputs[str(path)] = file_sha256(path)
        smeta = _json(source / "summary.json")
        triggers = [event["step"] for event in smeta["events"] if event["trigger"]]
        assert meta["cuts"] == smeta["cuts"] == triggers[:1] and len(meta["cuts"]) <= 1
        assert meta["no_alarm"] == smeta["no_alarm"] == (not meta["cuts"])
        assert meta["common_source_success"] == smeta["success"] and meta["replicates"] == repeats
        source_costs.append(dict(case_id=case["case_id"], **smeta.get("cost", {})))
        base_row = dict(case_id=case["case_id"], task=case["task"], env_seed=case["env_seed"],
                        alarm=bool(meta["cuts"]), cut=meta["cuts"][0] if meta["cuts"] else None)
        if not meta["cuts"]:
            counts["no_alarm_sources"] += 1
            rows.append(dict(**base_row, outcomes=np.full((len(METHODS), repeats), int(smeta["success"])).tolist(), prediction=None))
            continue
        counts["alarm_sources"] += 1
        cut = meta["cuts"][0]
        counts["late_alarm_sources_cut_gt_290"] += int(cut > 290)
        counts["budget_truncated_prefix_sources"] += int(cut+10 > cfg["control_budget"])
        original = _array_file(source / "trajectory.npz")
        group = target / f"cut{cut:03d}"
        packet = group / "candidates"
        sealed(packet, ROOT / "config.json")
        inputs[str(packet / "complete.json")] = file_sha256(packet / "complete.json")
        generation = _json(packet / "generation.json")
        plans = _array_file(packet / "plans.npz")
        directions = _array_file(packet / "directions.npz")
        reconstructed, _ = construct(plans["replan"], plans["velocity_native"], plans["direct_native"],
            directions["post_internal_metric_direction"], seed_for(cfg["random_seed_namespace"], case["env_seed"], cut), cfg["matching"])
        for method in METHODS:
            np.testing.assert_array_equal(plans[method], reconstructed[method])
        actual = _generation_checks(generation, plans, cfg, case, cut, source, stage)
        generations.append(dict(generation, case_id=case["case_id"], task=case["task"]))
        labels = []
        for method in METHODS:
            amplitudes.append(dict(case_id=case["case_id"], method=method, **actual[method]))
            outcomes, previous = [], None
            for rep in range(repeats):
                folder = group / method / f"replicate_{rep}"
                summary, endpoint = check_branch(folder, plans[method], case, cut, rep, original, cfg)
                inputs[str(folder / "complete.json")] = file_sha256(folder / "complete.json")
                if previous is not None:
                    np.testing.assert_array_equal(previous[0], endpoint[0])
                    assert previous[1] == endpoint[1]
                previous = endpoint
                outcomes.append(int(summary["success"]))
                branches.append(summary)
                counts["completed_branches"] += 1
                counts["terminal_shortened_prefix_branches"] += int(summary["actual_prefix_steps"] < min(10, cfg["control_budget"]-cut))
            labels.append(outcomes)
        for i, method in enumerate(METHODS):
            for j in range(i):
                if np.array_equal(plans[method][:10], plans[METHODS[j]][:10]):
                    assert labels[i] == labels[j]
                    counts["identical_candidate_pairs"] += 1
        rows.append(dict(**base_row, outcomes=labels, prediction=generation["predictions"]))
    budget, attempts = _budget()
    assert budget["attempts"] >= counts["completed_branches"]
    attempt_by_number = {item["number"]: item for item in attempts}
    for summary in branches:
        attempt = attempt_by_number[summary["budget_attempt"]]
        expected = ROOT / "rollouts" / stage / summary["case_id"] / f"cut{summary['step']:03d}" / summary["method"] / f"replicate_{summary['replicate']}"
        assert attempt["kind"] == stage and attempt["identity"] == str(expected)
    for case in cases:
        assert any(item["kind"] == "source_capture" and item["identity"] == case["case_id"] for item in attempts)
    concurrency = _concurrency_checks(inputs) if stage == "development" else []
    if stage == "development":
        assert len(concurrency) >= cfg["budget"]["concurrency_checks"]
        for check in concurrency:
            attempt = attempt_by_number[check["budget_attempt"]]
            assert attempt["kind"] == "concurrency_check" and attempt["identity"] == check["path"]
    analytic_response = {}
    if stage == "preflight":
        for mode in ("velocity", "direct"):
            values = [generation["preflight_checks"][mode+"_actual_sampler_linear_gain"] for generation in generations]
            assert any(value > 1e-5 for value in values), f"No unsaturated actual-sampler sign response: {mode}"
            analytic_response[mode] = _numbers(values)
    data = dict(config=cfg, rows=rows, generations=generations, branches=branches,
                amplitudes=amplitudes, source_costs=source_costs)
    technical = dict(status="passed", stage=stage, config_sha256=file_sha256(ROOT / "config.json"),
        counts=dict(counts), budget=budget, frozen_dependencies=frozen,
        concurrency_reproductions=concurrency,
        analytic_actual_sampler_response=analytic_response,
        candidate_generation_cost={mode: dict(
            calls=int(sum((generation["base_generation"] if mode == "base" else generation["guidance"][mode])["policy_calls"] for generation in generations)),
            seconds=float(sum((generation["base_generation"] if mode == "base" else generation["guidance"][mode])["seconds"] for generation in generations)),
            peak_cuda_allocated_mib=_numbers([(generation["base_generation"] if mode == "base" else generation["guidance"][mode])["peak_cuda_allocated_mib"] for generation in generations]))
            for mode in ("base", "velocity", "direct")},
        first_G0_alarm_audited=True, full_planned_denominator=True,
        specified_a0_fixed_across_objectives=True, same_initial_flow_noise=True,
        actual_final_command_amplitudes_matched=True, direct_reverse_symmetric=True,
        ten_step_prefix_and_fixed10_suffix=True, replay_physics_atol=1e-10,
        repeated_prefix_physics_images_exact=True, actual_suffix_sampling_streams_verified=True,
        identical_prefixes_have_identical_paired_outcomes=True,
        amplitudes=amplitudes, input_sha256=inputs,
        preflight_success_rates_disclosed=False if stage == "preflight" else None)
    return data, technical


def audit(stage):
    _, technical = collect(stage)
    dump(ROOT / "audits" / f"{stage}.json", technical)
    print(json.dumps({key: technical[key] for key in ("status", "stage", "counts", "budget")}), flush=True)
    return technical


def _estimate(rows, key, cfg):
    return estimate(rows, key, bootstraps=cfg["inference"]["bootstrap"], seed=cfg["inference"]["bootstrap_seed"])


def summarize_rows(rows, cfg):
    per_method = {}
    for method in METHODS:
        summaries = []
        for row in rows:
            y = np.asarray(row["outcomes"], dtype=np.int64)
            selected, baseline = y[METHODS.index(method)], y[0]
            summaries.append(dict(case_id=row["case_id"], task=row["task"],
                success=float(selected.mean()), baseline=float(baseline.mean()), gain=float((selected-baseline).mean()),
                rescues=int(((selected == 1) & (baseline == 0)).sum()), harms=int(((selected == 0) & (baseline == 1)).sum())))
        per_method[method] = dict(success=_estimate(summaries, "success", cfg), gain=_estimate(summaries, "gain", cfg),
            rescues=sum(row["rescues"] for row in summaries), harms=sum(row["harms"] for row in summaries),
            rescue_contribution=float(sum(row["rescues"] for row in summaries)/(len(rows)*cfg["replicates"])),
            harm_contribution=-float(sum(row["harms"] for row in summaries)/(len(rows)*cfg["replicates"])),
            sources=len(rows), paired_suffix_denominator=len(rows)*cfg["replicates"],
            positive_sources=sum(row["gain"] > 0 for row in summaries),
            negative_sources=sum(row["gain"] < 0 for row in summaries),
            zero_sources=sum(row["gain"] == 0 for row in summaries))
    comparisons = []
    for method, reference in cfg["primary_comparisons"]:
        values = []
        for row in rows:
            y = np.asarray(row["outcomes"], dtype=np.int64)
            a, b = y[METHODS.index(method)], y[METHODS.index(reference)]
            values.append(dict(case_id=row["case_id"], task=row["task"], gain=float((a-b).mean()),
                               rescues=int(((a == 1) & (b == 0)).sum()), harms=int(((a == 0) & (b == 1)).sum())))
        comparisons.append(dict(method=method, reference=reference, gain=_estimate(values, "gain", cfg),
                                rescues=sum(row["rescues"] for row in values), harms=sum(row["harms"] for row in values)))
    return dict(methods=per_method, registered_comparisons=comparisons)


def _diagnostics(data):
    generations, branches = data["generations"], data["branches"]
    amplitudes = data["amplitudes"]
    result = dict(amplitudes={method: {key: _numbers([row[key] for row in amplitudes if row["method"] == method])
                                      for key in ("xyz_rms", "gripper_rms", "xyz_linf", "gripper_linf")}
                              for method in METHODS}, guidance={}, predictions={}, cost={})
    for mode in ("velocity", "direct"):
        all_stats = [generation["guidance"][mode] for generation in generations]
        updates = [update for stats in all_stats for update in stats.get("updates", [])]
        result["guidance"][mode] = dict(
            sources=len(generations), fallback_sources=sum(bool(stats.get("fallback")) for stats in all_stats),
            fallback_reasons=dict(Counter(str(stats.get("fallback")) for stats in all_stats if stats.get("fallback"))),
            per_time={str(tau): {key: _numbers([row.get(key) for row in updates if abs(row["tau"]-tau) < 1e-6])
                                 for key in ("gradient_norm", "gradient_xyz_rms", "gradient_grip_rms",
                                             "injection_gradient_norm", "velocity_delta_norm", "clipping_fraction",
                                             "boundary_fraction", "zero_gradient_fraction", "clean_a0_xyz_rms",
                                             "clean_a0_grip_rms", "objective_before", "objective_after")}
                      for tau in data["config"]["guidance"]["times"]})
    result["matching"] = dict(sources=len(generations),
        masked_fraction=_numbers([generation["matching"]["masked_fraction"] for generation in generations]),
        groups={group: dict(zero_group_sources=sum(generation["matching"]["groups"][group]["zero_group"] for generation in generations),
                            shrunk_sources=sum(generation["matching"]["groups"][group]["shrunk"] for generation in generations),
                            achieved_target=_numbers([generation["matching"]["groups"][group]["achieved_target"] for generation in generations]))
                for group in ("xyz", "gripper")})
    alarm = [row for row in data["rows"] if row["alarm"]]
    for method in METHODS:
        predicted, actual, probabilities, baseline_probabilities = [], [], [], []
        for row in alarm:
            y = np.asarray(row["outcomes"])
            prediction = row["prediction"][method]
            predicted.append(prediction["mean_gain"])
            actual.append(float((y[METHODS.index(method)]-y[0]).mean()))
            probabilities.append(prediction["candidate_mean_probability"])
            baseline_probabilities.append(prediction["a0_mean_probability"])
        predicted, actual = np.asarray(predicted), np.asarray(actual)
        correlation = float(np.corrcoef(predicted, actual)[0, 1]) if len(predicted) > 1 and predicted.std() > 0 and actual.std() > 0 else None
        result["predictions"][method] = dict(alarm_sources=len(alarm), predicted_gain=_numbers(predicted),
            actual_gain=_numbers(actual), gain_mse=float(np.mean((predicted-actual)**2)) if len(actual) else None,
            gain_correlation=correlation, predicted_candidate_success=_numbers(probabilities),
            predicted_a0_success=_numbers(baseline_probabilities),
            predicted_positive_but_actual_nonpositive=int(((predicted > 0) & (actual <= 0)).sum()),
            predicted_positive_but_actual_negative=int(((predicted > 0) & (actual < 0)).sum()))
    branch_keys = ("wall_seconds", "replay_seconds", "suffix_policy_calls", "suffix_policy_seconds", "environment_seconds")
    result["cost"]["branches_total"] = {key: float(sum(row.get(key, 0.) for row in branches)) for key in branch_keys}
    result["cost"]["branches_by_method"] = {method: {key: float(sum(row.get(key, 0.) for row in branches if row["method"] == method))
                                                      for key in branch_keys} for method in METHODS}
    result["cost"]["candidate_generation"] = {}
    for mode in ("base", "velocity", "direct"):
        stats = [generation["base_generation"] if mode == "base" else generation["guidance"][mode] for generation in generations]
        result["cost"]["candidate_generation"][mode] = dict(
            totals={key: float(sum(row[key] for row in stats))
                    for key in ("policy_calls", "seconds", "objective_forward_calls", "backward_calls")},
            memory_mib={key: _numbers([row[key] for row in stats]) for key in
                        ("peak_cuda_allocated_mib", "peak_cuda_reserved_mib", "incremental_peak_cuda_allocated_mib")})
    result["cost"]["objective_totals"] = {key: float(sum(generation["objective_stats"][key] for generation in generations))
        for key in ("objective_forward_calls", "critic_member_forward_calls", "objective_backward_calls",
                    "critic_member_backward_calls", "critic_forward_seconds")}
    result["cost"]["generation_wall_seconds"] = _numbers([generation["wall_seconds"] for generation in generations])
    result["cost"]["post_gradient_seconds"] = _numbers([generation["post_gradient"]["seconds"] for generation in generations])
    # Keep exact instrumentation so unavailable fields cannot be mistaken for measured zero.
    result["cost"]["source_capture"] = data["source_costs"]
    result["cost"]["per_source_instrumentation"] = [dict(case_id=generation["case_id"],
        instrumentation={key: value for key, value in generation.items()
                         if any(part in key for part in ("cost", "seconds", "memory", "objective_stats", "preflight"))})
        for generation in generations]
    result["cost"]["interpretation"] = "Worker-summed wall time is compute burden, not parallel elapsed time; native and matched candidates share generation calls."
    return result


def _csv(rows):
    stream = io.StringIO(newline="")
    fields = ["case_id", "task", "env_seed", "alarm", "cut", "method", "success", "baseline", "gain",
              "rescues", "harms", "predicted_gain", "predicted_success", "predicted_a0"] + [f"success_rep{index}" for index in range(8)]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        y = np.asarray(row["outcomes"], dtype=np.int64)
        for index, method in enumerate(METHODS):
            prediction = row["prediction"][method] if row["prediction"] is not None else {}
            writer.writerow(dict({key: row[key] for key in ("case_id", "task", "env_seed", "alarm", "cut")},
                method=method, success=float(y[index].mean()), baseline=float(y[0].mean()), gain=float((y[index]-y[0]).mean()),
                rescues=int(((y[index] == 1) & (y[0] == 0)).sum()), harms=int(((y[index] == 0) & (y[0] == 1)).sum()),
                predicted_gain=prediction.get("mean_gain"), predicted_success=prediction.get("candidate_mean_probability"),
                predicted_a0=prediction.get("a0_mean_probability"),
                **{f"success_rep{rep}": int(value) for rep, value in enumerate(y[index])}))
    return stream.getvalue()


def evaluate():
    data, technical = collect("development")
    cfg, rows = data["config"], data["rows"]
    assert len(rows) == 30
    counts = Counter(row["task"] for row in rows)
    assert len(counts) == 5 and set(counts.values()) == {6}
    for row in rows:
        y = np.asarray(row["outcomes"])
        assert y.shape == (len(METHODS), 8) and np.isin(y, [0, 1]).all()
    result = dict(status="complete", stage="development", config_sha256=file_sha256(ROOT / "config.json"),
        formal_freeze_sha256=file_sha256(ROOT / "formal_freeze.json"),
        planned_sources=30, alarm_sources=sum(row["alarm"] for row in rows),
        no_alarm_sources=sum(not row["alarm"] for row in rows), paired_suffixes_per_source=8,
        independent_unit="source", denominator=30*8,
        **summarize_rows(rows, cfg),
        per_task={task: summarize_rows([row for row in rows if row["task"] == task], cfg) for task in sorted(counts)},
        diagnostics=_diagnostics(data), rows=rows, audit=technical,
        interpretation=cfg["inference"]["interpretation"], independent_validation_success=False,
        target_point_estimate_only={method: float(np.mean([(np.asarray(row["outcomes"])[METHODS.index(method)]-np.asarray(row["outcomes"])[0]).mean() for row in rows])) >= .05
                                    for method in METHODS if method != "replan"},
        limitations=["This is a new development mechanism screen, not independent confirmation of the best method.",
                     "Eight suffixes share one source; task-stratified bootstrap resamples sources, never suffixes.",
                     "Nominal 95% intervals across multiple registered comparisons are not multiplicity corrected.",
                     "Matched projection may expand or shrink native deltas; native algorithm arms are separately labeled.",
                     "A Q increase alone does not demonstrate real recovery or trustworthy local derivatives."])
    dump(ROOT / "audits/development.json", technical)
    dump(ROOT / "evaluation.json", result)
    dump(DOC / "per_source.json", dict(methods=METHODS, rows=rows, config_sha256=result["config_sha256"]))
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "per_source.csv").write_text(_csv(rows))
    print(json.dumps(dict(status="complete", planned_sources=30, methods=result["methods"],
                         registered_comparisons=result["registered_comparisons"])), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["audit", "evaluate", "budget"])
    parser.add_argument("--stage", choices=["preflight", "development"], default="preflight")
    args = parser.parse_args()
    if args.action == "audit":
        audit(args.stage)
    elif args.action == "evaluate":
        evaluate()
    else:
        print(json.dumps(_budget()[0]), flush=True)
