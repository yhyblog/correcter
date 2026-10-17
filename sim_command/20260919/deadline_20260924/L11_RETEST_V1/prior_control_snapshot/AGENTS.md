# Current workspace rules

## GPU occupancy — current user-provided rule (2026-09-22)

- Keep occupancy holders outside formal compute. Throughout a formal wave, stop **all** holder GPU computation, including model loading, gaps and GPUs whose jobs finish early. Restore only after the entire formal process family exits, including failures. Do not start idle-subset or tail auxiliary holders.
- Prefer useful approved work on all eight GPUs. Low utilization alone does not authorize an unplanned experiment or a holder alongside formal work. Never terminate unrelated processes.
- Start/check the local persistent guard through `/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py start` and `gpu_occupancy_lifecycle.sh status`. Formal work uses `/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh run -- COMMAND ...`. Confirm own holder descendants have exited before formal GPU entry. Avoid duplicate guards/nested formal.lock.
- Runtime state in `/tmp/gpu_occupancy_guard/` is host-local. Shared log filenames do not establish another host's status. Sandbox NVML failure is not proof of host driver failure. A container/machine restart needs actual recovery checks; a terminal disconnect does not justify duplicate work.
- The previous September21 idle-holder override is superseded prospectively by the current user-provided rule. Historical deviations remain recorded; do not rewrite their evidence.

## Corrector D24 execution scope

These project-specific rules apply to Corrector, not unrelated projects.

- Read the current task/authorization and `Corrector/sim_command/20260919/deadline_20260924/ABC_ASSIGNMENT_V1.md`. A handles pi05-MT50 main/E6/external comparisons; B handles E1 and LIBERO plus completed Smol/X Post; C independently handles Smol/X Velocity. Preserve already admitted jobs and avoid exact duplicate units.
- New C executor starts with `Corrector/sim_command/20260919/deadline_20260924/C_SERVER_ONBOARDING.md`. Its role is registered but hardware/host/thread must be observed locally. Never reuse another node's PID, GPU UUID, thread ID or launcher identity.
- User authorized necessary algorithm adaptation and the current experiment list. No per-batch analysis approval, full-state/MJB equality proofs, exhaustive hashes, million-event ledgers, repeated whole test suites, or separate GPU preflights. Check model/action units, legitimate observations, source splits and actual outcomes; use first planned episodes.
- No remaining475 collection, no repeated completed N/Post/main/standalone/pilot/SFT. No test-based model or threshold selection. Missing/technical outcomes are not success=false. Preserve original failures and label log-derived results.
- Only analysis edits shared CONTROL/TASK_BOARD/dispatch decisions. Executors write their node-specific work/results/receipts/identity and read frozen shared inputs. Use private code/environment adaptations; do not modify another live node's code, claims or packages. No shared data/weight deletion without the existing exact-path decision.
- Deadline: stop new experiment admissions September23 20:00 Beijing, final tables September23 23:00; submission September24 20:00. Do not restore superseded historical collection or approval gates.

## Long tasks and independent nodes

- Run finite detached, host-scoped queues with durable unique claims, process groups, heartbeats, actual result files and cleanup. Normal already-authorized batches continue automatically. No cross-node runtime/exit barrier.
- Register a completion/failure event for the fixed original executor thread; persist an event ACK when handled. Transport acceptance is not proof of wakeup. Do not use --last, a substitute thread, permission bypass, or recursive callbacks. Missing generic callback certification does not block useful authorized compute.
- Once real model readiness/progress and the terminal trigger are recorded, publish STABLE_HANDOFF and end the LLM turn. Lightweight process/time/resource supervision stays alive; do not spend tokens in long wait/tail loops. Notification retries never duplicate scientific launches.
- Ordinary capacity checks suffice. Target eight useful GPUs; if impossible report the actual resource constraint and executable concurrency, not a speculative guarantee. Keep occupancy cost separate from scientific cost, and do not call sampled utilization a continuous guarantee.

Historical AGENTS text is preserved at `Corrector/sim_command/20260919/deadline_20260924/archive/AGENTS_before_C_20260922.md`; it is not the current execution authority.

## Autonomous recovery and queue progress — user rule (2026-09-22)

- Apply `Corrector/sim_command/20260919/deadline_20260924/AUTONOMOUS_RECOVERY_AND_SKIP_V1.md`. Executors diagnose and privately repair engineering failures, then resume only unfinished units within current science scope and finite budgets; routine repairs do not need per-retry analysis approval. Preserve valid scientific failures as well as successes; do not replay completed units or healthy process families.
- If a scientific/ownership/resource decision needs analysis, persist and report the issue with an 1800-second response deadline. Continue independent authorized work immediately when available. After 30 minutes without an actionable analysis decision, keep the issue as blocked/deferred and advance to the next eligible queue task. A delivery receipt or ordinary ACK does not reset the deadline.
- A blocked task must not stall unrelated work. If every remaining task is truly blocked, publish explicit NO_RUNNABLE_TASKS reasons and retain lightweight dependency monitoring; do not invent work or bypass prerequisites. Only complete Post development selects the common loss; Velocity inherits that loss and continues for other work, outside this paper's final presentation.
- Register this as an additional operational directive, not a replacement live runtime authorization. Do not drain a healthy chain merely to publish an update. Whole-formal-wave holder shutdown, unique unit ownership, cancellation decisions and the deadline still apply.

## Quota-independent execution — user rule (2026-09-22)

- Apply `Corrector/sim_command/20260919/deadline_20260924/QUOTA_INDEPENDENT_AUTORUN_V1.md`. Prequeue all remaining authorized stages in finite detached Python/shell supervisors. Normal stage advancement, deterministic Post-only selection, ownership publication/consumption, predefined recovery and exports must not require an LLM turn, callback success or analysis ACK.
- Prioritize deploying missing automation before the conversation quota is exhausted. Preserve healthy processes and completed units. Notification failure only persists an outbox entry; it must not stop scientific work. Encode known recovery cases, retain unresolved issues and advance independent eligible work under the existing 30-minute rule. Do not claim all unforeseen bugs can be repaired without an executor.
