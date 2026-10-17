"""New CPU small-critic training core, not part of the already frozen P0 wave.

No real fit has been run to validate this module. It accepts audited in-memory
source arrays; dataset assembly, main-stage release, four-member orchestration,
real development rollouts and final policy export remain the launcher's work.
``fit_member`` requires an explicitly released training stage and reserves every
optimizer update. Tests use synthetic tensors and one local optimizer step only.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Mapping

import numpy as np
import torch
from torch.nn import functional as F

from corrector.critic import STATE_KEYS, TenStepCritic, from_state, observed_features
from .protocol import TASKS, episode_key, require_stage_budget, seed_for


CANDIDATES = (
    "a0", "xyz_positive", "xyz_negative", "gripper_positive", "gripper_negative",
    "random_half_positive", "random_half_negative", "random_full_positive",
    "random_full_negative", "velocity", "direct", "post", "reverse_post",
)
PAIRS = ((1, 2), (3, 4), (5, 6), (7, 8), (11, 12))
CHECKPOINTS = {"round1": (200, 400, 800, 1600, 2400),
               "final": (200, 400, 800, 1600, 2400, 3200, 4000)}
STAGES = {"round1": "training_round1", "final": "training_final"}
LEARNING_RATES = {"A": 1e-4, "B": 3e-4}


@contextmanager
def cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(2)
    try:
        yield
    finally:
        torch.set_num_threads(previous)


def _cpu(value, name, dtype=None):
    tensor = torch.as_tensor(value)
    if tensor.device.type != "cpu":
        raise ValueError(f"{name} must already be on CPU")
    if dtype is not None:
        tensor = tensor.to(dtype=dtype)
    return tensor


def _finite(value, name):
    if not bool(torch.isfinite(value).all()):
        raise ValueError(f"Nonfinite {name}")


def _rows(rows, expected_split=None):
    if not rows:
        raise ValueError("At least one complete source is required")
    seen = set()
    for row in rows:
        identity = episode_key(row.get("task"), row.get("env_seed"))
        if row.get("episode_id") != identity or identity in seen:
            raise ValueError("Duplicate/noncanonical source identity; split by whole episode")
        if expected_split is not None and row.get("split") != expected_split:
            raise ValueError("Only the specified source split is permitted")
        seen.add(identity)
    return list(rows)


def dedup_weights(group_ids, candidate_valid=None, pair_mask=None):
    """One weight per physical-command group, independent of success labels.

    Groups must come from audited raw-command/source/suffix equivalence, never
    from equality of clipped critic inputs alone. This routine cannot certify
    physical equivalence or nonzero +/- symmetry; the data audit must do that.
    """
    ids = _cpu(group_ids, "group_ids")
    if ids.ndim != 2 or ids.shape[1] != 13 or ids.dtype.is_floating_point or ids.dtype == torch.bool:
        raise ValueError("group_ids must be integer [sources,13]")
    valid = torch.ones_like(ids, dtype=torch.bool) if candidate_valid is None else _cpu(candidate_valid, "candidate_valid", torch.bool)
    if valid.shape != ids.shape or not bool(valid[:, 0].all()) or bool((ids[valid] < 0).any()):
        raise ValueError("Invalid candidate mask or missing baseline group")
    supplied = torch.ones((len(ids), len(PAIRS)), dtype=torch.bool) if pair_mask is None else _cpu(pair_mask, "pair_mask", torch.bool)
    if supplied.shape != (len(ids), len(PAIRS)):
        raise ValueError("pair_mask must be [sources,5]")
    candidate = torch.zeros_like(ids, dtype=torch.float32)
    gain = torch.zeros_like(candidate)
    pair = torch.zeros((len(ids), len(PAIRS)), dtype=torch.float32)
    for source in range(len(ids)):
        groups = Counter(int(ids[source, j]) for j in range(13) if valid[source, j])
        for j in range(13):
            if valid[source, j]:
                candidate[source, j] = 1 / groups[int(ids[source, j])]
                if ids[source, j] != ids[source, 0]:
                    gain[source, j] = candidate[source, j]
        pair_groups = []
        for index, (positive, negative) in enumerate(PAIRS):
            if supplied[source, index] and valid[source, positive] and valid[source, negative] and ids[source, positive] != ids[source, negative]:
                pair_groups.append((index, tuple(sorted((int(ids[source, positive]), int(ids[source, negative]))))))
        multiplicity = Counter(group for _, group in pair_groups)
        for index, group in pair_groups:
            pair[source, index] = 1 / multiplicity[group]
    return dict(candidate_weights=candidate, gain_weights=gain, pair_weights=pair)


def _weights(value, shape, name):
    value = _cpu(value, name, torch.float32)
    if tuple(value.shape) != tuple(shape):
        raise ValueError(f"{name} shape must be {shape}")
    _finite(value, name)
    if bool(((value < 0) | (value > 1)).any()):
        raise ValueError(f"{name} must be within [0,1]; no outcome-based upweighting")
    return value


def _source_average(values, weights):
    denominator = weights.sum(-1)
    return (values * weights).sum(-1) / torch.where(denominator > 0, denominator, torch.ones_like(denominator))


def loss_parts(logits, outcomes, *, candidate_weights, gain_weights, pair_weights, pair_mask=None):
    """BCE + relative gain MSE + .5 probability-difference MSE, then source mean.

    Masked unknown labels may use -1; active candidates require four binary
    outcomes. Empty gain/pair groups contribute exactly zero, while the source
    remains in the outer mean. No binary difference is divided by a radius.
    """
    logits = _cpu(logits, "logits")
    outcomes = _cpu(outcomes, "outcomes", torch.float32)
    if logits.ndim != 2 or not len(logits) or logits.shape[1] != 13 or outcomes.shape != (*logits.shape, 4):
        raise ValueError("Expected logits[N,13] and outcomes[N,13,4]; normal control is separate")
    _finite(logits, "logits");_finite(outcomes, "outcomes")
    n = len(logits)
    cw = _weights(candidate_weights, (n, 13), "candidate_weights")
    gw = _weights(gain_weights, (n, 13), "gain_weights")
    pw = _weights(pair_weights, (n, 5), "pair_weights")
    if pair_mask is not None:
        pw = pw * _weights(pair_mask, (n, 5), "pair_mask")
    if not bool((cw[:, 0] > 0).all()) or bool((gw[:, 0] != 0).any()):
        raise ValueError("BCE must include a0 and gain must exclude slot zero")
    active = (cw > 0) | (gw > 0)
    for index, (positive, negative) in enumerate(PAIRS):
        active[:, positive] |= pw[:, index] > 0
        active[:, negative] |= pw[:, index] > 0
    binary = ((outcomes == 0) | (outcomes == 1)).all(-1)
    if bool((active & ~binary).any()):
        raise ValueError("An active candidate lacks all four paired binary outcomes")
    target = torch.where(binary[..., None], outcomes, torch.zeros_like(outcomes)).mean(-1)
    probabilities = logits.sigmoid()
    bce_source = _source_average(F.binary_cross_entropy_with_logits(logits, target, reduction="none"), cw)
    predicted_gain = probabilities-probabilities[:, :1]
    observed_gain = target-target[:, :1]
    gain_source = _source_average((predicted_gain-observed_gain).square(), gw)
    predicted_pair = torch.stack([probabilities[:, a]-probabilities[:, b] for a, b in PAIRS], -1)
    observed_pair = torch.stack([target[:, a]-target[:, b] for a, b in PAIRS], -1)
    pair_source = _source_average((predicted_pair-observed_pair).square(), pw)
    source_loss = bce_source+gain_source+.5*pair_source
    return dict(loss=source_loss.mean(), bce=bce_source.mean(), gain_mse=gain_source.mean(),
                pair_mse=pair_source.mean(), per_source_loss=source_loss,
                per_source_bce=bce_source, per_source_gain_mse=gain_source,
                per_source_pair_mse=pair_source, predicted_gain=predicted_gain,
                observed_gain=observed_gain)


def fit_pca(values, dimension, *, return_diagnostics=False):
    """Copied train-only SVD definition; callers pass unique train rows only."""
    values = _cpu(values, "PCA values", torch.float32)
    if values.ndim != 2 or len(values) <= dimension:
        raise ValueError("Insufficient unique training sources for the registered PCA width")
    _finite(values, "PCA values")
    center = values.mean(0)
    _, singular_values, vh = torch.linalg.svd(values-center, full_matrices=False)
    basis = vh[:dimension].T.contiguous()
    projected = (values-center)@basis
    raw_scale = projected.std(0, unbiased=False)
    scale = raw_scale.clamp_min(1e-3)
    result = center, basis, scale
    if not return_diagnostics:
        return result
    return result, dict(singular_values=singular_values.tolist(),
                        retained_standard_deviations=raw_scale.tolist(),
                        scale_floor=1e-3, scale_floor_count=int((raw_scale < 1e-3).sum()),
                        projected_clip_fraction=float(((projected/scale).abs() > 8).float().mean()),
                        diagnostic_projection="batched train-only fit; canonical singleton inference must be audited separately")


def fit_train_preprocessing(arrays, rows, train_indices, *, norm_mean, norm_std):
    """B-path PCA uses unique train sources, before episode bootstrap duplication.

    Nontraining rows may be present in arrays, but they are sliced out before any
    feature statistics are computed. Frozen original visual normalization is an
    explicit input; this function never reads a checkpoint or a dataset file.
    """
    _rows(rows)
    indices = np.asarray(train_indices)
    if indices.ndim != 1 or indices.dtype.kind not in "iu" or len(indices) != len(set(indices.tolist())):
        raise ValueError("PCA fit indices must be unique integer training source indices")
    if not len(indices) or int(indices.min()) < 0 or int(indices.max()) >= len(rows):
        raise ValueError("Invalid PCA training indices")
    _rows([rows[int(i)] for i in indices], "train")
    values = {key: _cpu(arrays[key], key)[indices].detach().clone() for key in STATE_KEYS}
    if any(len(_cpu(arrays[key], key)) != len(rows) for key in STATE_KEYS):
        raise ValueError("State arrays and source identities disagree")
    norm_mean = _cpu(norm_mean, "norm_mean", torch.float32).detach().clone()
    norm_std = _cpu(norm_std, "norm_std", torch.float32).detach().clone().clamp_min(1e-6)
    if norm_mean.shape != (4096,) or norm_std.shape != (4096,):
        raise ValueError("Expected frozen visual normalization of width4096")
    with cpu_threads(), torch.no_grad():
        visual, language, _ = observed_features(values, norm_mean, norm_std)
        result = dict(norm_mean=norm_mean, norm_std=norm_std,
                      residual_scale=torch.tensor([.15, .15, .15, .4], dtype=torch.float32))
        diagnostics = {}
        for name, matrix, width in (("visual", visual, 16), ("language", language, 8)):
            components, diagnostics[name] = fit_pca(matrix, width, return_diagnostics=True)
            for suffix, tensor in zip(("center", "basis", "scale"), components):
                result[name+"_"+suffix] = tensor.detach().clone()
    return result, dict(fit_episode_ids=[rows[int(i)]["episode_id"] for i in indices],
                        fit_source_count=len(indices), train_only=True,
                        bootstrap_duplicates_used=False, visual_dimension=16, language_dimension=8,
                        pca_diagnostics=diagnostics,
                        real_frozen_objective_probability_gradient_reload_audit="required before real fit; not performed by this function")


def configure_trainable(model, path):
    if path not in LEARNING_RATES:
        raise ValueError("Only approved paths A/B are supported")
    model.requires_grad_(path == "B")
    if path == "A":
        model.residual.requires_grad_(True)
        model.advantage.requires_grad_(True)
    for value in model.buffers():
        if value.device.type != "cpu" or value.requires_grad:
            raise ValueError("Preprocessing buffers must be frozen CPU tensors")
    if any(parameter.device.type != "cpu" for parameter in model.parameters()):
        raise ValueError("Training is CPU-only")
    return [name for name, value in model.named_parameters() if value.requires_grad]


def initialize_model(path, *, seed, preprocessing=None, warm_start_state=None):
    """Create an owned model; never mutate the imported frozen member or buffers."""
    if path not in LEARNING_RATES or type(seed) is not int or not 0 <= seed < 2**63:
        raise ValueError("Expected path A/B and a valid explicit initialization seed")
    with cpu_threads(), torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        if path == "A":
            if warm_start_state is None or preprocessing is not None:
                raise ValueError("A requires an old state_dict and preserves its own preprocessing")
            state = {key: _cpu(value, key).detach().clone() for key, value in warm_start_state.items()}
            model = from_state(state)
        else:
            if preprocessing is None or warm_start_state is not None:
                raise ValueError("B requires new train-only preprocessing and fresh initialization")
            model = TenStepCritic({key: _cpu(value, key).detach().clone() for key, value in preprocessing.items()})
    if sum(value.numel() for value in model.parameters()) != 7058:
        raise ValueError("Registered small-critic architecture changed")
    model._native10_training_path = path
    configure_trainable(model, path)
    return model


def canonical_features(model, arrays):
    """Singleton feature path matches frozen inference; no batch-PCA shortcut."""
    tensors = {key: _cpu(arrays[key], key).detach() for key in STATE_KEYS}
    n = len(tensors["history"])
    if not n or any(len(value) != n for value in tensors.values()):
        raise ValueError("Inconsistent/empty state arrays")
    with cpu_threads(), torch.no_grad():
        return torch.cat([model.features({key: value[i:i+1] for key, value in tensors.items()})
                          for i in range(n)]).detach()


def stratified_episode_bootstrap(rows, *, seed):
    """Preserve each task's eligible-source count, draw complete episodes only."""
    rows = _rows(rows, "train")
    rng = np.random.default_rng(seed)
    indices, per_task = [], {}
    for task in TASKS:
        group = np.asarray([i for i, row in enumerate(rows) if row["task"] == task], dtype=np.int64)
        chosen = rng.choice(group, size=len(group), replace=True).tolist() if len(group) else []
        indices.extend(chosen)
        per_task[task] = dict(unique_available=len(group), drawn=len(chosen))
    ids = [rows[i]["episode_id"] for i in indices]
    return dict(seed=int(seed), indices=indices, episode_ids=ids,
                multiplicities=dict(Counter(ids)), per_task=per_task,
                source_grouped=True, outcome_weighting=False)


