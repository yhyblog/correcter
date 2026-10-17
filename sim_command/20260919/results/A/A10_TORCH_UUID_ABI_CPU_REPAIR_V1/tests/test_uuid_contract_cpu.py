"""Targeted UUID/authorization fakes. Never import Torch or load a driver."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

FORBIDDEN = {'torch', 'mujoco', 'metaworld', 'gymnasium', 'OpenGL', 'numpy', 'pynvml'}
blocked = []


def audit(event, args):
    if (event == 'import' and args[0].split('.')[0] in FORBIDDEN) or event in (
            'ctypes.dlopen', 'ctypes.dlsym', 'subprocess.Popen', 'os.system'):
        blocked.append({'event': event, 'name': str(args[0]) if args else None})
        raise RuntimeError('Forbidden CPU-test operation: ' + event)


assert not FORBIDDEN.intersection(sys.modules)
sys.addaudithook(audit)
PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE/'code'))
from core.native_egl import NativeEGL, check_policy_uuid
from core.graphics_contract import Refused, CAPS
from core import release as release_module
from core.validation import ContractError

TARGET = 'GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe'
BARE = TARGET.removeprefix('GPU-')


class FakeCUuuid:
    def __init__(self, text=BARE, error=None, observe=None):
        self.text, self.error, self.observe, self.calls = text, error, observe, 0

    def __str__(self):
        self.calls += 1
        if self.observe:
            self.observe()
        if self.error:
            raise self.error
        return self.text


# Names intentionally match the real binding; only the injected class token counts.
FakeCUuuid.__module__ = 'torch._C'
FakeCUuuid.__qualname__ = '_CUuuid'
SpoofCUuuid = type('_CUuuid', (), {'__module__': 'torch._C', '__str__': lambda self: BARE})


class ArbitraryStringifiable:
    def __init__(self):
        self.calls = 0

    def __str__(self):
        self.calls += 1
        return BARE


class StringSubclass(str):
    pass


class CUuuidSubclass(FakeCUuuid):
    pass


def expect_rejection(fn, message=None):
    try:
        fn()
    except (Refused, ContractError) as error:
        if message:
            assert message in str(error), str(error)
        return str(error)
    raise AssertionError('Expected rejection')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--campaign', required=True)
    args = parser.parse_args()
    out, campaign = Path(args.output_dir), Path(args.campaign)
    out.mkdir(parents=True, exist_ok=False)
    rows = []

    def case(name, fn):
        try:
            detail = fn()
            rows.append(dict(name=name, status='passed', detail=detail))
        except Exception as error:
            rows.append(dict(name=name, status='failed', error_type=type(error).__name__, error=str(error)))
        print(rows[-1]['status'], name, flush=True)

    def scalar(raw, accepted, reason, calls=0, token=FakeCUuuid):
        before = []
        result = check_policy_uuid(raw, TARGET, token, before_conversion=before.append)
        assert len(before) == 1 and before[0]['conversion_calls'] == 0
        assert before[0]['raw_type_module'] == type(raw).__module__
        assert before[0]['raw_type_qualname'] == type(raw).__qualname__
        assert result['accepted'] is accepted and result['reason'] == reason, result
        assert result['conversion_calls'] == calls
        if hasattr(raw, 'calls'):
            assert raw.calls == calls
        return result

    for name, raw in [('bare', BARE), ('prefixed', TARGET), ('upper_hex', BARE.upper()),
                      ('prefixed_upper_hex', 'GPU-' + BARE.upper())]:
        case('str_' + name, lambda raw=raw: scalar(raw, True, 'accepted'))
    case('trusted_CUuuid_once', lambda: scalar(FakeCUuuid(), True, 'accepted', 1))
    case('trusted_CUuuid_prefixed_once', lambda: scalar(FakeCUuuid(TARGET), True, 'accepted', 1))
    case('trusted_CUuuid_uppercase_once', lambda: scalar(FakeCUuuid(BARE.upper()), True, 'accepted', 1))
    for name, raw in [('spoof_same_module_qualname', SpoofCUuuid()),
                      ('arbitrary_stringifiable', ArbitraryStringifiable()),
                      ('bytes', BARE.encode('ascii')), ('none', None), ('integer', 1),
                      ('str_subclass', StringSubclass(BARE)), ('CUuuid_subclass', CUuuidSubclass())]:
        case(name, lambda raw=raw: scalar(raw, False, 'unsupported_uuid_type'))
    case('trusted_class_missing', lambda: scalar(FakeCUuuid(), False, 'unsupported_uuid_type', token=None))
    case('trusted_token_not_class', lambda: scalar(FakeCUuuid(), False, 'unsupported_uuid_type', token=object()))
    case('str_allowed_without_CUuuid_token', lambda: scalar(BARE, True, 'accepted', token=None))
    case('different_valid_UUID', lambda: scalar('00000000-0000-0000-0000-000000000000', False, 'uuid_mismatch'))
    case('CUuuid_different_valid_UUID', lambda: scalar(FakeCUuuid('00000000-0000-0000-0000-000000000000'), False, 'uuid_mismatch', 1))
    malformed = {'empty': '', 'space_before': ' ' + BARE, 'space_after': BARE + ' ',
                 'newline': BARE + '\n', 'truncated': BARE[:-1], 'unhyphenated': BARE.replace('-', ''),
                 'lowercase_prefix': 'gpu-' + BARE, 'duplicate_prefix': 'GPU-' + TARGET,
                 'braces': '{' + BARE + '}', 'non_hex': BARE[:-1] + 'g',
                 'unicode_digit': '\uff11' + BARE[1:], 'unicode_hyphen': BARE.replace('-', '\u2010'),
                 'embedded_nul': BARE + '\x00'}
    for name, raw in malformed.items():
        case('malformed_' + name, lambda raw=raw: scalar(raw, False, 'malformed_uuid_text'))
    case('CUuuid_malformed', lambda: scalar(FakeCUuuid(' ' + BARE), False, 'malformed_uuid_text', 1))
    case('CUuuid_conversion_exception', lambda: scalar(FakeCUuuid(error=ValueError('synthetic conversion failure')), False, 'uuid_conversion_failed', 1))
    case('CUuuid_str_non_string_return', lambda: scalar(FakeCUuuid(text=BARE.encode()), False, 'uuid_conversion_failed', 1))

    def bound(name, raw, ok):
        dest = out/name
        dest.mkdir()
        config = json.loads((PACKAGE/'config/INTEGRATION.json').read_text())
        runtime = NativeEGL(config, dest, lambda: None)
        runtime.policy_index = 0
        runtime.mapping['selected_egl_index'] = 0
        calls = dict(select=0, properties=0, loader=0)

        def selected(index):
            assert index == 0
            calls['select'] += 1

        def properties(index):
            assert index == 0
            calls['properties'] += 1
            return SimpleNamespace(uuid=raw)

        def loader():
            assert json.loads((dest/'policy_device.json').read_text())['accepted']
            calls['loader'] += 1
            return {'synthetic': True, 'source': 'fake_loader_no_proc_read'}

        def before_str():
            row = json.loads((dest/'policy_device_type.json').read_text())
            assert row['uuid_evidence_stage'] == 'before_conversion'
            assert row['raw_type_module'] == 'torch._C' and row['raw_type_qualname'] == '_CUuuid'
            assert row['conversion_calls'] == 0 and row['torch_uuid_text'] is None
            assert not (dest/'policy_device.json').exists()

        if type(raw) is FakeCUuuid:
            raw.observe = before_str
        runtime.api = SimpleNamespace(check_loaded_cuda=loader)
        fake_torch = SimpleNamespace(_C=SimpleNamespace(_CUuuid=FakeCUuuid),
                                     cuda=SimpleNamespace(set_device=selected, get_device_properties=properties))
        error = None
        if ok:
            assert runtime.bind_policy(fake_torch) == 'cuda:0'
        else:
            error = expect_rejection(lambda: runtime.bind_policy(fake_torch), 'Torch policy UUID rejected:')
        result = json.loads((dest/'policy_device.json').read_text())
        initial = json.loads((dest/'policy_device_type.json').read_text())
        assert result['accepted'] is ok and 'torch_uuid_raw' not in result
        assert result['raw_type_module'] == initial['raw_type_module']
        assert result['raw_type_qualname'] == initial['raw_type_qualname']
        assert calls == dict(select=1, properties=1, loader=int(ok))
        assert runtime.journal.counts['policy_device_property_queries'] == 1
        assert sum(runtime.journal.counts.values()) == 2
        assert ('after_torch_device_binding' in runtime.loader) is ok
        if hasattr(raw, 'calls'):
            assert raw.calls == (1 if type(raw) is FakeCUuuid else 0)
        return dict(fake_only=True, calls=calls, evidence=str(dest), rejection=error)

    case('binding_str_success', lambda: bound('binding_str_success', BARE, True))
    case('binding_CUuuid_success', lambda: bound('binding_CUuuid_success', FakeCUuuid(), True))
    case('binding_conversion_failure_retains_type', lambda: bound('binding_conversion_failure', FakeCUuuid(error=RuntimeError('synthetic')), False))
    case('binding_identity_failure_retains_evidence', lambda: bound('binding_identity_failure', FakeCUuuid('00000000-0000-0000-0000-000000000000'), False))
    case('binding_spoof_rejected_without_str', lambda: bound('binding_spoof', SpoofCUuuid(), False))
    case('binding_arbitrary_rejected_without_str', lambda: bound('binding_arbitrary', ArbitraryStringifiable(), False))

    proposal = json.loads((PACKAGE/'proposal/PROPOSAL.json').read_text())
    proposal['_sha256'] = hashlib.sha256((PACKAGE/'proposal/PROPOSAL.json').read_bytes()).hexdigest()
    template = json.loads((PACKAGE/'proposal/RELEASE_TEMPLATE.json').read_text())
    control = json.loads((PACKAGE/'proposal/CONTROL_REQUIRED.json').read_text())
    control['campaign_id'] = proposal['campaign_id']
    future = dict(template, status='released')  # memory-only; never a released file
    host = proposal['owner_host']
    case('synthetic_V3_metadata_accepts', lambda: release_module.authorize(control, future, proposal, hostname=host))
    case('template_not_authorized', lambda: expect_rejection(lambda: release_module.authorize(control, template, proposal, hostname=host), 'Explicit release'))
    case('current_prepare_CONTROL_denied', lambda: expect_rejection(lambda: release_module.authorize(json.loads((campaign/'CONTROL.json').read_text()), future, proposal, hostname=host), 'Formal compute'))
    case('old_V2_release_denied', lambda: expect_rejection(lambda: release_module.authorize(control, json.loads((campaign/'releases/P10_A_NATIVE_PREFLIGHT_V2.json').read_text()), proposal, hostname=host), 'active explicit compute release'))
    both_old = copy.deepcopy(control)
    both_old['active_compute_task_ids'] = ['A10_PREFLIGHT_NATIVE_V2']
    both_old['allowed_task_ids'] = ['A10_PREFLIGHT_NATIVE_V2']
    old_proposal, old_release = dict(proposal, task_id='A10_PREFLIGHT_NATIVE_V2'), dict(future, task_id='A10_PREFLIGHT_NATIVE_V2')
    case('V2_task_rejected_even_consistent_synthetic_ids', lambda: expect_rejection(lambda: release_module.authorize(both_old, old_release, old_proposal, hostname=host), 'new native V3'))
    incomplete = copy.deepcopy(control)
    incomplete['per_task_compute_limits'] = {'A10_PREFLIGHT_NATIVE_V2': proposal['native_control_minimum_limits']}
    case('missing_V3_per_task_budget_denied', lambda: expect_rejection(lambda: release_module.authorize(incomplete, future, proposal, hostname=host), 'Current native V3 CONTROL budget absent'))
    case('CPU_P00_denied_before_input_hash', lambda: expect_rejection(lambda: release_module.load_authorization(campaign, campaign/'releases/P00_TORCH_UUID_ABI_CPU_REPAIR_V1.json', PACKAGE/'proposal/PROPOSAL.json'), 'Formal compute'))
    case('template_path_denied_before_input_hash', lambda: expect_rejection(lambda: release_module.load_authorization(campaign, PACKAGE/'proposal/RELEASE_TEMPLATE.json', PACKAGE/'proposal/PROPOSAL.json'), 'Only a new release'))

    def no_scope_expansion():
        old = campaign/'results/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1'
        old_proposal = json.loads((old/'proposal/PROPOSAL.json').read_text())
        fields = ['source', 'resource_caps', 'initialization_caps', 'graphics_caps', 'device',
                  'physical_inventory', 'cuda_environment', 'observation_caps', 'identity_probe_caps',
                  'native_control_minimum_limits', 'timeout_seconds', 'kill_grace_seconds',
                  'timeout_scope', 'timeout_accounting', 'process_family_scope']
        for field in fields:
            assert proposal[field] == old_proposal[field], field
        tree = ast.parse((PACKAGE/'code/core/native_egl.py').read_text())
        bind = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'bind_policy')
        attrs = [n.func.attr for n in ast.walk(bind) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        assert attrs.count('get_device_properties') == 1 and attrs.count('set_device') == 1
        assert attrs.count('check_loaded_cuda') == 1
        assert sum(CAPS.values()) == 108
        return {'unchanged_fields': fields, 'explicit_graphics_cap': 108, 'properties_call_sites': 1}

    case('targeted_static_scope_unchanged', no_scope_expansion)
    assert not FORBIDDEN.intersection(sys.modules)
    result = dict(status='passed' if all(r['status'] == 'passed' for r in rows) and not blocked else 'failed',
                  cases=len(rows), passed=sum(r['status'] == 'passed' for r in rows),
                  rows=rows, blocked_operations=blocked, heavy_imports_present=sorted(FORBIDDEN.intersection(sys.modules)),
                  real_hardware_calls=0, torch_imports=0, holder_queries=0, holder_stops=0,
                  model_bytes_hashed=0, real_entry_invocations=0, synthetic_metadata_never_released=True)
    (out/'TEST_RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
