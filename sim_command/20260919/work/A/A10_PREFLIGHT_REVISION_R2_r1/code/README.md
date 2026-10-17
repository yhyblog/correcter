# A10 isolated CPU preparation, preflight revision R2 / code v4

This package prepares the P00 contracts. Importing core modules does not initialize a simulator, CUDA or a model.
The only real preflight entry is `preflight_pi05.py`; `launch_preflight.py` checks this campaign's newly released,
identity-bound finite proposal before entering the GPU lifecycle wrapper. P00 cannot pass that gate.

`core/vendor_solo.py` copies the completed standalone own-direction matcher with dependency imports changed.
`core/vendor_dependencies.py` contains exact extracted numpy helpers. `basis_manifest.json` identifies their source.
`legacy_basis` retains the previous engine/guidance/actions/critic as read-only references; its old experiment
protocol, models selected implicitly by old paths, READY and budget are never used as authorization.
`core/entry.py` preserves independent own a0, Post S-squared metric, same-noise Velocity, raw/mask/tail invariants.
It accepts actual sampler and objective callbacks; a new scientific runtime must bind D/G0/Q and instrument
all flow/critic/backward calls before that runtime is released. GPU Post/Velocity numerics are not validated here.
No score acceptance filter, method selection, random fallback or sampler retry is introduced.

`core/scheduling.py` and `core/runner.py` implement native H and intervention C clocks. Success/termination
precedes monitoring. After C10 the generated tail is discarded and a new nativeH plan is sampled.
N may request research-only shadow monitoring. An observation backend must supply true separate termination
flags; historical done is never split by guessing. Technical exceptions retain durable failed entries.

The public interface remains immutable `results/A/A10/interface_v1`.
`core/validation.py` adds semantic checks, parent-split and contiguous branch/suffix validation.
`core/accounting.py` records entered/returned/failed operations. Actual and method deployment counts derive
from unique event references; shared data never divides a0 cost. Event parents have no duplicate units.
Timing aggregates remove parent/child overlap, retain clocks and missing measurements, and label reconstruction
as an estimate. No-alarm outcomes and failed-call costs are retained; unresolved technical outcomes and zero
success do not become zero cost per success.
Resource units are identical operation metadata on entered and terminal rows, never incremental charges.
Only unique entered UUIDs count. Missing terminals preserve entered counts as incomplete, not as zero work.
Native E3 methods use unrestricted complete decision/sampling event streams; single episode cut/entry summary
may be null with a reason. The core one-intervention invariant is not imposed on external native systems.
Planned/completed/technical-failed denominators remain distinct until P20 freezes recovery/reporting policy.

`core/resume.py` consumes explicit v1 shard manifests. Hs and methods are unions of allowed entries;
the frozen E4/E9 cell table, not a Cartesian product, gives 16 cells: N/P/V at every H plus R only at H10.
All cells for a source remain on its analysis-assigned host. Source/seed assignment never uses current rank.
Matching complete runs are reused after SHA checks. Existing incomplete claims require an analysis recovery
release; PID age or an expired heartbeat alone never permits takeover or a new physical attempt.

Preflight proposal: one development diagnostic initial state, two native environment instances,
50 task-set resets + one wrapper initialization reset + one diagnostic reset, same observation sampled once at
each H10/20/30/40/50, then one actual native action. Stop at 1 attempt / 5 complete VLA entries / 50 actual
denoise forwards / 1 real control step / 0 backward / 0 monitors / 0 optimization; zero retries. Early errors
stop without replacement. Queue shape, sampler hooks, actual noise, immutable parameter versions, initial/next
images, raw action and true native terminal flags are checked. No complete evaluation episode is claimed.
H/C post-intervention semantics are CPU checked; this small proposal does not claim real corrected-policy validation.

`core/initialization.py` observes the standard initialization without changing its algorithm. Native reset
delegates to reset_model twice: 104 reset_model calls, 5,200 internal do_simulation calls and 26,000 initialization
physics substeps. The single first 30Hz policy control has 13 substeps separately. These are overlapping counter
dimensions, not additive episodes. Each source has durable entered/returned/failed rows and pre-entry caps;
returned calls and incomplete entries remain distinct. The external installed MetaWorld/Gymnasium source
manifest is hashed before initialization and bound to the new proposal/release. In-memory hooks are undone on
normal exit; no shared environment file is patched. CPU checks use synthetic callbacks only.

`authorize_cpu.py` is the read-only CPU authorization and SHA command, with no NVML query or lifecycle launch.
Do not use the actual shell launcher as a dry run. The real command requires a new active compute release,
current A task-board assignment, initialization/global budgets, and actual GPU UUID/driver identity.
The 1800-second timeout plus 30-second kill grace covers the diagnostic child, including its repeated hash
verification, imports, model loading, all initialization and diagnostic cleanup. It is not an end-to-end bound.
`run_reserved_diagnostic.py` records the reserved command/timed-child boundaries; the outer launcher records
preparation, reservation, compute, release and restoration observations, including failed exits. Guard polling
continues after release; the launcher observes up to 120 seconds without stopping unrelated work. Missing
timing or incomplete journals remain null/incomplete; no automatic retry is permitted.

`vendor_backend` copies the original lazy PI0.5 loader and contracts exactly. `vendor_vla/src` is a 4MB frozen
source dependency, not a copied environment or model. The runtime uses the persistent SFT directory, pinned
tokenizer and existing immutable environment versions. No downloads, old cache restoration or environment upgrades.

Wave policy: this minimal proposal is A-only and the launcher rejects multi-host releases. A/B joint runs need
a separately frozen wave launcher that holds each local lifecycle reservation until every named host records
`compute_exited` for the same wave/code/config/shard, including failed exits. It must never launch idle-subset
holders. The local lifecycle wrapper then restores occupancy for the whole wave. A stale heartbeat is not a
barrier completion. That multi-host production launcher is a P10/A11 deliverable, not silently enabled here.

CPU command artifacts and preflight proposal/quote are published separately. Training shape is a handoff to
B13; exact training seeds, update budgets and common initialization remain analysis/B13 decisions.
MT50 D/G0/Q adaptation is A12; old five-task A4000 is never relabeled as an MT50 model.