def _validated_training_data(data):
    rows = _rows(data["rows"], "train")
    actions = _cpu(data["actions"], "actions", torch.float32).detach()
    outcomes = _cpu(data["outcomes"], "outcomes", torch.float32).detach()
    if actions.shape != (len(rows), 13, 10, 4) or outcomes.shape != (len(rows), 13, 4):
        raise ValueError("Training requires 13 ten-step candidates and four labels; no normal-control slot")
    _finite(actions, "critic actions")
    if bool((actions.abs() > 1).any()) or not bool(((outcomes == 0) | (outcomes == 1)).all()):
        raise ValueError("Real fit requires bounded critic inputs and complete, binary audited labels")
    ids = _cpu(data["group_ids"], "group_ids")
    weights = dedup_weights(ids, pair_mask=data.get("pair_mask"))
    if ids.shape != (len(rows), 13):
        raise ValueError("Alias groups do not align with source rows")
    for source in range(len(rows)):
        for group in torch.unique(ids[source]).tolist():
            members = torch.nonzero(ids[source] == group).flatten()
            first = int(members[0])
            if not torch.equal(actions[source, members], actions[source, first].expand(len(members), -1, -1)) or not torch.equal(outcomes[source, members], outcomes[source, first].expand(len(members), -1)):
                raise ValueError("Audited aliases disagree in critic actions or paired outcomes")
    # If the assembler supplies weights, ensure they implement the declared alias
    # scheme rather than outcome-based weighting. Pure loss_parts accepts weights.
    for key, expected in weights.items():
        if key in data and not torch.equal(_cpu(data[key], key, torch.float32), expected):
            raise ValueError(f"Supplied {key} disagrees with audited alias groups")
    return rows, actions, outcomes, weights


