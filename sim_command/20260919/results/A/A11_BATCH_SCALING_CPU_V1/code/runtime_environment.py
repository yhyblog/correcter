"""Frozen per-child library/visibility environment; no runtime operation on import."""
import os
from core.contracts import ContractError
from core.handoff import require_handoff_environment
def child_environment(cfg,private_root):
    env=dict(os.environ)
    if env.get('NVIDIA_VISIBLE_DEVICES')!=cfg['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise ContractError('physical visibility changed')
    require_handoff_environment(cfg,env);env.update(cfg['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=cfg['hf_home'],
        OMP_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',
        XDG_CACHE_HOME=str(private_root/'cache'),TORCH_HOME=str(private_root/'cache'),
        TMPDIR=str(private_root/'temporary'),CUDA_CACHE_PATH=str(private_root/'cache/cuda'),
        TORCHINDUCTOR_CACHE_DIR=str(private_root/'cache/inductor'),TRITON_CACHE_DIR=str(private_root/'cache/triton'),LD_LIBRARY_PATH=cfg['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',
        __EGL_VENDOR_LIBRARY_FILENAMES=cfg['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for key in ('LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH'):env.pop(key,None)
    return env
