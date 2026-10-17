#!/usr/bin/env bash
# Usage: bash launchers/runtime.sh <environment-id> <command> [args...]
# No install, download, training or upload happens unless the command requests it.
set -euo pipefail
project_dir='/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/projects/vla-baselines'
workspace_dir='/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace'
environment_id=${1:?environment id required}
shift
case "$environment_id" in
  mw-pi05-legacy|mw-smolvla-lr044|mw-xvla-lr044|pi05-openpi-jax|libero-sim-openpi) ;;
  *) printf 'Unknown environment: %s\n' "$environment_id" >&2; exit 2 ;;
esac
environment_prefix="$workspace_dir/environments/$environment_id"
if [[ "$environment_id" == mw-pi05-legacy ]]; then
  environment_prefix="$workspace_dir/environments/lerobot"
fi
test -x "$environment_prefix/bin/python"
export VIRTUAL_ENV="$environment_prefix"
export PATH="$environment_prefix/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONNOUSERSITE=1
export PYTHONPATH="$project_dir"
if [[ "$environment_id" == libero-sim-openpi ]]; then
  # Required by the official LIBERO example: its legacy setup.py does not expose
  # the namespace package through the editable installation alone.
  export PYTHONPATH="$PYTHONPATH:$workspace_dir/projects/upstream/openpi-215abfb/third_party/libero"
fi
export HF_HOME="$workspace_dir/cache/shared-hub"
if [[ "$environment_id" == mw-pi05-legacy ]]; then
  # This cache contains only a link to the already-pinned tokenizer, no token file.
  export HF_HOME="$workspace_dir/cache/legacy-pi05"
fi
export HF_LEROBOT_HOME="$workspace_dir/cache/lerobot-openpi"
export HF_DATASETS_CACHE="/tmp/corrector_C_N_gaps/datasets/$environment_id"
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export HF_DATASETS_DISABLE_PROGRESS_BARS=1
export HF_HUB_DISABLE_TELEMETRY=1
export HF_HUB_DISABLE_PROGRESS_BARS=1
export WANDB_MODE=disabled
export WANDB_DISABLED=true
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=${VLA_CPU_THREADS:-4}
export XDG_CACHE_HOME="/tmp/corrector_C_N_gaps/cache/$environment_id"
mkdir -p "$XDG_CACHE_HOME/numba"
export NUMBA_CACHE_DIR="$XDG_CACHE_HOME/numba"
export OPENPI_DATA_HOME="$workspace_dir/cache/openpi"
export LIBERO_CONFIG_PATH="$workspace_dir/assets/libero/f78abd68/config"
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export XLA_PYTHON_CLIENT_PREALLOCATE=false
# Verified single-node profile. Inherited AF_INET6/=eth0 completed collectives
# but hung during ncclCommDestroy on this host; IPv4 loopback exits cleanly.
case ${VLA_DISTRIBUTED_PROFILE:-single_node} in
  single_node)
    export NCCL_SOCKET_FAMILY=AF_INET
    export NCCL_SOCKET_IFNAME='=lo'
    export NCCL_IB_DISABLE=1
    export NCCL_NVLS_ENABLE=0
    export NCCL_DEBUG=${VLA_NCCL_DEBUG:-WARN}
    ;;
  inherit) ;; # Multi-node is NOT verified by this project's preparation tests.
  *) printf 'Unknown distributed profile\n' >&2; exit 2 ;;
esac
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
# Keep simulator device selection independent of CUDA_VISIBLE_DEVICES, which
# may be empty on the CPU-only LIBERO client or remapped on a model server.
export MUJOCO_EGL_DEVICE_ID=${VLA_EGL_DEVICE_ID:-0}
package_dir=$("$environment_prefix/bin/python" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
export LD_LIBRARY_PATH="$package_dir/nvidia/cudnn/lib:$package_dir/nvidia/cublas/lib:$package_dir/nvidia/cuda_runtime/lib:$package_dir/torch/lib"
if [[ ${VLA_RENDERER:-mesa} == mesa ]]; then
  mesa_prefix=$(readlink -f "$workspace_dir/environments/mesa-render")
  export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$mesa_prefix/lib"
  export LIBGL_DRIVERS_PATH="$mesa_prefix/lib/dri"
  export __EGL_VENDOR_LIBRARY_FILENAMES="$mesa_prefix/share/glvnd/egl_vendor.d/50_mesa.json"
  export LIBGL_ALWAYS_SOFTWARE=1
  export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
  export GALLIUM_DRIVER=llvmpipe
  export EGL_PLATFORM=surfaceless
fi
exec "$@"
