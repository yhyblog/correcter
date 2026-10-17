"""Synthetic CPU checks only: no real checkpoint/dataset reads or fit_member run."""
from copy import deepcopy
import io
import math

import numpy as np
import pytest
import torch

from corrector.critic import STATE_KEYS, from_state
from experiments.native10_training_20260916.protocol import TASKS, ProtocolError, episode_key, pending_protocol
from experiments.native10_training_20260916.training import (
    CHECKPOINTS, PAIRS, canonical_features, checkpoint_selection_metrics,
    checkpoint_state, choose_checkpoint, cpu_threads, dedup_weights,
    fit_member, fit_train_preprocessing, initialize_model, loss_parts,
    stratified_episode_bootstrap, _validated_training_data,
)


def rows(n, split="train"):
    return [dict(episode_id=episode_key(TASKS[i % 5], 910000+i),
                 task=TASKS[i % 5], env_seed=910000+i, split=split, round=1)
            for i in range(n)]


def preprocessing():
    # Completely synthetic; never load an actual critic asset.
    return dict(norm_mean=torch.zeros(4096), norm_std=torch.ones(4096),
                visual_center=torch.zeros(8192), visual_basis=torch.eye(8192, 16),
                visual_scale=torch.ones(16), language_center=torch.zeros(2048),
                language_basis=torch.eye(2048, 8), language_scale=torch.ones(8),
                residual_scale=torch.tensor([.15, .15, .15, .4]))


def state_arrays(n):
    rng = torch.Generator().manual_seed(73)
    return dict(history=torch.randn(n, 5, 4096, generator=rng),
                history_mask=torch.ones(n, 5, dtype=torch.bool),
                proprio=torch.randn(n, 5, 4, generator=rng),
                proprio_mask=torch.ones(n, 5, dtype=torch.bool),
                past_actions=torch.randn(n, 4, 4, generator=rng),
                language=torch.randn(n, 2048, generator=rng),
                remaining=torch.full((n,), .8))


def test_loss_matches_manual_distinct_candidate_and_source_averages():
    p = torch.linspace(.2, .8, 26).reshape(2, 13)
    y = (torch.arange(104).reshape(2, 13, 4) % 3 == 0).float()
    # Second source aliases every slot to a0, yet retains one full source weight.
    ids = torch.stack([torch.arange(13), torch.zeros(13, dtype=torch.long)])
    p[1] = .4
    logits = torch.logit(p).requires_grad_(True)
    y[1] = 1
    weights = dedup_weights(ids)
    parts = loss_parts(logits, y, **weights)
    manual = []
    for source in range(2):
        target = y[source].numpy().mean(-1)
        probability = p[source].numpy()
        bce = -(target*np.log(probability)+(1-target)*np.log(1-probability))
        gain = ((probability-probability[0])-(target-target[0]))**2
        pair = np.array([((probability[a]-probability[b])-(target[a]-target[b]))**2
                         for a, b in PAIRS])
        terms = []
        for values, name in ((bce, "candidate_weights"), (gain, "gain_weights"), (pair, "pair_weights")):
            w = weights[name][source].numpy()
            terms.append(float((values*w).sum()/w.sum()) if w.sum() else 0.)
        manual.append(terms[0]+terms[1]+.5*terms[2])
    np.testing.assert_allclose(parts["per_source_loss"].detach(), manual, rtol=2e-6)
    assert float(parts["loss"].detach()) == pytest.approx(sum(manual)/2, rel=2e-6)
    assert parts["per_source_gain_mse"][1] == 0
    assert parts["per_source_pair_mse"][1] == 0
    parts["loss"].backward()
    assert torch.isfinite(logits.grad).all()


