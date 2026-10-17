"""Targeted CPU fakes only. A Python audit hook rejects any ctypes load/symbol use."""
import copy
import json
import os
from pathlib import Path
import struct
import sys
import unittest
import uuid

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK/'code'))


def no_driver(event, args):
    if event.startswith('ctypes.'):
        raise AssertionError('CPU test attempted ctypes load/lookup: ' + event)


sys.addaudithook(no_driver)
from cuda_mapping import (map_devices, CallRecorder, normalize_pci, validate_visibility,
                          validate_abi, raw_value, EXPECTED_ABI, Refused)
from probe_contract import CAPS, Journal, reconcile

ARTIFACTS = Path(os.environ['CPU_TEST_ARTIFACT_ROOT'])
ARTIFACTS.mkdir(parents=True, exist_ok=True)


class FakeAPI:
    def __init__(self):
        self.handles = [83, 21, 48, 72, 64, 91, 36, 55]
        self.cuda_handles = [5, 7, 0, 4, 2, 6, 3, 1]
        self.pcis = [f'0000:{bus:02x}:00.0' for bus in (15,45,68,91,137,168,192,216)]
        self.pci_by_handle = dict(zip(self.cuda_handles, self.pcis))
        self.attr = dict(zip(self.handles, self.cuda_handles))
        self.init_rc = self.attr_rc = self.pci_rc = 0
        self.extension = b'EGL_NV_device_cuda EGL_EXT_device_query_name'
        self.error_code = 0x3000
        self.calls = []
        self.bad_buffer = None

    def init(self, flags):
        self.calls.append(('cuInit', flags)); return self.init_rc

    def enumerate(self):
        self.calls.append(('enumerate',)); return dict(return_code=1, count=len(self.handles), handles=self.handles)

    def extensions(self, handle):
        self.calls.append(('extensions', handle)); return self.extension

    def attribute(self, handle):
        self.calls.append(('attribute', handle))
        return dict(return_code=self.attr_rc or 1, value=self.attr[handle])

    def pci(self, handle):
        self.calls.append(('pci', handle))
        value = self.bad_buffer if self.bad_buffer is not None else self.pci_by_handle[handle].encode().ljust(32, b'\0')
        return dict(return_code=self.pci_rc, buffer=value)

    def error(self):
        self.calls.append(('error',)); return self.error_code


