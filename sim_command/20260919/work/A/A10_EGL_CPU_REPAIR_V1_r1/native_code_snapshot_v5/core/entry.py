"""Independent R/Post/Velocity entry; real samplers/objectives are injected explicitly."""
import numpy as np
from .validation import ContractError
from .vendor_solo import project_solo, audit_solo, array_sha

MATCHING = dict(xyz_rms=.05, gripper_rms=.10, xyz_linf=.15, gripper_linf=.4,
                boundary_clearance=.05, tolerance=1e-6, zero_threshold=1e-10)


class IndependentEntry:
    def __init__(self, sampler, objective_factory, transform_slopes, journal, state_fingerprint):
        self.sampler, self.objective_factory = sampler, objective_factory
        self.slopes = np.asarray(transform_slopes)
        if self.slopes.shape != (4,) or not np.isfinite(self.slopes).all():
            raise ContractError('Four finite original unnormalization slopes required')
        self.journal, self.state_fingerprint = journal, state_fingerprint

    def generate(self, method, context, seed, step):
        if method not in ('R', 'Post', 'Velocity'):
            raise ContractError('Entry method must be fixed before observing its score')
        before = self.state_fingerprint()
        parent = self.journal.enter('intervention_decision', methods=[method], scope='container', environment_step=step)
        sampling_events = []

        def sample(objective=None):
            # Backend hooks log actual flow/Q/backward entries. Counts are never inferred from the method label.
            event = self.journal.enter('anchor_sample' if objective is None else 'guided_sample',
                methods=[method], units={'vla_sampling_calls': 1}, parent=parent,
                environment_step=step, sampling_index=len(sampling_events))
            sampling_events.append(event)
            try:
                plan, stats = self.sampler(seed=seed, objective=objective, mode=method,
                                            journal=self.journal, parent_event=event)
                raw = np.asarray(plan)
                if raw.dtype != np.float32 or raw.shape != (50, 4) or not np.isfinite(raw).all():
                    raise ContractError('Invalid raw50x4 sampler result')
                if stats.get('policy_calls') != 1 or stats.get('fallback') is not None or stats.get('automatic_retry') is not False:
                    raise ContractError('Sampler must prove exactly one call without retry/fallback')
                noise = stats.get('noise_sha256')
                if not isinstance(noise, str) or len(noise) != 64:
                    raise ContractError('Actual designated initial noise identity missing')
                self.journal.finish(event)
                return raw.copy(), stats
            except BaseException as error:
                if event not in self.journal.finished:
                    self.journal.finish(event, error=error)
                raise

        try:
            raw, base_stats = sample()
            metadata = {'method': method, 'seed': seed, 'noise_sha256': base_stats['noise_sha256'],
                        'raw_a0_sha256': array_sha(raw), 'cached_a0_used': False,
                        'other_direction_calls': 0, 'new_acceptance_rule': False}
            arrays = {'raw_a0': raw.copy()}
            if method == 'R':
                plan = raw.copy()  # Never clip the replan arm separately.
            else:
                base = np.clip(raw, -1, 1).astype(np.float32)
                objective = self.objective_factory(context, base, self.journal, parent)
                if method == 'Post':
                    gradient, stats = objective.gradient()
                    if stats.get('value') != 0:
                        raise ContractError('Post objective no longer anchored to its own a0')
                    if hasattr(gradient, 'detach'):
                        gradient = gradient.detach().cpu().numpy()
                    direction = np.asarray(gradient) * self.slopes[None] ** 2
                    arrays['post_command_gradient'] = np.asarray(gradient).copy()
                else:
                    native, native_stats = sample(objective)
                    if native_stats['noise_sha256'] != base_stats['noise_sha256']:
                        raise ContractError('Guided sample did not reuse its own actual initial noise')
                    direction = np.clip(native[:10], -1, 1).astype(float) - base[:10].astype(float)
                    arrays['own_native_raw'] = native
                plan, matching, projected = project_solo(raw, direction, MATCHING)
                arrays.update(projected)
                metadata.update(matching=matching, projection_audit=audit_solo(raw, plan, direction, MATCHING))
                objective.verify()
            if self.state_fingerprint() != before:
                raise ContractError('Generation changed observed context or physical state')
            metadata.update(actual_policy_calls=len(sampling_events), sampling_event_ids=sampling_events,
                            raw_plan_sha256=array_sha(plan), environment_unchanged=True)
            self.journal.finish(parent)
            return plan, metadata, arrays
        except BaseException as error:
            self.journal.finish(parent, error=error)
            raise
