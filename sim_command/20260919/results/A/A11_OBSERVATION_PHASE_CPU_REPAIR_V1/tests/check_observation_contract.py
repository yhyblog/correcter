"""Targeted stdlib CPU fixture: actual CONFIG/caller AST/scope/hooks/journal."""
import ast
import copy
import hashlib
import importlib.abc
import json
import os
from pathlib import Path
import sys
import time
from contextlib import contextmanager
from types import SimpleNamespace
import uuid

P = Path(__file__).resolve().parents[1]
B = P.parents[2]
OLD = B / 'results/A/A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1'
NATIVE = B / 'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code/native'
W = B / 'work/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1_r1'
DEST = W / 'targeted_v1'
DEST.mkdir(exist_ok=False)
sys.dont_write_bytecode = True
BLOCKED = {'torch', 'mujoco', 'gymnasium', 'lerobot', 'ctypes', 'pynvml', 'pycuda', 'OpenGL'}


class ForbidRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in BLOCKED:
            raise RuntimeError('CPU fixture forbidden import: ' + fullname)


sys.meta_path.insert(0, ForbidRuntime())
sys.path.insert(0, str(P / 'code'))
import inheritance
from observation_phase import observation_phase, validate_observation_config
from core import contracts

checks = []
synthetic = {'native_stub_calls': 0, 'scope_entries': 0, 'journal_rows': 0,
             'actual_reset_callsite_AST_evaluations': 0, 'actual_step_callsite_AST_evaluations': 0}


def record(name, **evidence):
    checks.append(dict(name=name, status='PASS', synthetic=True, **evidence))


def reject(fn, error=(ValueError, TypeError, KeyError)):
    try:
        fn()
    except error as e:
        return type(e).__name__ + ': ' + str(e)
    raise AssertionError('Expected rejection')


class SyntheticStore:
    def append(self, path, raw):
        row = json.loads(raw)
        row['synthetic'] = True
        with Path(path).open('a') as f:
            f.write(json.dumps(row, sort_keys=True) + '\n')
        synthetic['journal_rows'] += 1


contracts.configure_store(SyntheticStore())
cfg = json.loads((P / 'config/CONFIG.json').read_text())
phase_result = validate_observation_config(cfg)
assert len(cfg['native']['observation_phases']) == 301
record('actual_CONFIG_exact_301', result=phase_result)

class IntSubclass(int):
    pass

invalid_clocks = [-1, 301, -10**100, 10**100, True, False, 0.0, 300.0,
                  '0', 'step_0', None, [], {}, IntSubclass(0)]
clock_rejections = [{'repr': repr(x), 'error': reject(lambda x=x: observation_phase(x))} for x in invalid_clocks]
record('strict_clock_rejects_no_coercion', cases=clock_rejections)

config_bad = []
def bad_config(name, mutate):
    x = copy.deepcopy(cfg)
    mutate(x)
    config_bad.append({'case': name, 'error': reject(lambda: validate_observation_config(x))})
bad_config('old_17_item_limit', lambda x: x['native'].update(observation_phases=x['native']['observation_phases'][:17]))
bad_config('missing_s300', lambda x: x['native']['observation_phases'].pop())
bad_config('extra_s301', lambda x: x['native']['observation_phases'].append('step_301'))
bad_config('duplicate_s299', lambda x: x['native']['observation_phases'].__setitem__(300, 'step_299'))
bad_config('old_spelling', lambda x: x['native']['observation_phases'].__setitem__(0, 'step0'))
bad_config('wrong_order', lambda x: x['native']['observation_phases'].reverse())
bad_config('wildcard', lambda x: x['native']['observation_phases'].__setitem__(0, 'step_*'))
bad_config('non_string', lambda x: x['native']['observation_phases'].__setitem__(0, 0))
bad_config('tuple', lambda x: x['native'].update(observation_phases=tuple(x['native']['observation_phases'])))
for value in (299, 301, 300.0, True):
    bad_config('target_' + repr(value), lambda x, value=value: x['source'].update(absolute_target=value))
record('CONFIG_rejects_truncation_drift_and_wrong_target', cases=config_bad)

