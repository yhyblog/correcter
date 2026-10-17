"""Exercise the actual native summary function without importing its GPU module."""
import ast
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from summary_json import native_summary_for_json

SOURCE = Path('/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/src/lerobot/scripts/lerobot_eval_modified_detection.py')
tree = ast.parse(SOURCE.read_text())
names = {'_compute_recovery_latencies', '_make_episode_summary'}
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
assert len(functions) == 2
scope = {'np': np, 'Any': Any}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), 'exec'), scope)
summary = scope['_make_episode_summary']


def make(et, th, flags):
    return summary(task_group='synthetic', task_id=0, task_description='CPU fixture',
                   episode_idx=0, success=True, t_env=len(et), et_values=et,
                   thresh_values=th, meltdown_flags=flags, episode_error='')


checks = []
row = make([0.1, 0.2], [0.3, 0.3], [False, False])
try:
    json.dumps(row, allow_nan=False)
except ValueError:
    checks.append('actual_native_no_meltdown_reproduces_strict_JSON_failure')
else:
    raise AssertionError('Expected native NaN reproduction')
clean, reasons = native_summary_for_json(row)
assert clean['success'] is True and clean['env_steps_executed'] == 2
assert reasons == {'recovery_rate_after_meltdown': 'no_meltdown_events',
                   'recovery_steps_mean': 'no_observed_recoveries'}
json.dumps(clean, allow_nan=False)
checks.append('undefined_recovery_fields_are_null_with_explicit_reasons')

row = make([1.0, 0.1], [0.3, 0.3], [True, False])
clean, reasons = native_summary_for_json(row)
assert clean == row and reasons == {}
checks.append('finite_actual_native_summary_preserved_exactly')

row = make([], [], [])
clean, reasons = native_summary_for_json(row)
assert len(reasons) == 9
json.dumps(clean, allow_nan=False)
checks.append('empty_actual_native_statistics_explicitly_unavailable')

for field, value in [('et_mean', math.nan), ('et_mean', math.inf), ('unexpected', math.nan)]:
    row = make([0.1], [0.3], [False])
    row[field] = value
    try:
        native_summary_for_json(row)
    except ValueError:
        pass
    else:
        raise AssertionError('Unexpected nonfinite metric was concealed')
checks.append('unexpected_nan_and_all_infinities_rejected')

fixed = Path(__file__).with_name('resident_worker.repaired.py')
tree = ast.parse(fixed.read_text())
method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'episode_summary')
text = ast.get_source_segment(fixed.read_text(), method)
assert text.index("new_json(env.ep/'CORE_TERMINAL.json'") < text.index('native_summary_for_json(row)')
checks.append('actual_worker_patch_persists_core_before_diagnostic_serialization')

result = dict(status='PASS', synthetic=True, scientific_compute=0,
              torch_imported=False, actual_model_or_environment_calls=0,
              original_summary_source=str(SOURCE),
              original_summary_source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              tested_actual_native_functions=sorted(names), checks=checks)
target = Path(__file__).with_name('CPU_CHECK.json')
with target.open('x') as f:
    json.dump(result, f, indent=2, allow_nan=False)
    f.write('\n')
print(json.dumps(result))