def checkpoint_state(model):
    """Plain CPU state_dict, directly loadable by existing from_state/FrozenSelector."""
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


def save_checkpoint(model, path):
    """Write a new-only selected.pt; ensemble ranking/manifest belongs to wrapper.

    FrozenSelector expects <assets>/models/refit/member_<numeric id>/selected.pt
    and ranking.json with horizon=10 and the four SHA256 model_hashes. This file
    deliberately has no extra training wrapper around its tensor state_dict.
    """
    from .storage import ROOT, sha256
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()) or path.exists():
        raise ValueError("Checkpoint must be a new file inside the new workflow output")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        torch.save(checkpoint_state(model), stream)
    return dict(path=str(path), sha256=sha256(path), horizon=10, format="plain_cpu_state_dict")


def fit_member(config, ledger, *, phase, path, member, model, features, data,
               stop_after=None, on_checkpoint=None):
    """Gated in-memory fit; never discovers or loads real training files itself.

    The caller initializes A/B with audited train-only preprocessing and provides
    canonical features in row order. on_checkpoint(step, state_dict, metrics)
    may persist to a new version directory. No calibration/heldout data accepted.
    """
    if phase not in STAGES or path not in LEARNING_RATES or type(member) is not int or not 0 <= member < 4:
        raise ValueError("Only two approved phases/paths and four members are allowed")
    stage = STAGES[phase]
    require_stage_budget(config, stage, resource="training_updates")
    steps = CHECKPOINTS[phase][-1] if stop_after is None else stop_after
    if steps not in CHECKPOINTS[phase]:
        raise ValueError("Stop only at an approved checkpoint within this phase")
    if getattr(model, "_native10_training_path", None) != path:
        raise ValueError("Use initialize_model to create an owned A/B training model")
    rows, actions, outcomes, weights = _validated_training_data(data)
    registered = {row["episode_id"]: row for row in config["episode_manifest"]}
    for row in rows:
        planned = registered.get(row["episode_id"])
        if planned is None or planned.get("split") != "train" or any(planned.get(key) != row.get(key) for key in ("task", "env_seed", "round")):
            raise ValueError("Source not in the frozen training split/round")
        if phase == "round1" and row.get("round") != 1:
            raise ValueError("Round1 cannot train on round2 sources")
    features = _cpu(features, "features", torch.float32).detach()
    if features.shape != (len(rows), 61):
        raise ValueError("Expected canonical [source,61] features from this model's preprocessing")
    _finite(features, "features")
    namespace = config["seed_namespace"]
    bootstrap_seed = seed_for("training_bootstrap", phase, path, member, namespace=namespace)
    batch_seed = seed_for("training_minibatches", phase, path, member, namespace=namespace)
    bootstrap = stratified_episode_bootstrap(rows, seed=bootstrap_seed)
    pool = np.asarray(bootstrap["indices"], dtype=np.int64)
    rng = np.random.default_rng(batch_seed)
    trainable = configure_trainable(model, path)
    original_frozen = {name: value.detach().clone() for name, value in model.named_parameters() if not value.requires_grad}
    original_buffers = {name: value.detach().clone() for name, value in model.named_buffers()}
    history, saved, batches, attempts = [], {}, [], []
    with cpu_threads():
        optimizer = torch.optim.AdamW([value for value in model.parameters() if value.requires_grad],
                                     lr=LEARNING_RATES[path], weight_decay=.01)
        model.train()
        for step in range(1, steps+1):
            attempt = ledger.reserve(stage, "critic_optimizer_update", f"{phase}:{path}:{member}:{step}",
                                     resource="training_updates", requested=1)
            attempts.append(attempt["number"])
            chosen = pool[rng.integers(0, len(pool), 32)]
            batches.append(chosen.tolist())
            optimizer.zero_grad(set_to_none=True)
            logits = model(features[chosen], actions[chosen])
            parts = loss_parts(logits, outcomes[chosen], **{key: value[chosen] for key, value in weights.items()})
            if not bool(torch.isfinite(parts["loss"])):
                raise ValueError("Nonfinite training loss")
            parts["loss"].backward()
            gradient = torch.nn.utils.clip_grad_norm_([value for value in model.parameters() if value.requires_grad], 1.)
            if not bool(torch.isfinite(gradient)):
                raise ValueError("Nonfinite training gradient")
            optimizer.step()
            if step in CHECKPOINTS[phase]:
                metric = dict(step=step, loss=float(parts["loss"].detach()), bce=float(parts["bce"].detach()),
                              gain_mse=float(parts["gain_mse"].detach()), pair_mse=float(parts["pair_mse"].detach()),
                              last_minibatch_only=True)
                state = checkpoint_state(model)
                history.append(metric);saved[step] = state
                if on_checkpoint is not None:
                    on_checkpoint(step, state, dict(metric))
        optimizer.zero_grad(set_to_none=True)
        for name, value in model.named_parameters():
            if name in original_frozen and not torch.equal(value, original_frozen[name]):
                raise ValueError("A frozen parameter changed during training")
        for name, value in model.named_buffers():
            if not torch.equal(value, original_buffers[name]):
                raise ValueError("Preprocessing buffer changed during training")
        model.eval().requires_grad_(False)
    return dict(phase=phase, path=path, member=member, updates=steps, checkpoints=saved,
                history=history, bootstrap=bootstrap, batch_seed=batch_seed,
                minibatches=batches, attempt_numbers=attempts, trainable_parameters=trainable,
                source_ids=[row["episode_id"] for row in rows], normal_control_used_in_critic=False,
                calibration_or_heldout_used=False, selected_checkpoint=None,
                note="Checkpoint selection must use the separate complete development bank.")


