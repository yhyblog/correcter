"""Build only the new mapping revision; original published sources remain untouched."""
from pathlib import Path

WORK = Path(__file__).resolve().parent
OLD = WORK.parents[2] / 'results/A/A10_EGL_CPU_REPAIR_V1/code/graphics_probe.py'
old = OLD.read_text()
imports = old[:old.index('\ndef drm_identity')]
imports += '''
from cuda_mapping import (CallRecorder, map_devices, validate_visibility, validate_abi,
                          normalize_pci, EGL_SUCCESS)


def mapped_cuda_files():
    found = set()
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(None, 5)
        if len(fields) == 6 and Path(fields[5]).name.startswith('libcuda.so'):
            found.add(str(Path(fields[5]).resolve()))
    return sorted(found)


def check_loaded_cuda(root):
    expected = str((root/'isolation/lib/libcuda.so.535.161.08').resolve())
    actual = mapped_cuda_files()
    if actual != [expected]:
        raise Refused('Loaded CUDA library differs from frozen 535 stack: ' + repr(actual))
    return actual


def render_once(root, destination, proposal, journal):
    # Authorize, whole-host reservation, visibility and ABI precede all driver loading.
    import ctypes as ct
    from types import SimpleNamespace
    validate_visibility(os.environ, proposal['cuda_environment'])
    P, I, U, A = ct.c_void_p, ct.c_int, ct.c_uint, ct.c_ssize_t
    validate_abi(dict(pointer=ct.sizeof(P), EGLAttrib=ct.sizeof(A), EGLint=ct.sizeof(I),
        EGLBoolean=ct.sizeof(U), CUdevice=ct.sizeof(I), CUresult=ct.sizeof(I), unsigned_int=ct.sizeof(U)))
    if mapped_cuda_files():
        raise Refused('Unexpected CUDA library was already loaded before probe')
    pI = ct.POINTER(I)
    display = context = render_context = calls = release_thread = None
    initialized = False
    cleanup_errors = []
    result = None
    mapping = dict(stage='frozen_library_load', devices=[], selected_egl_index=None)
    loader = dict(CUDA_before=[], CUDA_after=None, environment=proposal['cuda_environment'])
    try:
        cuda = journal.call('probe_explicit_driver_library_loads', lambda: ct.CDLL(
            str(root/'isolation/lib/libcuda.so.535.161.08'), mode=ct.RTLD_GLOBAL | os.RTLD_NOW))
        loader['CUDA_after_first_load'] = check_loaded_cuda(root)
        egl = journal.call('probe_explicit_driver_library_loads', lambda: ct.CDLL(
            str(root/'isolation/lib/libEGL.so.1'), mode=ct.RTLD_GLOBAL | os.RTLD_NOW))
        loader['CUDA_after'] = check_loaded_cuda(root)

        def bind(lib, name, result_type, arguments, budget):
            f = journal.call(budget, lambda: getattr(lib, name))
            f.restype = result_type; f.argtypes = arguments
            return f

        def core(name, result_type, arguments):
            return bind(egl, name, result_type, arguments, 'probe_explicit_egl_core_symbol_lookups')

        cu_init = bind(cuda, 'cuInit', I, [U], 'probe_explicit_cuda_symbol_lookups')
        cu_pci = bind(cuda, 'cuDeviceGetPCIBusId', I, [ct.POINTER(ct.c_char), I, I],
                      'probe_explicit_cuda_symbol_lookups')
        proc = core('eglGetProcAddress', P, [ct.c_char_p])
        get_error = core('eglGetError', I, [])
        initialize = core('eglInitialize', U, [P, pI, pI])
        choose_config = core('eglChooseConfig', U, [P, pI, ct.POINTER(P), I, pI])
        bind_api = core('eglBindAPI', U, [U])
        create_context = core('eglCreateContext', P, [P, P, P, pI])
        make_current = core('eglMakeCurrent', U, [P, P, P, P])
        query_string = core('eglQueryString', ct.c_char_p, [P, I])
        destroy_context = core('eglDestroyContext', U, [P, P])
        terminate = core('eglTerminate', U, [P])
        release_thread = core('eglReleaseThread', U, [])
        calls = CallRecorder(journal, destination/'api_results.jsonl', get_error)
        if calls.error('preexisting_before_first_EGL_call') != EGL_SUCCESS:
            raise Refused('Non-success preexisting EGL error; recorded and stop')

        def extension(name, result_type, arguments):
            address = calls.egl('probe_explicit_egl_get_proc_address_calls',
                lambda: proc(name.encode()), check=bool, function=name)
            return ct.CFUNCTYPE(result_type, *arguments)(address)

        query_devices = extension('eglQueryDevicesEXT', U, [I, ct.POINTER(P), pI])
        query_device_string = extension('eglQueryDeviceStringEXT', ct.c_char_p, [P, I])
        query_attribute = extension('eglQueryDeviceAttribEXT', U, [P, I, ct.POINTER(A)])
        get_display = extension('eglGetPlatformDisplayEXT', P, [U, P, pI])

        def enumerate_devices():
            handles = (P * 16)(); count = I(-1)
            rc = int(query_devices(16, handles, ct.byref(count)))
            return dict(return_code=rc, count=count.value,
                        handles=list(handles)[:max(0, min(count.value, 16))])

        def query_cuda_attribute(handle):
            value = A(-(1 << 63))
            rc = int(query_attribute(handle, 0x323A, ct.byref(value)))
            return dict(return_code=rc, value=value.value, output_defined=(rc == 1),
                        sentinel=-(1 << 63))

        def query_pci(handle):
            buffer = (ct.c_char * 32).from_buffer_copy(bytes([0xa5]) * 32)
            rc = int(cu_pci(buffer, 32, handle))
            return dict(return_code=rc, buffer=bytes(buffer))

        api = SimpleNamespace(init=lambda flags: int(cu_init(flags)), enumerate=enumerate_devices,
            extensions=lambda handle: query_device_string(handle, 0x3055),
            attribute=query_cuda_attribute, pci=query_pci)
        target_handle, index = map_devices(api, calls, proposal['device'],
            proposal['physical_inventory'], mapping)
        loader['CUDA_after_mapping'] = check_loaded_cuda(root)
        # Exactly one display candidate after the entire mapping uniqueness check.
'''
body = old[old.index('        display = journal.call(\'egl_platform_display_calls\''):old.index('\ndef main():')]
body = body.replace('handles[index]', 'target_handle')
for key in ['egl_platform_display_calls','egl_initialize_calls','egl_choose_config_calls',
            'egl_bind_api_calls','graphics_context_creations','egl_make_current_calls','egl_query_string_calls']:
    body = body.replace("journal.call('" + key + "'", "calls.egl('" + key + "'")
