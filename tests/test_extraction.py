"""Check extracted inference against archived code and the real frozen assets."""
import ast
import hashlib
import json
import math
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest
import torch
from torch import nn
from torch.nn import functional as F

from corrector.actions import ActionTransform, GuidanceError
from corrector.config import DEFAULT_MATCHING, MATCHED
from corrector.critic import FrozenSelector, STATE_KEYS
from corrector.guidance import FrozenObjective, critic_threads, flow_update, post_direction


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'provenance' / 'source_snapshot'


def reference_definitions(relative, names):
    """Execute only requested definitions, never the archived repo imports."""
    path = SNAPSHOT / relative
    assert path.is_file(), f'Missing source snapshot: {path}'
    original = ast.parse(path.read_text(), filename=str(path))
    definitions = [node for node in original.body
                   if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert {node.name for node in definitions} == set(names)
    namespace = dict(np=np, torch=torch, nn=nn, F=F, math=math, time=time,
                     hashlib=hashlib, contextmanager=contextmanager,
                     GuidanceError=GuidanceError, STATE_KEYS=STATE_KEYS, MATCHED=MATCHED)
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


@pytest.fixture(scope='module')
def selector():
    return FrozenSelector()


def observed_context():
    generator = torch.Generator().manual_seed(20260916)
    return dict(history=torch.randn(5, 4096, generator=generator), history_mask=torch.ones(5),
                proprio=torch.randn(5, 4, generator=generator), proprio_mask=torch.ones(5),
                past_actions=torch.randn(4, 4, generator=generator),
                language=torch.randn(2048, generator=generator), remaining=torch.tensor([.7]))


def test_actual_checkpoints_and_gradients_are_bit_identical_to_archived_inference(selector):
    reference = reference_definitions('src/ac_tmil/ogg_research_v3/learning.py',
                                      ['observed_features', 'TenStepCritic', 'from_state'])
    reference_models = [reference['from_state'](torch.load(path, map_location='cpu', weights_only=True))
                        .eval().requires_grad_(False) for path in selector.model_paths]
    observed = observed_context()
    base = np.random.default_rng(16).uniform(-.5, .5, (50, 4)).astype(np.float32)
    actual = FrozenObjective(observed, base, selector=selector)
    expected = FrozenObjective(observed, base, models=reference_models)
    candidate = base[:10] + np.float32(.01)
    assert actual.evaluate(candidate) == expected.evaluate(candidate)
    torch.testing.assert_close(actual.gradient()[0], expected.gradient()[0], rtol=0, atol=0)
    for first, second in zip(actual.features, expected.features):
        torch.testing.assert_close(first, second, rtol=0, atol=0)
    assert selector.verify(check_files=True) and actual.verify()


@pytest.mark.parametrize('mode', ['velocity', 'direct'])
def test_flow_injection_matches_archived_update_exactly(mode):
    reference = reference_definitions('src/ac_tmil/ogg_flow/guidance.py',
                                      ['critic_threads', '_gradient_summary', '_distance', 'flow_update'])
    transform = ActionTransform.from_checkpoint(ROOT / 'assets' / 'action_transform', device='cpu')
    generator = torch.Generator().manual_seed(3941)
    x = torch.randn(1, 50, 32, generator=generator) * .3
    velocity = torch.randn(1, 50, 32, generator=generator) * .1
    objective = lambda actions: -(actions - .25).square().mean()
    settings = dict(mode=mode, alpha=10.)
    with critic_threads():
        actual, actual_log = flow_update(x, velocity, .3, transform, objective, settings)
        expected, expected_log = reference['flow_update'](x, velocity, .3, transform, objective, settings)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert actual_log == expected_log


def test_post_direction_preserves_original_numpy_metric_and_single_backward(selector):
    transform = ActionTransform.from_checkpoint(ROOT / 'assets' / 'action_transform', device='cpu')
    objective = FrozenObjective(observed_context(), np.zeros((50, 4), np.float32), selector=selector)
    gradient, _ = objective.gradient()
    scales = ((transform.q99 - transform.q01) / 2).detach().cpu().numpy()
    expected = gradient.numpy() * scales[None] ** 2
    before = objective.backward_calls
    actual, diagnostics = post_direction(objective, transform)
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == np.float32 and actual.shape == (10, 4)
    assert objective.backward_calls - before == 1
    assert diagnostics['metric'] == 'S squared command gradient'
    assert objective.verify()


def test_matching_keeps_all_five_direction_radius_dependencies():
    from corrector.candidates import construct
    reference = reference_definitions('src/ac_tmil/ogg_flow/candidates.py', ['radii', 'construct'])
    rng = np.random.default_rng(1584)
    base = rng.uniform(-.8, .8, (50, 4)).astype(np.float32)
    velocity = np.clip(base + rng.normal(0, .04, base.shape), -1, 1).astype(np.float32)
    direct = np.clip(base + rng.normal(0, .12, base.shape), -1, 1).astype(np.float32)
    post = rng.normal(size=(10, 4)).astype(np.float32)
    actual, actual_log = construct(base, velocity, direct, post, 548, DEFAULT_MATCHING)
    expected, expected_log = reference['construct'](base, velocity, direct, post, 548, DEFAULT_MATCHING)
    assert actual.keys() == expected.keys()
    for method in actual:
        np.testing.assert_array_equal(actual[method], expected[method])
    assert actual_log == expected_log
    assert set(actual_log['groups']['xyz']['feasible_radii']) == set(MATCHED)


def test_loader_rejects_changed_checkpoint_hash(tmp_path):
    assets = ROOT / 'assets' / 'critic'
    ranking = json.loads((assets / 'ranking.json').read_text())
    ranking['model_hashes'][next(iter(ranking['model_hashes']))] = '0' * 64
    (tmp_path / 'ranking.json').write_text(json.dumps(ranking))
    (tmp_path / 'models').symlink_to(assets / 'models', target_is_directory=True)
    with pytest.raises(ValueError, match='checkpoint SHA changed'):
        FrozenSelector(tmp_path)
