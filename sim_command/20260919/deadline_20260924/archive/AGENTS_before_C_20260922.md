# GPU occupancy policy

## Latest user override (2026-09-21; takes precedence)

The user explicitly requires all eight GPUs to remain in use and reports that
low aggregate utilization below 50% can lead to server shutdown. This overrides
the previous prohibition on idle-subset holders during a formal wave.

- Prefer useful approved tasks across all eight GPUs. When a GPU has no active
  formal work, a supervised auxiliary holder may fill it even while other GPUs
  are running a formal wave. Do not change frozen experiment concurrency,
  sources, seeds, scientific budgets or retry limits to satisfy occupancy.
- Formal tasks have priority on their assigned GPU. Queue launch must stop and
  confirm exit of its own holder descendants before formal GPU entry, including
  model loading. Low utilization does not make an active formal GPU eligible.
  Never terminate unrelated processes or run a holder alongside active formal
  work on the same GPU.
- For the existing Batch3, retain the frozen launcher, guard and formal.lock.
  Its separately recorded temporary supervisor is an explicit user override.
  A reaction to START is not proof of atomic pre-compute handoff: retain timing
  evidence and report unknowns. Do not claim uninterrupted all-holder-off.
- At the end of a temporary supervised wave, stop and reap temporary holders
  before handing idle occupancy back to the original guard. Avoid duplicate
  holder ownership. Keep node/host/boot/PID/start identity and GPU UUID records.
- Record holder runtime, duty and utilization separately from scientific model
  budgets. A 95% duty setting is not measured 95% utilization. The reported 50%
  threshold has no independently known platform aggregation window. Disclose
  occupancy conditions in runtime/throughput comparisons.
- Effective campaign supplement:
  `Corrector/sim_command/20260919/persistent_queue/OCCUPANCY_OVERRIDE_V1.md`
  and its SHA-bound JSON under queue CONTROL.operational_overrides. This
  supplement overrides conflicting older holder clauses, preserving all
  numerical/scientific authorizations.

## Persistent independent task queues

Latest scheduling decision: the next A wave targets exactly eight independent
formal parents on eight GPUs. Verify RAM/cgroup/IO/capacity and publish the
independent first-eight release; do not default to two or add ramp-up probes.
Any smaller executable maximum requires concrete resource evidence. Current
Batch3 remains frozen; its auxiliary holders are not formal throughput.

- A/B run detached host-scoped background queues, independent of the chat or
  terminal. Automatically schedule resource-admitted real work up to eight
  GPUs, with prompt backfill and actual per-GPU utilization records.
- A owns common-pool collection and main Corrector training/evaluation; B owns
  external baselines, ablations and applicability. A never waits for B views,
  readiness, models, shards or exit barriers. B reads immutable A publications.
  B failures pause B only; only final paper aggregation needs both sides.
- Keep a single node reservation across runnable consecutive batches. Use a
  queue-aware entry with inherited ownership; do not nest formal.lock. Apply
  the latest idle-card auxiliary policy within this lifecycle rather than
  blindly starting the shared guard inside a reserved wave.
- Current Batch3 retains its original formal process through completion. No
  hot patch, duplicate launch, or false acceptance from queue delivery.
- A waiting watcher is not a formal compute task; ordinary idle occupancy may
  run. Detached services survive terminal closure; machine/container restart
  needs a verified recovery mechanism, never automatic duplicate execution.

## Existing guard mechanisms

- Persistent per-GPU guard: `gpu_occupancy_guard.py`; start with
  `/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py start`.
- Formal GPU work uses
  `/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh run -- COMMAND ...`.
  It reserves GPUs, releases the original holders and restores after release.
  This alone does not implement the new supervised idle-card override.
- Inspect live status through `gpu_occupancy_lifecycle.sh status`; runtime state
  is in `/tmp/gpu_occupancy_guard/`, logs are `gpu_occupancy_guard.log` and
  `gpu_occupancy_guard.holders.log`. Shared log names are not cross-host proof.
- The original guard polls every five seconds, yields to other compute and
  retries its own holders. Never kill unrelated work to create room.
- A restart of the machine/container requires verified guard/service startup.
  GPU access may require sandbox escalation; sandbox NVML failure does not
  establish host driver failure.

## Long tasks: event-driven executor continuation (user update, 2026-09-21)

- Once a detached job has valid progress and its completion trigger is armed,
  record a stable handoff and end the current conversation turn. Do not keep
  an LLM active with repeated wait/sleep/tail loops. Ordinary lightweight
  process, timeout, occupancy and resource supervision must continue.
- Persist terminal/failed/blocked events in a host-scoped outbox and wake the
  node's fixed original executor thread. Each host invokes its own session.
  A queue message receipt is not proof of wakeup: require the original handler
  to write an event ACK. Verify unattended same-thread resume locally.
- Enforce single-writer session ownership, stable event IDs and idempotent
  handling. Never duplicate compute because of notification retries. Never
  use --last, create a substitute chat, bypass permissions or wake recursively
  on callback completion. Batch terminal events are coalesced.
- The resumed executor checks results and completes audits, then continues
  already-authorized work or returns to event-driven idle. Daemon-approved
  batches do not wait for conversational ACKs; the explicit first8 release
  and new scientific-stage gates still apply. A never waits for B.
- Binding policy: Corrector/sim_command/20260919/persistent_queue/
  LONG_TASK_EVENT_WAKEUP_V1.md and its JSON authorization. Implementation and
  bounded callback self-tests are authorized; actual wakeup readiness must
  be demonstrated, not inferred from a plan or transport success.
