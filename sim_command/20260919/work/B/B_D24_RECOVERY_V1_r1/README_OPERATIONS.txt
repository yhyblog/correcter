B D24 CONTROL-read recovery (event B_422445bd68021930284fe3fd62016937)

The original X-VLA r1 supervisor failed before scientific entry while reading CONTROL. Its original claim and missing RESULT are preserved; RESULT_RECONCILED.json records the diagnosis, without inventing a direct exit code.

Current detached order:
1. D24_N_CONTROL_REPAIR_r2: 7 Smol workers (280 untouched sources) plus 1 LIBERO spatial worker (72 untouched sources and 1 diagnosed corrected retry), all eight GPUs.
2. D24_XVLA_r2: waits for the above; existing eight-rank, seed42/global64 entry, at most30000 updates or six hours, last complete checkpoint.
3. D24_LIBERO_UNSTARTED_r3: waits for both; eight workers, 279 sources never claimed by the interrupted LIBERO repair.

Do not launch these configurations again. All have durable claims, host/PID/start identities and registered terminal triggers. Original completed258 episodes and five consumed unknown sources are preserved; the five explicit technical failures from the second LIBERO interruption are excluded from the unstarted-only queue. New recovery results add to, rather than replace, retained results. E1 remains48 complete jobs/192000 updates.

The private reader waits up to30 seconds at metadata boundaries for transient ENOENT/ESTALE/EIO/EAGAIN/ETIMEDOUT or partial JSON. No cached authorization substitutes for failed validation. Global/B stops and changed SHA-bound B grants remain enforced. Seven bounded CPU checks passed. No original running workers, shared CONTROL, A output, model, data, or environment was rewritten.

Each batch uses the existing formal GPU lifecycle and reaps owned descendants before releasing its reservation. Completion/failure events go to the fixed original B thread; A never waits for B. See STABLE_HANDOFF.json for actual progress and identities. Check a future event against those claims before any recovery; never replay completed or unknown sources.
