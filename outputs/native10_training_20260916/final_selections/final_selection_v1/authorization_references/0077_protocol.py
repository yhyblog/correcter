"""CPU-only protocol, episode grouping and immutable random-stream checks.

This module neither samples episodes nor reserves budgets.  A launcher must
atomically count every attempt (including failures/retries), verify its frozen
code/ready artifacts, and then call ``require_stage_budget`` before work.

Budget schema (no formal counts are supplied by this module)::

    budget = {
        "hard_total": <total simulator attempts>,
        "training_update_total": <total optimizer updates>,
        "count_failures": True, "count_retries": True,
        "stages": {<stage>: {"simulator_attempts": N, "training_updates": M}}
    }

Runnable protocols require status="frozen" and an analysis_approval containing
status="approved", approved_by="analysis", protocol_sha256=protocol_digest(cfg),
an absolute document_path, and its document_sha256.  The approval is an explicit
analysis handoff record, not a substitute for the launcher's ready/code checks.
Also provide analysis_ready={"path": <absolute NATIVE10_ANALYSIS_READY.json>,
"sha256": <hash>} and stage_release_scopes={<stage>: <released scope string>}.
Registering a stage budget does not release that stage: the READY artifact must
explicitly list its scope. The initial READY releases P0 only, not main training.
Pending protocols can be inspected but cannot authorize any stage.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path


TASKS = (
    "disassemble-v3", "pick-place-wall-v3", "shelf-place-v3",
    "stick-pull-v3", "stick-push-v3",
)
DEFAULT_NAMESPACE = "corrector_native10_training_20260916_v1"
RESOURCES = ("simulator_attempts", "training_updates")
OUTCOME_FIELDS = frozenset({
    "success", "source_success", "alarm", "has_alarm", "no_alarm", "reached",
    "outcome", "outcomes", "reward", "gain", "selected_by_success",
    "selected_by_alarm",
})


class ProtocolError(ValueError):
    """An explicit protocol or episode invariant is absent or inconsistent."""


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ProtocolError(f"{name} must be an integer >= {minimum}")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"{name} must be a nonempty string")
    return value


def _sequence(value, name):
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ProtocolError(f"{name} must be a sequence")
    return value


def canonical_hash(value):
    """Hash canonical JSON; nonfinite values and unsupported types are rejected."""
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ProtocolError(f"Not canonical finite JSON: {error}") from error
    return hashlib.sha256(data).hexdigest()


def protocol_digest(config):
    """Bind all settings/manifests/budgets, excluding only the approval record."""
    if not isinstance(config, Mapping):
        raise ProtocolError("protocol must be a mapping")
    return canonical_hash({key: value for key, value in config.items()
                           if key != "analysis_approval"})


def episode_key(task, env_seed):
    """One independent episode group, irrespective of cut, repeat or method.

    A later initial-state-variation schema must retain this parent grouping;
    giving related variations different IDs must not allow split leakage.
    """
    if task not in TASKS:
        raise ProtocolError(f"Unknown task: {task!r}")
    return f"{task}__{_integer(env_seed, 'env_seed')}"


def _episode_identity(episode):
    if isinstance(episode, Mapping):
        key = episode_key(episode.get("task"), episode.get("env_seed"))
        if "episode_id" in episode and episode["episode_id"] != key:
            raise ProtocolError("episode_id disagrees with task/env_seed")
        return key
    _text(episode, "episode")
    try:
        task, raw_seed = episode.rsplit("__", 1)
        key = episode_key(task, int(raw_seed))
    except (ValueError, TypeError) as error:
        raise ProtocolError("Expected canonical task__env_seed episode ID") from error
    if key != episode:
        raise ProtocolError("Episode ID must be canonical task__env_seed")
    return key


def seed_for(*identity, namespace=DEFAULT_NAMESPACE):
    """Stable 63-bit seed; Python hash(), process ID and method are never used.

    Different keys define distinct pseudorandom streams, not a mathematical
    guarantee against hash collisions.  Persist the namespace with the protocol.
    Use the typed wrappers below for source/candidate/suffix sampling.
    """
    _text(namespace, "seed namespace")
    digest = canonical_hash(["native10_seed_v1", namespace, *identity])
    return int(digest[:16], 16) % (2**63 - 1)


def source_seed(episode, natural_decision_index, *, namespace=DEFAULT_NAMESPACE):
    """Source natural queue exhaustion index, not an absolute control step."""
    return seed_for("source_natural_decision", _episode_identity(episode),
                    _integer(natural_decision_index, "natural_decision_index"),
                    namespace=namespace)


def candidate_seed(episode, cut_id, candidate_index=0, *, namespace=DEFAULT_NAMESPACE):
    """Seed for an a0/noise draw, shared by replan and every guided version.

    candidate_index identifies a distinct designated a0 draw, NEVER an arm.
    All velocity/direct/post versions of one a0 must reuse the returned seed.
    No method/arm argument is accepted.  This seed is independent of repeat.
    """
    return seed_for("designated_a0", _episode_identity(episode),
                    _integer(cut_id, "cut_id"),
                    _integer(candidate_index, "candidate_index"),
                    namespace=namespace)


def suffix_seed(episode, cut_id, repeat, decision_index, *, namespace=DEFAULT_NAMESPACE):
    """Paired suffix decision-index stream, independent of candidate or method.

    Different repeats get different keyed streams.  The normal continuation and
    intervention arms can sample at different control times; shared decision
    indices do NOT imply equal noise at equal absolute steps or equal states.
    Source natural-decision indices live in a separate domain.
    """
    return seed_for("branch_suffix_decision", _episode_identity(episode),
                    _integer(cut_id, "cut_id"), _integer(repeat, "repeat"),
                    _integer(decision_index, "decision_index"), namespace=namespace)


def validate_manifest(episodes):
    """One outcome-blind planned row per independent episode, before capture.

    Cuts, candidate draws and repeats belong in descendant records; they cannot
    create a second manifest row or move an episode into another split.
    """
    _sequence(episodes, "episode_manifest")
    lookup = {}
    for row in episodes:
        if not isinstance(row, Mapping):
            raise ProtocolError("Manifest rows must be mappings")
        if OUTCOME_FIELDS.intersection(row):
            raise ProtocolError("Planned manifest must not contain observed outcomes/alarm selection")
        key = _episode_identity(row)
        if row.get("episode_id") != key:
            raise ProtocolError("Manifest row requires canonical episode_id")
        _text(row.get("split"), "split")
        if key in lookup:
            raise ProtocolError(f"Duplicate episode or cross-split leakage: {key}")
        lookup[key] = dict(row)
    return lookup


def audit_records(episodes, records, *, require_all=True):
    """Audit descendant grouping and planned retention without filtering outcomes.

    Include source-result records for no-alarm, early-success and failed captures.
    Multiple cuts/repeats/arms are allowed but retain the manifest episode split.
    require_all=False is only for an explicitly partial/in-progress CPU audit.
    """
    lookup = validate_manifest(episodes)
    _sequence(records, "records")
    seen = Counter()
    for row in records:
        if not isinstance(row, Mapping):
            raise ProtocolError("Result records must be mappings")
        key = _episode_identity(row)
        if row.get("episode_id") != key or key not in lookup:
            raise ProtocolError(f"Unplanned or inconsistent episode record: {key}")
        if row.get("split") != lookup[key]["split"]:
            raise ProtocolError(f"Descendant split leakage: {key}")
        seen[key] += 1
    missing = sorted(set(lookup) - set(seen))
    if require_all and missing:
        raise ProtocolError(f"Missing planned episodes (do not filter failed/no-alarm/success): {missing}")
    return {"planned_episodes": len(lookup), "recorded_episodes": len(seen),
            "records": sum(seen.values()), "missing_episode_ids": missing,
            "episode_record_counts": dict(sorted(seen.items())),
            "split_episode_counts": dict(Counter(row["split"] for row in lookup.values()))}


def pending_protocol():
    """Editable CPU preparation only; no formal seeds, sizes or budget defaults."""
    return {
        "schema_version": 1, "status": "pending", "tasks": list(TASKS),
        "source_horizon": 10, "prefix_horizon": 10, "suffix_horizon": 10,
        "episode_manifest": [], "retain_all_planned": True,
        "no_outcome_filter": True, "manifest_filters": [],
        "seed_namespace": DEFAULT_NAMESPACE, "replicates": None,
        "cpu": {"worker_threads": None, "critic_threads": None},
        "budget": None, "analysis_approval": None, "analysis_ready": None,
        "stage_release_scopes": {},
    }


def _validate_budget(budget):
    if not isinstance(budget, Mapping):
        raise ProtocolError("Explicit analysis stage budget is required")
    totals = {"simulator_attempts": _integer(budget.get("hard_total"), "hard_total"),
              "training_updates": _integer(budget.get("training_update_total"), "training_update_total")}
    if budget.get("count_failures") is not True or budget.get("count_retries") is not True:
        raise ProtocolError("Budgets must count all failures and retries")
    stages = budget.get("stages")
    if not isinstance(stages, Mapping) or not stages:
        raise ProtocolError("Explicit per-stage budgets are required")
    sums = Counter()
    for stage, limits in stages.items():
        _text(stage, "stage")
        if not isinstance(limits, Mapping) or set(limits) != set(RESOURCES):
            raise ProtocolError("Each stage must explicitly declare simulator_attempts and training_updates")
        for resource in RESOURCES:
            sums[resource] += _integer(limits[resource], f"{stage}.{resource}")
    if any(sums[resource] > totals[resource] for resource in RESOURCES):
        raise ProtocolError("Stage allocations exceed the overall budget")
    return totals


def _validate_approval(config):
    approval = config.get("analysis_approval")
    if not isinstance(approval, Mapping) or approval.get("status") != "approved" or approval.get("approved_by") != "analysis":
        raise ProtocolError("Explicit analysis protocol approval is required")
    if approval.get("protocol_sha256") != protocol_digest(config):
        raise ProtocolError("Protocol/manifest/budget changed after analysis approval")
    name = _text(approval.get("document_path"), "analysis document_path")
    path = Path(name)
    if not path.is_absolute() or not path.is_file():
        raise ProtocolError("Analysis approval document must be an existing absolute file")
    if hashlib.sha256(path.read_bytes()).hexdigest() != approval.get("document_sha256"):
        raise ProtocolError("Analysis document SHA256 mismatch")


def _validate_ready(config):
    reference = config.get("analysis_ready")
    if not isinstance(reference, Mapping):
        raise ProtocolError("The new workflow analysis READY reference is required")
    path = Path(_text(reference.get("path"), "analysis_ready.path"))
    if not path.is_absolute() or path.name != "NATIVE10_ANALYSIS_READY.json" or not path.is_file():
        raise ProtocolError("An absolute new NATIVE10_ANALYSIS_READY.json is required; old READY cannot be reused")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != reference.get("sha256"):
        raise ProtocolError("Analysis READY changed after protocol freeze")
    try:
        ready = json.loads(content)
    except (ValueError, UnicodeDecodeError) as error:
        raise ProtocolError("Invalid analysis READY JSON") from error
    if not isinstance(ready, Mapping) or ready.get("task_id") != "native10-training-20260916":
        raise ProtocolError("Analysis READY belongs to another task")
    status = _text(ready.get("status"), "READY.status")
    if status != "approved" and not status.startswith("protocol_approved_"):
        raise ProtocolError("Analysis READY is not in an approved state")
    scopes = _sequence(ready.get("released_scope"), "READY.released_scope")
    if not scopes or any(not isinstance(scope, str) or not scope.strip() for scope in scopes):
        raise ProtocolError("Analysis READY has no explicit released scopes")
    # Coordination references in this workflow are relative to the Corrector
    # checkout. Also allow absolute references in self-contained test fixtures.
    for key in ("task_document", "protocol_review"):
        document = Path(_text(ready.get(key), f"READY.{key}"))
        if not document.is_absolute():
            document = path.parent.parent / document
        if not document.is_file() or hashlib.sha256(document.read_bytes()).hexdigest() != ready.get(key + "_sha256"):
            raise ProtocolError(f"READY {key} is missing or changed")
        if key == "task_document":
            approved = Path(config["analysis_approval"]["document_path"])
            if document.resolve() != approved.resolve():
                raise ProtocolError("Approval document does not match the new READY task document")
    mapping = config.get("stage_release_scopes")
    stages = config["budget"]["stages"]
    if not isinstance(mapping, Mapping) or set(mapping) != set(stages):
        raise ProtocolError("Every budgeted stage needs one explicit analysis release scope")
    for stage, scope in mapping.items():
        _text(scope, "stage release scope")
        if scope in {"isolated_implementation", "cpu_protocol_checks"}:
            raise ProtocolError("CPU/implementation scopes cannot release formal resources")
        if scope == "p0_anchor_and_native10_diagnostics":
            if stage != "p0":
                raise ProtocolError("Only stage='p0' may use the P0 release scope")
            if stages[stage]["training_updates"] != 0:
                raise ProtocolError("P0 release never authorizes optimizer updates")
        elif stage == "p0":
            raise ProtocolError("P0 must use its explicit diagnostics release scope")
    hard = _integer(ready.get("new_simulator_attempts_hard_limit"), "READY total limit")
    p0 = _integer(ready.get("p0_attempts_hard_limit"), "READY P0 limit")
    if config["budget"]["hard_total"] > hard:
        raise ProtocolError("Protocol simulator budget exceeds analysis READY limit")
    p0_sum = sum(stages[stage]["simulator_attempts"] for stage, scope in mapping.items()
                 if scope == "p0_anchor_and_native10_diagnostics")
    if p0_sum > p0:
        raise ProtocolError("Combined P0 stages exceed the analysis P0 limit")
    return ready


def validate_protocol(config, *, require_runnable=False):
    """Validate on CPU.  Pending inspection never returns runnable=True."""
    if not isinstance(config, Mapping) or type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise ProtocolError("Expected protocol schema_version=1")
    if config.get("status") not in ("pending", "frozen"):
        raise ProtocolError("Protocol status must be pending or frozen")
    tasks = _sequence(config.get("tasks"), "tasks")
    if len(tasks) != len(TASKS) or set(tasks) != set(TASKS):
        raise ProtocolError("Protocol must explicitly name exactly the original five tasks")
    for key in ("source_horizon", "prefix_horizon", "suffix_horizon"):
        if _integer(config.get(key), key) != 10:
            raise ProtocolError(f"{key} must be 10")
    if config.get("retain_all_planned") is not True or config.get("no_outcome_filter") is not True:
        raise ProtocolError("All planned episodes must be retained without outcome/alarm filtering")
    if config.get("manifest_filters") != []:
        raise ProtocolError("Outcome/alarm manifest filtering is forbidden")
    _text(config.get("seed_namespace"), "seed_namespace")
    lookup = validate_manifest(config.get("episode_manifest"))
    cpu = config.get("cpu")
    if not isinstance(cpu, Mapping):
        raise ProtocolError("Explicit CPU configuration is required")
    for key in ("worker_threads", "critic_threads"):
        if cpu.get(key) is not None:
            _integer(cpu[key], f"cpu.{key}", 1)
    if config.get("replicates") is not None:
        _integer(config["replicates"], "replicates", 1)
    if config.get("budget") is not None:
        _validate_budget(config["budget"])
    digest = protocol_digest(config)
    runnable = config["status"] == "frozen"
    if runnable:
        if not lookup:
            raise ProtocolError("Frozen protocol requires explicit planned episodes")
        _integer(config.get("replicates"), "replicates", 1)
        for key in ("worker_threads", "critic_threads"):
            _integer(cpu.get(key), f"cpu.{key}", 1)
        _validate_budget(config.get("budget"))
        _validate_approval(config)
        _validate_ready(config)
    if require_runnable and not runnable:
        raise ProtocolError("Pending protocol cannot run collection or training")
    return {"status": config["status"], "runnable": runnable,
            "protocol_sha256": digest, "planned_episodes": len(lookup),
            "task_counts": dict(Counter(row["task"] for row in lookup.values())),
            "split_counts": dict(Counter(row["split"] for row in lookup.values()))}


def require_stage_budget(config, stage, *, used=0, requested=1, total_used=0,
                         resource="simulator_attempts"):
    """Fail closed before work; this check does NOT reserve an attempt.

    The caller owns atomic ledger updates, checks against reuse/concurrency, and
    must supply pre-reservation stage/total counts including failed attempts.
    Training callers select resource="training_updates" explicitly.
    """
    validate_protocol(config, require_runnable=True)
    _text(stage, "stage")
    if resource not in RESOURCES:
        raise ProtocolError(f"Unknown budget resource: {resource}")
    used = _integer(used, "used")
    total_used = _integer(total_used, "total_used")
    requested = _integer(requested, "requested", 1)
    if used > total_used:
        raise ProtocolError("Stage usage cannot exceed total usage")
    budget = config["budget"]
    if stage not in budget["stages"]:
        raise ProtocolError(f"Stage was not explicitly budgeted: {stage}")
    ready = _validate_ready(config)
    if config["stage_release_scopes"][stage] not in ready["released_scope"]:
        raise ProtocolError(f"Analysis READY has not released stage: {stage}")
    limit = budget["stages"][stage][resource]
    total_limit = budget["hard_total" if resource == "simulator_attempts" else "training_update_total"]
    if used + requested > limit or total_used + requested > total_limit:
        raise ProtocolError(f"{stage}.{resource} stage/total budget exceeded")
    return {"stage": stage, "resource": resource, "limit": limit,
            "total_limit": total_limit, "used": used, "total_used": total_used,
            "requested": requested, "remaining_after": limit - used - requested,
            "total_remaining_after": total_limit - total_used - requested}