class MappingChecks(unittest.TestCase):
    def setUp(self):
        self.directory = ARTIFACTS / (self._testMethodName + '_' + uuid.uuid4().hex)
        self.directory.mkdir()
        self.api = FakeAPI()
        self.inventory = [dict(pci_bus_id=pci, gpu_uuid=f'GPU-fixture-{i}') for i,pci in enumerate(self.api.pcis)]
        self.target = self.inventory[2].copy()
        self.kernel = {r['pci_bus_id']: r.copy() for r in self.inventory}
        self.state = {}
        self.journal = Journal(self.directory/'events.jsonl', CAPS)
        self.recorder = CallRecorder(self.journal, self.directory/'raw.jsonl', self.api.error)

    def run_map(self):
        try:
            return map_devices(self.api, self.recorder, self.target, self.inventory, self.state, self.kernel.__getitem__)
        finally:
            (self.directory/'mapping.json').write_text(json.dumps(self.state, indent=2)+'\n')

    def reject(self, fragment):
        with self.assertRaisesRegex(Refused, fragment): self.run_map()
        self.assertIsNone(self.state['selected_egl_index'])

    def test_unique_permuted_egl_cuda_handles_zero_valid(self):
        self.assertEqual(self.run_map(), (48, 2))
        passed = [r[1] for r in self.api.calls if r[0] == 'pci']
        self.assertEqual(passed, [5,7,0,4,2,6,3,1])
        self.assertFalse(self.state['ordinal_assumption'])
        used = reconcile(self.journal.path)['entered_budget_usage']
        self.assertEqual([used[k] for k in ('cuda_driver_initializations','egl_device_enumerations','egl_device_string_queries','egl_device_attribute_queries','cuda_device_pci_queries')], [1,1,8,8,8])
        self.assertEqual(used['graphics_context_creations'], 0)

    def test_zero_target_match(self):
        self.api.handles.remove(48); self.reject('Exactly one fixed')

    def test_duplicate_physical_match(self):
        self.api.pci_by_handle[4] = self.target['pci_bus_id']; self.reject('Multiple EGL')

    def test_cuda_init_failure_stops_before_enumeration(self):
        self.api.init_rc = 100; self.reject('CUresult 100')
        self.assertEqual(self.api.calls, [('cuInit',0)])

    def test_cuda_pci_failure_raw_buffer_kept(self):
        self.api.pci_rc = 101; self.reject('CUresult 101')
        self.assertEqual(self.state['devices'][0]['cuda_pci']['return_code'], 101)

    def test_egl_attribute_failure_code_kept(self):
        self.api.attr_rc = 2; self.reject('EGLBoolean 2')
        self.assertEqual(self.state['devices'][0]['attribute']['return_code'],2)

    def test_egl_attribute_false_return_kept(self):
        self.api.attribute = lambda handle: dict(return_code=0,value=-(1<<63))
        self.reject('EGLBoolean 0')
        self.assertEqual(self.state['devices'][0]['attribute']['value'], -(1<<63))

    def test_handle_overflow_not_truncated(self):
        self.api.attr[83] = 1<<32; self.reject('C int')
        self.assertFalse(any(row[0]=='pci' for row in self.api.calls))

    def test_negative_handle_rejected(self):
        self.api.attr[83] = -1; self.reject('C int')

    def test_kernel_uuid_conflict(self):
        self.kernel[self.api.pcis[0]]['gpu_uuid'] = 'GPU-wrong'; self.reject('kernel UUID')

    def test_kernel_pci_conflict(self):
        self.kernel[self.api.pcis[0]]['pci_bus_id'] = self.api.pcis[1]; self.reject('kernel UUID')

    def test_frozen_target_conflict_before_driver_call(self):
        self.target['gpu_uuid'] = 'GPU-wrong'; self.reject('inventory/target')
        self.assertEqual(self.api.calls, [])

    def test_unknown_pci_fails_before_context(self):
        self.api.pci_by_handle[5] = '0000:fe:00.0'
        self.kernel['0000:fe:00.0'] = {'pci_bus_id':'0000:fe:00.0','gpu_uuid':'GPU-unknown'}
        self.reject('kernel UUID')

    def test_pci_eight_digit_zero_domain_normalization(self):
        self.api.pci_by_handle[0] = '00000000:44:00.0'; self.assertEqual(self.run_map()[1],2)

    def test_pci_not_terminated(self):
        self.api.bad_buffer = b'a'*32; self.reject('NUL')

    def test_pci_empty(self):
        self.api.bad_buffer = bytes(32); self.reject('Malformed PCI')

    def test_null_extensions_recorded(self):
        self.api.extension = None; self.reject('NULL and empty')
        self.assertEqual(self.state['devices'][0]['extensions_raw']['kind'],'NULL')

    def test_empty_extensions_recorded(self):
        self.api.extension = b''; self.reject('NULL and empty')
        self.assertEqual(self.state['devices'][0]['extensions_raw']['kind'],'empty')

    def test_extension_missing(self):
        self.api.extension = b'EGL_EXT_device_persistent_id'; self.reject('does not declare')
        self.assertFalse(any(row[0]=='attribute' for row in self.api.calls))

    def test_egl_error_recorded_immediately_and_stops(self):
        self.api.error_code=0x3008; self.reject('0x3008')
        rows=[json.loads(l) for l in self.recorder.path.read_text().splitlines()]
        self.assertEqual(rows[-1]['operation'],'egl_error_queries')
        self.assertEqual(rows[-1]['raw'],0x3008)
        self.assertEqual(rows[-1]['after_operation'],'egl_device_enumerations')

    def test_more_than_eight_devices_stops_before_strings(self):
        self.api.handles.append(999); self.reject('exceeds eight')
        self.assertFalse(any(row[0]=='extensions' for row in self.api.calls))

    def test_duplicate_egl_handle(self):
        self.api.handles[-1] = self.api.handles[0]; self.reject('duplicate EGL')

    def test_attribute_budget_stops_before_ninth_or_excess_call(self):
        self.journal.caps['egl_device_attribute_queries']=7
        with self.assertRaises(Refused): self.run_map()
        self.assertEqual(sum(x[0]=='attribute' for x in self.api.calls),7)

    def test_raw_null_empty_and_integer_zero_differ(self):
        self.assertNotEqual(raw_value(None),raw_value(b'')); self.assertEqual(raw_value(0),0)

    def test_visibility_rejects_target_only_mask(self):
        expected=json.loads((WORK/'VISIBILITY_AND_IDENTITY.json').read_text())['environment']
        changed={**expected,'CUDA_VISIBLE_DEVICES':expected['CUDA_VISIBLE_DEVICES'].split(',')[0]}
        with self.assertRaises(Refused): validate_visibility(changed,expected)

    def test_visibility_rejects_reordering(self):
        expected=json.loads((WORK/'VISIBILITY_AND_IDENTITY.json').read_text())['environment']
        with self.assertRaises(Refused): validate_visibility({**expected,'CUDA_DEVICE_ORDER':'FASTEST_FIRST'},expected)

    def test_cpu_native_abi_widths(self):
        validate_abi(dict(pointer=struct.calcsize('P'),EGLAttrib=struct.calcsize('n'),EGLint=struct.calcsize('i'),
                         EGLBoolean=struct.calcsize('I'),CUdevice=struct.calcsize('i'),CUresult=struct.calcsize('i'),unsigned_int=struct.calcsize('I')))

    def test_abi_rejects_32bit_egl_attrib(self):
        with self.assertRaises(Refused):validate_abi({**EXPECTED_ABI,'EGLAttrib':4})

    def test_abi_rejects_64bit_cudevice(self):
        with self.assertRaises(Refused):validate_abi({**EXPECTED_ABI,'CUdevice':8})

    def test_pci_rejects_truncation_of_high_domain(self):
        with self.assertRaises(Refused):normalize_pci('01000000:0f:00.0')

    def test_full_path_egl_error_cap_and_cleanup(self):
        egl_keys=['probe_explicit_egl_get_proc_address_calls','egl_device_enumerations','egl_device_string_queries',
                  'egl_device_attribute_queries','egl_platform_display_calls','egl_initialize_calls',
                  'egl_choose_config_calls','egl_bind_api_calls','graphics_context_creations',
                  'egl_make_current_calls','egl_query_string_calls','egl_destroy_context_calls',
                  'egl_terminate_calls','egl_release_thread_calls']
        self.assertEqual(1+sum(CAPS[k] for k in egl_keys),35)
        self.recorder.error('preexisting')
        for key in egl_keys:
            for _ in range(CAPS[key]):
                self.recorder.egl(key, lambda: 1, cleanup=key in ('egl_destroy_context_calls','egl_terminate_calls','egl_release_thread_calls'))
        self.assertEqual(self.journal.counts['egl_error_queries'],35)
        before=len(self.api.calls)
        with self.assertRaises(Refused):self.recorder.error('not_authorized_extra')
        self.assertEqual(len(self.api.calls),before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
