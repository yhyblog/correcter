# C finite Velocity wave

Original C thread:01a0c793-10d2-7791-a250-fd65d88e1ccb.
Observed host:trial-303269581-trialrun-303269581-worker-0.
Authoritative identity:../../../../nodes/C/identity.json (resolve from campaign).

MW_VELOCITY_BATCH.json assigns frozen500 sources per base across4 resident
workers each. batch.py owns8 worker process groups under one inherited
formal.lock. post_job.py owns each feature server and base client, keeping
the reservation in both. No nested lifecycle, holder, N/Post/SFT execution.

The job supervisor enforces12-hour jobs,30-minute episodes, stop controls,
and drains owned process groups before releasing the full-wave reservation.
Results are authoritative per-source RESULT.json. Optional stats failures
do not erase a core terminal. Scientific unit claims are unique across
notifications. Root task total budget2400; this wave plans1000 and no dev.
No automatic scientific retry. One concretely diagnosed correction is
authorized per technical failure, with a new attempt record preserving the
old claim/terminal; successful sources must never re-enter.

Completion is watched by wakeup.py through the C-only durable registration
and outbox. It uses `codex queue --thread EXACT_UUID` while the original
writer owns the thread, otherwise `codex exec resume EXACT_UUID`. It waits
for an inactive original turn and preserves its model/permissions/profile.
Only a new original handler turn containing the event ID can write an ACK.
Transport acceptance alone does not prove resume. Two bounded ACK-only
selftests are armed (interactive route and after original writer release).
No --last, new thread, permission override, recursive callback or blind
retry of an uncertain delivery. Notifier failure does not launch compute.

observe.py publishes small process/RAM/progress records and STABLE_HANDOFF
after all8 models are resident and each base has a real terminal. It exits
after the wave terminal and observed8-holder restoration, or records a
restoration timeout. No LLM waiting is needed after stable publication.

On a terminal callback, inspect C results, missing/technical rows, immutable
N/Post pairings and OCCUPANCY_RESTORATION_OBSERVED.json. If needed finish
allowed repairs and paired summaries, then write the event ACK with its
audit reference. If everything is done, return the two result tables.

Host/container restart is not terminal closure. There is no installed boot
autostart: verify boot/host, live process identities, durable unit claims,
formal reservation and local guard before any explicit recovery. Do not
automatically replay the consumed batch start command.