def test_raw_group_aliases_and_reversed_pair_duplicates_count_once():
    # Pairs1,2 share the same group pair in opposite orders; pair3 collapses.
    ids = torch.tensor([[0, 1, 2, 2, 1, 0, 0, 3, 4, 1, 0, 5, 6]])
    w = dedup_weights(ids)
    assert w["candidate_weights"].sum() == pytest.approx(7.)
    assert w["gain_weights"].sum() == pytest.approx(6.)
    assert torch.equal(w["gain_weights"][0, [0, 5, 6, 10]], torch.zeros(4))
    assert torch.equal(w["pair_weights"], torch.tensor([[.5, .5, 0., 1., 1.]]))
    masked = dedup_weights(ids, pair_mask=[[True, False, True, True, True]])
    assert masked["pair_weights"][0, 0] == 1
    assert masked["pair_weights"][0, 1] == 0
    w_all = dedup_weights(torch.zeros(1, 13, dtype=torch.long))
    assert w_all["gain_weights"].sum() == 0
    assert w_all["pair_weights"].sum() == 0


def test_masked_unknown_labels_are_not_fabricated_and_normal_is_separate():
    valid = torch.zeros(1, 13, dtype=torch.bool);valid[:, 0] = True
    weights = dedup_weights(torch.arange(13)[None], valid)
    y = torch.full((1, 13, 4), -1.);y[:, 0] = 1
    result = loss_parts(torch.zeros(1, 13), y, **weights)
    assert float(result["loss"]) == pytest.approx(math.log(2))
    invalid = dict(weights, candidate_weights=torch.ones(1, 13))
    with pytest.raises(ValueError, match="lacks all four"):
        loss_parts(torch.zeros(1, 13), y, **invalid)
    with pytest.raises(ValueError, match="normal control is separate"):
        loss_parts(torch.zeros(1, 14), torch.zeros(1, 14, 4), **weights)
    with pytest.raises(ValueError):
        loss_parts(torch.zeros(0, 13), torch.zeros(0, 13, 4), **weights)


def test_a_one_synthetic_update_only_changes_residual_advantage_and_keeps_anchor():
    old = initialize_model("B", seed=11, preprocessing=preprocessing())
    warm = checkpoint_state(old)
    warm_copy = {name: value.clone() for name, value in warm.items()}
    model = initialize_model("A", seed=12, warm_start_state=warm)
    before = checkpoint_state(model)
    trainable = [name for name, p in model.named_parameters() if p.requires_grad]
    assert trainable and all(name.split(".")[0] in ("residual", "advantage") for name in trainable)
    generator = torch.Generator().manual_seed(4)
    features = torch.randn(2, 61, generator=generator)
    actions = torch.rand(2, 13, 10, 4, generator=generator)*1.2-.6
    y = torch.randint(0, 2, (2, 13, 4), generator=generator).float()
    weights = dedup_weights(torch.arange(13)[None].expand(2, -1))
    with cpu_threads():
        baseline_before = model(features, actions)[:, 0].detach().clone()
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4, weight_decay=.01)
        optimizer.zero_grad(set_to_none=True)
        loss_parts(model(features, actions), y, **weights)["loss"].backward()
        assert torch.isfinite(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.))
        optimizer.step()
        after = checkpoint_state(model)
        # Existing inference evaluates head+actual-zero; cancellation is within
        # floating-point roundoff, while a0 gradient is exactly cancelled.
        torch.testing.assert_close(model(features, actions)[:, 0], baseline_before, rtol=1e-6, atol=1e-7)
        clones = actions[:, :1].expand(-1, 13, -1, -1)
        anchored = model(features, clones)
        # GEMM kernels can round identical input rows differently; the inherited
        # architecture guarantees analytic a0 cancellation, not bit identity.
        torch.testing.assert_close(anchored, anchored[:, :1].expand(-1, 13), rtol=1e-6, atol=1e-7)
    changed = [name for name in before if not torch.equal(before[name], after[name])]
    assert changed and all(name.split(".")[0] in ("residual", "advantage") for name in changed)
    assert all(torch.equal(value, warm_copy[name]) for name, value in warm.items())
    assert any(name.startswith("residual.") for name in changed)
    assert any(name.startswith("advantage.") for name in changed)


