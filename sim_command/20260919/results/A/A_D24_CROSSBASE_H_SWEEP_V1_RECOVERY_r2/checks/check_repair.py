"""Narrow CPU regression for the observed cached-statistics failure and recovery partition."""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import paths
import torch
from lerobot.configs.types import FeatureType, NormalizationMode, PolicyFeature
from lerobot.processor.normalize_processor import UnnormalizerProcessorStep
from action_postprocessor import autograd_safe_postprocessor
from admission import authority, frozen_units
from combined_publication import merge_cells

torch.set_num_threads(1)


def processor():
    return UnnormalizerProcessorStep(
        features={'action': PolicyFeature(type=FeatureType.ACTION, shape=(4,))},
        norm_map={FeatureType.ACTION: NormalizationMode.MEAN_STD},
        stats={'action': {'mean': [0.01, 0.02, 0.03, 0.04], 'std': [0.1, 0.2, 0.3, 0.4]}},
        device='cpu')


broken = processor()
with torch.inference_mode():
    original_values = broken._normalize_action(torch.zeros((10, 4), dtype=torch.float64), inverse=True)
assert any(t.is_inference() for t in broken._tensor_stats['action'].values())
try:
    leaf = torch.zeros((10, 4), dtype=torch.float64, requires_grad=True)
    torch.autograd.grad(broken._normalize_action(leaf, inverse=True).sum(), leaf)
except RuntimeError as exc:
    assert 'Inference tensors cannot be saved for backward' in str(exc)
    reproduced = str(exc)
else:
    raise AssertionError('Did not reproduce the recorded failure with the real normalizer')

fixed = processor()
post = autograd_safe_postprocessor(lambda a: fixed._normalize_action(a, inverse=True))
checks = []
for dtype in (torch.float64, torch.float32, torch.bfloat16, torch.float64):
    with torch.inference_mode():
        values = post(torch.zeros((10, 4), dtype=dtype))
    assert not any(t.is_inference() for t in fixed._tensor_stats['action'].values())
    leaf = torch.zeros((10, 4), dtype=dtype, requires_grad=True)
    physical = post(leaf)
    gradient = torch.autograd.grad(physical.clamp(-1, 1).sum(), leaf)[0]
    expected = fixed._tensor_stats['action']['std'].expand(10, 4)
    assert torch.equal(gradient, expected)
    assert torch.equal(physical.detach(), values)
    checks.append({'dtype': str(dtype), 'exact_normalization_and_gradient': True})
assert torch.equal(post(torch.zeros((10, 4), dtype=torch.float64)), original_values)

authorization = authority()
units = frozen_units()
excluded = set(json.loads((ROOT / 'EXCLUDED_VALID_UNITS.json').read_text())['unit_ids'])
assert len(units) == 1939 and len(excluded) == 2061 and not set(units) & excluded
assert 2442 + len(units) == 4381 <= authorization['nodes']['A']['stage_attempt_cap']
assert {u['method'] for u in units.values()} == {'Post', 'Velocity'}
old = Path(paths.CONFIG['old_root'])
assert (ROOT / 'code/native_velocity.py').read_bytes() == (old / 'code/native_velocity.py').read_bytes()
assert (ROOT / 'code/queue_protocol.py').read_bytes() == (old / 'code/queue_protocol.py').read_bytes()
for p in (ROOT / 'code').glob('*.py'):
    ast.parse(p.read_text(), filename=str(p))
model_tree = ast.parse((ROOT / 'code/smol_server.py').read_text())
assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'autograd_safe_postprocessor' for n in ast.walk(model_tree))
old_cells = json.loads((old / 'FINAL_SUMMARY.json').read_text())['cells']
merged = merge_cells(old_cells, {})
assert sum(c['valid'] for c in merged) == 2061 and sum(c['attempts_all_versions'] for c in merged) == 2442

result = {'status': 'PASS', 'device': 'CPU only', 'scientific_compute': 0, 'model_loads': 0,
          'environment_loads': 0, 'hardware_queries': 0, 'claims_created': 0,
          'real_normalizer_failure_reproduced': reproduced, 'dtype_checks': checks,
          'unit_partition': {'preserved_valid': 2061, 'pending': 1939, 'projected_total_attempts': 4381},
          'native_velocity_and_queue_byte_unchanged': True, 'actual_model_server_wrapper_wiring': True,
          'all_private_code_AST': True, 'prior_attempts_in_combined_publication': 2442}
(ROOT / 'CPU_REPAIR_CHECK.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
