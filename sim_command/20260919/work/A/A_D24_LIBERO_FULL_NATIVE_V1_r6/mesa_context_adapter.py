"""Use installed MuJoCo's Mesa selection for Robosuite's EGL context too."""
import importlib
import os


def install():
    if os.environ.get('VLA_RENDERER') != 'mesa' or os.environ.get('LIBGL_ALWAYS_SOFTWARE') != '1':
        raise RuntimeError('This private adapter is only for the existing Mesa software renderer')
    if 'MUJOCO_EGL_DEVICE_ID' in os.environ:
        raise RuntimeError('A forced hardware device conflicts with Mesa software selection')
    native = importlib.import_module('mujoco.egl')
    robo = importlib.import_module('robosuite.renderers.context.egl_context')

    def create_display(device_id=-1):
        # Both native APIs use the same EGL vendor/library. The installed native
        # MuJoCo selector already tries all devices and handles failed displays.
        # Robosuite's version instead parses an empty CUDA string and fixes one
        # device, which fails on A. Keep CUDA hidden from the CPU-only client.
        return native.create_initialized_egl_device_display()

    robo.create_initialized_egl_device_display = create_display
    return {'renderer': 'Mesa llvmpipe', 'selection': 'installed native MuJoCo EGL all-device fallback',
            'client_cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES'),
            'new_probe': False, 'shared_package_changed': False}
