# Public interface v1

Owner A; immutable publication for P00_PREP_V1 and B10. No experiment is released by this interface.
`interface.schema.json` validates one record. `examples.jsonl` contains seven explicitly synthetic CPU examples.
Record kinds: context, transition, episode, event, chunk, view_manifest, shard_manifest.

All real references require a path plus SHA256 and format; a path's presence alone is not identity verification.
Every null must have a nonempty `missing_reasons` entry using the dotted field path. Missing observations/next observations are not fabricated.
`synthetic://` references are allowed only in records marked synthetic. No synthetic examples may enter a real dataset manifest.
`transition.step` is pre-action state time; `next_step=step+executed_prefix_length`; reward/success sequences and executed actions have that actual length. Success at an action's result state uses step+1 indexing.
Parent episode determines split. Never splice across branch/suffix. Historical revealed-held data may only be historical/development, not new train/test.
Core MW H is10/20/30/40/50, C10, generated50, monitor5, at most one intervention, budget300. E8 may describe different dimensions/lengths only under a separate method contract.
Every complete VLA call emits an entered event before execution and one returned/failed event with the same event_id. Count the entered event once even if the call fails.
`resource_units` gives observed counts; do not infer flow_forward counts from method names. Container events have zero resource units.
Failed/incomplete episode success is null, never a fabricated false label. No-alarm/early-success completed episodes remain in denominators.
`is_deployment_required_for_methods` contains exact method names. A shadow monitor is not attributed to N. `is_research_only=true` requires an empty deployment-method list.
Costs: experiment_actual counts unique executed event IDs; each deployment reconstruction references prefix/own entry/own suffix and counts its referenced events without sharing/dividing a0 cost. Reused output does not execute or charge again.
Entered events use null wall_end/device_elapsed with reasons. Wall timestamps are monotonic seconds in hardware.clock_id. Device elapsed is explicit synchronized/device-event measurement, never assumed equal to host submission time.
Parent/child wall intervals must not be added; report union/root intervals as reconstructed estimates, separate from actual episode/wave wall clocks. Concurrent hardware clocks are separate.
Sampling seeds exclude method and host for same-H paired comparisons; source IDs and H distinguish cross-H trajectories. Explicit analysis shards assign all methods for one source to one host.
No stale heartbeat authorizes takeover. An existing matching completion is reused only after identity/file-SHA validation; incomplete claims require an explicit recovery decision.
B adapters consume this published directory and return records under the same schema. New interface revisions use a new directory and READY; never edit v1 in place.
