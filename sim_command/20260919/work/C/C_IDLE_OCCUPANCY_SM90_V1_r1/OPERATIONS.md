# C idle occupancy 90% SM target

Start/recover C's private guard with `/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/C/C_IDLE_OCCUPANCY_SM90_V1_r1/guard.py start` after verifying host/boot and any existing guard identity.

This is the original per-GPU guard with only C host binding, fixed workspace path and idle duty 0.90. It uses the original `/tmp/gpu_occupancy_guard/{daemon.lock,formal.lock,pid,status.json}` and original gpu_hold.py. The shared lifecycle command continues to discover the same active guard, stop all own holders before formal model load, and restore the same90% duty after whole-family exit. Do not start a second guard or holders beside formal compute.

The original shared guard file remains unchanged to avoid changing A/B. Its fallback startup default remains50%; use the C private entry for any verified recovery. Machine/container restart requires identity/recovery verification; this detached daemon survives terminal closure but is not a boot-service certification.

CONFIG records requested SM target separately from holder duty. RESULT stores measured nvidia-smi dmon SM samples. Occupancy runtime is not scientific compute or experiment throughput.