def checkpoint_selection_metrics(member_probabilities, outcomes, *, reached_mask, gain_weights):
    """Full-planned-source gain, harms and reached-source relative-gain MSE.

    Include all planned development episodes. No-cut rows must contain their
    same known binary outcome across arms/repeats; missing technical outcomes
    cannot be imputed. Probabilities for these no-cut rows are ignored.
    """
    p = _cpu(member_probabilities, "member_probabilities", torch.float64)
    y = _cpu(outcomes, "development outcomes", torch.float64)
    if p.ndim != 3 or p.shape[0] != 4 or not p.shape[1] or p.shape[2] != 13 or y.shape != (*p.shape[1:], 4):
        raise ValueError("Selection needs four members,13 candidates,four repeats")
    reached = _cpu(reached_mask, "reached_mask", torch.bool)
    if reached.shape != (p.shape[1],) or not bool(((y == 0) | (y == 1)).all()):
        raise ValueError("Incomplete development outcomes or incorrect source mask")
    if not bool(torch.isfinite(p[:, reached]).all()) or bool(((p[:, reached] < 0) | (p[:, reached] > 1)).any()):
        raise ValueError("Invalid reached-source probabilities")
    if not torch.equal(y[~reached], y[~reached, :1, :1].expand(-1, 13, 4)):
        raise ValueError("No-cut episodes must retain their shared known outcome")
    mean = torch.where(reached[None, :, None], p, torch.zeros_like(p)).mean(0)
    choice = mean.argmax(-1)  # registered a0 slot0 wins exact ties, then slot order
    choice[~reached] = 0
    chosen = y[torch.arange(len(y)), choice]
    baseline = y[:, 0]
    rescues = int(((chosen == 1) & (baseline == 0)).sum())
    harms = int(((chosen == 0) & (baseline == 1)).sum())
    gw = _weights(gain_weights, (len(y), 13), "gain_weights").double()
    if bool((gw[:, 0] != 0).any()):
        raise ValueError("Selection gain MSE excludes a0")
    actual = y.mean(-1)-y[:, :1].mean(-1)
    predicted = mean-mean[:, :1]
    source_error = _source_average((predicted-actual).square(), gw)
    mse = float(source_error[reached].mean()) if bool(reached.any()) else 0.
    return dict(planned_episodes=len(y), reached_episodes=int(reached.sum()),
                gain=(rescues-harms)/(len(y)*4), rescues=rescues, harms=harms,
                baseline_success=float(baseline.mean()), selected_success=float(chosen.mean()),
                gain_mse=mse, gain_mse_denominator="all reached source groups, including empty-gain groups as zero",
                selected_slots=choice.tolist(), gain_conditional=(rescues-harms)/(int(reached.sum())*4) if bool(reached.any()) else None,
                ensemble_mean_arithmetic="float64 of member float probabilities")


