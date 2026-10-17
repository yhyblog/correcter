# C R_H40 / R_H50 operations

Task: C_D24_R_H40_H50_V1. Runtime package: /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_R_H40_H50_V1
Authorization: /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/R_H_SWEEP_AUTHORIZATION_V1.json
Fixed original C thread: 01a0c793-10d2-7791-a250-fd65d88e1ccb.

The detached service has been started once. Do not launch again when CLAIM.json exists. No same-thread callback or notification retry permits duplicate computation. Authoritative entry/result paths are unit_claims/*.json and runs/*/episodes/*/RESULT.json; a job claim alone does not establish completion. Unknown entries remain consumed/unknown until an explicit reconciliation. Only a concrete repaired technical failure can use one corrected retry; this initial queue has none.

Read HEARTBEAT.json and chain/HEARTBEAT.json for finite queue progress. Per-slot MODEL_READY.json, renderer_identity.json, PROCESS.json and EPISODE_PROGRESS.json are under chain/workers. STABLE_HANDOFF.json is written automatically after all eight real model/render identities and the first formal terminal exist. The LLM should end its turn after this stable handoff and armed terminal registration.

A sole C notifier observes the registered supervisor identity, persists a stable host-scoped terminal event after process exit, and resumes only the original C executor. It preserves existing event ACKs and the prior A Full CPU watcher. No new selftest or callback-completion wakeup is created. Interactive queued callbacks have actual handler ACK evidence; unattended exec-resume readiness is not independently asserted.

On terminal callback: inspect CLAIM/RESULT, source results, chain/MANAGER_EXIT, BEFORE_RESERVATION_RELEASE and RESTORATION; verify exact first-entry/retry/cumulative counts and no live owned family. Finish the C task receipt at /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/C/C_D24_R_H40_H50_V1_RESULT.json using terminal SUMMARY/EPISODES/TASK_RESULTS/PAIRED_COMPARISONS/REPORT. ACK that terminal event via /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/C/C_D24_R_H40_H50_V1_r1/wakeup.py. No historical Velocity/N/Post/SFT reruns.

A normal terminal disconnect needs no restart. A host/container reboot requires identity and durable-claim reconciliation before any further admission. The six-hour stage timeout and September23 12:00 UTC experiment admission cutoff are enforced; holders restore after failures as well as success.
