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


def drm_identity(node, sysroot=Path('/sys/class/drm'), procroot=Path('/proc/driver/nvidia/gpus')):
    """EGL DRM path -> sysfs PCI device -> NVIDIA kernel UUID; never a CUDA ordinal."""
    p = Path(node)
    if p.parent != Path('/dev/dri') or not re.fullmatch(r'(card\d+|renderD\d+)', p.name):
        raise Refused('Unexpected EGL DRM node path')
    device = (sysroot / p.name / 'device').resolve(strict=True)
    pci = device.name.lower()
    if not re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', pci):
        raise Refused('No unambiguous PCI mapping for EGL DRM node')
    info = procroot / pci / 'information'
    fields = dict(line.split(':', 1) for line in info.read_text().splitlines() if ':' in line)
    uuid = fields['GPU UUID'].strip()
    if fields['Bus Location'].strip().lower() != pci:
        raise Refused('Kernel PCI identity differs')
    return dict(drm_node=node, drm_node_present=p.exists(), sysfs_device=str(device),
                pci_bus_id=pci, gpu_uuid=uuid, kernel_identity_path=str(info), kernel_identity_sha256=digest(info))


def choose_target(rows, device):
    matches = [r for r in rows if (r.get('mapping') or {}).get('gpu_uuid') == device['gpu_uuid']
               and r['mapping']['pci_bus_id'] == device['pci_bus_id'].lower()]
    if len(matches) != 1:
        raise Refused('EGL physical target is absent, unknown, or ambiguous; no device retries')
    return matches[0]['egl_index']


def render_once(root, destination, proposal, journal):
    # The only graphics process enters here, after release, input and reservation checks.
    import ctypes as ct
    egl = ct.CDLL(str(root / 'isolation/lib/libEGL.so.1'), mode=ct.RTLD_GLOBAL)
    P, I, U = ct.c_void_p, ct.c_int, ct.c_uint
    pI = ct.POINTER(I)
    def core(name, result, arguments):
        f = getattr(egl, name); f.restype = result; f.argtypes = arguments; return f
    proc = core('eglGetProcAddress', P, [ct.c_char_p])
    def extension(name, result, arguments):
        address = journal.call('probe_explicit_egl_get_proc_address_calls', lambda: proc(name.encode()), check=bool)
        return ct.CFUNCTYPE(result, *arguments)(address)
    query_devices = extension('eglQueryDevicesEXT', U, [I, ct.POINTER(P), pI])
    query_device_string = extension('eglQueryDeviceStringEXT', ct.c_char_p, [P, I])
    get_display = extension('eglGetPlatformDisplayEXT', P, [U, P, pI])
    initialize = core('eglInitialize', U, [P, pI, pI])
    choose_config = core('eglChooseConfig', U, [P, pI, ct.POINTER(P), I, pI])
    bind_api = core('eglBindAPI', U, [U])
    create_context = core('eglCreateContext', P, [P, P, P, pI])
    make_current = core('eglMakeCurrent', U, [P, P, P, P])
    query_string = core('eglQueryString', ct.c_char_p, [P, I])
    destroy_context = core('eglDestroyContext', U, [P, P])
    terminate = core('eglTerminate', U, [P])
    release_thread = core('eglReleaseThread', U, [])
    handles = (P * 16)(); count = I()
    display = context = render_context = None
    initialized = False
    cleanup_errors = []
    result = None
    try:
        journal.call('egl_device_enumerations', lambda: query_devices(16, handles, ct.byref(count)), check=bool)
        if not 0 < count.value < 16:
            raise Refused('Empty or potentially truncated EGL device list')
        mappings = []
        for index in range(count.value):
            handle = handles[index]
            ext = journal.call('egl_device_string_queries', lambda: query_device_string(handle, 0x3055))
            names = ext.decode().split() if ext else []
            row = dict(egl_index=index, extensions=names, mapping=None, mapping_errors=[])
            tokens = []
            if 'EGL_EXT_device_drm_render_node' in names: tokens.append(0x3377)
            if 'EGL_EXT_device_drm' in names: tokens.append(0x3233)
            mapped = []
            for token in tokens:
                raw = journal.call('egl_device_string_queries', lambda: query_device_string(handle, token))
                if raw:
                    try:
                        mapped.append(drm_identity(raw.decode()))
                    except (OSError, ValueError, KeyError) as e:
                        row['mapping_errors'].append(str(e))
            identities = {(r['gpu_uuid'], r['pci_bus_id']) for r in mapped}
            if len(identities) == 1:
                row['mapping'] = mapped[0]
            elif len(identities) > 1:
                row['mapping_errors'].append('DRM node identities disagree')
            row['mapping_evidence'] = mapped
            mappings.append(row)
        write_new(destination / 'device_mapping.json', dict(devices=mappings, target=proposal['device'],
            method='EGL DRM device string -> /sys/class/drm PCI link -> /proc/driver/nvidia/gpus UUID',
            CUDA_ordinal_used=False))
        index = choose_target(mappings, proposal['device'])
        # Exactly one display candidate. No initialize-on-every-GPU loop.
        display = journal.call('egl_platform_display_calls', lambda: get_display(0x313F, handles[index], None), check=bool)
        major, minor = I(), I()
        journal.call('egl_initialize_calls', lambda: initialize(display, ct.byref(major), ct.byref(minor)), check=bool)
        initialized = True
        configs, num_configs = (P * 1)(), I()
        attrs = (I * 17)(0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,24,0x3026,8,0x3033,1,0x3040,8,0x3038)
        journal.call('egl_choose_config_calls', lambda: choose_config(display, attrs, configs, 1, ct.byref(num_configs)), check=bool)
        if num_configs.value != 1: raise RuntimeError('No matching EGL configuration')
        journal.call('egl_bind_api_calls', lambda: bind_api(0x30A2), check=bool)
        context = journal.call('graphics_context_creations', lambda: create_context(display, configs[0], None, None), check=bool)
        journal.call('egl_make_current_calls', lambda: make_current(display, None, None, context), check=bool)
        gl_get_string = extension('glGetString', ct.c_char_p, [U])
        gl = {}
        for name, token in [('vendor',0x1F00),('renderer',0x1F01),('version',0x1F02)]:
            raw = journal.call('probe_explicit_gl_string_queries', lambda: gl_get_string(token), check=bool)
            gl[name] = raw.decode()
        egl_strings = {}
        for name, token in [('vendor',0x3053),('version',0x3054)]:
            raw = journal.call('egl_query_string_calls', lambda: query_string(display, token), check=bool)
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
        actions.append(('egl_release_thread_calls', lambda: release_thread()))
        for key, fn in actions:
            try:
                journal.call(key, fn, cleanup=True, check=None if key=='mujoco_render_context_frees' else bool)
            except BaseException as e:
                cleanup_errors.append(dict(operation=key, error_type=type(e).__name__, error=str(e)))
        write_new(destination / 'cleanup.json', dict(errors=cleanup_errors))
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