def test_b_capacity_fresh_seed_and_checkpoint_state_compatibility():
    model = initialize_model("B", seed=71, preprocessing=preprocessing())
    equal = initialize_model("B", seed=71, preprocessing=preprocessing())
    other = initialize_model("B", seed=72, preprocessing=preprocessing())
    assert sum(p.numel() for p in model.parameters()) == 7058
    assert all(p.requires_grad for p in model.parameters())
    assert all(torch.equal(a, b) for a, b in zip(model.parameters(), equal.parameters()))
    assert any(not torch.equal(a, b) for a, b in zip(model.parameters(), other.parameters()))
    stream = io.BytesIO();torch.save(checkpoint_state(model), stream);stream.seek(0)
    loaded = from_state(torch.load(stream, weights_only=True, map_location="cpu")).eval().requires_grad_(False)
    features = torch.zeros(2, 61);actions = torch.zeros(2, 13, 10, 4)
    with cpu_threads(), torch.no_grad():
        assert torch.equal(model(features, actions), loaded(features, actions))
    assert not any(p.requires_grad for p in loaded.parameters())


def test_pca_uses_only_unique_train_rows_and_canonical_singleton_features():
    manifest = rows(20)
    manifest[18]["split"] = "development";manifest[19]["split"] = "held"
    arrays = state_arrays(20)
    prep, audit = fit_train_preprocessing(arrays, manifest, range(18), norm_mean=torch.zeros(4096), norm_std=torch.ones(4096))
    changed = {key: value.clone() for key, value in arrays.items()}
    changed["history"][18:] = 1e6;changed["language"][18:] = -1e6
    prep2, _ = fit_train_preprocessing(changed, manifest, range(18), norm_mean=torch.zeros(4096), norm_std=torch.ones(4096))
    assert all(torch.equal(prep[key], prep2[key]) for key in prep)
    assert prep["visual_basis"].shape == (8192, 16)
    assert prep["language_basis"].shape == (2048, 8)
    assert audit["fit_source_count"] == 18 and audit["train_only"]
    assert len(audit["pca_diagnostics"]["visual"]["singular_values"]) == 18
    assert audit["pca_diagnostics"]["language"]["scale_floor"] == .001
    assert audit["fit_episode_ids"] == [row["episode_id"] for row in manifest[:18]]
    for invalid in (list(range(18))+[0], list(range(19))):
        with pytest.raises(ValueError):
            fit_train_preprocessing(arrays, manifest, invalid, norm_mean=torch.zeros(4096), norm_std=torch.ones(4096))
    model = initialize_model("B", seed=11, preprocessing=prep)
    features = canonical_features(model, arrays)
    with cpu_threads(), torch.no_grad():
        explicit = torch.cat([model.features({key: arrays[key][i:i+1] for key in STATE_KEYS}) for i in range(20)])
    assert features.shape == (20, 61) and not features.requires_grad
    assert torch.equal(features, explicit)


def test_bagging_is_task_stratified_episode_grouped_and_label_blind():
    manifest = rows(25)
    first = stratified_episode_bootstrap(manifest, seed=317)
    second = stratified_episode_bootstrap(manifest, seed=317)
    assert first == second
    assert len(first["indices"]) == 25
    assert sum(first["multiplicities"].values()) == 25
    assert all(value == dict(unique_available=5, drawn=5) for value in first["per_task"].values())
    assert first["episode_ids"] == [manifest[i]["episode_id"] for i in first["indices"]]
    with_labels = [dict(row, success=i % 2, informative=i % 3) for i, row in enumerate(manifest)]
    assert stratified_episode_bootstrap(with_labels, seed=317) == first
    assert not first["outcome_weighting"]
    for invalid in ([*manifest, manifest[0]], [dict(manifest[0], split="held")]):
        with pytest.raises(ValueError):
            stratified_episode_bootstrap(invalid, seed=317)


