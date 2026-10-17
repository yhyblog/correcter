"""Deferred ctypes ABI from the accepted CUDA-handle graphics probe.

No import of ctypes, symbol resolution, driver load, or call at module import.
Only NativeEGL.prepare(), below release/reservation/SHA gates, calls this module.
"""
import os
from pathlib import Path
from types import SimpleNamespace
from .cuda_mapping import CallRecorder, validate_abi, EGL_SUCCESS
from .graphics_contract import Refused


def mapped_cuda_files():
    found = set()
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(None, 5)
        if len(fields) == 6 and Path(fields[5]).name.startswith('libcuda.so'):
            found.add(str(Path(fields[5]).resolve()))
    return sorted(found)


def load_bindings(runtime):
    import ctypes as ct
    root = Path(runtime.config['isolation_root'])
    journal = runtime.journal
    P, I, U, A = ct.c_void_p, ct.c_int, ct.c_uint, ct.c_ssize_t
    pI = ct.POINTER(I)
    validate_abi(dict(pointer=ct.sizeof(P), EGLAttrib=ct.sizeof(A), EGLint=ct.sizeof(I),
        EGLBoolean=ct.sizeof(U), CUdevice=ct.sizeof(I), CUresult=ct.sizeof(I), unsigned_int=ct.sizeof(U)))
    if mapped_cuda_files():
        raise Refused('CUDA library loaded before the frozen driver preload')
    expected = str((root/'isolation/lib/libcuda.so.535.161.08').resolve())
    def check_loaded_cuda():
        actual = mapped_cuda_files()
        if actual != [expected]:
            raise Refused('Loaded CUDA is not the frozen 535 driver: ' + repr(actual))
        return actual
    runtime.loader.update(stage='explicit_driver_load', CUDA_before=[], environment=runtime.config['cuda_environment'])
    cuda = journal.call('probe_explicit_driver_library_loads', lambda: ct.CDLL(expected, mode=ct.RTLD_GLOBAL | os.RTLD_NOW))
    runtime.loader['CUDA_after_first_load'] = check_loaded_cuda()
    egl = journal.call('probe_explicit_driver_library_loads', lambda: ct.CDLL(
        str(root/'isolation/lib/libEGL.so.1'), mode=ct.RTLD_GLOBAL | os.RTLD_NOW))
    runtime.loader['CUDA_after_EGL_load'] = check_loaded_cuda()

    def bind(lib, name, result, args, key):
        function = journal.call(key, lambda: getattr(lib, name))
        function.restype, function.argtypes = result, args
        return function
    def core(name, result, args):
        return bind(egl, name, result, args, 'probe_explicit_egl_core_symbol_lookups')
    cu_init = bind(cuda, 'cuInit', I, [U], 'probe_explicit_cuda_symbol_lookups')
    cu_pci = bind(cuda, 'cuDeviceGetPCIBusId', I, [ct.POINTER(ct.c_char), I, I], 'probe_explicit_cuda_symbol_lookups')
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
    runtime.calls = calls = CallRecorder(journal, runtime.destination/'graphics_api_results.jsonl', get_error)
    # Preserve the cleanup symbol before any later extension or mapping failure.
    runtime.api = api = SimpleNamespace(release_thread=lambda: release_thread(),
        check_loaded_cuda=check_loaded_cuda, library_objects=(cuda, egl))
    if calls.error('preexisting_before_first_EGL_call') != EGL_SUCCESS:
        raise Refused('Preexisting EGL error; recorded without retry')
    def extension(name, result, args):
        address = calls.egl('probe_explicit_egl_get_proc_address_calls',
            lambda: proc(name.encode()), check=bool, function=name)
        return ct.CFUNCTYPE(result, *args)(address)
    query_devices = extension('eglQueryDevicesEXT', U, [I, ct.POINTER(P), pI])
    query_device_string = extension('eglQueryDeviceStringEXT', ct.c_char_p, [P, I])
    query_attribute = extension('eglQueryDeviceAttribEXT', U, [P, I, ct.POINTER(A)])
    get_display = extension('eglGetPlatformDisplayEXT', P, [U, P, pI])
    def enumerate_devices():
        handles, count = (P * 16)(), I(-1)
        rc = int(query_devices(16, handles, ct.byref(count)))
        return dict(return_code=rc, count=count.value, handles=list(handles)[:max(0, min(count.value, 16))])
    def attribute(handle):
        value = A(-(1 << 63))
        rc = int(query_attribute(handle, 0x323A, ct.byref(value)))
        return dict(return_code=rc, value=value.value, output_defined=rc == 1, sentinel=-(1 << 63))
    def pci(handle):
        buffer = (ct.c_char * 32).from_buffer_copy(bytes([0xa5]) * 32)
        rc = int(cu_pci(buffer, 32, handle))
        return dict(return_code=rc, buffer=bytes(buffer))
    def initialize_display(display):
        major, minor = I(), I()
        return int(initialize(display, ct.byref(major), ct.byref(minor)))
    def choose(display):
        configs, count = (P * 1)(), I()
        attrs = (I * 17)(0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,24,0x3026,8,0x3033,1,0x3040,8,0x3038)
        rc = int(choose_config(display, attrs, configs, 1, ct.byref(count)))
        return dict(return_code=rc, count=count.value, config=configs[0])
    api.init = lambda flags: int(cu_init(flags))
    api.enumerate = enumerate_devices
    api.extensions = lambda handle: query_device_string(handle, 0x3055)
    api.attribute, api.pci = attribute, pci
    api.get_display = lambda handle: get_display(0x313F, handle, None)
    api.initialize, api.choose_config = initialize_display, choose
    api.bind_api = lambda: bind_api(0x30A2)
    api.create_context = lambda display, config: create_context(display, config, None, None)
    api.make_current = lambda display, context: make_current(display, None, None, context)
    api.gl_get_string = lambda: extension('glGetString', ct.c_char_p, [U])
    api.query_string = query_string
    api.destroy_context, api.terminate = destroy_context, terminate
