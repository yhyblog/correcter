# Native10 training workflow

This is a separate workflow. ACT-RECAP, `Corrector/src/corrector`, the old small-batch code and all historical results are read-only dependencies. Formal collection/training requires the corresponding new analysis READY release; P0 authorization does not release main collection or optimizer updates.

Current stage artifacts are under `Corrector/outputs/native10_training_20260916`; progress and review are `coordination/NATIVE10_EXECUTOR_STATUS.json` and `coordination/NATIVE10_EXECUTOR_REVIEW.md`. Original planned episode IDs are in `preparation/episode_manifest.json`. No source is replenished based on outcomes.

## Semantics

- Actual policy queue capacity is ten from episode reset. The sampler may still generate fifty commands.
- Normal continuation finishes the current raw ten-command commitment. At cut 5 it executes five old commands and samples at 10. An interruption starts ten new commands and samples at 15. All later queues naturally execute ten.
- Natural boundary sampling happens before monitoring; age zero is ineligible. A full ten-step window must remain, so the final eligible midpoint is 285.
- All native commands retain the normal raw interface. Replan executes raw a0; corrections modify only the shared feasible mask. The critic sees the approved bounded representation, audited against actual command differences.
- Suffix randomness pairs episode/cut/repeat/post-prefix decision index. Different policy phases are not represented as identical absolute-time decisions.

## Modules

`semantics.py`, `protocol.py`, `commands.py`, `bank_audit.py` and `storage.py` supply the CPU contracts. `engine.py` and `adapter.py` connect those contracts to frozen real models. `candidates13.py` constructs the training bank without simulation. `diagnostics.py`, `probes.py`, and `legacy_diagnostic.py` implement separately counted technical probes. `runner.py` currently exposes only P0; `audit_p0.py` is a separate evidence review.

`training_design.json` and `TRAINING_SCHEMA.md` distinguish approved training parameters from proposed data masks. Any training implementation added later must use the explicit training stage gate and must not modify P0-frozen files.

## Commands

From the workspace parent:

```bash
bash Corrector/experiments/native10_training_20260916/run_cpu.sh register
bash Corrector/experiments/native10_training_20260916/run_cpu.sh cpu-check
```

Registration is outcome-blind. A pending registration is not runnable. The frozen P0 configuration and code are in `outputs/native10_training_20260916/p0/`; code snapshot and dependency hashes preserve its exact implementation. Do not re-freeze or edit an active stage.

The GPU launcher is the existing read-only `ACT-RECAP/scripts/run_recap_gpu_wave.py`, invoked **inside** `gpu_occupancy_lifecycle.sh run -- ...` with a new-workflow wave spec. Every formal GPU wave reserves all eight GPUs and restores holders after success or failure. No direct GPU launch is part of the CPU commands above.

P0 technical checks precede the 20-episode five-arm comparison. Technical success does not require positive policy gains. Historical anchor comparisons use their original native50/bounded protocol and are implementation diagnostics only.

Budget accounting is append-only in `budget/attempts.jsonl`; independent capture, independent candidate restore, each branch including its internal replay, and each standalone probe count before their first environment reset. Failed attempts remain. The mounted ledger uses a task-specific local `/tmp` lock and recoverable counter cache, avoiding mounted-file `flock` and a full-ledger scan on every branch.