native_tree = ast.parse((NATIVE / 'native_egl.py').read_text())
native_class = next(x for x in native_tree.body if isinstance(x, ast.ClassDef) and x.name == 'NativeEGL')
methods = [copy.deepcopy(x) for x in native_class.body if isinstance(x, ast.FunctionDef)
           and x.name in ('observation_scope', 'install_native_hooks')]
assert len(methods) == 2
new_class = ast.ClassDef(name='ActualScopeAndHooks', bases=[], keywords=[], body=methods, decorator_list=[])
ns = {'contextmanager': contextmanager, 'Refused': contracts.ContractError}
exec(compile(ast.fix_missing_locations(ast.Module(body=[new_class], type_ignores=[])),
             str(NATIVE / 'native_egl.py'), 'exec'), ns)
ActualScopeAndHooks = ns['ActualScopeAndHooks']

journal_tree = ast.parse((NATIVE / 'graphics_contract.py').read_text())
journal_class = next(x for x in journal_tree.body if isinstance(x, ast.ClassDef) and x.name == 'Journal')
caps_stmt = next(x for x in journal_tree.body if isinstance(x, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'CAPS' for t in x.targets))
journal_caps = ast.literal_eval(caps_stmt.value)
jns = dict(Path=Path, json=json, os=os, time=time, uuid=uuid, Refused=contracts.ContractError)
exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(journal_class)], type_ignores=[])),
             str(NATIVE / 'graphics_contract.py'), 'exec'), jns)
ActualJournal = jns['Journal']

def runtime(name, failing=None):
    obj = ActualScopeAndHooks()
    obj.config = cfg['native']
    obj.phase = None
    obj.journal = ActualJournal(DEST / (name + '.jsonl'), journal_caps)
    obj.journal.observation_phase = None
    obj.patches = []
    obj.render_contexts = []
    obj.shim = object()
    obj.close = lambda: None
    def stub(key):
        def original(*args, **kwargs):
            synthetic['native_stub_calls'] += 1
            if key == failing:
                raise RuntimeError('synthetic native stub failure')
            return key
        return original
    mj = SimpleNamespace(**{k: stub(k) for k in ('MjrContext', 'mjv_updateScene', 'mjr_setBuffer', 'mjr_render', 'mjr_readPixels')})
    class Viewer:
        def __init__(self, *args, **kwargs):
            pass
        def free(self):
            pass
        def close(self):
            pass
    def _import_egl():
        raise AssertionError('No renderer creation in a CPU fixture')
    rendering = SimpleNamespace(_ALL_RENDERERS={'egl': _import_egl}, OffScreenViewer=Viewer)
    # Actual hook method sees a CPU namespace; no mujoco module is installed/imported.
    ns['sys'] = SimpleNamespace(modules={'mujoco.egl': obj.shim})
    obj.install_native_hooks(mj, rendering)
    return obj, mj

engine_tree = ast.parse((P / 'code/runtime_engine.py').read_text())
engine_class = next(x for x in engine_tree.body if isinstance(x, ast.ClassDef) and x.name == 'Engine')
callsites = {}
for method in engine_class.body:
    if isinstance(method, ast.FunctionDef) and method.name in ('reset', 'step'):
        expressions = [x.context_expr for stmt in ast.walk(method) if isinstance(stmt, ast.With)
                       for x in stmt.items if isinstance(x.context_expr, ast.Call)
                       and isinstance(x.context_expr.func, ast.Attribute)
                       and x.context_expr.func.attr == 'observation_scope']
        assert len(expressions) == 1
        callsites[method.name] = expressions[0]
assert ast.unparse(callsites['reset']) == 'self.egl.observation_scope(observation_phase(0))'
assert ast.unparse(callsites['step']) == 'self.egl.observation_scope(observation_phase(step + 1))'
imports = [x for x in engine_tree.body if isinstance(x, ast.ImportFrom) and x.module == 'observation_phase']
assert len(imports) == 1 and [(a.name, a.asname) for a in imports[0].names] == [('observation_phase', None)]
compiled_calls = {k: compile(ast.Expression(copy.deepcopy(v)), str(P / 'code/runtime_engine.py'), 'eval')
                  for k, v in callsites.items()}