def choose_checkpoint(records):
    """Registered exact tie order; one A/B ensemble checkpoint per phase."""
    if not records:
        raise ValueError("No development checkpoint records")
    dataset = records[0].get("dataset_sha256")
    phase = records[0].get("phase")
    planned = records[0]["metrics"]["planned_episodes"]
    if not dataset or phase not in CHECKPOINTS:
        raise ValueError("Selection must bind one explicit dataset and approved phase")
    identities = set()
    for row in records:
        if row.get("dataset_sha256") != dataset or row.get("phase") != phase or row["path"] not in LEARNING_RATES or row["step"] not in CHECKPOINTS[phase] or row["metrics"]["planned_episodes"] != planned:
            raise ValueError("Cannot compare different banks, phases, denominators or unregistered paths")
        identity = (row["path"], row["step"])
        if identity in identities:
            raise ValueError("Duplicate path/checkpoint selection record")
        identities.add(identity)
        if not all(np.isfinite(row["metrics"][key]) for key in ("gain", "harms", "gain_mse")):
            raise ValueError("Nonfinite selection metric")
    best = max(records, key=lambda row: (row["metrics"]["gain"], -row["metrics"]["harms"],
        -row["metrics"]["gain_mse"], -row["step"], row["path"] == "B"))
    return deepcopy(best)
