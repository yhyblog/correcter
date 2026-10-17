# Corrector persistent queue v1

This unpublished collection package implements AUTHORIZATION_V2 and the independent
first-eight gate. A owns the remaining 475 frozen sources; B owns zero common-pool
sources. Original scientific controller, 15 cold branches, C10/C5, terminal s300,
state closure, candidate generation and numeric budgets are retained. No training,
formal evaluation, deletion, source replacement, model reuse or scientific retry.

`commands/start_a.sh` starts one detached A service. Repeating it is an idempotent
control-plane operation, never a repeat of a formal command. The service initially
waits for `P11_A_COMMON_POOL_QUEUE8_FIRST_V1.json` and the matching ready/running
task board entry. `proposal/RELEASE_TEMPLATE.json` is deliberately unauthorized.
The analyst must publish the independent first-eight release. If that release
explicitly enables continuation, machine acceptance of its actual saved evidence
unlocks the remaining fixed batches without chat or per-batch releases.

`commands/join_b.py --node B` is the B-only entry. The B host must execute it itself.
It verifies current authority, package bytes and host, runs its own tiny detached
CPU/singleton check, then starts a control-plane service awaiting B's independent
stage authorization. It cannot consume A sources or use A GPU bindings. It does
not claim that B scientific stage adapters or training/evaluation grants exist.

One original lifecycle invocation creates qdrain's isolated process group and
passes its existing formal.lock FD. qdrain transfers a duplicate of that SAME open
file description to the outer supervisor using a private local Unix socket. Neither
side reacquires the formal lock. The supervisor retains the FD through fatal-exit
drain and final evidence publication. qdrain uses one persistent PGID with separately
recorded per-batch child membership; each batch has a full group-exit/publication
barrier before the next starts. A parent stays on its UUID for all cold repeats.
The SHA-bound OCCUPANCY_OVERRIDE_V1 takes precedence over older all-holder-off
clauses. Assigned/pending/loading cards stay holder-free. A completed parent must
have a proven branch-family exit before its card becomes eligible for a private
auxiliary holder; no holder is inserted between that parent's cold branches.
Before any later formal Popen, the scheduler records a stop request and observes
its own holder manager and private-session descendants exiting, then records the
entry ACK. It signals no unrelated process and performs no additional GPU query
for that barrier. Idle eligibility also requires a fresh, empty reserved snapshot
from the existing guard. Auxiliary duty, intervals and existing utilization
samples are separate from scientific budgets. A duty setting is not utilization.
All auxiliary sessions must exit and their evidence be published before the
original same lock FD is released to restore the shared guard. Unknown cleanup
retains the reservation; it never permits another formal entry.

The old 475-source collection stage was superseded and disabled in current queue
CONTROL. This package has never been deployed, and its operational patch is not
proof of an active future D24 runner. No package/READY or new scientific grant is
published by this change. Frozen source plans, claims, shared guard and completed
launchers remain unchanged. See OCCUPANCY_OVERRIDE_READY.json for the narrow CPU
checks and handoff evidence; applying this adapter to a future authorized runner
must precede its launch.

Source, command and budget opportunities are one-shot. The shared ledger publishes
immutable CAS generations via atomic exclusive hard links (tested on this FUSE
mount); it does not depend on shared-filesystem flock or lease expiry. Local service
and formal locks stay in /tmp. Full per-source caps are charged on reservation and
never recycled into extra sources. Missing command/exit/cost evidence blocks new
admission. Three consecutive technical parent failures of the same category stop
the node. Legal early success or masked/partial targets do not create replacement
sources. Technical failures are never relabeled negative task outcomes.

`RESOURCE_ADMISSION.json` requests eight formal parents. 64 GiB per worker is an
engineering allowance, not a measured minimum. The visible host has ample RAM;
container memory limits, RSS/VRAM peaks, actual shared I/O and project quota remain
unknown. Runtime capacity and memory planning gates fail closed without silently
falling back to two. statvfs on the shared FUSE mount is not a physical quota.
All scientific caps stay in their private ledgers. Control-plane metrics, source
transactions, timers, FD handoff and notification costs are quoted separately in
`CONTROL_PLANE_AUX.json`. GPU utilization is sampled, with a clearly labeled idle
estimate and unobserved gaps; memory allocation is not treated as utilization.

Machine validation streams the saved private journals, verifies caps, exact
captured-field/MJB closure, public/sidecar source and split, repeat qualification,
alias masks and independent pair labels, then seals a streamed artifact manifest.
It is not analysis acceptance, a hidden-state equivalence theorem, or a method
ranking. `physical_equality_proven` remains null.

The service is independent of this terminal and survives terminal disconnects.
There is no systemd/container boot hook in this environment: after a host/container
restart, run the same start command once. Active/unknown durable jobs are blocked
for reconciliation; no timeout, lease expiry or daemon restart replays a claim.
Write `nodes/A/STOP.json` to request no new batch admissions and drain the current
batch. This is not an authorization to delete that record or restart failed work.

Terminal notifications are durable, deduplicated and addressed only to the original
node executor thread. The CLI queues to an existing writer, or uses exact-UUID
`codex exec resume` when its native writer lock is free. No model/permission bypass
flags or parallel writer are used. Transport acceptance is separate from the
original handler ACK. Offline resume and host restart limitations are reported
according to actual callback evidence; a README or queue message ID is not proof.