record('real_reset_and_step_callsite_AST_same_function', expressions={k: ast.unparse(v) for k, v in callsites.items()})

obj, mj = runtime('all_301_actual_scope_hooks_journal')
seen = []
for clock in range(301):
    site = 'reset' if clock == 0 else 'step'
    env = {'self': SimpleNamespace(egl=obj), 'step': clock - 1, 'observation_phase': observation_phase}
    with eval(compiled_calls[site], env):
        synthetic['actual_' + site + '_callsite_AST_evaluations'] += 1
        synthetic['scope_entries'] += 1
        expected = observation_phase(clock)
        assert obj.phase == obj.journal.observation_phase == expected
        for key in ('mjv_updateScene', 'mjr_render', 'mjr_readPixels'):
            assert getattr(mj, key)() == key
        if clock == 0:
            assert mj.mjr_setBuffer() == 'mjr_setBuffer'
        seen.append(expected)
    assert obj.phase is None and obj.journal.observation_phase is None
assert seen == cfg['native']['observation_phases']
rows = [json.loads(x) for x in obj.journal.path.read_text().splitlines()]
assert len(rows) == 1808 and all(x['synthetic'] for x in rows)
for phase in seen:
    events = [x for x in rows if x['native_observation_phase'] == phase and x['phase'] == 'entered']
    assert {x['operation'] for x in events} == ({'mujoco_scene_updates', 'render_calls', 'rgb_readback_calls', 'mujoco_set_buffer_calls'}
                                               if phase == 'step_0' else {'mujoco_scene_updates', 'render_calls', 'rgb_readback_calls'})
record('s0_to_s300_actual_calls_scope_hooks_and_journal', stages=301, journal_rows=len(rows),
       journal_event_pairs=904, boundary_stages=[seen[i] for i in (0, 16, 17, 299, 300)],
       journal_path=str(obj.journal.path), extra_real_operations=0)

bad_names = ['step0', 'step1', 'step16', 'step17', 'step300', 'step_00', 'step_-1',
             'step_301', 'step_*', '', 'step_0 ', None, True, 0]
bad_scope = []
for value in bad_names:
    bad_scope.append({'value': repr(value), 'error': reject(lambda value=value: obj.observation_scope(value).__enter__())})
    assert obj.phase is None and obj.journal.observation_phase is None
record('actual_scope_rejects_old_spellings_and_invalid_names', cases=bad_scope)

for clock in (0, 16, 17, 299, 300):
    phase = observation_phase(clock)
    with obj.observation_scope(phase):
        synthetic['scope_entries'] += 1
        reject(lambda: obj.observation_scope(observation_phase(0)).__enter__())
        assert obj.phase == obj.journal.observation_phase == phase
    try:
        with obj.observation_scope(phase):
            synthetic['scope_entries'] += 1
            raise RuntimeError('synthetic body failure')
    except RuntimeError:
        pass
    assert obj.phase is None and obj.journal.observation_phase is None
    with obj.observation_scope(phase):
        synthetic['scope_entries'] += 1
        assert obj.phase == obj.journal.observation_phase == phase
    assert obj.phase is None and obj.journal.observation_phase is None
record('actual_scope_boundary_nested_rejection_exception_cleanup_and_reentry', stages=[0, 16, 17, 299, 300])

before = obj.journal.path.read_bytes()
for key in ('mjv_updateScene', 'mjr_render', 'mjr_readPixels', 'mjr_setBuffer'):
    reject(getattr(mj, key))
obj.phase = 'step0'
reject(mj.mjr_render)
obj.phase = None
assert obj.journal.path.read_bytes() == before
record('actual_render_hooks_reject_outside_scope_before_journal_entry', rejected_calls=5)

err_obj, err_mj = runtime('actual_hook_exception', failing='mjr_render')
try:
    with err_obj.observation_scope(observation_phase(17)):
        synthetic['scope_entries'] += 1
        err_mj.mjr_render()
except RuntimeError as e:
    assert str(e) == 'synthetic native stub failure'
