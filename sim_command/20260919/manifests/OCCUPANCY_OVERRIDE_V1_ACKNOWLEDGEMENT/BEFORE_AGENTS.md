# GPU occupancy policy

## Persistent task queues (user update, 2026-09-21)

- Future A/B tasks must run from a persistent, host-scoped background queue;
  closing the Codex conversation or terminal must not stop an admitted task.
- User supplement on 2026-09-21: target useful work on all eight GPUs during
  queued experiments. Two-parent concurrency is a bootstrap setting, not the
  long-term target. Automatically admit up to eight real planned parent jobs
  per host when CPU/RAM/VRAM/storage capacity permits, with prompt backfill.
  Record actual per-GPU utilization and diagnose loading/simulation bottlenecks;
  allocated VRAM alone does not establish high utilization. This does not permit
  holders during active work or a change to an already-frozen running wave.
- On each host, stop **all** holder GPU computation while a real task is active
  or another approved, dependency-ready task can immediately run. Keep the
  reservation across consecutive batches, including preparation, auditing and
  publication. Do not restart holders between such batches or on idle subsets.
- Restore holders only when that host has no runnable approved task and all
  owned task descendants have exited and publication/cleanup is complete.
  Waiting on an unapproved/blocked dependency is idle; an idle queue watcher is
  not a compute task. Never terminate unrelated processes.
- The already-running Corrector Batch3 retains its frozen launcher through
  completion. Migrate future tasks at a verified idle boundary; do not hot-patch
  its guard/launcher. The queue-drain must not nest a second formal.lock
  acquisition. Use one reservation with inherited ownership for child batches.
- The authoritative queue migration and bounded stage authorization is under
  `Corrector/sim_command/20260919/persistent_queue/`. Queue delivery, daemon
  readiness, runtime completion and scientific acceptance remain distinct.
- User supplement: A owns common-pool collection and the main Corrector
  training/evaluation path independently; B owns external baselines, ablations
  and applicability work. A must not wait for B readiness, views, shards or
  exit barriers. B consumes immutable published data/protocol versions; local
  B failures pause B only. The final paper aggregation can wait for both.
- Detached processes survive terminal closure; machine/container restart
  requires a verified service restart/recovery mechanism, not a duplicate job.

## Existing single-wave mechanics

The user requires occupancy holders outside formal compute experiments. During a
formal experiment wave, stop all holder GPU computation to improve efficiency,
including holders on GPUs whose individual jobs finish early. Restore occupancy
after the entire formal wave finishes, including failed commands. This update
was explicitly requested by the user on 2026-09-15 and applies to subsequent tasks.

- Persistent per-GPU guard: `gpu_occupancy_guard.py`; start with
  `/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py start`.
- Launch formal GPU work through
  `/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh run -- COMMAND ...`.
  When the guard is active this reserves all GPUs before releasing holders, so
  holders cannot restart during model loading. Reservation release after command
  exit permits automatic occupancy restoration, including failed commands.
- Formal wave launchers must not start idle-subset holders during a running
  experiment. The ACT-RECAP wave launcher defaults to `hold_idle: false`.
- The guard polls every five seconds, fills idle GPUs independently, yields its
  own holder when another compute process appears, and retries failed holders.
  Never terminate unrelated compute processes to make space for a holder.
- Inspect live status through `gpu_occupancy_lifecycle.sh status`; runtime state
  is in `/tmp/gpu_occupancy_guard/`, logs are `gpu_occupancy_guard.log` and
  `gpu_occupancy_guard.holders.log` in this workspace.
- This daemon survives terminal disconnects, but a machine/container restart
  requires starting it again. Check/start it at the beginning of GPU tasks.
- GPU inspection and execution may require sandbox escalation. A sandbox NVML
  failure is not proof that the host GPU driver is unavailable.