body = body.replace("journal.call('probe_explicit_gl_string_queries'", "calls.call('probe_explicit_gl_string_queries'")
body = body.replace("raw = calls.call('probe_explicit_gl_string_queries', lambda: gl_get_string(token), check=bool)",
                    "raw = calls.call('probe_explicit_gl_string_queries', lambda: gl_get_string(token), token=token)\n            if not raw: raise Refused('GL string is NULL/empty; raw value preserved, GL error not queried')")
body = body.replace("actions.append(('egl_release_thread_calls', lambda: release_thread()))", "if release_thread is not None and calls is not None:\n            actions.append(('egl_release_thread_calls', lambda: release_thread()))")
body = body.replace("journal.call(key, fn, cleanup=True, check=None if key=='mujoco_render_context_frees' else bool)",
                    "if key == 'mujoco_render_context_frees':\n                    journal.call(key, fn, cleanup=True)\n                else:\n                    calls.egl(key, fn, cleanup=True, check=lambda value: value == 1)")
body = body.replace("write_new(destination / 'cleanup.json', dict(errors=cleanup_errors))",
                    "write_new(destination / 'cleanup.json', dict(errors=cleanup_errors))\n        write_new(destination/'device_mapping.json', mapping)\n        write_new(destination/'loader_identity.json', loader)")
main = old[old.index('\ndef main():'):]
main = main.replace("    journal = Journal(", "    validate_visibility(os.environ, proposal['cuda_environment'])\n    journal = Journal(")
(WORK/'code/graphics_probe.py').write_text(imports + body + main)
launch = WORK/'code/launch_graphics.py'
source = launch.read_text().replace("    actual = verify_device(proposal)",
    "    if os.environ.get('NVIDIA_VISIBLE_DEVICES') != proposal['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:\n        raise Refused('Container NVIDIA visibility changed; do not rewrite mount identity')\n    actual = verify_device(proposal)")
launch.write_text(source)
print('New staged graphics source built; original bundle unchanged')
