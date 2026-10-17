"""Proposed single NVIDIA EGL render. No graphics imports before explicit authorization."""
import argparse
from pathlib import Path
import json
import os
import re
import sys
import traceback
from probe_contract import authorize, current, Journal, reconcile, write_new, Refused, digest
from wave_timing import held_reservation_fds


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
        display = calls.egl('egl_platform_display_calls', lambda: get_display(0x313F, target_handle, None), check=bool)
        major, minor = I(), I()
        calls.egl('egl_initialize_calls', lambda: initialize(display, ct.byref(major), ct.byref(minor)), check=bool)
        initialized = True
        configs, num_configs = (P * 1)(), I()
        attrs = (I * 17)(0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,24,0x3026,8,0x3033,1,0x3040,8,0x3038)
        calls.egl('egl_choose_config_calls', lambda: choose_config(display, attrs, configs, 1, ct.byref(num_configs)), check=bool)
        if num_configs.value != 1: raise RuntimeError('No matching EGL configuration')
        calls.egl('egl_bind_api_calls', lambda: bind_api(0x30A2), check=bool)
        context = calls.egl('graphics_context_creations', lambda: create_context(display, configs[0], None, None), check=bool)
        calls.egl('egl_make_current_calls', lambda: make_current(display, None, None, context), check=bool)
        gl_get_string = extension('glGetString', ct.c_char_p, [U])
        gl = {}
        for name, token in [('vendor',0x1F00),('renderer',0x1F01),('version',0x1F02)]:
            raw = calls.call('probe_explicit_gl_string_queries', lambda: gl_get_string(token), token=token)
            if not raw: raise Refused('GL string is NULL/empty; raw value preserved, GL error not queried')
            gl[name] = raw.decode()
        egl_strings = {}
        for name, token in [('vendor',0x3053),('version',0x3054)]:
            raw = calls.egl('egl_query_string_calls', lambda: query_string(display, token), check=bool)
            egl_strings[name] = raw.decode()
        write_new(destination / 'renderer_identity.json', dict(GL=gl, EGL=egl_strings, egl_index=index))
        if 'nvidia' not in gl['vendor'].lower() or 'nvidia' not in egl_strings['vendor'].lower():
            raise Refused('Renderer is not NVIDIA; no software fallback')
        import numpy as np
        import mujoco
        model = journal.call('static_scene_constructions', lambda: mujoco.MjModel.from_xml_path(str(root / 'scene.xml')))
        if model.nq != 0 or model.nv != 0 or model.nu != 0:
            raise Refused('Scene must contain no dynamic degrees of freedom or actuators')
        data = journal.call('static_scene_data_constructions', lambda: mujoco.MjData(model))
        time_before = float(data.time)
        journal.call('explicit_mj_forward_calls', lambda: mujoco.mj_forward(model, data))
        scene = mujoco.MjvScene(model, maxgeom=10)
        camera = mujoco.MjvCamera(); camera.type = mujoco.mjtCamera.mjCAMERA_FIXED; camera.fixedcamid = 0
        journal.call('mujoco_scene_updates', lambda: mujoco.mjv_updateScene(model, data, mujoco.MjvOption(),
            None, camera, mujoco.mjtCatBit.mjCAT_ALL, scene))
        render_context = journal.call('mujoco_render_context_creations', lambda: mujoco.MjrContext(model, mujoco.mjtFontScale.mjFONTSCALE_100))
        mujoco.mjr_setBuffer(mujoco.mjtFramebuffer.mjFB_OFFSCREEN, render_context)
        viewport = mujoco.MjrRect(0, 0, 64, 64)
        pixels = np.empty((64, 64, 3), dtype=np.uint8)
        journal.call('render_calls', lambda: mujoco.mjr_render(viewport, scene, render_context))
        journal.call('rgb_readback_calls', lambda: mujoco.mjr_readPixels(pixels, None, viewport, render_context))
        if float(data.time) != time_before or time_before != 0.0:
            raise RuntimeError('Unexpected physical time advance')
        if not pixels.any() or pixels.max() == pixels.min():
            raise RuntimeError('Readback is empty or constant')
        pixels = np.flipud(pixels).copy()
        with (destination / 'rgb.npy').open('xb') as f: np.save(f, pixels)
        with (destination / 'rgb.ppm').open('xb') as f:
            f.write(b'P6\n64 64\n255\n'); f.write(pixels.tobytes())
        result = dict(status='complete', shape=list(pixels.shape), dtype=str(pixels.dtype),
            image_sha256=digest(destination/'rgb.npy'), GL=gl, EGL=egl_strings,
            selected_egl_index=index, mapped_physical_gpu=proposal['device'],
            data_time_before=time_before, data_time_after=float(data.time),
            meaning='One static NVIDIA EGL RGB readback only; MetaWorld and VLA compatibility remain unvalidated')
    finally:
        actions = []
        if render_context is not None:
            actions.append(('mujoco_render_context_frees', lambda: render_context.free()))
        if context:
            actions.extend([('egl_make_current_calls', lambda: make_current(display, None, None, None)),
                            ('egl_destroy_context_calls', lambda: destroy_context(display, context))])
        if initialized:
            actions.append(('egl_terminate_calls', lambda: terminate(display)))
        if release_thread is not None and calls is not None:
            actions.append(('egl_release_thread_calls', lambda: release_thread()))
        for key, fn in actions:
            try:
                if key == 'mujoco_render_context_frees':
                    journal.call(key, fn, cleanup=True)
                else:
                    calls.egl(key, fn, cleanup=True, check=lambda value: value == 1)
            except BaseException as e:
                cleanup_errors.append(dict(operation=key, error_type=type(e).__name__, error=str(e)))
        write_new(destination / 'cleanup.json', dict(errors=cleanup_errors))
        write_new(destination/'device_mapping.json', mapping)
        write_new(destination/'loader_identity.json', loader)
    if cleanup_errors:
        raise RuntimeError('Graphics cleanup failed; see cleanup.json')
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('campaign','release','proposal','launch-directory'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    if Path(__file__).resolve().parent.parent != Path(args.proposal).resolve().parent.parent:
        raise Refused('Executable must belong to the proposed bundle')
    release, proposal = authorize(args.campaign, args.release, args.proposal)
    if not held_reservation_fds():
        raise Refused('Active whole-host holder reservation is required')
    root = Path(args.proposal).resolve().parent.parent
    expected = Path(args.campaign).resolve()/'results/A/EGL_graphics_runs'/release['run_id']
    if Path(args.launch_directory).resolve() != expected:
        raise Refused('Unexpected output identity')
    destination = expected/'graphics'; destination.mkdir(exist_ok=False)
    if os.environ.get('__EGL_VENDOR_LIBRARY_FILENAMES') != str(root/'isolation/vendor/10_nvidia.json'):
        raise Refused('Explicit isolated NVIDIA vendor config required')
    expected_ld = ':'.join([str(root/'isolation/lib'), proposal['python_library_directory'],
                           '/usr/lib/x86_64-linux-gnu','/lib/x86_64-linux-gnu'])
    if os.environ.get('LD_LIBRARY_PATH') != expected_ld or os.environ.get('LD_PRELOAD'):
        raise Refused('Use the frozen isolated library search path without LD_PRELOAD')
    validate_visibility(os.environ, proposal['cuda_environment'])
    journal = Journal(destination/'events.jsonl', proposal['resource_caps'],
        lambda: current(args.campaign, args.release, release, proposal))
    outcome, error = None, None
    try:
        outcome = journal.call('graphics_probe_attempts', lambda: render_once(root, destination, proposal, journal))
    except BaseException as e:
        error = dict(error_type=type(e).__name__, error=str(e), traceback=traceback.format_exc())
    counts = reconcile(journal.path)
    write_new(destination/'RESULT.json', dict(status='failed' if error else 'complete', error=error,
        outcome=outcome, resources=counts, max_retries=0, gpu_seconds=None,
        unknown_gpu_seconds_reason='No GPU event timing or utilization integral; wall time is separate'))
    return 1 if error else 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps(dict(status='denied', error_type=type(e).__name__, error=str(e)))); sys.exit(2)
