"""Private entered/returned graphics ledger. CPU import has no foreign-library side effects."""
from pathlib import Path
import json, os, time, uuid
from core.contracts import ContractError
Refused = ContractError
CAPS = {'egl_device_enumerations': 1, 'egl_device_string_queries': 8, 'probe_explicit_egl_get_proc_address_calls': 5, 'egl_device_attribute_queries': 8, 'cuda_driver_initializations': 1, 'cuda_device_pci_queries': 8, 'egl_error_queries': 35, 'probe_explicit_driver_library_loads': 2, 'probe_explicit_cuda_symbol_lookups': 2, 'probe_explicit_egl_core_symbol_lookups': 11, 'cuda_device_count_queries': 0, 'cuda_uuid_queries': 0, 'cuda_error_string_queries': 0, 'egl_device_binary_queries': 0, 'egl_drm_string_queries': 0, 'egl_platform_display_calls': 1, 'egl_initialize_calls': 1, 'egl_choose_config_calls': 1, 'egl_bind_api_calls': 1, 'graphics_context_creations': 1, 'egl_make_current_calls': 2, 'egl_query_string_calls': 2, 'probe_explicit_gl_string_queries': 3, 'static_scene_constructions': 0, 'static_scene_data_constructions': 0, 'explicit_mj_forward_calls': 0, 'mujoco_render_context_creations': 1, 'mujoco_render_context_frees': 1, 'mujoco_scene_updates': 301, 'render_calls': 301, 'rgb_readback_calls': 301, 'egl_destroy_context_calls': 1, 'egl_terminate_calls': 1, 'egl_release_thread_calls': 1, 'mujoco_set_buffer_calls': 1, 'offscreen_viewer_creations': 1, 'policy_device_selections': 1, 'policy_device_property_queries': 1}

class Journal:
    def __init__(self, path, caps, gate=lambda: None):
        self.path = Path(path)
        self.path.open('x').close()
        self.caps = dict(caps); self.gate = gate
        self.counts = dict.fromkeys(caps, 0)

    def append(self,row):
        from core.contracts import append_json
        row={**row,'native_observation_phase':getattr(self,'observation_phase',None)}
        append_json(self.path,row)

    def call(self, key, fn, *, check=None, cleanup=False):
        if not cleanup:
            self.gate()
        if self.counts.get(key, 0) >= self.caps.get(key, 0):
            raise Refused('Operation cap exceeded before entry: ' + key)
        identity = dict(event_id=str(uuid.uuid4()), operation=key, resource_units={key: 1})
        self.append(dict(identity, phase='entered', monotonic_ns=time.monotonic_ns()))
        self.counts[key] += 1
        try:
            value = fn()
            if check is not None and not check(value):
                raise RuntimeError('Operation returned an invalid result: ' + key)
        except BaseException as e:
            self.append(dict(identity, phase='failed', error_type=type(e).__name__, error=str(e), monotonic_ns=time.monotonic_ns()))
            raise
        self.append(dict(identity, phase='returned', monotonic_ns=time.monotonic_ns()))
        return value


def reconcile(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    entered, terminal = {}, {}
    for row in rows:
        eid = row['event_id']
        if row['phase'] == 'entered':
            if eid in entered: raise Refused('Duplicate entry')
            entered[eid] = row
        else:
            if eid not in entered or eid in terminal or row['operation'] != entered[eid]['operation']:
                raise Refused('Invalid terminal identity')
            terminal[eid] = row
    counts = dict.fromkeys(CAPS, 0)
    for row in entered.values(): counts[row['operation']] += 1
    return dict(entered_budget_usage=counts, returned=sum(r['phase']=='returned' for r in terminal.values()),
        failed=sum(r['phase']=='failed' for r in terminal.values()), incomplete=len(entered)-len(terminal),
        missing_terminal_billing='Entered is charged once; terminal rows add zero; no refunds/retries')