assert err_obj.phase is None and err_obj.journal.observation_phase is None
err_rows = [json.loads(x) for x in err_obj.journal.path.read_text().splitlines()]
assert [x['phase'] for x in err_rows] == ['entered', 'failed']
assert all(x['native_observation_phase'] == 'step_17' for x in err_rows)
with err_obj.observation_scope(observation_phase(300)):
    synthetic['scope_entries'] += 1
    assert err_mj.mjr_readPixels() == 'mjr_readPixels'
record('actual_journal_records_failed_hook_with_phase_and_scope_recovers', journal=str(err_obj.journal.path))

# Prove no numerical method change beyond the two canonical context expressions.
old_tree = ast.parse((OLD / 'code/runtime_engine.py').read_text())
normalized = copy.deepcopy(engine_tree)
normalized.body = [x for x in normalized.body if not (isinstance(x, ast.ImportFrom) and x.module == 'observation_phase')]
old_engine = next(x for x in old_tree.body if isinstance(x, ast.ClassDef) and x.name == 'Engine')
new_engine = next(x for x in normalized.body if isinstance(x, ast.ClassDef) and x.name == 'Engine')
for name in ('reset', 'step'):
    old_method = next(x for x in old_engine.body if isinstance(x, ast.FunctionDef) and x.name == name)
    new_method = next(x for x in new_engine.body if isinstance(x, ast.FunctionDef) and x.name == name)
    old_arg = next(x for x in ast.walk(old_method) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                   and x.func.attr == 'observation_scope').args[0]
    new_call = next(x for x in ast.walk(new_method) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                   and x.func.attr == 'observation_scope')
    new_call.args[0] = copy.deepcopy(old_arg)
assert ast.dump(normalized, include_attributes=False) == ast.dump(old_tree, include_attributes=False)
record('whole_Engine_AST_unchanged_except_two_scope_arguments_and_import')

auth_tree = ast.parse((P / 'code/authorization.py').read_text())
auth = next(x for x in auth_tree.body if isinstance(x, ast.FunctionDef) and x.name == 'load_authorization')
validations = [x for x in ast.walk(auth) if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
               and x.func.id == 'validate_observation_config']
assert len(validations) == 1
assert any(isinstance(x, ast.Expr) and x.value is validations[0] for x in auth.body)
full = next(x for x in auth.body if isinstance(x, ast.If) and isinstance(x.test, ast.Name) and x.test.id == 'full')
assert validations[0].lineno < full.lineno
entry_evidence = []
for name, barriers in [('launch.py', ['exclusive_record', 'claim', 'verify_device']),
                       ('child.py', ['verify_device', 'Engine'])]:
    tree = ast.parse((P / 'code' / name).read_text())
    main = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'main')
    auth_line = min(x.lineno for x in ast.walk(main) if isinstance(x, ast.Call)
                    and isinstance(x.func, ast.Name) and x.func.id == 'load_authorization')
    later = [x.lineno for x in ast.walk(main) if isinstance(x, ast.Call)
             and ((isinstance(x.func, ast.Name) and x.func.id in barriers)
                  or (isinstance(x.func, ast.Attribute) and x.func.attr == 'prepare'))]
    assert later and all(auth_line < x for x in later)
    entry_evidence.append({'file': name, 'authorization_line': auth_line, 'hardware_model_or_claim_lines': later})
record('config_validation_unconditional_before_claim_model_and_hardware', entry_evidence=entry_evidence,
       validator_line=validations[0].lineno)

old_config = json.loads((OLD / 'config/CONFIG.json').read_text())
restored_config = copy.deepcopy(cfg)
restored_config['native']['observation_phases'] = old_config['native']['observation_phases']
assert restored_config == old_config
record('CONFIG_only_observation_phase_list_changed')
assert not any(name.split('.')[0] in BLOCKED for name in sys.modules)
record('forbidden_runtime_imports_absent_and_no_real_entry_invoked')
result = dict(status='PASS', synthetic=True, checks=checks, check_groups=len(checks),
              synthetic_operations=synthetic, real_operations=0,
              actual_native_module_imports=0, actual_Engine_module_imports=0,
              extraction='Exact actual class methods/Journal AST and actual two context-expression ASTs; stdlib CPU stubs only.',
              no_old_test_suites=True)
with (P / 'CPU_PHASE_CHECKS.json').open('x') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps(result, ensure_ascii=False))
