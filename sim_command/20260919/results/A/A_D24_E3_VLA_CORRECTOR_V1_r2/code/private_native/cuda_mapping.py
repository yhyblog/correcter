"""Pure control/recording logic; runtime functions are explicitly injected.

Importing this module cannot load EGL/CUDA. CPU tests inject Python fakes.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time
from .graphics_contract import Refused

EGL_SUCCESS = 0x3000
EGL_CUDA_DEVICE_NV = 0x323A
EXPECTED_ABI = {'pointer': 8, 'EGLAttrib': 8, 'EGLint': 4, 'EGLBoolean': 4,
                'CUdevice': 4, 'CUresult': 4, 'unsigned_int': 4}


def validate_abi(actual):
    if actual != EXPECTED_ABI:
        raise Refused('Expected Linux x86_64 LP64 ABI: EGLAttrib=intptr_t, CUdevice=C int')


def validate_visibility(actual, expected):
    if any(actual.get(k) != v for k, v in expected.items()):
        raise Refused('Frozen CUDA/container visibility or ordering differs')
    visible = expected['CUDA_VISIBLE_DEVICES'].split(',')
    if len(visible) != 8 or len(set(visible)) != 8 or any(not x.startswith('GPU-') for x in visible):
        raise Refused('Exactly eight frozen physical UUID visibility entries required')


def normalize_pci(value):
    m = re.fullmatch(r'([0-9a-fA-F]{4}|[0-9a-fA-F]{8}):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])', value)
    if not m:
        raise Refused('Malformed PCI identity')
    domain, bus, device, function = [int(v, 16) for v in m.groups()]
    if domain > 0xffff or device > 0x1f:
        raise Refused('PCI value outside frozen host domain/device range')
    return f'{domain:04x}:{bus:02x}:{device:02x}.{function:x}'


def raw_value(value):
    if value is None:
        return {'kind': 'NULL', 'bytes_hex': None}
    if isinstance(value, bytes):
        return {'kind': 'empty' if value == b'' else 'bytes', 'bytes_hex': value.hex(),
                'utf8_with_replacement': value.decode('utf-8', errors='replace')}
    if isinstance(value, dict):
        return {k: raw_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [raw_value(v) for v in value]
    return value


class CallRecorder:
    """Durable raw results plus explicitly budgeted, immediate EGL error reads."""
    def __init__(self, journal, path, egl_get_error):
        self.journal = journal
        self.path = Path(path)
        self.path.open('x').close()
        self.egl_get_error = egl_get_error
        self.sequence = 0

    def record(self, operation, value, **metadata):
        self.sequence += 1
        from core.contracts import append_json
        append_json(self.path,dict(sequence=self.sequence, operation=operation,
            raw=raw_value(value),monotonic_ns=time.monotonic_ns(),**metadata))

    def call(self, key, fn, *, cleanup=False, **metadata):
        def invoke():
            value = fn()
            self.record(key, value, **metadata)
            return value
        return self.journal.call(key, invoke, cleanup=cleanup)

    def error(self, after_operation, *, cleanup=False):
        return self.call('egl_error_queries', self.egl_get_error, cleanup=cleanup,
                         after_operation=after_operation, attribution='observed current thread error; no unqueried error is inferred')

    def egl(self, key, fn, *, cleanup=False, check=None, **metadata):
        value = self.call(key, fn, cleanup=cleanup, **metadata)
        error = self.error(key, cleanup=cleanup)
        if error != EGL_SUCCESS:
            raise Refused(f'{key}: observed EGL error 0x{error:x}')
        if check is not None and not check(value):
            raise Refused(f'{key}: returned invalid result (raw preserved)')
        return value


def read_kernel_identity(pci):
    path = Path('/proc/driver/nvidia/gpus') / pci / 'information'
    data = path.read_bytes()
    fields = dict(line.split(':', 1) for line in data.decode().splitlines() if ':' in line)
    return {'pci_bus_id': normalize_pci(fields['Bus Location'].strip()),
            'gpu_uuid': fields['GPU UUID'].strip(), 'kernel_path': str(path),
            'kernel_sha256': hashlib.sha256(data).hexdigest()}


def map_devices(api, recorder, target, inventory, state, kernel_reader=read_kernel_identity):
    """One cuInit, one EGL enumeration, <=8 attributes/PCI calls; no contexts."""
    state.update(method='EGL_CUDA_DEVICE_NV handle -> cuDeviceGetPCIBusId -> kernel PCI/UUID -> frozen NVML target',
                 devices=[], selected_egl_index=None, ordinal_assumption=False, stage='cuInit')
    expected = {row['pci_bus_id']: row['gpu_uuid'] for row in inventory}
    if len(expected) != 8 or expected.get(target['pci_bus_id']) != target['gpu_uuid']:
        raise Refused('Frozen inventory/target PCI-UUID mismatch')
    try:
        rc = recorder.call('cuda_driver_initializations', lambda: api.init(0), cuda_flags=0)
        state['cuda_init_return_code'] = rc
        if rc != 0:
            raise Refused(f'cuInit returned CUresult {rc}; no retry')
        state['stage'] = 'eglQueryDevicesEXT'
        enumeration = recorder.egl('egl_device_enumerations', api.enumerate)
        state['enumeration'] = enumeration
        if enumeration['return_code'] != 1 or not 0 < enumeration['count'] <= 8:
            raise Refused('EGL enumeration failed, empty, or exceeds eight candidates')
        handles = enumeration['handles']
        if len(handles) != enumeration['count'] or any(h is None or h == 0 for h in handles) or len(set(handles)) != len(handles):
            raise Refused('Invalid or duplicate EGL handles')
        matches, seen_pci = [], set()
        for index, handle in enumerate(handles):
            row = dict(egl_index=index, egl_handle=handle, extensions_raw=None,
                       attribute=None, cuda_pci=None, mapping=None, decision='pending')
            state['devices'].append(row)
            state['stage'] = f'candidate_{index}_extension'
            ext = recorder.egl('egl_device_string_queries', lambda: api.extensions(handle), egl_index=index, token=0x3055)
            row['extensions_raw'] = raw_value(ext)
            if not isinstance(ext, bytes) or not ext:
                raise Refused('Missing device extensions; NULL and empty retained separately')
            names = ext.decode('ascii').split()
            row['extensions'] = names
            if 'EGL_NV_device_cuda' not in names:
                raise Refused('Candidate does not declare EGL_NV_device_cuda')
            state['stage'] = f'candidate_{index}_attribute'
            attr = recorder.egl('egl_device_attribute_queries', lambda: api.attribute(handle), egl_index=index, token=EGL_CUDA_DEVICE_NV)
            row['attribute'] = attr
            if attr['return_code'] != 1:
                raise Refused(f'EGL CUDA attribute failed: EGLBoolean {attr["return_code"]}')
            cuda_handle = attr['value']
            if type(cuda_handle) is not int or not 0 <= cuda_handle <= 0x7fffffff:
                raise Refused('CUDA handle cannot be represented as a valid nonnegative C int')
            state['stage'] = f'candidate_{index}_PCI'
            pci_result = recorder.call('cuda_device_pci_queries', lambda: api.pci(cuda_handle),
                                       egl_index=index, CUDA_handle_passed_unmodified=cuda_handle)
            row['cuda_pci'] = raw_value(pci_result)
            if pci_result['return_code'] != 0:
                raise Refused(f'cuDeviceGetPCIBusId returned CUresult {pci_result["return_code"]}')
            buf = pci_result['buffer']
            if not isinstance(buf, bytes) or len(buf) != 32 or b'\0' not in buf:
                raise Refused('PCI output missing NUL or expected fixed buffer')
            pci = normalize_pci(buf.split(b'\0', 1)[0].decode('ascii'))
            row['normalized_pci'] = pci
            state['stage'] = f'candidate_{index}_kernel_identity'
            kernel = kernel_reader(pci)
            row['kernel_identity'] = kernel
            if kernel['pci_bus_id'] != pci or kernel['gpu_uuid'] != expected.get(pci):
                raise Refused('CUDA PCI / kernel UUID / frozen inventory conflict')
            if pci in seen_pci:
                raise Refused('Multiple EGL candidates map to one physical PCI identity')
            seen_pci.add(pci)
            row['mapping'] = {'pci_bus_id': pci, 'gpu_uuid': kernel['gpu_uuid']}
            row['decision'] = 'target' if row['mapping'] == {k: target[k] for k in ('pci_bus_id','gpu_uuid')} else 'non_target_no_context'
            if row['decision'] == 'target':
                matches.append(index)
        if len(matches) != 1:
            raise Refused('Exactly one fixed physical target must map; no device retries')
        state.update(stage='unique_mapping_complete', selected_egl_index=matches[0])
        return handles[matches[0]], matches[0]
    except BaseException as error:
        if state['devices'] and state['devices'][-1]['decision'] == 'pending':
            state['devices'][-1]['decision'] = 'refused'
        state['failure'] = {'error_type': type(error).__name__, 'error': str(error), 'stage': state['stage']}
        raise
