"""Private native EGL integration; importing this module performs only CPU work.

The released child prepares mapping before torch/MuJoCo imports. A private
``mujoco.egl`` module hands the selected EGL handle to Gymnasium's existing
OffScreenViewer. No shared package files or alternative renderers are changed.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType

from .cuda_mapping import map_devices, validate_visibility, EGL_SUCCESS
from .graphics_contract import Journal, CAPS, Refused, reconcile


def write_new(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')
        stream.flush(); os.fsync(stream.fileno())


def policy_ordinal(config, mapping):
    """Bind policy by UUID visibility; EGL enumeration index is irrelevant."""
    visible = config['cuda_environment']['CUDA_VISIBLE_DEVICES'].split(',')
    target = config['device']
    observed = {row['mapping']['gpu_uuid']: row['mapping']['pci_bus_id'] for row in mapping['devices'] if row.get('mapping')}
    expected = {row['gpu_uuid']: row['pci_bus_id'] for row in config['physical_inventory']}
    if len(mapping['devices']) != 8 or observed != expected:
        raise Refused('Native mapping must cover the complete frozen eight-device inventory')
    matches = [r for r in mapping['devices'] if r['decision'] == 'target']
    if len(matches) != 1 or matches[0]['mapping'] != {k: target[k] for k in ('pci_bus_id', 'gpu_uuid')}:
        raise Refused('Policy has no unique verified physical EGL mapping')
    if visible.count(target['gpu_uuid']) != 1:
        raise Refused('Policy UUID is not uniquely visible')
    return visible.index(target['gpu_uuid'])


def check_policy_uuid(raw, expected, cuuuid_type, *, before_conversion=None):
    """Return evidence; the caller persists it before enforcing the decision.

    cuuuid_type is the class token from the already imported torch._C._CUuuid.
    CPU tests inject a controlled class; names and arbitrary __str__ methods
    never grant support. No device query, byte decoding or endian inference.
    """
    raw_type = type(raw)
    trusted_class_available = isinstance(cuuuid_type, type)
    if raw_type is str:
        branch = 'native_str'
    elif trusted_class_available and raw_type is cuuuid_type:
        branch = 'torch_C_CUuuid_identity'
    else:
        branch = 'unsupported'
    evidence = dict(
        raw_type_module=raw_type.__module__, raw_type_qualname=raw_type.__qualname__,
        supported_type_branch=branch, trusted_class_available=trusted_class_available,
        trusted_class_module=cuuuid_type.__module__ if trusted_class_available else None,
        trusted_class_qualname=cuuuid_type.__qualname__ if trusted_class_available else None,
        trusted_class_identity_match=trusted_class_available and raw_type is cuuuid_type,
        torch_uuid_text=None, expected_uuid=expected, normalized_uuid=None,
        conversion_calls=0, conversion_status='not_entered', conversion_error=None,
        format_valid=None, expected_format_valid=None, target_matches=None,
        accepted=False, reason='not_evaluated')
    if before_conversion is not None:
        before_conversion(dict(evidence))
    if branch == 'unsupported':
        evidence.update(conversion_status='rejected_without_conversion', reason='unsupported_uuid_type')
        return evidence
    if branch == 'native_str':
        evidence.update(torch_uuid_text=raw, conversion_status='not_needed_native_str')
    else:
        evidence['conversion_calls'] = 1
        try:
            evidence['torch_uuid_text'] = str(raw)  # exactly once, only trusted type
        except Exception as error:
            evidence.update(conversion_status='raised', reason='uuid_conversion_failed',
                conversion_error=dict(module=type(error).__module__,
                    qualname=type(error).__qualname__, message=str(error)))
            return evidence
        evidence['conversion_status'] = 'returned'
    pattern = r'(?:GPU-)?[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
    text = evidence['torch_uuid_text']
    evidence['format_valid'] = type(text) is str and re.fullmatch(pattern, text, re.ASCII) is not None
    evidence['expected_format_valid'] = type(expected) is str and re.fullmatch(pattern, expected, re.ASCII) is not None
    if not evidence['format_valid'] or not evidence['expected_format_valid']:
        evidence['reason'] = 'malformed_uuid_text' if not evidence['format_valid'] else 'malformed_expected_uuid'
        return evidence
    actual = 'GPU-' + text.removeprefix('GPU-').lower()
    target = 'GPU-' + expected.removeprefix('GPU-').lower()
    evidence.update(normalized_uuid=actual, target_matches=actual == target,
                    accepted=actual == target, reason='accepted' if actual == target else 'uuid_mismatch')
    return evidence


def check_environment(config, environ=None, modules=None):
    environ = os.environ if environ is None else environ
    modules = sys.modules if modules is None else modules
    validate_visibility(environ, config['cuda_environment'])
    root = Path(config['isolation_root'])
    expected_ld = ':'.join([str(root/'isolation/lib'), config['python_library_directory'],
                            '/usr/lib/x86_64-linux-gnu', '/lib/x86_64-linux-gnu'])
    required = {'LD_LIBRARY_PATH': expected_ld, 'MUJOCO_GL': 'egl', 'PYOPENGL_PLATFORM': 'egl',
                '__EGL_VENDOR_LIBRARY_FILENAMES': str(root/'isolation/vendor/10_nvidia.json')}
    if any(environ.get(k) != v for k, v in required.items()):
        raise Refused('Isolated search/vendor/renderer configuration differs')
    if any(environ.get(k) for k in ('LD_PRELOAD', '__EGL_VENDOR_LIBRARY_DIRS', 'MUJOCO_EGL_DEVICE_ID')):
        raise Refused('Alternate library injection or ordinal EGL selector forbidden')
    if any(k.split('.')[0] in ('torch', 'mujoco', 'metaworld', 'gymnasium', 'OpenGL') for k in modules):
        raise Refused('Mapping and EGL shim must precede heavy imports')


class NativeEGL:
    def __init__(self, config, destination, gate):
        if config['graphics_caps'] != CAPS:
            raise Refused('Graphics caps changed')
        self.config, self.destination = config, Path(destination)
        self.journal = Journal(self.destination/'graphics_events.jsonl', CAPS, gate)
        self.mapping = dict(stage='not_entered', devices=[], selected_egl_index=None)
        self.loader = dict(stage='not_entered')
        self.api = self.calls = self.selected_handle = None
        self.display = self.context = None
        self.initialized = self.closed = self.opened = False
        self.render_contexts, self.patches, self.cleanup_errors = [], [], []
        self.phase = None
        self.shim = None
        self.policy_index = None

    def prepare(self):
        check_environment(self.config)
        from .native_egl_bindings import load_bindings
        # load_bindings stores partial API/recorder state on self for cleanup.
        load_bindings(self)
        self.selected_handle, _ = map_devices(self.api, self.calls, self.config['device'],
            self.config['physical_inventory'], self.mapping)
        self.policy_index = policy_ordinal(self.config, self.mapping)
        self.loader['after_mapping'] = self.api.check_loaded_cuda()
        self.install_shim()

    def install_shim(self, modules=None):
        modules = sys.modules if modules is None else modules
        if any(k == 'mujoco' or k.startswith('mujoco.') for k in modules):
            raise Refused('MuJoCo was imported before private GLContext injection')
        runtime = self

        class GLContext:
            def __init__(self, max_width, max_height):
                runtime.open_context(max_width, max_height)

            def make_current(self):
                runtime.make_current()

            def free(self):
                runtime.close()

            # No destructor driver calls: the explicit runtime owns cleanup.

        shim = ModuleType('mujoco.egl')
        shim.__file__ = __file__
        shim.GLContext = GLContext
        modules['mujoco.egl'] = shim
        self.shim = shim

    def bind_policy(self, torch):
        index = self.policy_index
        self.journal.call('policy_device_selections', lambda: torch.cuda.set_device(index))
        properties = self.journal.call('policy_device_property_queries', lambda: torch.cuda.get_device_properties(index))
        raw = properties.uuid
        identity = dict(logical_index=index,
            device=f'cuda:{index}', physical_target=self.config['device'],
            EGL_index=self.mapping['selected_egl_index'],
            binding='UUID position in frozen CUDA visibility, independently checked by Torch UUID')
        cuuuid_type = getattr(getattr(torch, '_C', None), '_CUuuid', None)
        evidence = check_policy_uuid(raw, self.config['device']['gpu_uuid'], cuuuid_type,
            before_conversion=lambda record: write_new(self.destination/'policy_device_type.json',
                dict(identity, uuid_evidence_stage='before_conversion', **record)))
        write_new(self.destination/'policy_device.json',
            dict(identity, uuid_evidence_stage='decision_recorded', **evidence))
        if not evidence['accepted']:
            raise Refused('Torch policy UUID rejected: ' + evidence['reason'])
        self.loader['after_torch_device_binding'] = self.api.check_loaded_cuda()
        return f'cuda:{index}'

    def open_context(self, width, height):
        if self.opened or self.closed or (width, height) != (480, 480) or self.selected_handle is None:
            raise Refused('Exactly one mapped native 480x480 GLContext is allowed')
        self.opened = True  # An unsuccessful constructor cannot be retried.
        c, a = self.calls, self.api
        # Save successful allocations before the subsequent EGL error query.
        def display():
            self.display = a.get_display(self.selected_handle)
            return self.display
        c.egl('egl_platform_display_calls', display, check=bool)
        def initialize():
            value = a.initialize(self.display)
            self.initialized = bool(value)
            return value
        c.egl('egl_initialize_calls', initialize, check=bool)
        result = c.egl('egl_choose_config_calls', lambda: a.choose_config(self.display),
                       check=lambda r: r['return_code'] == 1 and r['count'] == 1 and bool(r['config']))
        c.egl('egl_bind_api_calls', a.bind_api, check=bool)
        def context():
            self.context = a.create_context(self.display, result['config'])
            return self.context
        c.egl('graphics_context_creations', context, check=bool)

    def make_current(self):
        if not self.context or self.closed:
            raise Refused('No live private native context')
        self.calls.egl('egl_make_current_calls', lambda: self.api.make_current(self.display, self.context), check=bool)
        gl_get_string = self.api.gl_get_string()
        gl, egl = {}, {}
        for name, token in [('vendor', 0x1F00), ('renderer', 0x1F01), ('version', 0x1F02)]:
            raw = self.calls.call('probe_explicit_gl_string_queries', lambda: gl_get_string(token), token=token)
            if not raw: raise Refused('GL string NULL/empty; raw recorded')
            gl[name] = raw.decode()
        for name, token in [('vendor', 0x3053), ('version', 0x3054)]:
            raw = self.calls.egl('egl_query_string_calls', lambda: self.api.query_string(self.display, token), check=bool)
            egl[name] = raw.decode()
        write_new(self.destination/'renderer_identity.json', dict(GL=gl, EGL=egl,
            physical_device=self.config['device'], egl_index=self.mapping['selected_egl_index']))
        if 'nvidia' not in gl['vendor'].lower() or 'nvidia' not in egl['vendor'].lower():
            raise Refused('Only NVIDIA EGL is permitted')

    @contextmanager
    def observation_scope(self, phase):
        if phase not in self.config['observation_phases'] or self.phase is not None:
            raise Refused('Invalid observation phase')
        self.phase = self.journal.observation_phase = phase
        try:
            yield
        finally:
            self.phase = self.journal.observation_phase = None

    def install_native_hooks(self, mujoco, rendering):
        if sys.modules.get('mujoco.egl') is not self.shim or rendering._ALL_RENDERERS.get('egl').__name__ != '_import_egl':
            raise Refused('Native EGL import route differs')
        runtime = self

        def patch(owner, name, replacement):
            self.patches.append((owner, name, getattr(owner, name)))
            setattr(owner, name, replacement)

        original_context = mujoco.MjrContext
        def context(*args, **kwargs):
            def create():
                result = original_context(*args, **kwargs)
                runtime.render_contexts.append(result)
                return result
            return runtime.journal.call('mujoco_render_context_creations', create)
        patch(mujoco, 'MjrContext', context)
        for name, key in [('mjv_updateScene', 'mujoco_scene_updates'), ('mjr_setBuffer', 'mujoco_set_buffer_calls'),
                          ('mjr_render', 'render_calls'), ('mjr_readPixels', 'rgb_readback_calls')]:
            original = getattr(mujoco, name)
            def hook(*args, _original=original, _key=key, **kwargs):
                if runtime.phase not in runtime.config['observation_phases']:
                    raise Refused('Native render outside a frozen control-observation phase')
                return runtime.journal.call(_key, lambda: _original(*args, **kwargs))
            patch(mujoco, name, hook)
        original_init = rendering.OffScreenViewer.__init__
        def viewer_init(viewer, *args, **kwargs):
            return runtime.journal.call('offscreen_viewer_creations', lambda: original_init(viewer, *args, **kwargs))
        patch(rendering.OffScreenViewer, '__init__', viewer_init)
        # Existing Gymnasium free() only frees GLContext. Free the MjrContext
        # first and omit its unrelated GLFW terminate call on the EGL route.
        def close_viewer(viewer):
            runtime.close()
        patch(rendering.OffScreenViewer, 'free', close_viewer)
        patch(rendering.OffScreenViewer, 'close', close_viewer)

    def close(self):
        if self.closed:
            return
        self.closed = True
        actions = [('mujoco_render_context_frees', con.free) for con in self.render_contexts]
        if self.context:
            actions += [('egl_make_current_calls', lambda: self.api.make_current(self.display, None)),
                        ('egl_destroy_context_calls', lambda: self.api.destroy_context(self.display, self.context))]
        if self.initialized:
            actions.append(('egl_terminate_calls', lambda: self.api.terminate(self.display)))
        if self.calls is not None and self.api is not None and getattr(self.api, 'release_thread', None):
            actions.append(('egl_release_thread_calls', self.api.release_thread))
        for key, fn in actions:
            try:
                if key == 'mujoco_render_context_frees':
                    self.journal.call(key, fn, cleanup=True)
                else:
                    self.calls.egl(key, fn, cleanup=True, check=lambda x: x == 1)
            except BaseException as error:
                self.cleanup_errors.append(dict(operation=key, error_type=type(error).__name__, error=str(error)))
        # Explicit cleanup is one-shot even if a call fails. No hidden retry on __del__.

    def finish(self):
        self.close()
        # Keep idempotent viewer cleanup installed until interpreter teardown;
        # restoring Gymnasium's free() would let destructors re-enter EGL/GLFW.
        write_new(self.destination/'graphics_cleanup.json', dict(errors=self.cleanup_errors,
            explicit_cleanup_once=True, shared_files_modified=False))
        write_new(self.destination/'device_mapping.json', self.mapping)
        write_new(self.destination/'loader_identity.json', self.loader)
        receipt = reconcile(self.journal.path)
        write_new(self.destination/'graphics_receipt.json', receipt)
        if self.cleanup_errors:
            raise Refused('Native graphics cleanup failed; see graphics_cleanup.json')
        return receipt
