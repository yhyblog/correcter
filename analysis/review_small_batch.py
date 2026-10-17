#!/usr/bin/env python3
"""Independently review a complete, audited 15-source MetaWorld batch.

Only NumPy and the Python standard library are required. This script imports no
collector/evaluator code, never selects parameters, and writes no experiment
files. Incomplete or inconsistent input produces no review artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
METHODS = ["replan", "velocity_matched", "direct_matched", "post_matched", "continue_old"]
CORRECTIONS = METHODS[1:4]
PAIRS = [("replan", "continue_old"), *[(name, "replan") for name in CORRECTIONS],
         ("direct_matched", "velocity_matched"), ("post_matched", "velocity_matched"),
         ("post_matched", "direct_matched")]
LABELS = {"continue_old": "继续 old", "replan": "普通重规划", "velocity_matched": "Velocity",
          "direct_matched": "Direct", "post_matched": "Post"}
BOOTSTRAPS, BOOTSTRAP_SEED, REPLICATES = 10000, 29015, 8


class ReviewError(ValueError):
    """Missing, incomplete, unaudited, or contradictory experiment evidence."""


def require(condition, message):
    if not condition:
        raise ReviewError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    path = Path(path)
    require(path.is_file(), f"Required completed artifact absent: {path}")
    return json.loads(path.read_text())


def binary(value, label):
    require(type(value) in (bool, int) and value in (0, 1), f"Not a binary success: {label}")
    return int(value)


def close(actual, expected, label):
    require(np.allclose(actual, expected, rtol=0, atol=1e-12), f"Statistical mismatch: {label}")


def check_seal(folder, config_sha, required_files=()):
    metadata = read(folder / "complete.json")
    require(metadata.get("status") == "complete", f"Incomplete folder: {folder}")
    require(metadata.get("config_sha256") == config_sha, f"Configuration mismatch: {folder}")
    files = metadata.get("files", {})
    require(set(required_files) <= set(files), f"Seal missing required files: {folder}")
    for name, expected in files.items():
        path = (folder / name).resolve()
        require(path.is_relative_to(folder.resolve()), f"Seal path escapes folder: {path}")
        require(path.is_file() and sha256(path) == expected, f"Changed sealed file: {path}")
    return metadata


def bootstrap(values, tasks):
    """Resample whole sources within each task, retaining all paired suffixes."""
    values = np.asarray(values, dtype=np.float64)
    require(len(values) == len(tasks) and len(values) > 0, "Invalid source vector")
    require(np.isfinite(values).all(), "Nonfinite source statistic")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    totals = np.zeros(BOOTSTRAPS, dtype=np.float64)
    for task in sorted(set(tasks)):
        group = values[np.asarray(tasks) == task]
        draws = rng.integers(0, len(group), size=(BOOTSTRAPS, len(group)))
        totals += group[draws].sum(axis=1)
    return {"mean": float(values.mean()), "interval": np.quantile(totals / len(values), [.025, .975]).tolist(),
            "sources": len(values)}


def contrast(outcomes, tasks, method, reference):
    selected = outcomes[:, METHODS.index(method), :]
    baseline = outcomes[:, METHODS.index(reference), :]
    gain = (selected - baseline).mean(axis=1)
    return {"method": method, "reference": reference, "gain": bootstrap(gain, tasks),
            "rescues": int(((selected == 1) & (baseline == 0)).sum()),
            "harms": int(((selected == 0) & (baseline == 1)).sum()),
            "positive_sources": int((gain > 0).sum()), "negative_sources": int((gain < 0).sum()),
            "zero_sources": int((gain == 0).sum()), "per_source_gain": gain.tolist()}


def summarize(outcomes, tasks):
    summaries = {}
    for index, method in enumerate(METHODS):
        comparison = contrast(outcomes, tasks, method, "replan")
        summaries[method] = {**comparison, "success": bootstrap(outcomes[:, index, :].mean(axis=1), tasks),
                             "successes": int(outcomes[:, index, :].sum()),
                             "paired_suffix_denominator": len(outcomes) * REPLICATES}
    return {"methods": summaries, "comparisons": [contrast(outcomes, tasks, *pair) for pair in PAIRS]}


def check_summary(independent, reported, label):
    require(set(reported["methods"]) == set(METHODS), f"Wrong methods in {label}")
    for method, calculated in independent["methods"].items():
        other = reported["methods"][method]
        for metric in ("success", "gain"):
            close(calculated[metric]["mean"], other[metric]["mean"], f"{label}/{method}/{metric}/mean")
            close(calculated[metric]["interval"], other[metric]["interval"], f"{label}/{method}/{metric}/interval")
            require(calculated[metric]["sources"] == other[metric]["sources"], f"Wrong source count: {label}/{method}")
        for key in ("rescues", "harms", "positive_sources", "negative_sources", "zero_sources", "paired_suffix_denominator"):
            require(calculated[key] == other[key], f"Mismatch: {label}/{method}/{key}")
    reported_pairs = {(item["method"], item["reference"]): item for item in reported["registered_comparisons"]}
    require(len(reported_pairs) == len(PAIRS) and set(reported_pairs) == set(PAIRS), f"Wrong comparisons in {label}")
    for calculated in independent["comparisons"]:
        other = reported_pairs[(calculated["method"], calculated["reference"])]
        for key in ("mean", "interval"):
            close(calculated["gain"][key], other["gain"][key], f"{label}/comparison/{calculated['method']}/{key}")
        for key in ("rescues", "harms"):
            require(calculated[key] == other[key], f"Mismatch: {label}/comparison/{key}")


def load_complete(root):
    # Do not inspect any branch outcomes until the final evaluation and audit exist.
    evaluation = read(root / "evaluation.json")
    audit = read(root / "audits/development.json")
    require(evaluation.get("status") == "complete" and evaluation.get("stage") == "development", "Final evaluation is incomplete")
    require(audit.get("status") == "passed" and audit.get("stage") == "development", "Development audit has not passed")
    require(evaluation.get("audit") == audit, "Standalone audit differs from evaluation audit")
    cfg = read(root / "config.json")
    config_sha = sha256(root / "config.json")
    require(read(root / "config.identity.json")["sha256"] == config_sha, "Changed configuration")
    require(evaluation["config_sha256"] == audit["config_sha256"] == config_sha, "Audit/configuration mismatch")
    freeze = read(root / "formal_freeze.json")
    require(evaluation["formal_freeze_sha256"] == sha256(root / "formal_freeze.json"), "Changed formal freeze")
    require(freeze["config_sha256"] == config_sha and freeze["development_sources_absent"] is True,
            "Formal settings were not frozen before collection")
    require(freeze["preflight_outcomes_used_for_settings"] is False, "Preflight outcomes used to choose settings")
    require(cfg["methods"] == METHODS and cfg["replicates"] == REPLICATES, "Unexpected methods or suffix count")
    require(cfg["inference"]["bootstrap"] == BOOTSTRAPS and cfg["inference"]["bootstrap_seed"] == BOOTSTRAP_SEED,
            "Unexpected registered inference")
    require(set(map(tuple, cfg["primary_comparisons"])) == set(PAIRS), "Unexpected registered comparisons")
    cases = [case for case in cfg["cases"] if case["split"] == "development"]
    require(len(cases) == 15 and len({case["case_id"] for case in cases}) == 15, "Expected exactly 15 unique fresh sources")
    require({case["env_seed"] for case in cases} == set(range(2026106000, 2026106015)), "Unexpected source cohort; refusing historical or mixed sources")
    task_counts = Counter(case["task"] for case in cases)
    require(len(task_counts) == 5 and set(task_counts.values()) == {3}, "Expected five tasks with three sources each")
    require(evaluation["planned_sources"] == 15 and evaluation["denominator"] == 120 and
            evaluation["paired_suffixes_per_source"] == REPLICATES and evaluation["independent_unit"] == "source", "Wrong evaluation denominator")
    for flag in ("first_G0_alarm_audited", "full_planned_denominator", "specified_a0_fixed_across_objectives",
                 "same_initial_flow_noise", "actual_final_command_amplitudes_matched",
                 "intervention_ten_step_prefix_and_fixed10_suffix", "continue_old_natural_queue_then_native50",
                 "repeated_prefix_physics_images_exact", "actual_suffix_sampling_streams_verified"):
        require(audit.get(flag) is True, f"Required audit check missing: {flag}")
    require(audit["budget"]["attempts"] <= cfg["budget"]["hard_maximum"], "Experiment exceeded registered budget")
    for name, expected in audit["input_sha256"].items():
        path = Path(name).resolve()
        require(path.is_relative_to(root.resolve()), f"Audit input outside current batch: {path}")
        require(path.is_file() and sha256(path) == expected, f"Changed audited input: {path}")
    require(len(evaluation["rows"]) == 15, "Missing evaluation rows")
    reported = {row["case_id"]: row for row in evaluation["rows"]}
    require(set(reported) == {case["case_id"] for case in cases}, "Wrong/duplicate evaluation source rows")

    rows, generations, branch_count = [], [], 0
    for case in cases:
        target = root / "rollouts/development" / case["case_id"]
        source = root / "sources/single" / case["case_id"]
        meta = check_seal(target, config_sha)
        check_seal(source, config_sha, ("summary.json", "trajectory.npz"))
        source_summary = read(source / "summary.json")
        require(meta["case"] == case and source_summary["case"] == case and meta["replicates"] == REPLICATES,
                f"Source identity mismatch: {case['case_id']}")
        cuts = meta["cuts"]
        require(cuts == source_summary["cuts"] and len(cuts) <= 1 and meta["no_alarm"] == source_summary["no_alarm"] == (not cuts),
                f"Alarm bookkeeping mismatch: {case['case_id']}")
        common = binary(meta["common_source_success"], case["case_id"])
        require(common == binary(source_summary["success"], case["case_id"]), "No-alarm common outcome mismatch")
        outcomes = np.full((len(METHODS), REPLICATES), common, dtype=np.int64)
        if cuts:
            cut = cuts[0]
            packet = target / f"cut{cut:03d}/candidates"
            check_seal(packet, config_sha, ("generation.json", "plans.npz", "directions.npz"))
            generation = read(packet / "generation.json")
            require((generation["case_id"], generation["step"]) == (case["case_id"], cut),
                    f"Wrong candidate-generation identity: {packet}")
            generations.append(generation)
            for index, method in enumerate(METHODS):
                for replicate in range(REPLICATES):
                    folder = target / f"cut{cut:03d}" / method / f"replicate_{replicate}"
                    check_seal(folder, config_sha, ("summary.json", "trajectory.npz"))
                    summary = read(folder / "summary.json")
                    require((summary["case_id"], summary["task"], summary["method"], summary["replicate"], summary["step"]) ==
                            (case["case_id"], case["task"], method, replicate, cut), f"Wrong branch identity: {folder}")
                    expected_continuation = "continue_original_queue_then_native50_no_alarm_v1" if method == "continue_old" else "clear_queue_then_fixed10_v1"
                    require(summary["continuation"] == expected_continuation, f"Wrong continuation: {folder}")
                    expected_semantics = "raw_original_policy_output_preserved" if method == "continue_old" else "bounded_intervention_commands"
                    require(summary["commands_semantics"] == expected_semantics, f"Wrong action semantics: {folder}")
                    outcomes[index, replicate] = binary(summary["success"], str(folder))
                    branch_count += 1
        row = {"case_id": case["case_id"], "task": case["task"], "env_seed": case["env_seed"],
               "alarm": bool(cuts), "cut": cuts[0] if cuts else None, "outcomes": outcomes.tolist()}
        other = reported[case["case_id"]]
        for key in ("case_id", "task", "env_seed", "alarm", "cut", "outcomes"):
            require(row[key] == other[key], f"Independent branch/evaluation mismatch: {case['case_id']}/{key}")
        rows.append(row)
    alarm = sum(row["alarm"] for row in rows)
    require(alarm == evaluation["alarm_sources"] and 15 - alarm == evaluation["no_alarm_sources"], "Alarm denominator mismatch")
    require(audit["counts"]["planned_sources"] == 15 and audit["counts"].get("completed_branches", 0) == branch_count,
            "Audit branch/source count mismatch")
    outcomes = np.asarray([row["outcomes"] for row in rows], dtype=np.int64)
    require(outcomes.shape == (15, 5, 8) and np.isin(outcomes, [0, 1]).all(), "Expected a binary 15 × 5 × 8 outcome tensor")
    return evaluation, audit, rows, outcomes, generations, branch_count


def report_text(review):
    def rate(estimate):
        lo, hi = estimate["interval"]
        return f"{100 * estimate['mean']:.2f}% [{100 * lo:.2f}, {100 * hi:.2f}]"

    def gain(estimate):
        lo, hi = estimate["interval"]
        return f"{100 * estimate['mean']:+.2f} [{100 * lo:+.2f}, {100 * hi:+.2f}]"

    methods = review["methods"]
    lines = ["# MetaWorld 小批量独立复核：2026-09-16", "",
             "本次只分析当前 15 个新 source（5 个任务各 3 个），每个 source 配对 8 个 suffix；未混入历史 30 个 source。",
             "正式 evaluation 完整、development audit 通过且文件哈希一致；从原始分支 summary 独立重建 15×5×8 成功标签，复核总表、逐任务表及注册对比一致。",
             f"实际执行的正式分支数为 {review['verification']['completed_branches']}；无报警 source 为 {review['no_alarm_sources']}，按 common_source_success 保留为各臂相同结局。", "",
             "区间为按任务分层、以整个 source 为簇的 10,000 次 bootstrap，种子 29015。所有 95% CI 均为 nominal 区间，未作多重比较校正；120 个 suffix 不等于 120 个独立 source。此轮是小样本筛选，不是广泛验证。", "",
             "## 五臂绝对成功率", "", "| 方法 | 成功数/120 | 成功率及 95% CI |", "|---|---:|---:|"]
    for method in ["continue_old", *METHODS[:4]]:
        row = methods[method]
        lines.append(f"| {LABELS[method]} | {row['successes']}/120 | {rate(row['success'])} |")
    lines += ["", "## 配对收益", "", "收益单位为百分点；救回/损害是在相同 source、相同 suffix 编号下相对右侧方法的 0→1 / 1→0 次数。", "",
              "| 对比（左减右） | 收益及 95% CI | 救回/损害 | 正/负/零收益 source |", "|---|---:|---:|---:|"]
    for row in review["comparisons"]:
        lines.append(f"| {LABELS[row['method']]} − {LABELS[row['reference']]} | {gain(row['gain'])} | {row['rescues']}/{row['harms']} | {row['positive_sources']}/{row['negative_sources']}/{row['zero_sources']} |")
    lines += ["", "## 逐任务", "", "每个任务只有 3 个独立 source、24 个配对 suffix。完整逐任务置信区间和全部两两对比保存在 JSON。", "",
              "| 任务 | Old | Replan | Velocity | Direct | Post |", "|---|---:|---:|---:|---:|---:|"]
    for task, summary in review["per_task"].items():
        values = [f"{100 * summary['methods'][name]['success']['mean']:.2f}%" for name in ["continue_old", *METHODS[:4]]]
        lines.append("| " + " | ".join([task, *values]) + " |")
    lines += ["", "| 任务 | Replan−Old | Velocity−Replan | Direct−Replan | Post−Replan |", "|---|---:|---:|---:|---:|"]
    for task, summary in review["per_task"].items():
        values = [f"{100 * row['gain']['mean']:+.2f}" for row in summary["comparisons"][:4]]
        lines.append("| " + " | ".join([task, *values]) + " |")
    lines += ["", "## 如何解读方法差异", "",
              review["provisional_interpretation"], "",
              "Old 按原生 50 步动作块执行：先消耗原队列，再自然重采样；重规划及三个修正臂执行 10 步前缀后按 fixed10 继续。Old 保留 raw 原策略动作前缀，其他四臂使用有界动作。因此 replan−old 同时包含中断、native50/fixed10 节奏及 raw/有界前缀差异，不能归因为单一中断动作。四个干预臂之间的比较才共享执行前缀长度与后续节奏。", "",
              "## 主要异常与审计", "",
              "三种纠偏均未达到相对 replan 额外 +5 个百分点的目标。" if not any(review["target_gain_met"].values()) else "部分纠偏点估计达到 +5 个百分点；仍需结合 source 级区间和损害解释。"]
    diagnostics = review["diagnostics"]
    lines += ["", "纠偏与 replan 发生配对结局变化的源：" + ("、".join(diagnostics["changed_outcome_sources"]) or "无") + "。", "",
              "| 纠偏 | 平均预测增益 pp | 真实增益 pp | fallback 源数 |", "|---|---:|---:|---:|"]
    for method in CORRECTIONS:
        predicted = diagnostics["predicted_mean_gain"][method]
        predicted_text = "未触发" if predicted is None else f"{100 * predicted:+.2f}"
        fallback = diagnostics["fallback_sources"].get(method, "不适用")
        lines.append(f"| {LABELS[method]} | {predicted_text} | {100 * methods[method]['gain']['mean']:+.2f} | {fallback} |")
    lines += ["", "Q 上升不能替代真实配对成功率；本轮未执行反向/随机物理对照，不能据此唯一判定梯度方向错误。", ""]
    for group, counts in diagnostics["matching_groups"].items():
        lines.append(f"- {group}：零幅度源 {counts['zero_sources']}，共同半径收缩源 {counts['shrunk_sources']}。")
    budget = review["budget"]
    lines += ["", f"实际预算 {budget['attempts']}/{budget['hard_maximum']}；分项 {budget['by_kind']}；重复身份 {budget['repeated_identity_attempts']}。预算账本哈希、连续编号及分类计数已核对。",
              "正式源捕获前冻结，完整 source/branch 文件封存哈希与最终技术审计一致，正式分支标签独立重建通过。", "",
              "## 计算开销", "", "下表为触发 source 上每次候选生成的测量均值；不能据此直接声称某个方法的独立部署延迟。", "",
              "| 测量项 | 平均秒数 |", "|---|---:|"]
    for key, label in [("base_policy_seconds", "基础重规划调用"), ("velocity_policy_seconds", "Velocity 引导调用"),
                       ("direct_policy_seconds", "Direct 引导调用"), ("post_gradient_seconds", "Post 梯度子步骤"),
                       ("source_restore_seconds", "状态恢复与源轨迹回放"),
                       ("candidate_bank_seconds", "全部候选生成、评分和记录（排除回放）"),
                       ("all_candidate_generation_wall_seconds", "整体 wall time（包含回放）")]:
        value = review["cost"][key]["mean"]
        lines.append(f"| {label} | {'未发生' if value is None else f'{value:.6f}'} |")
    lines += ["", "Post 的梯度耗时只是子步骤。当前公平比较使用共同半径，半径仍依赖 velocity/direct/post/reverse/random 全部方向；因此不能把 Post 梯度耗时当作完整 Post 方法成本。完整候选生成还含基础 VLA 采样、其他方向生成、critic 评分、投影及相关记录。若要得到可独立部署的 Post 延迟，需要先定义并验证不依赖其他方向的半径方案。各 worker 的 wall time 总和也不是并行实验的实际经过时间。", "",
              "## 可追溯文件", "", "- 独立复核 JSON：`analysis/latest_review.json`。",
              "- 输入：`outputs/metaworld_small_20260916/evaluation.json`、`audits/development.json` 及封存的 source/branch 文件。",
              "- 分析脚本：`analysis/review_small_batch.py`。未修改实验代码、配置、数据或方法参数。", ""]
    return "\n".join(lines)


def analyze(root):
    evaluation, audit, rows, outcomes, generations, branch_count = load_complete(root)
    tasks = [row["task"] for row in rows]
    summary = summarize(outcomes, tasks)
    check_summary(summary, evaluation, "overall")
    per_task = {}
    for task in sorted(set(tasks)):
        indices = [index for index, name in enumerate(tasks) if name == task]
        per_task[task] = summarize(outcomes[indices], [task] * len(indices))
        check_summary(per_task[task], evaluation["per_task"][task], task)

    def costs(values):
        require(all(np.isfinite(value) and value >= 0 for value in values), "Invalid measured cost")
        return {"sources": len(values), "total": float(sum(values)), "mean": float(np.mean(values)) if values else None}

    cost = {"base_policy_seconds": costs([row["base_generation"]["seconds"] for row in generations]),
            "velocity_policy_seconds": costs([row["guidance"]["velocity"]["seconds"] for row in generations]),
            "direct_policy_seconds": costs([row["guidance"]["direct"]["seconds"] for row in generations]),
            "post_gradient_seconds": costs([row["post_gradient"]["seconds"] for row in generations]),
            "source_restore_seconds": costs([row["restore_seconds"] for row in generations]),
            "candidate_bank_seconds": costs([row["candidate_bank_seconds"] for row in generations]),
            "all_candidate_generation_wall_seconds": costs([row["wall_seconds"] for row in generations]),
            "standalone_post_latency_measured": False,
            "post_shared_radius_depends_on_all_generated_directions": True}
    for generation in generations:
        require(abs(generation["wall_seconds"] - generation["restore_seconds"] - generation["candidate_bank_seconds"]) < 1e-4,
                "Candidate timing components do not sum to total wall time")
    for key in ("source_restore_seconds", "candidate_bank_seconds", "post_gradient_seconds"):
        if generations:
            close(cost[key]["mean"], evaluation["diagnostics"]["cost"][key]["mean"], f"cost/{key}")
    ledger_path = root / "budget/attempts.jsonl"
    require(sha256(ledger_path) == audit["budget"]["ledger_sha256"], "Changed simulator budget ledger")
    ledger = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    require([row["number"] for row in ledger] == list(range(1, len(ledger) + 1)), "Nonconsecutive budget ledger")
    require(len(ledger) == audit["budget"]["attempts"], "Budget attempt count mismatch")
    require(dict(Counter(row["kind"] for row in ledger)) == audit["budget"]["by_kind"], "Budget category mismatch")
    repeated = len(ledger) - len({row["identity"] for row in ledger})
    require(repeated == audit["budget"]["repeated_identity_attempts"], "Budget repeats mismatch")
    diagnostics = {
        "changed_outcome_sources": [row["case_id"] for row, y in zip(rows, outcomes)
                                    if np.any(y[1:4] != y[0])],
        "fallback_sources": {mode + "_matched": sum(bool(row["guidance"][mode].get("fallback")) for row in generations)
                             for mode in ("velocity", "direct")},
        "matching_groups": {group: {
            "zero_sources": sum(bool(row["matching"]["groups"][group]["zero_group"]) for row in generations),
            "shrunk_sources": sum(bool(row["matching"]["groups"][group]["shrunk"]) for row in generations)}
            for group in ("xyz", "gripper")},
        "predicted_mean_gain": {method: float(np.mean([row["predictions"][method]["mean_gain"] for row in generations]))
                                if generations else None for method in CORRECTIONS},
        "late_alarm_sources": audit["counts"].get("late_alarm_sources_cut_gt_290", 0),
        "budget_truncated_prefix_sources": audit["counts"].get("budget_truncated_prefix_sources", 0)}
    best_rate = max(summary["methods"][name]["success"]["mean"] for name in CORRECTIONS)
    leaders = [name for name in CORRECTIONS if summary["methods"][name]["success"]["mean"] == best_rate]
    interpretation = "三种纠偏中的最高点估计为 " + "、".join(LABELS[name] for name in leaders) + "。"
    if all(row["gain"]["interval"][0] <= 0 <= row["gain"]["interval"][1] for row in summary["comparisons"][4:]):
        interpretation += "三个纠偏两两差异的 nominal 区间均覆盖 0，当前无法确定稳定胜者。"
    else:
        interpretation += "部分两两差异的 nominal 区间未覆盖 0，但 15 个 source 与未校正的多重比较仅支持暂定候选排序，仍不能确立稳定胜者。"
    if best_rate <= summary["methods"]["replan"]["success"]["mean"]:
        interpretation += "三种纠偏的最高点估计也未超过普通重规划，本批结果不足以支持加入纠偏。"
    else:
        interpretation += "是否值得继续使用纠偏还需同时看其相对普通重规划的救回、损害、逐任务一致性和完整计算成本。"
    return {"status": "passed", "created_at_utc": datetime.now(timezone.utc).isoformat(), "input_root": str(root),
            "independent_sources": 15, "paired_suffixes_per_source": 8, "denominator_per_method": 120,
            "alarm_sources": sum(row["alarm"] for row in rows), "no_alarm_sources": sum(not row["alarm"] for row in rows),
            "method_order": METHODS, "independent_outcome_shape": list(outcomes.shape),
            "inference": {"unit": "whole source", "stratified_by": "task", "bootstrap": BOOTSTRAPS,
                          "seed": BOOTSTRAP_SEED, "confidence_level": .95, "multiple_comparisons_corrected": False,
                          "scope": "15 fresh sources only; small exploratory screening; not broad validation"},
            "verification": {"completed_branches": branch_count, "summary_labels_match_evaluation_rows": True,
                             "overall_and_per_task_statistics_match": True, "audit_passed": True,
                             "sealed_files_and_audit_hashes_verified": True,
                             "inputs": {name: sha256(root / name) for name in
                                        ("config.json", "formal_freeze.json", "evaluation.json", "audits/development.json")},
                             "review_script_sha256": sha256(Path(__file__))},
            **summary, "per_task": per_task, "rows": rows, "cost": cost,
            "budget": audit["budget"], "diagnostics": diagnostics,
            "target_gain_met": {method: summary["methods"][method]["gain"]["mean"] >= .05 for method in CORRECTIONS},
            "provisional_interpretation": interpretation,
            "limitations": ["Nominal intervals; no multiplicity correction; only three sources per task.",
                            "No-alarm sources use the observed common outcome for all arms and suffix positions.",
                            "Replan versus old includes interruption, fixed10/native50 cadence, and bounded/raw prefix differences.",
                            "Post gradient time excludes dependencies required by the shared-radius candidate comparison.",
                            "Old and intervention sampling times/counts differ despite shared suffix decision-index seed namespace."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=PACKAGE / "outputs/metaworld_small_20260916")
    parser.add_argument("--json-output", type=Path, default=PACKAGE / "analysis/latest_review.json")
    parser.add_argument("--markdown-output", type=Path, default=PACKAGE / "docs/SMALL_BATCH_ANALYSIS_20260916.md")
    args = parser.parse_args()
    try:
        review = analyze(args.input.resolve())
        markdown = report_text(review)
        # No output paths are created until every verification has passed.
        require(args.json_output.resolve() != args.markdown_output.resolve(), "Output paths must differ")
        for path in (args.json_output, args.markdown_output):
            require(not path.resolve().is_relative_to(args.input.resolve()), "Refusing to write inside experiment input")
        for path, content in [(args.json_output, json.dumps(review, ensure_ascii=False, indent=2, allow_nan=False) + "\n"),
                              (args.markdown_output, markdown)]:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(content)
            temporary.replace(path)
        print(json.dumps({"status": "passed", "sources": 15, "json": str(args.json_output), "markdown": str(args.markdown_output)}, ensure_ascii=False))
    except (ReviewError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"Review refused; no new analysis should be used: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