def test_training_dataset_blocks_incomplete_aliases_and_outcome_weighting():
    data = dict(rows=rows(1), actions=torch.zeros(1, 13, 10, 4),
                outcomes=torch.zeros(1, 13, 4), group_ids=torch.zeros(1, 13, dtype=torch.long))
    checked = _validated_training_data(data)
    assert checked[3]["pair_weights"].sum() == 0
    bad = deepcopy(data);bad["outcomes"][0, 1, 0] = 1
    with pytest.raises(ValueError, match="aliases disagree"):
        _validated_training_data(bad)
    bad = deepcopy(data);bad["outcomes"][0, 1, 0] = -1
    with pytest.raises(ValueError, match="complete, binary"):
        _validated_training_data(bad)
    bad = deepcopy(data);bad["candidate_weights"] = torch.ones(1, 13)
    with pytest.raises(ValueError, match="disagrees"):
        _validated_training_data(bad)


def test_selection_uses_full_planned_denominator_with_paired_rescue_harm_and_ties():
    p = torch.full((4, 3, 13), .2)
    p[:, 0, 1] = .8  # choose a candidate on source0
    p[:, 1] = .4     # tie keeps a0 on source1
    p[:, 2] = float("nan")  # no-cut row is not scored
    y = torch.zeros(3, 13, 4)
    y[0, 0] = torch.tensor([0, 0, 1, 1])
    y[0, 1] = torch.tensor([1, 1, 0, 1])  # 2 rescue,1 harm
    y[1] = torch.tensor([1, 0, 0, 1]).expand(13, -1)
    y[2] = 1
    weights = dedup_weights(torch.arange(13)[None].expand(3, -1))["gain_weights"]
    result = checkpoint_selection_metrics(p, y, reached_mask=[True, True, False], gain_weights=weights)
    assert result["selected_slots"] == [1, 0, 0]
    assert result["rescues"] == 2 and result["harms"] == 1
    assert result["gain"] == pytest.approx(1/12)
    assert result["gain_conditional"] == pytest.approx(1/8)
    assert result["selected_success"] == pytest.approx(9/12)
    assert result["baseline_success"] == pytest.approx(8/12)
    assert result["gain_mse"] == pytest.approx(((.6-.25)**2+11*(0+.5)**2)/12/2)
    bad = y.clone();bad[2, 1, 0] = 0
    with pytest.raises(ValueError, match="No-cut"):
        checkpoint_selection_metrics(p, bad, reached_mask=[True, True, False], gain_weights=weights)


def test_checkpoint_tiebreaks_follow_registered_order_and_cannot_mix_banks():
    def record(path="A", step=200, gain=.1, harms=3, gain_mse=.2):
        return dict(path=path, step=step, phase="round1", dataset_sha256="synthetic-only",
                    metrics=dict(planned_episodes=100, gain=gain, harms=harms, gain_mse=gain_mse))
    comparisons = [
        (record("A", 200), record("B", 400, gain=.11)),
        (record("A", 200), record("B", 400, harms=2)),
        (record("A", 200), record("B", 400, gain_mse=.1)),
        (record("B", 400), record("A", 200)),
        (record("A", 200), record("B", 200)),
    ]
    for inferior, better in comparisons:
        assert choose_checkpoint([inferior, better]) == better
    with pytest.raises(ValueError, match="different banks"):
        choose_checkpoint([record(), dict(record("B"), dataset_sha256="other")])
    with pytest.raises(ValueError, match="Duplicate"):
        choose_checkpoint([record(), record()])
    assert CHECKPOINTS["round1"][-1] == 2400 and CHECKPOINTS["final"][-1] == 4000


def test_fit_entry_fails_pending_stage_before_ledger_or_model_access():
    class NoLedgerAccess:
        def reserve(self, *args, **kwargs):
            pytest.fail("Pending training stage reached update ledger")
    for phase in ("round1", "final"):
        for path in ("A", "B"):
            with pytest.raises(ProtocolError):
                fit_member(pending_protocol(), NoLedgerAccess(), phase=phase, path=path,
                           member=0, model=None, features=None, data=None)
